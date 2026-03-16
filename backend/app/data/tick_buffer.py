"""Ring buffer storing recent market snapshots per ticker."""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime

from app.broker.interface import OrderBook, Quote


@dataclass
class MarketSnapshot:
    """A single point-in-time market data snapshot."""

    quote: Quote
    order_book: OrderBook
    timestamp: datetime = field(default_factory=datetime.now)


class TickBuffer:
    """Per-ticker ring buffer of MarketSnapshots.

    Stores the most recent `maxlen` snapshots for each ticker,
    providing rolling history for signal feature computation.
    """

    def __init__(self, maxlen: int = 100) -> None:
        self._maxlen = maxlen
        self._buffers: dict[str, deque[MarketSnapshot]] = {}

    def push(self, ticker: str, snapshot: MarketSnapshot) -> None:
        """Append a snapshot, evicting the oldest if at capacity."""
        if ticker not in self._buffers:
            self._buffers[ticker] = deque(maxlen=self._maxlen)
        self._buffers[ticker].append(snapshot)

    def get_history(self, ticker: str) -> list[MarketSnapshot]:
        """Return all buffered snapshots for a ticker (oldest first)."""
        if ticker not in self._buffers:
            return []
        return list(self._buffers[ticker])

    def get_latest(self, ticker: str) -> MarketSnapshot | None:
        """Return the most recent snapshot, or None if empty."""
        buf = self._buffers.get(ticker)
        if not buf:
            return None
        return buf[-1]

    def has_minimum_history(self, ticker: str, minimum: int = 10) -> bool:
        """Check if enough snapshots exist for feature computation."""
        buf = self._buffers.get(ticker)
        return buf is not None and len(buf) >= minimum

    @property
    def tickers(self) -> list[str]:
        """Return all tickers with buffered data."""
        return list(self._buffers.keys())
