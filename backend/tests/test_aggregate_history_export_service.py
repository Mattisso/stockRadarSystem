from datetime import date, datetime, timezone
import json

from app.data.aggregate_history_export_service import AggregateHistoryExportService
from app.models.candidate_event import CandidateEvent
from app.models.decision_event import DecisionEvent
from app.models.polygon_minute_aggregate import PolygonMinuteAggregate
from app.models.polygon_second_aggregate import PolygonSecondAggregate
from app.models.universe_daily import (
    UNIVERSE_KIND_MARKET,
    UNIVERSE_KIND_OPERATIONAL,
    UNIVERSE_SOURCE_ACTIVE_WATCHLIST,
    UNIVERSE_SOURCE_POLYGON_FLATFILE,
    UniverseDaily,
)


def test_aggregate_history_export_service_writes_partition_files(db, tmp_path):
    db.add(
        UniverseDaily(
            trade_date=date(2026, 4, 13),
            ticker="LCID",
            universe_kind=UNIVERSE_KIND_MARKET,
            source=UNIVERSE_SOURCE_POLYGON_FLATFILE,
            exchange="NASDAQ",
            open_price=3.00,
            last_price=3.10,
            avg_volume=1200,
        )
    )
    db.add(
        UniverseDaily(
            trade_date=date(2026, 4, 13),
            ticker="LCID",
            universe_kind=UNIVERSE_KIND_OPERATIONAL,
            source=UNIVERSE_SOURCE_ACTIVE_WATCHLIST,
            exchange="NASDAQ",
        )
    )
    db.add(
        PolygonMinuteAggregate(
            ticker="LCID",
            minute_ts=datetime(2026, 4, 13, 13, 30, 0),
            open=3.00,
            high=3.10,
            low=2.99,
            close=3.08,
            volume=1000,
            vwap=3.05,
            transactions=2,
        )
    )
    db.add(
        PolygonSecondAggregate(
            ticker="LCID",
            second_ts=datetime(2026, 4, 13, 13, 30, 1),
            open=3.01,
            high=3.08,
            low=3.00,
            close=3.07,
            volume=120,
            vwap=3.04,
            transactions=1,
        )
    )
    db.add(
        CandidateEvent(
            ticker="LCID",
            event_ts=datetime(2026, 4, 13, 13, 30, 1),
            trigger_name="velocity_spike",
            trigger_payload='{"close": 3.07}',
            is_second_stream_stale=False,
            is_minute_stream_stale=False,
        )
    )
    db.add(
        DecisionEvent(
            ticker="LCID",
            decision_ts=datetime(2026, 4, 13, 13, 30, 2),
            decision_type="candidate",
            reason_code="validated_candidate",
            decision_payload='{"trigger_count": 1}',
            candidate_score=0.7,
            validation_pass_count=7,
            is_second_stream_stale=False,
            is_minute_stream_stale=False,
        )
    )
    db.commit()

    result = AggregateHistoryExportService(db).export_jsonl(
        output_dir=tmp_path,
        min_age_minutes=30,
        now=datetime(2026, 4, 14, 0, 0, 0, tzinfo=timezone.utc),
    )

    assert result.universe_rows == 1
    assert result.minute_rows == 1
    assert result.second_rows == 1
    assert result.candidate_rows == 1
    assert result.decision_rows == 1

    exported_files = {
        "universe_daily.jsonl",
        "minute_aggregates.jsonl",
        "second_aggregates.jsonl",
        "candidate_events.jsonl",
        "decision_events.jsonl",
    }
    assert exported_files == {path.name for path in tmp_path.iterdir()}

    decision_payload = json.loads((tmp_path / "decision_events.jsonl").read_text(encoding="utf-8").strip())
    assert decision_payload["ticker"] == "LCID"
    assert decision_payload["reason_code"] == "validated_candidate"
    universe_payload = json.loads((tmp_path / "universe_daily.jsonl").read_text(encoding="utf-8").strip())
    assert universe_payload["universe_kind"] == UNIVERSE_KIND_MARKET
