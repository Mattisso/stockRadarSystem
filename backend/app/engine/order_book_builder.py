"""Helpers for converting broker depth data into internal order book models."""

from datetime import datetime
from typing import Any

from app.broker.interface import OrderBook, OrderBookLevel


def _normalize_depth_rows(rows: list[Any] | None) -> list[OrderBookLevel]:
    levels: list[OrderBookLevel] = []
    for row in rows or []:
        price = getattr(row, "price", None)
        size = getattr(row, "size", None)
        if price is None or size is None:
            continue
        try:
            price_value = float(price)
            size_value = int(float(size))
        except (TypeError, ValueError):
            continue
        if price_value <= 0 or size_value < 0:
            continue
        levels.append(
            OrderBookLevel(
                price=price_value,
                size=size_value,
                order_count=int(getattr(row, "order_count", 1) or 1),
            )
        )
    return levels


def build_order_book_from_ticker(ticker: str, depth_ticker: Any) -> OrderBook:
    """Build an internal OrderBook from an IBKR depth ticker-like object."""
    return OrderBook(
        ticker=ticker,
        bids=_normalize_depth_rows(getattr(depth_ticker, "domBids", [])),
        asks=_normalize_depth_rows(getattr(depth_ticker, "domAsks", [])),
        timestamp=datetime.now(),
    )
