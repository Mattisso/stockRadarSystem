"""Helpers for building IBKR parent + child bracket orders."""

from dataclasses import dataclass

from ib_insync import LimitOrder, MarketOrder, Order, StopOrder

from app.broker.interface import OrderSide, OrderType


@dataclass
class BracketOrders:
    parent: Order
    target: Order
    stop: Order


def build_bracket_orders(
    *,
    order_id: int,
    side: OrderSide,
    quantity: int,
    order_type: OrderType,
    entry_price: float | None,
    target_price: float,
    stop_price: float,
) -> BracketOrders:
    """Create a standard IBKR bracket order chain."""
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    if target_price <= 0 or stop_price <= 0:
        raise ValueError("target and stop prices must be positive")

    parent_action = "BUY" if side == OrderSide.BUY else "SELL"
    child_action = "SELL" if side == OrderSide.BUY else "BUY"

    if order_type == OrderType.MARKET:
        parent = MarketOrder(parent_action, quantity)
    else:
        if entry_price is None:
            raise ValueError("entry_price required for LIMIT parent orders")
        parent = LimitOrder(parent_action, quantity, entry_price)

    parent.orderId = order_id
    parent.transmit = False

    target = LimitOrder(child_action, quantity, target_price)
    target.orderId = order_id + 1
    target.parentId = order_id
    target.transmit = False

    stop = StopOrder(child_action, quantity, stop_price)
    stop.orderId = order_id + 2
    stop.parentId = order_id
    stop.transmit = True

    return BracketOrders(parent=parent, target=target, stop=stop)
