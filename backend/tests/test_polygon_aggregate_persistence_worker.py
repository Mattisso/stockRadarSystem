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
