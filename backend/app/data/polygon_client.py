"""Polygon.io L1 and aggregate ingestion helpers."""

import asyncio
from datetime import date, datetime, timezone
from math import ceil
from typing import Any

import httpx
from websockets.exceptions import ConnectionClosed

from app.broker.interface import Quote
from app.core.market_hours import is_regular_us_market_time
from app.core.logging import get_logger
from app.core.metrics import POLYGON_RECONNECT_TOTAL, POLYGON_SESSION_CONNECTED
from app.data.cache import CacheInterface
from app.data.polygon_aggregate_parser import PolygonAggregateParser
from app.data.polygon_aggregate_service import (
    PolygonAggregateService,
    PolygonDayAggregateRecord,
    PolygonMinuteAggregateRecord,
    PolygonSecondAggregateRecord,
)
from app.data.polygon_event_bus import PolygonEventBus
from app.data.polygon_event_models import PolygonAggregateEvent
from app.data.polygon_connection import PolygonConnectionManager
from app.data.polygon_parser import PolygonMessageParser
from app.data.subscription_registry import SubscriptionRegistry

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
        enable_quotes: bool = True,
        enable_aggregates: bool = False,
        db_session_factory=None,
        aggregate_event_bus: PolygonEventBus | None = None,
        parser: PolygonMessageParser | None = None,
        connection_manager: PolygonConnectionManager | None = None,
    ) -> None:
        self._api_key = api_key
        self._mode = mode
        self._symbols = symbols or []
        self._subscription_registry = SubscriptionRegistry(
            initial_sources={"watchlist": list(self._symbols)},
        )
        self._cache = cache
        self._queue = queue
        self._ws_url = ws_url
        self._rest_url = rest_url
        self._rest_poll_interval = rest_poll_interval
        self._reconnect_max_delay = reconnect_max_delay
        self._dev_max_symbols = max(1, dev_max_symbols)
        self._include_trade_wildcard = include_trade_wildcard
        self._enable_quotes = enable_quotes
        self._enable_aggregates = enable_aggregates
        self._db_session_factory = db_session_factory
        self._aggregate_event_bus = aggregate_event_bus
        self._parser = parser or PolygonMessageParser()
        self._aggregate_parser = PolygonAggregateParser()
        self._connection_manager = connection_manager or PolygonConnectionManager(
            api_key=api_key,
            ws_url=ws_url,
            subscription_batch_size=subscription_batch_size,
        )
        self._task: asyncio.Task | None = None
        self._running = False
        self._subscriptions_paused = False
        self._subscription_generation_id = self._subscription_registry.generation_id
        self._session_connected = False
        self._reconnect_count = 0
        self._consecutive_failures = 0
        self._ws_quote_count = 0
        self._last_ws_quote_log_at = 0.0
        self._aggregate_batch_count = 0
        self._persisted_minute_bar_count = 0
        self._persisted_second_bar_count = 0
        self._last_connected_at: datetime | None = None
        self._last_disconnected_at: datetime | None = None
        self._last_error_at: datetime | None = None
        self._last_error_type: str | None = None
        self._last_error_code: int | str | None = None
        self._last_error_reason: str | None = None
        self._last_quote_received_at: datetime | None = None
        self._last_aggregate_received_at: datetime | None = None
        self._last_aggregate_persisted_at: datetime | None = None
        self._last_minute_persisted_at: datetime | None = None
        self._last_second_persisted_at: datetime | None = None
        self._ws: Any = None
        self._ws_lock = asyncio.Lock()

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

    def update_subscriptions(
        self,
        symbols: list[str],
        *,
        source: str = "watchlist",
        sticky: bool | None = None,
    ) -> None:
        """Update the list of symbols to track."""
        previous_symbols = self.current_symbols()
        changed = self._subscription_registry.update_source(source, symbols, sticky=sticky)
        self._symbols = self.current_symbols()
        if changed:
            self._subscription_generation_id = self._subscription_registry.generation_id
        if self._mode in {"dev", "sandbox"}:
            log.info(
                "polygon.subscriptions_updated",
                count=len(self._symbols),
                active_count=min(len(self._symbols), self._dev_max_symbols),
                mode=self._mode,
                source=source,
                generation_id=self._subscription_generation_id,
                sticky_count=len(self.sticky_symbols()),
            )
        else:
            log.info(
                "polygon.subscriptions_updated",
                count=len(self._symbols),
                source=source,
                generation_id=self._subscription_generation_id,
                sticky_count=len(self.sticky_symbols()),
            )

        if self._running and self._mode == "websocket" and not self._subscriptions_paused:
            asyncio.create_task(self._resubscribe())

    async def pause_subscriptions(self) -> None:
        """Temporarily remove live symbol subscriptions while retaining the desired symbol set."""
        if self._subscriptions_paused:
            return
        self._subscriptions_paused = True
        async with self._ws_lock:
            if self._ws and self.current_symbols():
                try:
                    await self._connection_manager.unsubscribe(
                        self._ws,
                        self.current_symbols(),
                        channels=self._subscription_channels(),
                        include_trades=self._enable_quotes and self._include_trade_wildcard,
                    )
                except Exception:
                    log.exception("polygon.pause_subscriptions_error")
        log.info("polygon.subscriptions_paused", count=len(self.current_symbols()))

    async def resume_subscriptions(self) -> None:
        """Restore live symbol subscriptions after a paused period."""
        if not self._subscriptions_paused:
            return
        self._subscriptions_paused = False
        async with self._ws_lock:
            if self._ws and self.current_symbols():
                try:
                    await self._connection_manager.subscribe(
                        self._ws,
                        self.current_symbols(),
                        channels=self._subscription_channels(),
                        include_trades=self._enable_quotes and self._include_trade_wildcard,
                    )
                except Exception:
                    log.exception("polygon.resume_subscriptions_error")
        log.info("polygon.subscriptions_resumed", count=len(self.current_symbols()))

    async def _resubscribe(self) -> None:
        """Send new subscription commands to the active WebSocket."""
        async with self._ws_lock:
            if self._ws and not self._subscriptions_paused:
                try:
                    await self._connection_manager.subscribe(
                        self._ws,
                        self.current_symbols(),
                        include_trades=self._include_trade_wildcard,
                    )
                except Exception:
                    log.exception("polygon.resubscribe_error")

    def current_symbols(self) -> list[str]:
        return self._subscription_registry.current_symbols()

    def sticky_symbols(self) -> list[str]:
        return self._subscription_registry.sticky_symbols()

    def session_snapshot(self) -> dict:
        now = datetime.now(tz=timezone.utc)

        def _iso(value: datetime | None) -> str | None:
            return value.isoformat() if value is not None else None

        def _age_seconds(value: datetime | None) -> float | None:
            if value is None:
                return None
            return max((now - value).total_seconds(), 0.0)

        return {
            "mode": self._mode,
            "connected": self._session_connected,
            "subscriptions_paused": self._subscriptions_paused,
            "reconnect_count": self._reconnect_count,
            "consecutive_failures": self._consecutive_failures,
            "subscription_count": len(self.current_symbols()),
            "subscription_generation_id": self._subscription_generation_id,
            "sticky_subscription_count": len(self.sticky_symbols()),
            "subscription_sources": [
                {
                    "source": state.source,
                    "count": len(state.symbols),
                    "sticky": state.sticky,
                }
                for state in self._subscription_registry.source_states()
            ],
            "include_trade_wildcard": self._include_trade_wildcard,
            "quotes_enabled": self._enable_quotes,
            "aggregates_enabled": self._enable_aggregates,
            "channels": list(self._subscription_channels()),
            "last_connected_at": _iso(self._last_connected_at),
            "last_disconnected_at": _iso(self._last_disconnected_at),
            "last_error_at": _iso(self._last_error_at),
            "last_error_type": self._last_error_type,
            "last_error_code": self._last_error_code,
            "last_error_reason": self._last_error_reason,
            "last_quote_received_at": _iso(self._last_quote_received_at),
            "last_aggregate_received_at": _iso(self._last_aggregate_received_at),
            "last_aggregate_persisted_at": _iso(self._last_aggregate_persisted_at),
            "last_minute_persisted_at": _iso(self._last_minute_persisted_at),
            "last_second_persisted_at": _iso(self._last_second_persisted_at),
            "quote_age_seconds": _age_seconds(self._last_quote_received_at),
            "aggregate_age_seconds": _age_seconds(self._last_aggregate_received_at),
            "aggregate_persist_age_seconds": _age_seconds(self._last_aggregate_persisted_at),
            "minute_persist_age_seconds": _age_seconds(self._last_minute_persisted_at),
            "second_persist_age_seconds": _age_seconds(self._last_second_persisted_at),
            "quote_message_count": self._ws_quote_count,
            "aggregate_batch_count": self._aggregate_batch_count,
            "persisted_minute_bar_count": self._persisted_minute_bar_count,
            "persisted_second_bar_count": self._persisted_second_bar_count,
        }

    def record_aggregate_persisted(
        self,
        minute_count: int,
        second_count: int,
        persisted_at: datetime | None = None,
    ) -> None:
        persisted_ts = persisted_at or datetime.now(tz=timezone.utc)
        self._aggregate_batch_count += 1
        self._persisted_minute_bar_count += minute_count
        self._persisted_second_bar_count += second_count
        self._last_aggregate_persisted_at = persisted_ts
        if minute_count:
            self._last_minute_persisted_at = persisted_ts
        if second_count:
            self._last_second_persisted_at = persisted_ts

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

    async def fetch_grouped_day_aggregates(self, trade_date: date) -> list[PolygonDayAggregateRecord]:
        """Fetch grouped daily aggregates for all symbols for one trade date."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(
                f"{self._rest_url}/v2/aggs/grouped/locale/us/market/stocks/{trade_date.isoformat()}",
                params={"adjusted": "true", "apiKey": self._api_key},
            )
            resp.raise_for_status()
            data = resp.json()
            records: list[PolygonDayAggregateRecord] = []
            for result in data.get("results", []):
                ticker = result.get("T")
                if not ticker:
                    continue
                records.append(
                    PolygonDayAggregateRecord(
                        ticker=ticker,
                        trade_date=trade_date,
                        open=result.get("o", 0.0) or 0.0,
                        high=result.get("h", 0.0) or 0.0,
                        low=result.get("l", 0.0) or 0.0,
                        close=result.get("c", 0.0) or 0.0,
                        volume=result.get("v", 0) or 0,
                        vwap=result.get("vw"),
                        transactions=result.get("n"),
                        source_ts=(
                            datetime.fromtimestamp(result["t"] / 1000, tz=timezone.utc)
                            if result.get("t") is not None
                            else None
                        ),
                    )
                )
            return records

    async def fetch_minute_aggregates_for_ticker(
        self,
        ticker: str,
        *,
        trade_date: date,
    ) -> list[PolygonMinuteAggregateRecord]:
        """Fetch 1-minute aggregates for a single symbol for one trade date."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(
                f"{self._rest_url}/v2/aggs/ticker/{ticker}/range/1/minute/{trade_date.isoformat()}/{trade_date.isoformat()}",
                params={
                    "adjusted": "true",
                    "sort": "asc",
                    "limit": 50000,
                    "apiKey": self._api_key,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            records: list[PolygonMinuteAggregateRecord] = []
            for result in data.get("results", []):
                timestamp = result.get("t")
                if timestamp is None:
                    continue
                minute_ts = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
                if not is_regular_us_market_time(minute_ts):
                    continue
                records.append(
                    PolygonMinuteAggregateRecord(
                        ticker=ticker,
                        minute_ts=minute_ts,
                        open=result.get("o", 0.0) or 0.0,
                        high=result.get("h", 0.0) or 0.0,
                        low=result.get("l", 0.0) or 0.0,
                        close=result.get("c", 0.0) or 0.0,
                        volume=result.get("v", 0) or 0,
                        vwap=result.get("vw"),
                        transactions=result.get("n"),
                    )
                )
            return records

    # ── WebSocket Mode (paid) ────────────────────────────────────────

    async def _ws_loop(self) -> None:
        """Connect to Polygon WebSocket and stream quotes."""
        delay = 1.0
        while self._running:
            ws_quote_count_before_session = self._ws_quote_count
            try:
                async with self._connection_manager.open() as ws:
                    self._ws = ws
                    self._session_connected = True
                    self._consecutive_failures = 0
                    self._last_connected_at = datetime.now(tz=timezone.utc)
                    POLYGON_SESSION_CONNECTED.labels(mode=self._mode).set(1)
                    if not self._subscriptions_paused:
                        await self._connection_manager.subscribe(
                            ws,
                            self.current_symbols(),
                            channels=self._subscription_channels(),
                            include_trades=self._enable_quotes and self._include_trade_wildcard,
                        )
                    else:
                        log.info("polygon.ws_subscription_skipped", reason="subscriptions_paused")
                    delay = 1.0  # Reset backoff on success
                    async for raw in ws:
                        if not self._running:
                            break
                        await self._handle_ws_payload(raw)
                log.info(
                    "polygon.ws_loop_ended",
                    quotes_received=self._ws_quote_count - ws_quote_count_before_session,
                )
                self._ws = None

            except asyncio.CancelledError:
                self._ws = None
                break
            except ConnectionClosed as exc:
                self._ws = None
                self._session_connected = False
                self._consecutive_failures += 1
                self._last_disconnected_at = datetime.now(tz=timezone.utc)
                self._last_error_at = self._last_disconnected_at
                self._last_error_type = "connection_closed"
                self._last_error_code = exc.code
                self._last_error_reason = exc.reason or None
                POLYGON_SESSION_CONNECTED.labels(mode=self._mode).set(0)
                self._reconnect_count += 1
                POLYGON_RECONNECT_TOTAL.labels(mode=self._mode).inc()
                log.warning(
                    "polygon.ws_closed",
                    code=exc.code,
                    reason=exc.reason,
                    quotes_received=self._ws_quote_count - ws_quote_count_before_session,
                    consecutive_failures=self._consecutive_failures,
                    delay=delay,
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, self._reconnect_max_delay)
            except Exception:
                self._ws = None
                self._session_connected = False
                self._consecutive_failures += 1
                self._last_disconnected_at = datetime.now(tz=timezone.utc)
                self._last_error_at = self._last_disconnected_at
                self._last_error_type = "exception"
                self._last_error_code = None
                self._last_error_reason = None
                POLYGON_SESSION_CONNECTED.labels(mode=self._mode).set(0)
                self._reconnect_count += 1
                POLYGON_RECONNECT_TOTAL.labels(mode=self._mode).inc()
                log.exception(
                    "polygon.ws_error",
                    delay=delay,
                    quotes_received=self._ws_quote_count - ws_quote_count_before_session,
                    consecutive_failures=self._consecutive_failures,
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, self._reconnect_max_delay)

    async def _handle_ws_payload(self, payload: str | bytes | dict | list[dict]) -> None:
        """Parse and dispatch all market-data events found in a WebSocket payload."""
        if self._enable_quotes:
            quotes = self._parser.parse_messages(payload)
            if quotes:
                self._ws_quote_count += len(quotes)
                self._last_quote_received_at = datetime.now(tz=timezone.utc)
                loop = asyncio.get_running_loop()
                now = loop.time()
                if now - self._last_ws_quote_log_at >= 10:
                    self._last_ws_quote_log_at = now
                    log.info("polygon.ws_quotes_received", total=self._ws_quote_count, batch_size=len(quotes))

                for quote in quotes:
                    await self._dispatch(quote)

        if self._enable_aggregates:
            await self._handle_aggregate_ws_payload(payload)

    async def _handle_ws_message(self, msg: dict) -> None:
        """Parse a Polygon WebSocket quote message."""
        quote = self._parser.parse_message(msg) if self._enable_quotes else None
        if quote is not None:
            await self._dispatch(quote)
        if self._enable_aggregates:
            await self._handle_aggregate_ws_payload(msg)

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

    def _subscription_channels(self) -> tuple[str, ...]:
        channels: list[str] = []
        if self._enable_quotes:
            channels.append("Q")
        if self._enable_aggregates:
            channels.extend(["AM", "A"])
        return tuple(channels)

    async def _handle_aggregate_ws_payload(self, payload: str | bytes | dict | list[dict]) -> None:
        if not self._aggregate_event_bus and not self._db_session_factory:
            return

        bars = self._aggregate_parser.parse_messages(payload)
        if not bars:
            return
        self._last_aggregate_received_at = datetime.now(tz=timezone.utc)

        allowed_tickers = set(self.current_symbols())
        minute_records: list[PolygonMinuteAggregateRecord] = []
        second_records: list[PolygonSecondAggregateRecord] = []

        for bar in bars:
            if bar.ticker not in allowed_tickers:
                continue
            if not is_regular_us_market_time(bar.timestamp):
                continue
            if bar.event_type == "AM":
                minute_records.append(
                    PolygonMinuteAggregateRecord(
                        ticker=bar.ticker,
                        minute_ts=bar.timestamp,
                        open=bar.open,
                        high=bar.high,
                        low=bar.low,
                        close=bar.close,
                        volume=bar.volume,
                        vwap=bar.vwap,
                        transactions=bar.transactions,
                    )
                )
            elif bar.event_type == "A":
                second_records.append(
                    PolygonSecondAggregateRecord(
                        ticker=bar.ticker,
                        second_ts=bar.timestamp,
                        open=bar.open,
                        high=bar.high,
                        low=bar.low,
                        close=bar.close,
                        volume=bar.volume,
                        vwap=bar.vwap,
                        transactions=bar.transactions,
                    )
                )

        if not minute_records and not second_records:
            return

        if self._aggregate_event_bus is not None:
            received_at = datetime.now(tz=timezone.utc)
            generation_id = getattr(self, "_subscription_generation_id", 0)
            events: list[PolygonAggregateEvent] = []
            for record in minute_records:
                events.append(
                    PolygonAggregateEvent(
                        ticker=record.ticker,
                        event_type="AM",
                        event_ts=record.minute_ts,
                        received_at=received_at,
                        subscription_generation_id=generation_id,
                        open=record.open,
                        high=record.high,
                        low=record.low,
                        close=record.close,
                        volume=record.volume,
                        vwap=record.vwap,
                        transactions=record.transactions,
                    )
                )
            for record in second_records:
                events.append(
                    PolygonAggregateEvent(
                        ticker=record.ticker,
                        event_type="A",
                        event_ts=record.second_ts,
                        received_at=received_at,
                        subscription_generation_id=generation_id,
                        open=record.open,
                        high=record.high,
                        low=record.low,
                        close=record.close,
                        volume=record.volume,
                        vwap=record.vwap,
                        transactions=record.transactions,
                    )
                )
            await self._aggregate_event_bus.publish_many(events)
            log.info(
                "polygon.aggregate_events_published",
                symbols=len(allowed_tickers),
                minute_count=len(minute_records),
                second_count=len(second_records),
                queue_depth=self._aggregate_event_bus.qsize(),
            )
            return

        db = self._db_session_factory()
        try:
            aggregate_service = PolygonAggregateService(db)
            if minute_records:
                aggregate_service.upsert_minute_aggregates(minute_records, allowed_tickers=allowed_tickers)
            if second_records:
                aggregate_service.upsert_second_aggregates(second_records, allowed_tickers=allowed_tickers)
            db.commit()
            persisted_at = datetime.now(tz=timezone.utc)
            self.record_aggregate_persisted(len(minute_records), len(second_records), persisted_at)
            log.info(
                "polygon.aggregate_batch_persisted",
                symbols=len(allowed_tickers),
                minute_count=len(minute_records),
                second_count=len(second_records),
            )
        finally:
            db.close()
