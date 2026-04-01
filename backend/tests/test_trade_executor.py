"""Tests for the TradeExecutor orchestrator."""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.broker.interface import OrderBook, OrderBookLevel, Quote
from app.broker.mock_broker import MockBroker
from app.core.config import settings
from app.data.tick_buffer import TickBuffer
from app.engine.buy_agent import BuyExecutionOutcome
from app.engine.execution_state import ExecutionPhase, ManagedExecutionState
from app.engine.signal_detector import SignalDetector
from app.engine.signal_detector import FeatureVector, SignalType
from app.engine.state_machine import SymbolStage
from app.engine.trade_executor import TradeExecutor
from app.models.signal import Signal
from app.models.trade import Trade, TradeSide, TradeStatus
from app.risk.risk_manager import RiskManager


@pytest.fixture
async def broker():
    b = MockBroker(initial_balance=50_000.0)
    await b.connect()
    yield b
    await b.disconnect()


@pytest.fixture
def executor(broker, db_session_factory):
    tick_buffer = TickBuffer(maxlen=100)
    signal_detector = SignalDetector(tick_buffer, minimum_history=10)
    risk_manager = RiskManager(broker)
    return TradeExecutor(
        broker=broker,
        tick_buffer=tick_buffer,
        signal_detector=signal_detector,
        risk_manager=risk_manager,
        db_session_factory=db_session_factory,
    )


@pytest.mark.asyncio
async def test_collect_market_data(executor):
    """Data collection should populate the tick buffer."""
    tickers = ["SIRI", "LCID"]
    await executor.collect_market_data(tickers)
    assert executor.tick_buffer.get_latest("SIRI") is not None
    assert executor.tick_buffer.get_latest("LCID") is not None


@pytest.mark.asyncio
async def test_collect_market_data_builds_history(executor):
    """Multiple collection rounds should build history."""
    for _ in range(15):
        await executor.collect_market_data(["SIRI"])
    assert executor.tick_buffer.has_minimum_history("SIRI", 10)


@pytest.mark.asyncio
async def test_scan_signals_persists_to_db(executor, db_session_factory):
    """After enough history, scanning should persist signals."""
    for _ in range(15):
        await executor.collect_market_data(["SIRI"])

    await executor.scan_signals(["SIRI"])

    db = db_session_factory()
    signals = db.query(Signal).filter_by(ticker="SIRI").all()
    assert len(signals) >= 1
    db.close()


@pytest.mark.asyncio
async def test_scan_signals_skips_insufficient_history(executor, db_session_factory):
    """No signals should be persisted without enough history."""
    await executor.collect_market_data(["SIRI"])  # Only 1 snapshot
    await executor.scan_signals(["SIRI"])

    db = db_session_factory()
    signals = db.query(Signal).all()
    assert len(signals) == 0
    db.close()


@pytest.mark.asyncio
async def test_monitor_positions_no_op_when_empty(executor):
    """Monitor should complete cleanly with no open positions."""
    await executor.monitor_positions()
    assert len(executor._open_positions) == 0


@pytest.mark.asyncio
async def test_full_lifecycle(executor, db_session_factory):
    """Integration: collect data → scan for signals → monitor positions."""
    # Build up history
    for _ in range(20):
        await executor.collect_market_data(["SIRI", "LCID", "SOFI"])

    # Scan signals (may or may not trigger trades depending on mock data)
    await executor.scan_signals(["SIRI", "LCID", "SOFI"])

    # Monitor positions (should handle any state)
    await executor.monitor_positions()

    # Verify DB has signal records
    db = db_session_factory()
    signals = db.query(Signal).all()
    assert len(signals) >= 1

    trades = db.query(Trade).all()
    # Trades may or may not exist depending on signal strength
    assert isinstance(trades, list)
    db.close()


