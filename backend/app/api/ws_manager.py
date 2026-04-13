"""Channel-aware WebSocket manager with optional Redis pub/sub fan-out."""

import asyncio
import contextlib
import json
from collections import defaultdict
from typing import Any

from fastapi import WebSocket
from redis.asyncio import Redis
from starlette.websockets import WebSocketState

from app.core.logging import get_logger

log = get_logger(__name__)

WS_CHANNELS: dict[str, tuple[str, ...]] = {
    "all": ("signal", "state_machine", "trade", "portfolio", "live_movers", "l2"),
    "signals": ("signal", "state_machine"),
    "trades": ("trade", "portfolio"),
    "l1": ("live_movers",),
    "l2": ("l2",),
}


class ConnectionManager:
    """Manages active WebSocket connections and channel broadcasts."""

    def __init__(self, redis_url: str | None = None) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._redis_url = redis_url or ""
        self._redis: Redis | None = None
        self._pubsub = None
        self._listener_task: asyncio.Task | None = None

    @property
    def active_count(self) -> int:
        return sum(len(peers) for peers in self._connections.values())

    @property
    def uses_pubsub(self) -> bool:
        return bool(self._redis_url)

    async def start(self) -> None:
        if not self._redis_url:
            return
        self._redis = Redis.from_url(self._redis_url, decode_responses=True)
        self._pubsub = self._redis.pubsub()
        await self._pubsub.subscribe(*[self._redis_channel(name) for name in WS_CHANNELS])
        self._listener_task = asyncio.create_task(self._listen())

    async def stop(self) -> None:
        if self._listener_task:
            self._listener_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._listener_task
        if self._pubsub:
            await self._pubsub.close()
        if self._redis:
            await self._redis.close()

    async def connect(self, ws: WebSocket, channel: str = "all") -> None:
        if channel not in WS_CHANNELS:
            raise ValueError(f"Unknown websocket channel: {channel}")
        await ws.accept()
        self._connections[channel].add(ws)
        log.info("ws.connected", channel=channel, active=self.active_count)

    def disconnect(self, ws: WebSocket, channel: str = "all") -> None:
        self._connections[channel].discard(ws)
        log.info("ws.disconnected", channel=channel, active=self.active_count)

    async def broadcast(self, topic: str, data: Any, channel: str = "all") -> None:
        """Broadcast to a logical channel, optionally via Redis pub/sub."""
        if channel not in WS_CHANNELS:
            raise ValueError(f"Unknown websocket channel: {channel}")

        if self._redis:
            payload = json.dumps({"topic": topic, "data": data}, default=str)
            await self._redis.publish(self._redis_channel(channel), payload)
            return

        await self._send_local(channel, topic, data)

    async def _listen(self) -> None:
        assert self._pubsub is not None
        while True:
            message = await self._pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if not message:
                await asyncio.sleep(0.05)
                continue

            channel = self._redis_channel_name(message["channel"])
            payload = json.loads(message["data"])
            await self._send_local(channel, payload["topic"], payload["data"])

    async def _send_local(self, channel: str, topic: str, data: Any) -> None:
        payload = json.dumps({"topic": topic, "data": data}, default=str)
        stale: list[tuple[str, WebSocket]] = []

        for target_channel in self._target_channels(channel):
            for ws in self._connections[target_channel]:
                try:
                    if ws.client_state == WebSocketState.CONNECTED:
                        await ws.send_text(payload)
                except Exception:
                    stale.append((target_channel, ws))

        for target_channel, ws in stale:
            self._connections[target_channel].discard(ws)

    def _target_channels(self, channel: str) -> tuple[str, ...]:
        if channel == "all":
            return tuple(self._connections.keys())
        return tuple({"all", channel})

    @staticmethod
    def _redis_channel(name: str) -> str:
        return f"stockradar:ws:{name}"

    @staticmethod
    def _redis_channel_name(name: str) -> str:
        return name.rsplit(":", 1)[-1]
