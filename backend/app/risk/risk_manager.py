"""Pre-trade risk management — sizing, limits, and exit conditions."""

from dataclasses import dataclass
from datetime import date
from math import floor

from app.broker.interface import BrokerInterface, Position
from app.core.config import settings
from app.core.logging import get_logger
from app.data.tick_buffer import MarketSnapshot

log = get_logger(__name__)


@dataclass
class TradeParameters:
    """Approved trade details after risk evaluation."""

    ticker: str
    quantity: int
    entry_price: float
    stop_loss_price: float
    target_price: float


@dataclass
class RiskRejection:
    """Rejection reason when a trade fails risk checks."""

    ticker: str
    reason: str


class RiskManager:
    """Enforces pre-trade risk limits and computes position sizing.

    Checks:
    - Daily loss limit
    - Max concurrent positions
    - Position size (dollar cap)
    - Computes stop-loss and target prices
    """

    def __init__(self, broker: BrokerInterface) -> None:
        self.broker = broker
        self._daily_pnl: float = 0.0
        self._last_reset_date: date = date.today()

    def _reset_if_new_day(self) -> None:
        """Reset daily P&L tracker on date change."""
        today = date.today()
        if today != self._last_reset_date:
            log.info("risk_manager.daily_reset", previous_pnl=self._daily_pnl)
            self._daily_pnl = 0.0
            self._last_reset_date = today

    def record_pnl(self, pnl: float) -> None:
        """Record realized P&L from a closed trade."""
        self._reset_if_new_day()
        self._daily_pnl += pnl

    async def evaluate_trade(
        self,
        ticker: str,
        entry_price: float,
        signal_score: float,
        latest: MarketSnapshot | None = None,
    ) -> TradeParameters | RiskRejection:
        """Evaluate whether a trade should be taken.

        Returns TradeParameters if approved, RiskRejection if denied.
        """
        self._reset_if_new_day()

        # Check 1: Daily loss limit
        if self._daily_pnl <= -settings.daily_loss_limit:
            return RiskRejection(
                ticker=ticker,
                reason=f"Daily loss limit reached: ${self._daily_pnl:.2f}",
            )

        # Check 2: Max concurrent positions
        positions = await self.broker.get_positions()
        if len(positions) >= settings.max_concurrent_positions:
            return RiskRejection(
                ticker=ticker,
                reason=f"Max positions reached: {len(positions)}/{settings.max_concurrent_positions}",
            )

        # Check 3: Already holding this ticker
        if any(p.ticker == ticker for p in positions):
            return RiskRejection(
                ticker=ticker,
                reason=f"Already holding position in {ticker}",
            )

        if entry_price <= 0:
            return RiskRejection(ticker=ticker, reason="Invalid entry price")

        execution_entry_price = round(entry_price * settings.execution_chase_multiplier, 4)
        percent_stop = round(
            execution_entry_price * (1.0 - settings.execution_percent_stop_pct),
            4,
        )
        support_stop = self._compute_support_stop(latest, execution_entry_price)
        stop_loss_price = max(percent_stop, support_stop) if support_stop is not None else percent_stop

        if stop_loss_price >= execution_entry_price:
            return RiskRejection(ticker=ticker, reason="Invalid stop price")

        stop_pct = (execution_entry_price - stop_loss_price) / execution_entry_price
        if stop_pct > settings.execution_max_stop_pct:
            return RiskRejection(ticker=ticker, reason="Stop too wide")

        risk_per_share = execution_entry_price - stop_loss_price
        if risk_per_share <= 0:
            return RiskRejection(ticker=ticker, reason="Invalid risk per share")

        risk_quantity = floor(settings.execution_max_dollar_risk / risk_per_share)
        max_notional_quantity = floor(settings.max_position_size / execution_entry_price)
        quantity = min(risk_quantity, max_notional_quantity)
        if quantity <= 0:
            return RiskRejection(
                ticker=ticker,
                reason="No shares allowed under risk limits",
            )

        # Scale target with signal strength: stronger signal → higher target
        score = max(0.0, min(1.0, signal_score))
        target_range = settings.target_profit_per_share_max - settings.target_profit_per_share_min
        target_offset = settings.target_profit_per_share_min + target_range * min(1.0, signal_score)
        target_price = round(execution_entry_price + target_offset, 4)

        log.info(
            "risk_manager.trade_approved",
            ticker=ticker,
            quantity=quantity,
            target_notional=round(quantity * execution_entry_price, 2),
            risk_per_share=round(risk_per_share, 4),
            stop=stop_loss_price,
            target=target_price,
        )

        return TradeParameters(
            ticker=ticker,
            quantity=quantity,
            entry_price=execution_entry_price,
            stop_loss_price=stop_loss_price,
            target_price=target_price,
        )

    def _compute_support_stop(
        self,
        latest: MarketSnapshot | None,
        entry_price: float,
    ) -> float | None:
        if latest is None or latest.order_book is None or not latest.order_book.bids:
            return None

        top_bids = latest.order_book.bids[:3]
        strongest_bid = max(top_bids, key=lambda level: (level.size, level.price))
        support_stop = strongest_bid.price * (1.0 - settings.execution_support_buffer_pct)
        support_stop = round(support_stop, 4)
        if support_stop <= 0 or support_stop >= entry_price:
            return None
        return support_stop

    def check_exit_conditions(
        self, position: Position, current_price: float, stop_loss: float, target: float
    ) -> str | None:
        """Check if a position should be exited.

        Returns "stop_loss", "take_profit", or None.
        """
        if current_price <= stop_loss:
            return "stop_loss"
        if current_price >= target:
            return "take_profit"
        return None
