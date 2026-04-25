import json
from datetime import datetime, timezone

import pytest

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
    state.validation_score = 0.7
    state.validation_pass_count = 7
    state.candidate_score = 0.6
    state.current_minute_high = 3.28
    state.rolling_second_high = 3.30
    state.rolling_second_low = 3.10
    state.candidate_status = "validated"
    state.is_second_stream_stale = False
    state.is_minute_stream_stale = False
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


def test_decision_engine_emits_buy_for_strong_validated_state(db):
    service = PolygonAggregateService(db)
    service.upsert_minute_aggregates(
        [
            PolygonMinuteAggregateRecord(
                ticker="LCID",
                minute_ts=datetime(2026, 4, 11, 14, 5, 0, tzinfo=timezone.utc),
                open=3.00,
                high=3.30,
                low=2.99,
                close=3.26,
                volume=1800,
            ),
        ]
    )
    service.upsert_second_aggregates(
        [
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 11, 14, 5, 1, tzinfo=timezone.utc), 3.10, 3.16, 3.10, 3.15, 400, 3.14, 1),
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 11, 14, 5, 2, tzinfo=timezone.utc), 3.15, 3.21, 3.14, 3.20, 420, 3.19, 1),
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 11, 14, 5, 3, tzinfo=timezone.utc), 3.20, 3.26, 3.19, 3.25, 450, 3.24, 1),
        ]
    )
    state = db.query(SymbolStateLive).filter_by(ticker="LCID").one()
    state.validation_score = 0.9
    state.validation_pass_count = 9
    state.candidate_score = 0.82
    state.current_minute_high = 3.30
    state.rolling_second_high = 3.29
    state.rolling_second_low = 3.19
    state.candidate_status = "validated"
    engine = AggregateDecisionEngine(db)

    decision = engine.evaluate(
        ticker="LCID",
        event_ts=datetime(2026, 4, 11, 14, 5, 3, tzinfo=timezone.utc),
        trigger_count=1,
        state=state,
    )
    inserted = engine.persist(decision, state)

    assert inserted == 1
    row = (
        db.query(DecisionEvent)
        .filter_by(decision_type="buy")
        .order_by(DecisionEvent.id.desc())
        .first()
    )
    assert row is not None
    assert row.decision_type == "buy"
    assert row.reason_code == "validated_buy_setup"
    assert json.loads(row.decision_payload)["validation_score"] == pytest.approx(0.9)
    assert state.candidate_status == "buy"


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


def test_decision_engine_emits_manage_after_buy_state(db):
    service = PolygonAggregateService(db)
    service.upsert_minute_aggregates(
        [
            PolygonMinuteAggregateRecord(
                ticker="LCID",
                minute_ts=datetime(2026, 4, 11, 14, 6, 0, tzinfo=timezone.utc),
                open=3.00,
                high=3.32,
                low=2.99,
                close=3.27,
                volume=1900,
            ),
        ]
    )
    service.upsert_second_aggregates(
        [
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 11, 14, 6, 1, tzinfo=timezone.utc), 3.15, 3.20, 3.14, 3.19, 410, 3.18, 1),
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 11, 14, 6, 2, tzinfo=timezone.utc), 3.19, 3.24, 3.18, 3.23, 430, 3.22, 1),
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 11, 14, 6, 3, tzinfo=timezone.utc), 3.23, 3.28, 3.22, 3.27, 460, 3.26, 1),
        ]
    )
    state = db.query(SymbolStateLive).filter_by(ticker="LCID").one()
    state.validation_score = 0.91
    state.validation_pass_count = 9
    state.candidate_score = 0.84
    state.current_minute_high = 3.32
    state.rolling_second_high = 3.30
    state.rolling_second_low = 3.23
    state.candidate_status = "buy"
    state.is_second_stream_stale = False
    state.is_minute_stream_stale = False
    engine = AggregateDecisionEngine(db)

    decision = engine.evaluate(
        ticker="LCID",
        event_ts=datetime(2026, 4, 11, 14, 6, 3, tzinfo=timezone.utc),
        trigger_count=1,
        state=state,
    )
    inserted = engine.persist(decision, state)

    assert inserted == 1
    row = (
        db.query(DecisionEvent)
        .filter_by(decision_type="manage")
        .order_by(DecisionEvent.id.desc())
        .first()
    )
    assert row is not None
    assert row.decision_type == "manage"
    assert row.reason_code == "active_position_manage"
    assert json.loads(row.decision_payload)["candidate_score"] == pytest.approx(0.84)
    assert state.candidate_status == "manage"


