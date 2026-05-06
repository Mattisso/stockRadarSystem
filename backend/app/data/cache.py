"""Cache abstraction — Redis or in-memory fallback for real-time data."""

from abc import ABC, abstractmethod
from datetime import datetime

from app.broker.interface import OrderBook, Quote

RUNTIME_SNAPSHOT_KEY = "stockradar:runtime:polygon_snapshot"


class CacheInterface(ABC):
    """Unified cache interface for L1/L2 market data."""

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def is_healthy(self) -> bool: ...

    # L1
    @abstractmethod
    async def set_l1(self, ticker: str, quote: Quote) -> None: ...

    @abstractmethod
    async def get_l1(self, ticker: str) -> Quote | None: ...

    # L2
    @abstractmethod
    async def set_l2(self, ticker: str, book: OrderBook) -> None: ...

    @abstractmethod
    async def get_l2(self, ticker: str) -> OrderBook | None: ...

    # Cross-pod runtime snapshot (worker writes, web reads — see
    # RuntimeSnapshotPublisher). Carries polygon WS session + event-bus +
    # persistence telemetry so the web pod can serve runtime KPIs without
    # owning the in-process objects.
    @abstractmethod
    async def set_runtime_snapshot(self, payload: dict, ttl_seconds: int) -> None: ...

    @abstractmethod
    async def get_runtime_snapshot(self) -> dict | None: ...


class InMemoryCache(CacheInterface):
    """Dict-based fallback when Redis is not configured."""

    def __init__(self, ttl: int = 10) -> None:
        self._ttl = ttl
        self._l1: dict[str, tuple[Quote, float]] = {}
        self._l2: dict[str, tuple[OrderBook, float]] = {}
        self._runtime_snapshot: tuple[dict, float] | None = None

    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        self._l1.clear()
        self._l2.clear()
        self._runtime_snapshot = None

    async def is_healthy(self) -> bool:
        return True

    async def set_l1(self, ticker: str, quote: Quote) -> None:
        self._l1[ticker] = (quote, datetime.now().timestamp())

    async def get_l1(self, ticker: str) -> Quote | None:
        entry = self._l1.get(ticker)
        if entry is None:
            return None
        quote, ts = entry
        if datetime.now().timestamp() - ts > self._ttl:
            del self._l1[ticker]
            return None
        return quote

    async def set_l2(self, ticker: str, book: OrderBook) -> None:
        self._l2[ticker] = (book, datetime.now().timestamp())

    async def get_l2(self, ticker: str) -> OrderBook | None:
        entry = self._l2.get(ticker)
        if entry is None:
            return None
        book, ts = entry
        if datetime.now().timestamp() - ts > self._ttl:
            del self._l2[ticker]
            return None
        return book

    async def set_runtime_snapshot(self, payload: dict, ttl_seconds: int) -> None:
        self._runtime_snapshot = (payload, datetime.now().timestamp() + max(1, ttl_seconds))

    async def get_runtime_snapshot(self) -> dict | None:
        if self._runtime_snapshot is None:
            return None
        payload, expires_at = self._runtime_snapshot
        if datetime.now().timestamp() > expires_at:
            self._runtime_snapshot = None
            return None
        return payload
