from datetime import datetime, timezone

from app.data.polygon_live_retention_service import PolygonLiveRetentionService
from app.models.polygon_minute_aggregate import PolygonMinuteAggregate
from app.models.polygon_minute_aggregate_live import PolygonMinuteAggregateLive
from app.models.polygon_second_aggregate import PolygonSecondAggregate
from app.models.polygon_second_aggregate_live import PolygonSecondAggregateLive
from app.models.polygon_tick import PolygonTick
from app.models.polygon_tick_live import PolygonTickLive


def test_polygon_live_retention_service_purges_only_old_live_rows(db):
    db.add_all(
        [
            PolygonTickLive(
                ticker="ALTS",
                event_type="trade",
                bid=1.10,
                ask=1.11,
                last=1.105,
                volume=100,
                tick_ts=datetime(2026, 4, 11, 12, 0, 0, tzinfo=timezone.utc),
            ),
            PolygonTickLive(
                ticker="ALTS",
                event_type="trade",
                bid=1.20,
                ask=1.21,
                last=1.205,
                volume=120,
                tick_ts=datetime(2026, 4, 11, 20, 0, 0, tzinfo=timezone.utc),
            ),
            PolygonSecondAggregateLive(
                ticker="ALTS",
                second_ts=datetime(2026, 4, 11, 11, 59, 59, tzinfo=timezone.utc),
                open=1.10,
                high=1.11,
                low=1.10,
                close=1.11,
                volume=100,
                vwap=1.105,
                transactions=1,
            ),
            PolygonSecondAggregateLive(
                ticker="ALTS",
                second_ts=datetime(2026, 4, 11, 20, 0, 0, tzinfo=timezone.utc),
                open=1.20,
                high=1.22,
                low=1.20,
                close=1.21,
                volume=150,
                vwap=1.21,
                transactions=2,
            ),
            PolygonMinuteAggregateLive(
                ticker="ALTS",
                minute_ts=datetime(2026, 4, 11, 11, 59, 0, tzinfo=timezone.utc),
                open=1.10,
                high=1.11,
                low=1.10,
                close=1.11,
                volume=100,
                vwap=1.105,
                transactions=1,
            ),
            PolygonMinuteAggregateLive(
                ticker="ALTS",
                minute_ts=datetime(2026, 4, 11, 20, 0, 0, tzinfo=timezone.utc),
                open=1.20,
                high=1.22,
                low=1.20,
                close=1.21,
                volume=150,
                vwap=1.21,
                transactions=2,
            ),
        ]
    )
    db.commit()

    result = PolygonLiveRetentionService(db).purge(
        tick_retention_hours=8,
        minute_retention_hours=8,
        second_retention_hours=8,
        now=datetime(2026, 4, 12, 0, 0, 0, tzinfo=timezone.utc),
    )
    db.commit()

    assert result.deleted_tick_rows == 1
    assert result.deleted_minute_rows == 1
    assert result.deleted_second_rows == 1
    assert db.query(PolygonTickLive).count() == 1
    assert db.query(PolygonMinuteAggregateLive).count() == 1
    assert db.query(PolygonSecondAggregateLive).count() == 1
    assert db.query(PolygonTickLive).one().tick_ts == datetime(2026, 4, 11, 20, 0, 0)
    assert db.query(PolygonMinuteAggregateLive).one().minute_ts == datetime(2026, 4, 11, 20, 0, 0)
    assert db.query(PolygonSecondAggregateLive).one().second_ts == datetime(2026, 4, 11, 20, 0, 0)


