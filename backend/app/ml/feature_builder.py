"""Build labeled training rows from materialized ML training examples."""

from dataclasses import dataclass

import numpy as np
from sqlalchemy.orm import Session

from app.models.ml_training_example import MLTrainingExample

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
    """Constructs ML-ready training data from materialized training examples."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def build_training_set(self) -> TrainingSet:
        examples = self.db.query(MLTrainingExample).order_by(MLTrainingExample.id.asc()).all()

        rows: list[dict] = []
        for example in examples:
            row = {
                "ticker": example.ticker,
                "signal_id": example.signal_id,
                "trade_id": example.trade_id,
                "label": example.label,
                "pattern_success": example.pattern_success,
                "outcome_pnl": example.outcome_pnl,
            }
            for column in FEATURE_COLUMNS:
                row[column] = getattr(example, column) or 0.0
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
