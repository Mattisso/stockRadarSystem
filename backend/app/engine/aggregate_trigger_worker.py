from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.market_hours import is_regular_us_market_hours
from app.data.polygon_aggregate_service import PolygonSecondAggregateRecord
from app.data.polygon_event_bus import PolygonEventBus
from app.data.polygon_event_models import PolygonAggregateEvent
from app.engine.aggregate_trigger_engine import AggregateTriggerEngine
from app.models.symbol_state_live import SymbolStateLive

log = get_logger(__name__)


class AggregateTriggerWorker:
    """Consume persisted second-bar events and emit candidate events downstream."""

    def __init__(
        self,
        event_bus: PolygonEventBus,
        db_session_factory,
        *,
        batch_size: int = 100,
        flush_interval_seconds: float = 0.5,
    ) -> None:
        self._event_bus = event_bus
        self._db_session_factory = db_session_factory
        self._batch_size = max(1, batch_size)
        self._flush_interval_seconds = max(0.05, flush_interval_seconds)
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run())
        log.info(
            "aggregate.trigger_worker_started",
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
        log.info("aggregate.trigger_worker_stopped")

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
                    self._process(pending)
                    pending = []
            except TimeoutError:
                if pending:
                    self._process(pending)
                    pending = []
            except asyncio.CancelledError:
                if pending:
                    self._process(pending)
                raise
            except Exception:
                log.exception("aggregate.trigger_worker_error")

    def _process(self, events: list[PolygonAggregateEvent]) -> None:
        db: Session = self._db_session_factory()
        try:
            trigger_engine = AggregateTriggerEngine(db)
            persisted_candidate_event_count = 0
            for event in events:
                if event.event_type != "A":
                    continue
                if not is_regular_us_market_hours(event.event_ts):
                    continue
                state = db.query(SymbolStateLive).filter_by(ticker=event.ticker.upper()).first()
                if state is None:
                    continue
                record = PolygonSecondAggregateRecord(
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
                triggers = trigger_engine.evaluate_second_bar(record, state)
                persisted_candidate_event_count += trigger_engine.persist_with_validation(
                    triggers,
                    state,
                    event_ts=record.second_ts,
                )
            db.commit()
            log.info(
                "aggregate.trigger_worker_batch_processed",
                second_event_count=sum(1 for event in events if event.event_type == "A"),
                persisted_candidate_event_count=persisted_candidate_event_count,
                processed_at=datetime.now(tz=timezone.utc).isoformat(),
            )
        except Exception:
            db.rollback()
            log.exception("aggregate.trigger_worker_batch_failed", event_count=len(events))
            raise
        finally:
            db.close()
            for _ in events:
                self._event_bus.task_done()
