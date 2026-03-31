"""Buy-side execution agent with retry, duplicate checks, and DB logging."""

import asyncio
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.broker.interface import OrderResult, OrderSide, OrderStatus, OrderType
from app.core.config import settings
from app.core.logging import get_logger
from app.data.tick_buffer import MarketSnapshot
from app.models.signal import Signal
from app.models.trade import Trade, TradeSide, TradeStatus
from app.risk.risk_manager import RiskManager, RiskRejection, TradeParameters

log = get_logger(__name__)


@dataclass
class BuyExecutionOutcome:
    """Successful buy execution details returned to the trade executor."""

    ticker: str
    trade_id: int
    quantity: int
    fill_price: float
    stop_loss: float
    target: float
    order_id: str


class BuyAgent:
    """Execute BUY signals with risk checks, duplicate guards, and retries."""

    ACTIVE_TRADE_STATUSES = (TradeStatus.PENDING, TradeStatus.FILLED, TradeStatus.PARTIAL)

    def __init__(self, broker, risk_manager: RiskManager) -> None:
        self.broker = broker
        self.risk_manager = risk_manager
        self._inflight_tickers: set[str] = set()

    async def execute(
        self,
        db: Session,
        signal_record: Signal,
        latest: MarketSnapshot,
        signal_score: float,
        stage: str | None = None,
    ) -> BuyExecutionOutcome | RiskRejection | None:
        """Execute one buy attempt for a symbol and persist order lifecycle to DB."""
        ticker = signal_record.ticker

        if ticker in self._inflight_tickers:
            log.info("buy_agent.duplicate_skipped", ticker=ticker, reason="inflight")
            return None

        if self._has_active_trade(db, ticker):
            log.info("buy_agent.duplicate_skipped", ticker=ticker, reason="active_trade")
            return None

        self._inflight_tickers.add(ticker)
        try:
            risk_result = await self.risk_manager.evaluate_trade(
                ticker=ticker,
                entry_price=latest.quote.ask,
                signal_score=signal_score,
            )
            if isinstance(risk_result, RiskRejection):
                return risk_result

            params = risk_result
            trade_record = self._create_pending_trade(db, signal_record, params, signal_score)
            order_type, limit_price = self._build_order(latest)

            final_order: OrderResult | None = None
            for attempt in range(1, settings.buy_retry_attempts + 1):
                order = await self.broker.submit_order(
                    ticker=ticker,
                    side=OrderSide.BUY,
                    quantity=params.quantity,
                    order_type=order_type,
                    limit_price=limit_price,
                )
                final_order = order
                trade_record.entry_order_id = order.order_id

                if order.status == OrderStatus.FILLED and order.fill_price is not None:
                    trade_record.status = TradeStatus.FILLED
                    trade_record.entry_price = order.fill_price
                    trade_record.entry_time = datetime.now()
                    trade_record.execution_phase = "managed"
                    signal_record.acted_on = True
                    db.flush()
                    log.info(
                        "buy_agent.entry_filled",
                        ticker=ticker,
                        trade_id=trade_record.id,
                        quantity=params.quantity,
                        fill_price=order.fill_price,
                        order_id=order.order_id,
                        stage=stage,
                    )
                    return BuyExecutionOutcome(
                        ticker=ticker,
                        trade_id=trade_record.id,
                        quantity=params.quantity,
                        fill_price=order.fill_price,
                        stop_loss=params.stop_loss_price,
                        target=params.target_price,
                        order_id=order.order_id,
                    )

                trade_record.status = _to_trade_status(order.status)
                trade_record.execution_phase = "entry_submitted"
                db.flush()

                if attempt >= settings.buy_retry_attempts:
                    break

                if order.status in (OrderStatus.PENDING, OrderStatus.PARTIAL):
                    await self.broker.cancel_order(order.order_id)

                log.warning(
                    "buy_agent.retrying_entry",
                    ticker=ticker,
                    attempt=attempt,
                    order_status=order.status.value,
                )
                await asyncio.sleep(settings.buy_retry_backoff_seconds * attempt)

            if final_order is not None:
                log.warning(
                    "buy_agent.entry_failed",
                    ticker=ticker,
                    final_status=final_order.status.value,
                    order_id=final_order.order_id,
                )
            return None
        finally:
            self._inflight_tickers.discard(ticker)

    def _has_active_trade(self, db: Session, ticker: str) -> bool:
        return (
            db.query(Trade)
            .filter(Trade.ticker == ticker, Trade.status.in_(self.ACTIVE_TRADE_STATUSES))
            .first()
            is not None
        )

    def _create_pending_trade(
        self,
        db: Session,
        signal_record: Signal,
        params: TradeParameters,
        signal_score: float,
    ) -> Trade:
        trade_record = Trade(
            ticker=params.ticker,
            signal_id=signal_record.id,
            side=TradeSide.BUY,
            status=TradeStatus.PENDING,
            quantity=params.quantity,
            entry_price=params.entry_price,
            last_stop_price=params.stop_loss_price,
            stop_loss_price=params.stop_loss_price,
            target_price=params.target_price,
            signal_score=signal_score,
            execution_phase="entry_submitted",
            entry_time=datetime.now(),
        )
        db.add(trade_record)
        db.flush()
        return trade_record

    def _build_order(self, latest: MarketSnapshot) -> tuple[OrderType, float | None]:
        """Choose a market or marketable limit order based on current spread."""
        style = settings.buy_order_style
        bid = latest.quote.bid
        ask = latest.quote.ask
        spread_pct = 0.0 if ask <= 0 else max(0.0, (ask - bid) / ask)

        if style == "market":
            return OrderType.MARKET, None

        if style == "limit" or spread_pct > settings.max_entry_slippage_pct:
            limit_price = round(ask * (1.0 + settings.max_entry_slippage_pct), 4)
            return OrderType.LIMIT, limit_price

        return OrderType.MARKET, None


def _to_trade_status(status: OrderStatus) -> TradeStatus:
    mapping = {
        OrderStatus.PENDING: TradeStatus.PENDING,
        OrderStatus.FILLED: TradeStatus.FILLED,
        OrderStatus.PARTIAL: TradeStatus.PARTIAL,
        OrderStatus.CANCELLED: TradeStatus.CANCELLED,
        OrderStatus.REJECTED: TradeStatus.CANCELLED,
    }
    return mapping.get(status, TradeStatus.PENDING)
