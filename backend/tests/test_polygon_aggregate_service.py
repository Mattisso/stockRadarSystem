from datetime import date, datetime, timezone

from app.data.polygon_aggregate_service import (
    PolygonAggregateService,
    PolygonDayAggregateRecord,
    PolygonMinuteAggregateRecord,
    PolygonSecondAggregateRecord,
)
from app.models.polygon_day_aggregate import PolygonDayAggregate
from app.models.polygon_minute_aggregate import PolygonMinuteAggregate
from app.models.polygon_second_aggregate import PolygonSecondAggregate
from app.models.symbol import Symbol
from app.models.universe_daily import UniverseDaily


def test_upsert_day_aggregates_and_build_universe(db):
    service = PolygonAggregateService(db)
    trade_date = date(2026, 4, 4)
    db.add(Symbol(ticker="OLD", exchange="NASDAQ", last_price=1.2, avg_volume=1000, is_active=True))
    db.commit()

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

    universe = service.build_daily_universe(trade_date=trade_date, max_close=10.0)
    db.commit()

    assert universe == ["LCID"]
    rows = db.query(UniverseDaily).all()
    assert len(rows) == 1
    assert rows[0].ticker == "LCID"
    assert rows[0].open_price == 3.25
    assert rows[0].last_price == 3.45
    assert rows[0].avg_volume == 500_000
    lcid_symbol = db.query(Symbol).filter_by(ticker="LCID").one()
    assert lcid_symbol.last_price == 3.45
    assert lcid_symbol.avg_volume == 500_000
    assert lcid_symbol.is_active is True
    old_symbol = db.query(Symbol).filter_by(ticker="OLD").one()
    assert old_symbol.is_active is False


def test_build_daily_universe_filters_by_close_not_open(db):
    service = PolygonAggregateService(db)
    trade_date = date(2026, 4, 4)

    service.upsert_day_aggregates(
        [
            PolygonDayAggregateRecord(
                ticker="OPENLOW_CLOSEHIGH",
                trade_date=trade_date,
                open=3.25,
                high=10.5,
                low=3.0,
                close=10.25,
                volume=100_000,
            ),
            PolygonDayAggregateRecord(
                ticker="OPENHIGH_CLOSELOW",
                trade_date=trade_date,
                open=11.0,
                high=11.2,
                low=9.5,
                close=9.9,
                volume=100_000,
            ),
        ]
    )

    universe = service.build_daily_universe(trade_date=trade_date, max_close=10.0)

    assert universe == ["OPENHIGH_CLOSELOW"]


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


def test_upsert_second_aggregates_merges_same_second_rows(db):
    service = PolygonAggregateService(db)

    inserted = service.upsert_second_aggregates(
        [
            PolygonSecondAggregateRecord(
                ticker="LCID",
                second_ts=datetime(2026, 4, 4, 14, 31, 5, 100000, tzinfo=timezone.utc),
                open=3.20,
                high=3.25,
                low=3.20,
                close=3.25,
                volume=100,
                vwap=3.225,
                transactions=2,
            )
        ]
    )
    assert inserted == 1

    inserted = service.upsert_second_aggregates(
        [
            PolygonSecondAggregateRecord(
                ticker="LCID",
                second_ts=datetime(2026, 4, 4, 14, 31, 5, 900000, tzinfo=timezone.utc),
                open=3.24,
                high=3.30,
                low=3.24,
                close=3.28,
                volume=200,
                vwap=3.27,
                transactions=3,
            )
        ]
    )
    assert inserted == 0

    row = db.query(PolygonSecondAggregate).one()
    assert row.ticker == "LCID"
    assert row.second_ts.replace(tzinfo=timezone.utc) == datetime(2026, 4, 4, 14, 31, 5, tzinfo=timezone.utc)
    assert row.open == 3.20
    assert row.high == 3.30
    assert row.low == 3.20
    assert row.close == 3.28
    assert row.volume == 300
    assert row.transactions == 5
