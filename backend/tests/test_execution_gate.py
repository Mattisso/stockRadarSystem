"""Tests for the strict L2 execution gate."""

from datetime import datetime

from app.broker.interface import OrderBook, OrderBookLevel, Quote
from app.data.tick_buffer import MarketSnapshot
from app.engine.execution_gate import L2ExecutionGate


def _snapshot(
    bid: float = 9.99,
    ask: float = 10.0,
    bids: list[tuple[float, int]] | None = None,
    asks: list[tuple[float, int]] | None = None,
) -> MarketSnapshot:
    bids = bids or [(9.99, 250), (9.98, 220), (9.97, 180), (9.96, 60)]
    asks = asks or [(10.00, 90), (10.01, 80), (10.02, 70), (10.03, 60)]
    return MarketSnapshot(
        quote=Quote(
            ticker="AAPL",
            bid=bid,
            ask=ask,
            last=ask,
            volume=1_000_000,
            timestamp=datetime.now(),
        ),
        order_book=OrderBook(
            ticker="AAPL",
            bids=[OrderBookLevel(price=price, size=size) for price, size in bids],
            asks=[OrderBookLevel(price=price, size=size) for price, size in asks],
            timestamp=datetime.now(),
        ),
        timestamp=datetime.now(),
    )


def test_gate_accepts_balanced_supportive_order_book():
    gate = L2ExecutionGate()

    decision = gate.evaluate(_snapshot())

    assert decision.allowed is True
    assert decision.reason is None


def test_gate_rejects_when_spread_is_too_wide():
    gate = L2ExecutionGate()

    decision = gate.evaluate(_snapshot(bid=9.80, ask=10.0))

    assert decision.allowed is False
    assert decision.reason == "spread_too_wide"


def test_gate_rejects_weak_bid_stack():
    gate = L2ExecutionGate()

    decision = gate.evaluate(
        _snapshot(
            bids=[(9.99, 40), (9.98, 40), (9.97, 40), (9.96, 400)],
            asks=[(10.00, 70), (10.01, 60), (10.02, 50)],
        )
    )

    assert decision.allowed is False
    assert decision.reason == "weak_bid_stack"


def test_gate_rejects_heavy_seller_overhead():
    gate = L2ExecutionGate()

    decision = gate.evaluate(
        _snapshot(
            bids=[(9.99, 120), (9.98, 100), (9.97, 80)],
            asks=[(10.00, 220), (10.01, 210), (10.02, 200)],
        )
    )

    assert decision.allowed is False
    assert decision.reason == "seller_wall_overhead"


def test_gate_rejects_unstable_support():
    gate = L2ExecutionGate()

    decision = gate.evaluate(
        _snapshot(
            bids=[(9.99, 1000), (9.98, 50), (9.97, 50), (9.96, 50)],
            asks=[(10.00, 90), (10.01, 80), (10.02, 70), (10.03, 60)],
        )
    )

    assert decision.allowed is False
    assert decision.reason == "unstable_support"
