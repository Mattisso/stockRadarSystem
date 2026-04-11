import json
from datetime import datetime, timezone

from app.data.polygon_aggregate_service import PolygonAggregateService, PolygonSecondAggregateRecord
from app.engine.aggregate_trigger_engine import AggregateTriggerEngine
from app.engine.symbol_state_live_service import SymbolStateLiveService
from app.models.candidate_event import CandidateEvent
from app.models.symbol_state_live import SymbolStateLive


def test_breakout_above_recent_high_emits_candidate_event(db):
    service = PolygonAggregateService(db)
    service.upsert_second_aggregates(
        [
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 30, 1, tzinfo=timezone.utc), 3.00, 3.02, 2.99, 3.01, 100, 3.01, 1),
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 30, 2, tzinfo=timezone.utc), 3.01, 3.04, 3.00, 3.03, 110, 3.03, 1),
        ]
    )
    state = db.query(SymbolStateLive).filter_by(ticker="LCID").one()
    engine = AggregateTriggerEngine(db)

    current = PolygonSecondAggregateRecord(
        "LCID",
        datetime(2026, 4, 10, 13, 30, 3, tzinfo=timezone.utc),
        3.04,
        3.10,
        3.04,
        3.10,
        120,
        3.09,
        1,
    )
    service.upsert_second_aggregates([current])
    state = db.query(SymbolStateLive).filter_by(ticker="LCID").one()
    triggers = engine.evaluate_second_bar(current, state)

    trigger_names = {trigger.trigger_name for trigger in triggers}
    assert "breakout_above_recent_high" in trigger_names
    row = (
        db.query(CandidateEvent)
        .filter_by(trigger_name="breakout_above_recent_high")
        .order_by(CandidateEvent.id.desc())
        .first()
    )
    assert row is not None
    assert row.trigger_name == "breakout_above_recent_high"
    assert json.loads(row.trigger_payload)["recent_high"] == 3.04


def test_second_volume_spike_emits_candidate_event(db):
    service = PolygonAggregateService(db)
    service.upsert_second_aggregates(
        [
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 31, 1, tzinfo=timezone.utc), 3.00, 3.01, 2.99, 3.00, 100, 3.00, 1),
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 31, 2, tzinfo=timezone.utc), 3.00, 3.01, 2.99, 3.00, 90, 3.00, 1),
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 31, 3, tzinfo=timezone.utc), 3.00, 3.01, 2.99, 3.00, 95, 3.00, 1),
        ]
    )
    current = PolygonSecondAggregateRecord(
        "LCID",
        datetime(2026, 4, 10, 13, 31, 4, tzinfo=timezone.utc),
        3.00,
        3.03,
        3.00,
        3.02,
        500,
        3.02,
        1,
    )
    service.upsert_second_aggregates([current])
    state = db.query(SymbolStateLive).filter_by(ticker="LCID").one()
    engine = AggregateTriggerEngine(db)

    triggers = engine.evaluate_second_bar(current, state)

    trigger_names = {trigger.trigger_name for trigger in triggers}
    assert "second_volume_spike" in trigger_names


def test_consecutive_green_seconds_emits_candidate_event(db):
    service = PolygonAggregateService(db)
    bars = [
        PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 32, 1, tzinfo=timezone.utc), 3.00, 3.02, 3.00, 3.02, 100, 3.01, 1),
        PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 32, 2, tzinfo=timezone.utc), 3.02, 3.04, 3.02, 3.04, 105, 3.03, 1),
        PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 32, 3, tzinfo=timezone.utc), 3.04, 3.06, 3.04, 3.06, 110, 3.05, 1),
    ]
    service.upsert_second_aggregates(bars)
    state = db.query(SymbolStateLive).filter_by(ticker="LCID").one()
    engine = AggregateTriggerEngine(db)

    triggers = engine.evaluate_second_bar(bars[-1], state)

    trigger_names = {trigger.trigger_name for trigger in triggers}
    assert "consecutive_green_seconds" in trigger_names


def test_upsert_second_aggregates_persists_candidate_events_and_live_score(db):
    service = PolygonAggregateService(db)
    service.upsert_second_aggregates(
        [
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 33, 1, tzinfo=timezone.utc), 3.00, 3.01, 2.99, 3.00, 100, 3.00, 1),
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 33, 2, tzinfo=timezone.utc), 3.00, 3.02, 2.99, 3.01, 100, 3.01, 1),
        ]
    )

    service.upsert_second_aggregates(
        [
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 33, 3, tzinfo=timezone.utc), 3.02, 3.10, 3.02, 3.10, 150, 3.08, 1),
        ]
    )

    events = db.query(CandidateEvent).filter_by(ticker="LCID").all()
    assert len(events) >= 1
    state = db.query(SymbolStateLive).filter_by(ticker="LCID").one()
    assert state.candidate_status == "candidate"
    assert state.candidate_score is not None
