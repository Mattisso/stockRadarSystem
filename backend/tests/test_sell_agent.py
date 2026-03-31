"""Tests for the sell-side exit agent."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from app.broker.interface import (
    OrderBook,
    OrderBookLevel,
    OrderResult,
    OrderSide,
    OrderStatus,
    OrderType,
    Quote,
)
from app.broker.mock_broker import MockBroker
from app.data.tick_buffer import MarketSnapshot
from app.engine.sell_agent import OpenPosition, SellAgent
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
def sell_agent(broker):
    return SellAgent(broker=broker, risk_manager=RiskManager(broker))


def _position() -> OpenPosition:
    return OpenPosition(
        ticker="AAPL",
        trade_id=1,
        quantity=10,
        entry_price=10.0,
        stop_loss=9.5,
        target=10.8,
        highest_price=10.0,
        entry_time=datetime.now(),
    )


def _snapshot(
    bid: float,
    ask: float,
    last: float | None = None,
    order_book: OrderBook | None = None,
) -> MarketSnapshot:
    return MarketSnapshot(
        quote=Quote(
            ticker="AAPL",
            bid=bid,
            ask=ask,
            last=last or ask,
            volume=1_000_000,
            timestamp=datetime.now(),
        ),
        order_book=order_book,
        timestamp=datetime.now(),
    )


@pytest.mark.asyncio
async def test_assess_exit_updates_trailing_stop(sell_agent):
    pos = _position()
    assessment = sell_agent.assess_exit(pos, _snapshot(bid=10.6, ask=10.62, last=10.65))
    assert assessment.reason is None
    assert assessment.highest_price == 10.65
    assert assessment.stop_loss > pos.stop_loss


@pytest.mark.asyncio
async def test_assess_exit_triggers_l2_weakness(sell_agent):
    pos = _position()
    order_book = OrderBook(
        ticker="AAPL",
        bids=[OrderBookLevel(price=10.0, size=100) for _ in range(5)],
        asks=[OrderBookLevel(price=10.01, size=1000) for _ in range(5)],
    )
    assessment = sell_agent.assess_exit(pos, _snapshot(bid=9.98, ask=10.0, order_book=order_book))
    assert assessment.reason == "l2_weakness"


@pytest.mark.asyncio
async def test_assess_exit_triggers_time_stop_for_non_proving_trade(sell_agent):
    pos = _position()
    pos.entry_time = datetime.now().replace(microsecond=0)
    stale_snapshot = _snapshot(bid=9.99, ask=10.0, last=10.0)
    stale_snapshot.timestamp = pos.entry_time + timedelta(seconds=21)

    assessment = sell_agent.assess_exit(pos, stale_snapshot)

    assert assessment.reason == "time_stop"


@pytest.mark.asyncio
async def test_execute_exit_closes_trade_and_updates_signal(
    sell_agent, broker, db_session_factory, monkeypatch
):
    monkeypatch.setattr(broker, "submit_order", AsyncMock(return_value=OrderResult(
        order_id="sell-1",
        ticker="AAPL",
        side=OrderSide.SELL,
        quantity=10,
        order_type=OrderType.MARKET,
        status=OrderStatus.FILLED,
        fill_price=10.5,
        filled_quantity=10,
    )))

    db = db_session_factory()
    signal = Signal(
        ticker="AAPL",
        signal_type=SignalType.BREAKOUT,
        score=0.9,
        liquidity_imbalance=0.8,
        spread_compression=0.8,
        bid_stacking=0.8,
        volume_acceleration=0.8,
        order_aggression=0.8,
        ml_confidence=0.5,
    )
    db.add(signal)
    db.flush()
    db.add(
        Trade(
            id=1,
            ticker="AAPL",
            signal_id=signal.id,
            side=TradeSide.BUY,
            status=TradeStatus.FILLED,
            quantity=10,
            entry_price=10.0,
            stop_loss_price=9.5,
            target_price=10.8,
        )
    )
    db.flush()

    closed = await sell_agent.execute_exit(
        db=db,
        position=_position(),
        assessment=sell_agent.assess_exit(_position(), _snapshot(bid=9.4, ask=9.42)),
    )

    trade = db.query(Trade).filter_by(id=1).one()
    db.refresh(signal)
    assert closed is True
    assert trade.status == TradeStatus.CLOSED
    assert trade.exit_price == 10.5
    assert signal.outcome_pnl == 5.0
    db.close()
