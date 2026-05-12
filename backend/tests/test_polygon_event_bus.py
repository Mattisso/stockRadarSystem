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


class _FakeRedisStream:
    def __init__(self) -> None:
        self.messages: list[tuple[str, dict[str, str]]] = []
        self.acked: list[str] = []
        self._next_id = 1

    async def xadd(self, stream_name: str, payload: dict[str, str], maxlen: int, approximate: bool) -> str:
        message_id = str(self._next_id)
        self._next_id += 1
        self.messages.append((message_id, payload))
        return message_id

    async def xreadgroup(self, *, groupname, consumername, streams, count, block=None):
        target = next(iter(streams.values()))
        if target == "0" and self.messages:
            message_id, payload = self.messages[0]
            return [("stream", [(message_id, payload)])]
        if target == ">" and self.messages:
            message_id, payload = self.messages[0]
            return [("stream", [(message_id, payload)])]
        return []

    async def xack(self, stream_name: str, group_name: str, *message_ids: str) -> int:
        acked = 0
        for message_id in message_ids:
            self.acked.append(message_id)
            self.messages = [entry for entry in self.messages if entry[0] != message_id]
            acked += 1
        return acked


class _FakeRedisStreamWithEmptyPending(_FakeRedisStream):
    def __init__(self) -> None:
        super().__init__()
        self._first_pending_read = True

    async def xreadgroup(self, *, groupname, consumername, streams, count, block=None):
        target = next(iter(streams.values()))
        if target == "0" and self._first_pending_read:
            self._first_pending_read = False
            return [("stream", [])]
        return await super().xreadgroup(
            groupname=groupname,
            consumername=consumername,
            streams=streams,
            count=count,
            block=block,
        )


class _FakeRedisStreamWithStickyPending(_FakeRedisStream):
    def __init__(self) -> None:
        super().__init__()
        self._pending_message: tuple[str, dict[str, str]] | None = None
        self._fresh_messages: list[tuple[str, dict[str, str]]] = []

    async def xadd(self, stream_name: str, payload: dict[str, str], maxlen: int, approximate: bool) -> str:
        message_id = str(self._next_id)
        self._next_id += 1
        if self._pending_message is None:
            self._pending_message = (message_id, payload)
        else:
            self._fresh_messages.append((message_id, payload))
        return message_id

    async def xreadgroup(self, *, groupname, consumername, streams, count, block=None):
        target = next(iter(streams.values()))
        if target == "0" and self._pending_message is not None:
            return [("stream", [self._pending_message])]
        if target == ">" and self._fresh_messages:
            message_id, payload = self._fresh_messages.pop(0)
            return [("stream", [(message_id, payload)])]
        return []

    async def xack(self, stream_name: str, group_name: str, *message_ids: str) -> int:
        acked = 0
        for message_id in message_ids:
            self.acked.append(message_id)
            if self._pending_message is not None and self._pending_message[0] == message_id:
                self._pending_message = None
            acked += 1
        return acked


class _FakeRedisStreamWithMalformedPending(_FakeRedisStream):
    def __init__(self) -> None:
        super().__init__()
        self._malformed_returned = False
        self._next_id = 2

    async def xreadgroup(self, *, groupname, consumername, streams, count, block=None):
        target = next(iter(streams.values()))
        if target == "0" and not self._malformed_returned:
            self._malformed_returned = True
            return [("stream", [("1", {"event_type": "A"})])]
        if target == ">" and self.messages:
            message_id, payload = self.messages[0]
            return [("stream", [(message_id, payload)])]
        return []

    async def xack(self, stream_name: str, group_name: str, *message_ids: str) -> int:
        acked = 0
        for message_id in message_ids:
            self.acked.append(message_id)
            self.messages = [entry for entry in self.messages if entry[0] != message_id]
            acked += 1
        return acked


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

    await bus.task_done()


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


@pytest.mark.asyncio
async def test_redis_stream_mode_round_trips_event_and_acks():
    bus = PolygonEventBus(
        maxsize=10,
        redis_url="redis://unit-test",
        stream_name="stockradar:polygon:aggregate",
        consumer_group="aggregate-persistence",
        consumer_name="aggregate-persistence",
    )
    bus._redis = _FakeRedisStream()
    event = _make_event(ticker="TEST", event_type="AM")

    await bus.publish(event)
    result = await bus.read()
    await bus.task_done()

    assert result.ticker == "TEST"
    assert result.event_type == "AM"
    assert result.event_ts == event.event_ts
    assert result.received_at == event.received_at
    assert result.volume == event.volume
    assert bus._redis.acked == ["1"]


