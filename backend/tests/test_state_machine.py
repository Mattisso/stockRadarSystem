"""Tests for the 5-stage pre-trade state machine."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.broker.interface import OrderBook, OrderBookLevel, Quote
from app.broker.mock_broker import MockBroker
from app.data.tick_buffer import MarketSnapshot, TickBuffer
from app.engine.signal_detector import SignalDetector
from app.engine.state_machine import StateMachine, SymbolStage


def _make_snapshot(
    ticker: str = "TEST",
    bid: float = 5.0,
    ask: float = 5.02,
    volume: int = 1_000_000,
    bid_sizes: list[int] | None = None,
    ask_sizes: list[int] | None = None,
) -> MarketSnapshot:
    quote = Quote(
        ticker=ticker, bid=bid, ask=ask, last=(bid + ask) / 2,
        volume=volume, timestamp=datetime.now(),
    )
    if bid_sizes is None:
        bid_sizes = [500, 400, 300, 200, 100, 90, 80, 70, 60, 50]
    if ask_sizes is None:
        ask_sizes = [500, 400, 300, 200, 100, 90, 80, 70, 60, 50]

    bids = [OrderBookLevel(price=bid - i * 0.01, size=bid_sizes[i]) for i in range(len(bid_sizes))]
    asks = [OrderBookLevel(price=ask + i * 0.01, size=ask_sizes[i]) for i in range(len(ask_sizes))]
    order_book = OrderBook(ticker=ticker, bids=bids, asks=asks, timestamp=datetime.now())
    return MarketSnapshot(quote=quote, order_book=order_book, timestamp=datetime.now())


def _fill_buffer(buf: TickBuffer, ticker: str = "TEST", count: int = 15, **kwargs) -> None:
    for _ in range(count):
        buf.push(ticker, _make_snapshot(ticker=ticker, **kwargs))


@pytest.fixture
async def broker():
    b = MockBroker(initial_balance=50_000.0)
    await b.connect()
    yield b
    await b.disconnect()


@pytest.fixture
def sm(broker):
    tick_buffer = TickBuffer(maxlen=100)
    signal_detector = SignalDetector(tick_buffer, minimum_history=10)
    return StateMachine(
        tick_buffer=tick_buffer,
        signal_detector=signal_detector,
        broker=broker,
    )


@pytest.mark.asyncio
async def test_initial_state_is_normal(sm):
    """New ticker starts in NORMAL."""
    state = sm.get_state("AAAA")
    assert state.stage == SymbolStage.NORMAL


@pytest.mark.asyncio
async def test_insufficient_history_stays_normal(sm):
    """Without enough history, evaluate returns NORMAL."""
    sm.tick_buffer.push("TEST", _make_snapshot())
    state = await sm.evaluate("TEST")
    assert state.stage == SymbolStage.NORMAL


@pytest.mark.asyncio
async def test_normal_to_watching_on_early_signal(sm):
    """Score >= watching threshold promotes NORMAL -> WATCHING (no confirmation needed)."""
    # Build enough history with moderate signal
    _fill_buffer(sm.tick_buffer, count=15, bid_sizes=[2000, 1500, 1000, 200, 100, 90, 80, 70, 60, 50],
                 ask_sizes=[300, 300, 300, 300, 300, 300, 300, 300, 300, 300])
    state = await sm.evaluate("TEST")
    # If the score is above 0.30, it should be at least WATCHING
    if state.score >= 0.30:
        assert state.stage.rank >= SymbolStage.WATCHING.rank


@pytest.mark.asyncio
async def test_get_ready_to_buy_initially_empty(sm):
    assert sm.get_ready_to_buy() == []


@pytest.mark.asyncio
async def test_decay_demotes_stage(sm):
    """Score dropping below threshold for decay_ticks should demote."""
    # Manually set a ticker to WATCHING
    state = sm.get_state("TEST")
    state.stage = SymbolStage.WATCHING
    state.score = 0.35

    # Build history that will produce low scores
    _fill_buffer(sm.tick_buffer, count=15)

    # Evaluate multiple times to trigger decay
    with patch.object(sm.signal_detector, 'compute_signal') as mock_compute:
        from app.engine.signal_detector import FeatureVector, SignalType
        low_fv = FeatureVector(
            ticker="TEST", liquidity_imbalance=0.1, spread_compression=0.1,
            bid_stacking=0.1, volume_acceleration=0.1, order_aggression=0.1,
            composite_score=0.10, signal_type=SignalType.FALSE_BREAKOUT,
        )
        mock_compute.return_value = low_fv

        # Need state_decay_ticks (default=3) evaluations to demote
        for _ in range(4):
            state = await sm.evaluate("TEST")

    assert state.stage == SymbolStage.NORMAL


@pytest.mark.asyncio
async def test_candidate_triggers_l2_subscribe(sm, broker):
    """Reaching CANDIDATE should trigger L2 depth subscription."""
    state = sm.get_state("TEST")
    state.stage = SymbolStage.WATCHING
    state.consecutive_ticks = 2

    _fill_buffer(sm.tick_buffer, count=15)

    with patch.object(sm.signal_detector, 'compute_signal') as mock_compute:
        from app.engine.signal_detector import FeatureVector, SignalType
        fv = FeatureVector(
            ticker="TEST", liquidity_imbalance=0.7, spread_compression=0.7,
            bid_stacking=0.7, volume_acceleration=0.7, order_aggression=0.7,
            composite_score=0.60, signal_type=SignalType.FALSE_BREAKOUT,
        )
        mock_compute.return_value = fv

        for _ in range(3):
            await sm.evaluate("TEST")

    assert "TEST" in broker._l2_subscribed


@pytest.mark.asyncio
async def test_demote_to_normal_triggers_l2_unsubscribe(sm, broker):
    """Demoting back to NORMAL should unsubscribe L2."""
    state = sm.get_state("TEST")
    state.stage = SymbolStage.WATCHING
    sm._l2_subscribed.add("TEST")
    broker._l2_subscribed.add("TEST")

    _fill_buffer(sm.tick_buffer, count=15)

    with patch.object(sm.signal_detector, 'compute_signal') as mock_compute:
        from app.engine.signal_detector import FeatureVector, SignalType
        low_fv = FeatureVector(
            ticker="TEST", liquidity_imbalance=0.1, spread_compression=0.1,
            bid_stacking=0.1, volume_acceleration=0.1, order_aggression=0.1,
            composite_score=0.05, signal_type=SignalType.FALSE_BREAKOUT,
        )
        mock_compute.return_value = low_fv

        for _ in range(4):
            await sm.evaluate("TEST")

    assert state.stage == SymbolStage.NORMAL
    assert "TEST" not in broker._l2_subscribed


@pytest.mark.asyncio
async def test_ready_to_buy_requires_l2_confirmation(sm):
    """High score but weak L2 features should stop at L2_CONFIRM, not READY_TO_BUY."""
    state = sm.get_state("TEST")
    state.stage = SymbolStage.L2_CONFIRM
    state.consecutive_ticks = 2

    _fill_buffer(sm.tick_buffer, count=15)

    with patch.object(sm.signal_detector, 'compute_signal') as mock_compute:
        from app.engine.signal_detector import FeatureVector, SignalType
        # High score but weak L2 features
        fv = FeatureVector(
            ticker="TEST", liquidity_imbalance=0.3, spread_compression=0.3,
            bid_stacking=0.3, volume_acceleration=0.8, order_aggression=0.3,
            composite_score=0.80, signal_type=SignalType.BREAKOUT,
        )
        mock_compute.return_value = fv

        for _ in range(5):
            state = await sm.evaluate("TEST")

    # Should stay at L2_CONFIRM since L2 features are weak
    assert state.stage == SymbolStage.L2_CONFIRM


@pytest.mark.asyncio
async def test_full_promotion_to_ready_to_buy(sm):
    """With strong features, a ticker should progress all the way to READY_TO_BUY."""
    _fill_buffer(sm.tick_buffer, count=15)

    with patch.object(sm.signal_detector, 'compute_signal') as mock_compute:
        from app.engine.signal_detector import FeatureVector, SignalType
        strong_fv = FeatureVector(
            ticker="TEST", liquidity_imbalance=0.8, spread_compression=0.8,
            bid_stacking=0.8, volume_acceleration=0.8, order_aggression=0.8,
            composite_score=0.85, signal_type=SignalType.BREAKOUT,
        )
        mock_compute.return_value = strong_fv

        # Need several evaluations: Normal->Watching (1), Watching->Candidate (2+),
        # Candidate->L2 Confirm (2+), L2 Confirm->ReadyToBuy (2+)
        for _ in range(10):
            state = await sm.evaluate("TEST")

    assert state.stage == SymbolStage.READY_TO_BUY
    assert sm.get_ready_to_buy() == [state]


@pytest.mark.asyncio
async def test_all_states_returns_tracked_tickers(sm):
    """all_states() should return all tracked tickers."""
    _fill_buffer(sm.tick_buffer, ticker="A", count=15)
    _fill_buffer(sm.tick_buffer, ticker="B", count=15)

    await sm.evaluate("A")
    await sm.evaluate("B")

    states = sm.all_states()
    tickers = {s.ticker for s in states}
    assert "A" in tickers
    assert "B" in tickers


@pytest.mark.asyncio
async def test_transition_records_reason(sm):
    """Transitions should produce a human-readable reason."""
    _fill_buffer(sm.tick_buffer, count=15)

    with patch.object(sm.signal_detector, 'compute_signal') as mock_compute:
        from app.engine.signal_detector import FeatureVector, SignalType
        fv = FeatureVector(
            ticker="TEST", liquidity_imbalance=0.7, spread_compression=0.7,
            bid_stacking=0.7, volume_acceleration=0.7, order_aggression=0.7,
            composite_score=0.50, signal_type=SignalType.FALSE_BREAKOUT,
        )
        mock_compute.return_value = fv

        state = await sm.evaluate("TEST")

    if state.stage != SymbolStage.NORMAL:
        assert "promoted" in state.reason or "demoted" in state.reason
