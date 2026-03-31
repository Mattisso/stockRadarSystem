"""Tests for IBKR bracket order construction."""

import pytest

from app.broker.bracket_builder import build_bracket_orders
from app.broker.interface import OrderSide, OrderType


def test_build_limit_bracket_orders():
    orders = build_bracket_orders(
        order_id=100,
        side=OrderSide.BUY,
        quantity=50,
        order_type=OrderType.LIMIT,
        entry_price=3.21,
        target_price=3.6,
        stop_price=3.0,
    )

    assert orders.parent.orderId == 100
    assert orders.target.orderId == 101
    assert orders.stop.orderId == 102
    assert orders.target.parentId == 100
    assert orders.stop.parentId == 100
    assert orders.parent.transmit is False
    assert orders.target.transmit is False
    assert orders.stop.transmit is True


def test_build_market_bracket_orders():
    orders = build_bracket_orders(
        order_id=200,
        side=OrderSide.BUY,
        quantity=10,
        order_type=OrderType.MARKET,
        entry_price=None,
        target_price=11.0,
        stop_price=9.5,
    )

    assert orders.parent.orderType == "MKT"
    assert orders.target.orderType == "LMT"
    assert orders.stop.orderType == "STP"


def test_build_limit_bracket_requires_entry_price():
    with pytest.raises(ValueError):
        build_bracket_orders(
            order_id=1,
            side=OrderSide.BUY,
            quantity=1,
            order_type=OrderType.LIMIT,
            entry_price=None,
            target_price=2.0,
            stop_price=1.0,
        )
