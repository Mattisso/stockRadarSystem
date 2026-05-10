"""Tests for Polygon client (mocked — no API key needed)."""

import asyncio
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest
from app.broker.interface import Quote
from app.data.cache import InMemoryCache
from app.data.polygon_client import PolygonClient
from app.data.polygon_event_bus import PolygonEventBus


@pytest.fixture
def cache():
    return InMemoryCache(ttl=10)


@pytest.fixture
def queue():
    return asyncio.Queue(maxsize=100)


@pytest.fixture
def client(cache, queue):
    return PolygonClient(
        api_key="test-key",
        mode="rest",
        symbols=["LCID", "GEVO"],
        cache=cache,
        queue=queue,
        rest_poll_interval=0.1,
    )


@pytest.mark.asyncio
async def test_update_subscriptions(client):
    client.update_subscriptions(["AAPL", "TSLA", "LCID"])
    assert len(client._symbols) == 3


@pytest.mark.asyncio
async def test_update_subscriptions_unions_multiple_sources(client):
    client.update_subscriptions(["AAPL", "TSLA"], source="watchlist")
    client.update_subscriptions(["LCID", "AAPL"], source="secret_universe")

    assert client.current_symbols() == ["AAPL", "TSLA", "LCID"]


@pytest.mark.asyncio
async def test_update_subscriptions_tracks_sticky_source_metadata(client):
    client.update_subscriptions(["AAPL", "TSLA"], source="watchlist")
    client.update_subscriptions(["LCID", "AAPL"], source="operational", sticky=True)

    snapshot = client.session_snapshot()
    assert snapshot["subscription_count"] == 3
    assert snapshot["sticky_subscription_count"] == 2
    assert snapshot["subscription_generation_id"] == 2
    assert snapshot["subscription_sources"] == [
        {"source": "watchlist", "count": 2, "sticky": False},
        {"source": "operational", "count": 2, "sticky": True},
    ]


@pytest.mark.asyncio
async def test_dispatch_to_cache(client, cache):
    await cache.connect()
    quote = Quote(ticker="LCID", bid=3.47, ask=3.48, last=3.48, volume=100000, timestamp=datetime.now())
    await client._dispatch(quote)
    result = await cache.get_l1("LCID")
    assert result is not None
    assert result.ticker == "LCID"


@pytest.mark.asyncio
async def test_dispatch_to_queue(client, queue):
    quote = Quote(ticker="LCID", bid=3.47, ask=3.48, last=3.48, volume=100000, timestamp=datetime.now())
    await client._dispatch(quote)
    assert not queue.empty()
    item = queue.get_nowait()
    assert item.ticker == "LCID"


@pytest.mark.asyncio
async def test_handle_ws_message(client, cache):
    await cache.connect()
    msg = {
        "ev": "Q",
        "sym": "GEVO",
        "bp": 1.87,
        "ap": 1.88,
        "z": 500000,
        "t": int(datetime.now(tz=timezone.utc).timestamp() * 1000),
    }
    await client._handle_ws_message(msg)
    result = await cache.get_l1("GEVO")
    assert result is not None
    assert result.bid == 1.87


@pytest.mark.asyncio
async def test_handle_ws_message_ignores_non_quote(client, cache):
    await cache.connect()
    msg = {"ev": "status", "sym": "GEVO"}  # Status event, not market data
    await client._handle_ws_message(msg)
    result = await cache.get_l1("GEVO")
    assert result is None


@pytest.mark.asyncio
async def test_handle_ws_message_dispatches_trade_message(client, cache, queue):
    await cache.connect()
    msg = {
        "ev": "T",
        "sym": "GEVO",
        "p": 1.87,
        "s": 2500,
        "t": int(datetime.now(tz=timezone.utc).timestamp() * 1000),
    }
    await client._handle_ws_message(msg)
    result = await cache.get_l1("GEVO")
    assert result is not None
    assert result.last == 1.87
    assert result.event_type == "trade"
    queued = queue.get_nowait()
    assert queued.event_type == "trade"


