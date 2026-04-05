"""Tests for the SignalDetector feature computation."""

from datetime import datetime

from app.broker.interface import OrderBook, OrderBookLevel, Quote
from app.data.tick_buffer import MarketSnapshot, TickBuffer
from app.engine.signal_detector import SignalDetector, SignalType


def _make_snapshot(
    ticker: str = "TEST",
    bid: float = 5.0,
    ask: float = 5.02,
    volume: int = 1_000_000,
    bid_sizes: list[int] | None = None,
    ask_sizes: list[int] | None = None,
) -> MarketSnapshot:
    """Helper to create a MarketSnapshot with controllable parameters."""
    quote = Quote(
        ticker=ticker, bid=bid, ask=ask, last=(bid + ask) / 2,
        volume=volume, timestamp=datetime.now(),
    )
    if bid_sizes is None:
        bid_sizes = [500, 400, 300, 200, 100, 90, 80, 70, 60, 50]
    if ask_sizes is None:
        ask_sizes = [500, 400, 300, 200, 100, 90, 80, 70, 60, 50]

    bids = [OrderBookLevel(price=bid - i * 0.01, size=bid_sizes[i]) for i in range(len(bid_sizes))]
    asks = [OrderBookLevel(price=ask + i * 0.01, size=ask_sizes[i]) for i in range(len(ask_sizes))]
    order_book = OrderBook(ticker=ticker, bids=bids, asks=asks, timestamp=datetime.now())
    return MarketSnapshot(quote=quote, order_book=order_book, timestamp=datetime.now())


def _fill_buffer(
    buf: TickBuffer, ticker: str = "TEST", count: int = 15, **kwargs
) -> None:
    """Push `count` identical snapshots into the buffer."""
    for _ in range(count):
        buf.push(ticker, _make_snapshot(ticker=ticker, **kwargs))


def test_returns_none_with_insufficient_history():
    buf = TickBuffer()
    buf.push("TEST", _make_snapshot())
    detector = SignalDetector(buf, minimum_history=10)
    assert detector.compute_signal("TEST") is None


def test_compute_signal_returns_feature_vector():
    buf = TickBuffer()
    _fill_buffer(buf, count=15)
    detector = SignalDetector(buf)
    result = detector.compute_signal("TEST")
    assert result is not None
    assert result.ticker == "TEST"
    assert 0.0 <= result.composite_score <= 1.0
    assert result.signal_type in (SignalType.BREAKOUT, SignalType.FALSE_BREAKOUT)


def test_liquidity_imbalance_bid_heavy():
    """When bids >> asks, liquidity imbalance should be high."""
    snap = _make_snapshot(
        bid_sizes=[5000] * 10,
        ask_sizes=[100] * 10,
    )
    score = SignalDetector._liquidity_imbalance(snap)
    assert score > 0.7


def test_liquidity_imbalance_balanced():
    """Equal bid and ask sizes → ~0.5."""
    snap = _make_snapshot(
        bid_sizes=[1000] * 10,
        ask_sizes=[1000] * 10,
    )
    score = SignalDetector._liquidity_imbalance(snap)
    assert 0.45 <= score <= 0.55


def test_spread_compression_tight():
    """Current spread tighter than historical → high score."""
    buf = TickBuffer()
    # History with wide spreads
    for _ in range(10):
        buf.push("TEST", _make_snapshot(bid=4.90, ask=5.10))  # spread = 0.20
    # Latest with tight spread
    latest = _make_snapshot(bid=5.00, ask=5.02)  # spread = 0.02
    history = buf.get_history("TEST") + [latest]
    score = SignalDetector._spread_compression(latest, history)
    assert score > 0.7


def test_bid_stacking_concentrated():
    """Top-3 bid levels dominating total → high score."""
    snap = _make_snapshot(
        bid_sizes=[5000, 4000, 3000, 100, 100, 100, 100, 100, 100, 100],
    )
    score = SignalDetector._bid_stacking(snap)
    assert score > 0.7


def test_volume_acceleration_spike():
    """Current volume >> average → high score."""
    buf = TickBuffer()
    _fill_buffer(buf, count=10, volume=500_000)
    latest = _make_snapshot(volume=2_000_000)
    history = buf.get_history("TEST") + [latest]
    score = SignalDetector._volume_acceleration(latest, history)
    assert score > 0.5


def test_all_features_bounded():
    """All features should be in [0, 1] range."""
    buf = TickBuffer()
    _fill_buffer(buf, count=15)
    detector = SignalDetector(buf)
    result = detector.compute_signal("TEST")
    assert result is not None
    for val in [
        result.liquidity_imbalance,
        result.spread_compression,
        result.bid_stacking,
        result.volume_acceleration,
        result.order_aggression,
        result.composite_score,
    ]:
        assert 0.0 <= val <= 1.0, f"Feature value {val} out of bounds"


def test_threshold_breakout():
    """Verify that score >= 0.65 produces BREAKOUT."""
    buf = TickBuffer()
    # Build rising pressure into the recent history so the balanced formula
    # sees both strong breakout characteristics and improving tape quality.
    for _ in range(10):
        buf.push(
            "BULL",
            _make_snapshot(
                ticker="BULL",
                bid=4.98,
                ask=5.03,
                volume=700_000,
                bid_sizes=[2600, 2400, 2200, 2000, 1800, 1600, 1400, 1200, 1000, 900],
                ask_sizes=[2400, 2300, 2200, 2100, 2000, 1900, 1800, 1700, 1600, 1500],
            ),
        )
    for _ in range(5):
        buf.push(
            "BULL",
            _make_snapshot(
                ticker="BULL",
                bid=5.00,
                ask=5.01,  # very tight spread
                volume=3_000_000,
                bid_sizes=[8000, 7200, 6500, 5400, 4600, 3800, 3000, 2400, 1900, 1500],
                ask_sizes=[1800, 1700, 1600, 1500, 1400, 1300, 1200, 1100, 1000, 900],
            ),
        )
    detector = SignalDetector(buf)
    result = detector.compute_signal("BULL")
    assert result is not None
    # This crafted scenario should produce a high score
    assert result.composite_score > 0.5
    assert result.signal_type == SignalType.BREAKOUT
