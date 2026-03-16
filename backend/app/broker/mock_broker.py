"""Mock broker for development and paper trading without an IBKR account."""

import random
import uuid
from datetime import datetime

import numpy as np

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

# Simulated NASDAQ sub-$10 universe
MOCK_UNIVERSE: list[dict] = [
    {"ticker": "SIRI", "name": "Sirius XM", "base_price": 3.20, "avg_volume": 8_000_000},
    {"ticker": "ACHR", "name": "Archer Aviation", "base_price": 8.50, "avg_volume": 5_000_000},
    {"ticker": "ABUS", "name": "Arbutus Biopharma", "base_price": 2.80, "avg_volume": 1_500_000},
    {"ticker": "BNGO", "name": "Bionano Genomics", "base_price": 1.45, "avg_volume": 3_200_000},
    {"ticker": "CLOV", "name": "Clover Health", "base_price": 1.90, "avg_volume": 4_100_000},
    {"ticker": "DATS", "name": "DatChat Inc", "base_price": 1.15, "avg_volume": 800_000},
    {"ticker": "EOSE", "name": "Eos Energy", "base_price": 3.70, "avg_volume": 2_400_000},
    {"ticker": "FCEL", "name": "FuelCell Energy", "base_price": 1.30, "avg_volume": 6_500_000},
    {"ticker": "GEVO", "name": "Gevo Inc", "base_price": 1.05, "avg_volume": 3_800_000},
    {"ticker": "HIMS", "name": "Hims & Hers", "base_price": 9.50, "avg_volume": 7_200_000},
    {"ticker": "IDEX", "name": "Ideanomics", "base_price": 1.60, "avg_volume": 2_100_000},
    {"ticker": "JAGX", "name": "Jaguar Health", "base_price": 1.25, "avg_volume": 1_200_000},
    {"ticker": "KALA", "name": "Kala Bio", "base_price": 5.40, "avg_volume": 900_000},
    {"ticker": "LCID", "name": "Lucid Group", "base_price": 4.10, "avg_volume": 9_500_000},
    {"ticker": "MNMD", "name": "MindMed", "base_price": 7.80, "avg_volume": 2_800_000},
    {"ticker": "NKLA", "name": "Nikola Corp", "base_price": 1.70, "avg_volume": 5_600_000},
    {"ticker": "OPEN", "name": "Opendoor", "base_price": 2.90, "avg_volume": 4_300_000},
    {"ticker": "PLTR", "name": "Palantir", "base_price": 8.20, "avg_volume": 11_000_000},
    {"ticker": "QUBT", "name": "Quantum Computing", "base_price": 2.10, "avg_volume": 1_600_000},
    {"ticker": "RIVN", "name": "Rivian", "base_price": 9.80, "avg_volume": 8_700_000},
    {"ticker": "SOFI", "name": "SoFi Technologies", "base_price": 7.30, "avg_volume": 10_000_000},
    {"ticker": "TELL", "name": "Tellurian", "base_price": 1.40, "avg_volume": 6_200_000},
    {"ticker": "UXIN", "name": "Uxin Limited", "base_price": 1.10, "avg_volume": 700_000},
    {"ticker": "VNET", "name": "VNET Group", "base_price": 4.60, "avg_volume": 1_100_000},
    {"ticker": "WKHS", "name": "Workhorse Group", "base_price": 1.55, "avg_volume": 3_500_000},
]