@pytest.mark.asyncio
async def test_redis_stream_mode_ignores_empty_pending_read_and_reads_fresh_event():
    bus = PolygonEventBus(
        maxsize=10,
        redis_url="redis://unit-test",
        stream_name="stockradar:polygon:aggregate",
        consumer_group="aggregate-persistence",
        consumer_name="aggregate-persistence",
    )
    bus._redis = _FakeRedisStreamWithEmptyPending()
    event = _make_event(ticker="TEST2", event_type="A")

    await bus.publish(event)
    result = await bus.read()
    await bus.task_done()

    assert result.ticker == "TEST2"
    assert result.event_type == "A"
    assert bus._redis.acked == ["1"]


@pytest.mark.asyncio
async def test_redis_stream_mode_does_not_replay_same_pending_message_while_unacked():
    bus = PolygonEventBus(
        maxsize=10,
        redis_url="redis://unit-test",
        stream_name="stockradar:polygon:aggregate",
        consumer_group="aggregate-persistence",
        consumer_name="aggregate-persistence",
    )
    bus._redis = _FakeRedisStreamWithStickyPending()
    pending_event = _make_event(ticker="PENDING", event_type="A")
    fresh_event = _make_event(ticker="FRESH", event_type="A")

    await bus.publish(pending_event)
    await bus.publish(fresh_event)

    first = await bus.read()
    second = await bus.read()

    assert first.ticker == "PENDING"
    assert second.ticker == "FRESH"

    await bus.task_done()
    await bus.task_done()

    assert bus._redis.acked == ["1", "2"]


@pytest.mark.asyncio
async def test_redis_stream_mode_acks_and_skips_malformed_pending_payload():
    bus = PolygonEventBus(
        maxsize=10,
        redis_url="redis://unit-test",
        stream_name="stockradar:polygon:aggregate",
        consumer_group="aggregate-persistence",
        consumer_name="aggregate-persistence",
    )
    bus._redis = _FakeRedisStreamWithMalformedPending()
    fresh_event = _make_event(ticker="FRESH", event_type="A")

    await bus.publish(fresh_event)
    result = await bus.read()
    await bus.task_done()

    assert result.ticker == "FRESH"
    assert bus._redis.acked == ["1", "2"]


class _FakeRedisStreamWithTombstonePending(_FakeRedisStream):
    """Pending replay returns a Redis Streams tombstone (empty payload) first."""

    def __init__(self) -> None:
        super().__init__()
        self._tombstone_returned = False
        self._next_id = 2

    async def xreadgroup(self, *, groupname, consumername, streams, count, block=None):
        target = next(iter(streams.values()))
        if target == "0" and not self._tombstone_returned:
            self._tombstone_returned = True
            return [("stream", [("1", {})])]
        if target == ">" and self.messages:
            message_id, payload = self.messages[0]
            return [("stream", [(message_id, payload)])]
        return []


class _FakeRedisStreamWithTombstoneBacklog(_FakeRedisStream):
    """PEL replay returns N tombstones in a single batch, then no more."""

    def __init__(self, tombstone_count: int) -> None:
        super().__init__()
        self._tombstone_ids = [str(i) for i in range(1, tombstone_count + 1)]
        self._delivered = False
        self._next_id = tombstone_count + 1

    async def xreadgroup(self, *, groupname, consumername, streams, count, block=None):
        target = next(iter(streams.values()))
        if target == "0" and not self._delivered:
            self._delivered = True
            return [("stream", [(mid, {}) for mid in self._tombstone_ids])]
        return []


