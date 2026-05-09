from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select, text
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
    deleted_historical_minute_rows: int = 0
    deleted_historical_second_rows: int = 0
    historical_tick_cutoff_ts: datetime | None = None
    historical_minute_cutoff_ts: datetime | None = None
    historical_second_cutoff_ts: datetime | None = None
    live_batches_run: int = 0
    historical_batches_run: int = 0
    live_stopped_reason: str = "not_run"
    historical_stopped_reason: str = "not_run"


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
        batch_size: int = 50_000,
        max_batches: int = 1_000,
        now: datetime | None = None,
    ) -> PolygonLiveRetentionResult:
        reference_time = now or datetime.now(timezone.utc)
        tick_cutoff_ts = reference_time - timedelta(hours=max(1, tick_retention_hours))
        minute_cutoff_ts = reference_time - timedelta(hours=max(1, minute_retention_hours))
        second_cutoff_ts = reference_time - timedelta(hours=max(1, second_retention_hours))
        deleted_tick_rows, tick_batches, tick_reason = self._delete_before_ts_in_batches(
            model=PolygonTickLive,
            ts_column=PolygonTickLive.tick_ts,
            cutoff_ts=tick_cutoff_ts,
            batch_size=batch_size,
            max_batches=max_batches,
        )
        deleted_minute_rows, minute_batches, minute_reason = self._delete_before_ts_in_batches(
            model=PolygonMinuteAggregateLive,
            ts_column=PolygonMinuteAggregateLive.minute_ts,
            cutoff_ts=minute_cutoff_ts,
            batch_size=batch_size,
            max_batches=max_batches,
        )
        deleted_second_rows, second_batches, second_reason = self._delete_before_ts_in_batches(
            model=PolygonSecondAggregateLive,
            ts_column=PolygonSecondAggregateLive.second_ts,
            cutoff_ts=second_cutoff_ts,
            batch_size=batch_size,
            max_batches=max_batches,
        )

        return PolygonLiveRetentionResult(
            deleted_tick_rows=deleted_tick_rows,
            deleted_minute_rows=deleted_minute_rows,
            deleted_second_rows=deleted_second_rows,
            tick_cutoff_ts=tick_cutoff_ts,
            minute_cutoff_ts=minute_cutoff_ts,
            second_cutoff_ts=second_cutoff_ts,
            live_batches_run=max(tick_batches, minute_batches, second_batches),
            live_stopped_reason=";".join((tick_reason, minute_reason, second_reason)),
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
        batch_size: int = 50_000,
        max_batches: int = 1_000,
        now: datetime | None = None,
    ) -> PolygonLiveRetentionResult:
        retention_result = self.purge(
            tick_retention_hours=tick_retention_hours,
            minute_retention_hours=minute_retention_hours,
            second_retention_hours=second_retention_hours,
            batch_size=batch_size,
            max_batches=max_batches,
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
            live_batches_run=retention_result.live_batches_run,
            live_stopped_reason=retention_result.live_stopped_reason,
        )

    def purge_historical(
        self,
        *,
        retention_business_days: int,
        batch_size: int = 50_000,
        max_batches: int = 1_000,
        now: datetime | None = None,
    ) -> PolygonLiveRetentionResult:
        if retention_business_days <= 0:
            raise ValueError("retention_business_days must be > 0")

        historical_cutoff_ts = self._historical_cutoff_from_market_days(
            retention_business_days=retention_business_days,
            now=now,
        )
        deleted_historical_tick_rows, tick_batches, tick_reason = self._delete_before_ts_in_batches(
            model=PolygonTick,
            ts_column=PolygonTick.tick_ts,
            cutoff_ts=historical_cutoff_ts,
            batch_size=batch_size,
            max_batches=max_batches,
        )
        deleted_historical_minute_rows, minute_batches, minute_reason = self._delete_before_ts_in_batches(
            model=PolygonMinuteAggregate,
            ts_column=PolygonMinuteAggregate.minute_ts,
            cutoff_ts=historical_cutoff_ts,
            batch_size=batch_size,
            max_batches=max_batches,
        )
        deleted_historical_second_rows, second_batches, second_reason = self._delete_before_ts_in_batches(
            model=PolygonSecondAggregate,
            ts_column=PolygonSecondAggregate.second_ts,
            cutoff_ts=historical_cutoff_ts,
            batch_size=batch_size,
            max_batches=max_batches,
        )

        return PolygonLiveRetentionResult(
            deleted_tick_rows=0,
            deleted_minute_rows=0,
            deleted_second_rows=0,
            tick_cutoff_ts=historical_cutoff_ts,
            minute_cutoff_ts=historical_cutoff_ts,
            second_cutoff_ts=historical_cutoff_ts,
            deleted_historical_tick_rows=deleted_historical_tick_rows,
            deleted_historical_minute_rows=deleted_historical_minute_rows,
            deleted_historical_second_rows=deleted_historical_second_rows,
            historical_tick_cutoff_ts=historical_cutoff_ts,
            historical_minute_cutoff_ts=historical_cutoff_ts,
            historical_second_cutoff_ts=historical_cutoff_ts,
            historical_batches_run=max(tick_batches, minute_batches, second_batches),
            historical_stopped_reason=";".join((tick_reason, minute_reason, second_reason)),
        )

    def purge_historical_ticks(
        self,
        *,
        retention_days: int,
        batch_size: int = 50_000,
        max_batches: int = 1_000,
        now: datetime | None = None,
    ) -> PolygonLiveRetentionResult:
        if retention_days <= 0:
            raise ValueError("retention_days must be > 0")
        reference_time = now or datetime.now(timezone.utc)
        historical_tick_cutoff_ts = reference_time - timedelta(days=retention_days)
        deleted_historical_tick_rows, tick_batches, tick_reason = self._delete_before_ts_in_batches(
            model=PolygonTick,
            ts_column=PolygonTick.tick_ts,
            cutoff_ts=historical_tick_cutoff_ts,
            batch_size=batch_size,
            max_batches=max_batches,
        )
        return PolygonLiveRetentionResult(
            deleted_tick_rows=0,
            deleted_minute_rows=0,
            deleted_second_rows=0,
            tick_cutoff_ts=reference_time,
            minute_cutoff_ts=reference_time,
            second_cutoff_ts=reference_time,
            deleted_historical_tick_rows=deleted_historical_tick_rows,
            historical_tick_cutoff_ts=historical_tick_cutoff_ts,
            historical_batches_run=tick_batches,
            historical_stopped_reason=tick_reason,
        )

    def _delete_sql(self, key: str, params: dict[str, object]) -> int:
        result = self.db.execute(text(self._SCOPE_DELETE_SQL[key]), params)
        return result.rowcount or 0

    def _delete_before_ts_in_batches(
        self,
        *,
        model,
        ts_column,
        cutoff_ts: datetime,
        batch_size: int,
        max_batches: int,
    ) -> tuple[int, int, str]:
        if batch_size <= 0:
            raise ValueError("batch_size must be > 0")
        if max_batches <= 0:
            raise ValueError("max_batches must be > 0")

        total_deleted = 0
        batches_run = 0
        stopped_reason = "no_more_rows"

        for batches_run in range(1, max_batches + 1):
            victims = (
                select(model.id)
                .where(ts_column < cutoff_ts)
                .order_by(ts_column.asc(), model.id.asc())
                .limit(batch_size)
                .scalar_subquery()
            )
            stmt = delete(model).where(model.id.in_(victims)).execution_options(synchronize_session=False)
            result = self.db.execute(stmt)
            self.db.commit()
            deleted_in_batch = result.rowcount or 0
            total_deleted += deleted_in_batch
            if deleted_in_batch < batch_size:
                break
        else:
            stopped_reason = "max_batches_reached"

        return total_deleted, batches_run, stopped_reason

    def _historical_cutoff_from_market_days(
        self,
        *,
        retention_business_days: int,
        now: datetime | None = None,
    ) -> datetime:
        reference_time = now or datetime.now(timezone.utc)
        ny_now = reference_time.astimezone(NEW_YORK_TZ)
        candidate = ny_now.date()
        retained_market_days: list[date] = []

        while len(retained_market_days) < retention_business_days:
            if self._is_us_market_business_day(candidate):
                retained_market_days.append(candidate)
            candidate -= timedelta(days=1)

        earliest_retained_date = retained_market_days[-1]
        return datetime.combine(earliest_retained_date, time.min, tzinfo=NEW_YORK_TZ).astimezone(timezone.utc)

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

    @classmethod
    def _is_us_market_business_day(cls, candidate: date) -> bool:
        return candidate.weekday() < 5 and candidate not in cls._us_market_holidays(candidate.year)

    @classmethod
    def _us_market_holidays(cls, year: int) -> set[date]:
        holidays = {
            cls._observed_date(date(year, 1, 1)),
            cls._nth_weekday_of_month(year, 1, 0, 3),   # MLK Day
            cls._nth_weekday_of_month(year, 2, 0, 3),   # Presidents Day
            cls._good_friday(year),
            cls._last_weekday_of_month(year, 5, 0),     # Memorial Day
            cls._observed_date(date(year, 6, 19)) if year >= 2022 else None,
            cls._observed_date(date(year, 7, 4)),
            cls._nth_weekday_of_month(year, 9, 0, 1),   # Labor Day
            cls._nth_weekday_of_month(year, 11, 3, 4),  # Thanksgiving
            cls._observed_date(date(year, 12, 25)),
        }
        return {holiday for holiday in holidays if holiday is not None}

    @staticmethod
    def _observed_date(candidate: date) -> date:
        if candidate.weekday() == 5:
            return candidate - timedelta(days=1)
        if candidate.weekday() == 6:
            return candidate + timedelta(days=1)
        return candidate

    @staticmethod
    def _nth_weekday_of_month(year: int, month: int, weekday: int, n: int) -> date:
        candidate = date(year, month, 1)
        while candidate.weekday() != weekday:
            candidate += timedelta(days=1)
        candidate += timedelta(days=7 * (n - 1))
        return candidate

    @staticmethod
    def _last_weekday_of_month(year: int, month: int, weekday: int) -> date:
        if month == 12:
            candidate = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            candidate = date(year, month + 1, 1) - timedelta(days=1)
        while candidate.weekday() != weekday:
            candidate -= timedelta(days=1)
        return candidate

    @classmethod
    def _good_friday(cls, year: int) -> date:
        return cls._easter_sunday(year) - timedelta(days=2)

    @staticmethod
    def _easter_sunday(year: int) -> date:
        a = year % 19
        b = year // 100
        c = year % 100
        d = b // 4
        e = b % 4
        f = (b + 8) // 25
        g = (b - f + 1) // 3
        h = (19 * a + b - d - g + 15) % 30
        i = c // 4
        k = c % 4
        l = (32 + 2 * e + 2 * i - h - k) % 7
        m = (a + 11 * h + 22 * l) // 451
        month = (h + l - 7 * m + 114) // 31
        day = ((h + l - 7 * m + 114) % 31) + 1
        return date(year, month, day)
