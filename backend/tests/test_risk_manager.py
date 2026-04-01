"""Tests for the RiskManager pre-trade checks."""

from datetime import datetime

import pytest

from app.broker.interface import OrderBook, OrderBookLevel, Position, Quote
from app.broker.mock_broker import MockBroker
from app.core.config import settings
from app.data.tick_buffer import MarketSnapshot
from app.risk.risk_manager import RiskManager, RiskRejection, TradeParameters


@pytest.fixture
async def broker():
    b = MockBroker(initial_balance=50_000.0)
    await b.connect()
    yield b
    await b.disconnect()


@pytest.fixture
def risk_manager(broker):
    return RiskManager(broker)


def _snapshot(
    ticker: str = "SIRI",
    bid: float = 3.19,
    ask: float = 3.20,
    bids: list[tuple[float, int]] | None = None,
) -> MarketSnapshot:
    bids = bids or [(3.19, 1200), (3.18, 900), (3.17, 700)]
    return MarketSnapshot(
        quote=Quote(
            ticker=ticker,
            bid=bid,
            ask=ask,
            last=ask,
            volume=1_000_000,
            timestamp=datetime.now(),
        ),
        order_book=OrderBook(
            ticker=ticker,
            bids=[OrderBookLevel(price=price, size=size) for price, size in bids],
            asks=[
                OrderBookLevel(price=ask, size=400),
                OrderBookLevel(price=round(ask + 0.01, 2), size=350),
                OrderBookLevel(price=round(ask + 0.02, 2), size=300),
            ],
            timestamp=datetime.now(),
        ),
        timestamp=datetime.now(),
    )


@pytest.mark.asyncio
async def test_approve_trade(risk_manager):
    result = await risk_manager.evaluate_trade(
        ticker="SIRI", entry_price=3.20, signal_score=0.75, latest=_snapshot()
    )
    assert isinstance(result, TradeParameters)
    assert result.ticker == "SIRI"
    assert result.quantity > 0
    assert result.stop_loss_price < result.entry_price
    assert result.target_price > result.entry_price


@pytest.mark.asyncio
async def test_position_sizing(risk_manager):
    result = await risk_manager.evaluate_trade(
        ticker="SIRI", entry_price=5.0, signal_score=0.70, latest=_snapshot(bid=4.99, ask=5.0, bids=[(4.99, 1200), (4.98, 900), (4.97, 700)])
    )
    assert isinstance(result, TradeParameters)
    execution_entry = round(5.0 * settings.execution_chase_multiplier, 4)
    support_stop = round(4.99 * (1.0 - settings.execution_support_buffer_pct), 4)
    percent_stop = round(execution_entry * (1.0 - settings.execution_percent_stop_pct), 4)
    chosen_stop = max(support_stop, percent_stop)
    expected_qty = min(
        int(settings.execution_max_dollar_risk // (execution_entry - chosen_stop)),
        int(settings.max_position_size // execution_entry),
    )
    assert result.quantity == expected_qty


@pytest.mark.asyncio
async def test_position_sizing_uses_tighter_support_stop_when_available(risk_manager):
    result = await risk_manager.evaluate_trade(
        ticker="SIRI",
        entry_price=4.0,
        signal_score=0.0,
        latest=_snapshot(bid=3.99, ask=4.0, bids=[(3.99, 1500), (3.98, 500), (3.97, 400)]),
    )
    assert isinstance(result, TradeParameters)
    expected_entry = round(4.0 * settings.execution_chase_multiplier, 4)
    support_stop = round(3.99 * (1.0 - settings.execution_support_buffer_pct), 4)
    percent_stop = round(expected_entry * (1.0 - settings.execution_percent_stop_pct), 4)
    assert result.entry_price == expected_entry
    assert result.stop_loss_price == max(support_stop, percent_stop)


@pytest.mark.asyncio
async def test_reject_daily_loss_limit(risk_manager):
    # Simulate exceeding daily loss limit
    risk_manager._daily_pnl = -settings.daily_loss_limit
    result = await risk_manager.evaluate_trade(
        ticker="SIRI", entry_price=3.20, signal_score=0.70, latest=_snapshot()
    )
    assert isinstance(result, RiskRejection)
    assert "Daily loss limit" in result.reason


@pytest.mark.asyncio
async def test_reject_max_positions(broker, risk_manager):
    # Fill up positions in the broker
    for i in range(settings.max_concurrent_positions):
        ticker = f"T{i:03d}"
        broker._positions[ticker] = Position(
            ticker=ticker, quantity=100, avg_cost=5.0,
            market_value=500.0, unrealized_pnl=0.0,
        )
    result = await risk_manager.evaluate_trade(
        ticker="SIRI", entry_price=3.20, signal_score=0.70, latest=_snapshot()
    )
    assert isinstance(result, RiskRejection)
    assert "Max positions" in result.reason


@pytest.mark.asyncio
async def test_reject_duplicate_ticker(broker, risk_manager):
    broker._positions["SIRI"] = Position(
        ticker="SIRI", quantity=100, avg_cost=3.20,
        market_value=320.0, unrealized_pnl=0.0,
    )
    result = await risk_manager.evaluate_trade(
        ticker="SIRI", entry_price=3.20, signal_score=0.70, latest=_snapshot()
    )
    assert isinstance(result, RiskRejection)
    assert "Already holding" in result.reason


@pytest.mark.asyncio
async def test_reject_when_stop_is_too_wide(risk_manager, monkeypatch):
    monkeypatch.setattr("app.risk.risk_manager.settings.execution_percent_stop_pct", 0.05)
    result = await risk_manager.evaluate_trade(
        ticker="SIRI",
        entry_price=3.20,
        signal_score=0.70,
        latest=_snapshot(bid=2.90, ask=3.20, bids=[(0.50, 1200), (0.49, 900), (0.48, 700)]),
    )
    assert isinstance(result, RiskRejection)
    assert result.reason == "Stop too wide"


def test_check_exit_stop_loss(risk_manager):
    result = risk_manager.check_exit_conditions(
        position=None, current_price=2.80, stop_loss=3.00, target=4.00
    )
    assert result == "stop_loss"


def test_check_exit_take_profit(risk_manager):
    result = risk_manager.check_exit_conditions(
        position=None, current_price=4.10, stop_loss=3.00, target=4.00
    )
    assert result == "take_profit"


def test_check_exit_none(risk_manager):
    result = risk_manager.check_exit_conditions(
        position=None, current_price=3.50, stop_loss=3.00, target=4.00
    )
    assert result is None


def test_record_pnl(risk_manager):
    risk_manager.record_pnl(-50.0)
    risk_manager.record_pnl(-30.0)
    assert risk_manager._daily_pnl == -80.0
