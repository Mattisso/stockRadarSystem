"""Tests for materializing immutable ML training examples."""

from app.ml.training_example_builder import TrainingExampleBuilder
from app.models.feature_snapshot import FeatureSnapshot
from app.models.ml_training_example import MLTrainingExample
from app.models.signal import Signal, SignalType
from app.models.trade import Trade, TradeSide, TradeStatus


def test_materialize_pending_examples_from_closed_trade(db):
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

    snapshot = FeatureSnapshot(
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
    db.add(snapshot)
    db.commit()

    result = TrainingExampleBuilder(db).materialize_pending_examples()
    db.commit()

    assert result.created_count == 1
    row = db.query(MLTrainingExample).one()
    assert row.feature_snapshot_id == snapshot.id
    assert row.label == 1
    assert row.outcome_pnl == 25.0
    assert row.pattern_success is True


def test_materialize_pending_examples_is_idempotent(db):
    signal = Signal(
        ticker="LCID",
        signal_type=SignalType.BREAKOUT,
        score=0.7,
        liquidity_imbalance=0.7,
        spread_compression=0.6,
        bid_stacking=0.7,
        volume_acceleration=0.8,
        order_aggression=0.7,
        outcome_pnl=-10.0,
    )
    db.add(signal)
    db.flush()

    trade = Trade(
        ticker="LCID",
        signal_id=signal.id,
        side=TradeSide.BUY,
        status=TradeStatus.CLOSED,
        quantity=100,
        entry_price=3.0,
        exit_price=2.9,
        pnl=-10.0,
    )
    db.add(trade)
    db.flush()

    db.add(
        FeatureSnapshot(
            signal_id=signal.id,
            trade_id=trade.id,
            ticker="LCID",
            stage="candidate",
            liquidity_imbalance=0.5,
            spread_compression=0.5,
            bid_stacking=0.5,
            volume_acceleration=0.5,
            order_aggression=0.5,
        )
    )
    db.commit()

    first = TrainingExampleBuilder(db).materialize_pending_examples()
    second = TrainingExampleBuilder(db).materialize_pending_examples()
    db.commit()

    assert first.created_count == 1
    assert second.created_count == 0
    assert db.query(MLTrainingExample).count() == 1
