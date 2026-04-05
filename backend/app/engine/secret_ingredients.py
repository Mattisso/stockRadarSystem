"""First-sprint Secret Ingredients persistence and handoff helpers."""

from dataclasses import asdict, dataclass
from datetime import date, datetime
import json

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.engine.secret_candidate_scorer import SecretCandidateEvent
from app.models.l1_candidate import L1Candidate
from app.models.l1_to_l2_event import L1ToL2Event
from app.models.symbol import Symbol
from app.models.universe_daily import UniverseDaily


@dataclass(frozen=True)
class DailyUniverseSnapshot:
    ticker: str
    exchange: str = "NASDAQ"
    open_price: float | None = None
    prev_close: float | None = None
    last_price: float | None = None
    avg_volume: int | None = None


class SecretIngredientsService:
    """Persist first-sprint Secret Ingredients outputs around the existing L1 path."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def record_daily_universe(
        self,
        tickers: list[str],
        *,
        trade_date: date | None = None,
        snapshots_by_ticker: dict[str, DailyUniverseSnapshot] | None = None,
    ) -> int:
        trade_date = trade_date or date.today()
        rows_added = 0
        snapshots_by_ticker = snapshots_by_ticker or {}
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
            snapshot = snapshots_by_ticker.get(ticker)
            exchange = (
                snapshot.exchange if snapshot is not None and snapshot.exchange else
                symbol.exchange if symbol is not None else
                "NASDAQ"
            )
            open_price = snapshot.open_price if snapshot is not None else None
            prev_close = snapshot.prev_close if snapshot is not None else None
            last_price = (
                snapshot.last_price if snapshot is not None and snapshot.last_price is not None else
                symbol.last_price if symbol is not None else
                None
            )
            avg_volume = (
                snapshot.avg_volume if snapshot is not None and snapshot.avg_volume is not None else
                symbol.avg_volume if symbol is not None else
                None
            )
            if existing is not None:
                existing.exchange = exchange
                existing.open_price = open_price
                existing.prev_close = prev_close
                existing.last_price = last_price
                existing.avg_volume = avg_volume
                continue
            row = UniverseDaily(
                trade_date=trade_date,
                ticker=ticker,
                exchange=exchange,
                open_price=open_price,
                prev_close=prev_close,
                last_price=last_price,
                avg_volume=avg_volume,
            )
            self.db.add(row)
            rows_added += 1
        self.db.flush()
        return rows_added

    def latest_daily_universe_tickers(self) -> list[str]:
        """Return the most recent persisted Secret Ingredients universe snapshot."""
        latest_trade_date = self.db.query(UniverseDaily.trade_date).order_by(desc(UniverseDaily.trade_date)).limit(1).scalar()
        if latest_trade_date is None:
            return []
        rows = (
            self.db.query(UniverseDaily)
            .filter_by(trade_date=latest_trade_date)
            .order_by(UniverseDaily.ticker.asc())
            .all()
        )
        return [row.ticker for row in rows]

    def record_candidates(self, events: list[SecretCandidateEvent]) -> list[L1Candidate]:
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

    def record_l1_to_l2_events(self, events: list[SecretCandidateEvent]) -> list[L1ToL2Event]:
        rows: list[L1ToL2Event] = []
        for event in events:
            payload = self.build_handoff_payload(event)
            now = datetime.now()
            row = L1ToL2Event(
                ticker=event.ticker,
                detect_ts=event.timestamp,
                escalate_ts=now,
                latency_ms=max(0.0, (now - event.timestamp).total_seconds() * 1000),
                escalation_reason="secret_candidate",
                handoff_payload=json.dumps(payload, sort_keys=True),
            )
            self.db.add(row)
            rows.append(row)
        self.db.flush()
        return rows

    @staticmethod
    def build_handoff_payload(event: SecretCandidateEvent) -> dict:
        payload = asdict(event)
        payload["timestamp"] = event.timestamp.isoformat()
        payload["promotion_reason"] = "secret_candidate"
        return payload

    @staticmethod
    def _reason_flags(event: SecretCandidateEvent) -> str:
        if event.reason_flags:
            return ",".join(event.reason_flags)
        flags: list[str] = []
        if event.breakout_score >= 0.6:
            flags.append("candidate_score")
        if event.pct_change_1m >= 3.0:
            flags.append("price_velocity")
        if event.volume_ratio >= 1.8:
            flags.append("volume_expansion")
        if event.buy_pressure >= 0.65:
            flags.append("buy_pressure")
        return ",".join(flags)
