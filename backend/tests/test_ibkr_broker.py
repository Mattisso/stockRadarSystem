"""Tests for the IBKRBroker implementation with mocked ib_insync."""

import asyncio
import math
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.broker.interface import OrderSide, OrderStatus, OrderType


def _make_mock_ib():
    """Create a fully mocked ib_insync.IB instance."""
    ib = MagicMock()
    ib.isConnected.return_value = True
    ib.connectAsync = AsyncMock()
    ib.disconnect = MagicMock()
    ib.qualifyContractsAsync = AsyncMock()
    ib.reqMktData = MagicMock()
    ib.cancelMktData = MagicMock()
    ib.reqMktDepth = MagicMock()
    ib.cancelMktDepth = MagicMock()
    ib.placeOrder = MagicMock()
    ib.cancelOrder = MagicMock()
    ib.positions = MagicMock(return_value=[])
    ib.accountSummary = MagicMock(return_value=[])
    ib.pnl = MagicMock(return_value=[])
    ib.openTrades = MagicMock(return_value=[])
    ib.reqScannerDataAsync = AsyncMock(return_value=[])
    ib.disconnectedEvent = MagicMock()
    ib.disconnectedEvent.__iadd__ = MagicMock(return_value=ib.disconnectedEvent)
    ib.disconnectedEvent.__isub__ = MagicMock(return_value=ib.disconnectedEvent)
    return ib


def _make_ticker(bid=5.0, ask=5.02, last=5.01, volume=1000000):
    """Create a mock Ticker with given values."""
    ticker = SimpleNamespace(
        bid=bid,
        ask=ask,
        last=last,
        volume=volume,
        domBids=[],
        domAsks=[],
    )
    return ticker


def _make_contract(symbol="AAPL", con_id=12345):
    """Create a mock qualified contract."""
    contract = SimpleNamespace(symbol=symbol, conId=con_id)
    return contract


@pytest.fixture
async def broker():
    """Create an IBKRBroker with mocked IB instance — skip real thread/loop."""
    with patch("app.broker.ibkr_broker.IB") as mock_ib_class:
        mock_ib = _make_mock_ib()
        mock_ib_class.return_value = mock_ib

        from app.broker.ibkr_broker import IBKRBroker

        b = IBKRBroker(host="127.0.0.1", port=7497, client_id=1)
        b._ib = mock_ib
        b._connected = True

        # Set up a real event loop for _run_on_ib_loop
        loop = asyncio.new_event_loop()
        b._ib_loop = loop

        import threading

        def _run_loop():
            asyncio.set_event_loop(loop)
            loop.run_forever()

        thread = threading.Thread(target=_run_loop, daemon=True)
        thread.start()

        # Default: qualify returns a valid contract
        qualified_contract = _make_contract()
        mock_ib.qualifyContractsAsync.return_value = [qualified_contract]

        yield b

        # Cleanup
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=2)


@pytest.mark.asyncio
async def test_connect(broker):
    assert broker._connected is True


@pytest.mark.asyncio
async def test_disconnect(broker):
    await broker.disconnect()
    assert broker._connected is False


@pytest.mark.asyncio
async def test_get_quote(broker):
    mock_ticker = _make_ticker(bid=3.20, ask=3.22, last=3.21, volume=5000000)
    broker._ib.reqMktData.return_value = mock_ticker

    quote = await broker.get_quote("SIRI")
    assert quote.ticker == "SIRI"
    assert quote.bid == 3.20
    assert quote.ask == 3.22
    assert quote.last == 3.21
    assert quote.volume == 5000000


@pytest.mark.asyncio
async def test_get_quote_handles_nan(broker):
    """NaN values from IB should become 0.0."""
    mock_ticker = _make_ticker(
        bid=float("nan"),
        ask=float("nan"),
        last=float("nan"),
        volume=float("nan"),
    )
    broker._ib.reqMktData.return_value = mock_ticker

    quote = await broker.get_quote("TEST")
    assert quote.bid == 0.0
    assert quote.ask == 0.0
    assert quote.last == 0.0
    assert quote.volume == 0


@pytest.mark.asyncio
async def test_get_quote_from_subscription(broker):
    """Subscribed tickers should return cached market data without new request."""
    mock_ticker = _make_ticker(bid=4.50, ask=4.52, last=4.51, volume=2000000)
    broker._market_data["LCID"] = mock_ticker

    quote = await broker.get_quote("LCID")
    assert quote.ticker == "LCID"
    assert quote.bid == 4.50
    # Should not call reqMktData since data is cached
    broker._ib.reqMktData.assert_not_called()


@pytest.mark.asyncio
async def test_get_order_book(broker):
    mock_ticker = _make_ticker()
    mock_ticker.domBids = [
        SimpleNamespace(price=5.00, size=100),
        SimpleNamespace(price=4.99, size=200),
    ]
    mock_ticker.domAsks = [
        SimpleNamespace(price=5.02, size=150),
        SimpleNamespace(price=5.03, size=250),
    ]
    broker._ib.reqMktDepth.return_value = mock_ticker

    book = await broker.get_order_book("AAPL")
    assert book.ticker == "AAPL"
    assert len(book.bids) == 2
    assert len(book.asks) == 2
    assert book.bids[0].price == 5.00
    assert book.asks[0].price == 5.02


