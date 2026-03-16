"""Tests for API routes."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_health_check(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_get_universe_empty(client):
    response = client.get("/api/universe")
    assert response.status_code == 200
    # May be empty if DB has no symbols — that's fine for now
    assert isinstance(response.json(), list)


def test_get_trades_empty(client):
    response = client.get("/api/trades")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_signals_empty(client):
    response = client.get("/api/signals")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
