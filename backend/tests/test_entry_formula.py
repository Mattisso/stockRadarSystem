from app.engine.entry_formula import EntryFormulaConfig, EntryFormulaInputs, EntryFormulaScorer


def _balanced_scorer() -> EntryFormulaScorer:
    return EntryFormulaScorer(
        EntryFormulaConfig(
            breakout_score_weight=0.35,
            liquidity_imbalance_weight=0.25,
            bid_stacking_weight=0.15,
            volume_acceleration_weight=0.10,
            order_aggression_weight=0.10,
            ml_confidence_weight=0.05,
            entry_threshold=0.72,
            min_spread_compression=0.55,
            max_spoofing_risk=0.35,
            min_ml_confidence=0.0,
        )
    )


def test_balanced_entry_formula_allows_high_quality_signal():
    result = _balanced_scorer().score(
        EntryFormulaInputs(
            breakout_score=0.86,
            liquidity_imbalance=0.80,
            bid_stacking=0.76,
            spread_compression=0.70,
            volume_acceleration=0.74,
            order_aggression=0.72,
            ml_confidence=0.68,
            spoofing_risk=0.10,
        )
    )

    assert result.allowed is True
    assert result.score >= 0.72
    assert result.veto_reason is None


def test_balanced_entry_formula_vetoes_wide_spread():
    result = _balanced_scorer().score(
        EntryFormulaInputs(
            breakout_score=0.90,
            liquidity_imbalance=0.90,
            bid_stacking=0.90,
            spread_compression=0.40,
            volume_acceleration=0.90,
            order_aggression=0.90,
            ml_confidence=0.90,
            spoofing_risk=0.05,
        )
    )

    assert result.allowed is False
    assert result.veto_reason == "spread_compression_too_low"


def test_balanced_entry_formula_vetoes_high_spoofing():
    result = _balanced_scorer().score(
        EntryFormulaInputs(
            breakout_score=0.90,
            liquidity_imbalance=0.90,
            bid_stacking=0.90,
            spread_compression=0.90,
            volume_acceleration=0.90,
            order_aggression=0.90,
            ml_confidence=0.90,
            spoofing_risk=0.50,
        )
    )

    assert result.allowed is False
    assert result.veto_reason == "spoofing_risk_too_high"
