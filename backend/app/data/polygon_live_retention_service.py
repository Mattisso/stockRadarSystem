from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.polygon_second_aggregate_live import PolygonSecondAggregateLive
from app.models.polygon_tick_live import PolygonTickLive


@dataclass(slots=True)
class PolygonLiveRetentionResult:
    deleted_tick_rows: int
    deleted_second_rows: int
    tick_cutoff_ts: datetime
    second_cutoff_ts: datetime


class PolygonLiveRetentionService:
    """Trim hot operational Polygon tables so they do not become history tables."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def purge(
        self,
        *,
        tick_retention_hours: int,
        second_retention_hours: int,
        now: datetime | None = None,
    ) -> PolygonLiveRetentionResult:
        reference_time = now or datetime.now(timezone.utc)
        tick_cutoff_ts = reference_time - timedelta(hours=max(1, tick_retention_hours))
        second_cutoff_ts = reference_time - timedelta(hours=max(1, second_retention_hours))

        deleted_tick_rows = (
            self.db.query(PolygonTickLive)
            .filter(PolygonTickLive.tick_ts < tick_cutoff_ts)
            .delete(synchronize_session=False)
        )
        deleted_second_rows = (
            self.db.query(PolygonSecondAggregateLive)
            .filter(PolygonSecondAggregateLive.second_ts < second_cutoff_ts)
            .delete(synchronize_session=False)
        )
        self.db.flush()

        return PolygonLiveRetentionResult(
            deleted_tick_rows=deleted_tick_rows,
            deleted_second_rows=deleted_second_rows,
            tick_cutoff_ts=tick_cutoff_ts,
            second_cutoff_ts=second_cutoff_ts,
        )
