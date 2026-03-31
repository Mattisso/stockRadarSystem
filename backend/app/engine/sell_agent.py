"""Sell-side exit agent with trailing stops, L2 weakness, and emergency exits."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.broker.interface import OrderBook, OrderSide, OrderStatus, OrderType
from app.core.config import settings
from app.core.logging import get_logger
from app.data.tick_buffer import MarketSnapshot
from app.models.signal import Signal
from app.models.trade import Trade, TradeStatus
from app.risk.risk_manager import RiskManager

log = get_logger(__name__)


@dataclass
class OpenPosition:
    """In-memory tracking for fast exit monitoring."""

    ticker: str
    trade_id: int
    quantity: int
    entry_price: float
    stop_loss: float
    target: float
    highest_price: float
    entry_time: datetime


@dataclass
class ExitAssessment:
    """Exit decision and updated trailing state for one position."""

    reason: str | None
    current_price: float
    stop_loss: float
    highest_price: float


class SellAgent:
    """Manage exits with priority on capital protection."""

    def __init__(self, broker, risk_manager: RiskManager) -> None:
        self.broker = broker
        self.risk_manager = risk_manager

    def assess_exit(self, position: OpenPosition, latest: MarketSnapshot) -> ExitAssessment:
        """Update trailing state and decide whether the position should be exited."""
        current_price = latest.quote.bid
        highest_price = max(position.highest_price, latest.quote.last, current_price)

        trailing_stop = round(highest_price * (1.0 - settings.trailing_stop_pct), 4)
        effective_stop = max(position.stop_loss, trailing_stop)
        emergency_stop = round(position.entry_price * (1.0 - settings.emergency_stop_loss_pct), 4)

        if current_price <= emergency_stop:
            return ExitAssessment("emergency_exit", current_price, effective_stop, highest_price)

        elapsed_seconds = max(0.0, (latest.timestamp - position.entry_time).total_seconds())
        min_progress_price = round(
            position.entry_price * (1.0 + settings.execution_min_progress_pct),
            4,
        )
        if (
            elapsed_seconds >= settings.execution_time_stop_seconds
            and highest_price < min_progress_price
            and current_price <= position.entry_price
        ):
            return ExitAssessment("time_stop", current_price, effective_stop, highest_price)

        l2_reason = self._detect_l2_weakness(latest.order_book)
        if l2_reason is not None:
            return ExitAssessment(l2_reason, current_price, effective_stop, highest_price)

        risk_reason = self.risk_manager.check_exit_conditions(
            position=None,
            current_price=current_price,
            stop_loss=effective_stop,
            target=position.target,
        )
        return ExitAssessment(risk_reason, current_price, effective_stop, highest_price)

    async def execute_exit(
        self,
        db: Session,
        position: OpenPosition,
        assessment: ExitAssessment,
    ) -> bool:
        """Submit exit order and persist trade close if the broker fills it."""
        order = await self.broker.submit_order(
            ticker=position.ticker,
            side=OrderSide.SELL,
            quantity=position.quantity,
            order_type=OrderType.MARKET,
        )

        if order.status != OrderStatus.FILLED or order.fill_price is None:
            log.warning(
                "sell_agent.exit_not_filled",
                ticker=position.ticker,
                status=order.status.value,
                reason=assessment.reason,
            )
            return False

        pnl = (order.fill_price - position.entry_price) * position.quantity
        self.risk_manager.record_pnl(pnl)

        trade = db.query(Trade).filter_by(id=position.trade_id).first()
        if trade:
            trade.status = TradeStatus.CLOSED
            trade.exit_price = order.fill_price
            trade.exit_time = datetime.now()
            trade.pnl = pnl

            if trade.signal_id:
                signal = db.query(Signal).filter_by(id=trade.signal_id).first()
                if signal:
                    signal.outcome_pnl = pnl

        log.info(
            "sell_agent.exit_executed",
            ticker=position.ticker,
            reason=assessment.reason,
            fill_price=order.fill_price,
            pnl=round(pnl, 2),
            trade_id=position.trade_id,
            order_id=order.order_id,
        )
        return True

    def _detect_l2_weakness(self, order_book: OrderBook | None) -> str | None:
        if order_book is None or not order_book.bids or not order_book.asks:
            return None

        bid_liquidity = sum(level.size for level in order_book.bids[:5])
        ask_liquidity = sum(level.size for level in order_book.asks[:5])
        total = bid_liquidity + ask_liquidity
        if total <= 0:
            return None

        imbalance = bid_liquidity / total
        if imbalance < settings.l2_exit_imbalance_threshold:
            return "l2_weakness"
        return None