@pytest.mark.asyncio
async def test_queue_full_does_not_raise(cache):
    """When queue is full, dispatch should not raise."""
    small_queue = asyncio.Queue(maxsize=1)
    c = PolygonClient(api_key="x", cache=cache, queue=small_queue)
    await cache.connect()

    q1 = Quote(ticker="A", bid=1, ask=2, last=1, volume=1, timestamp=datetime.now())
    q2 = Quote(ticker="B", bid=1, ask=2, last=1, volume=1, timestamp=datetime.now())

    await c._dispatch(q1)
    await c._dispatch(q2)  # Should not raise even though queue is full
    assert small_queue.qsize() == 1


@pytest.mark.asyncio
async def test_rest_poll_mocked(client, cache):
    """Test REST poll with mocked httpx response."""
    await cache.connect()

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = lambda: {
        "results": [
            {"ticker": "LCID", "session": {"close": 3.50, "volume": 200000}},
            {"ticker": "GEVO", "session": {"close": 1.90, "volume": 150000}},
        ]
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    await client._rest_poll(mock_client)

    mock_client.get.assert_awaited_once_with(
        "https://api.polygon.io/v3/snapshot",
        params={"ticker.any_of": "LCID,GEVO", "apiKey": "test-key"},
    )

    lcid = await cache.get_l1("LCID")
    assert lcid is not None
    assert lcid.last == 3.50

    gevo = await cache.get_l1("GEVO")
    assert gevo is not None
    assert gevo.last == 1.90


@pytest.mark.asyncio
async def test_load_reference_universe_filters_reference_and_snapshot_data(client):
    reference_page = AsyncMock()
    reference_page.raise_for_status = lambda: None
    reference_page.json = lambda: {
        "results": [
            {"ticker": "LCID"},
            {"ticker": "GEVO"},
            {"ticker": "AAPL"},
        ]
    }

    snapshot_page = AsyncMock()
    snapshot_page.raise_for_status = lambda: None
    snapshot_page.json = lambda: {
        "results": [
            {"ticker": "LCID", "session": {"close": 3.50, "volume": 200000}},
            {"ticker": "GEVO", "session": {"close": 0.90, "volume": 300000}},
            {"ticker": "AAPL", "session": {"close": 180.00, "volume": 5000000}},
        ]
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=snapshot_page)

    universe = await client._fetch_snapshot_universe(
        mock_client,
        tickers=["LCID", "GEVO", "AAPL"],
        max_price=10.0,
        min_price=1.0,
        min_volume=100000,
    )
    assert [quote.ticker for quote in universe] == ["LCID"]

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=reference_page)
    tickers = await client._fetch_reference_tickers(mock_client, exchange="XNAS")
    assert tickers == ["LCID", "GEVO", "AAPL"]


@pytest.mark.asyncio
async def test_dev_poll_mocked(client, cache):
    await cache.connect()
    client._mode = "dev"
    client._dev_max_symbols = 2

    response_by_symbol = {
        "LCID": {
            "results": [
                {"c": 3.50, "v": 200000, "t": int(datetime.now(tz=timezone.utc).timestamp() * 1000)}
            ]
        },
        "GEVO": {
            "results": [
                {"c": 1.90, "v": 150000, "t": int(datetime.now(tz=timezone.utc).timestamp() * 1000)}
            ]
        },
    }

    async def fake_get(url, params):
        symbol = url.rstrip("/").split("/")[-2]
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = lambda: response_by_symbol[symbol]
        return mock_response

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=fake_get)

    await client._dev_poll(mock_client)

    mock_client.get.assert_any_await(
        "https://api.polygon.io/v2/aggs/ticker/LCID/prev",
        params={"adjusted": "true", "apiKey": "test-key"},
    )
    mock_client.get.assert_any_await(
        "https://api.polygon.io/v2/aggs/ticker/GEVO/prev",
        params={"adjusted": "true", "apiKey": "test-key"},
    )
    assert mock_client.get.await_count == 2

    lcid = await cache.get_l1("LCID")
    assert lcid is not None
    assert lcid.last == 3.50

    gevo = await cache.get_l1("GEVO")
    assert gevo is not None
    assert gevo.last == 1.90


