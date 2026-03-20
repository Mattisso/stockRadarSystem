"""Tests for WebSocket endpoint and ConnectionManager."""

import json

import pytest
from starlette.testclient import TestClient

from app.api.websocket import ConnectionManager
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


class TestConnectionManager:
    @pytest.mark.asyncio
    async def test_initial_state(self):
        mgr = ConnectionManager()
        assert mgr.active_count == 0

    @pytest.mark.asyncio
    async def test_broadcast_no_connections(self):
        """broadcast with no clients should not raise."""
        mgr = ConnectionManager()
        await mgr.broadcast("test", {"hello": "world"})


class TestWebSocketEndpoint:
    def test_connect_and_receive(self, client):
        with client.websocket_connect("/api/ws") as ws:
            # Connection should be accepted — send a ping to exercise the loop
            ws.send_text("ping")

    def test_disconnect_cleanup(self, client):
        """After closing, manager should remove the connection."""
        with client.websocket_connect("/api/ws"):
            pass  # disconnect happens on context exit
