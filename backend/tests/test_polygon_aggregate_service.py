from datetime import date, datetime, timezone

from app.data.polygon_aggregate_service import (
    PolygonAggregateService,
    PolygonDayAggregateRecord,
    PolygonMinuteAggregateRecord,
)
from app.models.polygon_day_aggregate import PolygonDayAggregate
from app.models.polygon_minute_aggregate import PolygonMinuteAggregate
from app.models.universe_daily import UniverseDaily


def test_upsert_day_aggregates_and_build_universe(db):
    service = PolygonAggregateService(db)
    trade_date = date(2026, 4, 4)

    inserted = service.upsert_day_aggregates(
        [
            PolygonDayAggregateRecord(
                ticker="AAPL",
                trade_date=trade_date,
                open=150.0,
                high=151.0,
                low=149.5,
                close=150.5,
                volume=1_000_000,
            ),
            PolygonDayAggregateRecord(
                ticker="LCID",
                trade_date=trade_date,
                open=3.25,
                high=3.5,
                low=3.1,
                close=3.45,
                volume=500_000,
            ),
        ]
    )

    assert inserted == 2
    assert db.query(PolygonDayAggregate).count() == 2

    universe = service.build_daily_universe(trade_date=trade_date, max_open=10.0)
    db.commit()

    assert universe == ["LCID"]
    rows = db.query(UniverseDaily).all()
    assert len(rows) == 1
    assert rows[0].ticker == "LCID"
    assert rows[0].open_price == 3.25
    assert rows[0].last_price == 3.45
    assert rows[0].avg_volume == 500_000


def test_upsert_minute_aggregates_filters_to_allowed_tickers(db):
    service = PolygonAggregateService(db)

    inserted = service.upsert_minute_aggregates(
        [
            PolygonMinuteAggregateRecord(
                ticker="LCID",
                minute_ts=datetime(2026, 4, 4, 14, 31, 45, tzinfo=timezone.utc),
                open=3.2,
                high=3.25,
                low=3.18,
                close=3.24,
                volume=1000,
            ),
            PolygonMinuteAggregateRecord(
                ticker="AAPL",
                minute_ts=datetime(2026, 4, 4, 14, 31, 10, tzinfo=timezone.utc),
                open=150.0,
                high=150.2,
                low=149.9,
                close=150.1,
                volume=2000,
            ),
        ],
        allowed_tickers={"LCID"},
    )

    assert inserted == 1
    rows = db.query(PolygonMinuteAggregate).all()
    assert len(rows) == 1
    assert rows[0].ticker == "LCID"
    assert rows[0].minute_ts.replace(tzinfo=timezone.utc) == datetime(2026, 4, 4, 14, 31, tzinfo=timezone.utc)
