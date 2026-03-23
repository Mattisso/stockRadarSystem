"""Tests for L1 Breakout Detection Engine."""

from datetime import datetime, timedelta

import pytest

from app.broker.interface import Quote
from app.engine.breakout_engine import BreakoutEngine, L1Tick, SymbolTracker


# ── SymbolTracker ────────────────────────────────────────────────────


class TestSymbolTracker:
    def test_push_and_pct_change(self):
        tracker = SymbolTracker(ticker="LCID")
        now = datetime.now()
        tracker.push(L1Tick(price=3.00, volume=100000, timestamp=now - timedelta(seconds=30)))
        tracker.push(L1Tick(price=3.60, volume=120000, timestamp=now))
        # 20% move
        pct = tracker.pct_change(60)
        assert pct == pytest.approx(20.0, rel=0.01)

    def test_pct_change_no_data(self):
        tracker = SymbolTracker(ticker="LCID")
        assert tracker.pct_change(60) == 0.0

    def test_volume_ratio_normal(self):
        tracker = SymbolTracker(ticker="LCID")
        now = datetime.now()
        # Uniform volume over 5 min
        for i in range(300):
            tracker.push(L1Tick(price=3.00, volume=1000, timestamp=now - timedelta(seconds=300 - i)))
        ratio = tracker.volume_ratio(60)
        assert 0.8 <= ratio <= 1.3  # Should be ~1.0

    def test_volume_ratio_spike(self):
        tracker = SymbolTracker(ticker="LCID")
        now = datetime.now()
        # Low volume for 4 min, then high volume for 1 min
        for i in range(240):
            tracker.push(L1Tick(price=3.00, volume=100, timestamp=now - timedelta(seconds=300 - i)))
        for i in range(60):
            tracker.push(L1Tick(price=3.00, volume=1000, timestamp=now - timedelta(seconds=60 - i)))
        ratio = tracker.volume_ratio(60)
        assert ratio > 2.0  # Volume spike

    def test_cooldown(self):
        tracker = SymbolTracker(ticker="LCID")
        assert tracker.can_emit() is True
        tracker.last_event_time = datetime.now()
        assert tracker.can_emit() is False
        tracker.last_event_time = datetime.now() - timedelta(seconds=31)
        assert tracker.can_emit() is True


# ── BreakoutEngine ───────────────────────────────────────────────────


class TestBreakoutEngine:
    def test_ingest_quote(self):
        engine = BreakoutEngine()
        quote = Quote(ticker="LCID", bid=3.47, ask=3.48, last=3.48, volume=100000, timestamp=datetime.now())
        engine.ingest(quote)
        assert engine.active_trackers == 1
        assert len(engine.get_tracker("LCID").ticks) == 1

    def test_scan_empty(self):
        engine = BreakoutEngine()
        events = engine.scan()
        assert events == []

    def test_scan_no_movement(self):
        """Flat price, normal volume → no breakout events."""
        engine = BreakoutEngine()
        now = datetime.now()
        for i in range(20):
            engine.ingest(Quote(
                ticker="FLAT", bid=5.0, ask=5.01, last=5.0,
                volume=1000, timestamp=now - timedelta(seconds=20 - i),
            ))
        events = engine.scan(["FLAT"])
        assert len(events) == 0

    def test_scan_strong_move(self):
        """20%+ price move → should trigger a breakout event."""
        engine = BreakoutEngine()
        now = datetime.now()
        # Build baseline at $3.00
        for i in range(10):
            engine.ingest(Quote(
                ticker="RUNNER", bid=3.0, ask=3.01, last=3.0,
                volume=100000, timestamp=now - timedelta(seconds=50 - i),
            ))
        # Price spikes to $3.75 (25%)
        for i in range(10):
            engine.ingest(Quote(
                ticker="RUNNER", bid=3.75, ask=3.76, last=3.75,
                volume=300000, timestamp=now - timedelta(seconds=10 - i),
            ))
        events = engine.scan(["RUNNER"])
        assert len(events) == 1
        assert events[0].ticker == "RUNNER"
        assert events[0].breakout_score >= 0.3

    def test_scan_volume_surge(self):
        """Volume spike without huge price move → may trigger watching."""
        engine = BreakoutEngine()
        now = datetime.now()
        # Normal volume baseline
        for i in range(200):
            engine.ingest(Quote(
                ticker="VOLSPIKE", bid=2.0, ask=2.01, last=2.0,
                volume=1000, timestamp=now - timedelta(seconds=250 - i),
            ))
        # Volume surges 10x with small price move
        for i in range(50):
            engine.ingest(Quote(
                ticker="VOLSPIKE", bid=2.10, ask=2.11, last=2.10,
                volume=10000, timestamp=now - timedelta(seconds=50 - i),
            ))
        events = engine.scan(["VOLSPIKE"])
        # Should detect the volume surge
        assert len(events) >= 1
        assert events[0].volume_ratio > 2.0

    def test_score_computation(self):
        engine = BreakoutEngine()
        # No movement, no volume → 0
        assert engine._compute_score(0.0, 0.0, 1.0) == 0.0
        # Strong move + volume → high score
        score = engine._compute_score(25.0, 30.0, 3.0)
        assert score >= 0.5
        # Extreme move
        score = engine._compute_score(50.0, 60.0, 5.0)
        assert score >= 0.8

    def test_cooldown_prevents_duplicate_events(self):
        """Same symbol should not emit twice within cooldown period."""
        engine = BreakoutEngine()
        now = datetime.now()
        for i in range(10):
            engine.ingest(Quote(
                ticker="COOL", bid=3.0, ask=3.01, last=3.0,
                volume=100000, timestamp=now - timedelta(seconds=50 - i),
            ))
        for i in range(10):
            engine.ingest(Quote(
                ticker="COOL", bid=3.75, ask=3.76, last=3.75,
                volume=300000, timestamp=now - timedelta(seconds=10 - i),
            ))
        events1 = engine.scan(["COOL"])
        events2 = engine.scan(["COOL"])
        assert len(events1) == 1
        assert len(events2) == 0  # Cooldown blocks re-emit
