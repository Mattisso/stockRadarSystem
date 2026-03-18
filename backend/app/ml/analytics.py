"""Trade analytics and KPI computation."""

from datetime import datetime, timedelta

import numpy as np
from sqlalchemy.orm import Session

from app.models.signal import Signal, SignalType
from app.models.trade import Trade, TradeStatus


class TradeAnalytics:
    """Computes trading KPIs from historical trade data."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def compute_kpis(self, days: int = 30) -> dict:
        """Compute trading KPIs over the last N days."""
        cutoff = datetime.now() - timedelta(days=days)
        trades = (
            self.db.query(Trade)
            .filter(
                Trade.status == TradeStatus.CLOSED,
                Trade.created_at >= cutoff,
                Trade.pnl.isnot(None),
            )
            .all()
        )

        if not trades:
            return {
                "total_trades": 0, "winning_trades": 0, "losing_trades": 0,
                "total_pnl": 0.0, "win_rate": 0.0, "avg_win": 0.0, "avg_loss": 0.0,
                "profit_factor": 0.0, "sharpe_ratio": 0.0, "avg_hold_time_minutes": 0.0,
                "days": days,
            }

        pnls = [t.pnl for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        total_win = sum(wins)
        total_loss = abs(sum(losses))

        # Hold times
        hold_times = []
        for t in trades:
            if t.entry_time and t.exit_time:
                hold_times.append((t.exit_time - t.entry_time).total_seconds() / 60)

        # Sharpe
        pnl_arr = np.array(pnls)
        sharpe = 0.0
        if len(pnl_arr) > 1 and np.std(pnl_arr) > 0:
            sharpe = float(np.mean(pnl_arr) / np.std(pnl_arr) * np.sqrt(252))

        return {
            "total_trades": len(trades),
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "total_pnl": round(sum(pnls), 2),
            "win_rate": round(len(wins) / len(trades), 4) if trades else 0.0,
            "avg_win": round(total_win / len(wins), 2) if wins else 0.0,
            "avg_loss": round(sum(losses) / len(losses), 2) if losses else 0.0,
            "profit_factor": round(total_win / total_loss, 4) if total_loss > 0 else 0.0,
            "sharpe_ratio": round(sharpe, 4),
            "avg_hold_time_minutes": round(sum(hold_times) / len(hold_times), 1) if hold_times else 0.0,
            "days": days,
        }

    def feature_importance(self, classifier) -> dict:
        """Return feature importances from the trained classifier."""
        importances = classifier.feature_importances()
        return importances or {}

    def signal_accuracy_by_bucket(self, bucket_size: float = 0.1) -> list[dict]:
        """Win rate grouped by score buckets."""
        signals = (
            self.db.query(Signal)
            .filter(
                Signal.signal_type == SignalType.BREAKOUT,
                Signal.outcome_pnl.isnot(None),
            )
            .all()
        )

        if not signals:
            return []

        buckets: dict[str, dict] = {}
        for s in signals:
            bucket_low = round(int(s.score / bucket_size) * bucket_size, 2)
            bucket_high = round(bucket_low + bucket_size, 2)
            key = f"{bucket_low:.2f}-{bucket_high:.2f}"

            if key not in buckets:
                buckets[key] = {"range": key, "total": 0, "wins": 0}
            buckets[key]["total"] += 1
            if s.outcome_pnl > 0:
                buckets[key]["wins"] += 1

        result = []
        for bucket in sorted(buckets.values(), key=lambda b: b["range"]):
            bucket["win_rate"] = round(bucket["wins"] / bucket["total"], 4) if bucket["total"] > 0 else 0.0
            result.append(bucket)

        return result
