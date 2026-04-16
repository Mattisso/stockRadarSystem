"""Universe-scoped Polygon aggregate websocket client."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any
from websockets.exceptions import ConnectionClosed

from app.core.logging import get_logger
from app.data.polygon_aggregate_parser import PolygonAggregateParser
from app.data.polygon_aggregate_service import (
    PolygonAggregateService,
    PolygonMinuteAggregateRecord,
    PolygonSecondAggregateRecord,
)
from app.data.polygon_connection import PolygonConnectionManager

log = get_logger(__name__)


class PolygonAggregateClient:
    """Stream A/AM aggregate events for the active universe and persist them."""

    def __init__(
        self,
        *,
        api_key: str,
        db_session_factory,
        ws_url: str,
        reconnect_max_delay: float,
        subscription_batch_size: int,
    ) -> None:
        self._db_session_factory = db_session_factory
        self._connection_manager = PolygonConnectionManager(
            api_key=api_key,
            ws_url=ws_url,
            subscription_batch_size=subscription_batch_size,
        )
        self._parser = PolygonAggregateParser()
        self._reconnect_max_delay = reconnect_max_delay
        self._subscription_sources: dict[str, list[str]] = {"secret_universe": []}
        self._task: asyncio.Task | None = None
        self._running = False
        self._ws: Any = None
        self._ws_lock = asyncio.Lock()

    def update_subscriptions(self, tickers: list[str], *, source: str = "secret_universe") -> None:
        self._subscription_sources[source] = list(dict.fromkeys(tickers))
        log.info("polygon.aggregate_subscriptions_updated", count=len(self.current_symbols()), source=source)
        if self._running:
            asyncio.create_task(self._resubscribe())

    async def _resubscribe(self) -> None:
        """Send new subscription commands to the active WebSocket."""
        async with self._ws_lock:
            if self._ws:
                try:
                    await self._connection_manager.subscribe(
                        self._ws,
                        self.current_symbols(),
                        channels=("AM", "A"),
                    )
                except Exception:
                    log.exception("polygon.aggregate_resubscribe_error")

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

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._running = True
        self._task = asyncio.create_task(self._ws_loop())
        log.info("polygon.aggregate_client_started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        log.info("polygon.aggregate_client_stopped")

    async def _ws_loop(self) -> None:
        delay = 1.0
        while self._running:
            try:
                async with self._connection_manager.open() as ws:
                    async with self._ws_lock:
                        self._ws = ws
                        symbols = self.current_symbols()
                        await self._connection_manager.subscribe(ws, symbols, channels=("AM", "A"))
                    delay = 1.0
                    async for raw in ws:
                        if not self._running:
                            break
                        await self._handle_payload(raw)
            except asyncio.CancelledError:
                break
            except ConnectionClosed as exc:
                async with self._ws_lock:
                    self._ws = None
                log.warning("polygon.aggregate_ws_closed", code=exc.code, reason=exc.reason, delay=delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, self._reconnect_max_delay)
            except Exception:
                async with self._ws_lock:
                    self._ws = None
                log.exception("polygon.aggregate_ws_error", delay=delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, self._reconnect_max_delay)
            finally:
                async with self._ws_lock:
                    self._ws = None

    async def _handle_payload(self, payload) -> None:
        bars = self._parser.parse_messages(payload)
        if not bars:
            return

        allowed_tickers = set(self.current_symbols())
        minute_records: list[PolygonMinuteAggregateRecord] = []
        second_records: list[PolygonSecondAggregateRecord] = []

        for bar in bars:
            if bar.ticker not in allowed_tickers:
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

        db = self._db_session_factory()
        try:
            aggregate_service = PolygonAggregateService(db)
            if minute_records:
                aggregate_service.upsert_minute_aggregates(minute_records, allowed_tickers=allowed_tickers)
            if second_records:
                aggregate_service.upsert_second_aggregates(second_records, allowed_tickers=allowed_tickers)
            db.commit()
            log.info(
                "polygon.aggregate_batch_persisted",
                symbols=len(allowed_tickers),
                minute_count=len(minute_records),
                second_count=len(second_records),
            )
        finally:
            db.close()