@pytest.mark.asyncio
async def test_start_uses_dev_mode_loop(cache, queue):
    client = PolygonClient(api_key="test-key", mode="dev", cache=cache, queue=queue)

    with patch.object(client, "_dev_poll_loop", new=AsyncMock()) as dev_loop:
        await client.start()
        await asyncio.sleep(0)
        await client.stop()

    dev_loop.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_ws_payload_dispatches_batch(client, cache, queue):
    await cache.connect()
    now_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)

    await client._handle_ws_payload([
        {"ev": "status", "message": "connected"},
        {"ev": "Q", "sym": "LCID", "bp": 3.47, "ap": 3.48, "z": 100000, "t": now_ms},
    ])

    cached = await cache.get_l1("LCID")
    assert cached is not None
    assert cached.bid == 3.47
    queued = queue.get_nowait()
    assert queued.ticker == "LCID"


class _RetryWebSocket:
    def __init__(self, client):
        self._client = client
        self._messages = [(
            '[{"ev":"Q","sym":"AAPL","bp":150.0,"ap":150.1,"z":1000,"t":1000}]'
        )]

    async def send(self, payload: str) -> None:
        return None

    async def recv(self) -> str:
        return '{"status":"auth_success"}'

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._messages:
            return self._messages.pop(0)
        self._client._running = False
        raise StopAsyncIteration


class _RetryConnectionManager:
    def __init__(self, client):
        self.client = client
        self.open_calls = 0
        self.subscribe_calls: list[list[str]] = []
        self.unsubscribe_calls: list[list[str]] = []

    @asynccontextmanager
    async def open(self):
        self.open_calls += 1
        if self.open_calls == 1:
            raise RuntimeError("boom")
        yield _RetryWebSocket(self.client)

    async def subscribe(self, ws, symbols, channels=("Q",), include_trades=False):
        self.subscribe_calls.append(
            {"symbols": list(symbols), "channels": list(channels), "include_trades": include_trades}
        )

    async def unsubscribe(self, ws, symbols, channels=("Q",), include_trades=False):
        self.unsubscribe_calls.append(
            {"symbols": list(symbols), "channels": list(channels), "include_trades": include_trades}
        )


@pytest.mark.asyncio
async def test_ws_loop_retries_and_resubscribes(cache, queue):
    await cache.connect()
    client = PolygonClient(
        api_key="test-key",
        mode="websocket",
        symbols=["AAPL", "TSLA"],
        cache=cache,
        queue=queue,
    )
    manager = _RetryConnectionManager(client)
    client._connection_manager = manager

    with patch("app.data.polygon_client.asyncio.sleep", new=AsyncMock()) as sleep_mock:
        client._running = True
        await client._ws_loop()

    assert manager.open_calls == 2
    assert manager.subscribe_calls == [{"symbols": ["AAPL", "TSLA"], "channels": ["Q"], "include_trades": False}]
    sleep_mock.assert_awaited_once()
    cached = await cache.get_l1("AAPL")
    assert cached is not None
    assert cached.bid == 150.0


@pytest.mark.asyncio
async def test_ws_loop_secret_session_resubscribes_union_with_trade_wildcard(cache, queue):
    await cache.connect()
    client = PolygonClient(
        api_key="test-key",
        mode="websocket",
        cache=cache,
        queue=queue,
        include_trade_wildcard=True,
    )
    client.update_subscriptions(["AAPL"], source="watchlist")
    client.update_subscriptions(["LCID"], source="secret_universe")
    manager = _RetryConnectionManager(client)
    client._connection_manager = manager

    with patch("app.data.polygon_client.asyncio.sleep", new=AsyncMock()):
        client._running = True
        await client._ws_loop()

    assert manager.subscribe_calls == [
        {"symbols": ["AAPL", "LCID"], "channels": ["Q"], "include_trades": True}
    ]
    snapshot = client.session_snapshot()
    assert snapshot["reconnect_count"] == 1
    assert snapshot["include_trade_wildcard"] is True
    assert snapshot["last_error_type"] == "exception"
    assert snapshot["last_error_at"] is not None
    assert snapshot["last_connected_at"] is not None
    assert snapshot["consecutive_failures"] == 0