def test_decision_engine_emits_sell_for_active_position_breakdown(db):
    service = PolygonAggregateService(db)
    service.upsert_minute_aggregates(
        [
            PolygonMinuteAggregateRecord(
                ticker="LCID",
                minute_ts=datetime(2026, 4, 11, 14, 7, 0, tzinfo=timezone.utc),
                open=3.00,
                high=3.30,
                low=2.99,
                close=3.10,
                volume=2000,
            ),
        ]
    )
    service.upsert_second_aggregates(
        [
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 11, 14, 7, 1, tzinfo=timezone.utc), 3.18, 3.19, 3.05, 3.07, 500, 3.09, 1),
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 11, 14, 7, 2, tzinfo=timezone.utc), 3.07, 3.08, 3.00, 3.01, 520, 3.03, 1),
        ]
    )
    state = db.query(SymbolStateLive).filter_by(ticker="LCID").one()
    state.validation_score = 0.88
    state.validation_pass_count = 9
    state.candidate_score = 0.83
    state.current_minute_high = 3.30
    state.rolling_second_high = 3.19
    state.rolling_second_low = 3.00
    state.candidate_status = "manage"
    engine = AggregateDecisionEngine(db)

    decision = engine.evaluate(
        ticker="LCID",
        event_ts=datetime(2026, 4, 11, 14, 7, 2, tzinfo=timezone.utc),
        trigger_count=1,
        state=state,
    )
    inserted = engine.persist(decision, state)

    assert inserted == 1
    row = (
        db.query(DecisionEvent)
        .filter_by(decision_type="sell")
        .order_by(DecisionEvent.id.desc())
        .first()
    )
    assert row is not None
    assert row.decision_type == "sell"
    assert row.reason_code == "active_position_sharp_reversal"
    assert state.candidate_status == "sold"


def test_decision_engine_blocks_same_day_reentry_after_sell(db):
    state = SymbolStateLive(
        ticker="HIMS",
        candidate_status="sold",
        validation_score=0.95,
        validation_pass_count=9,
        candidate_score=0.9,
        current_minute_high=12.0,
        rolling_second_high=11.95,
        rolling_second_low=11.8,
        is_second_stream_stale=False,
        is_minute_stream_stale=False,
    )
    db.add(state)
    db.add(
        DecisionEvent(
            ticker="HIMS",
            decision_ts=datetime(2026, 4, 24, 13, 10, 0),
            decision_type="buy",
            reason_code="validated_buy_setup",
            decision_payload=json.dumps({"current_close": 11.9}),
            candidate_score=0.9,
            validation_pass_count=9,
            is_second_stream_stale=False,
            is_minute_stream_stale=False,
        )
    )
    db.add(
        DecisionEvent(
            ticker="HIMS",
            decision_ts=datetime(2026, 4, 24, 13, 12, 0),
            decision_type="sell",
            reason_code="active_position_sharp_reversal",
            decision_payload=json.dumps({"entry_price": 11.9}),
            candidate_score=0.85,
            validation_pass_count=9,
            is_second_stream_stale=False,
            is_minute_stream_stale=False,
        )
    )
    db.flush()

    engine = AggregateDecisionEngine(db)
    decision = engine.evaluate(
        ticker="HIMS",
        event_ts=datetime(2026, 4, 24, 13, 20, 0, tzinfo=timezone.utc),
        trigger_count=1,
        state=state,
    )

    assert decision is None
    assert state.candidate_status == "sold"