@pytest.mark.asyncio
async def test_submit_market_order(broker):
    mock_trade = MagicMock()
    mock_trade.orderStatus.status = "Filled"
    mock_trade.order.orderId = 42
    mock_trade.isDone.return_value = True
    mock_fill = SimpleNamespace(
        execution=SimpleNamespace(price=3.21, shares=100)
    )
    mock_trade.fills = [mock_fill]
    broker._ib.placeOrder.return_value = mock_trade

    result = await broker.submit_order(
        ticker="SIRI",
        side=OrderSide.BUY,
        quantity=100,
        order_type=OrderType.MARKET,
    )
    assert result.status == OrderStatus.FILLED
    assert result.fill_price == 3.21
    assert result.filled_quantity == 100
    assert result.order_id == "42"


@pytest.mark.asyncio
async def test_submit_limit_order(broker):
    mock_trade = MagicMock()
    mock_trade.orderStatus.status = "Submitted"
    mock_trade.order.orderId = 43
    mock_trade.isDone.return_value = False
    mock_trade.fills = []
    broker._ib.placeOrder.return_value = mock_trade

    result = await broker.submit_order(
        ticker="SIRI",
        side=OrderSide.BUY,
        quantity=100,
        order_type=OrderType.LIMIT,
        limit_price=3.00,
    )
    assert result.status == OrderStatus.PENDING
    assert result.fill_price is None
    assert result.filled_quantity == 0


@pytest.mark.asyncio
async def test_cancel_order(broker):
    mock_trade = MagicMock()
    mock_trade.order.orderId = 42
    broker._ib.openTrades.return_value = [mock_trade]

    success = await broker.cancel_order("42")
    assert success is True
    broker._ib.cancelOrder.assert_called_once()


@pytest.mark.asyncio
async def test_cancel_order_not_found(broker):
    broker._ib.openTrades.return_value = []
    success = await broker.cancel_order("999")
    assert success is False


@pytest.mark.asyncio
async def test_get_positions(broker):
    mock_pos = SimpleNamespace(
        contract=SimpleNamespace(symbol="SIRI"),
        position=100.0,
        avgCost=3.15,
    )
    broker._ib.positions.return_value = [mock_pos]

    # Mock get_quote for market value calculation
    mock_ticker = _make_ticker(bid=3.20, ask=3.22, last=3.21)
    broker._ib.reqMktData.return_value = mock_ticker

    positions = await broker.get_positions()
    assert len(positions) == 1
    assert positions[0].ticker == "SIRI"
    assert positions[0].quantity == 100
    assert positions[0].avg_cost == 3.15


@pytest.mark.asyncio
async def test_get_account_summary(broker):
    broker._ib.accountSummary.return_value = [
        SimpleNamespace(tag="TotalCashValue", value="45000.00"),
        SimpleNamespace(tag="NetLiquidation", value="50000.00"),
        SimpleNamespace(tag="BuyingPower", value="90000.00"),
    ]
    broker._ib.pnl.return_value = [SimpleNamespace(dailyPnL=125.50)]
    broker._ib.positions.return_value = []

    summary = await broker.get_account_summary()
    assert summary.cash_balance == 45000.0
    assert summary.total_value == 50000.0
    assert summary.buying_power == 90000.0
    assert summary.daily_pnl == 125.50


@pytest.mark.asyncio
async def test_get_universe(broker):
    scan_results = [
        SimpleNamespace(
            contractDetails=SimpleNamespace(
                contract=SimpleNamespace(symbol="SIRI")
            )
        ),
        SimpleNamespace(
            contractDetails=SimpleNamespace(
                contract=SimpleNamespace(symbol="LCID")
            )
        ),
    ]
    broker._ib.reqScannerDataAsync.return_value = scan_results

    tickers = await broker.get_universe(max_price=10.0, min_price=1.0, min_volume=100_000)
    assert tickers == ["SIRI", "LCID"]


@pytest.mark.asyncio
async def test_universe_cache(broker):
    scan_results = [
        SimpleNamespace(
            contractDetails=SimpleNamespace(
                contract=SimpleNamespace(symbol="SIRI")
            )
        ),
    ]
    broker._ib.reqScannerDataAsync.return_value = scan_results

    # First call - hits IB
    await broker.get_universe(max_price=10.0, min_price=1.0, min_volume=100_000)
    # Second call - from cache
    tickers = await broker.get_universe(max_price=10.0, min_price=1.0, min_volume=100_000)

    assert tickers == ["SIRI"]
    # reqScannerDataAsync should only be called once
    assert broker._ib.reqScannerDataAsync.await_count == 1


@pytest.mark.asyncio
async def test_subscribe_unsubscribe(broker):
    mock_ticker = _make_ticker()
    broker._ib.reqMktData.return_value = mock_ticker

    await broker.subscribe_market_data(["SIRI", "LCID"])
    assert "SIRI" in broker._subscribed
    assert "LCID" in broker._subscribed

    await broker.unsubscribe_market_data(["SIRI"])
    assert "SIRI" not in broker._subscribed
    assert "LCID" in broker._subscribed


@pytest.mark.asyncio
async def test_map_order_status():
    from app.broker.ibkr_broker import IBKRBroker

    assert IBKRBroker._map_order_status("Filled") == OrderStatus.FILLED
    assert IBKRBroker._map_order_status("Submitted") == OrderStatus.PENDING
    assert IBKRBroker._map_order_status("Cancelled") == OrderStatus.CANCELLED
    assert IBKRBroker._map_order_status("Inactive") == OrderStatus.REJECTED
    assert IBKRBroker._map_order_status("Unknown") == OrderStatus.PENDING


@pytest.mark.asyncio
async def test_safe_float():
    from app.broker.ibkr_broker import _safe_float

    assert _safe_float(1.5) == 1.5
    assert _safe_float(float("nan")) == 0.0
    assert _safe_float(None) == 0.0
    assert _safe_float(float("nan"), default=99.0) == 99.0
