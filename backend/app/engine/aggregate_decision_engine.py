from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.decision_event import DecisionEvent
from app.models.symbol_state_live import SymbolStateLive


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
        if trigger_count <= 0:
            return None

        if state.is_second_stream_stale:
            return AggregateDecision(
                ticker=ticker.upper(),
                decision_ts=event_ts,
                decision_type="reject",
                reason_code="second_stream_stale",
                payload=self._payload(state, trigger_count),
            )
        if state.is_minute_stream_stale:
            return AggregateDecision(
                ticker=ticker.upper(),
                decision_ts=event_ts,
                decision_type="reject",
                reason_code="minute_stream_stale",
                payload=self._payload(state, trigger_count),
            )
        if (state.validation_score or 0.0) < settings.aggregate_decision_min_validation_score:
            return AggregateDecision(
                ticker=ticker.upper(),
                decision_ts=event_ts,
                decision_type="reject",
                reason_code="validation_below_threshold",
                payload=self._payload(state, trigger_count),
            )
        if (state.validation_pass_count or 0) < settings.aggregate_decision_min_validation_pass_count:
            return AggregateDecision(
                ticker=ticker.upper(),
                decision_ts=event_ts,
                decision_type="reject",
                reason_code="validation_pass_count_too_low",
                payload=self._payload(state, trigger_count),
            )

        return AggregateDecision(
            ticker=ticker.upper(),
            decision_ts=event_ts,
            decision_type="candidate",
            reason_code="validated_candidate",
            payload=self._payload(state, trigger_count),
        )

    def persist(self, decision: AggregateDecision | None, state: SymbolStateLive) -> int:
        if decision is None:
            return 0

        self.db.add(
            DecisionEvent(
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
        )
        state.candidate_status = "validated" if decision.decision_type == "candidate" else "rejected"
        self.db.flush()
        return 1

    @staticmethod
    def _payload(state: SymbolStateLive, trigger_count: int) -> dict:
        return {
            "trigger_count": trigger_count,
            "candidate_score": state.candidate_score,
            "validation_score": state.validation_score,
            "validation_pass_count": state.validation_pass_count,
        }
