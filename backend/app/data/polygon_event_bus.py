from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Sequence
from uuid import uuid4

from redis.asyncio import Redis

from app.core.logging import get_logger
from app.core.metrics import POLYGON_EVENT_BUS_TOMBSTONES_ACKED
from app.data.polygon_event_models import PolygonAggregateEvent

log = get_logger(__name__)


class PolygonEventBus:
    """Normalized aggregate event bus with in-memory and Redis Streams modes."""

    def __init__(
        self,
        *,
        maxsize: int = 10000,
        redis_url: str | None = None,
        stream_name: str | None = None,
        consumer_group: str | None = None,
        consumer_name: str | None = None,
        stream_maxlen: int | None = None,
        janitor_interval_seconds: float = 300.0,
        janitor_idle_ms: int = 5 * 60 * 1000,
        janitor_batch_size: int = 100,
    ) -> None:
        self._queue: asyncio.Queue[PolygonAggregateEvent] = asyncio.Queue(maxsize=max(1, maxsize))
        self._redis_url = redis_url or ""
        self._stream_name = stream_name or ""
        self._consumer_group = consumer_group or ""
        self._consumer_name = consumer_name or f"consumer-{uuid4().hex[:8]}"
        self._stream_maxlen = max(1000, stream_maxlen or max(1, maxsize) * 10)
        self._redis: Redis | None = None
        self._pending_ids: deque[str] = deque()
        self._janitor_interval_seconds = max(1.0, janitor_interval_seconds)
        self._janitor_idle_ms = max(1, janitor_idle_ms)
        self._janitor_batch_size = max(1, janitor_batch_size)
        self._janitor_task: asyncio.Task | None = None

    @property
    def uses_redis_stream(self) -> bool:
        return bool(self._redis_url and self._stream_name and self._consumer_group)

    async def connect(self) -> None:
        if not self.uses_redis_stream:
            return
        self._redis = Redis.from_url(self._redis_url, decode_responses=True)
        await self._redis.ping()
        try:
            await self._redis.xgroup_create(
                name=self._stream_name,
                groupname=self._consumer_group,
                id="0",
                mkstream=True,
            )
        except Exception as exc:
            if "BUSYGROUP" not in str(exc):
                raise
        drained = await self._drain_tombstones()
        log.info(
            "polygon.event_bus_connected",
            stream_name=self._stream_name,
            consumer_group=self._consumer_group,
            consumer_name=self._consumer_name,
            mode="redis" if self.uses_redis_stream else "memory",
            tombstones_drained_on_connect=drained,
        )
        self._janitor_task = asyncio.create_task(self._run_janitor())

    async def disconnect(self) -> None:
        if self._janitor_task is not None:
            self._janitor_task.cancel()
            try:
                await self._janitor_task
            except asyncio.CancelledError:
                pass
            self._janitor_task = None
        self._pending_ids.clear()
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None

    async def publish(self, event: PolygonAggregateEvent) -> None:
        if self._redis is not None:
            await self._redis.xadd(
                self._stream_name,
                event.to_payload(),
                maxlen=self._stream_maxlen,
                approximate=True,
            )
            return
        await self._queue.put(event)

    async def publish_many(self, events: Sequence[PolygonAggregateEvent]) -> None:
        for event in events:
            await self.publish(event)

    async def read(self) -> PolygonAggregateEvent:
        if self._redis is not None:
            if not self._pending_ids:
                pending = await self._redis.xreadgroup(
                    groupname=self._consumer_group,
                    consumername=self._consumer_name,
                    streams={self._stream_name: "0"},
                    count=1,
                )
                pending_event = await self._decode_stream_event(pending)
                if pending_event is not None:
                    return pending_event

            while True:
                fresh = await self._redis.xreadgroup(
                    groupname=self._consumer_group,
                    consumername=self._consumer_name,
                    streams={self._stream_name: ">"},
                    count=1,
                    block=1000,
                )
                fresh_event = await self._decode_stream_event(fresh)
                if fresh_event is not None:
                    return fresh_event
        return await self._queue.get()

    def read_nowait(self) -> PolygonAggregateEvent:
        if self._redis is not None:
            raise asyncio.QueueEmpty()
        return self._queue.get_nowait()

    async def task_done(self) -> None:
        # Synchronous ack: the previous fire-and-forget asyncio.create_task path
        # let workers exit before XACK reached Redis, so the consumer-group
        # pending-list kept replaying the same events on restart (observed:
        # one HIMS aggregate processed 300x on 2026-05-04). Callers are all
        # already in async contexts, so awaiting here is safe.
        if self._redis is not None:
            if self._pending_ids:
                message_id = self._pending_ids.popleft()
                await self._ack_stream_message(message_id)
            return
        self._queue.task_done()

    def qsize(self) -> int:
        if self._redis is not None:
            return len(self._pending_ids)
        return self._queue.qsize()

    async def snapshot(self) -> dict:
        base = {
            "mode": "redis" if self._redis is not None else "memory",
            "stream_name": self._stream_name or None,
            "consumer_group": self._consumer_group or None,
            "consumer_name": self._consumer_name,
            "in_flight_pending_count": len(self._pending_ids),
            "pending_count": len(self._pending_ids),
            "lag_count": 0,
        }
        if self._redis is None or not self.uses_redis_stream:
            return base

        groups = await self._redis.xinfo_groups(self._stream_name)
        group = next((row for row in groups if row.get("name") == self._consumer_group), None)
        if group is None:
            return base

        return {
            **base,
            "pending_count": int(group.get("pending", 0) or 0),
            "lag_count": int(group.get("lag", 0) or 0),
            "entries_read": int(group.get("entries-read", 0) or 0),
        }

    async def _decode_stream_event(self, entries) -> PolygonAggregateEvent | None:
        if not entries:
            return None
        _, messages = entries[0]
        if not messages:
            return None
        message_id, payload = messages[0]
        # Empty payload = Redis Streams tombstone: the message_id is still in
        # the consumer group's PEL but the actual stream entry was trimmed by
        # XADD ... MAXLEN approximate. No producer bug; the event was
        # published correctly and is now physically gone. ACK silently and
        # do not route to the (future) malformed-payload DLQ.
        if hasattr(payload, "keys") and not payload:
            log.info(
                "polygon.event_bus_tombstone_acked",
                stream_name=self._stream_name,
                consumer_group=self._consumer_group,
                consumer_name=self._consumer_name,
                message_id=message_id,
                source="read",
            )
            await self._ack_stream_message(message_id)
            self._record_tombstones_acked(1, source="read")
            return None
        try:
            event = PolygonAggregateEvent.from_payload(payload)
        except Exception:
            log.exception(
                "polygon.event_bus_malformed_payload",
                stream_name=self._stream_name,
                consumer_group=self._consumer_group,
                consumer_name=self._consumer_name,
                message_id=message_id,
                payload_keys=sorted(payload.keys()) if hasattr(payload, "keys") else None,
            )
            await self._ack_stream_message(message_id)
            return None
        self._pending_ids.append(message_id)
        return event

    async def _ack_stream_message(self, message_id: str) -> None:
        if self._redis is None:
            return
        await self._redis.xack(self._stream_name, self._consumer_group, message_id)

    async def _drain_tombstones(self) -> int:
        """ACK the contiguous prefix of empty-payload PEL entries on connect.

        Without this, every read() call would trickle out one tombstone per
        flush, taking minutes to clean a large PEL backlog (observed on
        2026-05-11: ~20 tombstones drained over 4 min). Stops at the first
        non-empty entry so the normal read() loop handles real events.
        """
        if self._redis is None:
            return 0
        total = 0
        while True:
            entries = await self._redis.xreadgroup(
                groupname=self._consumer_group,
                consumername=self._consumer_name,
                streams={self._stream_name: "0"},
                count=self._janitor_batch_size,
            )
            if not entries:
                break
            _, messages = entries[0]
            if not messages:
                break
            ack_ids: list[str] = []
            saw_non_empty = False
            for message_id, payload in messages:
                if hasattr(payload, "keys") and not payload:
                    ack_ids.append(message_id)
                else:
                    saw_non_empty = True
                    break
            if ack_ids:
                await self._redis.xack(
                    self._stream_name,
                    self._consumer_group,
                    *ack_ids,
                )
                total += len(ack_ids)
                self._record_tombstones_acked(len(ack_ids), source="drain")
            if saw_non_empty or len(messages) < self._janitor_batch_size:
                break
        return total

    async def _run_janitor(self) -> None:
        """Periodically XAUTOCLAIM idle PEL entries and ACK tombstones.

        Self-heals orphaned PEL from retired consumer names (e.g. a previous
        pod that crashed before ACK). Non-empty entries reclaimed by this
        method end up in the current consumer's PEL and are picked up by
        the next read() "0" scan, so we do not need to re-enqueue them.
        """
        while True:
            try:
                await asyncio.sleep(self._janitor_interval_seconds)
                await self._reclaim_idle_tombstones()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception(
                    "polygon.event_bus_janitor_error",
                    stream_name=self._stream_name,
                    consumer_group=self._consumer_group,
                )

    async def _reclaim_idle_tombstones(self) -> int:
        if self._redis is None:
            return 0
        total = 0
        cursor = "0-0"
        while True:
            result = await self._redis.xautoclaim(
                name=self._stream_name,
                groupname=self._consumer_group,
                consumername=self._consumer_name,
                min_idle_time=self._janitor_idle_ms,
                start_id=cursor,
                count=self._janitor_batch_size,
            )
            next_cursor, claimed, _deleted_ids = (
                result if len(result) == 3 else (result[0], result[1], [])
            )
            if not claimed:
                break
            ack_ids = [
                message_id
                for message_id, payload in claimed
                if hasattr(payload, "keys") and not payload
            ]
            if ack_ids:
                await self._redis.xack(
                    self._stream_name,
                    self._consumer_group,
                    *ack_ids,
                )
                total += len(ack_ids)
                self._record_tombstones_acked(len(ack_ids), source="janitor")
            if not next_cursor or str(next_cursor) in {"0-0", "0"}:
                break
            cursor = next_cursor
        if total:
            log.info(
                "polygon.event_bus_janitor_reclaimed_tombstones",
                stream_name=self._stream_name,
                consumer_group=self._consumer_group,
                count=total,
            )
        return total

    def _record_tombstones_acked(self, count: int, *, source: str) -> None:
        if count <= 0:
            return
        POLYGON_EVENT_BUS_TOMBSTONES_ACKED.labels(
            stream=self._stream_name or "memory",
            group=self._consumer_group or "memory",
            source=source,
        ).inc(count)
