import json
from datetime import datetime, timezone

from app.data.polygon_aggregate_service import (
    PolygonAggregateService,
    PolygonMinuteAggregateRecord,
    PolygonSecondAggregateRecord,
)
from app.engine.aggregate_trigger_engine import AggregateCandidateTrigger, AggregateTriggerEngine
from app.engine.symbol_state_live_service import SymbolStateLiveService
from app.models.candidate_event import CandidateEvent
from app.models.decision_event import DecisionEvent
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
    decisions = db.query(DecisionEvent).filter_by(ticker="LCID").all()
    assert len(decisions) == 0
    state = db.query(SymbolStateLive).filter_by(ticker="LCID").one()
    assert state.candidate_status in {"candidate", "validated", "rejected"}
    assert state.candidate_score is not None
    assert max(event.trigger_score or 0.0 for event in events) > 0.0


def test_velocity_spike_emits_candidate_event(db):
    service = PolygonAggregateService(db)
    bars = [
        PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 40, 1, tzinfo=timezone.utc), 3.00, 3.01, 2.99, 3.00, 100, 3.00, 1),
        PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 40, 2, tzinfo=timezone.utc), 3.00, 3.01, 2.99, 3.00, 100, 3.00, 1),
        PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 40, 3, tzinfo=timezone.utc), 3.00, 3.01, 2.99, 3.00, 100, 3.00, 1),
    ]
    service.upsert_second_aggregates(bars)
    current = PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 40, 4, tzinfo=timezone.utc), 3.00, 3.05, 3.00, 3.04, 100, 3.03, 1)
    service.upsert_second_aggregates([current])
    state = db.query(SymbolStateLive).filter_by(ticker="LCID").one()
    triggers = AggregateTriggerEngine(db).evaluate_second_bar(current, state)
    assert "velocity_spike" in {trigger.trigger_name for trigger in triggers}


def test_range_expansion_emits_candidate_event(db):
    service = PolygonAggregateService(db)
    bars = [
        PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 41, second, tzinfo=timezone.utc), 3.00, 3.01, 3.00, 3.005, 100, 3.005, 1)
        for second in range(1, 11)
    ]
    service.upsert_second_aggregates(bars)
    current = PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 41, 11, tzinfo=timezone.utc), 3.00, 3.05, 3.00, 3.045, 100, 3.04, 1)
    service.upsert_second_aggregates([current])
    state = db.query(SymbolStateLive).filter_by(ticker="LCID").one()
    triggers = AggregateTriggerEngine(db).evaluate_second_bar(current, state)
    assert "range_expansion" in {trigger.trigger_name for trigger in triggers}


def test_break_current_and_previous_minute_high_emit_candidate_events(db):
    service = PolygonAggregateService(db)
    service.upsert_minute_aggregates(
        [
            PolygonMinuteAggregateRecord("LCID", datetime(2026, 4, 10, 13, 42, tzinfo=timezone.utc), 3.00, 3.04, 2.99, 3.03, 1000, 3.02, 1),
            PolygonMinuteAggregateRecord("LCID", datetime(2026, 4, 10, 13, 43, tzinfo=timezone.utc), 3.03, 3.06, 3.02, 3.05, 1000, 3.04, 1),
        ]
    )
    current = PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 43, 30, tzinfo=timezone.utc), 3.06, 3.08, 3.06, 3.08, 100, 3.08, 1)
    service.upsert_second_aggregates([current])
    state = db.query(SymbolStateLive).filter_by(ticker="LCID").one()
    triggers = AggregateTriggerEngine(db).evaluate_second_bar(current, state)
    names = {trigger.trigger_name for trigger in triggers}
    assert "break_current_minute_high" in names
    assert "break_previous_minute_high" in names


def test_recovery_spike_emits_candidate_event(db):
    service = PolygonAggregateService(db)
    bars = [
        PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 44, 1, tzinfo=timezone.utc), 3.10, 3.12, 3.09, 3.11, 100, 3.11, 1),
        PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 44, 2, tzinfo=timezone.utc), 3.11, 3.11, 3.00, 3.02, 100, 3.04, 1),
        PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 44, 3, tzinfo=timezone.utc), 3.02, 3.03, 3.01, 3.02, 100, 3.02, 1),
        PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 44, 4, tzinfo=timezone.utc), 3.02, 3.03, 3.01, 3.02, 100, 3.02, 1),
        PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 44, 5, tzinfo=timezone.utc), 3.02, 3.03, 3.01, 3.02, 100, 3.02, 1),
    ]
    service.upsert_second_aggregates(bars)
    current = PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 44, 6, tzinfo=timezone.utc), 3.02, 3.05, 3.02, 3.05, 100, 3.05, 1)
    service.upsert_second_aggregates([current])
    state = db.query(SymbolStateLive).filter_by(ticker="LCID").one()
    triggers = AggregateTriggerEngine(db).evaluate_second_bar(current, state)
    assert "recovery_spike" in {trigger.trigger_name for trigger in triggers}