@pytest.mark.asyncio
async def test_scan_signals_tracks_filled_buy(executor, db_session_factory):
    """READY_TO_BUY signals should route through BuyAgent and open tracking."""
    executor.state_machine = SimpleNamespace()
    executor.state_machine.evaluate = AsyncMock(return_value=SimpleNamespace(
        ticker="SIRI",
        stage=SymbolStage.READY_TO_BUY,
        reason="test",
        feature_vector=FeatureVector(
            ticker="SIRI",
            liquidity_imbalance=0.8,
            spread_compression=0.8,
            bid_stacking=0.8,
            volume_acceleration=0.8,
            order_aggression=0.8,
            composite_score=0.85,
            signal_type=SignalType.BREAKOUT,
        ),
    ))

    db = db_session_factory()
    db.add(
        Trade(
            id=7,
            ticker="SIRI",
            side=TradeSide.BUY,
            status=TradeStatus.FILLED,
            quantity=100,
            entry_price=3.21,
            stop_loss_price=3.0,
            target_price=3.45,
        )
    )
    db.commit()
    db.close()

    executor.tick_buffer.push(
        "SIRI",
        SimpleNamespace(
            quote=Quote(
                ticker="SIRI",
                bid=3.19,
                ask=3.21,
                last=3.20,
                volume=1_000_000,
                timestamp=datetime.now(),
            ),
            order_book=None,
            timestamp=datetime.now(),
        ),
    )
    executor.buy_agent.execute = AsyncMock(return_value=BuyExecutionOutcome(
        ticker="SIRI",
        trade_id=7,
        quantity=100,
        fill_price=3.21,
        stop_loss=3.00,
        target=3.45,
        order_id="ord-1",
    ))

    await executor.scan_signals(["SIRI"])

    db = db_session_factory()
    signal = db.query(Signal).filter_by(ticker="SIRI").one()
    trade = db.query(Trade).filter_by(id=7).one()
    assert "SIRI" in executor._open_positions
    assert "SIRI" in executor._execution_states
    assert executor._execution_states["SIRI"].phase == ExecutionPhase.MANAGED
    assert trade.execution_phase == "managed"
    assert trade.entry_order_id == "ord-1"
    assert trade.last_stop_price == 3.0
    assert signal.stage == "ready_to_buy"
    db.close()


@pytest.mark.asyncio
async def test_scan_signals_tracks_bracket_child_ids_in_execution_state(executor, db_session_factory):
    executor.state_machine = SimpleNamespace()
    executor.state_machine.evaluate = AsyncMock(return_value=SimpleNamespace(
        ticker="SIRI",
        stage=SymbolStage.READY_TO_BUY,
        reason="test",
        feature_vector=FeatureVector(
            ticker="SIRI",
            liquidity_imbalance=0.8,
            spread_compression=0.8,
            bid_stacking=0.8,
            volume_acceleration=0.8,
            order_aggression=0.8,
            composite_score=0.85,
            signal_type=SignalType.BREAKOUT,
        ),
    ))

    db = db_session_factory()
    db.add(
        Trade(
            id=8,
            ticker="SIRI",
            side=TradeSide.BUY,
            status=TradeStatus.FILLED,
            quantity=100,
            entry_price=3.21,
            stop_loss_price=3.0,
            target_price=3.45,
        )
    )
    db.commit()
    db.close()

    executor.tick_buffer.push(
        "SIRI",
        SimpleNamespace(
            quote=Quote(
                ticker="SIRI",
                bid=3.19,
                ask=3.21,
                last=3.20,
                volume=1_000_000,
                timestamp=datetime.now(),
            ),
            order_book=None,
            timestamp=datetime.now(),
        ),
    )
    executor.buy_agent.execute = AsyncMock(return_value=BuyExecutionOutcome(
        ticker="SIRI",
        trade_id=8,
        quantity=100,
        fill_price=3.21,
        stop_loss=3.00,
        target=3.45,
        order_id="ord-parent",
        target_order_id="ord-target",
        stop_order_id="ord-stop",
    ))

    await executor.scan_signals(["SIRI"])

    state = executor._execution_states["SIRI"]
    assert state.order_id == "ord-parent"


