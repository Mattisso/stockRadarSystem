"""Feature extraction for ML training and inference."""

import numpy as np
from sqlalchemy.orm import Session

from app.models.signal import Signal

FEATURE_COLUMNS = [
    "liquidity_imbalance",
    "spread_compression",
    "bid_stacking",
    "volume_acceleration",
    "order_aggression",
]


def extract_training_data(db: Session) -> tuple[np.ndarray, np.ndarray]:
    """Extract labeled training data from signals with known outcomes.

    Returns (X, y) where X is the feature matrix and y is binary labels
    (1 = profitable, 0 = unprofitable).
    """
    signals = (
        db.query(Signal)
        .filter(Signal.outcome_pnl.isnot(None))
        .all()
    )

    if not signals:
        return np.empty((0, len(FEATURE_COLUMNS))), np.empty(0)

    X = np.array([
        [
            getattr(s, col) or 0.0
            for col in FEATURE_COLUMNS
        ]
        for s in signals
    ])
    y = np.array([1 if s.outcome_pnl > 0 else 0 for s in signals])

    return X, y


def signal_to_features(feature_vector) -> np.ndarray:
    """Convert a FeatureVector dataclass to a 1-row numpy array for prediction."""
    return np.array([[
        feature_vector.liquidity_imbalance,
        feature_vector.spread_compression,
        feature_vector.bid_stacking,
        feature_vector.volume_acceleration,
        feature_vector.order_aggression,
    ]])