def test_first_move_after_quiet_emits_candidate_event(db):
    service = PolygonAggregateService(db)
    bars = [
        PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 45, second, tzinfo=timezone.utc), 3.00, 3.003, 2.999, 3.001, 100, 3.001, 1)
        for second in range(1, 11)
    ]
    service.upsert_second_aggregates(bars)
    current = PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 45, 11, tzinfo=timezone.utc), 3.001, 3.03, 3.001, 3.03, 100, 3.02, 1)
    service.upsert_second_aggregates([current])
    state = db.query(SymbolStateLive).filter_by(ticker="LCID").one()
    triggers = AggregateTriggerEngine(db).evaluate_second_bar(current, state)
    assert "first_move_after_quiet" in {trigger.trigger_name for trigger in triggers}


def test_new_high_of_day_early_emits_candidate_event(db):
    service = PolygonAggregateService(db)
    bars = [
        PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 31, 0, tzinfo=timezone.utc), 3.00, 3.01, 2.99, 3.00, 100, 3.00, 1),
        PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 31, 1, tzinfo=timezone.utc), 3.00, 3.02, 2.99, 3.01, 100, 3.01, 1),
        PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 31, 2, tzinfo=timezone.utc), 3.01, 3.03, 3.00, 3.02, 100, 3.02, 1),
    ]
    service.upsert_second_aggregates(bars)
    current = PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 31, 3, tzinfo=timezone.utc), 3.03, 3.05, 3.03, 3.05, 100, 3.05, 1)
    service.upsert_second_aggregates([current])
    state = db.query(SymbolStateLive).filter_by(ticker="LCID").one()
    triggers = AggregateTriggerEngine(db).evaluate_second_bar(current, state)
    assert "new_high_of_day_early" in {trigger.trigger_name for trigger in triggers}


def test_trigger_persist_with_validation_does_not_overwrite_active_or_sold_states(db):
    engine = AggregateTriggerEngine(db)
    event_ts = datetime(2026, 4, 24, 13, 30, 0, tzinfo=timezone.utc)

    for protected_status in ("buy", "manage", "sold"):
        state = SymbolStateLive(
            ticker=f"T{protected_status[0].upper()}",
            candidate_status=protected_status,
            validation_score=0.0,
            validation_pass_count=0,
            is_second_stream_stale=False,
            is_minute_stream_stale=False,
        )
        db.add(state)
        db.flush()

        trigger = AggregateCandidateTrigger(
            ticker=state.ticker,
            event_ts=event_ts,
            trigger_name="breakout_above_recent_high",
            score=0.91,
            payload={"close": 3.1},
        )
        engine.persist_with_validation([trigger], state, event_ts=event_ts)
        assert state.candidate_status == protected_status


def test_trigger_engine_persist_is_idempotent_on_redelivery(db):
    # Regression: on Redis Streams redelivery the same trigger can hit
    # persist() twice. Without the _candidate_event_exists guard we would
    # insert duplicate candidate_events rows (no unique constraint exists
    # at the DB level today).
    engine = AggregateTriggerEngine(db)
    event_ts = datetime(2026, 4, 24, 13, 30, 0, tzinfo=timezone.utc)

    state = SymbolStateLive(
        ticker="LCID",
        candidate_status="idle",
        validation_score=0.0,
        validation_pass_count=0,
        is_second_stream_stale=False,
        is_minute_stream_stale=False,
    )
    db.add(state)
    db.flush()

    trigger = AggregateCandidateTrigger(
        ticker="LCID",
        event_ts=event_ts,
        trigger_name="breakout_above_recent_high",
        score=0.91,
        payload={"close": 3.1},
    )

    first = engine.persist([trigger], state)
    second = engine.persist([trigger], state)

    assert first == 1
    assert second == 0
    assert db.query(CandidateEvent).filter_by(ticker="LCID", event_ts=event_ts).count() == 1
