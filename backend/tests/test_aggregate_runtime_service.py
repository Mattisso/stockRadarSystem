from datetime import date, datetime, timezone

from app.data.polygon_aggregate_service import (
    PolygonAggregateService,
    PolygonMinuteAggregateRecord,
    PolygonSecondAggregateRecord,
)
from app.engine.aggregate_trigger_engine import AggregateTriggerEngine
from app.engine.aggregate_runtime_service import AggregateRuntimeService
from app.models.candidate_event import CandidateEvent
from app.models.decision_event import DecisionEvent
from app.models.symbol_state_live import SymbolStateLive
from app.models.universe_daily import UniverseDaily


def _seed_candidate_events(db, *, ticker: str, event_ts: datetime, o: float, h: float, l: float, c: float, v: int, vw: float):
    state = db.query(SymbolStateLive).filter_by(ticker=ticker).one()
    trigger_engine = AggregateTriggerEngine(db)
    record = PolygonSecondAggregateRecord(
        ticker=ticker,
        second_ts=event_ts,
        open=o,
        high=h,
        low=l,
        close=c,
        volume=v,
        vwap=vw,
        transactions=1,
    )
    triggers = trigger_engine.evaluate_second_bar(record, state)
    assert len(triggers) >= 1
    trigger_engine.persist_with_validation(triggers, state, event_ts=event_ts)
    db.commit()


def test_aggregate_runtime_service_refreshes_staleness_and_emits_sell_for_active_position(db):
    aggregate_service = PolygonAggregateService(db)
    aggregate_service.upsert_minute_aggregates(
        [
            PolygonMinuteAggregateRecord(
                ticker="LCID",
                minute_ts=datetime(2026, 4, 10, 13, 30, 0, tzinfo=timezone.utc),
                open=3.00,
                high=3.20,
                low=2.99,
                close=3.18,
                volume=1_200,
            )
        ]
    )
    aggregate_service.upsert_second_aggregates(
        [
            PolygonSecondAggregateRecord(
                ticker="LCID",
                second_ts=datetime(2026, 4, 10, 13, 30, 1, tzinfo=timezone.utc),
                open=3.10,
                high=3.16,
                low=3.09,
                close=3.15,
                volume=200,
                transactions=1,
            )
        ]
    )
    state = db.query(SymbolStateLive).filter_by(ticker="LCID").one()
    state.candidate_status = "buy"
    db.add(
        DecisionEvent(
            ticker="LCID",
            decision_ts=datetime(2026, 4, 10, 13, 30, 1),
            decision_type="buy",
            reason_code="validated_buy_setup",
            decision_payload='{"current_close": 3.15}',
            candidate_score=0.9,
            validation_pass_count=8,
            is_second_stream_stale=False,
            is_minute_stream_stale=False,
        )
    )
    db.commit()

    result = AggregateRuntimeService(db).refresh_validation_and_decisions(
        as_of=datetime(2026, 4, 10, 13, 30, 5, tzinfo=timezone.utc)
    )
    db.commit()

    assert result.refreshed_state_count == 1
    assert result.refreshed_validation_count == 1
    assert result.persisted_decision_count == 1

    state = db.query(SymbolStateLive).filter_by(ticker="LCID").one()
    decision = (
        db.query(DecisionEvent)
        .filter_by(ticker="LCID")
        .order_by(DecisionEvent.id.desc())
        .first()
    )
    assert state.is_second_stream_stale is True
    assert state.candidate_status == "sold"
    assert decision.decision_type == "sell"
    assert decision.reason_code == "active_position_second_stream_stale"


