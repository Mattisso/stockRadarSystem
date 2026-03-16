"""Tests for the TradeExecutor orchestrator."""

import pytest

from app.broker.mock_broker import MockBroker
from app.data.tick_buffer import TickBuffer
from app.engine.signal_detector import SignalDetector
from app.engine.trade_executor import TradeExecutor
from app.models.signal import Signal
from app.models.trade import Trade
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
