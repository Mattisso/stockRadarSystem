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


@pytest.mark.asyncio
async def test_persistence_worker_flushes_small_live_batch_without_waiting_for_full_batch(db, db_session_factory):
    event_bus = PolygonEventBus(maxsize=10)
    persisted_batches: list[tuple[int, int]] = []
    worker = PolygonAggregatePersistenceWorker(
        event_bus,
        db_session_factory,
        batch_size=500,
        flush_interval_seconds=0.05,
        on_batch_persisted=lambda minute_count, second_count, _persisted_at: persisted_batches.append((minute_count, second_count)),
    )

    now = datetime.now(tz=timezone.utc)
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
            ticker="SIRI",
            event_type="A",
            event_ts=now,
            received_at=now,
            subscription_generation_id=1,
            open=6.12,
            high=6.15,
            low=6.11,
            close=6.14,
            volume=200,
            vwap=6.13,
            transactions=6,
        )
    )

    await worker.start()
    await asyncio.sleep(0.2)
    await worker.stop()

    assert db.query(PolygonSecondAggregate).count() == 2
    assert persisted_batches == [(0, 2)]


@pytest.mark.asyncio
async def test_persistence_worker_does_not_ack_when_commit_fails(db_session_factory):
    # Regression: prior to the ack-after-commit fix the worker fire-and-forgot
    # XACK before commit, so a failing commit silently consumed the message and
    # the redelivery path could not recover it. Verify the message is NOT acked
    # when commit raises.
    event_bus = PolygonEventBus(maxsize=10)

    def failing_session_factory():
        session = db_session_factory()
        def _raise():
            raise RuntimeError("commit failed (simulated)")
        session.commit = _raise  # type: ignore[method-assign]
        return session

    worker = PolygonAggregatePersistenceWorker(
        event_bus,
        failing_session_factory,
        batch_size=10,
        flush_interval_seconds=0.05,
    )

    market_hours_ts = datetime(2026, 4, 10, 14, 30, 0, tzinfo=timezone.utc)  # 10:30 ET, Friday
    event = PolygonAggregateEvent(
        ticker="LCID",
        event_type="A",
        event_ts=market_hours_ts,
        received_at=market_hours_ts,
        subscription_generation_id=1,
        open=3.47,
        high=3.49,
        low=3.46,
        close=3.48,
        volume=100,
        vwap=3.48,
        transactions=4,
    )
    await event_bus.publish(event)
    assert event_bus._queue._unfinished_tasks == 1

    with pytest.raises(RuntimeError, match="commit failed"):
        await worker._flush([event])

    # Critical invariant: commit failed, so the message must remain pending for
    # Redis Streams to redeliver. If task_done() were called, the consumer group
    # would advance past this message and the data would be lost.
    assert event_bus._queue._unfinished_tasks == 1
