"""Persistence helpers for historical feature snapshots and performance metrics."""

from datetime import datetime

from sqlalchemy.orm import Session

from app.engine.l2_pattern_engine import L2PatternSignal
from app.engine.signal_detector import FeatureVector
from app.models.feature_snapshot import FeatureSnapshot
from app.models.performance_metric import PerformanceMetric


class DataLayer:
    """Small repository for 09 historical persistence concerns."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def record_feature_snapshot(
        self,
        feature: FeatureVector,
        signal_id: int | None = None,
        trade_id: int | None = None,
        stage: str | None = None,
        l2_pattern: L2PatternSignal | None = None,
    ) -> FeatureSnapshot:
        snapshot = FeatureSnapshot(
            signal_id=signal_id,
            trade_id=trade_id,
            ticker=feature.ticker,
            stage=stage,
            liquidity_imbalance=feature.liquidity_imbalance,
            spread_compression=feature.spread_compression,
            bid_stacking=feature.bid_stacking,
            volume_acceleration=feature.volume_acceleration,
            order_aggression=feature.order_aggression,
            ml_confidence=feature.ml_confidence,
            composite_score=feature.composite_score,
            pattern_type=l2_pattern.pattern_type.value if l2_pattern else None,
            confidence_score=l2_pattern.confidence_score if l2_pattern else None,
        )
        self.db.add(snapshot)
        self.db.flush()
        return snapshot

    def record_performance_metric(
        self,
        metric_name: str,
        metric_value: float,
        *,
        metric_scope: str = "system",
        metric_unit: str | None = None,
        as_of: datetime | None = None,
        window_days: int | None = None,
    ) -> PerformanceMetric:
        metric = PerformanceMetric(
            metric_name=metric_name,
            metric_scope=metric_scope,
            metric_value=metric_value,
            metric_unit=metric_unit,
            as_of=as_of or datetime.utcnow(),
            window_days=window_days,
        )
        self.db.add(metric)
        self.db.flush()
        return metric
