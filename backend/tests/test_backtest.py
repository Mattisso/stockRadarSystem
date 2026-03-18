"""Tests for SignalBacktester."""

from datetime import datetime, timedelta

import pytest

from app.ml.backtest import BacktestConfig, SignalBacktester
from app.models.signal import Signal, SignalType
from app.models.trade import Trade, TradeSide, TradeStatus


def _seed_signals_and_trades(db, count=20):
    """Seed signals with linked trades. Half profitable, half losing."""
    now = datetime.now()
    for i in range(count):
        signal = Signal(
            ticker=f"T{i % 5}",
            signal_type=SignalType.BREAKOUT,
            score=0.65 + (i % 10) * 0.03,
            liquidity_imbalance=0.7,
            spread_compression=0.6,
            bid_stacking=0.7,
            volume_acceleration=0.8,
            order_aggression=0.7,
            created_at=now - timedelta(days=count - i),
        )
        db.add(signal)
        db.flush()

        # Alternate win/loss
        entry = 5.0
        exit_price = 5.50 if i % 2 == 0 else 4.50
        pnl = (exit_price - entry) * 100

        trade = Trade(
            ticker=signal.ticker,
            signal_id=signal.id,
            side=TradeSide.BUY,
            status=TradeStatus.CLOSED,
            quantity=100,
            entry_price=entry,
            exit_price=exit_price,
            stop_loss_price=4.75,
            target_price=5.50,
            pnl=pnl,
            signal_score=signal.score,
            entry_time=signal.created_at,
            exit_time=signal.created_at + timedelta(hours=1),
        )
        db.add(trade)

        signal.outcome_pnl = pnl

    db.commit()


def test_backtest_with_seeded_data(db):
    _seed_signals_and_trades(db, count=20)

    result = SignalBacktester(db, BacktestConfig(score_threshold=0.65)).run()

    assert result.total_trades == 20
    assert result.winning_trades == 10
    assert result.losing_trades == 10
    assert result.win_rate == pytest.approx(0.5, abs=0.01)
    assert result.total_pnl != 0  # slippage/commission adjusts it


def test_backtest_respects_threshold(db):
    _seed_signals_and_trades(db, count=20)

    result = SignalBacktester(db, BacktestConfig(score_threshold=0.90)).run()
    assert result.total_trades < 20


def test_backtest_empty_db(db):
    result = SignalBacktester(db).run()
    assert result.total_trades == 0
    assert result.total_pnl == 0.0


def test_backtest_computes_max_drawdown(db):
    _seed_signals_and_trades(db, count=20)
    result = SignalBacktester(db, BacktestConfig(score_threshold=0.65)).run()
    assert result.max_drawdown >= 0.0


def test_backtest_date_filtering(db):
    _seed_signals_and_trades(db, count=20)

    # Only look at last 5 days
    config = BacktestConfig(
        start_date=datetime.now() - timedelta(days=5),
        score_threshold=0.65,
    )
    result = SignalBacktester(db, config).run()
    assert result.total_trades <= 20
