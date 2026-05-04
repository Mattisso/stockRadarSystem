from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models.candidate_event import CandidateEvent
from app.models.decision_event import DecisionEvent
from app.models.polygon_minute_aggregate import PolygonMinuteAggregate
from app.models.polygon_second_aggregate import PolygonSecondAggregate
from app.models.universe_daily import (
    UNIVERSE_KIND_MARKET,
    UniverseDaily,
)


@dataclass(slots=True)
class AggregateHistoryExportResult:
    universe_rows: int
    minute_rows: int
    second_rows: int
    candidate_rows: int
    decision_rows: int
    export_dir: Path
    cutoff_ts: datetime
    cutoff_date: date


class AggregateHistoryExportService:
    """Export older aggregate-phase operational data to partitioned JSONL files."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def export_jsonl(
        self,
        *,
        output_dir: str | Path,
        min_age_minutes: int,
        now: datetime | None = None,
    ) -> AggregateHistoryExportResult:
        reference_ts = self._normalize_ts(now or datetime.now(timezone.utc))
        cutoff_ts = reference_ts - timedelta(minutes=max(1, min_age_minutes))
        cutoff_date = cutoff_ts.date()
        export_dir = Path(output_dir)
        export_dir.mkdir(parents=True, exist_ok=True)

        universe_rows = self._export_model(
            export_dir / "universe_daily.jsonl",
            self.db.query(UniverseDaily)
            .filter(UniverseDaily.universe_kind == UNIVERSE_KIND_MARKET)
            .filter(UniverseDaily.trade_date <= cutoff_date)
            .order_by(UniverseDaily.trade_date.asc(), UniverseDaily.ticker.asc())
            .all(),
            self._serialize_universe_row,
        )
        minute_rows = self._export_model(
            export_dir / "minute_aggregates.jsonl",
            self.db.query(PolygonMinuteAggregate)
            .filter(PolygonMinuteAggregate.minute_ts < cutoff_ts)
            .order_by(PolygonMinuteAggregate.minute_ts.asc(), PolygonMinuteAggregate.ticker.asc())
            .all(),
            self._serialize_aggregate_row,
        )
        second_rows = self._export_model(
            export_dir / "second_aggregates.jsonl",
            self.db.query(PolygonSecondAggregate)
            .filter(PolygonSecondAggregate.second_ts < cutoff_ts)
            .order_by(PolygonSecondAggregate.second_ts.asc(), PolygonSecondAggregate.ticker.asc())
            .all(),
            self._serialize_aggregate_row,
        )
        candidate_rows = self._export_model(
            export_dir / "candidate_events.jsonl",
            self.db.query(CandidateEvent)
            .filter(CandidateEvent.event_ts < cutoff_ts)
            .order_by(CandidateEvent.event_ts.asc(), CandidateEvent.id.asc())
            .all(),
            self._serialize_candidate_row,
        )
        decision_rows = self._export_model(
            export_dir / "decision_events.jsonl",
            self.db.query(DecisionEvent)
            .filter(DecisionEvent.decision_ts < cutoff_ts)
            .order_by(DecisionEvent.decision_ts.asc(), DecisionEvent.id.asc())
            .all(),
            self._serialize_decision_row,
        )

        return AggregateHistoryExportResult(
            universe_rows=universe_rows,
            minute_rows=minute_rows,
            second_rows=second_rows,
            candidate_rows=candidate_rows,
            decision_rows=decision_rows,
            export_dir=export_dir,
            cutoff_ts=cutoff_ts,
            cutoff_date=cutoff_date,
        )

    def _export_model(self, path: Path, rows: list[Any], serializer) -> int:
        if not rows:
            return 0
        with path.open("a", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(serializer(row), sort_keys=True))
                handle.write("\n")
        return len(rows)

    @staticmethod
    def _serialize_universe_row(row: UniverseDaily) -> dict[str, Any]:
        return {
            "trade_date": row.trade_date.isoformat(),
            "ticker": row.ticker,
            "universe_kind": row.universe_kind,
            "source": row.source,
            "exchange": row.exchange,
            "open_price": row.open_price,
            "prev_close": row.prev_close,
            "last_price": row.last_price,
            "avg_volume": row.avg_volume,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    @staticmethod
    def _serialize_aggregate_row(row: PolygonMinuteAggregate | PolygonSecondAggregate) -> dict[str, Any]:
        ts_field = "minute_ts" if hasattr(row, "minute_ts") else "second_ts"
        row_ts = getattr(row, ts_field)
        return {
            "ticker": row.ticker,
            ts_field: row_ts.isoformat() if row_ts else None,
            "open": row.open,
            "high": row.high,
            "low": row.low,
            "close": row.close,
            "volume": row.volume,
            "vwap": row.vwap,
            "transactions": row.transactions,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    @staticmethod
    def _serialize_candidate_row(row: CandidateEvent) -> dict[str, Any]:
        return {
            "ticker": row.ticker,
            "event_ts": row.event_ts.isoformat(),
            "trigger_name": row.trigger_name,
            "trigger_payload": row.trigger_payload,
            "last_second_ts": row.last_second_ts.isoformat() if row.last_second_ts else None,
            "last_minute_ts": row.last_minute_ts.isoformat() if row.last_minute_ts else None,
            "seconds_since_last_trade_bar": row.seconds_since_last_trade_bar,
            "minutes_since_last_trade_bar": row.minutes_since_last_trade_bar,
            "is_second_stream_stale": row.is_second_stream_stale,
            "is_minute_stream_stale": row.is_minute_stream_stale,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    @staticmethod
    def _serialize_decision_row(row: DecisionEvent) -> dict[str, Any]:
        return {
            "ticker": row.ticker,
            "decision_ts": row.decision_ts.isoformat(),
            "decision_type": row.decision_type,
            "reason_code": row.reason_code,
            "decision_payload": row.decision_payload,
            "candidate_score": row.candidate_score,
            "validation_pass_count": row.validation_pass_count,
            "seconds_since_last_trade_bar": row.seconds_since_last_trade_bar,
            "minutes_since_last_trade_bar": row.minutes_since_last_trade_bar,
            "is_second_stream_stale": row.is_second_stream_stale,
            "is_minute_stream_stale": row.is_minute_stream_stale,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    @staticmethod
    def _normalize_ts(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(microsecond=0)
        return value.astimezone(timezone.utc).replace(tzinfo=None, microsecond=0)
