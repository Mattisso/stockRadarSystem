from datetime import datetime, timezone

from app.data.polygon_live_retention_service import PolygonLiveRetentionService
from app.models.polygon_minute_aggregate_live import PolygonMinuteAggregateLive
from app.models.polygon_second_aggregate_live import PolygonSecondAggregateLive
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
