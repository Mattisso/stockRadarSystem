from datetime import datetime, timezone

from app.data.polygon_aggregate_service import (
    PolygonAggregateService,
    PolygonMinuteAggregateRecord,
    PolygonSecondAggregateRecord,
)
from app.engine.aggregate_runtime_service import AggregateRuntimeService
from app.models.decision_event import DecisionEvent
from app.models.symbol_state_live import SymbolStateLive


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
