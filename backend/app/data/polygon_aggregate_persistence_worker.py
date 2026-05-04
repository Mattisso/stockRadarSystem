from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timezone
import time

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
        self._last_flush_completed_at: datetime | None = None
        self._last_flush_latency_ms: float | None = None
        self._last_batch_event_count = 0
        self._last_batch_minute_count = 0
        self._last_batch_second_count = 0
        self._last_error_at: datetime | None = None
        self._last_error_message: str | None = None
        self._error_count = 0

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

    def snapshot(self) -> dict:
        return {
            "running": self._running,
            "batch_size": self._batch_size,
            "flush_interval_seconds": self._flush_interval_seconds,
            "last_flush_completed_at": self._last_flush_completed_at.isoformat()
            if self._last_flush_completed_at is not None
            else None,
            "last_flush_latency_ms": self._last_flush_latency_ms,
            "last_batch_event_count": self._last_batch_event_count,
            "last_batch_minute_count": self._last_batch_minute_count,
            "last_batch_second_count": self._last_batch_second_count,
            "error_count": self._error_count,
            "last_error_at": self._last_error_at.isoformat() if self._last_error_at is not None else None,
            "last_error_message": self._last_error_message,
        }

    async def _run(self) -> None:
        pending: list[PolygonAggregateEvent] = []
        batch_started_at: float | None = None
        while self._running:
            try:
                event = await asyncio.wait_for(
                    self._event_bus.read(),
                    timeout=self._flush_interval_seconds,
                )
                if not pending:
                    batch_started_at = time.monotonic()
                pending.append(event)
                should_flush = len(pending) >= self._batch_size
                if not should_flush and batch_started_at is not None:
                    should_flush = (time.monotonic() - batch_started_at) >= self._flush_interval_seconds
                if should_flush:
                    await self._flush(pending)
                    pending = []
                    batch_started_at = None
            except TimeoutError:
                if pending:
                    await self._flush(pending)
                    pending = []
                    batch_started_at = None
            except asyncio.CancelledError:
                if pending:
                    await self._flush(pending)
                raise
            except Exception:
                log.exception("polygon.aggregate_persistence_worker_error")

    async def _flush(self, events: list[PolygonAggregateEvent]) -> None:
        flush_started_at = time.monotonic()
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
            self._last_flush_completed_at = persisted_at
            self._last_flush_latency_ms = (time.monotonic() - flush_started_at) * 1000.0
            self._last_batch_event_count = len(events)
            self._last_batch_minute_count = len(minute_records)
            self._last_batch_second_count = len(second_records)
            log.info(
                "polygon.aggregate_persistence_batch_committed",
                minute_count=len(minute_records),
                second_count=len(second_records),
                event_count=len(events),
            )
        except Exception:
            db.rollback()
            self._error_count += 1
            self._last_error_at = datetime.now(tz=timezone.utc)
            self._last_error_message = "aggregate_persistence_batch_failed"
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
