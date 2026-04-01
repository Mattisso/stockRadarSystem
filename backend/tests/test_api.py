"""Tests for API routes."""

import pytest
from fastapi.testclient import TestClient

from app.core.auth import create_access_token
from app.main import app


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
