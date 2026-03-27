"""Tests for ModelTrainer learning-loop persistence."""

from app.ml.model import BreakoutClassifier
from app.ml.trainer import ModelTrainer
from app.models.feature_snapshot import FeatureSnapshot
from app.models.performance_metric import PerformanceMetric
from app.models.signal import Signal, SignalType
from app.models.trade import Trade, TradeSide, TradeStatus


def _seed_training_rows(db, count: int = 12):
    for i in range(count):
        pnl = 20.0 if i % 2 == 0 else -10.0
        signal = Signal(
            ticker=f"T{i}",
            signal_type=SignalType.BREAKOUT,
            score=0.6 + (i % 3) * 0.1,
            liquidity_imbalance=0.7,
            spread_compression=0.6,
            bid_stacking=0.7,
            volume_acceleration=0.8,
            order_aggression=0.7,
            outcome_pnl=pnl,
        )
        db.add(signal)
        db.flush()

        trade = Trade(
            ticker=f"T{i}",
            signal_id=signal.id,
            side=TradeSide.BUY,
            status=TradeStatus.CLOSED,
            quantity=100,
            entry_price=10.0,
            exit_price=10.2 if pnl > 0 else 9.9,
            pnl=pnl,
        )
        db.add(trade)
        db.flush()

        db.add(
            FeatureSnapshot(
                signal_id=signal.id,
                trade_id=trade.id,
                ticker=f"T{i}",
                stage="ready_to_buy",
                liquidity_imbalance=0.7,
                spread_compression=0.6,
                bid_stacking=0.7,
                volume_acceleration=0.8,
                order_aggression=0.7,
                ml_confidence=0.5,
                composite_score=signal.score,
                confidence_score=0.65,
            )
        )
    db.commit()


async def test_trainer_persists_learning_metrics(db_session_factory, tmp_path):
    db = db_session_factory()
    _seed_training_rows(db, count=12)
    db.close()

    trainer = ModelTrainer(
        BreakoutClassifier(model_dir=str(tmp_path)),
        db_session_factory,
        min_samples=4,
    )
    metrics = await trainer.retrain_if_needed()

    db = db_session_factory()
    stored = db.query(PerformanceMetric).all()
    assert metrics is not None
    assert metrics["samples"] == 12
    assert any(m.metric_name == "pattern_success_rate" for m in stored)
    assert any(m.metric_name == "ml_cv_accuracy_mean" for m in stored)
    db.close()
