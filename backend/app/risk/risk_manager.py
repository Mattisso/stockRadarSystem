"""Pre-trade risk management — sizing, limits, and exit conditions."""

from dataclasses import dataclass
from datetime import date

from app.broker.interface import BrokerInterface, Position
from app.core.config import settings
from app.core.logging import get_logger

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
        self, ticker: str, entry_price: float, signal_score: float
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

        # Position sizing: max_position_size / entry_price, floored to whole shares
        if entry_price <= 0:
            return RiskRejection(ticker=ticker, reason="Invalid entry price")

        quantity = int(settings.max_position_size / entry_price)
        if quantity <= 0:
            return RiskRejection(
                ticker=ticker,
                reason=f"Price ${entry_price:.2f} exceeds max position size ${settings.max_position_size:.2f}",
            )

        # Stop-loss and target prices
        stop_loss_price = round(entry_price * (1.0 - settings.stop_loss_pct), 4)

        # Scale target with signal strength: stronger signal → higher target
        target_range = settings.target_profit_per_share_max - settings.target_profit_per_share_min
        target_offset = settings.target_profit_per_share_min + target_range * min(1.0, signal_score)
        target_price = round(entry_price + target_offset, 4)

        log.info(
            "risk_manager.trade_approved",
            ticker=ticker,
            quantity=quantity,
            stop=stop_loss_price,
            target=target_price,
        )

        return TradeParameters(
            ticker=ticker,
            quantity=quantity,
            entry_price=entry_price,
            stop_loss_price=stop_loss_price,
            target_price=target_price,
        )

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