def test_decision_engine_emits_sell_for_active_position_stale_stream(db):
    service = PolygonAggregateService(db)
    service.upsert_minute_aggregates(
        [
            PolygonMinuteAggregateRecord(
                ticker="LCID",
                minute_ts=datetime(2026, 4, 11, 14, 8, 0, tzinfo=timezone.utc),
                open=3.00,
                high=3.28,
                low=2.99,
                close=3.24,
                volume=1700,
            ),
        ]
    )
    service.upsert_second_aggregates(
        [
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 11, 14, 8, 1, tzinfo=timezone.utc), 3.16, 3.20, 3.15, 3.19, 410, 3.18, 1),
        ]
    )
    state = db.query(SymbolStateLive).filter_by(ticker="LCID").one()
    state.validation_score = 0.9
    state.validation_pass_count = 9
    state.candidate_score = 0.82
    state.candidate_status = "buy"
    state.is_second_stream_stale = True
    engine = AggregateDecisionEngine(db)

    decision = engine.evaluate(
        ticker="LCID",
        event_ts=datetime(2026, 4, 11, 14, 8, 5, tzinfo=timezone.utc),
        trigger_count=1,
        state=state,
    )
    inserted = engine.persist(decision, state)

    assert inserted == 1
    row = (
        db.query(DecisionEvent)
        .filter_by(decision_type="sell")
        .order_by(DecisionEvent.id.desc())
        .first()
    )
    assert row is not None
    assert row.reason_code == "active_position_second_stream_stale"
    assert state.candidate_status == "sold"


def test_decision_engine_emits_sell_for_stop_loss(db):
    service = PolygonAggregateService(db)
    service.upsert_second_aggregates(
        [
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 11, 14, 9, 1, tzinfo=timezone.utc), 3.20, 3.22, 3.19, 3.21, 300, 3.21, 1),
        ]
    )
    state = db.query(SymbolStateLive).filter_by(ticker="LCID").one()
    state.validation_score = 0.9
    state.validation_pass_count = 9
    state.candidate_score = 0.82
    state.current_minute_high = 3.22
    state.rolling_second_high = 3.22
    state.rolling_second_low = 3.19
    state.is_second_stream_stale = False
    state.is_minute_stream_stale = False
    buy_engine = AggregateDecisionEngine(db)
    buy = buy_engine.evaluate(
        ticker="LCID",
        event_ts=datetime(2026, 4, 11, 14, 9, 1, tzinfo=timezone.utc),
        trigger_count=1,
        state=state,
    )
    buy_engine.persist(buy, state)

    service.upsert_second_aggregates(
        [
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 11, 14, 9, 2, tzinfo=timezone.utc), 3.21, 3.21, 3.09, 3.10, 320, 3.12, 1),
        ]
    )
    state = db.query(SymbolStateLive).filter_by(ticker="LCID").one()
    state.candidate_status = "manage"
    state.is_second_stream_stale = False
    state.is_minute_stream_stale = False
    decision = buy_engine.evaluate(
        ticker="LCID",
        event_ts=datetime(2026, 4, 11, 14, 9, 2, tzinfo=timezone.utc),
        trigger_count=1,
        state=state,
    )
    assert decision is not None
    assert decision.reason_code == "active_position_stop_loss"


def test_decision_engine_emits_sell_for_momentum_dies(db):
    service = PolygonAggregateService(db)
    buy_engine = AggregateDecisionEngine(db)
    service.upsert_second_aggregates(
        [
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 11, 14, 10, 1, tzinfo=timezone.utc), 3.10, 3.12, 3.09, 3.11, 300, 3.11, 1),
        ]
    )
    state = db.query(SymbolStateLive).filter_by(ticker="LCID").one()
    state.validation_score = 0.9
    state.validation_pass_count = 9
    state.candidate_score = 0.82
    state.current_minute_high = 3.12
    state.rolling_second_high = 3.12
    state.rolling_second_low = 3.09
    state.is_second_stream_stale = False
    state.is_minute_stream_stale = False
    buy_engine.persist(
        buy_engine.evaluate(
            ticker="LCID",
            event_ts=datetime(2026, 4, 11, 14, 10, 1, tzinfo=timezone.utc),
            trigger_count=1,
            state=state,
        ),
        state,
    )
    service.upsert_second_aggregates(
        [
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 11, 14, 10, 2, tzinfo=timezone.utc), 3.11, 3.12, 3.10, 3.11, 300, 3.11, 1),
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 11, 14, 10, 3, tzinfo=timezone.utc), 3.11, 3.12, 3.10, 3.11, 300, 3.11, 1),
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 11, 14, 10, 4, tzinfo=timezone.utc), 3.11, 3.12, 3.10, 3.11, 300, 3.11, 1),
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 11, 14, 10, 5, tzinfo=timezone.utc), 3.11, 3.12, 3.10, 3.11, 300, 3.11, 1),
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 11, 14, 10, 6, tzinfo=timezone.utc), 3.11, 3.11, 3.04, 3.05, 300, 3.06, 1),
        ]
    )
    state = db.query(SymbolStateLive).filter_by(ticker="LCID").one()
    state.candidate_status = "manage"
    state.is_second_stream_stale = False
    state.is_minute_stream_stale = False
    decision = buy_engine.evaluate(
        ticker="LCID",
        event_ts=datetime(2026, 4, 11, 14, 10, 6, tzinfo=timezone.utc),
        trigger_count=1,
        state=state,
    )
    assert decision is not None
    assert decision.reason_code == "active_position_momentum_dies"


