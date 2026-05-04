from datetime import datetime, timezone

import asyncio
import pytest

from app.data.polygon_aggregate_persistence_worker import PolygonAggregatePersistenceWorker
from app.data.polygon_event_bus import PolygonEventBus
from app.data.polygon_event_models import PolygonAggregateEvent
from app.models.polygon_minute_aggregate import PolygonMinuteAggregate
from app.models.polygon_second_aggregate import PolygonSecondAggregate


@pytest.mark.asyncio
async def test_persistence_worker_persists_aggregate_events(db, db_session_factory):
    event_bus = PolygonEventBus(maxsize=10)
    persisted_batches: list[tuple[int, int]] = []
    worker = PolygonAggregatePersistenceWorker(
        event_bus,
        db_session_factory,
        batch_size=10,
        flush_interval_seconds=0.05,
        on_batch_persisted=lambda minute_count, second_count, _persisted_at: persisted_batches.append((minute_count, second_count)),
    )

    now = datetime.now(tz=timezone.utc)
    await event_bus.publish(
        PolygonAggregateEvent(
            ticker="LCID",
            event_type="AM",
            event_ts=now,
            received_at=now,
            subscription_generation_id=1,
            open=3.40,
            high=3.50,
            low=3.39,
            close=3.48,
            volume=1000,
            vwap=3.45,
            transactions=10,
        )
    )
    await event_bus.publish(
        PolygonAggregateEvent(
            ticker="LCID",
            event_type="A",
            event_ts=now,
            received_at=now,
            subscription_generation_id=1,
            open=3.47,
            high=3.49,
            low=3.46,
            close=3.48,
            volume=100,
            vwap=3.48,
            transactions=4,
        )
    )

    await worker.start()
    await asyncio.sleep(0.2)
    await worker.stop()

    assert db.query(PolygonMinuteAggregate).count() == 1
    assert db.query(PolygonSecondAggregate).count() == 1
    assert persisted_batches == [(1, 1)]


@pytest.mark.asyncio
async def test_persistence_worker_merges_duplicate_second_events_within_single_batch(db, db_session_factory):
    event_bus = PolygonEventBus(maxsize=10)
    persisted_batches: list[tuple[int, int]] = []
    worker = PolygonAggregatePersistenceWorker(
        event_bus,
        db_session_factory,
        batch_size=10,
        flush_interval_seconds=0.05,
        on_batch_persisted=lambda minute_count, second_count, _persisted_at: persisted_batches.append((minute_count, second_count)),
    )

    now = datetime.now(tz=timezone.utc).replace(microsecond=123456)
    await event_bus.publish(
        PolygonAggregateEvent(
            ticker="LCID",
            event_type="A",
            event_ts=now,
            received_at=now,
            subscription_generation_id=1,
            open=3.47,
            high=3.49,
            low=3.46,
            close=3.48,
            volume=100,
            vwap=3.48,
            transactions=4,
        )
    )
    await event_bus.publish(
        PolygonAggregateEvent(
            ticker="LCID",
            event_type="A",
            event_ts=now.replace(microsecond=987654),
            received_at=now.replace(microsecond=987654),
            subscription_generation_id=1,
            open=3.48,
            high=3.52,
            low=3.45,
            close=3.50,
            volume=150,
            vwap=3.50,
            transactions=5,
        )
    )

    await worker.start()
    await asyncio.sleep(0.2)
    await worker.stop()

    rows = db.query(PolygonSecondAggregate).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.ticker == "LCID"
    assert row.high == 3.52
    assert row.low == 3.45
    assert row.close == 3.50
    assert row.volume == 250
    assert row.transactions == 9
    assert persisted_batches == [(0, 2)]
