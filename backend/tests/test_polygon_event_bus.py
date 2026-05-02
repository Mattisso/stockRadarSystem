"""Tests for PolygonEventBus queue semantics."""

import asyncio
from datetime import datetime, timezone

import pytest

from app.data.polygon_event_bus import PolygonEventBus
from app.data.polygon_event_models import PolygonAggregateEvent


def _make_event(ticker: str = "LCID", event_type: str = "A") -> PolygonAggregateEvent:
    now = datetime.now(tz=timezone.utc)
    return PolygonAggregateEvent(
        ticker=ticker,
        event_type=event_type,
        event_ts=now,
        received_at=now,
        subscription_generation_id=1,
        open=3.10,
        high=3.15,
        low=3.09,
        close=3.12,
        volume=500,
    )


@pytest.mark.asyncio
async def test_publish_and_read_single_event():
    bus = PolygonEventBus(maxsize=10)
    event = _make_event()

    await bus.publish(event)

    assert bus.qsize() == 1
    result = await bus.read()
    assert result is event
    assert bus.qsize() == 0


@pytest.mark.asyncio
async def test_publish_many_preserves_order():
    bus = PolygonEventBus(maxsize=10)
    events = [_make_event(ticker=f"T{i}") for i in range(5)]

    await bus.publish_many(events)

    assert bus.qsize() == 5
    for expected in events:
        result = await bus.read()
        assert result.ticker == expected.ticker


@pytest.mark.asyncio
async def test_read_nowait_raises_on_empty():
    bus = PolygonEventBus(maxsize=10)

    with pytest.raises(asyncio.QueueEmpty):
        bus.read_nowait()


@pytest.mark.asyncio
async def test_read_nowait_returns_event():
    bus = PolygonEventBus(maxsize=10)
    event = _make_event()
    await bus.publish(event)

    result = bus.read_nowait()

    assert result is event
    assert bus.qsize() == 0


@pytest.mark.asyncio
async def test_publish_blocks_when_full():
    bus = PolygonEventBus(maxsize=2)
    await bus.publish(_make_event(ticker="A"))
    await bus.publish(_make_event(ticker="B"))
    assert bus.qsize() == 2

    publish_completed = False

    async def delayed_publish():
        nonlocal publish_completed
        await bus.publish(_make_event(ticker="C"))
        publish_completed = True

    task = asyncio.create_task(delayed_publish())
    await asyncio.sleep(0.05)
    assert not publish_completed

    await bus.read()
    await asyncio.sleep(0.05)
    assert publish_completed
    assert bus.qsize() == 2
    task.cancel()


@pytest.mark.asyncio
async def test_task_done():
    bus = PolygonEventBus(maxsize=10)
    await bus.publish(_make_event())
    await bus.read()

    bus.task_done()


@pytest.mark.asyncio
async def test_qsize_tracks_depth():
    bus = PolygonEventBus(maxsize=100)
    assert bus.qsize() == 0

    for i in range(7):
        await bus.publish(_make_event(ticker=f"T{i}"))
    assert bus.qsize() == 7

    await bus.read()
    await bus.read()
    assert bus.qsize() == 5


@pytest.mark.asyncio
async def test_maxsize_clamped_to_at_least_one():
    bus = PolygonEventBus(maxsize=0)
    assert bus._queue.maxsize == 1