def test_aggregate_runtime_service_dedupes_identical_repeated_decisions(db):
    aggregate_service = PolygonAggregateService(db)
    aggregate_service.upsert_minute_aggregates(
        [
            PolygonMinuteAggregateRecord(
                ticker="LCID",
                minute_ts=datetime(2026, 4, 10, 13, 30, 0, tzinfo=timezone.utc),
                open=3.00,
                high=3.20,
                low=2.99,
                close=3.18,
                volume=1_200,
            )
        ]
    )
    aggregate_service.upsert_second_aggregates(
        [
            PolygonSecondAggregateRecord(
                ticker="LCID",
                second_ts=datetime(2026, 4, 10, 13, 30, 1, tzinfo=timezone.utc),
                open=3.10,
                high=3.16,
                low=3.09,
                close=3.15,
                volume=200,
                transactions=1,
            )
        ]
    )
    state = db.query(SymbolStateLive).filter_by(ticker="LCID").one()
    state.candidate_status = "buy"
    db.add(
        DecisionEvent(
            ticker="LCID",
            decision_ts=datetime(2026, 4, 10, 13, 30, 1),
            decision_type="buy",
            reason_code="validated_buy_setup",
            decision_payload='{"current_close": 3.15}',
            candidate_score=0.9,
            validation_pass_count=8,
            is_second_stream_stale=False,
            is_minute_stream_stale=False,
        )
    )
    db.commit()

    service = AggregateRuntimeService(db)
    first = service.refresh_validation_and_decisions(
        as_of=datetime(2026, 4, 10, 13, 30, 5, tzinfo=timezone.utc)
    )
    db.commit()
    second = service.refresh_validation_and_decisions(
        as_of=datetime(2026, 4, 10, 13, 30, 6, tzinfo=timezone.utc)
    )
    db.commit()

    decisions = db.query(DecisionEvent).filter_by(ticker="LCID").order_by(DecisionEvent.id.asc()).all()
    assert first.persisted_decision_count == 1
    assert second.persisted_decision_count == 0
    assert [row.reason_code for row in decisions] == [
        "validated_buy_setup",
        "active_position_second_stream_stale",
    ]


def test_aggregate_runtime_service_skips_validation_and_decisions_outside_regular_hours(db):
    aggregate_service = PolygonAggregateService(db)
    aggregate_service.upsert_minute_aggregates(
        [
            PolygonMinuteAggregateRecord(
                ticker="LCID",
                minute_ts=datetime(2026, 4, 10, 20, 0, 0, tzinfo=timezone.utc),
                open=3.00,
                high=3.20,
                low=2.99,
                close=3.18,
                volume=1_200,
            )
        ]
    )
    aggregate_service.upsert_second_aggregates(
        [
            PolygonSecondAggregateRecord(
                ticker="LCID",
                second_ts=datetime(2026, 4, 10, 19, 59, 58, tzinfo=timezone.utc),
                open=3.10,
                high=3.16,
                low=3.09,
                close=3.15,
                volume=200,
                transactions=1,
            )
        ]
    )
    state = db.query(SymbolStateLive).filter_by(ticker="LCID").one()
    state.candidate_status = "buy"
    db.add(
        DecisionEvent(
            ticker="LCID",
            decision_ts=datetime(2026, 4, 10, 19, 59, 58),
            decision_type="buy",
            reason_code="validated_buy_setup",
            decision_payload='{"current_close": 3.15}',
            candidate_score=0.9,
            validation_pass_count=8,
            is_second_stream_stale=False,
            is_minute_stream_stale=False,
        )
    )
    db.commit()

    result = AggregateRuntimeService(db).refresh_validation_and_decisions(
        as_of=datetime(2026, 4, 10, 20, 0, 5, tzinfo=timezone.utc)
    )
    db.commit()

    assert result.refreshed_state_count == 1
    assert result.refreshed_validation_count == 0
    assert result.persisted_decision_count == 0

    state = db.query(SymbolStateLive).filter_by(ticker="LCID").one()
    decisions = db.query(DecisionEvent).filter_by(ticker="LCID").all()
    assert state.is_second_stream_stale is True
    assert state.candidate_status == "buy"
    assert len(decisions) == 1