@pytest.mark.asyncio
async def test_monitor_positions_trails_runner_stop_from_strongest_bid(executor, db_session_factory, monkeypatch):
    db = db_session_factory()
    db.add(
        Trade(
            id=21,
            ticker="SIRI",
            side=TradeSide.BUY,
            status=TradeStatus.FILLED,
            quantity=100,
            entry_price=3.21,
            stop_loss_price=3.00,
            target_price=3.45,
            last_stop_price=3.00,
            execution_phase="runner_mode",
        )
    )
    db.commit()
    db.close()

    executor._open_positions["SIRI"] = SimpleNamespace(
        ticker="SIRI",
        trade_id=21,
        quantity=100,
        entry_price=3.21,
        stop_loss=3.00,
        target=3.45,
        highest_price=3.40,
        entry_time=datetime.now() - timedelta(seconds=30),
    )
    state = executor._execution_states["SIRI"] = ManagedExecutionState(
        ticker="SIRI",
        trade_id=21,
        order_id="parent-21",
        filled_at=datetime.now() - timedelta(seconds=30),
        target_order_id="target-21",
        stop_order_id="stop-21",
        current_stop_price=3.00,
        phase=ExecutionPhase.RUNNER_MODE,
    )
    monkeypatch.setattr(executor.broker, "revise_stop_leg", AsyncMock(return_value=True))

    executor.tick_buffer.push(
        "SIRI",
        SimpleNamespace(
            quote=Quote(
                ticker="SIRI",
                bid=3.36,
                ask=3.37,
                last=3.38,
                volume=1_000_000,
                timestamp=datetime.now(),
            ),
            order_book=OrderBook(
                ticker="SIRI",
                bids=[
                    OrderBookLevel(price=3.36, size=200),
                    OrderBookLevel(price=3.35, size=900),
                    OrderBookLevel(price=3.34, size=700),
                ],
                asks=[
                    OrderBookLevel(price=3.37, size=100),
                    OrderBookLevel(price=3.38, size=90),
                ],
                timestamp=datetime.now(),
            ),
            timestamp=datetime.now(),
        ),
    )

    await executor.monitor_positions()

    revised_stop = round(3.35 * (1.0 - settings.execution_support_buffer_pct), 4)
    executor.broker.revise_stop_leg.assert_awaited_once_with("parent-21", revised_stop)
    assert executor._open_positions["SIRI"].stop_loss == revised_stop
    assert state.current_stop_price == revised_stop

    db = db_session_factory()
    trade = db.query(Trade).filter_by(id=21).one()
    assert trade.last_stop_price == revised_stop
    db.close()


@pytest.mark.asyncio
async def test_monitor_positions_throttles_runner_stop_revisions(executor, monkeypatch):
    executor._open_positions["SIRI"] = SimpleNamespace(
        ticker="SIRI",
        trade_id=22,
        quantity=100,
        entry_price=3.21,
        stop_loss=3.00,
        target=3.45,
        highest_price=3.40,
        entry_time=datetime.now() - timedelta(seconds=30),
    )
    state = executor._execution_states["SIRI"] = ManagedExecutionState(
        ticker="SIRI",
        trade_id=22,
        order_id="parent-22",
        filled_at=datetime.now() - timedelta(seconds=30),
        target_order_id="target-22",
        stop_order_id="stop-22",
        current_stop_price=3.00,
        phase=ExecutionPhase.RUNNER_MODE,
        last_stop_revision_at=datetime.now(),
    )
    revise = AsyncMock(return_value=True)
    monkeypatch.setattr(executor.broker, "revise_stop_leg", revise)

    executor.tick_buffer.push(
        "SIRI",
        SimpleNamespace(
            quote=Quote(
                ticker="SIRI",
                bid=3.36,
                ask=3.37,
                last=3.38,
                volume=1_000_000,
                timestamp=datetime.now(),
            ),
            order_book=OrderBook(
                ticker="SIRI",
                bids=[
                    OrderBookLevel(price=3.36, size=200),
                    OrderBookLevel(price=3.35, size=900),
                    OrderBookLevel(price=3.34, size=700),
                ],
                asks=[
                    OrderBookLevel(price=3.37, size=100),
                    OrderBookLevel(price=3.38, size=90),
                ],
                timestamp=datetime.now(),
            ),
            timestamp=datetime.now(),
        ),
    )

    await executor.monitor_positions()

    revise.assert_not_awaited()
    assert executor._open_positions["SIRI"].stop_loss == 3.298
    assert state.current_stop_price == 3.298