@pytest.mark.asyncio
async def test_redis_stream_mode_acks_tombstone_silently_and_records_metric():
    bus = PolygonEventBus(
        maxsize=10,
        redis_url="redis://unit-test",
        stream_name="stockradar:polygon:aggregate",
        consumer_group="aggregate-persistence",
        consumer_name="aggregate-persistence",
    )
    bus._redis = _FakeRedisStreamWithTombstonePending()
    fresh_event = _make_event(ticker="FRESH_AFTER_TOMB", event_type="A")

    from app.core.metrics import POLYGON_EVENT_BUS_TOMBSTONES_ACKED

    counter = POLYGON_EVENT_BUS_TOMBSTONES_ACKED.labels(
        stream="stockradar:polygon:aggregate",
        group="aggregate-persistence",
        source="read",
    )
    before = counter._value.get()

    await bus.publish(fresh_event)
    result = await bus.read()
    await bus.task_done()

    assert result.ticker == "FRESH_AFTER_TOMB"
    assert "1" in bus._redis.acked
    assert "2" in bus._redis.acked
    assert counter._value.get() == before + 1


@pytest.mark.asyncio
async def test_drain_tombstones_drains_full_backlog_in_one_pass():
    bus = PolygonEventBus(
        maxsize=10,
        redis_url="redis://unit-test",
        stream_name="stockradar:polygon:aggregate",
        consumer_group="aggregate-persistence",
        consumer_name="aggregate-persistence",
        janitor_batch_size=100,
    )
    bus._redis = _FakeRedisStreamWithTombstoneBacklog(tombstone_count=17)

    from app.core.metrics import POLYGON_EVENT_BUS_TOMBSTONES_ACKED

    counter = POLYGON_EVENT_BUS_TOMBSTONES_ACKED.labels(
        stream="stockradar:polygon:aggregate",
        group="aggregate-persistence",
        source="drain",
    )
    before = counter._value.get()

    drained = await bus._drain_tombstones()

    assert drained == 17
    assert bus._redis.acked == [str(i) for i in range(1, 18)]
    assert counter._value.get() == before + 17


@pytest.mark.asyncio
async def test_drain_tombstones_stops_at_first_non_empty_payload():
    bus = PolygonEventBus(
        maxsize=10,
        redis_url="redis://unit-test",
        stream_name="stockradar:polygon:aggregate",
        consumer_group="aggregate-persistence",
        consumer_name="aggregate-persistence",
        janitor_batch_size=100,
    )

    class _Mixed(_FakeRedisStream):
        def __init__(self) -> None:
            super().__init__()
            self._delivered = False

        async def xreadgroup(self, *, groupname, consumername, streams, count, block=None):
            target = next(iter(streams.values()))
            if target == "0" and not self._delivered:
                self._delivered = True
                return [
                    (
                        "stream",
                        [
                            ("1", {}),
                            ("2", {}),
                            ("3", {"ticker": "STOP"}),
                            ("4", {}),
                        ],
                    )
                ]
            return []

    bus._redis = _Mixed()
    drained = await bus._drain_tombstones()

    assert drained == 2
    assert bus._redis.acked == ["1", "2"]


class _FakeRedisStreamWithJanitor(_FakeRedisStream):
    """Supports xautoclaim returning a mix of tombstones and live entries."""

    def __init__(self, claimed: list[tuple[str, dict]]) -> None:
        super().__init__()
        self._claimed = claimed
        self._called = False

    async def xautoclaim(
        self,
        *,
        name,
        groupname,
        consumername,
        min_idle_time,
        start_id,
        count,
    ):
        if self._called:
            return ("0-0", [], [])
        self._called = True
        return ("0-0", list(self._claimed), [])


@pytest.mark.asyncio
async def test_janitor_acks_only_tombstones_from_xautoclaim():
    bus = PolygonEventBus(
        maxsize=10,
        redis_url="redis://unit-test",
        stream_name="stockradar:polygon:aggregate",
        consumer_group="aggregate-persistence",
        consumer_name="aggregate-persistence",
    )
    bus._redis = _FakeRedisStreamWithJanitor(
        claimed=[
            ("10", {}),
            ("11", {"ticker": "REAL", "event_type": "A"}),
            ("12", {}),
        ]
    )

    from app.core.metrics import POLYGON_EVENT_BUS_TOMBSTONES_ACKED

    counter = POLYGON_EVENT_BUS_TOMBSTONES_ACKED.labels(
        stream="stockradar:polygon:aggregate",
        group="aggregate-persistence",
        source="janitor",
    )
    before = counter._value.get()

    reclaimed = await bus._reclaim_idle_tombstones()

    assert reclaimed == 2
    assert bus._redis.acked == ["10", "12"]
    assert counter._value.get() == before + 2
