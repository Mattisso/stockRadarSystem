"""Build labeled training rows from historical feature snapshots and outcomes."""

from dataclasses import dataclass

import numpy as np
from sqlalchemy.orm import Session

from app.models.feature_snapshot import FeatureSnapshot
from app.models.signal import Signal, SignalType
from app.models.trade import Trade, TradeStatus

FEATURE_COLUMNS = [
    "liquidity_imbalance",
    "spread_compression",
    "bid_stacking",
    "volume_acceleration",
    "order_aggression",
]


@dataclass
class TrainingSet:
    X: np.ndarray
    y: np.ndarray
    rows: list[dict]


class FeatureBuilder:
    """Constructs ML-ready training data from persisted snapshots and outcomes."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def build_training_set(self) -> TrainingSet:
        snapshots = (
            self.db.query(FeatureSnapshot, Signal, Trade)
            .outerjoin(Signal, FeatureSnapshot.signal_id == Signal.id)
            .outerjoin(Trade, FeatureSnapshot.trade_id == Trade.id)
            .all()
        )

        rows: list[dict] = []
        for snapshot, signal, trade in snapshots:
            outcome_pnl = self._outcome_pnl(signal, trade)
            if outcome_pnl is None:
                continue

            label = 1 if outcome_pnl > 0 else 0
            pattern_success = (
                signal is not None
                and signal.signal_type == SignalType.BREAKOUT
                and outcome_pnl > 0
            )
            row = {
                "ticker": snapshot.ticker,
                "signal_id": snapshot.signal_id,
                "trade_id": snapshot.trade_id,
                "label": label,
                "pattern_success": pattern_success,
                "outcome_pnl": outcome_pnl,
            }
            for column in FEATURE_COLUMNS:
                row[column] = getattr(snapshot, column) or 0.0
            rows.append(row)

        if not rows:
            return TrainingSet(
                X=np.empty((0, len(FEATURE_COLUMNS))),
                y=np.empty(0),
                rows=[],
            )

        X = np.array([[row[col] for col in FEATURE_COLUMNS] for row in rows], dtype=float)
        y = np.array([row["label"] for row in rows], dtype=int)
        return TrainingSet(X=X, y=y, rows=rows)

    @staticmethod
    def _outcome_pnl(signal: Signal | None, trade: Trade | None) -> float | None:
        if trade is not None and trade.status == TradeStatus.CLOSED and trade.pnl is not None:
            return trade.pnl
        if signal is not None and signal.outcome_pnl is not None:
            return signal.outcome_pnl
        return None
