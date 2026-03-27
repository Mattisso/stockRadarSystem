"""Tests for the buy-side execution agent."""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from app.broker.interface import OrderResult, OrderSide, OrderStatus, OrderType, Quote
from app.broker.mock_broker import MockBroker
from app.data.tick_buffer import MarketSnapshot
from app.engine.buy_agent import BuyAgent
from app.models.signal import Signal, SignalType
from app.models.trade import Trade, TradeSide, TradeStatus
from app.risk.risk_manager import RiskManager


@pytest.fixture
async def broker():
    b = MockBroker(initial_balance=50_000.0)
    await b.connect()
    yield b
    await b.disconnect()


@pytest.fixture
def buy_agent(broker):
    return BuyAgent(broker=broker, risk_manager=RiskManager(broker))


def _snapshot(ticker: str, bid: float = 9.95, ask: float = 10.0) -> MarketSnapshot:
    return MarketSnapshot(
        quote=Quote(
            ticker=ticker,
            bid=bid,
            ask=ask,
            last=ask,
            volume=1_000_000,
            timestamp=datetime.now(),
        ),
        order_book=None,
        timestamp=datetime.now(),
    )


def _signal(db, ticker: str) -> Signal:
    signal = Signal(
        ticker=ticker,
        signal_type=SignalType.BREAKOUT,
        score=0.85,
        liquidity_imbalance=0.8,
        spread_compression=0.8,
        bid_stacking=0.8,
        volume_acceleration=0.8,
        order_aggression=0.8,
        ml_confidence=0.5,
        stage="ready_to_buy",
        reason="test",
    )
    db.add(signal)
    db.flush()
    return signal


@pytest.mark.asyncio
async def test_execute_persists_filled_trade(buy_agent, broker, db_session_factory, monkeypatch):
    monkeypatch.setattr(broker, "submit_order", AsyncMock(return_value=OrderResult(
        order_id="abc123",
        ticker="AAPL",
        side=OrderSide.BUY,
        quantity=820,
        order_type=OrderType.MARKET,
        status=OrderStatus.FILLED,
        fill_price=10.02,
        filled_quantity=820,
    )))

    db = db_session_factory()
    signal = _signal(db, "AAPL")

    outcome = await buy_agent.execute(
        db=db,
        signal_record=signal,
        latest=_snapshot("AAPL"),
        signal_score=0.5,
        stage="ready_to_buy",
    )

    trade = db.query(Trade).filter_by(ticker="AAPL").one()
    db.refresh(signal)

    assert outcome is not None
    assert outcome.trade_id == trade.id
    assert trade.status == TradeStatus.FILLED
    assert trade.side == TradeSide.BUY
    assert signal.acted_on is True
    db.close()


@pytest.mark.asyncio
async def test_execute_skips_duplicate_active_trade(buy_agent, broker, db_session_factory):
    db = db_session_factory()
    signal = _signal(db, "AAPL")
    db.add(
        Trade(
            ticker="AAPL",
            signal_id=signal.id,
            side=TradeSide.BUY,
            status=TradeStatus.PENDING,
            quantity=100,
            entry_price=10.0,
        )
    )
    db.flush()

    result = await buy_agent.execute(
        db=db,
        signal_record=signal,
        latest=_snapshot("AAPL"),
        signal_score=0.8,
        stage="ready_to_buy",
    )

    trades = db.query(Trade).filter_by(ticker="AAPL").all()
    assert result is None
    assert len(trades) == 1
    db.close()


@pytest.mark.asyncio
async def test_execute_retries_pending_then_fills(buy_agent, broker, db_session_factory, monkeypatch):
    pending = OrderResult(
        order_id="pending-1",
        ticker="AAPL",
        side=OrderSide.BUY,
        quantity=880,
        order_type=OrderType.MARKET,
        status=OrderStatus.PENDING,
    )
    filled = OrderResult(
        order_id="filled-2",
        ticker="AAPL",
        side=OrderSide.BUY,
        quantity=880,
        order_type=OrderType.MARKET,
        status=OrderStatus.FILLED,
        fill_price=10.01,
        filled_quantity=880,
    )
    submit = AsyncMock(side_effect=[pending, filled])
    cancel = AsyncMock(return_value=True)
    monkeypatch.setattr(broker, "submit_order", submit)
    monkeypatch.setattr(broker, "cancel_order", cancel)
    monkeypatch.setattr("app.engine.buy_agent.settings.buy_retry_backoff_seconds", 0.0)
    monkeypatch.setattr("app.engine.buy_agent.settings.buy_order_style", "market")

    db = db_session_factory()
    signal = _signal(db, "AAPL")

    outcome = await buy_agent.execute(
        db=db,
        signal_record=signal,
        latest=_snapshot("AAPL"),
        signal_score=0.4,
        stage="ready_to_buy",
    )

    trade = db.query(Trade).filter_by(ticker="AAPL").one()
    assert outcome is not None
    assert submit.await_count == 2
    cancel.assert_awaited_once_with("pending-1")
    assert trade.status == TradeStatus.FILLED
    db.close()
