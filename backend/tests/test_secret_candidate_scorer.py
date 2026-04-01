from datetime import datetime, timezone

from app.engine.l1_feature_engine import L1FeatureSnapshot
from app.engine.secret_candidate_scorer import SecretCandidateScorer


def _snapshot(
    ticker: str,
    *,
    price_velocity_1m: float,
    spread_pct: float,
    quote_rate: float,
    volume_expansion: float,
    buy_pressure: float,
) -> L1FeatureSnapshot:
    return L1FeatureSnapshot(
        ticker=ticker,
        price_velocity_1m=price_velocity_1m,
        spread_pct=spread_pct,
        quote_rate=quote_rate,
        volume_expansion=volume_expansion,
        buy_pressure=buy_pressure,
        last_price=5.0,
        last_updated=datetime.now(tz=timezone.utc),
    )


def test_secret_candidate_scorer_accepts_strong_snapshot():
    scorer = SecretCandidateScorer(
        min_score=0.55,
        max_spread_pct=0.02,
        min_quote_rate=0.10,
        min_buy_pressure=0.45,
        min_volume_expansion=1.10,
    )

    event = scorer.score_snapshot(
        _snapshot(
            "LCID",
            price_velocity_1m=5.5,
            spread_pct=0.004,
            quote_rate=1.2,
            volume_expansion=2.1,
            buy_pressure=0.72,
        )
    )

    assert event is not None
    assert event.breakout_score >= 0.55
    assert "price_velocity" in event.reason_flags
    assert "buy_pressure" in event.reason_flags


def test_secret_candidate_scorer_rejects_wide_spread():
    scorer = SecretCandidateScorer(
        min_score=0.55,
        max_spread_pct=0.02,
        min_quote_rate=0.10,
        min_buy_pressure=0.45,
        min_volume_expansion=1.10,
    )

    event = scorer.score_snapshot(
        _snapshot(
            "SIRI",
            price_velocity_1m=6.0,
            spread_pct=0.05,
            quote_rate=1.0,
            volume_expansion=2.0,
            buy_pressure=0.8,
        )
    )

    assert event is None


def test_secret_candidate_scorer_sorts_candidates():
    scorer = SecretCandidateScorer(
        min_score=0.40,
        max_spread_pct=0.02,
        min_quote_rate=0.10,
        min_buy_pressure=0.30,
        min_volume_expansion=1.0,
    )

    events = scorer.score_snapshots(
        [
            _snapshot(
                "A",
                price_velocity_1m=3.0,
                spread_pct=0.005,
                quote_rate=0.8,
                volume_expansion=1.6,
                buy_pressure=0.5,
            ),
            _snapshot(
                "B",
                price_velocity_1m=7.0,
                spread_pct=0.003,
                quote_rate=1.4,
                volume_expansion=2.2,
                buy_pressure=0.8,
            ),
        ]
    )

    assert [event.ticker for event in events] == ["B", "A"]
