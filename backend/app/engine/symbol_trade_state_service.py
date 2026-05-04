from __future__ import annotations

import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.decision_event import DecisionEvent
from app.models.symbol_trade_state import SymbolTradeState

NEW_YORK_TZ = ZoneInfo("America/New_York")


class SymbolTradeStateService:
    """Canonical current-position state for aggregate lifecycle decisions."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_or_create(self, *, ticker: str, as_of: datetime | None = None) -> SymbolTradeState:
        symbol = ticker.upper()
        row = (
            self.db.query(SymbolTradeState)
            .filter(SymbolTradeState.ticker == symbol)
            .with_for_update()
            .first()
        )
        if row is not None:
            # If the existing row's trade date is from a different day than as_of, 
            # we might need to reset it, but seeding logic already handles 'flat' vs 'open'.
            # For robustness, we re-seed if the trade date is stale.
            effective_as_of = as_of or datetime.now(timezone.utc)
            today = self._trade_day_for_ts(effective_as_of)
            if row.trade_date != today:
                self._seed_from_decision_history(row, as_of=effective_as_of)
            return row

        row = SymbolTradeState(ticker=symbol)
        self._seed_from_decision_history(row, as_of=as_of)
        self.db.add(row)
        self.db.flush()
        return row

    @staticmethod
    def has_open_position(row: SymbolTradeState) -> bool:
        return row.position_status == "open"

    def mark_open(
        self,
        row: SymbolTradeState,
        *,
        decision_event: DecisionEvent,
        entry_price: float | None,
    ) -> None:
        row.position_status = "open"
        row.trade_date = self._trade_day_for_ts(decision_event.decision_ts)
        row.entry_decision_id = decision_event.id
        row.entry_ts = decision_event.decision_ts
        row.entry_price = entry_price
        row.exit_decision_id = None
        row.exit_ts = None
        row.exit_price = None

    def mark_closed(
        self,
        row: SymbolTradeState,
        *,
        decision_event: DecisionEvent,
        exit_price: float | None,
    ) -> None:
        row.position_status = "closed"
        row.trade_date = self._trade_day_for_ts(decision_event.decision_ts)
        row.exit_decision_id = decision_event.id
        row.exit_ts = decision_event.decision_ts
        row.exit_price = exit_price

    def _seed_from_decision_history(self, row: SymbolTradeState, *, as_of: datetime | None = None) -> None:
        latest_buy = (
            self.db.query(DecisionEvent)
            .filter(
                DecisionEvent.ticker == row.ticker,
                DecisionEvent.decision_type == "buy",
            )
            .order_by(DecisionEvent.decision_ts.desc(), DecisionEvent.id.desc())
            .first()
        )
        latest_sell = (
            self.db.query(DecisionEvent)
            .filter(
                DecisionEvent.ticker == row.ticker,
                DecisionEvent.decision_type == "sell",
            )
            .order_by(DecisionEvent.decision_ts.desc(), DecisionEvent.id.desc())
            .first()
        )
        if latest_buy is None and latest_sell is None:
            row.position_status = "flat"
            return

        # Fix: Ensure we only seed from today's history to avoid cross-day pollution
        reference_ts = as_of or datetime.now(timezone.utc)
        today = self._trade_day_for_ts(reference_ts)

        if latest_buy is not None and (
            latest_sell is None
            or self._normalize_ts(latest_buy.decision_ts) > self._normalize_ts(latest_sell.decision_ts)
        ):
            if self._trade_day_for_ts(latest_buy.decision_ts) == today:
                payload = json.loads(latest_buy.decision_payload or "{}")
                row.position_status = "open"
                row.trade_date = self._trade_day_for_ts(latest_buy.decision_ts)
                row.entry_decision_id = latest_buy.id
                row.entry_ts = latest_buy.decision_ts
                row.entry_price = payload.get("current_close") or payload.get("entry_price")
                return
            else:
                row.position_status = "flat"
                return

        if latest_sell is not None:
            if self._trade_day_for_ts(latest_sell.decision_ts) == today:
                payload = json.loads(latest_sell.decision_payload or "{}")
                row.position_status = "closed"
                row.trade_date = self._trade_day_for_ts(latest_sell.decision_ts)
                row.exit_decision_id = latest_sell.id
                row.exit_ts = latest_sell.decision_ts
                row.exit_price = payload.get("current_close") or payload.get("entry_price")
            else:
                row.position_status = "flat"

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
