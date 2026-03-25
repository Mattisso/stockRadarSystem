"""Tests for order book building from broker depth rows."""

from types import SimpleNamespace

from app.engine.order_book_builder import build_order_book_from_ticker


def test_build_order_book_state_from_depth_rows():
    ticker = SimpleNamespace(
        domBids=[SimpleNamespace(price=5.0, size=100), SimpleNamespace(price=4.99, size=200)],
        domAsks=[SimpleNamespace(price=5.02, size=150), SimpleNamespace(price=5.03, size=250)],
    )

    book = build_order_book_from_ticker("AAPL", ticker)

    assert book.ticker == "AAPL"
    assert len(book.bids) == 2
    assert len(book.asks) == 2
    assert book.bids[0].price == 5.0
    assert book.asks[0].price == 5.02


def test_handle_empty_depth_safely():
    ticker = SimpleNamespace(domBids=[], domAsks=[])
    book = build_order_book_from_ticker("AAPL", ticker)
    assert book.bids == []
    assert book.asks == []


def test_handle_malformed_depth_rows_safely():
    ticker = SimpleNamespace(
        domBids=[SimpleNamespace(price=5.0, size=100), SimpleNamespace(price=None, size=50)],
        domAsks=[SimpleNamespace(price="bad", size=100), SimpleNamespace(price=5.02, size=150)],
    )
    book = build_order_book_from_ticker("AAPL", ticker)
    assert len(book.bids) == 1
    assert len(book.asks) == 1
    assert book.bids[0].price == 5.0
    assert book.asks[0].price == 5.02
