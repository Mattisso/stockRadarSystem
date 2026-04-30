"""Tests for API routes."""

from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.core.auth import create_access_token
from app.core.database import get_db
from app.main import app
from app.models.candidate_event import CandidateEvent
from app.models.decision_event import DecisionEvent
from app.models.polygon_minute_aggregate import PolygonMinuteAggregate
from app.models.polygon_minute_aggregate_live import PolygonMinuteAggregateLive
from app.models.polygon_second_aggregate import PolygonSecondAggregate
from app.models.polygon_second_aggregate_live import PolygonSecondAggregateLive
from app.models.polygon_tick import PolygonTick
from app.models.polygon_tick_live import PolygonTickLive
from app.models.symbol_state_live import SymbolStateLive
from app.models.symbol import Symbol
from app.models.universe_daily import UniverseDaily


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers():
    token = create_access_token()
    return {"Authorization": f"Bearer {token}"}


# ── Public routes ────────────────────────────────────────────────────


def test_health_check(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "system_status" in body


def test_cors_preflight_allows_local_frontend_origin(client):
    response = client.options(
        "/api/portfolio",
        headers={
            "Origin": "http://127.0.0.1:14201",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:14201"


# ── Auth ─────────────────────────────────────────────────────────────


def test_auth_token_valid(client):
    from app.core.config import settings
    response = client.post("/api/auth/token", json={"api_key": settings.api_secret_key})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_auth_token_invalid(client):
    response = client.post("/api/auth/token", json={"api_key": "wrong-key"})
    assert response.status_code == 401


def test_contract_metadata(client):
    response = client.get("/api/contract")
    assert response.status_code == 200
    body = response.json()
    assert body["rest_base"] == "/api"
    assert "/api/ws/signals" in body["websocket_channels"]
    assert "/api/secret-sauce/handoffs" in body["protected_routes"]


# ── Protected routes require auth ────────────────────────────────────


def test_protected_route_no_auth(client):
    response = client.get("/api/universe")
    assert response.status_code == 401


def test_get_universe_empty(client, auth_headers):
    response = client.get("/api/universe", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_trades_empty(client, auth_headers):
    response = client.get("/api/trades", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_signals_empty(client, auth_headers):
    response = client.get("/api/signals", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_system_health_endpoint(client, auth_headers):
    response = client.get("/api/health/system", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert "services" in body
    assert "background_tasks" in body


def test_portfolio_degrades_when_broker_disconnected(client, auth_headers):
    client.app.state.broker._connected = False
    response = client.get("/api/portfolio", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["positions"] == []


def test_signal_accuracy_typed_response(client, auth_headers):
    response = client.get("/api/analytics/signal-accuracy", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_secret_sauce_contract(client, auth_headers):
    response = client.get("/api/secret-sauce/contract", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["consumer"] == "secret_sauce"
    assert body["handoff_route"] == "/api/secret-sauce/handoffs"


def test_secret_sauce_handoffs_returns_recent_events(client, auth_headers):
    from app.engine.secret_sauce_handoff import SecretSauceHandoffManager
    from app.engine.secret_candidate_scorer import SecretCandidateEvent
    from datetime import datetime, timezone

    manager = SecretSauceHandoffManager()
    manager.emit(
        [
            SecretCandidateEvent(
                ticker="AAPL",
                breakout_score=0.81,
                pct_change_1m=4.2,
                pct_change_5m=4.2,
                volume_ratio=2.0,
                spread_pct=0.004,
                quote_rate=1.1,
                buy_pressure=0.74,
                timestamp=datetime.now(tz=timezone.utc),
                reason_flags=["price_velocity", "buy_pressure"],
            )
        ]
    )
    client.app.state.secret_sauce_handoffs = manager

    response = client.get("/api/secret-sauce/handoffs", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["ticker"] == "AAPL"
    assert body[0]["consumer"] == "secret_sauce"


def test_secret_sauce_queue_status(client, auth_headers):
    response = client.get("/api/secret-sauce/queue", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert "queue_depth" in body
    assert "active_tickers" in body


def test_secret_sauce_status(client, auth_headers):
    response = client.get("/api/secret-sauce/status", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert "runtime" in body
    assert "queue" in body
    assert "polygon_session" in body
    assert "configured_secret_universe_source" in body["runtime"]
    assert "last_secret_universe_source" in body["runtime"]


def test_secret_sauce_replay(client, auth_headers):
    payload = {
        "quotes": [
            {
                "ticker": "LCID",
                "bid": 3.00,
                "ask": 3.01,
                "last": 3.005,
                "volume": 20000,
                "timestamp": "2026-04-01T09:30:00Z",
            },
            {
                "ticker": "LCID",
                "bid": 3.05,
                "ask": 3.06,
                "last": 3.055,
                "volume": 40000,
                "timestamp": "2026-04-01T09:30:15Z",
            },
            {
                "ticker": "LCID",
                "bid": 3.10,
                "ask": 3.11,
                "last": 3.105,
                "volume": 60000,
                "timestamp": "2026-04-01T09:30:30Z",
            },
            {
                "ticker": "LCID",
                "bid": 3.15,
                "ask": 3.16,
                "last": 3.155,
                "volume": 80000,
                "timestamp": "2026-04-01T09:30:45Z",
            },
            {
                "ticker": "LCID",
                "bid": 3.20,
                "ask": 3.21,
                "last": 3.205,
                "volume": 100000,
                "timestamp": "2026-04-01T09:31:00Z",
            },
        ]
    }

    response = client.post("/api/secret-sauce/replay", json=payload, headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert "snapshots" in body
    assert "candidates" in body
    assert "handoffs" in body
    assert "queue" in body
    assert "promoted_tickers" in body


def test_polygon_second_aggregates_filters_to_latest_under_ten_universe(db_engine, auth_headers):
    TestingSessionLocal = sessionmaker(bind=db_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestingSessionLocal() as db:
            db.add_all(
                [
                    UniverseDaily(
                        trade_date=date(2026, 4, 7),
                        ticker="AAPL",
                        open_price=150.0,
                        last_price=151.0,
                        avg_volume=1_000_000,
                    ),
                    UniverseDaily(
                        trade_date=date(2026, 4, 7),
                        ticker="SIRI",
                        open_price=9.5,
                        last_price=9.7,
                        avg_volume=2_000_000,
                    ),
                    PolygonSecondAggregate(
                        ticker="SIRI",
                        second_ts=datetime(2026, 4, 7, 13, 30, 0, tzinfo=timezone.utc),
                        open=9.50,
                        high=9.60,
                        low=9.50,
                        close=9.60,
                        volume=300,
                        vwap=9.56,
                        transactions=2,
                    ),
                    PolygonSecondAggregate(
                        ticker="SIRI",
                        second_ts=datetime(2026, 4, 7, 13, 10, 0, tzinfo=timezone.utc),
                        open=9.20,
                        high=9.20,
                        low=9.20,
                        close=9.20,
                        volume=50,
                        vwap=9.20,
                        transactions=1,
                    ),
                    PolygonSecondAggregateLive(
                        ticker="SIRI",
                        second_ts=datetime(2026, 4, 7, 13, 30, 0, tzinfo=timezone.utc),
                        open=9.50,
                        high=9.60,
                        low=9.50,
                        close=9.60,
                        volume=300,
                        vwap=9.56,
                        transactions=2,
                    ),
                    PolygonSecondAggregateLive(
                        ticker="SIRI",
                        second_ts=datetime(2026, 4, 7, 13, 10, 0, tzinfo=timezone.utc),
                        open=9.20,
                        high=9.20,
                        low=9.20,
                        close=9.20,
                        volume=50,
                        vwap=9.20,
                        transactions=1,
                    ),
                    PolygonSecondAggregate(
                        ticker="AAPL",
                        second_ts=datetime(2026, 4, 7, 13, 30, 0, tzinfo=timezone.utc),
                        open=150.0,
                        high=150.0,
                        low=150.0,
                        close=150.0,
                        volume=999,
                        vwap=150.0,
                        transactions=1,
                    ),
                    PolygonSecondAggregateLive(
                        ticker="AAPL",
                        second_ts=datetime(2026, 4, 7, 13, 30, 0, tzinfo=timezone.utc),
                        open=150.0,
                        high=150.0,
                        low=150.0,
                        close=150.0,
                        volume=999,
                        vwap=150.0,
                        transactions=1,
                    ),
                ]
            )
            db.commit()

        with TestClient(app) as client:
            response = client.get(
                "/api/polygon/second-aggregates",
                headers=auth_headers,
                params={"page": 0, "page_size": 10},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["trade_date"] == "2026-04-07"
        assert body["total"] is None
        assert len(body["items"]) == 2
        assert body["items"][0]["ticker"] == "SIRI"
        assert body["items"][0]["second_ts"].startswith("2026-04-07T13:30:00")
        assert body["items"][0]["open"] == 9.5
        assert body["items"][0]["high"] == 9.6
        assert body["items"][0]["low"] == 9.5
        assert body["items"][0]["close"] == 9.6
        assert body["items"][0]["volume"] == 300
        assert body["items"][0]["transactions"] == 2
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_symbol_state_live_filters_to_latest_under_ten_universe(db_engine, auth_headers):
    TestingSessionLocal = sessionmaker(bind=db_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestingSessionLocal() as db:
            db.add_all(
                [
                    UniverseDaily(
                        trade_date=date(2026, 4, 10),
                        ticker="AAPL",
                        open_price=150.0,
                        last_price=151.0,
                        avg_volume=1_000_000,
                    ),
                    UniverseDaily(
                        trade_date=date(2026, 4, 10),
                        ticker="SIRI",
                        open_price=9.5,
                        last_price=9.7,
                        avg_volume=2_000_000,
                    ),
                    SymbolStateLive(
                        ticker="SIRI",
                        candidate_status="candidate",
                        candidate_score=0.82,
                        rolling_second_volume=1200,
                        rolling_green_count=3,
                        is_second_stream_stale=False,
                        is_minute_stream_stale=False,
                        updated_at=datetime(2026, 4, 10, 13, 35, 0),
                    ),
                    SymbolStateLive(
                        ticker="AAPL",
                        candidate_status="idle",
                        candidate_score=None,
                        rolling_second_volume=2500,
                        rolling_green_count=1,
                        is_second_stream_stale=False,
                        is_minute_stream_stale=False,
                        updated_at=datetime(2026, 4, 10, 13, 34, 0),
                    ),
                ]
            )
            db.commit()

        with TestClient(app) as client:
            response = client.get(
                "/api/aggregate/symbol-state-live",
                headers=auth_headers,
                params={"page": 0, "page_size": 10},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert len(body["items"]) == 1
        assert body["items"][0]["ticker"] == "SIRI"
        assert body["items"][0]["candidate_status"] == "candidate"
        assert body["items"][0]["candidate_score"] == 0.82
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_polygon_minute_aggregates_reads_live_table(db_engine, auth_headers):
    TestingSessionLocal = sessionmaker(bind=db_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestingSessionLocal() as db:
            db.add_all(
                [
                    UniverseDaily(
                        trade_date=date(2026, 4, 7),
                        ticker="SIRI",
                        exchange="NASDAQ",
                        open_price=9.1,
                        last_price=9.4,
                        avg_volume=500_000,
                    ),
                    PolygonMinuteAggregate(
                        ticker="SIRI",
                        minute_ts=datetime(2026, 4, 7, 13, 29, 0, tzinfo=timezone.utc),
                        open=9.0,
                        high=9.05,
                        low=8.95,
                        close=9.01,
                        volume=50,
                        vwap=9.0,
                        transactions=1,
                    ),
                    PolygonMinuteAggregateLive(
                        ticker="SIRI",
                        minute_ts=datetime(2026, 4, 7, 13, 30, 0, tzinfo=timezone.utc),
                        open=9.50,
                        high=9.60,
                        low=9.50,
                        close=9.60,
                        volume=300,
                        vwap=9.56,
                        transactions=2,
                    ),
                    PolygonMinuteAggregate(
                        ticker="AAPL",
                        minute_ts=datetime(2026, 4, 7, 13, 30, 0, tzinfo=timezone.utc),
                        open=150.0,
                        high=150.0,
                        low=150.0,
                        close=150.0,
                        volume=999,
                        vwap=150.0,
                        transactions=1,
                    ),
                    PolygonMinuteAggregateLive(
                        ticker="AAPL",
                        minute_ts=datetime(2026, 4, 7, 13, 30, 0, tzinfo=timezone.utc),
                        open=150.0,
                        high=150.0,
                        low=150.0,
                        close=150.0,
                        volume=999,
                        vwap=150.0,
                        transactions=1,
                    ),
                ]
            )
            db.commit()

        with TestClient(app) as client:
            response = client.get(
                "/api/polygon/minute-aggregates",
                headers=auth_headers,
                params={"page": 0, "page_size": 10},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["trade_date"] == "2026-04-07"
        assert body["total"] is None
        assert len(body["items"]) == 1
        assert body["items"][0]["ticker"] == "SIRI"
        assert body["items"][0]["minute_ts"].startswith("2026-04-07T13:30:00")
        assert body["items"][0]["open"] == 9.5
        assert body["items"][0]["high"] == 9.6
        assert body["items"][0]["low"] == 9.5
        assert body["items"][0]["close"] == 9.6
        assert body["items"][0]["volume"] == 300
        assert body["items"][0]["transactions"] == 2
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_polygon_minute_aggregates_excludes_rows_priced_over_ten_even_if_ticker_is_in_universe(db_engine, auth_headers):
    TestingSessionLocal = sessionmaker(bind=db_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestingSessionLocal() as db:
            db.add_all(
                [
                    UniverseDaily(
                        trade_date=date(2026, 4, 24),
                        ticker="SOFI",
                        exchange="NASDAQ",
                        open_price=9.5,
                        last_price=9.7,
                        avg_volume=500_000,
                    ),
                    PolygonMinuteAggregateLive(
                        ticker="SOFI",
                        minute_ts=datetime(2026, 4, 24, 13, 20, 0, tzinfo=timezone.utc),
                        open=18.30,
                        high=18.36,
                        low=18.29,
                        close=18.36,
                        volume=300,
                        vwap=18.33,
                        transactions=2,
                    ),
                ]
            )
            db.commit()

        with TestClient(app) as client:
            response = client.get(
                "/api/polygon/minute-aggregates",
                headers=auth_headers,
                params={"page": 0, "page_size": 10},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["trade_date"] is None
        assert body["total"] is None
        assert body["items"] == []
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_candidate_events_filters_by_trade_date_and_universe(db_engine, auth_headers):
    TestingSessionLocal = sessionmaker(bind=db_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestingSessionLocal() as db:
            db.add_all(
                [
                    UniverseDaily(
                        trade_date=date(2026, 4, 10),
                        ticker="AAPL",
                        open_price=150.0,
                        last_price=151.0,
                        avg_volume=1_000_000,
                    ),
                    UniverseDaily(
                        trade_date=date(2026, 4, 10),
                        ticker="SIRI",
                        open_price=9.5,
                        last_price=9.7,
                        avg_volume=2_000_000,
                    ),
                    CandidateEvent(
                        ticker="SIRI",
                        event_ts=datetime(2026, 4, 10, 13, 35, 0, tzinfo=timezone.utc),
                        trigger_name="breakout_above_recent_high",
                        trigger_payload='{"recent_high": 9.6}',
                        last_second_ts=datetime(2026, 4, 10, 13, 35, 0, tzinfo=timezone.utc),
                        is_second_stream_stale=False,
                        is_minute_stream_stale=False,
                    ),
                    CandidateEvent(
                        ticker="SIRI",
                        event_ts=datetime(2026, 4, 9, 13, 35, 0, tzinfo=timezone.utc),
                        trigger_name="second_volume_spike",
                        trigger_payload='{"second_volume": 2000}',
                        last_second_ts=datetime(2026, 4, 9, 13, 35, 0, tzinfo=timezone.utc),
                        is_second_stream_stale=False,
                        is_minute_stream_stale=False,
                    ),
                    CandidateEvent(
                        ticker="AAPL",
                        event_ts=datetime(2026, 4, 10, 13, 35, 0, tzinfo=timezone.utc),
                        trigger_name="breakout_above_recent_high",
                        trigger_payload='{"recent_high": 150.0}',
                        last_second_ts=datetime(2026, 4, 10, 13, 35, 0, tzinfo=timezone.utc),
                        is_second_stream_stale=False,
                        is_minute_stream_stale=False,
                    ),
                ]
            )
            db.commit()

        with TestClient(app) as client:
            response = client.get(
                "/api/aggregate/candidate-events",
                headers=auth_headers,
                params={"page": 0, "page_size": 10},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["trade_date"] == "2026-04-10"
        assert body["total"] == 1
        assert len(body["items"]) == 1
        assert body["items"][0]["ticker"] == "SIRI"
        assert body["items"][0]["trigger_name"] == "breakout_above_recent_high"
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_decision_events_filters_by_trade_date_and_universe(db_engine, auth_headers):
    TestingSessionLocal = sessionmaker(bind=db_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestingSessionLocal() as db:
            db.add_all(
                [
                    UniverseDaily(
                        trade_date=date(2026, 4, 10),
                        ticker="AAPL",
                        open_price=150.0,
                        last_price=151.0,
                        avg_volume=1_000_000,
                    ),
                    UniverseDaily(
                        trade_date=date(2026, 4, 10),
                        ticker="SIRI",
                        open_price=9.5,
                        last_price=9.7,
                        avg_volume=2_000_000,
                    ),
                    DecisionEvent(
                        ticker="SIRI",
                        decision_ts=datetime(2026, 4, 10, 13, 40, 0, tzinfo=timezone.utc),
                        decision_type="candidate",
                        reason_code="validated_candidate",
                        decision_payload='{"validation_score": 0.8}',
                        candidate_score=0.82,
                        validation_pass_count=8,
                        is_second_stream_stale=False,
                        is_minute_stream_stale=False,
                    ),
                    DecisionEvent(
                        ticker="SIRI",
                        decision_ts=datetime(2026, 4, 9, 13, 40, 0, tzinfo=timezone.utc),
                        decision_type="reject",
                        reason_code="validation_below_threshold",
                        decision_payload='{"validation_score": 0.3}',
                        candidate_score=0.45,
                        validation_pass_count=3,
                        is_second_stream_stale=False,
                        is_minute_stream_stale=False,
                    ),
                    DecisionEvent(
                        ticker="AAPL",
                        decision_ts=datetime(2026, 4, 10, 13, 40, 0, tzinfo=timezone.utc),
                        decision_type="candidate",
                        reason_code="validated_candidate",
                        decision_payload='{"validation_score": 0.9}',
                        candidate_score=0.90,
                        validation_pass_count=9,
                        is_second_stream_stale=False,
                        is_minute_stream_stale=False,
                    ),
                ]
            )
            db.commit()

        with TestClient(app) as client:
            response = client.get(
                "/api/aggregate/decision-events",
                headers=auth_headers,
                params={"page": 0, "page_size": 10},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["trade_date"] == "2026-04-10"
        assert body["total"] == 1
        assert len(body["items"]) == 1
        assert body["items"][0]["ticker"] == "SIRI"
        assert body["items"][0]["decision_type"] == "candidate"
        assert body["items"][0]["reason_code"] == "validated_candidate"
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_decision_event_analytics_summary_and_by_reason(db_engine, auth_headers):
    TestingSessionLocal = sessionmaker(bind=db_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestingSessionLocal() as db:
            db.add_all(
                [
                    DecisionEvent(
                        ticker="AAA",
                        decision_ts=datetime(2026, 4, 29, 14, 0, 0, tzinfo=timezone.utc),
                        decision_type="buy",
                        reason_code="validated_buy_setup",
                        decision_payload='{"current_close": 10.0}',
                        candidate_score=0.9,
                        validation_pass_count=9,
                        is_second_stream_stale=False,
                        is_minute_stream_stale=False,
                    ),
                    DecisionEvent(
                        ticker="AAA",
                        decision_ts=datetime(2026, 4, 29, 14, 5, 0, tzinfo=timezone.utc),
                        decision_type="sell",
                        reason_code="active_position_momentum_dies",
                        decision_payload='{"current_close": 10.5, "entry_price": 10.0}',
                        candidate_score=0.9,
                        validation_pass_count=9,
                        is_second_stream_stale=False,
                        is_minute_stream_stale=False,
                    ),
                    DecisionEvent(
                        ticker="BBB",
                        decision_ts=datetime(2026, 4, 29, 15, 0, 0, tzinfo=timezone.utc),
                        decision_type="buy",
                        reason_code="validated_buy_setup",
                        decision_payload='{"current_close": 20.0}',
                        candidate_score=0.9,
                        validation_pass_count=9,
                        is_second_stream_stale=False,
                        is_minute_stream_stale=False,
                    ),
                    DecisionEvent(
                        ticker="BBB",
                        decision_ts=datetime(2026, 4, 29, 15, 10, 0, tzinfo=timezone.utc),
                        decision_type="sell",
                        reason_code="active_position_stop_loss",
                        decision_payload='{"current_close": 19.0, "entry_price": 20.0}',
                        candidate_score=0.9,
                        validation_pass_count=9,
                        is_second_stream_stale=False,
                        is_minute_stream_stale=False,
                    ),
                ]
            )
            db.commit()

        with TestClient(app) as client:
            summary = client.get(
                "/api/analytics/decision-events/summary",
                headers=auth_headers,
                params={"trade_date": "2026-04-29"},
            )
            by_reason = client.get(
                "/api/analytics/decision-events/by-reason",
                headers=auth_headers,
                params={"trade_date": "2026-04-29"},
            )

        assert summary.status_code == 200
        body = summary.json()
        assert body["trade_date"] == "2026-04-29"
        assert body["completed_trades"] == 2
        assert body["profitable_sales"] == 1
        assert body["losing_sales"] == 1
        assert body["flat_sales"] == 0
        assert body["avg_pnl_pct"] == pytest.approx(0.0)

        assert by_reason.status_code == 200
        reason_rows = {row["reason_code"]: row for row in by_reason.json()}
        assert reason_rows["active_position_momentum_dies"]["profitable_sales"] == 1
        assert reason_rows["active_position_stop_loss"]["losing_sales"] == 1
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_decision_event_analytics_details_and_duplicate_buys(db_engine, auth_headers):
    TestingSessionLocal = sessionmaker(bind=db_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestingSessionLocal() as db:
            db.add_all(
                [
                    DecisionEvent(
                        ticker="CLVT",
                        decision_ts=datetime(2026, 4, 29, 14, 0, 0, tzinfo=timezone.utc),
                        decision_type="buy",
                        reason_code="validated_buy_setup",
                        decision_payload='{"current_close": 5.0}',
                        candidate_score=0.9,
                        validation_pass_count=9,
                        is_second_stream_stale=False,
                        is_minute_stream_stale=False,
                    ),
                    DecisionEvent(
                        ticker="CLVT",
                        decision_ts=datetime(2026, 4, 29, 14, 5, 0, tzinfo=timezone.utc),
                        decision_type="buy",
                        reason_code="validated_buy_setup",
                        decision_payload='{"current_close": 5.1}',
                        candidate_score=0.9,
                        validation_pass_count=9,
                        is_second_stream_stale=False,
                        is_minute_stream_stale=False,
                    ),
                    DecisionEvent(
                        ticker="CLVT",
                        decision_ts=datetime(2026, 4, 29, 14, 10, 0, tzinfo=timezone.utc),
                        decision_type="sell",
                        reason_code="active_position_momentum_dies",
                        decision_payload='{"current_close": 5.2, "entry_price": 5.0}',
                        candidate_score=0.9,
                        validation_pass_count=9,
                        is_second_stream_stale=False,
                        is_minute_stream_stale=False,
                    ),
                ]
            )
            db.commit()

        with TestClient(app) as client:
            details = client.get(
                "/api/analytics/decision-events/details",
                headers=auth_headers,
                params={"trade_date": "2026-04-29", "reason_code": "active_position_momentum_dies"},
            )
            duplicate_buys = client.get(
                "/api/analytics/decision-events/duplicate-buys",
                headers=auth_headers,
                params={"trade_date": "2026-04-29"},
            )

        assert details.status_code == 200
        detail_rows = details.json()
        assert len(detail_rows) == 1
        assert detail_rows[0]["ticker"] == "CLVT"
        assert detail_rows[0]["buy_price"] == pytest.approx(5.0)
        assert detail_rows[0]["sell_price"] == pytest.approx(5.2)

        assert duplicate_buys.status_code == 200
        audit_rows = duplicate_buys.json()
        assert len(audit_rows) == 1
        assert audit_rows[0]["ticker"] == "CLVT"
        assert audit_rows[0]["buy_count"] == 2
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_decision_event_market_validation_endpoint(db_engine, auth_headers):
    TestingSessionLocal = sessionmaker(bind=db_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestingSessionLocal() as db:
            db.add_all(
                [
                    DecisionEvent(
                        ticker="PLTR",
                        decision_ts=datetime(2026, 4, 29, 22, 41, 29, tzinfo=timezone.utc),
                        decision_type="buy",
                        reason_code="validated_buy_setup",
                        decision_payload='{"current_close": 137.51}',
                        candidate_score=0.9,
                        validation_pass_count=9,
                        is_second_stream_stale=False,
                        is_minute_stream_stale=False,
                    ),
                    DecisionEvent(
                        ticker="PLTR",
                        decision_ts=datetime(2026, 4, 29, 22, 41, 32, tzinfo=timezone.utc),
                        decision_type="sell",
                        reason_code="active_position_momentum_dies",
                        decision_payload='{"current_close": 137.51, "entry_price": 137.51}',
                        candidate_score=0.9,
                        validation_pass_count=9,
                        is_second_stream_stale=False,
                        is_minute_stream_stale=False,
                    ),
                    DecisionEvent(
                        ticker="OPK",
                        decision_ts=datetime(2026, 4, 29, 17, 39, 30, tzinfo=timezone.utc),
                        decision_type="sell",
                        reason_code="active_position_momentum_dies",
                        decision_payload='{"current_close": 1.114}',
                        candidate_score=0.9,
                        validation_pass_count=9,
                        is_second_stream_stale=False,
                        is_minute_stream_stale=False,
                    ),
                    PolygonSecondAggregate(
                        ticker="PLTR",
                        second_ts=datetime(2026, 4, 29, 22, 41, 28),
                        open=137.40,
                        high=137.52,
                        low=137.39,
                        close=137.51,
                        volume=1000,
                        vwap=137.49,
                        transactions=10,
                    ),
                ]
            )
            db.commit()

        with TestClient(app) as client:
            response = client.get(
                "/api/analytics/decision-events/market-validation",
                headers=auth_headers,
                params={"trade_date": "2026-04-29", "page": 0, "page_size": 10},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["trade_date"] == "2026-04-29"
        assert body["total"] == 2
        assert body["summary"]["MATCHED"] == 1
        assert body["summary"]["NO_PRIOR_BUY"] == 1
        matched = next(row for row in body["items"] if row["ticker"] == "PLTR")
        assert matched["match_status"] == "MATCHED"
        assert matched["buy_price_from_market"] == pytest.approx(137.51)
        assert matched["sell_price_from_market"] == pytest.approx(137.51)
        unmatched = next(row for row in body["items"] if row["ticker"] == "OPK")
        assert unmatched["match_status"] == "NO_PRIOR_BUY"
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_polygon_ticks_reads_operational_live_table_only(db_engine, auth_headers):
    TestingSessionLocal = sessionmaker(bind=db_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestingSessionLocal() as db:
            db.add(
                UniverseDaily(
                    trade_date=date(2026, 4, 11),
                    ticker="ALTS",
                    open_price=1.12,
                    last_price=1.10,
                    avg_volume=1_100_000,
                )
            )
            db.add(
                PolygonTick(
                    ticker="ALTS",
                    event_type="trade",
                    bid=1.09,
                    ask=1.10,
                    last=1.095,
                    volume=999,
                    tick_ts=datetime(2026, 4, 11, 13, 30, 1, tzinfo=timezone.utc),
                )
            )
            db.add(
                PolygonTickLive(
                    ticker="ALTS",
                    event_type="trade",
                    bid=1.11,
                    ask=1.12,
                    last=1.115,
                    volume=2500,
                    tick_ts=datetime(2026, 4, 11, 13, 30, 2, tzinfo=timezone.utc),
                )
            )
            db.add(
                PolygonTickLive(
                    ticker="ALTS",
                    event_type="trade",
                    bid=1.11,
                    ask=1.12,
                    last=1.115,
                    volume=2500,
                    tick_ts=datetime(2026, 4, 11, 13, 30, 2, tzinfo=timezone.utc),
                )
            )
            db.commit()

        with TestClient(app) as client:
            response = client.get(
                "/api/polygon/ticks?ticker=ALTS",
                headers=auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["page"] is None
        assert len(body["items"]) == 1
        assert body["items"][0]["volume"] == 2500
        assert body["items"][0]["last"] == pytest.approx(1.115)
        assert body["has_more"] is False
        assert body["next_cursor"] is None
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_polygon_ticks_does_not_fallback_to_symbol_table_when_universe_daily_is_empty(db_engine, auth_headers):
    TestingSessionLocal = sessionmaker(bind=db_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestingSessionLocal() as db:
            db.add(
                Symbol(
                    ticker="SOFI",
                    exchange="NASDAQ",
                    last_price=9.5,
                    avg_volume=2_000_000,
                    is_active=True,
                )
            )
            db.add(
                PolygonTickLive(
                    ticker="SOFI",
                    event_type="trade",
                    bid=18.30,
                    ask=18.31,
                    last=18.30,
                    volume=1000,
                    tick_ts=datetime(2026, 4, 24, 13, 20, 0, tzinfo=timezone.utc),
                )
            )
            db.commit()

        with TestClient(app) as client:
            response = client.get(
                "/api/polygon/ticks",
                headers=auth_headers,
                params={"page_size": 25},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["items"] == []
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_polygon_ticks_history_reads_retained_history_table(db_engine, auth_headers):
    TestingSessionLocal = sessionmaker(bind=db_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestingSessionLocal() as db:
            db.add(
                UniverseDaily(
                    trade_date=date(2026, 4, 11),
                    ticker="ALTS",
                    open_price=1.12,
                    last_price=1.10,
                    avg_volume=1_100_000,
                )
            )
            db.add(
                PolygonTick(
                    ticker="ALTS",
                    event_type="trade",
                    bid=1.09,
                    ask=1.10,
                    last=1.095,
                    volume=999,
                    tick_ts=datetime(2026, 4, 11, 13, 30, 1, tzinfo=timezone.utc),
                )
            )
            db.add(
                PolygonTick(
                    ticker="ALTS",
                    event_type="trade",
                    bid=1.09,
                    ask=1.10,
                    last=1.095,
                    volume=999,
                    tick_ts=datetime(2026, 4, 11, 13, 30, 1, tzinfo=timezone.utc),
                )
            )
            db.add(
                PolygonTickLive(
                    ticker="ALTS",
                    event_type="trade",
                    bid=1.11,
                    ask=1.12,
                    last=1.115,
                    volume=2500,
                    tick_ts=datetime(2026, 4, 11, 13, 30, 2, tzinfo=timezone.utc),
                )
            )
            db.commit()

        with TestClient(app) as client:
            response = client.get(
                "/api/polygon/history/ticks?ticker=ALTS",
                headers=auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert len(body["items"]) == 1
        assert body["items"][0]["volume"] == 999
        assert body["items"][0]["last"] == pytest.approx(1.095)
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_polygon_second_aggregates_history_reads_retained_history_table(db_engine, auth_headers):
    TestingSessionLocal = sessionmaker(bind=db_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestingSessionLocal() as db:
            db.add(
                UniverseDaily(
                    trade_date=date(2026, 4, 11),
                    ticker="ALTS",
                    open_price=1.12,
                    last_price=1.10,
                    avg_volume=1_100_000,
                )
            )
            db.add(
                PolygonSecondAggregate(
                    ticker="ALTS",
                    second_ts=datetime(2026, 4, 11, 13, 30, 1, tzinfo=timezone.utc),
                    open=1.09,
                    high=1.10,
                    low=1.09,
                    close=1.10,
                    volume=999,
                    vwap=1.095,
                    transactions=1,
                )
            )
            db.add(
                PolygonSecondAggregateLive(
                    ticker="ALTS",
                    second_ts=datetime(2026, 4, 11, 13, 30, 2, tzinfo=timezone.utc),
                    open=1.11,
                    high=1.12,
                    low=1.11,
                    close=1.12,
                    volume=2500,
                    vwap=1.115,
                    transactions=2,
                )
            )
            db.commit()

        with TestClient(app) as client:
            response = client.get(
                "/api/polygon/history/second-aggregates?ticker=ALTS",
                headers=auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert len(body["items"]) == 1
        assert body["items"][0]["volume"] == 999
        assert body["items"][0]["close"] == pytest.approx(1.10)
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_polygon_minute_aggregates_history_reads_historical_table(db_engine, auth_headers):
    TestingSessionLocal = sessionmaker(bind=db_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestingSessionLocal() as db:
            db.add(
                UniverseDaily(
                    trade_date=date(2026, 4, 11),
                    ticker="ALTS",
                    open_price=1.12,
                    last_price=1.10,
                    avg_volume=1_100_000,
                )
            )
            db.add(
                PolygonMinuteAggregate(
                    ticker="ALTS",
                    minute_ts=datetime(2026, 4, 11, 13, 30, 0, tzinfo=timezone.utc),
                    open=1.09,
                    high=1.10,
                    low=1.09,
                    close=1.10,
                    volume=999,
                    vwap=1.095,
                    transactions=1,
                )
            )
            db.add(
                PolygonMinuteAggregateLive(
                    ticker="ALTS",
                    minute_ts=datetime(2026, 4, 11, 13, 31, 0, tzinfo=timezone.utc),
                    open=1.11,
                    high=1.12,
                    low=1.11,
                    close=1.12,
                    volume=2500,
                    vwap=1.115,
                    transactions=2,
                )
            )
            db.commit()

        with TestClient(app) as client:
            response = client.get(
                "/api/polygon/history/minute-aggregates?ticker=ALTS",
                headers=auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert len(body["items"]) == 1
        assert body["items"][0]["volume"] == 999
        assert body["items"][0]["close"] == pytest.approx(1.10)
    finally:
        app.dependency_overrides.pop(get_db, None)
