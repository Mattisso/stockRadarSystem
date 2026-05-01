from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.config import settings
from app.engine.secret_ingredients import SecretIngredientsService
from app.engine.symbol_trade_state_service import SymbolTradeStateService
from app.models.decision_event import DecisionEvent
from app.models.polygon_second_aggregate import PolygonSecondAggregate
from app.models.symbol_state_live import SymbolStateLive

NEW_YORK_TZ = ZoneInfo("America/New_York")


@dataclass(slots=True)
class AggregateDecision:
    ticker: str
    decision_ts: datetime
    decision_type: str
    reason_code: str
    payload: dict


class AggregateDecisionEngine:
    """Persist the first explicit aggregate-only decisions."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def evaluate(
        self,
        *,
        ticker: str,
        event_ts: datetime,
        trigger_count: int,
        state: SymbolStateLive,
    ) -> AggregateDecision | None:
        if not self._is_ticker_in_current_aggregate_universe(ticker):
            return None

        if trigger_count <= 0 and not self._requires_ongoing_decision(state):
            return None

        latest_second = self._latest_second_row(ticker=ticker, event_ts=event_ts)
        buy_context = self._latest_buy_context(ticker=ticker, event_ts=event_ts)

        # Preserve a completed same-day round-trip. Once a symbol has bought and sold
        # on the same trading day, do not allow trigger churn to re-open it again.
        if state.candidate_status == "sold" and self._has_buy_on_trade_day(ticker=ticker, event_ts=event_ts):
            return None

        active_sell_allowed = self._is_active_position(state) and buy_context is not None

        if active_sell_allowed and state.is_second_stream_stale:
            return AggregateDecision(
                ticker=ticker.upper(),
                decision_ts=event_ts,
                decision_type="sell",
                reason_code="active_position_second_stream_stale",
                payload=self._payload(state, trigger_count, latest_second=latest_second, buy_context=buy_context),
            )
        if active_sell_allowed and self._minute_context_is_unusable(state):
            return AggregateDecision(
                ticker=ticker.upper(),
                decision_ts=event_ts,
                decision_type="sell",
                reason_code="active_position_minute_stream_stale",
                payload=self._payload(state, trigger_count, latest_second=latest_second, buy_context=buy_context),
            )
        if active_sell_allowed and self._should_sell_stop_loss(latest_second, buy_context):
            return AggregateDecision(
                ticker=ticker.upper(),
                decision_ts=event_ts,
                decision_type="sell",
                reason_code="active_position_stop_loss",
                payload=self._payload(state, trigger_count, latest_second=latest_second, buy_context=buy_context),
            )
        if active_sell_allowed and self._should_sell_momentum_dies(
            ticker=ticker,
            event_ts=event_ts,
            latest_second=latest_second,
            buy_context=buy_context,
        ):
            return AggregateDecision(
                ticker=ticker.upper(),
                decision_ts=event_ts,
                decision_type="sell",
                reason_code="active_position_momentum_dies",
                payload=self._payload(state, trigger_count, latest_second=latest_second, buy_context=buy_context),
            )
        if active_sell_allowed and self._should_sell_quick_profit_spike(
            ticker=ticker,
            event_ts=event_ts,
            latest_second=latest_second,
            buy_context=buy_context,
        ):
            return AggregateDecision(
                ticker=ticker.upper(),
                decision_ts=event_ts,
                decision_type="sell",
                reason_code="active_position_quick_profit_spike",
                payload=self._payload(state, trigger_count, latest_second=latest_second, buy_context=buy_context),
            )
        if active_sell_allowed and self._should_sell_sharp_reversal(state=state, latest_second=latest_second):
            return AggregateDecision(
                ticker=ticker.upper(),
                decision_ts=event_ts,
                decision_type="sell",
                reason_code="active_position_sharp_reversal",
                payload=self._payload(state, trigger_count, latest_second=latest_second, buy_context=buy_context),
            )
        if active_sell_allowed and self._should_sell_no_continuation(
            ticker=ticker,
            event_ts=event_ts,
            state=state,
            buy_context=buy_context,
        ):
            return AggregateDecision(
                ticker=ticker.upper(),
                decision_ts=event_ts,
                decision_type="sell",
                reason_code="active_position_no_continuation",
                payload=self._payload(state, trigger_count, latest_second=latest_second, buy_context=buy_context),
            )
        if active_sell_allowed and self._should_sell_on_breakdown(state):
            return AggregateDecision(
                ticker=ticker.upper(),
                decision_ts=event_ts,
                decision_type="sell",
                reason_code="active_position_breakdown",
                payload=self._payload(state, trigger_count, latest_second=latest_second, buy_context=buy_context),
            )

        if state.is_second_stream_stale:
            return AggregateDecision(
                ticker=ticker.upper(),
                decision_ts=event_ts,
                decision_type="reject",
                reason_code="second_stream_stale",
                payload=self._payload(state, trigger_count, latest_second=latest_second, buy_context=buy_context),
            )
        if self._minute_context_is_unusable(state):
            return AggregateDecision(
                ticker=ticker.upper(),
                decision_ts=event_ts,
                decision_type="reject",
                reason_code="minute_stream_stale",
                payload=self._payload(state, trigger_count, latest_second=latest_second, buy_context=buy_context),
            )
        if (state.validation_score or 0.0) < settings.aggregate_decision_min_validation_score:
            return AggregateDecision(
                ticker=ticker.upper(),
                decision_ts=event_ts,
                decision_type="reject",
                reason_code="validation_below_threshold",
                payload=self._payload(state, trigger_count, latest_second=latest_second, buy_context=buy_context),
            )
        if (state.validation_pass_count or 0) < settings.aggregate_decision_min_validation_pass_count:
            return AggregateDecision(
                ticker=ticker.upper(),
                decision_ts=event_ts,
                decision_type="reject",
                reason_code="validation_pass_count_too_low",
                payload=self._payload(state, trigger_count, latest_second=latest_second, buy_context=buy_context),
            )

        if self._should_buy(state):
            if state.candidate_status in {"buy", "manage"}:
                return AggregateDecision(
                    ticker=ticker.upper(),
                    decision_ts=event_ts,
                    decision_type="manage",
                    reason_code="active_position_manage",
                    payload=self._payload(state, trigger_count, latest_second=latest_second, buy_context=buy_context),
                )
            return AggregateDecision(
                ticker=ticker.upper(),
                decision_ts=event_ts,
                decision_type="buy",
                reason_code="validated_buy_setup",
                payload=self._payload(state, trigger_count, latest_second=latest_second, buy_context=buy_context),
            )

        return AggregateDecision(
            ticker=ticker.upper(),
            decision_ts=event_ts,
            decision_type="candidate",
            reason_code="validated_candidate",
            payload=self._payload(state, trigger_count, latest_second=latest_second, buy_context=buy_context),
        )

    def persist(self, decision: AggregateDecision | None, state: SymbolStateLive, *, dedupe: bool = False) -> int:
        if decision is None:
            return 0

        decision = self._coerce_for_trade_state(decision)
        if decision is None:
            return 0

        self._apply_state_transition(state, decision.decision_type)

        if dedupe:
            latest = self._latest_persisted_decision(ticker=decision.ticker)
            if (
                latest is not None
                and self._normalize_ts(latest.decision_ts) < self._normalize_ts(decision.decision_ts)
                and latest.decision_type == decision.decision_type
                and latest.reason_code == decision.reason_code
            ):
                self.db.flush()
                return 0

        row = DecisionEvent(
            ticker=decision.ticker,
            decision_ts=decision.decision_ts,
            decision_type=decision.decision_type,
            reason_code=decision.reason_code,
            decision_payload=json.dumps(decision.payload, sort_keys=True),
            candidate_score=state.candidate_score,
            validation_pass_count=state.validation_pass_count,
            seconds_since_last_trade_bar=state.seconds_since_last_trade_bar,
            minutes_since_last_trade_bar=state.minutes_since_last_trade_bar,
            is_second_stream_stale=state.is_second_stream_stale,
            is_minute_stream_stale=state.is_minute_stream_stale,
        )
        self.db.add(row)
        self.db.flush()
        self._record_trade_state_transition(row)
        return 1

    def _coerce_for_trade_state(self, decision: AggregateDecision) -> AggregateDecision | None:
        if decision.decision_type not in {"buy", "sell"}:
            return decision

        trade_state_service = SymbolTradeStateService(self.db)
        trade_state = trade_state_service.get_or_create(ticker=decision.ticker)

        if decision.decision_type == "buy" and trade_state_service.has_open_position(trade_state):
            return AggregateDecision(
                ticker=decision.ticker,
                decision_ts=decision.decision_ts,
                decision_type="manage",
                reason_code="active_position_manage",
                payload=decision.payload,
            )
        if decision.decision_type == "sell":
            if not trade_state_service.has_open_position(trade_state):
                return None
            if (
                trade_state.entry_ts is None
                or self._normalize_ts(trade_state.entry_ts) > self._normalize_ts(decision.decision_ts)
            ):
                return None
        return decision

    def _record_trade_state_transition(self, row: DecisionEvent) -> None:
        if row.decision_type not in {"buy", "sell"}:
            return
        payload = json.loads(row.decision_payload or "{}")
        trade_state_service = SymbolTradeStateService(self.db)
        trade_state = trade_state_service.get_or_create(ticker=row.ticker)
        if row.decision_type == "buy":
            trade_state_service.mark_open(
                trade_state,
                decision_event=row,
                entry_price=payload.get("current_close") or payload.get("entry_price"),
            )
        else:
            trade_state_service.mark_closed(
                trade_state,
                decision_event=row,
                exit_price=payload.get("current_close") or payload.get("entry_price"),
            )

    @staticmethod
    def _payload(
        state: SymbolStateLive,
        trigger_count: int,
        *,
        latest_second: PolygonSecondAggregate | None,
        buy_context: dict | None,
    ) -> dict:
        payload = {
            "trigger_count": trigger_count,
            "candidate_score": state.candidate_score,
            "validation_score": state.validation_score,
            "validation_pass_count": state.validation_pass_count,
        }
        if latest_second is not None:
            payload["current_close"] = latest_second.close
            payload["current_high"] = latest_second.high
            payload["current_low"] = latest_second.low
        if buy_context is not None:
            payload["entry_price"] = buy_context.get("entry_price")
            payload["entry_ts"] = buy_context.get("entry_ts")
        return payload

    @staticmethod
    def _should_buy(state: SymbolStateLive) -> bool:
        if (state.validation_score or 0.0) < settings.aggregate_buy_min_validation_score:
            return False
        if (state.validation_pass_count or 0) < settings.aggregate_buy_min_validation_pass_count:
            return False
        if (state.candidate_score or 0.0) < settings.aggregate_buy_min_candidate_score:
            return False

        current_high = state.current_minute_high
        rolling_high = state.rolling_second_high
        rolling_low = state.rolling_second_low
        if current_high is None or rolling_high is None or rolling_low is None:
            return False
        if rolling_high <= 0:
            return False

        near_high_floor = rolling_high * (1.0 - settings.aggregate_buy_near_high_buffer_pct)
        if current_high < near_high_floor:
            return False
        if rolling_low > current_high:
            return False
        return True

    @staticmethod
    def _is_active_position(state: SymbolStateLive) -> bool:
        return state.candidate_status in {"buy", "manage"}

    @staticmethod
    def _minute_context_is_unusable(state: SymbolStateLive) -> bool:
        if not state.is_minute_stream_stale:
            return False
        if state.last_minute_ts is None:
            return True
        minute_gap = state.minutes_since_last_trade_bar
        if minute_gap is None:
            return True
        return minute_gap > settings.aggregate_decision_max_minute_gap_minutes

    @staticmethod
    def _requires_ongoing_decision(state: SymbolStateLive) -> bool:
        return state.candidate_status in {"candidate", "validated", "buy", "manage"}

    @staticmethod
    def _apply_state_transition(state: SymbolStateLive, decision_type: str) -> None:
        if decision_type == "candidate":
            state.candidate_status = "validated"
        elif decision_type == "buy":
            state.candidate_status = "buy"
        elif decision_type == "manage":
            state.candidate_status = "manage"
        elif decision_type == "sell":
            state.candidate_status = "sold"
        else:
            state.candidate_status = "rejected"

    @staticmethod
    def _should_sell_on_breakdown(state: SymbolStateLive) -> bool:
        current_high = state.current_minute_high
        rolling_low = state.rolling_second_low
        if current_high is None or rolling_low is None or current_high <= 0:
            return False
        return rolling_low <= current_high * (1.0 - settings.aggregate_validation_sharp_drop_pct)

    def _should_sell_stop_loss(self, latest_second: PolygonSecondAggregate | None, buy_context: dict | None) -> bool:
        if latest_second is None or buy_context is None:
            return False
        entry_price = buy_context.get("entry_price")
        if entry_price is None or entry_price <= 0:
            return False
        return latest_second.close <= entry_price * (1.0 - settings.aggregate_sell_stop_loss_pct)

    def _should_sell_momentum_dies(
        self,
        *,
        ticker: str,
        event_ts: datetime,
        latest_second: PolygonSecondAggregate | None,
        buy_context: dict | None = None,
    ) -> bool:
        if latest_second is None or buy_context is None:
            return False
        entry_price = buy_context.get("entry_price")
        if entry_price is None or entry_price <= 0:
            return False
        # Momentum-dies is a profit-protection rule, not a loss-cutting rule.
        # If the trade is below entry, let stop-loss / reversal logic own the exit.
        if latest_second.close < entry_price:
            return False
        lookback = settings.aggregate_sell_momentum_lookback_bars
        prior_rows = (
            self.db.query(PolygonSecondAggregate)
            .filter(
                PolygonSecondAggregate.ticker == ticker.upper(),
                PolygonSecondAggregate.second_ts < event_ts,
            )
            .order_by(PolygonSecondAggregate.second_ts.desc())
            .limit(lookback)
            .all()
        )
        if len(prior_rows) < lookback:
            return False
        anchor = list(reversed(prior_rows))[0]
        return latest_second.close < anchor.close

    @staticmethod
    def _should_sell_sharp_reversal(
        *,
        state: SymbolStateLive,
        latest_second: PolygonSecondAggregate | None,
    ) -> bool:
        if latest_second is None or state.rolling_second_high is None or state.rolling_second_high <= 0:
            return False
        return latest_second.low <= state.rolling_second_high * (1.0 - settings.aggregate_sell_sharp_reversal_pct)

    def _should_sell_no_continuation(
        self,
        *,
        ticker: str,
        event_ts: datetime,
        state: SymbolStateLive,
        buy_context: dict | None,
    ) -> bool:
        if buy_context is None:
            return False
        entry_ts = buy_context.get("entry_dt")
        entry_price = buy_context.get("entry_price")
        if entry_ts is None or entry_price is None:
            return False
        elapsed = (self._normalize_ts(event_ts) - self._normalize_ts(entry_ts)).total_seconds()
        if elapsed < settings.aggregate_sell_no_continuation_seconds:
            return False
        highs_since_buy = (
            self.db.query(PolygonSecondAggregate.high)
            .filter(
                PolygonSecondAggregate.ticker == ticker.upper(),
                PolygonSecondAggregate.second_ts >= entry_ts,
                PolygonSecondAggregate.second_ts <= event_ts,
            )
            .all()
        )
        max_high = max((row[0] for row in highs_since_buy), default=None)
        if max_high is None:
            return False
        if max_high > entry_price:
            return False
        return (state.validation_score or 0.0) < settings.aggregate_decision_min_validation_score

    def _should_sell_quick_profit_spike(
        self,
        *,
        ticker: str,
        event_ts: datetime,
        latest_second: PolygonSecondAggregate | None,
        buy_context: dict | None,
    ) -> bool:
        if latest_second is None or buy_context is None:
            return False
        entry_ts = buy_context.get("entry_dt")
        entry_price = buy_context.get("entry_price")
        if entry_ts is None or entry_price is None or entry_price <= 0:
            return False
        highs_since_buy = (
            self.db.query(PolygonSecondAggregate.high)
            .filter(
                PolygonSecondAggregate.ticker == ticker.upper(),
                PolygonSecondAggregate.second_ts >= entry_ts,
                PolygonSecondAggregate.second_ts <= event_ts,
            )
            .all()
        )
        highest_since_buy = max((row[0] for row in highs_since_buy), default=None)
        if highest_since_buy is None:
            return False
        if highest_since_buy < entry_price * (1.0 + settings.aggregate_sell_quick_profit_pct):
            return False
        return latest_second.close <= highest_since_buy * (1.0 - settings.aggregate_sell_quick_profit_retrace_pct)

    def _latest_second_row(self, *, ticker: str, event_ts: datetime) -> PolygonSecondAggregate | None:
        return (
            self.db.query(PolygonSecondAggregate)
            .filter(
                PolygonSecondAggregate.ticker == ticker.upper(),
                PolygonSecondAggregate.second_ts <= event_ts,
            )
            .order_by(PolygonSecondAggregate.second_ts.desc())
            .first()
        )

    def _latest_buy_context(self, *, ticker: str, event_ts: datetime) -> dict | None:
        cutoff_ts = self._normalize_ts(event_ts)
        row = (
            self.db.query(DecisionEvent)
            .filter(
                DecisionEvent.ticker == ticker.upper(),
                DecisionEvent.decision_type == "buy",
                DecisionEvent.decision_ts <= cutoff_ts,
            )
            .order_by(DecisionEvent.decision_ts.desc(), DecisionEvent.id.desc())
            .first()
        )
        if row is None:
            return None
        payload = json.loads(row.decision_payload or "{}")
        entry_price = payload.get("current_close")
        return {
            "entry_price": entry_price,
            "entry_ts": row.decision_ts.isoformat(),
            "entry_dt": row.decision_ts,
        }

    def _latest_persisted_decision(self, *, ticker: str) -> DecisionEvent | None:
        return (
            self.db.query(DecisionEvent)
            .filter(DecisionEvent.ticker == ticker.upper())
            .order_by(DecisionEvent.decision_ts.desc(), DecisionEvent.id.desc())
            .first()
        )

    def _has_buy_on_trade_day(self, *, ticker: str, event_ts: datetime) -> bool:
        trade_day = self._trade_day_for_ts(event_ts)
        rows = (
            self.db.query(DecisionEvent.decision_ts)
            .filter(
                DecisionEvent.ticker == ticker.upper(),
                DecisionEvent.decision_type == "buy",
            )
            .all()
        )
        return any(self._trade_day_for_ts(row[0]) == trade_day for row in rows)

    def _is_ticker_in_current_aggregate_universe(self, ticker: str) -> bool:
        allowed = SecretIngredientsService(self.db).select_aggregate_subscription_tickers()
        if not allowed:
            return True
        return ticker.upper() in {symbol.upper() for symbol in allowed}

    @staticmethod
    def _trade_day_for_ts(value: datetime) -> datetime.date:
        if value.tzinfo is None:
            aware = value.replace(tzinfo=timezone.utc)
        else:
            aware = value.astimezone(timezone.utc)
        return aware.astimezone(NEW_YORK_TZ).date()

    @staticmethod
    def _normalize_ts(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None)
