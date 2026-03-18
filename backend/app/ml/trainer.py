"""Retraining orchestration for the breakout classifier."""

from app.core.logging import get_logger
from app.ml.features import extract_training_data
from app.ml.model import BreakoutClassifier

log = get_logger(__name__)


class ModelTrainer:
    """Periodically retrains the classifier when enough labeled data exists."""

    def __init__(self, classifier: BreakoutClassifier, db_session_factory, min_samples: int = 50) -> None:
        self.classifier = classifier
        self.db_session_factory = db_session_factory
        self.min_samples = min_samples

    async def retrain_if_needed(self) -> dict | None:
        """Retrain if sufficient labeled signals exist. Returns metrics or None."""
        db = self.db_session_factory()
        try:
            X, y = extract_training_data(db)

            if len(y) < self.min_samples:
                log.info("ml.retrain_skipped", samples=len(y), min_required=self.min_samples)
                return None

            metrics = self.classifier.train(X, y)
            self.classifier.save()
            log.info("ml.retrain_complete", **metrics)
            return metrics
        except Exception:
            log.exception("ml.retrain_error")
            return None
        finally:
            db.close()
