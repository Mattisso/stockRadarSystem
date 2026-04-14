"""Tests for Polygon WebSocket connection management."""

import json
from contextlib import asynccontextmanager

import pytest

from app.data.polygon_connection import PolygonConnectionManager


class FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send(self, payload: str) -> None:
        self.sent.append(payload)


class FakeConnectWebSocket(FakeWebSocket):
    def __init__(self, responses: list[str]) -> None:
        super().__init__()
        self._responses = list(responses)

    async def recv(self) -> str:
        if not self._responses:
            raise RuntimeError("No more responses")
        return self._responses.pop(0)


class FakeConnector:
    def __init__(self, ws: FakeConnectWebSocket) -> None:
        self._ws = ws

    @asynccontextmanager
    async def __call__(self, url: str):
        yield self._ws


def test_build_subscription_batches_chunks_large_universe():
    manager = PolygonConnectionManager(api_key="key", subscription_batch_size=2)

    batches = manager.build_subscription_batches(["AAPL", "TSLA", "MSFT", "NVDA", "AMD"])

    assert batches == [
        "Q.AAPL,Q.TSLA",
        "Q.MSFT,Q.NVDA",
        "Q.AMD",
    ]


def test_build_subscription_batches_for_aggregate_channels():
    manager = PolygonConnectionManager(api_key="key", subscription_batch_size=2)

    batches = manager.build_subscription_batches(["AAPL", "TSLA", "MSFT"], channels=("AM", "A"))

    assert batches == [
        "AM.AAPL,AM.TSLA,A.AAPL,A.TSLA",
        "AM.MSFT,A.MSFT",
    ]


def test_build_subscription_batches_can_include_trade_wildcard():
    manager = PolygonConnectionManager(api_key="key", subscription_batch_size=2)

    batches = manager.build_subscription_batches(["AAPL", "TSLA"], include_trades=True)

    assert batches == [
        "T.*",
        "Q.AAPL,Q.TSLA",
    ]


async def test_subscribe_sends_one_message_per_batch():
    manager = PolygonConnectionManager(api_key="key", subscription_batch_size=2)
    ws = FakeWebSocket()

    await manager.subscribe(ws, ["AAPL", "TSLA", "MSFT"])

    assert [json.loads(payload) for payload in ws.sent] == [
        {"action": "subscribe", "params": "Q.AAPL,Q.TSLA"},
        {"action": "subscribe", "params": "Q.MSFT"},
    ]


@pytest.mark.asyncio
async def test_subscribe_can_send_trade_wildcard():
    manager = PolygonConnectionManager(api_key="key", subscription_batch_size=2)
    ws = FakeWebSocket()

    await manager.subscribe(ws, ["AAPL", "TSLA"], include_trades=True)

    assert [json.loads(payload) for payload in ws.sent] == [
        {"action": "subscribe", "params": "T.*"},
        {"action": "subscribe", "params": "Q.AAPL,Q.TSLA"},
    ]


@pytest.mark.asyncio
async def test_open_waits_for_auth_success():
    ws = FakeConnectWebSocket([
        '[{"ev":"status","status":"connected","message":"Connected Successfully"}]',
        '[{"ev":"status","status":"auth_success","message":"authenticated"}]',
    ])
    manager = PolygonConnectionManager(api_key="key", connector=FakeConnector(ws))

    async with manager.open():
        pass

    assert [json.loads(payload) for payload in ws.sent] == [
        {"action": "auth", "params": "key"},
    ]


@pytest.mark.asyncio
async def test_open_raises_when_auth_success_never_arrives():
    ws = FakeConnectWebSocket([
        '[{"ev":"status","status":"connected","message":"Connected Successfully"}]',
    ] * 5)
    manager = PolygonConnectionManager(api_key="key", connector=FakeConnector(ws))

    with pytest.raises(RuntimeError, match="auth success not received"):
        async with manager.open():
            pass
