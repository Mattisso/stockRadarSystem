from datetime import datetime, timezone

from app.data.polygon_aggregate_service import PolygonAggregateService, PolygonMinuteAggregateRecord, PolygonSecondAggregateRecord
from app.engine.aggregate_validation_engine import AggregateValidationEngine
from app.models.symbol_state_live import SymbolStateLive


def test_validation_engine_scores_strong_breakout_sequence(db):
    service = PolygonAggregateService(db)
    service.upsert_minute_aggregates(
        [
            PolygonMinuteAggregateRecord(
                ticker="LCID",
                minute_ts=datetime(2026, 4, 10, 13, 40, 0, tzinfo=timezone.utc),
                open=3.00,
                high=3.20,
                low=2.99,
                close=3.15,
                volume=1000,
            ),
            PolygonMinuteAggregateRecord(
                ticker="LCID",
                minute_ts=datetime(2026, 4, 10, 13, 41, 0, tzinfo=timezone.utc),
                open=3.15,
                high=3.34,
                low=3.14,
                close=3.30,
                volume=1400,
            ),
        ]
    )
    service.upsert_second_aggregates(
        [
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 41, 1, tzinfo=timezone.utc), 3.10, 3.18, 3.10, 3.18, 350, 3.17, 1),
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 41, 2, tzinfo=timezone.utc), 3.18, 3.24, 3.17, 3.23, 380, 3.22, 1),
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 41, 3, tzinfo=timezone.utc), 3.23, 3.30, 3.22, 3.29, 420, 3.28, 1),
        ]
    )
    state = db.query(SymbolStateLive).filter_by(ticker="LCID").one()
    engine = AggregateValidationEngine(db)

    result = engine.evaluate("LCID", state, datetime(2026, 4, 10, 13, 41, 3, tzinfo=timezone.utc))
    engine.persist(state, result)

    assert result.pass_count >= 8
    assert result.score >= 0.8
    assert result.checks["momentum_still_positive"] is True
    assert result.checks["price_holds_near_high"] is True
    assert state.validation_score == result.score
    assert state.validation_pass_count == result.pass_count


def test_validation_engine_penalizes_fading_spike(db):
    service = PolygonAggregateService(db)
    service.upsert_minute_aggregates(
        [
            PolygonMinuteAggregateRecord(
                ticker="LCID",
                minute_ts=datetime(2026, 4, 10, 13, 42, 0, tzinfo=timezone.utc),
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
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 42, 1, tzinfo=timezone.utc), 3.10, 3.22, 3.10, 3.21, 180, 3.20, 1),
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 42, 2, tzinfo=timezone.utc), 3.21, 3.22, 3.05, 3.08, 120, 3.11, 1),
            PolygonSecondAggregateRecord("LCID", datetime(2026, 4, 10, 13, 42, 3, tzinfo=timezone.utc), 3.08, 3.09, 3.00, 3.01, 90, 3.03, 1),
        ]
    )
    state = db.query(SymbolStateLive).filter_by(ticker="LCID").one()
    engine = AggregateValidationEngine(db)

    result = engine.evaluate("LCID", state, datetime(2026, 4, 10, 13, 42, 3, tzinfo=timezone.utc))

    assert result.pass_count <= 4
    assert result.score <= 0.4
    assert result.checks["momentum_still_positive"] is False
    assert result.checks["price_holds_near_high"] is False
    assert result.checks["no_immediate_sharp_drop"] is False