@pytest.mark.asyncio
async def test_ws_loop_subscribes_q_am_a_when_aggregates_enabled(cache, queue):
    await cache.connect()
    client = PolygonClient(
        api_key="test-key",
        mode="websocket",
        cache=cache,
        queue=queue,
        enable_quotes=True,
        enable_aggregates=True,
    )
    client.update_subscriptions(["AAPL"], source="secret_universe")
    manager = _RetryConnectionManager(client)
    client._connection_manager = manager

    with patch("app.data.polygon_client.asyncio.sleep", new=AsyncMock()):
        client._running = True
        await client._ws_loop()

    assert manager.subscribe_calls == [
        {"symbols": ["AAPL"], "channels": ["Q", "AM", "A"], "include_trades": False}
    ]


@pytest.mark.asyncio
async def test_pause_and_resume_subscriptions_preserves_desired_symbols(cache, queue):
    await cache.connect()
    client = PolygonClient(
        api_key="test-key",
        mode="websocket",
        cache=cache,
        queue=queue,
        include_trade_wildcard=True,
    )
    client.update_subscriptions(["AAPL"], source="watchlist")
    client.update_subscriptions(["LCID"], source="secret_universe")
    manager = _RetryConnectionManager(client)
    client._connection_manager = manager
    client._ws = object()

    await client.pause_subscriptions()
    client.update_subscriptions(["TSLA"], source="watchlist")
    await client.resume_subscriptions()

    assert manager.unsubscribe_calls == [
        {"symbols": ["AAPL", "LCID"], "channels": ["Q"], "include_trades": True}
    ]
    assert manager.subscribe_calls == [
        {"symbols": ["TSLA", "LCID"], "channels": ["Q"], "include_trades": True}
    ]
    snapshot = client.session_snapshot()
    assert snapshot["subscriptions_paused"] is False


@pytest.mark.asyncio
async def test_update_subscriptions_resubscribe_preserves_aggregate_channels(cache, queue):
    await cache.connect()
    client = PolygonClient(
        api_key="test-key",
        mode="websocket",
        cache=cache,
        queue=queue,
        enable_quotes=True,
        enable_aggregates=True,
    )
    manager = _RetryConnectionManager(client)
    client._connection_manager = manager
    client._running = True
    client._ws = object()

    client.update_subscriptions(["AAPL"], source="secret_universe")
    await asyncio.sleep(0)

    assert manager.subscribe_calls == [
        {"symbols": ["AAPL"], "channels": ["Q", "AM", "A"], "include_trades": False}
    ]


@pytest.mark.asyncio
async def test_ws_loop_skips_initial_subscribe_when_paused(cache, queue):
    await cache.connect()
    client = PolygonClient(
        api_key="test-key",
        mode="websocket",
        cache=cache,
        queue=queue,
    )
    client.update_subscriptions(["AAPL"], source="watchlist")
    client._subscriptions_paused = True
    manager = _RetryConnectionManager(client)
    client._connection_manager = manager

    with patch("app.data.polygon_client.asyncio.sleep", new=AsyncMock()):
        client._running = True
        await client._ws_loop()

    assert manager.subscribe_calls == []
    assert client.session_snapshot()["subscriptions_paused"] is True


@pytest.mark.asyncio
async def test_start_and_stop_websocket_mode(cache, queue):
    client = PolygonClient(api_key="test-key", mode="websocket", cache=cache, queue=queue)

    with patch.object(client, "_ws_loop", new=AsyncMock()) as ws_loop:
        await client.start()
        await asyncio.sleep(0)
        await client.stop()

    ws_loop.assert_awaited_once()