def test_aggregate_runtime_service_processes_candidate_events_promptly(db):
    aggregate_service = PolygonAggregateService(db)
    aggregate_service.upsert_minute_aggregates(
        [
            PolygonMinuteAggregateRecord(
                ticker="LCID",
                minute_ts=datetime(2026, 4, 10, 13, 45, 0, tzinfo=timezone.utc),
                open=3.00,
                high=3.30,
                low=2.99,
                close=3.26,
                volume=1800,
            )
        ]
    )
    aggregate_service.upsert_second_aggregates(
        [
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 45, 1, tzinfo=timezone.utc), 3.10, 3.16, 3.10, 3.15, 350, 3.14, 1),
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 45, 2, tzinfo=timezone.utc), 3.15, 3.21, 3.14, 3.20, 380, 3.19, 1),
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 45, 3, tzinfo=timezone.utc), 3.20, 3.27, 3.19, 3.26, 420, 3.25, 1),
        ]
    )
    db.commit()
    _seed_candidate_events(
        db,
        ticker="LCID",
        event_ts=datetime(2026, 4, 10, 13, 45, 3, tzinfo=timezone.utc),
        o=3.20,
        h=3.27,
        l=3.19,
        c=3.26,
        v=420,
        vw=3.25,
    )

    candidate_events = db.query(CandidateEvent).filter_by(ticker="LCID").all()
    assert len(candidate_events) >= 1
    assert db.query(DecisionEvent).filter_by(ticker="LCID").count() == 0

    result = AggregateRuntimeService(db).refresh_validation_and_decisions(
        as_of=datetime(2026, 4, 10, 13, 45, 4, tzinfo=timezone.utc)
    )
    db.commit()

    assert result.processed_candidate_event_count >= 1
    assert result.persisted_decision_count >= 1

    decisions = db.query(DecisionEvent).filter_by(ticker="LCID").all()
    assert len(decisions) >= 1
    assert all(event.processed_at is not None for event in candidate_events)


def test_aggregate_runtime_service_processes_candidate_events_when_event_ts_is_skewed(db):
    aggregate_service = PolygonAggregateService(db)
    aggregate_service.upsert_minute_aggregates(
        [
            PolygonMinuteAggregateRecord(
                ticker="LCID",
                minute_ts=datetime(2026, 4, 10, 13, 45, 0, tzinfo=timezone.utc),
                open=3.00,
                high=3.30,
                low=2.99,
                close=3.26,
                volume=1800,
            )
        ]
    )
    aggregate_service.upsert_second_aggregates(
        [
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 45, 1, tzinfo=timezone.utc), 3.10, 3.16, 3.10, 3.15, 350, 3.14, 1),
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 45, 2, tzinfo=timezone.utc), 3.15, 3.21, 3.14, 3.20, 380, 3.19, 1),
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 45, 3, tzinfo=timezone.utc), 3.20, 3.27, 3.19, 3.26, 420, 3.25, 1),
        ]
    )
    db.commit()
    _seed_candidate_events(
        db,
        ticker="LCID",
        event_ts=datetime(2026, 4, 10, 13, 45, 3, tzinfo=timezone.utc),
        o=3.20,
        h=3.27,
        l=3.19,
        c=3.26,
        v=420,
        vw=3.25,
    )

    candidate_events = db.query(CandidateEvent).filter_by(ticker="LCID").all()
    assert len(candidate_events) >= 1
    for event in candidate_events:
        event.event_ts = datetime(2026, 4, 10, 17, 45, 3)
    db.commit()

    result = AggregateRuntimeService(db).refresh_validation_and_decisions(
        as_of=datetime(2026, 4, 10, 13, 45, 4, tzinfo=timezone.utc)
    )
    db.commit()

    assert result.processed_candidate_event_count >= 1
    assert result.persisted_decision_count >= 1
    refreshed = db.query(CandidateEvent).filter_by(ticker="LCID").all()
    assert all(event.processed_at is not None for event in refreshed)