class MockBroker(BrokerInterface):
    """Simulated broker for development — generates realistic market data."""

    def __init__(self, initial_balance: float = 50_000.0) -> None:
        self._connected = False
        self._initial_balance = initial_balance
        self._cash_balance = initial_balance
        self._positions: dict[str, Position] = {}
        self._orders: dict[str, OrderResult] = {}
        self._prices: dict[str, float] = {}
        self._subscribed: set[str] = set()
        self._daily_pnl: float = 0.0
        self._tick_count: int = 0

    async def connect(self) -> None:
        self._connected = True
        # Seed prices from mock universe
        for stock in MOCK_UNIVERSE:
            self._prices[stock["ticker"]] = stock["base_price"]
        log.info("mock_broker.connected", balance=self._initial_balance)

    async def disconnect(self) -> None:
        self._connected = False
        log.info("mock_broker.disconnected")

    def _simulate_price_tick(self, ticker: str) -> float:
        """Apply a small random walk to the current price."""
        current = self._prices.get(ticker, 3.0)
        # Random walk: ~0.1% standard deviation per tick
        change = current * np.random.normal(0, 0.001)
        new_price = max(0.01, round(current + change, 4))
        self._prices[ticker] = new_price
        self._tick_count += 1
        return new_price

    async def get_quote(self, ticker: str) -> Quote:
        price = self._simulate_price_tick(ticker)
        spread = round(max(0.01, price * random.uniform(0.002, 0.005)), 4)
        half_spread = spread / 2
        stock = next((s for s in MOCK_UNIVERSE if s["ticker"] == ticker), None)
        vol = stock["avg_volume"] if stock else 1_000_000
        return Quote(
            ticker=ticker,
            bid=round(price - half_spread, 4),
            ask=round(price + half_spread, 4),
            last=price,
            volume=int(vol * random.uniform(0.3, 1.2)),
            timestamp=datetime.now(),
        )

    async def get_order_book(self, ticker: str) -> OrderBook:
        quote = await self.get_quote(ticker)
        bids = []
        asks = []
        for i in range(10):
            offset = (i + 1) * 0.01
            bid_price = round(quote.bid - offset, 4)
            ask_price = round(quote.ask + offset, 4)
            # Randomize sizes — occasionally create larger walls
            bid_size = random.randint(100, 5000)
            ask_size = random.randint(100, 5000)
            if random.random() < 0.1:  # 10% chance of a wall
                bid_size *= random.randint(3, 8)
            if random.random() < 0.1:
                ask_size *= random.randint(3, 8)
            bids.append(OrderBookLevel(price=bid_price, size=bid_size, order_count=random.randint(1, 20)))
            asks.append(OrderBookLevel(price=ask_price, size=ask_size, order_count=random.randint(1, 20)))
        return OrderBook(ticker=ticker, bids=bids, asks=asks, timestamp=datetime.now())

    async def submit_order(
        self,
        ticker: str,
        side: OrderSide,
        quantity: int,
        order_type: OrderType = OrderType.LIMIT,
        limit_price: float | None = None,
    ) -> OrderResult:
        quote = await self.get_quote(ticker)

        # Simulate fill with slippage
        if side == OrderSide.BUY:
            base_price = quote.ask
            slippage = base_price * random.uniform(0, 0.002)
            fill_price = round(base_price + slippage, 4)
        else:
            base_price = quote.bid
            slippage = base_price * random.uniform(0, 0.002)
            fill_price = round(base_price - slippage, 4)

        # Check limit price
        if order_type == OrderType.LIMIT and limit_price is not None:
            if side == OrderSide.BUY and fill_price > limit_price:
                return OrderResult(
                    order_id=str(uuid.uuid4()),
                    ticker=ticker,
                    side=side,
                    quantity=quantity,
                    order_type=order_type,
                    status=OrderStatus.REJECTED,
                    timestamp=datetime.now(),
                )
            if side == OrderSide.SELL and fill_price < limit_price:
                return OrderResult(
                    order_id=str(uuid.uuid4()),
                    ticker=ticker,
                    side=side,
                    quantity=quantity,
                    order_type=order_type,
                    status=OrderStatus.REJECTED,
                    timestamp=datetime.now(),
                )

        order_id = str(uuid.uuid4())
        cost = fill_price * quantity

        # Update positions and cash
        if side == OrderSide.BUY:
            self._cash_balance -= cost
            if ticker in self._positions:
                pos = self._positions[ticker]
                total_qty = pos.quantity + quantity
                pos.avg_cost = (pos.avg_cost * pos.quantity + cost) / total_qty
                pos.quantity = total_qty
            else:
                self._positions[ticker] = Position(
                    ticker=ticker,
                    quantity=quantity,
                    avg_cost=fill_price,
                    market_value=cost,
                    unrealized_pnl=0.0,
                )
        else:  # SELL
            self._cash_balance += cost
            if ticker in self._positions:
                pos = self._positions[ticker]
                realized_pnl = (fill_price - pos.avg_cost) * quantity
                self._daily_pnl += realized_pnl
                pos.quantity -= quantity
                if pos.quantity <= 0:
                    del self._positions[ticker]

        result = OrderResult(
            order_id=order_id,
            ticker=ticker,
            side=side,
            quantity=quantity,
            order_type=order_type,
            status=OrderStatus.FILLED,
            fill_price=fill_price,
            filled_quantity=quantity,
            timestamp=datetime.now(),
        )
        self._orders[order_id] = result
        log.info(
            "mock_broker.order_filled",
            ticker=ticker,
            side=side.value,
            quantity=quantity,
            fill_price=fill_price,
        )
        return result

    async def cancel_order(self, order_id: str) -> bool:
        if order_id in self._orders:
            self._orders[order_id].status = OrderStatus.CANCELLED
            return True
        return False

    async def get_positions(self) -> list[Position]:
        # Update market values
        for ticker, pos in self._positions.items():
            current_price = self._prices.get(ticker, pos.avg_cost)
            pos.market_value = current_price * pos.quantity
            pos.unrealized_pnl = (current_price - pos.avg_cost) * pos.quantity
        return list(self._positions.values())

    async def get_account_summary(self) -> AccountSummary:
        positions = await self.get_positions()
        total_market_value = sum(p.market_value for p in positions)
        return AccountSummary(
            cash_balance=self._cash_balance,
            total_value=self._cash_balance + total_market_value,
            buying_power=self._cash_balance,
            positions=positions,
            daily_pnl=self._daily_pnl,
        )

    async def get_universe(
        self, max_price: float, min_price: float, min_volume: int
    ) -> list[str]:
        return [
            s["ticker"]
            for s in MOCK_UNIVERSE
            if min_price <= s["base_price"] <= max_price and s["avg_volume"] >= min_volume
        ]

    async def subscribe_market_data(self, tickers: list[str]) -> None:
        self._subscribed.update(tickers)
        log.info("mock_broker.subscribed", count=len(tickers))

    async def unsubscribe_market_data(self, tickers: list[str]) -> None:
        self._subscribed -= set(tickers)
        log.info("mock_broker.unsubscribed", count=len(tickers))
