from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from zoneinfo import ZoneInfo

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.market_hours import is_regular_us_market_hours
from app.engine.aggregate_decision_engine import AggregateDecisionEngine
from app.engine.aggregate_validation_engine import AggregateValidationEngine
from app.engine.symbol_state_live_service import SymbolStateLiveService
from app.models.candidate_event import CandidateEvent
from app.models.symbol_state_live import SymbolStateLive

NEW_YORK_TZ = ZoneInfo("America/New_York")


@dataclass(slots=True)
class AggregateRollingRefreshResult:
    refreshed_state_count: int
    persisted_decision_count: int
    refreshed_validation_count: int
    processed_candidate_event_count: int
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
        states = (
            self.db.query(SymbolStateLive)
            .filter(
                SymbolStateLive.candidate_status.in_(("candidate", "validated", "buy", "manage"))
            )
            .order_by(SymbolStateLive.ticker.asc())
            .all()
        )

        state_service = SymbolStateLiveService(self.db)
        validation_engine = AggregateValidationEngine(self.db)
        decision_engine = AggregateDecisionEngine(self.db)

        refreshed_validation_count = 0
        persisted_decision_count = 0
        processed_candidate_event_count = 0
        allow_decisions = is_regular_us_market_hours(reference_ts)
        if allow_decisions:
            persisted_from_events, processed_candidate_event_count = self._process_candidate_events(
                state_service=state_service,
                decision_engine=decision_engine,
                as_of=reference_ts,
            )
            persisted_decision_count += persisted_from_events
        for state in states:
            state_service.refresh_state(state, as_of=reference_ts)
            if state.last_second_ts is None:
                continue
            if not allow_decisions:
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
            processed_candidate_event_count=processed_candidate_event_count,
            as_of=reference_ts,
        )

    def _process_candidate_events(
        self,
        *,
        state_service: SymbolStateLiveService,
        decision_engine: AggregateDecisionEngine,
        as_of: datetime,
    ) -> tuple[int, int]:
        reference_trade_day = self._trade_day_for_ts(as_of)
        allow_live_decisions = is_regular_us_market_hours(as_of)
        order_by = (
            (CandidateEvent.created_at.desc(), CandidateEvent.id.desc())
            if allow_live_decisions
            else (CandidateEvent.created_at.asc(), CandidateEvent.id.asc())
        )
        rows = (
            self.db.query(CandidateEvent)
            .filter(
                CandidateEvent.processed_at.is_(None),
                or_(
                    CandidateEvent.last_second_ts <= as_of,
                    CandidateEvent.event_ts <= as_of,
                    CandidateEvent.created_at <= as_of,
                ),
            )
            .order_by(*order_by)
            .limit(1000)
            .all()
        )
        if not rows:
            return 0, 0

        persisted_decision_count = 0
        processed_count = 0
        idx = 0
        while idx < len(rows):
            batch_start = rows[idx]
            batch = [batch_start]
            idx += 1
            while idx < len(rows):
                row = rows[idx]
                if row.ticker != batch_start.ticker or row.event_ts != batch_start.event_ts:
                    break
                batch.append(row)
                idx += 1

            effective_event_ts = self._effective_event_ts(batch_start)
            if self._trade_day_for_ts(effective_event_ts) != reference_trade_day:
                for row in batch:
                    row.processed_at = as_of
                processed_count += len(batch)
                continue

            if allow_live_decisions and not self._is_candidate_event_fresh(
                event_ts=effective_event_ts,
                as_of=as_of,
            ):
                for row in batch:
                    row.processed_at = as_of
                processed_count += len(batch)
                continue

            state = self.db.query(SymbolStateLive).filter_by(ticker=batch_start.ticker).one_or_none()
            if state is not None and is_regular_us_market_hours(effective_event_ts):
                self._apply_candidate_batch_to_state(state, batch)
                decision = decision_engine.evaluate(
                    ticker=batch_start.ticker,
                    event_ts=effective_event_ts,
                    trigger_count=len(batch),
                    state=state,
                )
                persisted_decision_count += decision_engine.persist(decision, state, dedupe=True)

            for row in batch:
                row.processed_at = as_of
            processed_count += len(batch)

        self.db.flush()
        return persisted_decision_count, processed_count

    @staticmethod
    def _apply_candidate_batch_to_state(state: SymbolStateLive, batch: list[CandidateEvent]) -> None:
        validation_score = None
        validation_pass_count = None
        for row in batch:
            try:
                payload = json.loads(row.trigger_payload or "{}")
            except json.JSONDecodeError:
                payload = {}
            if payload.get("validation_score") is not None:
                try:
                    validation_score = float(payload["validation_score"])
                except (TypeError, ValueError):
                    pass
            if payload.get("validation_pass_count") is not None:
                try:
                    validation_pass_count = int(payload["validation_pass_count"])
                except (TypeError, ValueError):
                    pass

        state.last_second_ts = batch[-1].last_second_ts or state.last_second_ts
        state.last_minute_ts = batch[-1].last_minute_ts or state.last_minute_ts
        state.seconds_since_last_trade_bar = batch[-1].seconds_since_last_trade_bar
        state.minutes_since_last_trade_bar = batch[-1].minutes_since_last_trade_bar
        state.is_second_stream_stale = any(row.is_second_stream_stale for row in batch)
        state.is_minute_stream_stale = any(row.is_minute_stream_stale for row in batch)
        if validation_score is not None:
            state.validation_score = validation_score
        if validation_pass_count is not None:
            state.validation_pass_count = validation_pass_count
        trigger_score = max((row.trigger_score or 0.0) for row in batch)
        state.candidate_score = trigger_score or state.candidate_score
        if state.candidate_status not in {"buy", "manage", "sold"}:
            state.candidate_status = "candidate"

    def _effective_event_ts(self, row: CandidateEvent) -> datetime:
        return self._normalize_ts(row.last_second_ts or row.event_ts)

    @staticmethod
    def _is_candidate_event_fresh(*, event_ts: datetime, as_of: datetime) -> bool:
        max_age_seconds = max(settings.aggregate_candidate_event_max_age_seconds, 0)
        return (as_of - event_ts).total_seconds() <= max_age_seconds

    @staticmethod
    def _trade_day_for_ts(value: datetime) -> datetime.date:
        normalized = AggregateRuntimeService._normalize_ts(value)
        aware = normalized.replace(tzinfo=timezone.utc)
        return aware.astimezone(NEW_YORK_TZ).date()

    @staticmethod
    def _normalize_ts(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(microsecond=0)
        return value.astimezone(timezone.utc).replace(tzinfo=None, microsecond=0)
