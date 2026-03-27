"""WebSocket endpoints for real-time streaming."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.auth import verify_token
from app.core.logging import get_logger
from app.api.ws_manager import ConnectionManager

log = get_logger(__name__)

router = APIRouter()

async def _serve_channel(ws: WebSocket, channel: str) -> None:
    # Authenticate via query param: /api/ws?token=<jwt>
    token = ws.query_params.get("token")
    if not token:
        await ws.close(code=4001, reason="Missing token")
        return
    try:
        verify_token(token)
    except Exception:
        await ws.close(code=4001, reason="Invalid token")
        return

    manager: ConnectionManager = ws.app.state.ws_manager
    await manager.connect(ws, channel=channel)
    try:
        while True:
            # Keep-alive loop — receive pings or future commands
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws, channel=channel)


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await _serve_channel(ws, "all")


@router.websocket("/ws/l1")
async def websocket_l1(ws: WebSocket) -> None:
    await _serve_channel(ws, "l1")


@router.websocket("/ws/l2")
async def websocket_l2(ws: WebSocket) -> None:
    await _serve_channel(ws, "l2")


@router.websocket("/ws/signals")
async def websocket_signals(ws: WebSocket) -> None:
    await _serve_channel(ws, "signals")


@router.websocket("/ws/trades")
async def websocket_trades(ws: WebSocket) -> None:
    await _serve_channel(ws, "trades")
