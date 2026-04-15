from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.engine.aggregate_validation_engine import AggregateValidationEngine
from app.core.config import settings
from app.models.candidate_event import CandidateEvent
from app.models.polygon_second_aggregate import PolygonSecondAggregate
from app.models.symbol_state_live import SymbolStateLive

if TYPE_CHECKING:
    from app.data.polygon_aggregate_service import PolygonSecondAggregateRecord

NEW_YORK_TZ = ZoneInfo("America/New_York")


@dataclass(slots=True)
class AggregateCandidateTrigger:
    ticker: str
    event_ts: datetime
    trigger_name: str
    score: float
    payload: dict


class AggregateTriggerEngine:
    """Evaluate aggregate-only candidate triggers from stored second bars."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def evaluate_second_bar(
        self,
        record: "PolygonSecondAggregateRecord | PolygonSecondAggregate",
        state: SymbolStateLive,
    ) -> list[AggregateCandidateTrigger]:
        second_ts = self._normalize_ts(record.second_ts)
        if state.is_second_stream_stale:
            return []

        prior_rows = (
            self.db.query(PolygonSecondAggregate)
            .filter(
                PolygonSecondAggregate.ticker == record.ticker.upper(),
                PolygonSecondAggregate.second_ts < second_ts,
                PolygonSecondAggregate.second_ts >= second_ts - timedelta(seconds=settings.polygon_symbol_state_rolling_window_seconds),
            )
            .order_by(PolygonSecondAggregate.second_ts.desc())
            .all()
        )

        triggers: list[AggregateCandidateTrigger] = []
        breakout = self._trigger_breakout_above_recent_high(record, second_ts, prior_rows)
        if breakout is not None:
            triggers.append(breakout)

        volume_spike = self._trigger_second_volume_spike(record, second_ts, prior_rows)
        if volume_spike is not None:
            triggers.append(volume_spike)

        velocity = self._trigger_velocity_spike(record, second_ts, prior_rows)
        if velocity is not None:
            triggers.append(velocity)

        range_expansion = self._trigger_range_expansion(record, second_ts, prior_rows)
        if range_expansion is not None:
            triggers.append(range_expansion)

        consecutive = self._trigger_consecutive_green_seconds(record, second_ts)
        if consecutive is not None:
            triggers.append(consecutive)

        current_minute = self._trigger_break_current_minute_high(record, second_ts, state)
        if current_minute is not None:
            triggers.append(current_minute)

        previous_minute = self._trigger_break_previous_minute_high(record, second_ts, state)
        if previous_minute is not None:
            triggers.append(previous_minute)

        recovery = self._trigger_recovery_spike(record, second_ts, prior_rows)
        if recovery is not None:
            triggers.append(recovery)

        first_move = self._trigger_first_move_after_quiet(record, second_ts, prior_rows)
        if first_move is not None:
            triggers.append(first_move)

        new_high_day = self._trigger_new_high_of_day_early(record, second_ts)
        if new_high_day is not None:
            triggers.append(new_high_day)

        return triggers

    def persist(self, triggers: list[AggregateCandidateTrigger], state: SymbolStateLive) -> int:
        if not triggers:
            state.candidate_status = "idle"
            state.candidate_score = None
            self.db.flush()
            return 0

        for trigger in triggers:
            self.db.add(
                CandidateEvent(
                    ticker=trigger.ticker,
                    event_ts=trigger.event_ts,
                    trigger_name=trigger.trigger_name,
                    trigger_payload=json.dumps(trigger.payload, sort_keys=True),
                    last_second_ts=state.last_second_ts,
                    last_minute_ts=state.last_minute_ts,
                    seconds_since_last_trade_bar=state.seconds_since_last_trade_bar,
                    minutes_since_last_trade_bar=state.minutes_since_last_trade_bar,
                    is_second_stream_stale=state.is_second_stream_stale,
                    is_minute_stream_stale=state.is_minute_stream_stale,
                )
            )
        state.candidate_status = "candidate"
        state.candidate_score = max(trigger.score for trigger in triggers)
        self.db.flush()
        return len(triggers)

    def persist_with_validation(
        self,
        triggers: list[AggregateCandidateTrigger],
        state: SymbolStateLive,
        *,
        event_ts: datetime,
    ) -> int:
        validation = AggregateValidationEngine(self.db).evaluate(state.ticker, state, event_ts)
        AggregateValidationEngine(self.db).persist(state, validation)
        if not triggers:
            state.candidate_status = "idle"
            state.candidate_score = None
            self.db.flush()
            return 0

        for trigger in triggers:
            payload = {
                **trigger.payload,
                "validation_score": validation.score,
                "validation_pass_count": validation.pass_count,
                "validation_checks": validation.checks,
            }
            self.db.add(
                CandidateEvent(
                    ticker=trigger.ticker,
                    event_ts=trigger.event_ts,
                    trigger_name=trigger.trigger_name,
                    trigger_payload=json.dumps(payload, sort_keys=True),
                    last_second_ts=state.last_second_ts,
                    last_minute_ts=state.last_minute_ts,
                    seconds_since_last_trade_bar=state.seconds_since_last_trade_bar,
                    minutes_since_last_trade_bar=state.minutes_since_last_trade_bar,
                    is_second_stream_stale=state.is_second_stream_stale,
                    is_minute_stream_stale=state.is_minute_stream_stale,
                )
            )
        state.candidate_status = "candidate"
        state.candidate_score = max(trigger.score for trigger in triggers)
        self.db.flush()
        return len(triggers)

    def _trigger_breakout_above_recent_high(
        self,
        record: "PolygonSecondAggregateRecord | PolygonSecondAggregate",
        second_ts: datetime,
        prior_rows: list[PolygonSecondAggregate],
    ) -> AggregateCandidateTrigger | None:
        if not prior_rows:
            return None
        recent_high = max(row.high for row in prior_rows)
        threshold = recent_high * (1.0 + settings.aggregate_trigger_breakout_buffer_pct)
        if record.close <= threshold:
            return None
        move_pct = (record.close / recent_high) - 1.0 if recent_high > 0 else 0.0
        score = min(1.0, 0.6 + move_pct * 20.0)
        return AggregateCandidateTrigger(
            ticker=record.ticker.upper(),
            event_ts=second_ts,
            trigger_name="breakout_above_recent_high",
            score=round(score, 4),
            payload={
                "close": record.close,
                "recent_high": round(recent_high, 6),
                "buffer_pct": settings.aggregate_trigger_breakout_buffer_pct,
            },
        )

    def _trigger_second_volume_spike(
        self,
        record: "PolygonSecondAggregateRecord | PolygonSecondAggregate",
        second_ts: datetime,
        prior_rows: list[PolygonSecondAggregate],
    ) -> AggregateCandidateTrigger | None:
        if not prior_rows:
            return None
        avg_volume = sum(max(0, row.volume) for row in prior_rows) / len(prior_rows)
        if avg_volume <= 0:
            return None
        required_volume = max(
            settings.aggregate_trigger_second_volume_spike_min_volume,
            avg_volume * settings.aggregate_trigger_second_volume_spike_multiplier,
        )
        if record.volume < required_volume:
            return None
        score = min(1.0, 0.5 + (record.volume / required_volume - 1.0) * 0.5)
        return AggregateCandidateTrigger(
            ticker=record.ticker.upper(),
            event_ts=second_ts,
            trigger_name="second_volume_spike",
            score=round(score, 4),
            payload={
                "second_volume": record.volume,
                "average_prior_second_volume": round(avg_volume, 2),
                "required_volume": round(required_volume, 2),
            },
        )

    def _trigger_consecutive_green_seconds(
        self,
        record: "PolygonSecondAggregateRecord | PolygonSecondAggregate",
        second_ts: datetime,
    ) -> AggregateCandidateTrigger | None:
        rows = (
            self.db.query(PolygonSecondAggregate)
            .filter(
                PolygonSecondAggregate.ticker == record.ticker.upper(),
                PolygonSecondAggregate.second_ts <= second_ts,
            )
            .order_by(PolygonSecondAggregate.second_ts.desc())
            .limit(settings.aggregate_trigger_consecutive_green_seconds)
            .all()
        )
        if not rows:
            return None
        streak = 0
        for row in rows:
            if row.close > row.open:
                streak += 1
            else:
                break
        if streak < settings.aggregate_trigger_consecutive_green_seconds:
            return None
        score = min(1.0, 0.55 + 0.1 * streak)
        return AggregateCandidateTrigger(
            ticker=record.ticker.upper(),
            event_ts=second_ts,
            trigger_name="consecutive_green_seconds",
            score=round(score, 4),
            payload={
                "streak": streak,
                "required_streak": settings.aggregate_trigger_consecutive_green_seconds,
            },
        )

    def _trigger_velocity_spike(
        self,
        record: "PolygonSecondAggregateRecord | PolygonSecondAggregate",
        second_ts: datetime,
        prior_rows: list[PolygonSecondAggregate],
    ) -> AggregateCandidateTrigger | None:
        bars = settings.aggregate_trigger_velocity_bars
        if len(prior_rows) < bars:
            return None
        anchor_row = list(reversed(prior_rows[:bars]))[0]
        anchor_close = anchor_row.close
        if anchor_close <= 0:
            return None
        velocity_pct = record.close / anchor_close - 1.0
        if velocity_pct < settings.aggregate_trigger_velocity_spike_pct:
            return None
        score = min(1.0, 0.55 + (velocity_pct / settings.aggregate_trigger_velocity_spike_pct - 1.0) * 0.2)
        return AggregateCandidateTrigger(
            ticker=record.ticker.upper(),
            event_ts=second_ts,
            trigger_name="velocity_spike",
            score=round(score, 4),
            payload={
                "anchor_close": round(anchor_close, 6),
                "bars_ago": bars,
                "velocity_pct": round(velocity_pct, 6),
                "required_pct": settings.aggregate_trigger_velocity_spike_pct,
            },
        )

    def _trigger_range_expansion(
        self,
        record: "PolygonSecondAggregateRecord | PolygonSecondAggregate",
        second_ts: datetime,
        prior_rows: list[PolygonSecondAggregate],
    ) -> AggregateCandidateTrigger | None:
        window = settings.aggregate_trigger_range_expansion_window
        if len(prior_rows) < window:
            return None
        sample_rows = prior_rows[:window]
        prior_ranges = [max(0.0, row.high - row.low) for row in sample_rows]
        avg_range = sum(prior_ranges) / len(prior_ranges) if prior_ranges else 0.0
        current_range = max(0.0, record.high - record.low)
        if avg_range <= 0 or current_range < avg_range * settings.aggregate_trigger_range_expansion_multiplier:
            return None
        if current_range <= 0:
            return None
        close_in_range = (record.close - record.low) / current_range
        if close_in_range < settings.aggregate_trigger_range_expansion_close_in_range_pct:
            return None
        score = min(1.0, 0.55 + (current_range / (avg_range * settings.aggregate_trigger_range_expansion_multiplier) - 1.0) * 0.25)
        return AggregateCandidateTrigger(
            ticker=record.ticker.upper(),
            event_ts=second_ts,
            trigger_name="range_expansion",
            score=round(score, 4),
            payload={
                "current_range": round(current_range, 6),
                "average_prior_range": round(avg_range, 6),
                "close_in_range": round(close_in_range, 6),
            },
        )

    def _trigger_break_current_minute_high(
        self,
        record: "PolygonSecondAggregateRecord | PolygonSecondAggregate",
        second_ts: datetime,
        state: SymbolStateLive,
    ) -> AggregateCandidateTrigger | None:
        if state.current_minute_high is None or state.current_minute_high <= 0:
            return None
        threshold = state.current_minute_high * (1.0 + settings.aggregate_trigger_minute_high_buffer_pct)
        if record.close <= threshold:
            return None
        move_pct = record.close / state.current_minute_high - 1.0
        return AggregateCandidateTrigger(
            ticker=record.ticker.upper(),
            event_ts=second_ts,
            trigger_name="break_current_minute_high",
            score=round(min(1.0, 0.55 + move_pct * 30.0), 4),
            payload={
                "current_minute_high": round(state.current_minute_high, 6),
                "buffer_pct": settings.aggregate_trigger_minute_high_buffer_pct,
            },
        )

    def _trigger_break_previous_minute_high(
        self,
        record: "PolygonSecondAggregateRecord | PolygonSecondAggregate",
        second_ts: datetime,
        state: SymbolStateLive,
    ) -> AggregateCandidateTrigger | None:
        if state.previous_minute_high is None or state.previous_minute_high <= 0:
            return None
        threshold = state.previous_minute_high * (1.0 + settings.aggregate_trigger_minute_high_buffer_pct)
        if record.close <= threshold:
            return None
        move_pct = record.close / state.previous_minute_high - 1.0
        return AggregateCandidateTrigger(
            ticker=record.ticker.upper(),
            event_ts=second_ts,
            trigger_name="break_previous_minute_high",
            score=round(min(1.0, 0.55 + move_pct * 30.0), 4),
            payload={
                "previous_minute_high": round(state.previous_minute_high, 6),
                "buffer_pct": settings.aggregate_trigger_minute_high_buffer_pct,
            },
        )

    def _trigger_recovery_spike(
        self,
        record: "PolygonSecondAggregateRecord | PolygonSecondAggregate",
        second_ts: datetime,
        prior_rows: list[PolygonSecondAggregate],
    ) -> AggregateCandidateTrigger | None:
        window = settings.aggregate_trigger_recovery_window_seconds
        if len(prior_rows) < window:
            return None
        sample_rows = list(reversed(prior_rows[:window]))
        local_high = max(row.high for row in sample_rows)
        local_low = min(row.low for row in sample_rows)
        if local_high <= 0 or local_low <= 0:
            return None
        pullback_pct = 1.0 - (local_low / local_high)
        if pullback_pct < settings.aggregate_trigger_recovery_pullback_pct:
            return None
        rebound_pct = record.close / local_low - 1.0
        if rebound_pct < settings.aggregate_trigger_recovery_rebound_pct:
            return None
        current_range = max(0.0, record.high - record.low)
        if current_range <= 0:
            return None
        close_in_range = (record.close - record.low) / current_range
        if close_in_range < settings.aggregate_trigger_recovery_close_in_range_pct:
            return None
        return AggregateCandidateTrigger(
            ticker=record.ticker.upper(),
            event_ts=second_ts,
            trigger_name="recovery_spike",
            score=round(min(1.0, 0.6 + rebound_pct * 10.0), 4),
            payload={
                "local_high": round(local_high, 6),
                "local_low": round(local_low, 6),
                "pullback_pct": round(pullback_pct, 6),
                "rebound_pct": round(rebound_pct, 6),
            },
        )

    def _trigger_first_move_after_quiet(
        self,
        record: "PolygonSecondAggregateRecord | PolygonSecondAggregate",
        second_ts: datetime,
        prior_rows: list[PolygonSecondAggregate],
    ) -> AggregateCandidateTrigger | None:
        window = settings.aggregate_trigger_quiet_window
        if len(prior_rows) < window:
            return None
        sample_rows = prior_rows[:window]
        reference_price = sample_rows[0].close if sample_rows[0].close > 0 else None
        if reference_price is None:
            return None
        avg_range_pct = sum(max(0.0, row.high - row.low) / reference_price for row in sample_rows) / len(sample_rows)
        avg_volume = sum(max(0, row.volume) for row in sample_rows) / len(sample_rows)
        if avg_range_pct >= settings.aggregate_trigger_quiet_max_avg_range_pct:
            return None
        if avg_volume >= settings.aggregate_trigger_quiet_max_avg_volume:
            return None
        recent_high = max(row.high for row in sample_rows)
        breakout_pct = record.close / recent_high - 1.0 if recent_high > 0 else 0.0
        if breakout_pct < settings.aggregate_trigger_quiet_breakout_pct:
            return None
        return AggregateCandidateTrigger(
            ticker=record.ticker.upper(),
            event_ts=second_ts,
            trigger_name="first_move_after_quiet",
            score=round(min(1.0, 0.6 + breakout_pct * 10.0), 4),
            payload={
                "average_range_pct": round(avg_range_pct, 6),
                "average_volume": round(avg_volume, 2),
                "recent_high": round(recent_high, 6),
                "breakout_pct": round(breakout_pct, 6),
            },
        )

    def _trigger_new_high_of_day_early(
        self,
        record: "PolygonSecondAggregateRecord | PolygonSecondAggregate",
        second_ts: datetime,
    ) -> AggregateCandidateTrigger | None:
        second_ts_utc = second_ts.replace(tzinfo=timezone.utc) if second_ts.tzinfo is None else second_ts.astimezone(timezone.utc)
        second_ts_ny = second_ts_utc.astimezone(NEW_YORK_TZ)
        minutes_from_open = (second_ts_ny.hour * 60 + second_ts_ny.minute) - (9 * 60 + 30)
        if minutes_from_open < 0 or minutes_from_open > settings.aggregate_trigger_new_high_day_early_minutes:
            return None
        session_start_ny = second_ts_ny.replace(hour=9, minute=30, second=0, microsecond=0)
        session_start_utc = session_start_ny.astimezone(timezone.utc).replace(tzinfo=None)
        prior_rows = (
            self.db.query(PolygonSecondAggregate)
            .filter(
                PolygonSecondAggregate.ticker == record.ticker.upper(),
                PolygonSecondAggregate.second_ts >= session_start_utc,
                PolygonSecondAggregate.second_ts < second_ts,
            )
            .order_by(PolygonSecondAggregate.second_ts.asc())
            .all()
        )
        if not prior_rows:
            return None
        session_high = max(row.high for row in prior_rows)
        threshold = session_high * (1.0 + settings.aggregate_trigger_new_high_day_buffer_pct)
        if record.close <= threshold:
            return None
        move_pct = record.close / session_high - 1.0 if session_high > 0 else 0.0
        return AggregateCandidateTrigger(
            ticker=record.ticker.upper(),
            event_ts=second_ts,
            trigger_name="new_high_of_day_early",
            score=round(min(1.0, 0.6 + move_pct * 30.0), 4),
            payload={
                "session_high_before_current": round(session_high, 6),
                "minutes_from_open": minutes_from_open,
                "buffer_pct": settings.aggregate_trigger_new_high_day_buffer_pct,
            },
        )

    @staticmethod
    def _normalize_ts(value: datetime) -> datetime:
        return value.replace(tzinfo=None) if value.tzinfo is None else value.astimezone(timezone.utc).replace(tzinfo=None)
