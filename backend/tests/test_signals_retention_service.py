"""Tests for SignalsRetentionService — bounded purge of old signals rows."""

from datetime import datetime, timedelta, timezone

from app.data.signals_retention_service import SignalsRetentionService
from app.models.signal import Signal, SignalType


def _make_signal(*, ticker: str, created_at: datetime) -> Signal:
    return Signal(
        ticker=ticker,
        signal_type=SignalType.BREAKOUT,
        score=0.6,
        liquidity_imbalance=0.0,
        spread_compression=0.0,
        bid_stacking=0.0,
        volume_acceleration=0.0,
        order_aggression=0.0,
        ml_confidence=0.0,
        acted_on=False,
        outcome_pnl=0.0,
        created_at=created_at,
    )


def test_purge_deletes_only_rows_older_than_cutoff(db):
    now = datetime(2026, 5, 6, 0, 0, 0, tzinfo=timezone.utc)
    fresh = now - timedelta(days=10)
    stale = now - timedelta(days=120)

    db.add_all(
        [
            _make_signal(ticker="LCID", created_at=fresh),
            _make_signal(ticker="OPK", created_at=fresh),
            _make_signal(ticker="OLD1", created_at=stale),
            _make_signal(ticker="OLD2", created_at=stale),
        ]
    )
    db.commit()

    result = SignalsRetentionService(db).purge(retention_days=90, batch_size=100, now=now)

    assert result.deleted_signal_rows == 2
    assert result.stopped_reason == "no_more_rows"
    remaining_tickers = {row.ticker for row in db.query(Signal).all()}
    assert remaining_tickers == {"LCID", "OPK"}


def test_purge_runs_in_multiple_batches_when_more_rows_than_batch_size(db):
    now = datetime(2026, 5, 6, 0, 0, 0, tzinfo=timezone.utc)
    stale = now - timedelta(days=200)
    db.add_all([_make_signal(ticker=f"T{i}", created_at=stale) for i in range(7)])
    db.commit()

    result = SignalsRetentionService(db).purge(retention_days=90, batch_size=3, now=now)

    # 7 rows / batch=3 → batches: 3, 3, 1 (the partial batch ends the loop).
    assert result.deleted_signal_rows == 7
    assert result.batches_run == 3
    assert result.stopped_reason == "no_more_rows"
    assert db.query(Signal).count() == 0


def test_purge_respects_max_batches_safety_stop(db):
    now = datetime(2026, 5, 6, 0, 0, 0, tzinfo=timezone.utc)
    stale = now - timedelta(days=200)
    db.add_all([_make_signal(ticker=f"T{i}", created_at=stale) for i in range(10)])
    db.commit()

    result = SignalsRetentionService(db).purge(
        retention_days=90, batch_size=2, max_batches=3, now=now
    )

    assert result.deleted_signal_rows == 6
    assert result.batches_run == 3
    assert result.stopped_reason == "max_batches_reached"
    assert db.query(Signal).count() == 4


def test_purge_with_zero_retention_days_raises():
    import pytest
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine("sqlite:///:memory:")
    db = sessionmaker(bind=engine)()
    with pytest.raises(ValueError):
        SignalsRetentionService(db).purge(retention_days=0)
