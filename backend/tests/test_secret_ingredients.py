"""Tests for Secret Ingredients first-sprint persistence helpers."""

from datetime import date, datetime, timedelta

from app.engine.secret_candidate_scorer import SecretCandidateEvent
from app.engine.secret_ingredients import SecretIngredientsService
from app.models.l1_candidate import L1Candidate
from app.models.l1_to_l2_event import L1ToL2Event
from app.models.symbol import Symbol
from app.models.universe_daily import UniverseDaily


def test_record_daily_universe_is_idempotent(db):
    db.add(Symbol(ticker="SIRI", exchange="NASDAQ", last_price=3.2, avg_volume=1000000, is_active=True))
    db.commit()

    service = SecretIngredientsService(db)
    added_first = service.record_daily_universe(["SIRI"], trade_date=date(2026, 3, 31))
    added_second = service.record_daily_universe(["SIRI"], trade_date=date(2026, 3, 31))
    db.commit()

    rows = db.query(UniverseDaily).all()
    assert added_first == 1
    assert added_second == 0
    assert len(rows) == 1
    assert rows[0].ticker == "SIRI"


def test_latest_daily_universe_tickers_returns_most_recent_snapshot(db):
    db.add(Symbol(ticker="SIRI", exchange="NASDAQ", last_price=3.2, avg_volume=1000000, is_active=True))
    db.add(Symbol(ticker="LCID", exchange="NASDAQ", last_price=2.8, avg_volume=2000000, is_active=False))
    db.commit()

    service = SecretIngredientsService(db)
    service.record_daily_universe(["SIRI"], trade_date=date(2026, 3, 31))
    service.record_daily_universe(["LCID"], trade_date=date(2026, 4, 1))
    db.commit()

    assert service.latest_daily_universe_tickers() == ["LCID"]


def test_record_candidates_persists_breakout_fields(db):
    service = SecretIngredientsService(db)
    event = SecretCandidateEvent(
        ticker="SIRI",
        breakout_score=0.72,
        pct_change_1m=8.5,
        pct_change_5m=12.2,
        volume_ratio=2.8,
        spread_pct=0.004,
        quote_rate=1.2,
        buy_pressure=0.73,
        timestamp=datetime.now() - timedelta(seconds=1),
        reason_flags=["price_velocity", "volume_expansion", "buy_pressure"],
    )

    service.record_candidates([event])
    db.commit()

    row = db.query(L1Candidate).one()
    assert row.ticker == "SIRI"
    assert row.breakout_score == 0.72
    assert "buy_pressure" in row.reason_flags
    assert "price_velocity" in row.reason_flags
    assert "volume_expansion" in row.reason_flags


def test_record_l1_to_l2_events_persists_handoff_payload(db):
    service = SecretIngredientsService(db)
    event = SecretCandidateEvent(
        ticker="LCID",
        breakout_score=0.63,
        pct_change_1m=6.2,
        pct_change_5m=9.8,
        volume_ratio=2.2,
        spread_pct=0.005,
        quote_rate=1.1,
        buy_pressure=0.66,
        timestamp=datetime.now() - timedelta(milliseconds=50),
        reason_flags=["price_velocity", "active_tape"],
    )

    service.record_l1_to_l2_events([event])
    db.commit()

    row = db.query(L1ToL2Event).one()
    assert row.ticker == "LCID"
    assert row.escalation_reason == "secret_candidate"
    assert row.latency_ms is not None
    assert "promotion_reason" in row.handoff_payload
