"""Background consumer for Polygon quote queue."""

import asyncio
from typing import Any

from app.broker.interface import Quote
from app.core.logging import get_logger
from app.engine.breakout_engine import BreakoutEngine
from app.engine.l1_feature_engine import L1FeatureEngine

log = get_logger(__name__)


class BreakoutQueueConsumer:
    """Drain quotes from a queue and ingest them into the breakout engine."""

    def __init__(
        self,
        queue: asyncio.Queue[Quote],
        breakout_engine: BreakoutEngine,
        l1_feature_engine: L1FeatureEngine | None = None,
        tick_persister: Any | None = None,
    ) -> None:
        self._queue = queue
        self._breakout_engine = breakout_engine
        self._l1_feature_engine = l1_feature_engine
        self._tick_persister = tick_persister
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._running = True
        self._task = asyncio.create_task(self._run())
        log.info("polygon.queue_consumer_started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._tick_persister is not None:
            self._tick_persister.close()
        log.info("polygon.queue_consumer_stopped")

    async def _run(self) -> None:
        while self._running:
            quote = None
            try:
                quote = await self._queue.get()
                if self._tick_persister is not None:
                    self._tick_persister.record(quote)
                if quote.event_type == "quote":
                    self._breakout_engine.ingest(quote)
                if self._l1_feature_engine is not None:
                    self._l1_feature_engine.ingest(quote)
            except asyncio.CancelledError:
                break
            except Exception:
                log.exception("polygon.queue_consumer_error")
            finally:
                if quote is not None:
                    self._queue.task_done()
