"""WebSocket endpoint for real-time streaming."""

import json
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.core.logging import get_logger

log = get_logger(__name__)

router = APIRouter()


class ConnectionManager:
    """Manages active WebSocket connections and broadcasts messages."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    @property
    def active_count(self) -> int:
        return len(self._connections)

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.add(ws)
        log.info("ws.connected", active=self.active_count)

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.discard(ws)
        log.info("ws.disconnected", active=self.active_count)

    async def broadcast(self, topic: str, data: Any) -> None:
        """Send a message to all connected clients."""
        if not self._connections:
            return

        payload = json.dumps({"topic": topic, "data": data}, default=str)
        stale: list[WebSocket] = []

        for ws in self._connections:
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_text(payload)
            except Exception:
                stale.append(ws)

        for ws in stale:
            self._connections.discard(ws)


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    manager: ConnectionManager = ws.app.state.ws_manager
    await manager.connect(ws)
    try:
        while True:
            # Keep-alive loop — receive pings or future commands
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)
