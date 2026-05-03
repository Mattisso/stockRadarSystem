from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Sequence
from uuid import uuid4

from redis.asyncio import Redis

from app.core.logging import get_logger
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
    ) -> None:
        self._queue: asyncio.Queue[PolygonAggregateEvent] = asyncio.Queue(maxsize=max(1, maxsize))
        self._redis_url = redis_url or ""
        self._stream_name = stream_name or ""
        self._consumer_group = consumer_group or ""
        self._consumer_name = consumer_name or f"consumer-{uuid4().hex[:8]}"
        self._stream_maxlen = max(1000, stream_maxlen or max(1, maxsize) * 10)
        self._redis: Redis | None = None
        self._pending_ids: deque[str] = deque()

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
        log.info(
            "polygon.event_bus_connected",
            stream_name=self._stream_name,
            consumer_group=self._consumer_group,
            consumer_name=self._consumer_name,
            mode="redis" if self.uses_redis_stream else "memory",
        )

    async def disconnect(self) -> None:
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
            pending = await self._redis.xreadgroup(
                groupname=self._consumer_group,
                consumername=self._consumer_name,
                streams={self._stream_name: "0"},
                count=1,
            )
            if pending:
                return self._decode_stream_event(pending)

            while True:
                fresh = await self._redis.xreadgroup(
                    groupname=self._consumer_group,
                    consumername=self._consumer_name,
                    streams={self._stream_name: ">"},
                    count=1,
                    block=1000,
                )
                if fresh:
                    return self._decode_stream_event(fresh)
        return await self._queue.get()

    def read_nowait(self) -> PolygonAggregateEvent:
        if self._redis is not None:
            raise asyncio.QueueEmpty()
        return self._queue.get_nowait()

    def task_done(self) -> None:
        if self._redis is not None:
            if self._pending_ids:
                message_id = self._pending_ids.popleft()
                asyncio.create_task(self._ack_stream_message(message_id))
            return
        self._queue.task_done()

    def qsize(self) -> int:
        if self._redis is not None:
            return len(self._pending_ids)
        return self._queue.qsize()

    def _decode_stream_event(self, entries) -> PolygonAggregateEvent:
        _, messages = entries[0]
        message_id, payload = messages[0]
        self._pending_ids.append(message_id)
        return PolygonAggregateEvent.from_payload(payload)

    async def _ack_stream_message(self, message_id: str) -> None:
        if self._redis is None:
            return
        await self._redis.xack(self._stream_name, self._consumer_group, message_id)
