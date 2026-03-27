"""Tests for the L2 pattern engine."""

from datetime import datetime

from app.broker.interface import OrderBook, OrderBookLevel
from app.engine.l2_pattern_engine import L2PatternEngine, PatternType


def _book(
    ticker: str = "AAPL",
    bid_sizes: list[int] | None = None,
    ask_sizes: list[int] | None = None,
    bid_price: float = 5.00,
    ask_price: float = 5.02,
) -> OrderBook:
    bid_sizes = bid_sizes or [500, 400, 300, 200, 100]
    ask_sizes = ask_sizes or [500, 400, 300, 200, 100]

    bids = [OrderBookLevel(price=bid_price - i * 0.01, size=size) for i, size in enumerate(bid_sizes)]
    asks = [OrderBookLevel(price=ask_price + i * 0.01, size=size) for i, size in enumerate(ask_sizes)]
    return OrderBook(ticker=ticker, bids=bids, asks=asks, timestamp=datetime.now())


def test_analyze_returns_none_without_order_book():
    engine = L2PatternEngine()
    assert engine.analyze(None) is None


def test_detects_order_book_imbalance():
    engine = L2PatternEngine()
    signal = engine.analyze(_book(bid_sizes=[2000, 1500, 1200], ask_sizes=[100, 80, 60]))
    assert signal is not None
    assert signal.liquidity_imbalance > 0.8
    assert signal.confidence_score > 0.5


def test_detects_bid_stacking_pattern():
    engine = L2PatternEngine()
    signal = engine.analyze(_book(bid_sizes=[3000, 2500, 2000, 100, 50], ask_sizes=[400, 300, 200, 100, 50]))
    assert signal is not None
    assert signal.bid_stacking > 0.8
    assert signal.pattern_type in {PatternType.BID_STACKING, PatternType.MIXED}


def test_detects_spoofing_signal():
    engine = L2PatternEngine()
    signal = engine.analyze(_book(bid_sizes=[10000, 100, 80, 70, 60], ask_sizes=[100, 90, 80, 70, 60]))
    assert signal is not None
    assert signal.spoofing_score > 0.7


def test_detects_momentum_confirmation():
    engine = L2PatternEngine()
    signal = engine.analyze(_book(bid_sizes=[1500, 1200, 900], ask_sizes=[100, 80, 60], bid_price=5.00, ask_price=5.01))
    assert signal is not None
    assert signal.momentum_confirmation > 0.7


def test_mixed_pattern_when_scores_are_close():
    engine = L2PatternEngine()
    signal = engine.analyze(_book(bid_sizes=[900, 850, 800, 500, 400], ask_sizes=[250, 240, 230, 220, 210]))
    assert signal is not None
    assert signal.pattern_type in {PatternType.MIXED, PatternType.BID_STACKING, PatternType.IMBALANCE}