def test_polygon_live_retention_service_purges_out_of_scope_live_and_historical_rows(db):
    db.add_all(
        [
            PolygonTick(
                ticker="PLTR",
                event_type="quote",
                bid=150.0,
                ask=150.1,
                last=150.05,
                volume=100,
                tick_ts=datetime(2026, 4, 11, 14, 0, 0, tzinfo=timezone.utc),
            ),
            PolygonTick(
                ticker="LCID",
                event_type="quote",
                bid=3.0,
                ask=3.01,
                last=3.005,
                volume=100,
                tick_ts=datetime(2026, 4, 11, 15, 0, 0, tzinfo=timezone.utc),
            ),
            PolygonTickLive(
                ticker="LCID",
                event_type="quote",
                bid=3.0,
                ask=3.01,
                last=3.005,
                volume=100,
                tick_ts=datetime(2026, 4, 11, 13, 0, 0, tzinfo=timezone.utc),
            ),
            PolygonMinuteAggregate(
                ticker="PLTR",
                minute_ts=datetime(2026, 4, 11, 14, 0, 0, tzinfo=timezone.utc),
                open=150.0,
                high=150.2,
                low=149.9,
                close=150.1,
                volume=1000,
                vwap=150.05,
                transactions=10,
            ),
            PolygonMinuteAggregate(
                ticker="LCID",
                minute_ts=datetime(2026, 4, 11, 15, 0, 0, tzinfo=timezone.utc),
                open=3.0,
                high=3.1,
                low=2.99,
                close=3.05,
                volume=1000,
                vwap=3.04,
                transactions=10,
            ),
            PolygonMinuteAggregateLive(
                ticker="LCID",
                minute_ts=datetime(2026, 4, 11, 21, 0, 0, tzinfo=timezone.utc),
                open=3.0,
                high=3.1,
                low=2.99,
                close=3.05,
                volume=1000,
                vwap=3.04,
                transactions=10,
            ),
            PolygonSecondAggregate(
                ticker="PLTR",
                second_ts=datetime(2026, 4, 11, 14, 0, 0, tzinfo=timezone.utc),
                open=150.0,
                high=150.1,
                low=149.9,
                close=150.05,
                volume=100,
                vwap=150.02,
                transactions=2,
            ),
            PolygonSecondAggregate(
                ticker="LCID",
                second_ts=datetime(2026, 4, 11, 15, 0, 0, tzinfo=timezone.utc),
                open=3.0,
                high=3.01,
                low=2.99,
                close=3.0,
                volume=100,
                vwap=3.0,
                transactions=2,
            ),
            PolygonSecondAggregateLive(
                ticker="LCID",
                second_ts=datetime(2026, 4, 11, 21, 0, 0, tzinfo=timezone.utc),
                open=3.0,
                high=3.01,
                low=2.99,
                close=3.0,
                volume=100,
                vwap=3.0,
                transactions=2,
            ),
        ]
    )
    db.commit()

    result = PolygonLiveRetentionService(db).purge_out_of_scope(
        max_price=10.0,
        session_start_et="09:30:00",
        session_end_et="16:00:00",
    )
    db.commit()

    assert result.deleted_scope_tick_rows == 1
    assert result.deleted_scope_tick_live_rows == 1
    assert result.deleted_scope_minute_rows == 1
    assert result.deleted_scope_minute_live_rows == 1
    assert result.deleted_scope_second_rows == 1
    assert result.deleted_scope_second_live_rows == 1
    assert db.query(PolygonTick).count() == 1
    assert db.query(PolygonTickLive).count() == 0
    assert db.query(PolygonMinuteAggregate).count() == 1
    assert db.query(PolygonMinuteAggregateLive).count() == 0
    assert db.query(PolygonSecondAggregate).count() == 1
    assert db.query(PolygonSecondAggregateLive).count() == 0


def test_polygon_live_retention_service_purges_historical_ticks_by_age(db):
    db.add_all(
        [
            PolygonTick(
                ticker="LCID",
                event_type="quote",
                bid=3.0,
                ask=3.01,
                last=3.005,
                volume=100,
                tick_ts=datetime(2026, 4, 10, 14, 0, 0, tzinfo=timezone.utc),
            ),
            PolygonTick(
                ticker="LCID",
                event_type="quote",
                bid=3.1,
                ask=3.11,
                last=3.105,
                volume=120,
                tick_ts=datetime(2026, 4, 25, 14, 0, 0, tzinfo=timezone.utc),
            ),
        ]
    )
    db.commit()

    result = PolygonLiveRetentionService(db).purge_historical_ticks(
        retention_days=14,
        now=datetime(2026, 5, 1, 0, 0, 0, tzinfo=timezone.utc),
    )
    db.commit()

    assert result.deleted_historical_tick_rows == 1
    assert result.historical_tick_cutoff_ts == datetime(2026, 4, 17, 0, 0, 0, tzinfo=timezone.utc)
    assert db.query(PolygonTick).count() == 1
    assert db.query(PolygonTick).one().tick_ts == datetime(2026, 4, 25, 14, 0, 0)
