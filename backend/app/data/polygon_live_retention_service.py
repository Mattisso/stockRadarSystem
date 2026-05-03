from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.polygon_minute_aggregate import PolygonMinuteAggregate
from app.models.polygon_minute_aggregate_live import PolygonMinuteAggregateLive
from app.models.polygon_second_aggregate import PolygonSecondAggregate
from app.models.polygon_second_aggregate_live import PolygonSecondAggregateLive
from app.models.polygon_tick import PolygonTick
from app.models.polygon_tick_live import PolygonTickLive

NEW_YORK_TZ = ZoneInfo("America/New_York")


@dataclass(slots=True)
class PolygonLiveRetentionResult:
    deleted_tick_rows: int
    deleted_minute_rows: int
    deleted_second_rows: int
    tick_cutoff_ts: datetime
    minute_cutoff_ts: datetime
    second_cutoff_ts: datetime
    deleted_scope_tick_rows: int = 0
    deleted_scope_tick_live_rows: int = 0
    deleted_scope_minute_rows: int = 0
    deleted_scope_minute_live_rows: int = 0
    deleted_scope_second_rows: int = 0
    deleted_scope_second_live_rows: int = 0
    deleted_historical_tick_rows: int = 0
    historical_tick_cutoff_ts: datetime | None = None


