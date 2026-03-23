"""Tests for Polygon client (mocked — no API key needed)."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.broker.interface import Quote
from app.data.cache import InMemoryCache
from app.data.polygon_client import PolygonClient


@pytest.fixture
def cache():
    return InMemoryCache(ttl=10)


@pytest.fixture
def queue():
    return asyncio.Queue(maxsize=100)


@pytest.fixture
def client(cache, queue):
    return PolygonClient(
        api_key="test-key",
        mode="rest",
        symbols=["LCID", "GEVO"],
        cache=cache,
        queue=queue,
        rest_poll_interval=0.1,
    )


@pytest.mark.asyncio
async def test_update_subscriptions(client):
    client.update_subscriptions(["AAPL", "TSLA", "LCID"])
    assert len(client._symbols) == 3


@pytest.mark.asyncio
async def test_dispatch_to_cache(client, cache):
    await cache.connect()
    quote = Quote(ticker="LCID", bid=3.47, ask=3.48, last=3.48, volume=100000, timestamp=datetime.now())
    await client._dispatch(quote)
    result = await cache.get_l1("LCID")
    assert result is not None
    assert result.ticker == "LCID"


@pytest.mark.asyncio
async def test_dispatch_to_queue(client, queue):
    quote = Quote(ticker="LCID", bid=3.47, ask=3.48, last=3.48, volume=100000, timestamp=datetime.now())
    await client._dispatch(quote)
    assert not queue.empty()
    item = queue.get_nowait()
    assert item.ticker == "LCID"


@pytest.mark.asyncio
async def test_handle_ws_message(client, cache):
    await cache.connect()
    msg = {
        "ev": "Q",
        "sym": "GEVO",
        "bp": 1.87,
        "ap": 1.88,
        "z": 500000,
        "t": int(datetime.now(tz=timezone.utc).timestamp() * 1000),
    }
    await client._handle_ws_message(msg)
    result = await cache.get_l1("GEVO")
    assert result is not None
    assert result.bid == 1.87


@pytest.mark.asyncio
async def test_handle_ws_message_ignores_non_quote(client, cache):
    await cache.connect()
    msg = {"ev": "T", "sym": "GEVO"}  # Trade event, not quote
    await client._handle_ws_message(msg)
    result = await cache.get_l1("GEVO")
    assert result is None


@pytest.mark.asyncio
async def test_queue_full_does_not_raise(cache):
    """When queue is full, dispatch should not raise."""
    small_queue = asyncio.Queue(maxsize=1)
    c = PolygonClient(api_key="x", cache=cache, queue=small_queue)
    await cache.connect()

    q1 = Quote(ticker="A", bid=1, ask=2, last=1, volume=1, timestamp=datetime.now())
    q2 = Quote(ticker="B", bid=1, ask=2, last=1, volume=1, timestamp=datetime.now())

    await c._dispatch(q1)
    await c._dispatch(q2)  # Should not raise even though queue is full
    assert small_queue.qsize() == 1


@pytest.mark.asyncio
async def test_rest_poll_mocked(client, cache):
    """Test REST poll with mocked httpx response."""
    await cache.connect()

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = lambda: {
        "results": [
            {"ticker": "LCID", "session": {"close": 3.50, "volume": 200000}},
            {"ticker": "GEVO", "session": {"close": 1.90, "volume": 150000}},
        ]
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    await client._rest_poll(mock_client)

    lcid = await cache.get_l1("LCID")
    assert lcid is not None
    assert lcid.last == 3.50

    gevo = await cache.get_l1("GEVO")
    assert gevo is not None
    assert gevo.last == 1.90
