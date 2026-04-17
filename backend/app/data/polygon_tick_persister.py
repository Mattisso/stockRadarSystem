"""Buffered persistence for raw Polygon L1 events.

Raw ticks are persisted for L1 and audit use only. Aggregate second bars must
come from the Polygon ``A`` websocket feed, not reconstructed quote batches.
"""

from collections.abc import Callable
from collections import deque

from sqlalchemy.orm import Session

from app.broker.interface import Quote
from app.core.logging import get_logger
from app.models.polygon_tick import PolygonTick
from app.models.polygon_tick_live import PolygonTickLive

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
        self._pending_live: list[PolygonTickLive] = []
        self._pending_quotes: list[Quote] = []
        self._recent_keys: deque[tuple] = deque(maxlen=max(1000, self._batch_size * 8))
        self._recent_key_set: set[tuple] = set()

    def record(self, quote: Quote) -> None:
        key = (
            quote.ticker,
            quote.event_type,
            quote.bid,
            quote.ask,
            quote.last,
            max(0, quote.volume),
            quote.timestamp,
        )
        if key in self._recent_key_set:
            return
        if len(self._recent_keys) == self._recent_keys.maxlen:
            oldest = self._recent_keys.popleft()
            self._recent_key_set.discard(oldest)
        self._recent_keys.append(key)
        self._recent_key_set.add(key)
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
        self._pending_live.append(
            PolygonTickLive(
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
        live_rows = self._pending_live
        self._pending = []
        self._pending_live = []
        self._pending_quotes = []
        try:
            db.add_all(rows)
            db.add_all(live_rows)
            db.commit()
            log.info(
                "polygon.tick_batch_persisted",
                count=len(rows),
                live_count=len(live_rows),
                second_aggregate_count=0,
            )
        except Exception:
            db.rollback()
            log.exception("polygon.tick_persist_failed", count=len(rows))
        finally:
            db.close()

    def close(self) -> None:
        self.flush()
