"""Interactive Brokers broker implementation using ib_insync."""

import asyncio
import math
import threading
import time
from datetime import datetime

from ib_insync import IB, Contract, LimitOrder, MarketOrder, ScannerSubscription, Stock, Ticker, Trade

from app.broker.interface import (
    AccountSummary,
    BrokerInterface,
    OrderBook,
    OrderBookLevel,
    OrderResult,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    Quote,
)
from app.core.logging import get_logger

log = get_logger(__name__)

# IB has a 100 active market data line limit
_MARKET_DATA_WARN_THRESHOLD = 80
_MARKET_DATA_MAX = 100


def _safe_float(val: float, default: float = 0.0) -> float:
    """Convert IB's nan values to a safe default."""
    if val is None or math.isnan(val):
        return default
    return float(val)


class IBKRBroker(BrokerInterface):
    """Real Interactive Brokers integration via ib_insync."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7497,
        client_id: int = 1,
        timeout: int = 30,
        max_reconnect_attempts: int = 10,
    ) -> None:
        self._host = host
        self._port = port
        self._client_id = client_id
        self._timeout = timeout
        self._max_reconnect_attempts = max_reconnect_attempts

        self._ib = IB()
        self._ib_loop: asyncio.AbstractEventLoop | None = None
        self._ib_thread: threading.Thread | None = None
        self._connected = False

        self._subscribed: dict[str, Contract] = {}
        self._market_data: dict[str, Ticker] = {}
        self._qualified: dict[str, Contract] = {}

        self._universe_cache: list[str] = []
        self._universe_cache_time: float = 0.0
        self._universe_cache_ttl: float = 60.0

    # ── Event loop bridging ──────────────────────────────────────────

    def _run_on_ib_loop(self, coro):
        """Schedule a coroutine on the IB event loop and return an awaitable future."""
        if self._ib_loop is None or self._ib_loop.is_closed():
            raise RuntimeError("IB event loop is not running")
        future = asyncio.run_coroutine_threadsafe(coro, self._ib_loop)
        return asyncio.wrap_future(future)

    def _start_ib_thread(self) -> None:
        """Start the daemon thread that runs ib_insync's event loop."""
        loop = asyncio.new_event_loop()
        self._ib_loop = loop

        def _run():
            asyncio.set_event_loop(loop)
            loop.run_forever()

        self._ib_thread = threading.Thread(target=_run, daemon=True, name="ib-event-loop")
        self._ib_thread.start()

    # ── Connection management ────────────────────────────────────────

    async def connect(self) -> None:
        self._start_ib_thread()

        async def _connect():
            await self._ib.connectAsync(
                self._host,
                self._port,
                clientId=self._client_id,
                timeout=self._timeout,
            )

        await self._run_on_ib_loop(_connect())
        self._connected = True
        self._ib.disconnectedEvent += self._on_disconnect
        log.info(
            "ibkr_broker.connected",
            host=self._host,
            port=self._port,
            client_id=self._client_id,
        )

    async def disconnect(self) -> None:
        self._ib.disconnectedEvent -= self._on_disconnect
        if self._ib.isConnected():

            async def _disconnect():
                self._ib.disconnect()

            await self._run_on_ib_loop(_disconnect())
        self._connected = False

        if self._ib_loop and self._ib_loop.is_running():
            self._ib_loop.call_soon_threadsafe(self._ib_loop.stop)
        if self._ib_thread:
            self._ib_thread.join(timeout=5)

        log.info("ibkr_broker.disconnected")

    def _on_disconnect(self) -> None:
        """Handle unexpected disconnects with exponential backoff reconnect."""
        self._connected = False
        log.warning("ibkr_broker.disconnected_unexpectedly")

        def _reconnect():
            delay = 1.0
            for attempt in range(1, self._max_reconnect_attempts + 1):
                try:
                    log.info("ibkr_broker.reconnecting", attempt=attempt, delay=delay)
                    time.sleep(delay)
                    # Run connect on the IB loop
                    future = asyncio.run_coroutine_threadsafe(
                        self._ib.connectAsync(
                            self._host,
                            self._port,
                            clientId=self._client_id,
                            timeout=self._timeout,
                        ),
                        self._ib_loop,
                    )
                    future.result(timeout=self._timeout)
                    self._connected = True
                    log.info("ibkr_broker.reconnected", attempt=attempt)
                    # Re-subscribe market data
                    self._resubscribe_market_data()
                    return
                except Exception:
                    log.exception("ibkr_broker.reconnect_failed", attempt=attempt)
                    delay = min(delay * 2, 60.0)

            log.error("ibkr_broker.reconnect_exhausted", max_attempts=self._max_reconnect_attempts)

        # Run reconnect in a separate thread to avoid blocking the IB loop
        threading.Thread(target=_reconnect, daemon=True, name="ib-reconnect").start()

    def _resubscribe_market_data(self) -> None:
        """Re-subscribe all previously subscribed market data after reconnect."""
        if not self._subscribed:
            return
        for ticker, contract in list(self._subscribed.items()):
            try:
                ib_ticker = self._ib.reqMktData(contract)
                self._market_data[ticker] = ib_ticker
            except Exception:
                log.exception("ibkr_broker.resubscribe_failed", ticker=ticker)

    # ── Contract helpers ─────────────────────────────────────────────

    async def _make_contract(self, ticker: str) -> Contract:
        """Create and qualify a Stock contract, using cache."""
        if ticker in self._qualified:
            return self._qualified[ticker]

        contract = Stock(ticker, "SMART", "USD")

        async def _qualify():
            qualified = await self._ib.qualifyContractsAsync(contract)
            return qualified

        qualified = await self._run_on_ib_loop(_qualify())
        if not qualified or qualified[0].conId == 0:
            raise ValueError(f"Failed to qualify contract for {ticker}")

        self._qualified[ticker] = qualified[0]
        return qualified[0]

    # ── Read-only methods ────────────────────────────────────────────

    async def get_quote(self, ticker: str) -> Quote:
        # Use cached market data if subscribed
        if ticker in self._market_data:
            ib_ticker = self._market_data[ticker]
            return Quote(
                ticker=ticker,
                bid=_safe_float(ib_ticker.bid),
                ask=_safe_float(ib_ticker.ask),
                last=_safe_float(ib_ticker.last),
                volume=int(_safe_float(ib_ticker.volume)),
                timestamp=datetime.now(),
            )

        # Otherwise request a snapshot
        contract = await self._make_contract(ticker)

        async def _snapshot():
            t = self._ib.reqMktData(contract, snapshot=True)
            await asyncio.sleep(2)  # wait for snapshot data
            self._ib.cancelMktData(contract)
            return t

        ib_ticker = await self._run_on_ib_loop(_snapshot())
        return Quote(
            ticker=ticker,
            bid=_safe_float(ib_ticker.bid),
            ask=_safe_float(ib_ticker.ask),
            last=_safe_float(ib_ticker.last),
            volume=int(_safe_float(ib_ticker.volume)),
            timestamp=datetime.now(),
        )

    async def get_order_book(self, ticker: str) -> OrderBook:
        contract = await self._make_contract(ticker)

        async def _depth():
            depth = self._ib.reqMktDepth(contract, numRows=10)
            await asyncio.sleep(2)  # wait for depth data to populate
            return depth

        ib_ticker = await self._run_on_ib_loop(_depth())

        bids = [
            OrderBookLevel(
                price=_safe_float(row.price),
                size=int(_safe_float(row.size)),
            )
            for row in ib_ticker.domBids
        ]
        asks = [
            OrderBookLevel(
                price=_safe_float(row.price),
                size=int(_safe_float(row.size)),
            )
            for row in ib_ticker.domAsks
        ]

        # Cancel depth subscription
        async def _cancel():
            self._ib.cancelMktDepth(contract)

        await self._run_on_ib_loop(_cancel())

        return OrderBook(ticker=ticker, bids=bids, asks=asks, timestamp=datetime.now())

    async def get_positions(self) -> list[Position]:
        async def _positions():
            return self._ib.positions()

        ib_positions = await self._run_on_ib_loop(_positions())
        positions = []
        for pos in ib_positions:
            ticker = pos.contract.symbol
            quantity = int(pos.position)
            avg_cost = float(pos.avgCost)

            # Get current price for market value
            try:
                quote = await self.get_quote(ticker)
                current_price = quote.last if quote.last > 0 else avg_cost
            except Exception:
                current_price = avg_cost

            market_value = current_price * abs(quantity)
            unrealized_pnl = (current_price - avg_cost) * quantity

            positions.append(
                Position(
                    ticker=ticker,
                    quantity=quantity,
                    avg_cost=avg_cost,
                    market_value=market_value,
                    unrealized_pnl=unrealized_pnl,
                )
            )
        return positions

    async def get_account_summary(self) -> AccountSummary:
        async def _summary():
            return self._ib.accountSummary()

        async def _pnl():
            pnl = self._ib.pnl()
            return pnl

        summary_items = await self._run_on_ib_loop(_summary())
        pnl_items = await self._run_on_ib_loop(_pnl())

        # Parse account summary tags
        values: dict[str, float] = {}
        for item in summary_items:
            if item.tag in ("TotalCashValue", "NetLiquidation", "BuyingPower"):
                try:
                    values[item.tag] = float(item.value)
                except (ValueError, TypeError):
                    values[item.tag] = 0.0

        daily_pnl = 0.0
        if pnl_items:
            pnl_item = pnl_items[0] if isinstance(pnl_items, list) else pnl_items
            daily_pnl = _safe_float(getattr(pnl_item, "dailyPnL", 0.0))

        positions = await self.get_positions()

        return AccountSummary(
            cash_balance=values.get("TotalCashValue", 0.0),
            total_value=values.get("NetLiquidation", 0.0),
            buying_power=values.get("BuyingPower", 0.0),
            positions=positions,
            daily_pnl=daily_pnl,
        )

    # ── Trading methods ──────────────────────────────────────────────

    async def submit_order(
        self,
        ticker: str,
        side: OrderSide,
        quantity: int,
        order_type: OrderType = OrderType.LIMIT,
        limit_price: float | None = None,
    ) -> OrderResult:
        contract = await self._make_contract(ticker)
        action = "BUY" if side == OrderSide.BUY else "SELL"

        if order_type == OrderType.MARKET:
            ib_order = MarketOrder(action, quantity)
        else:
            if limit_price is None:
                raise ValueError("limit_price required for LIMIT orders")
            ib_order = LimitOrder(action, quantity, limit_price)

        async def _place():
            trade: Trade = self._ib.placeOrder(contract, ib_order)
            # Wait up to 5s for market order fills
            if order_type == OrderType.MARKET:
                for _ in range(50):
                    if trade.isDone():
                        break
                    await asyncio.sleep(0.1)
            return trade

        trade = await self._run_on_ib_loop(_place())

        status = self._map_order_status(trade.orderStatus.status)
        fill_price = None
        filled_qty = 0

        if trade.fills:
            fill_price = sum(f.execution.price * f.execution.shares for f in trade.fills) / sum(
                f.execution.shares for f in trade.fills
            )
            filled_qty = int(sum(f.execution.shares for f in trade.fills))

        order_id = str(trade.order.orderId)
        log.info(
            "ibkr_broker.order_submitted",
            ticker=ticker,
            side=side.value,
            quantity=quantity,
            order_type=order_type.value,
            status=status.value,
            order_id=order_id,
        )

        return OrderResult(
            order_id=order_id,
            ticker=ticker,
            side=side,
            quantity=quantity,
            order_type=order_type,
            status=status,
            fill_price=fill_price,
            filled_quantity=filled_qty,
            timestamp=datetime.now(),
        )

    async def cancel_order(self, order_id: str) -> bool:
        async def _cancel():
            for trade in self._ib.openTrades():
                if str(trade.order.orderId) == order_id:
                    self._ib.cancelOrder(trade.order)
                    return True
            return False

        result = await self._run_on_ib_loop(_cancel())
        log.info("ibkr_broker.cancel_order", order_id=order_id, success=result)
        return result

    @staticmethod
    def _map_order_status(ib_status: str) -> OrderStatus:
        """Map IB order status string to our OrderStatus enum."""
        mapping = {
            "Submitted": OrderStatus.PENDING,
            "PreSubmitted": OrderStatus.PENDING,
            "PendingSubmit": OrderStatus.PENDING,
            "PendingCancel": OrderStatus.PENDING,
            "Filled": OrderStatus.FILLED,
            "Cancelled": OrderStatus.CANCELLED,
            "ApiCancelled": OrderStatus.CANCELLED,
            "Inactive": OrderStatus.REJECTED,
        }
        return mapping.get(ib_status, OrderStatus.PENDING)

    # ── Market data management ───────────────────────────────────────

    async def get_universe(self, max_price: float, min_price: float, min_volume: int) -> list[str]:
        # Return cached result if fresh
        if self._universe_cache and (time.time() - self._universe_cache_time) < self._universe_cache_ttl:
            return self._universe_cache

        sub = ScannerSubscription(
            instrument="STK",
            locationCode="STK.NASDAQ",
            scanCode="TOP_PERC_GAIN",
            abovePrice=min_price,
            belowPrice=max_price,
            aboveVolume=min_volume,
            numberOfRows=50,
        )

        async def _scan():
            results = await self._ib.reqScannerDataAsync(sub)
            return results

        scan_results = await self._run_on_ib_loop(_scan())
        tickers = [sd.contractDetails.contract.symbol for sd in (scan_results or [])]

        self._universe_cache = tickers
        self._universe_cache_time = time.time()

        log.info("ibkr_broker.universe_scan", count=len(tickers))
        return tickers

    async def subscribe_market_data(self, tickers: list[str]) -> None:
        active_count = len(self._subscribed)
        for ticker in tickers:
            if ticker in self._subscribed:
                continue
            if active_count >= _MARKET_DATA_MAX:
                log.error("ibkr_broker.market_data_limit_reached", max=_MARKET_DATA_MAX)
                break
            if active_count >= _MARKET_DATA_WARN_THRESHOLD:
                log.warning(
                    "ibkr_broker.market_data_nearing_limit",
                    active=active_count,
                    max=_MARKET_DATA_MAX,
                )

            contract = await self._make_contract(ticker)

            async def _subscribe(c=contract):
                return self._ib.reqMktData(c)

            ib_ticker = await self._run_on_ib_loop(_subscribe())
            self._subscribed[ticker] = contract
            self._market_data[ticker] = ib_ticker
            active_count += 1

        log.info("ibkr_broker.subscribed", count=len(tickers), active=len(self._subscribed))

    async def unsubscribe_market_data(self, tickers: list[str]) -> None:
        for ticker in tickers:
            contract = self._subscribed.pop(ticker, None)
            self._market_data.pop(ticker, None)
            self._qualified.pop(ticker, None)
            if contract:

                async def _unsub(c=contract):
                    self._ib.cancelMktData(c)

                await self._run_on_ib_loop(_unsub())

        log.info("ibkr_broker.unsubscribed", count=len(tickers), active=len(self._subscribed))
