from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.polygon_minute_aggregate import PolygonMinuteAggregate
from app.models.polygon_second_aggregate import PolygonSecondAggregate
from app.models.symbol_state_live import SymbolStateLive

if TYPE_CHECKING:
    from app.data.polygon_aggregate_service import PolygonMinuteAggregateRecord, PolygonSecondAggregateRecord


class SymbolStateLiveService:
    """Maintain one live aggregate-state row per symbol."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def update_from_second_aggregate(
        self,
        record: "PolygonSecondAggregateRecord | PolygonSecondAggregate",
        *,
        as_of: datetime | None = None,
    ) -> SymbolStateLive:
        ticker = record.ticker.upper()
        second_ts = self._normalize_second_ts(record.second_ts)
        state = self._get_or_create(ticker)
        state.last_second_ts = second_ts

        window_start = second_ts - timedelta(seconds=max(1, settings.polygon_symbol_state_rolling_window_seconds) - 1)
        second_rows = (
            self.db.query(PolygonSecondAggregate)
            .filter(
                PolygonSecondAggregate.ticker == ticker,
                PolygonSecondAggregate.second_ts >= window_start,
                PolygonSecondAggregate.second_ts <= second_ts,
            )
            .order_by(PolygonSecondAggregate.second_ts.asc())
            .all()
        )
        if second_rows:
            state.rolling_second_high = max(row.high for row in second_rows)
            state.rolling_second_low = min(row.low for row in second_rows)
            state.rolling_second_volume = sum(max(0, row.volume) for row in second_rows)
            state.rolling_green_count = sum(1 for row in second_rows if row.close > row.open)

        self._recompute_staleness(state, as_of=as_of or second_ts)
        self.db.flush()
        return state

    def update_from_minute_aggregate(
        self,
        record: "PolygonMinuteAggregateRecord | PolygonMinuteAggregate",
        *,
        as_of: datetime | None = None,
    ) -> SymbolStateLive:
        ticker = record.ticker.upper()
        minute_ts = self._normalize_minute_ts(record.minute_ts)
        state = self._get_or_create(ticker)
        state.last_minute_ts = minute_ts

        rows = (
            self.db.query(PolygonMinuteAggregate)
            .filter(
                PolygonMinuteAggregate.ticker == ticker,
                PolygonMinuteAggregate.minute_ts <= minute_ts,
            )
            .order_by(PolygonMinuteAggregate.minute_ts.desc())
            .limit(2)
            .all()
        )
        if rows:
            state.current_minute_high = rows[0].high
            state.previous_minute_high = rows[1].high if len(rows) > 1 else None

        self._recompute_staleness(state, as_of=as_of or minute_ts)
        self.db.flush()
        return state

    def refresh_staleness(self, *, as_of: datetime | None = None, ticker: str | None = None) -> int:
        target_as_of = self._normalize_reference_ts(as_of or datetime.now(timezone.utc))
        query = self.db.query(SymbolStateLive)
        if ticker:
            query = query.filter(SymbolStateLive.ticker == ticker.upper())
        states = query.all()
        for state in states:
            self._recompute_staleness(state, as_of=target_as_of)
        self.db.flush()
        return len(states)

    def _get_or_create(self, ticker: str) -> SymbolStateLive:
        state = self.db.query(SymbolStateLive).filter_by(ticker=ticker).first()
        if state is None:
            state = SymbolStateLive(ticker=ticker, candidate_status="idle")
            self.db.add(state)
            self.db.flush()
        return state

    def _recompute_staleness(self, state: SymbolStateLive, *, as_of: datetime) -> None:
        reference_ts = self._normalize_reference_ts(as_of)

        if state.last_second_ts is None:
            state.seconds_since_last_trade_bar = None
            state.is_second_stream_stale = True
        else:
            second_delta = max(0, int((reference_ts - self._normalize_reference_ts(state.last_second_ts)).total_seconds()))
            state.seconds_since_last_trade_bar = second_delta
            state.is_second_stream_stale = second_delta > settings.polygon_second_stream_stale_after_seconds

        if state.last_minute_ts is None:
            state.minutes_since_last_trade_bar = None
            state.is_minute_stream_stale = True
        else:
            minute_delta = max(
                0,
                int((reference_ts - self._normalize_reference_ts(state.last_minute_ts)).total_seconds() // 60),
            )
            state.minutes_since_last_trade_bar = minute_delta
            state.is_minute_stream_stale = minute_delta > settings.polygon_minute_stream_stale_after_minutes

        state.updated_at = reference_ts

    @staticmethod
    def _normalize_minute_ts(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(second=0, microsecond=0)
        return value.astimezone(timezone.utc).replace(second=0, microsecond=0, tzinfo=None)

    @staticmethod
    def _normalize_second_ts(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(microsecond=0)
        return value.astimezone(timezone.utc).replace(microsecond=0, tzinfo=None)

    @staticmethod
    def _normalize_reference_ts(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(microsecond=0)
        return value.astimezone(timezone.utc).replace(microsecond=0, tzinfo=None)