@pytest.mark.asyncio
async def test_monitor_positions_uses_sell_agent_and_closes_position(executor):
    """Exit monitoring should route through SellAgent and drop closed positions."""
    executor._open_positions["SIRI"] = SimpleNamespace(
        ticker="SIRI",
        trade_id=1,
        quantity=100,
        entry_price=3.0,
        stop_loss=2.8,
        target=3.4,
        highest_price=3.1,
        entry_time=datetime.now(),
    )
    executor.tick_buffer.push(
        "SIRI",
        SimpleNamespace(
            quote=Quote(
                ticker="SIRI",
                bid=2.75,
                ask=2.77,
                last=2.76,
                volume=1_000_000,
                timestamp=datetime.now(),
            ),
            order_book=None,
            timestamp=datetime.now(),
        ),
    )
    executor.sell_agent.assess_exit = lambda pos, latest: SimpleNamespace(
        reason="stop_loss",
        current_price=2.75,
        stop_loss=2.8,
        highest_price=3.1,
    )
    executor.sell_agent.execute_exit = AsyncMock(return_value=True)

    await executor.monitor_positions()

    executor.sell_agent.execute_exit.assert_awaited_once()
    assert "SIRI" not in executor._open_positions


@pytest.mark.asyncio
async def test_monitor_positions_promotes_runner_mode(executor):
    executor._open_positions["SIRI"] = SimpleNamespace(
        ticker="SIRI",
        trade_id=7,
        quantity=100,
        entry_price=10.0,
        stop_loss=9.6,
        target=11.0,
        highest_price=10.0,
        entry_time=datetime.now(),
    )
    executor._execution_states["SIRI"] = SimpleNamespace(
        trade_id=7,
        order_id="ord-7",
        phase=ExecutionPhase.MANAGED,
        mark_runner_mode=lambda: setattr(executor._execution_states["SIRI"], "phase", ExecutionPhase.RUNNER_MODE),
    )
    executor.tick_buffer.push(
        "SIRI",
        SimpleNamespace(
            quote=Quote(
                ticker="SIRI",
                bid=10.35,
                ask=10.37,
                last=10.4,
                volume=1_000_000,
                timestamp=datetime.now(),
            ),
            order_book=None,
            timestamp=datetime.now(),
        ),
    )
    executor.broker.cancel_target_leg = AsyncMock(return_value=True)
    executor.broker.revise_stop_leg = AsyncMock(return_value=True)

    await executor.monitor_positions()

    executor.broker.cancel_target_leg.assert_awaited_once_with("ord-7")
    executor.broker.revise_stop_leg.assert_awaited_once_with("ord-7", 10.0)
    assert executor._execution_states["SIRI"].phase == ExecutionPhase.RUNNER_MODE
    assert executor._open_positions["SIRI"].stop_loss >= 10.0


@pytest.mark.asyncio
async def test_monitor_positions_persists_runner_mode(executor, db_session_factory):
    db = db_session_factory()
    db.add(
        Trade(
            id=7,
            ticker="SIRI",
            side=TradeSide.BUY,
            status=TradeStatus.FILLED,
            quantity=100,
            entry_price=10.0,
            stop_loss_price=9.6,
            target_price=11.0,
        )
    )
    db.commit()
    db.close()

    executor._open_positions["SIRI"] = SimpleNamespace(
        ticker="SIRI",
        trade_id=7,
        quantity=100,
        entry_price=10.0,
        stop_loss=9.6,
        target=11.0,
        highest_price=10.0,
        entry_time=datetime.now(),
    )
    state = SimpleNamespace(
        trade_id=7,
        order_id="ord-7",
        phase=ExecutionPhase.MANAGED,
    )
    state.mark_runner_mode = lambda: setattr(state, "phase", ExecutionPhase.RUNNER_MODE)
    executor._execution_states["SIRI"] = state
    executor.tick_buffer.push(
        "SIRI",
        SimpleNamespace(
            quote=Quote(
                ticker="SIRI",
                bid=10.35,
                ask=10.37,
                last=10.4,
                volume=1_000_000,
                timestamp=datetime.now(),
            ),
            order_book=None,
            timestamp=datetime.now(),
        ),
    )
    executor.broker.cancel_target_leg = AsyncMock(return_value=True)
    executor.broker.revise_stop_leg = AsyncMock(return_value=True)

    await executor.monitor_positions()

    db = db_session_factory()
    trade = db.query(Trade).filter_by(id=7).one()
    assert trade.runner_mode == "true"
    assert trade.execution_phase == "runner_mode"
    assert trade.last_stop_price >= 10.0
    db.close()
