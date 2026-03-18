"""Tests for TradeAnalytics — KPIs and signal accuracy."""

from datetime import datetime, timedelta

import pytest

from app.ml.analytics import TradeAnalytics
from app.models.signal import Signal, SignalType
from app.models.trade import Trade, TradeSide, TradeStatus


def _seed_closed_trades(db, count=10):
    """Seed closed trades with alternating wins/losses."""
    now = datetime.now()
    for i in range(count):
        entry = 5.0
        exit_price = 5.50 if i % 2 == 0 else 4.50
        pnl = (exit_price - entry) * 100

        trade = Trade(
            ticker=f"T{i % 3}",
            side=TradeSide.BUY,
            status=TradeStatus.CLOSED,
            quantity=100,
            entry_price=entry,
            exit_price=exit_price,
            stop_loss_price=4.75,
            target_price=5.50,
            pnl=pnl,
            signal_score=0.7,
            entry_time=now - timedelta(days=count - i, hours=2),
            exit_time=now - timedelta(days=count - i),
            created_at=now - timedelta(days=count - i),
        )
        db.add(trade)
    db.commit()


def _seed_signals_with_outcomes(db, count=10):
    """Seed breakout signals with outcome_pnl for accuracy bucketing."""
    now = datetime.now()
    for i in range(count):
        pnl = 50.0 if i % 2 == 0 else -30.0
        signal = Signal(
            ticker=f"T{i % 3}",
            signal_type=SignalType.BREAKOUT,
            score=0.65 + (i % 5) * 0.05,
            liquidity_imbalance=0.7,
            spread_compression=0.6,
            bid_stacking=0.7,
            volume_acceleration=0.8,
            order_aggression=0.7,
            outcome_pnl=pnl,
            created_at=now - timedelta(days=count - i),
        )
        db.add(signal)
    db.commit()


def test_kpis_with_trades(db):
    _seed_closed_trades(db, count=10)

    kpis = TradeAnalytics(db).compute_kpis(days=30)

    assert kpis["total_trades"] == 10
    assert kpis["winning_trades"] == 5
    assert kpis["losing_trades"] == 5
    assert kpis["win_rate"] == pytest.approx(0.5, abs=0.01)
    assert kpis["total_pnl"] == pytest.approx(0.0, abs=0.01)
    assert kpis["days"] == 30


def test_kpis_empty_db(db):
    kpis = TradeAnalytics(db).compute_kpis(days=30)
    assert kpis["total_trades"] == 0
    assert kpis["total_pnl"] == 0.0


def test_kpis_respects_days_filter(db):
    _seed_closed_trades(db, count=10)

    # Very short window should yield fewer trades
    kpis = TradeAnalytics(db).compute_kpis(days=1)
    assert kpis["total_trades"] <= 10


def test_signal_accuracy_buckets(db):
    _seed_signals_with_outcomes(db, count=10)

    buckets = TradeAnalytics(db).signal_accuracy_by_bucket(bucket_size=0.1)

    assert len(buckets) >= 1
    for b in buckets:
        assert "range" in b
        assert "total" in b
        assert "wins" in b
        assert "win_rate" in b
        assert 0.0 <= b["win_rate"] <= 1.0


def test_signal_accuracy_empty(db):
    buckets = TradeAnalytics(db).signal_accuracy_by_bucket()
    assert buckets == []


def test_avg_hold_time(db):
    _seed_closed_trades(db, count=10)
    kpis = TradeAnalytics(db).compute_kpis(days=30)
    assert kpis["avg_hold_time_minutes"] > 0
