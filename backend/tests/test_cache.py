"""Tests for cache abstraction (InMemoryCache)."""

import asyncio
from datetime import datetime

import pytest

from app.broker.interface import OrderBook, OrderBookLevel, Quote
from app.data.cache import InMemoryCache


@pytest.fixture
def cache():
    return InMemoryCache(ttl=2)


@pytest.fixture
def sample_quote():
    return Quote(ticker="LCID", bid=3.47, ask=3.48, last=3.48, volume=100000, timestamp=datetime.now())


@pytest.fixture
def sample_book():
    return OrderBook(
        ticker="LCID",
        bids=[OrderBookLevel(price=3.47, size=1000), OrderBookLevel(price=3.46, size=800)],
        asks=[OrderBookLevel(price=3.48, size=900), OrderBookLevel(price=3.49, size=700)],
    )


@pytest.mark.asyncio
async def test_connect_disconnect(cache):
    await cache.connect()
    assert await cache.is_healthy()
    await cache.disconnect()


@pytest.mark.asyncio
async def test_l1_set_get(cache, sample_quote):
    await cache.connect()
    await cache.set_l1("LCID", sample_quote)
    result = await cache.get_l1("LCID")
    assert result is not None
    assert result.ticker == "LCID"
    assert result.bid == 3.47


@pytest.mark.asyncio
async def test_l1_missing_key(cache):
    await cache.connect()
    result = await cache.get_l1("NONEXISTENT")
    assert result is None


@pytest.mark.asyncio
async def test_l1_ttl_expiry(cache, sample_quote):
    await cache.connect()
    await cache.set_l1("LCID", sample_quote)
    await asyncio.sleep(2.1)
    result = await cache.get_l1("LCID")
    assert result is None


@pytest.mark.asyncio
async def test_l2_set_get(cache, sample_book):
    await cache.connect()
    await cache.set_l2("LCID", sample_book)
    result = await cache.get_l2("LCID")
    assert result is not None
    assert result.ticker == "LCID"
    assert len(result.bids) == 2


@pytest.mark.asyncio
async def test_l2_missing_key(cache):
    await cache.connect()
    result = await cache.get_l2("NONEXISTENT")
    assert result is None
