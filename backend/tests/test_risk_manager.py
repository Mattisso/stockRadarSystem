"""Tests for the RiskManager pre-trade checks."""

import pytest

from app.broker.interface import Position
from app.broker.mock_broker import MockBroker
from app.core.config import settings
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


@pytest.mark.asyncio
async def test_approve_trade(risk_manager):
    result = await risk_manager.evaluate_trade(
        ticker="SIRI", entry_price=3.20, signal_score=0.75
    )
    assert isinstance(result, TradeParameters)
    assert result.ticker == "SIRI"
    assert result.quantity > 0
    assert result.stop_loss_price < result.entry_price
    assert result.target_price > result.entry_price


@pytest.mark.asyncio
async def test_position_sizing(risk_manager):
    result = await risk_manager.evaluate_trade(
        ticker="SIRI", entry_price=5.0, signal_score=0.70
    )
    assert isinstance(result, TradeParameters)
    expected_qty = int(settings.max_position_size / 5.0)
    assert result.quantity == expected_qty


@pytest.mark.asyncio
async def test_reject_daily_loss_limit(risk_manager):
    # Simulate exceeding daily loss limit
    risk_manager._daily_pnl = -settings.daily_loss_limit
    result = await risk_manager.evaluate_trade(
        ticker="SIRI", entry_price=3.20, signal_score=0.70
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
        ticker="SIRI", entry_price=3.20, signal_score=0.70
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
        ticker="SIRI", entry_price=3.20, signal_score=0.70
    )
    assert isinstance(result, RiskRejection)
    assert "Already holding" in result.reason


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
