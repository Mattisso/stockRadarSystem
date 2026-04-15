from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.engine.aggregate_decision_engine import AggregateDecisionEngine
from app.engine.aggregate_validation_engine import AggregateValidationEngine
from app.engine.symbol_state_live_service import SymbolStateLiveService
from app.models.symbol_state_live import SymbolStateLive


@dataclass(slots=True)
class AggregateRollingRefreshResult:
    refreshed_state_count: int
    persisted_decision_count: int
    refreshed_validation_count: int
    as_of: datetime


class AggregateRuntimeService:
    """Refresh aggregate validation and decisions on a wall-clock cadence."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def refresh_validation_and_decisions(
        self,
        *,
        as_of: datetime | None = None,
    ) -> AggregateRollingRefreshResult:
        reference_ts = self._normalize_ts(as_of or datetime.now(timezone.utc))
        recent_cutoff = reference_ts - timedelta(
            minutes=max(1, settings.polygon_second_aggregate_recent_window_minutes)
        )
        states = (
            self.db.query(SymbolStateLive)
            .filter(
                or_(
                    SymbolStateLive.last_second_ts >= recent_cutoff,
                    SymbolStateLive.candidate_status.in_(("candidate", "validated", "buy", "manage")),
                )
            )
            .order_by(SymbolStateLive.ticker.asc())
            .all()
        )

        state_service = SymbolStateLiveService(self.db)
        validation_engine = AggregateValidationEngine(self.db)
        decision_engine = AggregateDecisionEngine(self.db)

        refreshed_validation_count = 0
        persisted_decision_count = 0
        for state in states:
            state_service.refresh_state(state, as_of=reference_ts)
            if state.last_second_ts is None:
                continue
            validation = validation_engine.evaluate(state.ticker, state, reference_ts)
            validation_engine.persist(state, validation)
            refreshed_validation_count += 1

            decision = decision_engine.evaluate(
                ticker=state.ticker,
                event_ts=reference_ts,
                trigger_count=0,
                state=state,
            )
            persisted_decision_count += decision_engine.persist(decision, state, dedupe=True)

        self.db.flush()
        return AggregateRollingRefreshResult(
            refreshed_state_count=len(states),
            refreshed_validation_count=refreshed_validation_count,
            persisted_decision_count=persisted_decision_count,
            as_of=reference_ts,
        )

    @staticmethod
    def _normalize_ts(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(microsecond=0)
        return value.astimezone(timezone.utc).replace(tzinfo=None, microsecond=0)
