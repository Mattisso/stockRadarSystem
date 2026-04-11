from datetime import datetime, timedelta, timezone

from app.data.polygon_aggregate_service import (
    PolygonAggregateService,
    PolygonMinuteAggregateRecord,
    PolygonSecondAggregateRecord,
)
from app.engine.symbol_state_live_service import SymbolStateLiveService
from app.models.symbol_state_live import SymbolStateLive


def test_symbol_state_live_updates_from_second_and_minute_aggregates(db):
    aggregate_service = PolygonAggregateService(db)

    aggregate_service.upsert_minute_aggregates(
        [
            PolygonMinuteAggregateRecord(
                ticker="LCID",
                minute_ts=datetime(2026, 4, 10, 13, 29, 0, tzinfo=timezone.utc),
                open=2.95,
                high=3.15,
                low=2.94,
                close=3.05,
                volume=1_000,
            ),
            PolygonMinuteAggregateRecord(
                ticker="LCID",
                minute_ts=datetime(2026, 4, 10, 13, 30, 0, tzinfo=timezone.utc),
                open=3.05,
                high=3.25,
                low=3.02,
                close=3.20,
                volume=1_500,
            ),
        ]
    )
    aggregate_service.upsert_second_aggregates(
        [
            PolygonSecondAggregateRecord(
                ticker="LCID",
                second_ts=datetime(2026, 4, 10, 13, 30, 1, tzinfo=timezone.utc),
                open=3.00,
                high=3.10,
                low=3.00,
                close=3.10,
                volume=100,
                transactions=1,
            ),
            PolygonSecondAggregateRecord(
                ticker="LCID",
                second_ts=datetime(2026, 4, 10, 13, 30, 2, tzinfo=timezone.utc),
                open=3.10,
                high=3.12,
                low=3.00,
                close=3.00,
                volume=150,
                transactions=1,
            ),
            PolygonSecondAggregateRecord(
                ticker="LCID",
                second_ts=datetime(2026, 4, 10, 13, 30, 3, tzinfo=timezone.utc),
                open=3.00,
                high=3.20,
                low=2.99,
                close=3.20,
                volume=120,
                transactions=1,
            ),
        ]
    )

    state = db.query(SymbolStateLive).filter_by(ticker="LCID").one()
    assert state.last_second_ts == datetime(2026, 4, 10, 13, 30, 3)
    assert state.last_minute_ts == datetime(2026, 4, 10, 13, 30, 0)
    assert state.rolling_second_high == 3.20
    assert state.rolling_second_low == 2.99
    assert state.rolling_second_volume == 370
    assert state.rolling_green_count == 2
    assert state.current_minute_high == 3.25
    assert state.previous_minute_high == 3.15
    assert state.is_second_stream_stale is False
    assert state.is_minute_stream_stale is False
    assert state.candidate_status == "validated"
    assert state.candidate_score is not None


def test_symbol_state_live_refreshes_stale_flags(db):
    aggregate_service = PolygonAggregateService(db)
    aggregate_service.upsert_minute_aggregates(
        [
            PolygonMinuteAggregateRecord(
                ticker="LCID",
                minute_ts=datetime(2026, 4, 10, 13, 30, 0, tzinfo=timezone.utc),
                open=3.05,
                high=3.25,
                low=3.02,
                close=3.20,
                volume=1_500,
            )
        ]
    )
    aggregate_service.upsert_second_aggregates(
        [
            PolygonSecondAggregateRecord(
                ticker="LCID",
                second_ts=datetime(2026, 4, 10, 13, 30, 3, tzinfo=timezone.utc),
                open=3.00,
                high=3.20,
                low=2.99,
                close=3.20,
                volume=120,
                transactions=1,
            )
        ]
    )

    service = SymbolStateLiveService(db)
    service.refresh_staleness(as_of=datetime(2026, 4, 10, 13, 30, 24, tzinfo=timezone.utc), ticker="LCID")
    state = db.query(SymbolStateLive).filter_by(ticker="LCID").one()
    assert state.seconds_since_last_trade_bar == 21
    assert state.is_second_stream_stale is True
    assert state.minutes_since_last_trade_bar == 0
    assert state.is_minute_stream_stale is False

    service.refresh_staleness(as_of=datetime(2026, 4, 10, 13, 33, 24, tzinfo=timezone.utc), ticker="LCID")
    state = db.query(SymbolStateLive).filter_by(ticker="LCID").one()
    assert state.minutes_since_last_trade_bar == 3
    assert state.is_minute_stream_stale is True
