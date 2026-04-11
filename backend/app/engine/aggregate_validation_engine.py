from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.polygon_second_aggregate import PolygonSecondAggregate
from app.models.symbol_state_live import SymbolStateLive


@dataclass(slots=True)
class AggregateValidationResult:
    score: float
    pass_count: int
    checks: dict[str, bool]


class AggregateValidationEngine:
    """Evaluate rolling validation rules against stored second-bar context."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def evaluate(self, ticker: str, state: SymbolStateLive, event_ts: datetime) -> AggregateValidationResult:
        normalized_ts = self._normalize_ts(event_ts)
        window_start = normalized_ts - timedelta(seconds=max(1, settings.polygon_symbol_state_rolling_window_seconds) - 1)
        rows = (
            self.db.query(PolygonSecondAggregate)
            .filter(
                PolygonSecondAggregate.ticker == ticker.upper(),
                PolygonSecondAggregate.second_ts >= window_start,
                PolygonSecondAggregate.second_ts <= normalized_ts,
            )
            .order_by(PolygonSecondAggregate.second_ts.asc())
            .all()
        )
        if not rows:
            return AggregateValidationResult(score=0.0, pass_count=0, checks={})

        current = rows[-1]
        prior = rows[:-1]
        prior_high = max((row.high for row in prior), default=current.high)
        average_range = sum(max(0.0, row.high - row.low) for row in rows) / len(rows)
        average_volume = sum(max(0, row.volume) for row in rows) / len(rows)
        red_count = max(0, len(rows) - state.rolling_green_count)
        prior_close = prior[-1].close if prior else current.close
        close_delta = current.close - prior_close
        rolling_high = state.rolling_second_high or current.high
        rolling_low = state.rolling_second_low or current.low
        extension_anchor = state.previous_minute_high or state.current_minute_high or prior_high or current.close

        checks = {
            "momentum_still_positive": close_delta > 0,
            "volume_stays_elevated": average_volume >= settings.aggregate_validation_min_average_second_volume,
            "price_holds_near_high": current.close >= rolling_high * (1.0 - settings.aggregate_validation_near_high_buffer_pct),
            "no_immediate_sharp_drop": current.low >= prior_high * (1.0 - settings.aggregate_validation_sharp_drop_pct),
            "higher_highs_continue": current.high >= prior_high,
            "pullbacks_are_small": current.close >= rolling_high * (1.0 - settings.aggregate_validation_pullback_buffer_pct),
            "more_green_than_red_seconds": state.rolling_green_count > red_count,
            "current_minute_strong": (
                state.current_minute_high is None
                or current.close >= state.current_minute_high * (1.0 - settings.aggregate_validation_minute_strength_buffer_pct)
            ),
            "range_expands_without_collapse": (
                (current.high - current.low) >= average_range * settings.aggregate_validation_range_expansion_multiplier
                and current.close >= current.low + ((current.high - current.low) * settings.aggregate_validation_range_close_position_pct)
            ),
            "not_too_extended_already": current.close <= extension_anchor * (1.0 + settings.aggregate_validation_max_extension_pct),
        }

        pass_count = sum(1 for passed in checks.values() if passed)
        score = round(pass_count / len(checks), 4)
        return AggregateValidationResult(score=score, pass_count=pass_count, checks=checks)

    def persist(self, state: SymbolStateLive, result: AggregateValidationResult) -> None:
        state.validation_score = result.score
        state.validation_pass_count = result.pass_count
        self.db.flush()

    @staticmethod
    def _normalize_ts(value: datetime) -> datetime:
        return value.replace(tzinfo=None) if value.tzinfo is None else value.astimezone(timezone.utc).replace(tzinfo=None)
