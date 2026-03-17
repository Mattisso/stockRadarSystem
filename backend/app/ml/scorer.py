"""Hybrid rule + ML scorer."""

from app.ml.features import signal_to_features
from app.ml.model import BreakoutClassifier


class MLScorer:
    """Blends rule-based composite score with ML confidence."""

    def __init__(self, classifier: BreakoutClassifier, weight: float = 0.3) -> None:
        self.classifier = classifier
        self.weight = weight

    def score(self, feature_vector) -> tuple[float, float]:
        """Return (adjusted_score, ml_confidence).

        adjusted_score = (1 - weight) * rule_score + weight * ml_confidence
        When classifier is untrained, ml_confidence = 1.0 so adjusted ≈ rule_score.
        """
        X = signal_to_features(feature_vector)
        ml_confidence = self.classifier.predict_proba(X)
        adjusted_score = (1 - self.weight) * feature_vector.composite_score + self.weight * ml_confidence
        return round(adjusted_score, 4), round(ml_confidence, 4)
