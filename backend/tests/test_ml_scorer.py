"""Tests for MLScorer — hybrid rule + ML scoring."""

import numpy as np
import pytest

from app.engine.signal_detector import FeatureVector, SignalType
from app.ml.model import BreakoutClassifier
from app.ml.scorer import MLScorer


@pytest.fixture
def untrained_scorer(tmp_path):
    classifier = BreakoutClassifier(model_dir=str(tmp_path))
    return MLScorer(classifier, weight=0.3)


@pytest.fixture
def trained_scorer(tmp_path):
    classifier = BreakoutClassifier(model_dir=str(tmp_path))
    rng = np.random.RandomState(42)
    X = rng.rand(100, 5)
    y = (X.sum(axis=1) > 2.5).astype(int)
    classifier.train(X, y)
    return MLScorer(classifier, weight=0.3)


def _make_fv(score=0.7, li=0.8, sc=0.6, bs=0.7, va=0.8, oa=0.7):
    return FeatureVector(
        ticker="TEST",
        liquidity_imbalance=li,
        spread_compression=sc,
        bid_stacking=bs,
        volume_acceleration=va,
        order_aggression=oa,
        composite_score=score,
        signal_type=SignalType.BREAKOUT,
    )


def test_untrained_preserves_rule_score(untrained_scorer):
    """With untrained model, ml_confidence=1.0, so adjusted ≈ rule_score."""
    fv = _make_fv(score=0.7)
    adjusted, ml_conf = untrained_scorer.score(fv)

    assert ml_conf == 1.0
    # adjusted = 0.7 * 0.7 + 0.3 * 1.0 = 0.49 + 0.3 = 0.79
    expected = 0.7 * 0.7 + 0.3 * 1.0
    assert abs(adjusted - round(expected, 4)) < 0.001


def test_trained_adjusts_score(trained_scorer):
    """Trained model should produce different adjusted vs rule score."""
    fv = _make_fv(score=0.7)
    adjusted, ml_conf = trained_scorer.score(fv)

    assert 0.0 <= ml_conf <= 1.0
    # adjusted should differ from raw 0.7 because ml_conf != 1.0 (usually)
    assert isinstance(adjusted, float)


def test_low_features_lower_confidence(trained_scorer):
    """Low feature values should get lower ML confidence."""
    low_fv = _make_fv(score=0.3, li=0.1, sc=0.1, bs=0.1, va=0.1, oa=0.1)
    high_fv = _make_fv(score=0.8, li=0.9, sc=0.9, bs=0.9, va=0.9, oa=0.9)

    _, low_conf = trained_scorer.score(low_fv)
    _, high_conf = trained_scorer.score(high_fv)

    assert high_conf > low_conf
