import json
from datetime import datetime, timezone

from app.data.polygon_aggregate_service import PolygonAggregateService, PolygonMinuteAggregateRecord, PolygonSecondAggregateRecord
from app.engine.aggregate_decision_engine import AggregateDecisionEngine
from app.models.decision_event import DecisionEvent
from app.models.symbol_state_live import SymbolStateLive


def test_decision_engine_emits_candidate_for_validated_state(db):
    service = PolygonAggregateService(db)
    service.upsert_minute_aggregates(
        [
            PolygonMinuteAggregateRecord(
                ticker="LCID",
                minute_ts=datetime(2026, 4, 11, 13, 45, 0, tzinfo=timezone.utc),
                open=3.00,
                high=3.28,
                low=2.99,
                close=3.24,
                volume=1200,
            ),
        ]
    )
    service.upsert_second_aggregates(
        [
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 11, 13, 45, 1, tzinfo=timezone.utc), 3.10, 3.18, 3.10, 3.18, 350, 3.17, 1),
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 11, 13, 45, 2, tzinfo=timezone.utc), 3.18, 3.24, 3.17, 3.23, 380, 3.22, 1),
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 11, 13, 45, 3, tzinfo=timezone.utc), 3.23, 3.30, 3.22, 3.29, 420, 3.28, 1),
        ]
    )
    state = db.query(SymbolStateLive).filter_by(ticker="LCID").one()
    engine = AggregateDecisionEngine(db)

    decision = engine.evaluate(
        ticker="LCID",
        event_ts=datetime(2026, 4, 11, 13, 45, 3, tzinfo=timezone.utc),
        trigger_count=1,
        state=state,
    )
    inserted = engine.persist(decision, state)

    assert inserted == 1
    row = (
        db.query(DecisionEvent)
        .filter_by(decision_type="candidate")
        .order_by(DecisionEvent.id.desc())
        .first()
    )
    assert row is not None
    assert row.decision_type == "candidate"
    assert row.reason_code == "validated_candidate"
    assert json.loads(row.decision_payload)["validation_pass_count"] == state.validation_pass_count
    assert state.candidate_status == "validated"


def test_decision_engine_rejects_weak_validation(db):
    service = PolygonAggregateService(db)
    service.upsert_minute_aggregates(
        [
            PolygonMinuteAggregateRecord(
                ticker="LCID",
                minute_ts=datetime(2026, 4, 11, 13, 46, 0, tzinfo=timezone.utc),
                open=3.10,
                high=3.20,
                low=3.00,
                close=3.12,
                volume=800,
            ),
        ]
    )
    service.upsert_second_aggregates(
        [
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 11, 13, 46, 1, tzinfo=timezone.utc), 3.10, 3.22, 3.10, 3.21, 180, 3.20, 1),
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 11, 13, 46, 2, tzinfo=timezone.utc), 3.21, 3.22, 3.05, 3.08, 120, 3.11, 1),
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 11, 13, 46, 3, tzinfo=timezone.utc), 3.08, 3.09, 3.00, 3.01, 90, 3.03, 1),
        ]
    )
    state = db.query(SymbolStateLive).filter_by(ticker="LCID").one()
    engine = AggregateDecisionEngine(db)

    decision = engine.evaluate(
        ticker="LCID",
        event_ts=datetime(2026, 4, 11, 13, 46, 3, tzinfo=timezone.utc),
        trigger_count=1,
        state=state,
    )
    inserted = engine.persist(decision, state)

    assert inserted == 1
    row = (
        db.query(DecisionEvent)
        .filter_by(decision_type="reject")
        .order_by(DecisionEvent.id.desc())
        .first()
    )
    assert row is not None
    assert row.decision_type == "reject"
    assert row.reason_code in {"validation_below_threshold", "validation_pass_count_too_low"}
    assert state.candidate_status == "rejected"
