from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timezone

from app.core.market_hours import is_regular_us_market_time
from app.core.logging import get_logger
from app.data.polygon_aggregate_service import (
    PolygonAggregateService,
    PolygonMinuteAggregateRecord,
    PolygonSecondAggregateRecord,
)
from app.data.polygon_event_bus import PolygonEventBus
from app.data.polygon_event_models import PolygonAggregateEvent

log = get_logger(__name__)


class PolygonAggregatePersistenceWorker:
    """Consume normalized aggregate events and persist them off the websocket thread."""

    def __init__(
        self,
        event_bus: PolygonEventBus,
        db_session_factory,
        *,
        batch_size: int = 500,
        flush_interval_seconds: float = 0.5,
        on_batch_persisted: Callable[[int, int, datetime], None] | None = None,
        trigger_event_bus: PolygonEventBus | None = None,
    ) -> None:
        self._event_bus = event_bus
        self._db_session_factory = db_session_factory
        self._batch_size = max(1, batch_size)
        self._flush_interval_seconds = max(0.05, flush_interval_seconds)
        self._on_batch_persisted = on_batch_persisted
        self._trigger_event_bus = trigger_event_bus
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run())
        log.info(
            "polygon.aggregate_persistence_worker_started",
            batch_size=self._batch_size,
            flush_interval_seconds=self._flush_interval_seconds,
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
        log.info("polygon.aggregate_persistence_worker_stopped")

    async def _run(self) -> None:
        pending: list[PolygonAggregateEvent] = []
        while self._running:
            try:
                event = await asyncio.wait_for(
                    self._event_bus.read(),
                    timeout=self._flush_interval_seconds,
                )
                pending.append(event)
                if len(pending) >= self._batch_size:
                    await self._flush(pending)
                    pending = []
            except TimeoutError:
                if pending:
                    await self._flush(pending)
                    pending = []
            except asyncio.CancelledError:
                if pending:
                    await self._flush(pending)
                raise
            except Exception:
                log.exception("polygon.aggregate_persistence_worker_error")

    async def _flush(self, events: list[PolygonAggregateEvent]) -> None:
        minute_records: list[PolygonMinuteAggregateRecord] = []
        second_records: list[PolygonSecondAggregateRecord] = []

        for event in events:
            if not is_regular_us_market_time(event.event_ts):
                continue
            if event.event_type == "AM":
                minute_records.append(
                    PolygonMinuteAggregateRecord(
                        ticker=event.ticker,
                        minute_ts=event.event_ts,
                        open=event.open,
                        high=event.high,
                        low=event.low,
                        close=event.close,
                        volume=event.volume,
                        vwap=event.vwap,
                        transactions=event.transactions,
                    )
                )
            else:
                second_records.append(
                    PolygonSecondAggregateRecord(
                        ticker=event.ticker,
                        second_ts=event.event_ts,
                        open=event.open,
                        high=event.high,
                        low=event.low,
                        close=event.close,
                        volume=event.volume,
                        vwap=event.vwap,
                        transactions=event.transactions,
                    )
                )

        db = self._db_session_factory()
        try:
            aggregate_service = PolygonAggregateService(db)
            if minute_records:
                aggregate_service.upsert_minute_aggregates(minute_records)
            if second_records:
                aggregate_service.upsert_second_aggregates(second_records)
            db.commit()
            persisted_at = datetime.now(tz=timezone.utc)
            if self._trigger_event_bus is not None and second_records:
                trigger_events = [event for event in events if event.event_type == "A"]
                if trigger_events:
                    await self._trigger_event_bus.publish_many(trigger_events)
            if self._on_batch_persisted is not None:
                self._on_batch_persisted(len(minute_records), len(second_records), persisted_at)
            log.info(
                "polygon.aggregate_persistence_batch_committed",
                minute_count=len(minute_records),
                second_count=len(second_records),
                event_count=len(events),
            )
        except Exception:
            db.rollback()
            log.exception(
                "polygon.aggregate_persistence_batch_failed",
                minute_count=len(minute_records),
                second_count=len(second_records),
                event_count=len(events),
            )
            raise
        finally:
            db.close()
            for _ in events:
                self._event_bus.task_done()
