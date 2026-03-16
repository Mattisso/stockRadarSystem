"""Tests for the MockBroker implementation."""

import pytest

from app.broker.interface import OrderSide, OrderStatus, OrderType
from app.broker.mock_broker import MockBroker


@pytest.fixture
async def broker():
    b = MockBroker(initial_balance=50_000.0)
    await b.connect()
    yield b
    await b.disconnect()


@pytest.mark.asyncio
async def test_connect_disconnect(broker):
    assert broker._connected is True


@pytest.mark.asyncio
async def test_get_quote(broker):
    quote = await broker.get_quote("SIRI")
    assert quote.ticker == "SIRI"
    assert quote.bid > 0
    assert quote.ask > quote.bid
    assert quote.last > 0
    assert quote.volume > 0


@pytest.mark.asyncio
async def test_get_order_book(broker):
    book = await broker.get_order_book("LCID")
    assert book.ticker == "LCID"
    assert len(book.bids) == 10
    assert len(book.asks) == 10
    assert book.bids[0].price > book.bids[1].price  # Descending bids
    assert book.asks[0].price < book.asks[1].price  # Ascending asks


@pytest.mark.asyncio
async def test_submit_buy_order(broker):
    result = await broker.submit_order(
        ticker="SIRI",
        side=OrderSide.BUY,
        quantity=100,
        order_type=OrderType.MARKET,
    )
    assert result.status == OrderStatus.FILLED
    assert result.fill_price > 0
    assert result.filled_quantity == 100
    positions = await broker.get_positions()
    assert len(positions) == 1
    assert positions[0].ticker == "SIRI"
    assert positions[0].quantity == 100


@pytest.mark.asyncio
async def test_submit_sell_order(broker):
    # Buy first
    await broker.submit_order("SIRI", OrderSide.BUY, 100, OrderType.MARKET)
    # Then sell
    result = await broker.submit_order("SIRI", OrderSide.SELL, 100, OrderType.MARKET)
    assert result.status == OrderStatus.FILLED
    positions = await broker.get_positions()
    assert len(positions) == 0


@pytest.mark.asyncio
async def test_account_summary(broker):
    summary = await broker.get_account_summary()
    assert summary.cash_balance == 50_000.0
    assert summary.total_value == 50_000.0
    assert summary.buying_power == 50_000.0


@pytest.mark.asyncio
async def test_get_universe(broker):
    tickers = await broker.get_universe(max_price=10.0, min_price=1.0, min_volume=100_000)
    assert len(tickers) > 0
    assert all(isinstance(t, str) for t in tickers)


@pytest.mark.asyncio
async def test_subscribe_unsubscribe(broker):
    await broker.subscribe_market_data(["SIRI", "LCID"])
    assert "SIRI" in broker._subscribed
    await broker.unsubscribe_market_data(["SIRI"])
    assert "SIRI" not in broker._subscribed
    assert "LCID" in broker._subscribed


@pytest.mark.asyncio
async def test_limit_order_rejected_when_price_exceeds_limit(broker):
    result = await broker.submit_order(
        ticker="SIRI",
        side=OrderSide.BUY,
        quantity=100,
        order_type=OrderType.LIMIT,
        limit_price=0.01,  # Way below market — should reject
    )
    assert result.status == OrderStatus.REJECTED
