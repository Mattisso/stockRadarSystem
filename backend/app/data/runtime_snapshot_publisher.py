from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from app.core.logging import get_logger
from app.data.cache import CacheInterface

log = get_logger(__name__)


class RuntimeSnapshotPublisher:
    """Periodically publish in-process runtime telemetry to the shared cache.

    The web pod (role=web) does not own the polygon_client, event buses, or
    persistence worker — those live in the polygon-ingest worker pod
    (role=worker). To let the web pod serve runtime KPIs honestly, the worker
    serializes its snapshots to a fixed cache key with a short TTL; the web
    pod reads that key. TTL expiry surfaces a dead worker as "Down" within
    `ttl_seconds` rather than reporting a stale snapshot indefinitely.
    """

    DEFAULT_INTERVAL_SECONDS = 1.0
    DEFAULT_TTL_SECONDS = 10

    def __init__(
        self,
        *,
        cache: CacheInterface,
        polygon_client: Any | None = None,
        aggregate_event_bus: Any | None = None,
        trigger_event_bus: Any | None = None,
        persistence_worker: Any | None = None,
        interval_seconds: float = DEFAULT_INTERVAL_SECONDS,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> None:
        self._cache = cache
        self._polygon_client = polygon_client
        self._aggregate_event_bus = aggregate_event_bus
        self._trigger_event_bus = trigger_event_bus
        self._persistence_worker = persistence_worker
        self._interval_seconds = max(0.1, interval_seconds)
        self._ttl_seconds = max(2, ttl_seconds)
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run())
        log.info(
            "runtime_snapshot.publisher_started",
            interval_seconds=self._interval_seconds,
            ttl_seconds=self._ttl_seconds,
        )

    async def stop(self) -> None:
        self._running = False
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        log.info("runtime_snapshot.publisher_stopped")

    async def publish_once(self) -> dict:
        payload = await self._build_payload()
        await self._cache.set_runtime_snapshot(payload, self._ttl_seconds)
        return payload

    async def _run(self) -> None:
        while self._running:
            try:
                await self.publish_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("runtime_snapshot.publish_failed")
            try:
                await asyncio.sleep(self._interval_seconds)
            except asyncio.CancelledError:
                raise

    async def _build_payload(self) -> dict:
        polygon_session: dict = {}
        if self._polygon_client is not None:
            try:
                polygon_session = self._polygon_client.session_snapshot()
            except Exception:
                log.exception("runtime_snapshot.polygon_session_failed")

        aggregate_stream: dict = {}
        if self._aggregate_event_bus is not None:
            try:
                aggregate_stream = await self._aggregate_event_bus.snapshot()
            except Exception:
                log.exception("runtime_snapshot.aggregate_stream_failed")

        trigger_stream: dict = {}
        if self._trigger_event_bus is not None:
            try:
                trigger_stream = await self._trigger_event_bus.snapshot()
            except Exception:
                log.exception("runtime_snapshot.trigger_stream_failed")

        persistence: dict = {}
        if self._persistence_worker is not None:
            try:
                persistence = self._persistence_worker.snapshot()
            except Exception:
                log.exception("runtime_snapshot.persistence_failed")

        return {
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
            "polygon_session": polygon_session,
            "aggregate_stream": aggregate_stream,
            "trigger_stream": trigger_stream,
            "persistence": persistence,
        }
