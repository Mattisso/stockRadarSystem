"""Retraining orchestration for the breakout classifier."""

from app.data.data_layer import DataLayer
from app.core.logging import get_logger
from app.core.metrics import ML_MODEL_TRAINED, ML_RETRAIN_TOTAL
from app.ml.feature_builder import FeatureBuilder
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
            training_set = FeatureBuilder(db).build_training_set()
            X, y = training_set.X, training_set.y

            if len(y) < self.min_samples:
                ML_RETRAIN_TOTAL.labels(status="skipped").inc()
                log.info("ml.retrain_skipped", samples=len(y), min_required=self.min_samples)
                return None

            metrics = self.classifier.train(X, y)
            metrics["wins"] = int(y.sum())
            metrics["losses"] = int((y == 0).sum())
            pattern_successes = sum(1 for row in training_set.rows if row["pattern_success"])
            metrics["pattern_success_rate"] = round(pattern_successes / len(training_set.rows), 4)
            self.classifier.save()
            data_layer = DataLayer(db)
            data_layer.record_performance_metric(
                "ml_cv_accuracy_mean",
                float(metrics.get("cv_accuracy_mean", 0.0)),
                metric_scope="ml",
                metric_unit="ratio",
                window_days=None,
            )
            data_layer.record_performance_metric(
                "pattern_success_rate",
                float(metrics["pattern_success_rate"]),
                metric_scope="ml",
                metric_unit="ratio",
                window_days=None,
            )
            db.commit()
            ML_RETRAIN_TOTAL.labels(status="success").inc()
            ML_MODEL_TRAINED.set(1)
            log.info("ml.retrain_complete", **metrics)
            return metrics
        except Exception:
            db.rollback()
            ML_RETRAIN_TOTAL.labels(status="error").inc()
            log.exception("ml.retrain_error")
            return None
        finally:
            db.close()