def test_decision_engine_emits_sell_for_no_continuation(db):
    service = PolygonAggregateService(db)
    engine = AggregateDecisionEngine(db)
    service.upsert_second_aggregates(
        [
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 11, 14, 11, 1, tzinfo=timezone.utc), 3.10, 3.11, 3.09, 3.11, 300, 3.11, 1),
        ]
    )
    state = db.query(SymbolStateLive).filter_by(ticker="LCID").one()
    state.validation_score = 0.9
    state.validation_pass_count = 9
    state.candidate_score = 0.82
    state.current_minute_high = 3.11
    state.rolling_second_high = 3.11
    state.rolling_second_low = 3.09
    state.is_second_stream_stale = False
    state.is_minute_stream_stale = False
    engine.persist(
        engine.evaluate(
            ticker="LCID",
            event_ts=datetime(2026, 4, 11, 14, 11, 1, tzinfo=timezone.utc),
            trigger_count=1,
            state=state,
        ),
        state,
    )
    service.upsert_second_aggregates(
        [
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 11, 14, 11, 12, tzinfo=timezone.utc), 3.11, 3.11, 3.10, 3.10, 300, 3.10, 1),
        ]
    )
    state = db.query(SymbolStateLive).filter_by(ticker="LCID").one()
    state.candidate_status = "manage"
    state.validation_score = 0.5
    state.is_second_stream_stale = False
    state.is_minute_stream_stale = False
    decision = engine.evaluate(
        ticker="LCID",
        event_ts=datetime(2026, 4, 11, 14, 11, 12, tzinfo=timezone.utc),
        trigger_count=1,
        state=state,
    )
    assert decision is not None
    assert decision.reason_code == "active_position_no_continuation"


def test_decision_engine_emits_sell_for_quick_profit_spike(db):
    service = PolygonAggregateService(db)
    engine = AggregateDecisionEngine(db)
    service.upsert_second_aggregates(
        [
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 11, 14, 12, 1, tzinfo=timezone.utc), 3.00, 3.01, 2.99, 3.00, 300, 3.00, 1),
        ]
    )
    state = db.query(SymbolStateLive).filter_by(ticker="LCID").one()
    state.validation_score = 0.9
    state.validation_pass_count = 9
    state.candidate_score = 0.82
    state.current_minute_high = 3.01
    state.rolling_second_high = 3.01
    state.rolling_second_low = 2.99
    state.is_second_stream_stale = False
    state.is_minute_stream_stale = False
    engine.persist(
        engine.evaluate(
            ticker="LCID",
            event_ts=datetime(2026, 4, 11, 14, 12, 1, tzinfo=timezone.utc),
            trigger_count=1,
            state=state,
        ),
        state,
    )
    service.upsert_second_aggregates(
        [
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 11, 14, 12, 2, tzinfo=timezone.utc), 3.00, 3.20, 3.00, 3.18, 300, 3.17, 1),
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 11, 14, 12, 3, tzinfo=timezone.utc), 3.18, 3.18, 3.10, 3.12, 300, 3.13, 1),
        ]
    )
    state = db.query(SymbolStateLive).filter_by(ticker="LCID").one()
    state.candidate_status = "manage"
    state.is_second_stream_stale = False
    state.is_minute_stream_stale = False
    decision = engine.evaluate(
        ticker="LCID",
        event_ts=datetime(2026, 4, 11, 14, 12, 3, tzinfo=timezone.utc),
        trigger_count=1,
        state=state,
    )
    assert decision is not None
    assert decision.reason_code == "active_position_quick_profit_spike"