def test_aggregate_runtime_service_marks_stale_candidate_events_processed_without_decision(db):
    aggregate_service = PolygonAggregateService(db)
    aggregate_service.upsert_minute_aggregates(
        [
            PolygonMinuteAggregateRecord(
                ticker="LCID",
                minute_ts=datetime(2026, 4, 10, 13, 45, 0, tzinfo=timezone.utc),
                open=3.00,
                high=3.30,
                low=2.99,
                close=3.26,
                volume=1800,
            )
        ]
    )
    aggregate_service.upsert_second_aggregates(
        [
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 45, 1, tzinfo=timezone.utc), 3.10, 3.16, 3.10, 3.15, 350, 3.14, 1),
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 45, 2, tzinfo=timezone.utc), 3.15, 3.21, 3.14, 3.20, 380, 3.19, 1),
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 45, 3, tzinfo=timezone.utc), 3.20, 3.27, 3.19, 3.26, 420, 3.25, 1),
        ]
    )
    db.commit()
    _seed_candidate_events(
        db,
        ticker="LCID",
        event_ts=datetime(2026, 4, 10, 13, 45, 3, tzinfo=timezone.utc),
        o=3.20,
        h=3.27,
        l=3.19,
        c=3.26,
        v=420,
        vw=3.25,
    )

    candidate_events = db.query(CandidateEvent).filter_by(ticker="LCID").all()
    assert len(candidate_events) >= 1
    state = db.query(SymbolStateLive).filter_by(ticker="LCID").one()
    state.candidate_status = "idle"
    for event in candidate_events:
        event.event_ts = datetime(2026, 4, 10, 13, 44, 30)
        event.last_second_ts = datetime(2026, 4, 10, 13, 44, 30)
    db.commit()

    result = AggregateRuntimeService(db).refresh_validation_and_decisions(
        as_of=datetime(2026, 4, 10, 13, 45, 4, tzinfo=timezone.utc)
    )
    db.commit()

    assert result.processed_candidate_event_count >= 1
    assert result.persisted_decision_count == 0
    refreshed = db.query(CandidateEvent).filter_by(ticker="LCID").all()
    assert all(event.processed_at is not None for event in refreshed)
    assert db.query(DecisionEvent).filter_by(ticker="LCID").count() == 0


def test_aggregate_runtime_service_processes_candidates_even_if_latest_universe_changed(db):
    aggregate_service = PolygonAggregateService(db)
    aggregate_service.upsert_minute_aggregates(
        [
            PolygonMinuteAggregateRecord(
                ticker="LCID",
                minute_ts=datetime(2026, 4, 10, 13, 45, 0, tzinfo=timezone.utc),
                open=3.00,
                high=3.30,
                low=2.99,
                close=3.26,
                volume=1800,
            )
        ]
    )
    aggregate_service.upsert_second_aggregates(
        [
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 45, 1, tzinfo=timezone.utc), 3.10, 3.16, 3.10, 3.15, 350, 3.14, 1),
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 45, 2, tzinfo=timezone.utc), 3.15, 3.21, 3.14, 3.20, 380, 3.19, 1),
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 45, 3, tzinfo=timezone.utc), 3.20, 3.27, 3.19, 3.26, 420, 3.25, 1),
        ]
    )
    db.commit()
    _seed_candidate_events(
        db,
        ticker="LCID",
        event_ts=datetime(2026, 4, 10, 13, 45, 3, tzinfo=timezone.utc),
        o=3.20,
        h=3.27,
        l=3.19,
        c=3.26,
        v=420,
        vw=3.25,
    )

    db.query(UniverseDaily).delete()
    db.add(
        UniverseDaily(
            trade_date=date(2026, 4, 11),
            ticker="AAPL",
            open_price=150.0,
            last_price=151.0,
            avg_volume=1_000_000,
        )
    )
    db.commit()

    candidate_events = db.query(CandidateEvent).filter_by(ticker="LCID").all()
    assert len(candidate_events) >= 1

    result = AggregateRuntimeService(db).refresh_validation_and_decisions(
        as_of=datetime(2026, 4, 10, 13, 45, 4, tzinfo=timezone.utc)
    )
    db.commit()

    assert result.processed_candidate_event_count >= 1
    assert result.persisted_decision_count >= 1
    assert db.query(DecisionEvent).filter_by(ticker="LCID").count() >= 1
