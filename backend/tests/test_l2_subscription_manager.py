"""Tests for the L2 subscription manager."""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from app.broker.interface import OrderBook, OrderBookLevel
from app.engine.l2_subscription_manager import L2SubscriptionManager


@pytest.fixture
def broker():
    broker = AsyncMock()
    broker.subscribe_l2_depth = AsyncMock()
    broker.unsubscribe_l2_depth = AsyncMock()
    broker.get_order_book = AsyncMock(
        return_value=OrderBook(
            ticker="AAPL",
            bids=[OrderBookLevel(price=5.0, size=100)],
            asks=[OrderBookLevel(price=5.02, size=100)],
            timestamp=datetime.now(),
        )
    )
    return broker


def _clock(start: float = 0.0):
    value = {"now": start}

    def _now():
        return value["now"]

    def _set(new_value: float):
        value["now"] = new_value

    return _now, _set


@pytest.mark.asyncio
async def test_subscribe_on_breakout_detection(broker):
    clock, _ = _clock()
    manager = L2SubscriptionManager(broker, timeout_seconds=30.0, clock=clock)

    subscribed = await manager.subscribe("AAPL")

    assert subscribed is True
    broker.subscribe_l2_depth.assert_awaited_once_with("AAPL")
    assert manager.is_active("AAPL")
    assert "AAPL" in manager.active_symbols


@pytest.mark.asyncio
async def test_avoid_duplicate_subscriptions(broker):
    clock, _ = _clock()
    manager = L2SubscriptionManager(broker, timeout_seconds=30.0, clock=clock)

    await manager.subscribe("AAPL")
    subscribed = await manager.subscribe("AAPL")

    assert subscribed is False
    broker.subscribe_l2_depth.assert_awaited_once()


@pytest.mark.asyncio
async def test_unsubscribe_after_expiry_without_confirmation(broker):
    clock, set_clock = _clock()
    manager = L2SubscriptionManager(broker, timeout_seconds=10.0, clock=clock)

    await manager.subscribe("AAPL")
    set_clock(11.0)
    expired = await manager.cleanup_expired()

    assert expired == ["AAPL"]
    broker.unsubscribe_l2_depth.assert_awaited_once_with("AAPL")
    assert not manager.is_active("AAPL")


@pytest.mark.asyncio
async def test_keep_tracking_during_valid_window(broker):
    clock, set_clock = _clock()
    manager = L2SubscriptionManager(broker, timeout_seconds=10.0, clock=clock)

    await manager.subscribe("AAPL")
    set_clock(5.0)
    expired = await manager.cleanup_expired()

    assert expired == []
    broker.unsubscribe_l2_depth.assert_not_awaited()
    assert manager.is_active("AAPL")


@pytest.mark.asyncio
async def test_mark_confirmed_prevents_expiry_cleanup(broker):
    clock, set_clock = _clock()
    manager = L2SubscriptionManager(broker, timeout_seconds=10.0, clock=clock)

    await manager.subscribe("AAPL")
    manager.mark_confirmed("AAPL")
    set_clock(20.0)
    expired = await manager.cleanup_expired()

    assert expired == []
    broker.unsubscribe_l2_depth.assert_not_awaited()
    assert manager.is_active("AAPL")


@pytest.mark.asyncio
async def test_reconnect_resubscribes_active_symbols(broker):
    clock, _ = _clock()
    manager = L2SubscriptionManager(broker, timeout_seconds=10.0, clock=clock)

    await manager.subscribe("AAPL")
    await manager.subscribe("TSLA")
    broker.subscribe_l2_depth.reset_mock()

    await manager.on_reconnect()

    broker.subscribe_l2_depth.assert_any_await("AAPL")
    broker.subscribe_l2_depth.assert_any_await("TSLA")
    assert broker.subscribe_l2_depth.await_count == 2


@pytest.mark.asyncio
async def test_cancel_unknown_symbol_is_safe(broker):
    clock, _ = _clock()
    manager = L2SubscriptionManager(broker, timeout_seconds=10.0, clock=clock)

    result = await manager.unsubscribe("MSFT")

    assert result is False
    broker.unsubscribe_l2_depth.assert_not_awaited()


@pytest.mark.asyncio
async def test_depth_snapshot_can_be_read_during_active_tracking(broker):
    clock, _ = _clock()
    manager = L2SubscriptionManager(broker, timeout_seconds=10.0, clock=clock)

    await manager.subscribe("AAPL")
    order_book = await manager.get_order_book("AAPL")

    assert order_book is not None
    assert order_book.ticker == "AAPL"
    assert order_book.bids[0].price == 5.0
