from datetime import datetime, timedelta, timezone

import pytest

from app.engine.secret_candidate_scorer import SecretCandidateScorer
from app.engine.secret_replay_validator import SecretReplayValidator, build_replay_quote


@pytest.mark.asyncio
async def test_secret_replay_validator_runs_real_scoring_and_queue_flow():
    start = datetime.now(tz=timezone.utc) - timedelta(seconds=70)
    quotes = []
    for idx in range(20):
        last = 3.00 + (idx * 0.02)
        quotes.append(
            build_replay_quote(
                ticker="LCID",
                bid=last - 0.005,
                ask=last + 0.005,
                last=last,
                volume=20_000 + (idx * 5_000),
                timestamp=start + timedelta(seconds=idx * 4),
            )
        )

    validator = SecretReplayValidator(
        scorer=SecretCandidateScorer(
            min_score=0.1,
            max_spread_pct=0.02,
            min_quote_rate=0.05,
            min_buy_pressure=0.2,
            min_volume_expansion=1.0,
        ),
        max_active=4,
        max_queue_size=10,
    )

    result = await validator.run(quotes)

    assert len(result.snapshots) == 1
    assert result.snapshots[0]["ticker"] == "LCID"
    assert len(result.candidates) == 1
    assert result.candidates[0]["ticker"] == "LCID"
    assert len(result.handoffs) == 1
    assert result.handoffs[0]["ticker"] == "LCID"
    assert result.promoted_tickers == ["LCID"]
    assert result.queue["active_tickers"] == ["LCID"]
