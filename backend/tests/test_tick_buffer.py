"""Tests for the TickBuffer data pipeline."""

from datetime import datetime

from app.broker.interface import OrderBook, OrderBookLevel, Quote
from app.data.tick_buffer import MarketSnapshot, TickBuffer


def _make_snapshot(ticker: str = "TEST", bid: float = 5.0, ask: float = 5.02) -> MarketSnapshot:
    """Helper to create a MarketSnapshot with realistic data."""
    quote = Quote(
        ticker=ticker, bid=bid, ask=ask, last=(bid + ask) / 2,
        volume=1_000_000, timestamp=datetime.now(),
    )
    order_book = OrderBook(
        ticker=ticker,
        bids=[OrderBookLevel(price=bid - i * 0.01, size=100 * (i + 1)) for i in range(5)],
        asks=[OrderBookLevel(price=ask + i * 0.01, size=100 * (i + 1)) for i in range(5)],
        timestamp=datetime.now(),
    )
    return MarketSnapshot(quote=quote, order_book=order_book, timestamp=datetime.now())


def test_push_and_get_latest():
    buf = TickBuffer(maxlen=10)
    snap = _make_snapshot()
    buf.push("TEST", snap)
    assert buf.get_latest("TEST") is snap


def test_get_latest_empty():
    buf = TickBuffer()
    assert buf.get_latest("MISSING") is None


def test_get_history_returns_ordered():
    buf = TickBuffer(maxlen=10)
    snaps = [_make_snapshot(bid=5.0 + i * 0.01) for i in range(5)]
    for s in snaps:
        buf.push("TEST", s)
    history = buf.get_history("TEST")
    assert len(history) == 5
    assert history[0] is snaps[0]
    assert history[-1] is snaps[-1]


def test_get_history_empty():
    buf = TickBuffer()
    assert buf.get_history("MISSING") == []


def test_eviction_at_capacity():
    buf = TickBuffer(maxlen=3)
    snaps = [_make_snapshot(bid=5.0 + i * 0.01) for i in range(5)]
    for s in snaps:
        buf.push("TEST", s)
    history = buf.get_history("TEST")
    assert len(history) == 3
    # Oldest two should be evicted
    assert history[0] is snaps[2]
    assert history[-1] is snaps[4]


def test_has_minimum_history():
    buf = TickBuffer(maxlen=20)
    assert buf.has_minimum_history("TEST", minimum=1) is False
    for i in range(5):
        buf.push("TEST", _make_snapshot())
    assert buf.has_minimum_history("TEST", minimum=5) is True
    assert buf.has_minimum_history("TEST", minimum=6) is False


def test_multiple_tickers():
    buf = TickBuffer(maxlen=10)
    buf.push("AAA", _make_snapshot(ticker="AAA"))
    buf.push("BBB", _make_snapshot(ticker="BBB"))
    assert len(buf.get_history("AAA")) == 1
    assert len(buf.get_history("BBB")) == 1
    assert set(buf.tickers) == {"AAA", "BBB"}
