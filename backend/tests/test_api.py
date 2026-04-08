"""Tests for API routes."""

from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.core.auth import create_access_token
from app.core.database import get_db
from app.main import app
from app.models.polygon_tick import PolygonTick
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
                    PolygonTick(
                        ticker="SIRI",
                        event_type="trade",
                        bid=9.50,
                        ask=9.50,
                        last=9.50,
                        volume=100,
                        tick_ts=datetime(2026, 4, 7, 13, 30, 0, 100000, tzinfo=timezone.utc),
                    ),
                    PolygonTick(
                        ticker="SIRI",
                        event_type="trade",
                        bid=9.60,
                        ask=9.60,
                        last=9.60,
                        volume=200,
                        tick_ts=datetime(2026, 4, 7, 13, 30, 0, 900000, tzinfo=timezone.utc),
                    ),
                    PolygonTick(
                        ticker="AAPL",
                        event_type="trade",
                        bid=150.0,
                        ask=150.0,
                        last=150.0,
                        volume=999,
                        tick_ts=datetime(2026, 4, 7, 13, 30, 0, 500000, tzinfo=timezone.utc),
                    ),
                ]
            )
            db.commit()

        with TestClient(app) as client:
            response = client.get(
                "/api/polygon/second-aggregates",
                headers=auth_headers,
                params={"limit": 10},
            )

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["ticker"] == "SIRI"
        assert body[0]["open"] == 9.5
        assert body[0]["high"] == 9.6
        assert body[0]["low"] == 9.5
        assert body[0]["close"] == 9.6
        assert body[0]["volume"] == 300
        assert body[0]["transactions"] == 2
    finally:
        app.dependency_overrides.pop(get_db, None)