class PolygonLiveRetentionService:
    """Trim hot operational Polygon tables so they do not become history tables."""

    _SCOPE_DELETE_SQL = {
        "polygon_ticks": """
            delete from stock_radar.polygon_ticks
            where greatest(coalesce(bid, 0), coalesce(ask, 0), coalesce(last, 0)) > :max_price
               or timezone('America/New_York', tick_ts at time zone 'UTC')::time < cast(:session_start_et as time)
               or timezone('America/New_York', tick_ts at time zone 'UTC')::time > cast(:session_end_et as time)
        """,
        "polygon_ticks_live": """
            delete from stock_radar.polygon_ticks_live
            where greatest(coalesce(bid, 0), coalesce(ask, 0), coalesce(last, 0)) > :max_price
               or timezone('America/New_York', tick_ts at time zone 'UTC')::time < cast(:session_start_et as time)
               or timezone('America/New_York', tick_ts at time zone 'UTC')::time > cast(:session_end_et as time)
        """,
        "polygon_minute_aggregates": """
            delete from stock_radar.polygon_minute_aggregates
            where greatest(coalesce(open, 0), coalesce(high, 0), coalesce(low, 0), coalesce(close, 0)) > :max_price
               or timezone('America/New_York', minute_ts at time zone 'UTC')::time < cast(:session_start_et as time)
               or timezone('America/New_York', minute_ts at time zone 'UTC')::time > cast(:session_end_et as time)
        """,
        "minute_aggregates_live": """
            delete from stock_radar.minute_aggregates_live
            where greatest(coalesce(open, 0), coalesce(high, 0), coalesce(low, 0), coalesce(close, 0)) > :max_price
               or timezone('America/New_York', minute_ts at time zone 'UTC')::time < cast(:session_start_et as time)
               or timezone('America/New_York', minute_ts at time zone 'UTC')::time > cast(:session_end_et as time)
        """,
        "second_aggregates": """
            delete from stock_radar.second_aggregates
            where greatest(coalesce(open, 0), coalesce(high, 0), coalesce(low, 0), coalesce(close, 0)) > :max_price
               or timezone('America/New_York', second_ts at time zone 'UTC')::time < cast(:session_start_et as time)
               or timezone('America/New_York', second_ts at time zone 'UTC')::time > cast(:session_end_et as time)
        """,
        "second_aggregates_live": """
            delete from stock_radar.second_aggregates_live
            where greatest(coalesce(open, 0), coalesce(high, 0), coalesce(low, 0), coalesce(close, 0)) > :max_price
               or timezone('America/New_York', second_ts at time zone 'UTC')::time < cast(:session_start_et as time)
               or timezone('America/New_York', second_ts at time zone 'UTC')::time > cast(:session_end_et as time)
        """,
    }

    def __init__(self, db: Session) -> None:
        self.db = db

    def purge(
        self,
        *,
        tick_retention_hours: int,
        minute_retention_hours: int,
        second_retention_hours: int,
        now: datetime | None = None,
    ) -> PolygonLiveRetentionResult:
        reference_time = now or datetime.now(timezone.utc)
        tick_cutoff_ts = reference_time - timedelta(hours=max(1, tick_retention_hours))
        minute_cutoff_ts = reference_time - timedelta(hours=max(1, minute_retention_hours))
        second_cutoff_ts = reference_time - timedelta(hours=max(1, second_retention_hours))

        deleted_tick_rows = (
            self.db.query(PolygonTickLive)
            .filter(PolygonTickLive.tick_ts < tick_cutoff_ts)
            .delete(synchronize_session=False)
        )
        deleted_minute_rows = (
            self.db.query(PolygonMinuteAggregateLive)
            .filter(PolygonMinuteAggregateLive.minute_ts < minute_cutoff_ts)
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
            deleted_minute_rows=deleted_minute_rows,
            deleted_second_rows=deleted_second_rows,
            tick_cutoff_ts=tick_cutoff_ts,
            minute_cutoff_ts=minute_cutoff_ts,
            second_cutoff_ts=second_cutoff_ts,
        )

    def purge_out_of_scope(
        self,
        *,
        max_price: float,
        session_start_et: str,
        session_end_et: str,
    ) -> PolygonLiveRetentionResult:
        if self.db.bind is not None and self.db.bind.dialect.name == "postgresql":
            params = {
                "max_price": max_price,
                "session_start_et": session_start_et,
                "session_end_et": session_end_et,
            }
            deleted_scope_tick_rows = self._delete_sql("polygon_ticks", params)
            deleted_scope_tick_live_rows = self._delete_sql("polygon_ticks_live", params)
            deleted_scope_minute_rows = self._delete_sql("polygon_minute_aggregates", params)
            deleted_scope_minute_live_rows = self._delete_sql("minute_aggregates_live", params)
            deleted_scope_second_rows = self._delete_sql("second_aggregates", params)
            deleted_scope_second_live_rows = self._delete_sql("second_aggregates_live", params)
        else:
            deleted_scope_tick_rows = self._delete_scope_rows_orm(
                model=PolygonTick,
                ts_field="tick_ts",
                price_fields=("bid", "ask", "last"),
                max_price=max_price,
                session_start_et=session_start_et,
                session_end_et=session_end_et,
            )
            deleted_scope_tick_live_rows = self._delete_scope_rows_orm(
                model=PolygonTickLive,
                ts_field="tick_ts",
                price_fields=("bid", "ask", "last"),
                max_price=max_price,
                session_start_et=session_start_et,
                session_end_et=session_end_et,
            )
            deleted_scope_minute_rows = self._delete_scope_rows_orm(
                model=PolygonMinuteAggregate,
                ts_field="minute_ts",
                price_fields=("open", "high", "low", "close"),
                max_price=max_price,
                session_start_et=session_start_et,
                session_end_et=session_end_et,
            )
            deleted_scope_minute_live_rows = self._delete_scope_rows_orm(
                model=PolygonMinuteAggregateLive,
                ts_field="minute_ts",
                price_fields=("open", "high", "low", "close"),
                max_price=max_price,
                session_start_et=session_start_et,
                session_end_et=session_end_et,
            )
            deleted_scope_second_rows = self._delete_scope_rows_orm(
                model=PolygonSecondAggregate,
                ts_field="second_ts",
                price_fields=("open", "high", "low", "close"),
                max_price=max_price,
                session_start_et=session_start_et,
                session_end_et=session_end_et,
            )
            deleted_scope_second_live_rows = self._delete_scope_rows_orm(
                model=PolygonSecondAggregateLive,
                ts_field="second_ts",
                price_fields=("open", "high", "low", "close"),
                max_price=max_price,
                session_start_et=session_start_et,
                session_end_et=session_end_et,
            )
        self.db.flush()

        return PolygonLiveRetentionResult(
            deleted_tick_rows=0,
            deleted_minute_rows=0,
            deleted_second_rows=0,
            tick_cutoff_ts=datetime.now(timezone.utc),
            minute_cutoff_ts=datetime.now(timezone.utc),
            second_cutoff_ts=datetime.now(timezone.utc),
            deleted_scope_tick_rows=deleted_scope_tick_rows,
            deleted_scope_tick_live_rows=deleted_scope_tick_live_rows,
            deleted_scope_minute_rows=deleted_scope_minute_rows,
            deleted_scope_minute_live_rows=deleted_scope_minute_live_rows,
            deleted_scope_second_rows=deleted_scope_second_rows,
            deleted_scope_second_live_rows=deleted_scope_second_live_rows,
        )

    def purge_live_and_out_of_scope(
        self,
        *,
        tick_retention_hours: int,
        minute_retention_hours: int,
        second_retention_hours: int,
        max_price: float,
        session_start_et: str,
        session_end_et: str,
        now: datetime | None = None,
    ) -> PolygonLiveRetentionResult:
        retention_result = self.purge(
            tick_retention_hours=tick_retention_hours,
            minute_retention_hours=minute_retention_hours,
            second_retention_hours=second_retention_hours,
            now=now,
        )
        scope_result = self.purge_out_of_scope(
            max_price=max_price,
            session_start_et=session_start_et,
            session_end_et=session_end_et,
        )
        return PolygonLiveRetentionResult(
            deleted_tick_rows=retention_result.deleted_tick_rows,
            deleted_minute_rows=retention_result.deleted_minute_rows,
            deleted_second_rows=retention_result.deleted_second_rows,
            tick_cutoff_ts=retention_result.tick_cutoff_ts,
            minute_cutoff_ts=retention_result.minute_cutoff_ts,
            second_cutoff_ts=retention_result.second_cutoff_ts,
            deleted_scope_tick_rows=scope_result.deleted_scope_tick_rows,
            deleted_scope_tick_live_rows=scope_result.deleted_scope_tick_live_rows,
            deleted_scope_minute_rows=scope_result.deleted_scope_minute_rows,
            deleted_scope_minute_live_rows=scope_result.deleted_scope_minute_live_rows,
            deleted_scope_second_rows=scope_result.deleted_scope_second_rows,
            deleted_scope_second_live_rows=scope_result.deleted_scope_second_live_rows,
        )

    def purge_historical_ticks(
        self,
        *,
        retention_days: int,
        now: datetime | None = None,
    ) -> PolygonLiveRetentionResult:
        reference_time = now or datetime.now(timezone.utc)
        historical_tick_cutoff_ts = reference_time - timedelta(days=max(1, retention_days))
        deleted_historical_tick_rows = (
            self.db.query(PolygonTick)
            .filter(PolygonTick.tick_ts < historical_tick_cutoff_ts)
            .delete(synchronize_session=False)
        )
        self.db.flush()

        return PolygonLiveRetentionResult(
            deleted_tick_rows=0,
            deleted_minute_rows=0,
            deleted_second_rows=0,
            tick_cutoff_ts=reference_time,
            minute_cutoff_ts=reference_time,
            second_cutoff_ts=reference_time,
            deleted_historical_tick_rows=deleted_historical_tick_rows,
            historical_tick_cutoff_ts=historical_tick_cutoff_ts,
        )

    def _delete_sql(self, key: str, params: dict[str, object]) -> int:
        result = self.db.execute(text(self._SCOPE_DELETE_SQL[key]), params)
        return result.rowcount or 0

    def _delete_scope_rows_orm(
        self,
        *,
        model,
        ts_field: str,
        price_fields: tuple[str, ...],
        max_price: float,
        session_start_et: str,
        session_end_et: str,
    ) -> int:
        rows = self.db.query(model).all()
        deleted = 0
        for row in rows:
            if self._row_is_out_of_scope(
                row=row,
                ts_field=ts_field,
                price_fields=price_fields,
                max_price=max_price,
                session_start_et=session_start_et,
                session_end_et=session_end_et,
            ):
                self.db.delete(row)
                deleted += 1
        return deleted

    @staticmethod
    def _row_is_out_of_scope(
        *,
        row,
        ts_field: str,
        price_fields: tuple[str, ...],
        max_price: float,
        session_start_et: str,
        session_end_et: str,
    ) -> bool:
        max_seen_price = max(float(getattr(row, field) or 0.0) for field in price_fields)
        if max_seen_price > max_price:
            return True

        ts = getattr(row, ts_field)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        else:
            ts = ts.astimezone(timezone.utc)
        et_time = ts.astimezone(NEW_YORK_TZ).time().strftime("%H:%M:%S")
        return et_time < session_start_et or et_time > session_end_et
