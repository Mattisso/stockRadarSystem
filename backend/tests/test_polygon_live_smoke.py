"""Live Polygon integration smoke test.

This test is gated by environment variables so it safely skips unless real
Polygon credentials are present.
"""

import asyncio
import json
import os

import httpx
import pytest
import websockets


def _live_mode() -> str:
    return os.getenv("POLYGON_SMOKE_MODE", os.getenv("POLYGON_MODE", "rest")).lower()


@pytest.mark.asyncio
async def test_polygon_live_smoke():
    api_key = os.getenv("POLYGON_API_KEY")
    if not api_key:
        pytest.skip("POLYGON_API_KEY is not set")

    symbol = os.getenv("POLYGON_SMOKE_SYMBOL", "AAPL")
    mode = _live_mode()

    if mode in {"dev", "sandbox"}:
        rest_url = os.getenv("POLYGON_REST_URL", "https://api.polygon.io")
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                f"{rest_url}/v2/aggs/ticker/{symbol}/prev",
                params={"adjusted": "true", "apiKey": api_key},
            )

        assert response.status_code == 200, response.text
        body = response.json()
        results = body.get("results", [])
        assert results, body
        assert results[0].get("c") is not None, body
        return

    if mode == "websocket":
        ws_url = os.getenv("POLYGON_WS_URL", "wss://socket.polygon.io/stocks")
        async with websockets.connect(ws_url) as ws:
            await ws.send(json.dumps({"action": "auth", "params": api_key}))

            auth_payload = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
            auth_messages = auth_payload if isinstance(auth_payload, list) else [auth_payload]
            assert any(
                msg.get("status") in {"auth_success", "connected", "success"}
                or "auth" in str(msg).lower()
                for msg in auth_messages
                if isinstance(msg, dict)
            )

            await ws.send(json.dumps({"action": "subscribe", "params": f"Q.{symbol}"}))

            for _ in range(10):
                payload = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
                messages = payload if isinstance(payload, list) else [payload]
                for msg in messages:
                    if not isinstance(msg, dict):
                        continue
                    if msg.get("ev") == "Q" and msg.get("sym") == symbol:
                        assert "t" in msg
                        return

            pytest.fail(f"No quote event received for {symbol}")

    rest_url = os.getenv("POLYGON_REST_URL", "https://api.polygon.io")
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            f"{rest_url}/v3/snapshot",
            params={"ticker.any_of": symbol, "apiKey": api_key},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    results = body.get("results", [])
    assert any(result.get("ticker") == symbol for result in results), body
