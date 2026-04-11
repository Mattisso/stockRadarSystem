"""Buffered persistence for raw Polygon L1 events."""

from collections.abc import Callable

from sqlalchemy.orm import Session

from app.broker.interface import Quote
from app.core.logging import get_logger
from app.data.polygon_aggregate_service import PolygonAggregateService
from app.models.polygon_tick import PolygonTick

log = get_logger(__name__)


class PolygonTickPersister:
    """Persist raw Polygon quotes/trades to Postgres in small batches."""

    def __init__(
        self,
        db_session_factory: Callable[[], Session],
        *,
        batch_size: int = 100,
    ) -> None:
        self._db_session_factory = db_session_factory
        self._batch_size = max(1, batch_size)
        self._pending: list[PolygonTick] = []
        self._pending_quotes: list[Quote] = []

    def record(self, quote: Quote) -> None:
        self._pending_quotes.append(quote)
        self._pending.append(
            PolygonTick(
                ticker=quote.ticker,
                event_type=quote.event_type,
                bid=quote.bid,
                ask=quote.ask,
                last=quote.last,
                volume=max(0, quote.volume),
                tick_ts=quote.timestamp,
            )
        )
        if len(self._pending) >= self._batch_size:
            self.flush()

    def flush(self) -> None:
        if not self._pending:
            return

        db = self._db_session_factory()
        rows = self._pending
        quotes = self._pending_quotes
        self._pending = []
        self._pending_quotes = []
        try:
            db.add_all(rows)
            second_records = PolygonAggregateService.second_records_from_quotes(quotes)
            if second_records:
                PolygonAggregateService(db).upsert_second_aggregates(second_records)
            db.commit()
            log.info("polygon.tick_batch_persisted", count=len(rows), second_aggregate_count=len(second_records))
        except Exception:
            db.rollback()
            log.exception("polygon.tick_persist_failed", count=len(rows))
        finally:
            db.close()

    def close(self) -> None:
        self.flush()
