"""Polygon.io L1 data ingestion — WebSocket streaming or REST polling."""

import asyncio
import json
from datetime import datetime, timezone

import httpx
import websockets

from app.broker.interface import Quote
from app.core.logging import get_logger
from app.data.cache import CacheInterface

log = get_logger(__name__)


class PolygonClient:
    """Connects to Polygon for real-time L1 quotes (price, volume, timestamp).

    Supports two modes:
    - "websocket": streams via wss://socket.polygon.io/stocks (paid plan)
    - "rest": polls /v3/snapshot via REST API (free tier)

    Pushes parsed quotes to cache and an internal asyncio.Queue.
    """

    def __init__(
        self,
        api_key: str,
        mode: str = "rest",
        symbols: list[str] | None = None,
        cache: CacheInterface | None = None,
        queue: asyncio.Queue | None = None,
        ws_url: str = "wss://socket.polygon.io/stocks",
        rest_url: str = "https://api.polygon.io",
        rest_poll_interval: float = 1.0,
        reconnect_max_delay: float = 30.0,
    ) -> None:
        self._api_key = api_key
        self._mode = mode
        self._symbols = symbols or []
        self._cache = cache
        self._queue = queue
        self._ws_url = ws_url
        self._rest_url = rest_url
        self._rest_poll_interval = rest_poll_interval
        self._reconnect_max_delay = reconnect_max_delay
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        """Launch the background ingestion task."""
        self._running = True
        if self._mode == "websocket":
            self._task = asyncio.create_task(self._ws_loop())
        else:
            self._task = asyncio.create_task(self._rest_poll_loop())
        log.info("polygon.started", mode=self._mode, symbols=len(self._symbols))

    async def stop(self) -> None:
        """Gracefully shutdown the ingestion task."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        log.info("polygon.stopped")

    def update_subscriptions(self, symbols: list[str]) -> None:
        """Update the list of symbols to track."""
        self._symbols = symbols
        log.info("polygon.subscriptions_updated", count=len(symbols))

    # ── WebSocket Mode (paid) ────────────────────────────────────────

    async def _ws_loop(self) -> None:
        """Connect to Polygon WebSocket and stream quotes."""
        delay = 1.0
        while self._running:
            try:
                async with websockets.connect(f"{self._ws_url}") as ws:
                    # Authenticate
                    await ws.send(json.dumps({"action": "auth", "params": self._api_key}))
                    auth_resp = await ws.recv()
                    log.info("polygon.ws_auth", response=str(auth_resp)[:100])

                    # Subscribe to quotes for all symbols (Q.* = all, or Q.AAPL,Q.TSLA,...)
                    if self._symbols:
                        subs = ",".join(f"Q.{s}" for s in self._symbols)
                    else:
                        subs = "Q.*"
                    await ws.send(json.dumps({"action": "subscribe", "params": subs}))

                    delay = 1.0  # Reset backoff on success
                    async for raw in ws:
                        if not self._running:
                            break
                        messages = json.loads(raw)
                        if isinstance(messages, list):
                            for msg in messages:
                                await self._handle_ws_message(msg)
                        else:
                            await self._handle_ws_message(messages)

            except asyncio.CancelledError:
                break
            except Exception:
                log.exception("polygon.ws_error", delay=delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, self._reconnect_max_delay)

    async def _handle_ws_message(self, msg: dict) -> None:
        """Parse a Polygon WebSocket quote message."""
        ev = msg.get("ev")
        if ev != "Q":
            return

        quote = Quote(
            ticker=msg.get("sym", ""),
            bid=msg.get("bp", 0.0),
            ask=msg.get("ap", 0.0),
            last=msg.get("bp", 0.0),  # Polygon Q events don't have last; use bid
            volume=msg.get("z", 0),
            timestamp=datetime.fromtimestamp(msg.get("t", 0) / 1000, tz=timezone.utc),
        )
        await self._dispatch(quote)

    # ── REST Mode (free tier) ────────────────────────────────────────

    async def _rest_poll_loop(self) -> None:
        """Poll Polygon snapshot endpoint for all tickers."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            while self._running:
                try:
                    await self._rest_poll(client)
                except asyncio.CancelledError:
                    break
                except Exception:
                    log.exception("polygon.rest_poll_error")
                await asyncio.sleep(self._rest_poll_interval)

    async def _rest_poll(self, client: httpx.AsyncClient) -> None:
        """Fetch snapshot of all tickers in one call."""
        url = f"{self._rest_url}/v3/snapshot?ticker.any_of={','.join(self._symbols[:500])}&apiKey={self._api_key}"
        if not self._symbols:
            return

        resp = await client.get(url)
        if resp.status_code != 200:
            log.warning("polygon.rest_error", status=resp.status_code)
            return

        data = resp.json()
        for result in data.get("results", []):
            session = result.get("session", {})
            quote = Quote(
                ticker=result.get("ticker", ""),
                bid=session.get("close", 0.0),
                ask=session.get("close", 0.0),
                last=session.get("close", 0.0),
                volume=session.get("volume", 0),
                timestamp=datetime.now(tz=timezone.utc),
            )
            await self._dispatch(quote)

    # ── Dispatch ─────────────────────────────────────────────────────

    async def _dispatch(self, quote: Quote) -> None:
        """Push quote to cache and internal queue."""
        if self._cache:
            await self._cache.set_l1(quote.ticker, quote)

        if self._queue:
            try:
                self._queue.put_nowait(quote)
            except asyncio.QueueFull:
                pass  # Drop oldest — consumer will catch up