@pytest.mark.asyncio
async def test_session_snapshot_reports_quote_and_aggregate_telemetry(cache, queue):
    await cache.connect()

    class _FakeSession:
        def commit(self):
            return None

        def close(self):
            return None

    client = PolygonClient(
        api_key="test-key",
        mode="websocket",
        cache=cache,
        queue=queue,
        enable_quotes=True,
        enable_aggregates=True,
        db_session_factory=_FakeSession,
    )
    client.update_subscriptions(["LCID"], source="secret_universe")

    now_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
    with patch("app.data.polygon_client.PolygonAggregateService") as aggregate_service_cls:
        aggregate_service = aggregate_service_cls.return_value
        aggregate_service.upsert_minute_aggregates.return_value = 1
        aggregate_service.upsert_second_aggregates.return_value = 1
        await client._handle_ws_payload(
            [
                {"ev": "Q", "sym": "LCID", "bp": 3.47, "ap": 3.48, "z": 100000, "t": now_ms},
                {"ev": "AM", "sym": "LCID", "o": 3.40, "h": 3.50, "l": 3.39, "c": 3.48, "v": 1000, "s": now_ms, "e": now_ms + 60000, "av": 3.45, "a": 10},
                {"ev": "A", "sym": "LCID", "o": 3.47, "h": 3.49, "l": 3.46, "c": 3.48, "v": 100, "s": now_ms, "e": now_ms + 1000, "av": 3.48, "a": 4},
            ]
        )

    snapshot = client.session_snapshot()
    assert snapshot["quotes_enabled"] is True
    assert snapshot["aggregates_enabled"] is True
    assert snapshot["quote_message_count"] == 1
    assert snapshot["aggregate_batch_count"] == 1
    assert snapshot["persisted_minute_bar_count"] == 1
    assert snapshot["persisted_second_bar_count"] == 1
    assert snapshot["last_quote_received_at"] is not None
    assert snapshot["last_aggregate_received_at"] is not None
    assert snapshot["last_aggregate_persisted_at"] is not None
    assert snapshot["last_minute_persisted_at"] is not None
    assert snapshot["last_second_persisted_at"] is not None
    assert snapshot["quote_age_seconds"] is not None
    assert snapshot["aggregate_persist_age_seconds"] is not None


@pytest.mark.asyncio
async def test_handle_aggregate_ws_payload_publishes_to_event_bus(cache, queue):
    await cache.connect()
    event_bus = PolygonEventBus(maxsize=10)
    client = PolygonClient(
        api_key="test-key",
        mode="websocket",
        cache=cache,
        queue=queue,
        enable_quotes=False,
        enable_aggregates=True,
        aggregate_event_bus=event_bus,
    )
    client.update_subscriptions(["LCID"], source="secret_universe")

    now_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
    await client._handle_ws_payload(
        [
            {"ev": "AM", "sym": "LCID", "o": 3.40, "h": 3.50, "l": 3.39, "c": 3.48, "v": 1000, "s": now_ms, "e": now_ms + 60000, "av": 3.45, "a": 10},
            {"ev": "A", "sym": "LCID", "o": 3.47, "h": 3.49, "l": 3.46, "c": 3.48, "v": 100, "s": now_ms, "e": now_ms + 1000, "av": 3.48, "a": 4},
        ]
    )

    assert event_bus.qsize() == 2
    first = event_bus.read_nowait()
    second = event_bus.read_nowait()
    assert first.ticker == "LCID"
    assert first.subscription_generation_id == 1
    assert first.event_type == "AM"
    assert second.event_type == "A"

    snapshot = client.session_snapshot()
    assert snapshot["aggregate_batch_count"] == 0
    assert snapshot["persisted_minute_bar_count"] == 0
    assert snapshot["persisted_second_bar_count"] == 0
    assert snapshot["last_aggregate_received_at"] is not None
