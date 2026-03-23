"""Tests for SignalDetector with L1-only data (no order book)."""

import pytest

from app.broker.interface import Quote
from app.data.tick_buffer import MarketSnapshot, TickBuffer
from app.engine.signal_detector import SignalDetector


@pytest.fixture
def tick_buffer():
    return TickBuffer(maxlen=50)


@pytest.fixture
def detector(tick_buffer):
    return SignalDetector(tick_buffer, minimum_history=5)


def make_l1_snapshot(bid=3.47, ask=3.48, volume=100000):
    """Create a MarketSnapshot with only L1 data (no order book)."""
    from datetime import datetime

    return MarketSnapshot(
        quote=Quote(ticker="LCID", bid=bid, ask=ask, last=bid, volume=volume, timestamp=datetime.now()),
        order_book=None,
    )


def test_l1_only_features_return_neutral(detector, tick_buffer):
    """L2-dependent features should return neutral values when order_book is None."""
    for _ in range(10):
        tick_buffer.push("LCID", make_l1_snapshot())

    fv = detector.compute_signal("LCID")
    assert fv is not None
    # L2-dependent features return neutral
    assert fv.liquidity_imbalance == 0.5
    assert fv.bid_stacking == 0.0
    assert fv.order_aggression == 0.5


def test_l1_only_spread_compression_works(detector, tick_buffer):
    """Spread compression should work with L1 data only."""
    for _ in range(5):
        tick_buffer.push("LCID", make_l1_snapshot(bid=3.40, ask=3.50))
    for _ in range(5):
        tick_buffer.push("LCID", make_l1_snapshot(bid=3.47, ask=3.48))

    fv = detector.compute_signal("LCID")
    assert fv is not None
    assert fv.spread_compression > 0.5  # Tighter spread = higher score


def test_l1_only_volume_acceleration_works(detector, tick_buffer):
    """Volume acceleration should work with L1 data only."""
    for _ in range(5):
        tick_buffer.push("LCID", make_l1_snapshot(volume=50000))
    for _ in range(5):
        tick_buffer.push("LCID", make_l1_snapshot(volume=200000))

    fv = detector.compute_signal("LCID")
    assert fv is not None
    assert fv.volume_acceleration > 0.3  # Higher recent volume = higher score


def test_l1_only_produces_valid_composite(detector, tick_buffer):
    """Composite score should be valid even with L1-only data."""
    for _ in range(10):
        tick_buffer.push("LCID", make_l1_snapshot())

    fv = detector.compute_signal("LCID")
    assert fv is not None
    assert 0.0 <= fv.composite_score <= 1.0
