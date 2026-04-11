from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from app.engine.aggregate_validation_engine import AggregateValidationEngine
from app.core.config import settings
from app.models.candidate_event import CandidateEvent
from app.models.polygon_second_aggregate import PolygonSecondAggregate
from app.models.symbol_state_live import SymbolStateLive

if TYPE_CHECKING:
    from app.data.polygon_aggregate_service import PolygonSecondAggregateRecord


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

        consecutive = self._trigger_consecutive_green_seconds(record, second_ts)
        if consecutive is not None:
            triggers.append(consecutive)

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

    @staticmethod
    def _normalize_ts(value: datetime) -> datetime:
        return value.replace(tzinfo=None) if value.tzinfo is None else value.astimezone(timezone.utc).replace(tzinfo=None)
