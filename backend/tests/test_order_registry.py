"""Tests for the in-memory bracket order registry."""

from app.broker.order_registry import OrderChainState, OrderRegistry


def test_order_registry_tracks_and_updates_chain():
    registry = OrderRegistry()
    chain = OrderChainState(
        ticker="AAPL",
        parent_order_id="10",
        target_order_id="11",
        stop_order_id="12",
        parent_side="buy",
        entry_order_type="limit",
        quantity=100,
        target_price=12.0,
        stop_price=9.5,
    )
    registry.register(chain)

    assert registry.get("10") is chain
    assert registry.by_child_order_id("11") is chain

    registry.update_fill("10", fill_price=10.25, filled_quantity=100, status="filled")
    assert chain.fill_price == 10.25
    assert chain.filled_quantity == 100
    assert chain.status == "filled"
    assert chain.filled_at is not None


def test_order_registry_stop_updates_are_monotonic():
    registry = OrderRegistry()
    chain = OrderChainState(
        ticker="AAPL",
        parent_order_id="20",
        target_order_id="21",
        stop_order_id="22",
        parent_side="buy",
        entry_order_type="limit",
        quantity=100,
        target_price=12.0,
        stop_price=9.5,
    )
    registry.register(chain)

    assert registry.update_stop("20", 9.75) is True
    assert chain.stop_price == 9.75
    assert registry.update_stop("20", 9.4) is False
    assert chain.stop_price == 9.75


def test_order_registry_updates_child_order_statuses():
    registry = OrderRegistry()
    chain = OrderChainState(
        ticker="AAPL",
        parent_order_id="30",
        target_order_id="31",
        stop_order_id="32",
        parent_side="buy",
        entry_order_type="limit",
        quantity=100,
        target_price=12.0,
        stop_price=9.5,
    )
    registry.register(chain)

    assert registry.update_order_status("31", "cancelled") is True
    assert registry.update_order_status("32", "pending") is True
    assert chain.target_status == "cancelled"
    assert chain.stop_status == "pending"
