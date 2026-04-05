from app.engine.exit_formula import ExitFormulaConfig, ExitFormulaInputs, ExitFormulaScorer


def _balanced_scorer() -> ExitFormulaScorer:
    return ExitFormulaScorer(
        ExitFormulaConfig(
            l2_weakness_weight=0.40,
            momentum_decay_weight=0.25,
            spread_worsening_weight=0.20,
            pnl_drawdown_from_peak_weight=0.15,
            exit_threshold=0.70,
        )
    )


def test_balanced_exit_formula_triggers_on_clear_weakness():
    result = _balanced_scorer().score(
        ExitFormulaInputs(
            l2_weakness=0.80,
            momentum_decay=0.90,
            spread_worsening=0.85,
            pnl_drawdown_from_peak=0.75,
        )
    )

    assert result.should_exit is True
    assert result.score >= 0.70


def test_balanced_exit_formula_holds_on_mild_noise():
    result = _balanced_scorer().score(
        ExitFormulaInputs(
            l2_weakness=0.10,
            momentum_decay=0.15,
            spread_worsening=0.20,
            pnl_drawdown_from_peak=0.10,
        )
    )

    assert result.should_exit is False
    assert result.score < 0.70
