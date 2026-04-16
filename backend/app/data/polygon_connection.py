"""Polygon WebSocket connection management."""

import json
from contextlib import asynccontextmanager
from json import JSONDecodeError
from typing import Any, AsyncIterator, Callable

import websockets

from app.core.logging import get_logger

log = get_logger(__name__)

WebSocketConnector = Callable[[str], Any]


class PolygonConnectionManager:
    """Manage Polygon WebSocket auth and subscriptions."""

    def __init__(
        self,
        api_key: str,
        ws_url: str = "wss://socket.massive.com/stocks",
        subscription_batch_size: int = 500,
        connector: WebSocketConnector | None = None,
    ) -> None:
        self._api_key = api_key
        self._ws_url = ws_url
        self._subscription_batch_size = max(1, subscription_batch_size)
        self._connector = connector or websockets.connect

    @asynccontextmanager
    async def open(self) -> AsyncIterator[Any]:
        """Open and authenticate a WebSocket connection."""
        async with self._connector(self._ws_url) as ws:
            log.info("polygon.ws_connected", url=self._ws_url)
            await ws.send(json.dumps({"action": "auth", "params": self._api_key}))
            await wait_for_auth_success(ws)
            yield ws

    def build_subscription_batches(
        self,
        symbols: list[str],
        *,
        channels: tuple[str, ...] = ("Q",),
        include_trades: bool = False,
    ) -> list[str]:
        """Build Polygon subscription parameter batches."""
        batches: list[str] = []
        if include_trades:
            batches.append("T.*")

        if not symbols:
            if not batches:
                return [f"{channel}.*" for channel in channels]
            return batches

        for i in range(0, len(symbols), self._subscription_batch_size):
            chunk = symbols[i : i + self._subscription_batch_size]
            batches.append(",".join(f"{channel}.{symbol}" for channel in channels for symbol in chunk))
        return batches

    async def subscribe(
        self,
        ws: Any,
        symbols: list[str],
        *,
        channels: tuple[str, ...] = ("Q",),
        include_trades: bool = False,
    ) -> None:
        """Subscribe the socket to one or more symbol batches."""
        batches = self.build_subscription_batches(
            symbols,
            channels=channels,
            include_trades=include_trades,
        )
        for params in batches:
            await ws.send(json.dumps({"action": "subscribe", "params": params}))
        log.info(
            "polygon.ws_subscribed",
            symbols=len(symbols),
            batches=len(batches),
            channels=",".join(channels),
            include_trades=include_trades,
        )

    async def unsubscribe(
        self,
        ws: Any,
        symbols: list[str],
        *,
        channels: tuple[str, ...] = ("Q",),
        include_trades: bool = False,
    ) -> None:
        """Unsubscribe the socket from one or more symbol batches."""
        batches = self.build_subscription_batches(
            symbols,
            channels=channels,
            include_trades=include_trades,
        )
        for params in batches:
            await ws.send(json.dumps({"action": "unsubscribe", "params": params}))
        log.info(
            "polygon.ws_unsubscribed",
            symbols=len(symbols),
            batches=len(batches),
            channels=",".join(channels),
            include_trades=include_trades,
        )


def log_auth_response(auth_resp: Any) -> None:
    """Log the initial Polygon WebSocket response with clearer semantics."""
    try:
        payload = json.loads(auth_resp) if isinstance(auth_resp, (str, bytes)) else auth_resp
    except JSONDecodeError:
        log.info("polygon.ws_auth_response", response=str(auth_resp)[:200])
        return

    messages = payload if isinstance(payload, list) else [payload]
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        status = msg.get("status")
        message = msg.get("message", "")
        event = msg.get("ev")

        if event == "status" and status == "connected":
            log.info("polygon.ws_status", status=status, message=message)
        elif event == "status" and status in {"auth_success", "success", "authenticated"}:
            log.info("polygon.ws_auth_success", status=status, message=message)
        elif event == "status":
            log.info("polygon.ws_status", status=status, message=message)
        else:
            log.info("polygon.ws_auth_response", response=str(msg)[:200])


async def wait_for_auth_success(ws: Any, max_messages: int = 5) -> None:
    """Consume initial status frames until auth success is observed."""
    saw_connected = False

    for _ in range(max_messages):
        auth_resp = await ws.recv()
        log_auth_response(auth_resp)

        try:
            payload = json.loads(auth_resp) if isinstance(auth_resp, (str, bytes)) else auth_resp
        except JSONDecodeError:
            continue

        messages = payload if isinstance(payload, list) else [payload]
        for msg in messages:
            if not isinstance(msg, dict):
                continue

            if msg.get("ev") != "status":
                continue

            status = msg.get("status")
            if status == "connected":
                saw_connected = True
            elif status in {"auth_success", "success", "authenticated"}:
                return
            elif status in {"auth_failed", "error"}:
                raise RuntimeError(f"Polygon auth failed: {msg}")

    if saw_connected:
        raise RuntimeError("Polygon auth success not received after initial connected status")
    raise RuntimeError("Polygon auth did not return a recognized success status")
