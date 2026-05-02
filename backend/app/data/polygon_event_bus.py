from __future__ import annotations

import asyncio
from collections.abc import Sequence

from app.data.polygon_event_models import PolygonAggregateEvent


class PolygonEventBus:
    """Hot in-process queue for normalized Polygon aggregate events."""

    def __init__(self, *, maxsize: int = 10000) -> None:
        self._queue: asyncio.Queue[PolygonAggregateEvent] = asyncio.Queue(maxsize=max(1, maxsize))

    async def publish(self, event: PolygonAggregateEvent) -> None:
        await self._queue.put(event)

    async def publish_many(self, events: Sequence[PolygonAggregateEvent]) -> None:
        for event in events:
            await self.publish(event)

    async def read(self) -> PolygonAggregateEvent:
        return await self._queue.get()

    def read_nowait(self) -> PolygonAggregateEvent:
        return self._queue.get_nowait()

    def task_done(self) -> None:
        self._queue.task_done()

    def qsize(self) -> int:
        return self._queue.qsize()
