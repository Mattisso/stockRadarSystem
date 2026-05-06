from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.signal import Signal

log = get_logger(__name__)


@dataclass(slots=True)
class SignalsRetentionResult:
    deleted_signal_rows: int
    cutoff_ts: datetime
    batches_run: int
    stopped_reason: str


class SignalsRetentionService:
    """Trim the historical signals table so it does not grow without bound.

    The dashboard's /api/signals listing orders by created_at DESC LIMIT N. An
    index on created_at makes that query cheap regardless of row count, but
    without retention the table accumulates indefinitely (852K rows in a
    single day during March 2026), which costs storage and slows down full
    scans for analytics.

    Deletes in batches so that:
      - each transaction is bounded (no multi-million-row WAL spike),
      - a stuck batch does not block writers for long,
      - operators can safely interrupt the job mid-purge.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def purge(
        self,
        *,
        retention_days: int,
        batch_size: int = 50_000,
        max_batches: int = 1_000,
        now: datetime | None = None,
    ) -> SignalsRetentionResult:
        if retention_days <= 0:
            raise ValueError("retention_days must be > 0")
        reference_time = now or datetime.now(timezone.utc)
        cutoff_ts = reference_time - timedelta(days=retention_days)

        total_deleted = 0
        batches_run = 0
        stopped_reason = "no_more_rows"

        # Each iteration runs a self-contained DELETE in its own transaction:
        # commits per batch so we don't accumulate WAL or lock the table for
        # the whole purge. The IN(subquery) constrains the delete to
        # <= batch_size rows via a primary-key lookup, which is fast given
        # the created_at index.
        for batches_run in range(1, max_batches + 1):
            victims = (
                select(Signal.id)
                .where(Signal.created_at < cutoff_ts)
                .order_by(Signal.created_at.asc())
                .limit(batch_size)
                .scalar_subquery()
            )
            stmt = (
                delete(Signal)
                .where(Signal.id.in_(victims))
                .execution_options(synchronize_session=False)
            )
            result = self.db.execute(stmt)
            self.db.commit()
            deleted_in_batch = result.rowcount or 0
            total_deleted += deleted_in_batch
            if deleted_in_batch < batch_size:
                stopped_reason = "no_more_rows"
                break
        else:
            stopped_reason = "max_batches_reached"

        return SignalsRetentionResult(
            deleted_signal_rows=total_deleted,
            cutoff_ts=cutoff_ts,
            batches_run=batches_run,
            stopped_reason=stopped_reason,
        )
