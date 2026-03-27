"""Tests for 09 data layer persistence helpers and models."""

from datetime import datetime

from app.data.data_layer import DataLayer
from app.engine.l2_pattern_engine import L2PatternSignal, PatternType
from app.engine.signal_detector import FeatureVector, SignalType
from app.models.feature_snapshot import FeatureSnapshot
from app.models.performance_metric import PerformanceMetric
from app.models.signal import Signal


def test_record_feature_snapshot(db):
    signal = Signal(
        ticker="AAPL",
        signal_type=SignalType.BREAKOUT,
        score=0.82,
        liquidity_imbalance=0.7,
        spread_compression=0.6,
        bid_stacking=0.8,
        volume_acceleration=0.9,
        order_aggression=0.7,
    )
    db.add(signal)
    db.flush()

    feature = FeatureVector(
        ticker="AAPL",
        liquidity_imbalance=0.7,
        spread_compression=0.6,
        bid_stacking=0.8,
        volume_acceleration=0.9,
        order_aggression=0.7,
        composite_score=0.82,
        signal_type=SignalType.BREAKOUT,
        ml_confidence=0.55,
    )
    l2_pattern = L2PatternSignal(
        symbol="AAPL",
        confidence_score=0.76,
        pattern_type=PatternType.BID_STACKING,
        liquidity_imbalance=0.7,
        bid_stacking=0.8,
        spoofing_score=0.1,
        momentum_confirmation=0.6,
    )

    snapshot = DataLayer(db).record_feature_snapshot(
        feature,
        signal_id=signal.id,
        stage="candidate",
        l2_pattern=l2_pattern,
    )
    db.commit()

    stored = db.query(FeatureSnapshot).filter_by(id=snapshot.id).one()
    assert stored.ticker == "AAPL"
    assert stored.signal_id == signal.id
    assert stored.pattern_type == PatternType.BID_STACKING.value
    assert stored.confidence_score == 0.76


def test_record_performance_metric(db):
    metric = DataLayer(db).record_performance_metric(
        "win_rate",
        0.63,
        metric_scope="daily",
        metric_unit="ratio",
        as_of=datetime(2026, 3, 27, 0, 0, 0),
        window_days=30,
    )
    db.commit()

    stored = db.query(PerformanceMetric).filter_by(id=metric.id).one()
    assert stored.metric_name == "win_rate"
    assert stored.metric_scope == "daily"
    assert stored.metric_value == 0.63
    assert stored.window_days == 30
