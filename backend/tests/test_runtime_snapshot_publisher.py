"""Tests for RuntimeSnapshotPublisher cross-pod runtime telemetry."""

import asyncio
from datetime import datetime, timezone

import pytest

from app.data.cache import InMemoryCache
from app.data.runtime_snapshot_publisher import RuntimeSnapshotPublisher


class _StubPolygonClient:
    def __init__(self, snapshot: dict) -> None:
        self._snapshot = snapshot

    def session_snapshot(self) -> dict:
        return dict(self._snapshot)


class _StubEventBus:
    def __init__(self, snapshot: dict) -> None:
        self._snapshot = snapshot

    async def snapshot(self) -> dict:
        return dict(self._snapshot)


class _StubPersistenceWorker:
    def __init__(self, snapshot: dict) -> None:
        self._snapshot = snapshot

    def snapshot(self) -> dict:
        return dict(self._snapshot)


@pytest.mark.asyncio
async def test_publish_once_writes_combined_payload_to_cache():
    cache = InMemoryCache(ttl=2)
    polygon = _StubPolygonClient({"connected": True, "subscriptions_paused": False, "subscription_count": 42})
    aggregate_bus = _StubEventBus({"mode": "redis", "pending_count": 0, "lag_count": 0})
    trigger_bus = _StubEventBus({"mode": "redis", "pending_count": 1, "lag_count": 0})
    persistence = _StubPersistenceWorker({"running": True, "error_count": 0, "last_flush_latency_ms": 12.3})

    publisher = RuntimeSnapshotPublisher(
        cache=cache,
        polygon_client=polygon,
        aggregate_event_bus=aggregate_bus,
        trigger_event_bus=trigger_bus,
        persistence_worker=persistence,
        ttl_seconds=10,
    )
    payload = await publisher.publish_once()

    snapshot = await cache.get_runtime_snapshot()
    assert snapshot is not None
    assert snapshot == payload
    assert snapshot["polygon_session"]["connected"] is True
    assert snapshot["aggregate_stream"]["pending_count"] == 0
    assert snapshot["trigger_stream"]["pending_count"] == 1
    assert snapshot["persistence"]["last_flush_latency_ms"] == 12.3
    # generated_at is present and parseable
    datetime.fromisoformat(snapshot["generated_at"])


@pytest.mark.asyncio
async def test_publish_once_tolerates_failing_source():
    # If one source raises, the rest still publish (so the UI degrades
    # gracefully — e.g. event-bus snapshot failing should not blank the
    # polygon session reading).
    cache = InMemoryCache(ttl=2)

    class _FailingBus:
        async def snapshot(self) -> dict:
            raise RuntimeError("snapshot blew up")

    polygon = _StubPolygonClient({"connected": True})
    publisher = RuntimeSnapshotPublisher(
        cache=cache,
        polygon_client=polygon,
        aggregate_event_bus=_FailingBus(),
        trigger_event_bus=None,
        persistence_worker=None,
    )

    payload = await publisher.publish_once()
    assert payload["polygon_session"]["connected"] is True
    assert payload["aggregate_stream"] == {}
    assert payload["trigger_stream"] == {}
    assert payload["persistence"] == {}


@pytest.mark.asyncio
async def test_get_runtime_snapshot_expires_after_ttl():
    cache = InMemoryCache(ttl=2)
    await cache.set_runtime_snapshot({"polygon_session": {"connected": True}}, ttl_seconds=1)
    assert (await cache.get_runtime_snapshot())["polygon_session"]["connected"] is True

    await asyncio.sleep(1.1)
    # After expiry the reader sees None — surfaces a dead worker as Down
    # within the TTL window rather than reporting a stale snapshot.
    assert await cache.get_runtime_snapshot() is None


@pytest.mark.asyncio
async def test_start_then_stop_publishes_at_least_once():
    cache = InMemoryCache(ttl=2)
    polygon = _StubPolygonClient({"connected": True, "subscription_count": 7})
    publisher = RuntimeSnapshotPublisher(
        cache=cache,
        polygon_client=polygon,
        aggregate_event_bus=None,
        trigger_event_bus=None,
        persistence_worker=None,
        interval_seconds=0.1,
        ttl_seconds=5,
    )

    await publisher.start()
    await asyncio.sleep(0.25)
    await publisher.stop()

    snapshot = await cache.get_runtime_snapshot()
    assert snapshot is not None
    assert snapshot["polygon_session"]["subscription_count"] == 7
