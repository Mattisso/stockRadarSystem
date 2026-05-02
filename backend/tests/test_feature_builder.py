"""Tests for ML feature builder and training-set labels."""

from app.ml.feature_builder import FeatureBuilder
from app.ml.training_example_builder import TrainingExampleBuilder
from app.models.feature_snapshot import FeatureSnapshot
from app.models.signal import Signal, SignalType
from app.models.trade import Trade, TradeSide, TradeStatus


def test_build_training_set_from_feature_snapshots(db):
    signal = Signal(
        ticker="AAPL",
        signal_type=SignalType.BREAKOUT,
        score=0.82,
        liquidity_imbalance=0.7,
        spread_compression=0.6,
        bid_stacking=0.8,
        volume_acceleration=0.9,
        order_aggression=0.7,
        outcome_pnl=25.0,
    )
    db.add(signal)
    db.flush()

    trade = Trade(
        ticker="AAPL",
        signal_id=signal.id,
        side=TradeSide.BUY,
        status=TradeStatus.CLOSED,
        quantity=100,
        entry_price=10.0,
        exit_price=10.25,
        pnl=25.0,
    )
    db.add(trade)
    db.flush()

    db.add(
        FeatureSnapshot(
            signal_id=signal.id,
            trade_id=trade.id,
            ticker="AAPL",
            stage="ready_to_buy",
            liquidity_imbalance=0.7,
            spread_compression=0.6,
            bid_stacking=0.8,
            volume_acceleration=0.9,
            order_aggression=0.7,
            ml_confidence=0.55,
            composite_score=0.82,
            pattern_type="bid_stacking",
            confidence_score=0.76,
        )
    )
    db.commit()

    result = TrainingExampleBuilder(db).materialize_pending_examples()
    training_set = FeatureBuilder(db).build_training_set()
    assert result.created_count == 1
    assert training_set.X.shape == (1, 5)
    assert training_set.y.tolist() == [1]
    assert training_set.rows[0]["pattern_success"] is True


def test_build_training_set_skips_unlabeled_rows(db):
    db.add(
        FeatureSnapshot(
            ticker="AAPL",
            stage="candidate",
            liquidity_imbalance=0.4,
            spread_compression=0.5,
            bid_stacking=0.5,
            volume_acceleration=0.4,
            order_aggression=0.4,
            composite_score=0.5,
        )
    )
    db.commit()

    result = TrainingExampleBuilder(db).materialize_pending_examples()
    training_set = FeatureBuilder(db).build_training_set()
    assert result.created_count == 0
    assert training_set.X.shape == (0, 5)
    assert training_set.y.size == 0
