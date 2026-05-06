"""Redis-backed cache for real-time L1/L2 market data."""

import json
from datetime import datetime

from app.broker.interface import OrderBook, OrderBookLevel, Quote
from app.data.cache import RUNTIME_SNAPSHOT_KEY, CacheInterface


class RedisCache(CacheInterface):
    """Redis cache with JSON serialization and TTL expiration."""

    def __init__(self, url: str, l1_ttl: int = 10, l2_ttl: int = 10) -> None:
        self._url = url
        self._l1_ttl = l1_ttl
        self._l2_ttl = l2_ttl
        self._redis = None

    async def connect(self) -> None:
        import redis.asyncio as aioredis

        self._redis = aioredis.from_url(self._url, decode_responses=True)
        await self._redis.ping()

    async def disconnect(self) -> None:
        if self._redis:
            await self._redis.aclose()

    async def is_healthy(self) -> bool:
        if self._redis is None:
            return False
        try:
            await self._redis.ping()
            return True
        except Exception:
            return False

    # ── L1 ────────────────────────────────────────────────────────────

    async def set_l1(self, ticker: str, quote: Quote) -> None:
        data = json.dumps({
            "ticker": quote.ticker,
            "bid": quote.bid,
            "ask": quote.ask,
            "last": quote.last,
            "volume": quote.volume,
            "timestamp": quote.timestamp.isoformat(),
        })
        await self._redis.setex(f"l1:{ticker}", self._l1_ttl, data)

    async def get_l1(self, ticker: str) -> Quote | None:
        raw = await self._redis.get(f"l1:{ticker}")
        if raw is None:
            return None
        d = json.loads(raw)
        return Quote(
            ticker=d["ticker"],
            bid=d["bid"],
            ask=d["ask"],
            last=d["last"],
            volume=d["volume"],
            timestamp=datetime.fromisoformat(d["timestamp"]),
        )

    # ── L2 ────────────────────────────────────────────────────────────

    async def set_l2(self, ticker: str, book: OrderBook) -> None:
        data = json.dumps({
            "ticker": book.ticker,
            "bids": [{"price": l.price, "size": l.size, "order_count": l.order_count} for l in book.bids],
            "asks": [{"price": l.price, "size": l.size, "order_count": l.order_count} for l in book.asks],
            "timestamp": book.timestamp.isoformat(),
        })
        await self._redis.setex(f"l2:{ticker}", self._l2_ttl, data)

    async def get_l2(self, ticker: str) -> OrderBook | None:
        raw = await self._redis.get(f"l2:{ticker}")
        if raw is None:
            return None
        d = json.loads(raw)
        return OrderBook(
            ticker=d["ticker"],
            bids=[OrderBookLevel(price=l["price"], size=l["size"], order_count=l["order_count"]) for l in d["bids"]],
            asks=[OrderBookLevel(price=l["price"], size=l["size"], order_count=l["order_count"]) for l in d["asks"]],
            timestamp=datetime.fromisoformat(d["timestamp"]),
        )

    async def set_runtime_snapshot(self, payload: dict, ttl_seconds: int) -> None:
        await self._redis.setex(RUNTIME_SNAPSHOT_KEY, max(1, ttl_seconds), json.dumps(payload, default=str))

    async def get_runtime_snapshot(self) -> dict | None:
        raw = await self._redis.get(RUNTIME_SNAPSHOT_KEY)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None
