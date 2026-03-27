"""Feature extraction for ML training and inference."""

import numpy as np
from sqlalchemy.orm import Session

from app.ml.feature_builder import FEATURE_COLUMNS, FeatureBuilder


def extract_training_data(db: Session) -> tuple[np.ndarray, np.ndarray]:
    """Extract labeled training data from persisted feature snapshots and outcomes."""
    training_set = FeatureBuilder(db).build_training_set()
    return training_set.X, training_set.y


def signal_to_features(feature_vector) -> np.ndarray:
    """Convert a FeatureVector dataclass to a 1-row numpy array for prediction."""
    return np.array([[
        feature_vector.liquidity_imbalance,
        feature_vector.spread_compression,
        feature_vector.bid_stacking,
        feature_vector.volume_acceleration,
        feature_vector.order_aggression,
    ]])
