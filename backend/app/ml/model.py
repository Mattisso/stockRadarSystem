"""Breakout classifier — sklearn LogisticRegression wrapper."""

from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score

from app.core.logging import get_logger

log = get_logger(__name__)

MODEL_FILENAME = "breakout_classifier.joblib"


class BreakoutClassifier:
    """Wraps a LogisticRegression classifier for breakout prediction."""

    def __init__(self, model_dir: str = "models") -> None:
        self.model_dir = Path(model_dir)
        self._model: LogisticRegression | None = None

    @property
    def is_trained(self) -> bool:
        return self._model is not None

    def train(self, X: np.ndarray, y: np.ndarray) -> dict:
        """Train the classifier. Returns metrics dict."""
        self._model = LogisticRegression(
            max_iter=1000,
            random_state=42,
        )
        self._model.fit(X, y)

        # Stratified cross-validation (only if enough samples per class)
        unique, counts = np.unique(y, return_counts=True)
        min_class_count = counts.min() if len(counts) > 0 else 0
        cv_folds = min(5, min_class_count)

        metrics = {"samples": len(y), "class_distribution": dict(zip(unique.tolist(), counts.tolist()))}

        if cv_folds >= 2:
            cv_scores = cross_val_score(self._model, X, y, cv=cv_folds, scoring="accuracy")
            metrics["cv_accuracy_mean"] = round(float(cv_scores.mean()), 4)
            metrics["cv_accuracy_std"] = round(float(cv_scores.std()), 4)

        log.info("ml.model_trained", **metrics)
        return metrics

    def predict_proba(self, X: np.ndarray) -> float:
        """Return probability of positive class. Returns 1.0 if untrained (cold start)."""
        if self._model is None:
            return 1.0
        proba = self._model.predict_proba(X)
        # Index 1 = positive class probability
        return float(proba[0, 1])

    def feature_importances(self) -> dict[str, float] | None:
        """Return feature importance mapping, or None if untrained."""
        if self._model is None:
            return None
        from app.ml.features import FEATURE_COLUMNS
        if hasattr(self._model, "feature_importances_"):
            values = self._model.feature_importances_.tolist()
        else:
            values = np.abs(self._model.coef_[0]).tolist()
        return dict(zip(FEATURE_COLUMNS, values))

    def save(self) -> Path:
        """Persist model to disk."""
        self.model_dir.mkdir(parents=True, exist_ok=True)
        path = self.model_dir / MODEL_FILENAME
        joblib.dump(self._model, path)
        log.info("ml.model_saved", path=str(path))
        return path

    def load(self) -> bool:
        """Load model from disk. Returns False if no saved model."""
        path = self.model_dir / MODEL_FILENAME
        if not path.exists():
            return False
        self._model = joblib.load(path)
        log.info("ml.model_loaded", path=str(path))
        return True
