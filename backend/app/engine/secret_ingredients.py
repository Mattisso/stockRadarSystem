"""First-sprint Secret Ingredients persistence and handoff helpers."""

from dataclasses import asdict
from datetime import date, datetime
import json

from sqlalchemy.orm import Session

from app.engine.breakout_engine import BreakoutEvent
from app.models.l1_candidate import L1Candidate
from app.models.l1_to_l2_event import L1ToL2Event
from app.models.symbol import Symbol
from app.models.universe_daily import UniverseDaily


class SecretIngredientsService:
    """Persist first-sprint Secret Ingredients outputs around the existing L1 path."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def record_daily_universe(
        self,
        tickers: list[str],
        *,
        trade_date: date | None = None,
    ) -> int:
        trade_date = trade_date or date.today()
        rows_added = 0
        symbols = {
            symbol.ticker: symbol
            for symbol in self.db.query(Symbol).filter(Symbol.ticker.in_(tickers)).all()
        }
        for ticker in tickers:
            existing = (
                self.db.query(UniverseDaily)
                .filter_by(trade_date=trade_date, ticker=ticker)
                .first()
            )
            symbol = symbols.get(ticker)
            if existing is not None:
                if symbol is not None:
                    existing.last_price = symbol.last_price
                    existing.avg_volume = symbol.avg_volume
                continue
            row = UniverseDaily(
                trade_date=trade_date,
                ticker=ticker,
                exchange=symbol.exchange if symbol is not None else "NASDAQ",
                last_price=symbol.last_price if symbol is not None else None,
                avg_volume=symbol.avg_volume if symbol is not None else None,
            )
            self.db.add(row)
            rows_added += 1
        self.db.flush()
        return rows_added

    def record_candidates(self, events: list[BreakoutEvent]) -> list[L1Candidate]:
        records: list[L1Candidate] = []
        for event in events:
            record = L1Candidate(
                ticker=event.ticker,
                detected_at=event.timestamp,
                breakout_score=event.breakout_score,
                price=None,
                pct_change_1m=event.pct_change_1m,
                pct_change_5m=event.pct_change_5m,
                volume_ratio=event.volume_ratio,
                reason_flags=self._reason_flags(event),
            )
            self.db.add(record)
            records.append(record)
        self.db.flush()
        return records

    def record_l1_to_l2_events(self, events: list[BreakoutEvent]) -> list[L1ToL2Event]:
        rows: list[L1ToL2Event] = []
        for event in events:
            payload = self.build_handoff_payload(event)
            row = L1ToL2Event(
                ticker=event.ticker,
                detect_ts=event.timestamp,
                escalate_ts=datetime.now(),
                latency_ms=max(0.0, (datetime.now() - event.timestamp).total_seconds() * 1000),
                escalation_reason="breakout_candidate",
                handoff_payload=json.dumps(payload, sort_keys=True),
            )
            self.db.add(row)
            rows.append(row)
        self.db.flush()
        return rows

    @staticmethod
    def build_handoff_payload(event: BreakoutEvent) -> dict:
        payload = asdict(event)
        payload["timestamp"] = event.timestamp.isoformat()
        payload["promotion_reason"] = "breakout_candidate"
        return payload

    @staticmethod
    def _reason_flags(event: BreakoutEvent) -> str:
        flags: list[str] = []
        if event.breakout_score >= 0.6:
            flags.append("candidate_score")
        if event.pct_change_1m >= 5.0:
            flags.append("price_velocity")
        if event.volume_ratio >= 2.0:
            flags.append("volume_surge")
        return ",".join(flags)
