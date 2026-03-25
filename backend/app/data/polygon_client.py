"""Polygon.io L1 data ingestion — WebSocket streaming or REST polling."""

import asyncio
from datetime import datetime, timezone

import httpx
from websockets.exceptions import ConnectionClosed

from app.broker.interface import Quote
from app.core.logging import get_logger
from app.data.cache import CacheInterface
from app.data.polygon_connection import PolygonConnectionManager
from app.data.polygon_parser import PolygonMessageParser

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
        subscription_batch_size: int = 500,
        dev_max_symbols: int = 3,
        parser: PolygonMessageParser | None = None,
        connection_manager: PolygonConnectionManager | None = None,
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
        self._dev_max_symbols = max(1, dev_max_symbols)
        self._parser = parser or PolygonMessageParser()
        self._connection_manager = connection_manager or PolygonConnectionManager(
            api_key=api_key,
            ws_url=ws_url,
            subscription_batch_size=subscription_batch_size,
        )
        self._task: asyncio.Task | None = None
        self._running = False
        self._ws_quote_count = 0
        self._last_ws_quote_log_at = 0.0

    async def start(self) -> None:
        """Launch the background ingestion task."""
        self._running = True
        if self._mode == "websocket":
            self._task = asyncio.create_task(self._ws_loop())
        elif self._mode in {"dev", "sandbox"}:
            self._task = asyncio.create_task(self._dev_poll_loop())
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
        if self._mode in {"dev", "sandbox"}:
            log.info(
                "polygon.subscriptions_updated",
                count=len(symbols),
                active_count=min(len(symbols), self._dev_max_symbols),
                mode=self._mode,
            )
        else:
            log.info("polygon.subscriptions_updated", count=len(symbols))

    # ── WebSocket Mode (paid) ────────────────────────────────────────

    async def _ws_loop(self) -> None:
        """Connect to Polygon WebSocket and stream quotes."""
        delay = 1.0
        while self._running:
            ws_quote_count_before_session = self._ws_quote_count
            try:
                async with self._connection_manager.open() as ws:
                    await self._connection_manager.subscribe(ws, self._symbols)
                    delay = 1.0  # Reset backoff on success
                    async for raw in ws:
                        if not self._running:
                            break
                        await self._handle_ws_payload(raw)
                    log.info(
                        "polygon.ws_loop_ended",
                        quotes_received=self._ws_quote_count - ws_quote_count_before_session,
                    )

            except asyncio.CancelledError:
                break
            except ConnectionClosed as exc:
                log.warning(
                    "polygon.ws_closed",
                    code=exc.code,
                    reason=exc.reason,
                    quotes_received=self._ws_quote_count - ws_quote_count_before_session,
                    delay=delay,
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, self._reconnect_max_delay)
            except Exception:
                log.exception(
                    "polygon.ws_error",
                    delay=delay,
                    quotes_received=self._ws_quote_count - ws_quote_count_before_session,
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, self._reconnect_max_delay)

    async def _handle_ws_payload(self, payload: str | bytes | dict | list[dict]) -> None:
        """Parse and dispatch all quotes found in a WebSocket payload."""
        quotes = self._parser.parse_messages(payload)
        if not quotes:
            return

        self._ws_quote_count += len(quotes)
        loop = asyncio.get_running_loop()
        now = loop.time()
        if now - self._last_ws_quote_log_at >= 10:
            self._last_ws_quote_log_at = now
            log.info("polygon.ws_quotes_received", total=self._ws_quote_count, batch_size=len(quotes))

        for quote in quotes:
            await self._dispatch(quote)

    async def _handle_ws_message(self, msg: dict) -> None:
        """Parse a Polygon WebSocket quote message."""
        quote = self._parser.parse_message(msg)
        if quote is not None:
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
        if not self._symbols:
            return

        resp = await client.get(
            f"{self._rest_url}/v3/snapshot",
            params={
                "ticker.any_of": ",".join(self._symbols[:500]),
                "apiKey": self._api_key,
            },
        )
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

    # ── Dev / Sandbox Mode ──────────────────────────────────────────

    async def _dev_poll_loop(self) -> None:
        """Poll a lightweight previous-day endpoint for local development."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            while self._running:
                try:
                    await self._dev_poll(client)
                except asyncio.CancelledError:
                    break
                except Exception:
                    log.exception("polygon.dev_poll_error")
                await asyncio.sleep(self._rest_poll_interval)

    async def _dev_poll(self, client: httpx.AsyncClient) -> None:
        """Fetch previous-day aggregates per symbol for dev/sandbox mode."""
        if not self._symbols:
            return

        active_symbols = self._symbols[: self._dev_max_symbols]
        log.info("polygon.dev_poll_cycle", symbols=len(active_symbols), total_symbols=len(self._symbols))

        for symbol in active_symbols:
            resp = await client.get(
                f"{self._rest_url}/v2/aggs/ticker/{symbol}/prev",
                params={
                    "adjusted": "true",
                    "apiKey": self._api_key,
                },
            )
            if resp.status_code != 200:
                log.warning("polygon.dev_error", status=resp.status_code, symbol=symbol)
                continue

            data = resp.json()
            results = data.get("results", [])
            if not results:
                continue

            bar = results[0]
            timestamp = bar.get("t")
            quote = Quote(
                ticker=symbol,
                bid=bar.get("c", 0.0),
                ask=bar.get("c", 0.0),
                last=bar.get("c", 0.0),
                volume=bar.get("v", 0),
                timestamp=(
                    datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
                    if timestamp is not None
                    else datetime.now(tz=timezone.utc)
                ),
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
                pass  # Drop the new quote rather than blocking the reader
