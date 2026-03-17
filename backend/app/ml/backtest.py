"""Signal-replay backtester — replays historical signals against trade outcomes."""

from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
from sqlalchemy.orm import Session

from app.models.signal import Signal, SignalType
from app.models.trade import Trade


@dataclass
class BacktestConfig:
    start_date: datetime | None = None
    end_date: datetime | None = None
    slippage_pct: float = 0.001
    commission_per_share: float = 0.005
    initial_capital: float = 50_000.0
    max_position_size: float = 5_000.0
    score_threshold: float = 0.65


@dataclass
class BacktestResult:
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    trades: list[dict] = field(default_factory=list)


class SignalBacktester:
    """Replays BREAKOUT signals that have linked trades with outcomes."""

    def __init__(self, db: Session, config: BacktestConfig | None = None) -> None:
        self.db = db
        self.config = config or BacktestConfig()

    def run(self) -> BacktestResult:
        query = (
            self.db.query(Signal, Trade)
            .join(Trade, Trade.signal_id == Signal.id)
            .filter(
                Signal.signal_type == SignalType.BREAKOUT,
                Trade.pnl.isnot(None),
            )
        )

        if self.config.start_date:
            query = query.filter(Signal.created_at >= self.config.start_date)
        if self.config.end_date:
            query = query.filter(Signal.created_at <= self.config.end_date)

        query = query.filter(Signal.score >= self.config.score_threshold)
        rows = query.order_by(Signal.created_at).all()

        if not rows:
            return BacktestResult()

        wins: list[float] = []
        losses: list[float] = []
        trade_details: list[dict] = []
        equity_curve: list[float] = [self.config.initial_capital]

        for signal, trade in rows:
            # Apply slippage and commission
            entry = trade.entry_price * (1 + self.config.slippage_pct)
            exit_ = trade.exit_price * (1 - self.config.slippage_pct) if trade.exit_price else entry
            qty = min(trade.quantity, int(self.config.max_position_size / entry)) if entry > 0 else 0
            if qty == 0:
                continue

            commission = self.config.commission_per_share * qty * 2  # entry + exit
            adjusted_pnl = (exit_ - entry) * qty - commission

            if adjusted_pnl > 0:
                wins.append(adjusted_pnl)
            else:
                losses.append(adjusted_pnl)

            equity_curve.append(equity_curve[-1] + adjusted_pnl)
            trade_details.append({
                "ticker": signal.ticker,
                "signal_score": signal.score,
                "entry_price": round(entry, 4),
                "exit_price": round(exit_, 4),
                "quantity": qty,
                "pnl": round(adjusted_pnl, 2),
                "date": signal.created_at.isoformat() if signal.created_at else None,
            })

        total_trades = len(wins) + len(losses)
        total_win = sum(wins)
        total_loss = abs(sum(losses))

        # Max drawdown
        peak = equity_curve[0]
        max_dd = 0.0
        for val in equity_curve:
            if val > peak:
                peak = val
            dd = (peak - val) / peak if peak > 0 else 0.0
            max_dd = max(max_dd, dd)

        # Sharpe ratio (annualized, assuming daily trades)
        returns = np.diff(equity_curve) / np.array(equity_curve[:-1]) if len(equity_curve) > 1 else np.array([])
        sharpe = 0.0
        if len(returns) > 1 and np.std(returns) > 0:
            sharpe = float(np.mean(returns) / np.std(returns) * np.sqrt(252))

        return BacktestResult(
            total_trades=total_trades,
            winning_trades=len(wins),
            losing_trades=len(losses),
            total_pnl=round(total_win - total_loss, 2),
            win_rate=round(len(wins) / total_trades, 4) if total_trades > 0 else 0.0,
            avg_win=round(total_win / len(wins), 2) if wins else 0.0,
            avg_loss=round(sum(losses) / len(losses), 2) if losses else 0.0,
            profit_factor=round(total_win / total_loss, 4) if total_loss > 0 else float("inf") if total_win > 0 else 0.0,
            max_drawdown=round(max_dd, 4),
            sharpe_ratio=round(sharpe, 4),
            trades=trade_details,
        )
