"""Polygon.io L1 data ingestion — WebSocket streaming or REST polling."""

import asyncio
from datetime import datetime, timezone
from math import ceil

import httpx
from websockets.exceptions import ConnectionClosed

from app.broker.interface import Quote
from app.core.logging import get_logger
from app.core.metrics import POLYGON_RECONNECT_TOTAL, POLYGON_SESSION_CONNECTED
from app.data.cache import CacheInterface
from app.data.polygon_connection import PolygonConnectionManager
from app.data.polygon_parser import PolygonMessageParser

log = get_logger(__name__)


class PolygonClient:
    """Connects to Polygon for real-time L1 quotes (price, volume, timestamp).

    Supports two modes:
    - "websocket": streams via wss://socket.massive.com/stocks (paid plan)
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
        ws_url: str = "wss://socket.massive.com/stocks",
        rest_url: str = "https://api.polygon.io",
        rest_poll_interval: float = 1.0,
        reconnect_max_delay: float = 30.0,
        subscription_batch_size: int = 500,
        dev_max_symbols: int = 3,
        include_trade_wildcard: bool = False,
        parser: PolygonMessageParser | None = None,
        connection_manager: PolygonConnectionManager | None = None,
    ) -> None:
        self._api_key = api_key
        self._mode = mode
        self._symbols = symbols or []
        self._subscription_sources: dict[str, list[str]] = {"watchlist": list(self._symbols)}
        self._cache = cache
        self._queue = queue
        self._ws_url = ws_url
        self._rest_url = rest_url
        self._rest_poll_interval = rest_poll_interval
        self._reconnect_max_delay = reconnect_max_delay
        self._dev_max_symbols = max(1, dev_max_symbols)
        self._include_trade_wildcard = include_trade_wildcard
        self._parser = parser or PolygonMessageParser()
        self._connection_manager = connection_manager or PolygonConnectionManager(
            api_key=api_key,
            ws_url=ws_url,
            subscription_batch_size=subscription_batch_size,
        )
        self._task: asyncio.Task | None = None
        self._running = False
        self._session_connected = False
        self._reconnect_count = 0
        self._ws_quote_count = 0
        self._last_ws_quote_log_at = 0.0

    async def start(self) -> None:
        """Launch the background ingestion task."""
        self._running = True
        POLYGON_SESSION_CONNECTED.labels(mode=self._mode).set(0)
        if self._mode == "websocket":
            self._task = asyncio.create_task(self._ws_loop())
        elif self._mode in {"dev", "sandbox"}:
            self._task = asyncio.create_task(self._dev_poll_loop())
        else:
            self._task = asyncio.create_task(self._rest_poll_loop())
        log.info("polygon.started", mode=self._mode, symbols=len(self.current_symbols()))

    async def stop(self) -> None:
        """Gracefully shutdown the ingestion task."""
        self._running = False
        self._session_connected = False
        POLYGON_SESSION_CONNECTED.labels(mode=self._mode).set(0)
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        log.info("polygon.stopped")

    def update_subscriptions(self, symbols: list[str], *, source: str = "watchlist") -> None:
        """Update the list of symbols to track."""
        self._subscription_sources[source] = list(symbols)
        self._symbols = self.current_symbols()
        if self._mode in {"dev", "sandbox"}:
            log.info(
                "polygon.subscriptions_updated",
                count=len(self._symbols),
                active_count=min(len(self._symbols), self._dev_max_symbols),
                mode=self._mode,
                source=source,
            )
        else:
            log.info("polygon.subscriptions_updated", count=len(self._symbols), source=source)

    def current_symbols(self) -> list[str]:
        seen: set[str] = set()
        symbols: list[str] = []
        for source_symbols in self._subscription_sources.values():
            for symbol in source_symbols:
                if symbol in seen:
                    continue
                seen.add(symbol)
                symbols.append(symbol)
        return symbols

    def session_snapshot(self) -> dict:
        return {
            "mode": self._mode,
            "connected": self._session_connected,
            "reconnect_count": self._reconnect_count,
            "subscription_count": len(self.current_symbols()),
            "include_trade_wildcard": self._include_trade_wildcard,
        }

    async def load_reference_universe(
        self,
        *,
        max_price: float,
        min_price: float,
        min_volume: int,
        exchange: str = "XNAS",
    ) -> list[Quote]:
        """Build a filtered equity universe from Polygon reference + snapshot REST APIs."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            tickers = await self._fetch_reference_tickers(client, exchange=exchange)
            if not tickers:
                return []
            return await self._fetch_snapshot_universe(
                client,
                tickers=tickers,
                max_price=max_price,
                min_price=min_price,
                min_volume=min_volume,
            )

    # ── WebSocket Mode (paid) ────────────────────────────────────────

    async def _ws_loop(self) -> None:
        """Connect to Polygon WebSocket and stream quotes."""
        delay = 1.0
        while self._running:
            ws_quote_count_before_session = self._ws_quote_count
            try:
                async with self._connection_manager.open() as ws:
                    self._session_connected = True
                    POLYGON_SESSION_CONNECTED.labels(mode=self._mode).set(1)
                    await self._connection_manager.subscribe(
                        ws,
                        self.current_symbols(),
                        include_trades=self._include_trade_wildcard,
                    )
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
                self._session_connected = False
                POLYGON_SESSION_CONNECTED.labels(mode=self._mode).set(0)
                self._reconnect_count += 1
                POLYGON_RECONNECT_TOTAL.labels(mode=self._mode).inc()
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
                self._session_connected = False
                POLYGON_SESSION_CONNECTED.labels(mode=self._mode).set(0)
                self._reconnect_count += 1
                POLYGON_RECONNECT_TOTAL.labels(mode=self._mode).inc()
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
        symbols = self.current_symbols()
        if not symbols:
            return

        resp = await client.get(
            f"{self._rest_url}/v3/snapshot",
            params={
                "ticker.any_of": ",".join(symbols[:500]),
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

    async def _fetch_reference_tickers(self, client: httpx.AsyncClient, *, exchange: str) -> list[str]:
        tickers: list[str] = []
        next_url = f"{self._rest_url}/v3/reference/tickers"
        params = {
            "market": "stocks",
            "exchange": exchange,
            "type": "CS",
            "active": "true",
            "limit": 1000,
            "sort": "ticker",
            "order": "asc",
            "apiKey": self._api_key,
        }

        while next_url:
            resp = await client.get(next_url, params=params)
            resp.raise_for_status()
            data = resp.json()
            tickers.extend(
                result["ticker"]
                for result in data.get("results", [])
                if result.get("ticker")
            )
            raw_next_url = data.get("next_url")
            if not raw_next_url:
                break
            next_url = raw_next_url
            params = {"apiKey": self._api_key}

        return tickers

    async def _fetch_snapshot_universe(
        self,
        client: httpx.AsyncClient,
        *,
        tickers: list[str],
        max_price: float,
        min_price: float,
        min_volume: int,
    ) -> list[Quote]:
        filtered: list[Quote] = []
        batch_size = 250
        batch_count = ceil(len(tickers) / batch_size)

        for batch_index in range(batch_count):
            batch = tickers[batch_index * batch_size : (batch_index + 1) * batch_size]
            resp = await client.get(
                f"{self._rest_url}/v3/snapshot",
                params={
                    "ticker.any_of": ",".join(batch),
                    "apiKey": self._api_key,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            for result in data.get("results", []):
                session = result.get("session", {})
                last = session.get("close") or 0.0
                volume = session.get("volume") or 0
                if last < min_price or last > max_price:
                    continue
                if volume < min_volume:
                    continue
                filtered.append(
                    Quote(
                        ticker=result.get("ticker", ""),
                        bid=last,
                        ask=last,
                        last=last,
                        volume=volume,
                        timestamp=datetime.now(tz=timezone.utc),
                    )
                )

        return filtered

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
        symbols = self.current_symbols()
        if not symbols:
            return

        active_symbols = symbols[: self._dev_max_symbols]
        log.info("polygon.dev_poll_cycle", symbols=len(active_symbols), total_symbols=len(symbols))

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
