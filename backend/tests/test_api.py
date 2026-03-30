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
