from datetime import datetime, timezone

import asyncio
import pytest
from unittest.mock import AsyncMock

from app.data.polygon_aggregate_service import PolygonMinuteAggregateRecord, PolygonSecondAggregateRecord, PolygonAggregateService
from app.data.polygon_event_bus import PolygonEventBus
from app.data.polygon_event_models import PolygonAggregateEvent
from app.engine.aggregate_trigger_worker import AggregateTriggerWorker
from app.models.candidate_event import CandidateEvent
from app.models.symbol_state_live import SymbolStateLive


@pytest.mark.asyncio
async def test_aggregate_trigger_worker_persists_candidate_events(db, db_session_factory):
    service = PolygonAggregateService(db)
    service.upsert_minute_aggregates(
        [
            PolygonMinuteAggregateRecord(
                ticker="LCID",
                minute_ts=datetime(2026, 4, 4, 14, 31, 0, tzinfo=timezone.utc),
                open=3.00,
                high=3.30,
                low=2.99,
                close=3.26,
                volume=1800,
            )
        ]
    )
    service.upsert_second_aggregates(
        [
            PolygonSecondAggregateRecord(
                ticker="LCID",
                second_ts=datetime(2026, 4, 4, 14, 31, 1, tzinfo=timezone.utc),
                open=3.10,
                high=3.16,
                low=3.10,
                close=3.15,
                volume=350,
                transactions=1,
            ),
            PolygonSecondAggregateRecord(
                ticker="LCID",
                second_ts=datetime(2026, 4, 4, 14, 31, 2, tzinfo=timezone.utc),
                open=3.15,
                high=3.21,
                low=3.14,
                close=3.20,
                volume=380,
                transactions=1,
            ),
        ]
    )
    db.commit()

    state = db.query(SymbolStateLive).filter_by(ticker="LCID").one()
    assert state.candidate_score is None

    event_bus = PolygonEventBus(maxsize=10)
    worker = AggregateTriggerWorker(
        event_bus,
        db_session_factory,
        batch_size=10,
        flush_interval_seconds=0.05,
    )
    now = datetime(2026, 4, 4, 14, 31, 3, tzinfo=timezone.utc)
    await event_bus.publish(
        PolygonAggregateEvent(
            ticker="LCID",
            event_type="A",
            event_ts=now,
            received_at=now,
            subscription_generation_id=1,
            open=3.20,
            high=3.27,
            low=3.19,
            close=3.26,
            volume=420,
            vwap=3.23,
            transactions=1,
        )
    )

    await worker.start()
    await asyncio.sleep(0.2)
    await worker.stop()

    assert db.query(CandidateEvent).count() > 0
    db.expire_all()
    state = db.query(SymbolStateLive).filter_by(ticker="LCID").one()
    assert state.candidate_status == "validated"
    assert state.candidate_score is not None
    assert state.validation_score is not None


@pytest.mark.asyncio
async def test_aggregate_trigger_worker_notifies_candidate_lifecycle_refresh(db, db_session_factory):
    service = PolygonAggregateService(db)
    service.upsert_minute_aggregates(
        [
            PolygonMinuteAggregateRecord(
                ticker="LCID",
                minute_ts=datetime(2026, 4, 4, 14, 31, 0, tzinfo=timezone.utc),
                open=3.00,
                high=3.30,
                low=2.99,
                close=3.26,
                volume=1800,
            )
        ]
    )
    service.upsert_second_aggregates(
        [
            PolygonSecondAggregateRecord(
                ticker="LCID",
                second_ts=datetime(2026, 4, 4, 14, 31, 1, tzinfo=timezone.utc),
                open=3.10,
                high=3.16,
                low=3.10,
                close=3.15,
                volume=350,
                transactions=1,
            ),
            PolygonSecondAggregateRecord(
                ticker="LCID",
                second_ts=datetime(2026, 4, 4, 14, 31, 2, tzinfo=timezone.utc),
                open=3.15,
                high=3.21,
                low=3.14,
                close=3.20,
                volume=380,
                transactions=1,
            ),
        ]
    )
    db.commit()

    callback = AsyncMock()
    event_bus = PolygonEventBus(maxsize=10)
    worker = AggregateTriggerWorker(
        event_bus,
        db_session_factory,
        batch_size=10,
        flush_interval_seconds=0.05,
        on_candidate_events_persisted=callback,
    )
    now = datetime(2026, 4, 4, 14, 31, 3, tzinfo=timezone.utc)
    await event_bus.publish(
        PolygonAggregateEvent(
            ticker="LCID",
            event_type="A",
            event_ts=now,
            received_at=now,
            subscription_generation_id=1,
            open=3.20,
            high=3.27,
            low=3.19,
            close=3.26,
            volume=420,
            vwap=3.23,
            transactions=1,
        )
    )

    await worker.start()
    await asyncio.sleep(0.2)
    await worker.stop()

    callback.assert_awaited_once_with(["LCID"])
