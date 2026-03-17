"""Tests for BreakoutClassifier — train, predict, save/load."""

import numpy as np
import pytest

from app.ml.model import BreakoutClassifier


@pytest.fixture
def classifier(tmp_path):
    return BreakoutClassifier(model_dir=str(tmp_path))


@pytest.fixture
def synthetic_data():
    """Synthetic features (5 cols) and binary labels."""
    rng = np.random.RandomState(42)
    X = rng.rand(100, 5)
    # Label based on sum of features > 2.5
    y = (X.sum(axis=1) > 2.5).astype(int)
    return X, y


def test_cold_start_returns_one(classifier):
    """Untrained model should return 1.0 (pass-through for rule score)."""
    X = np.array([[0.5, 0.5, 0.5, 0.5, 0.5]])
    assert classifier.predict_proba(X) == 1.0


def test_is_trained_false_initially(classifier):
    assert classifier.is_trained is False


def test_train_and_predict(classifier, synthetic_data):
    X, y = synthetic_data
    metrics = classifier.train(X, y)

    assert classifier.is_trained is True
    assert "samples" in metrics
    assert metrics["samples"] == 100

    # Predict on a high-feature sample — should give > 0.5
    high = np.array([[0.9, 0.9, 0.9, 0.9, 0.9]])
    assert classifier.predict_proba(high) > 0.5

    # Predict on a low-feature sample — should give < 0.5
    low = np.array([[0.1, 0.1, 0.1, 0.1, 0.1]])
    assert classifier.predict_proba(low) < 0.5


def test_save_and_load(classifier, synthetic_data, tmp_path):
    X, y = synthetic_data
    classifier.train(X, y)
    path = classifier.save()
    assert path.exists()

    # Load into a new classifier
    new_classifier = BreakoutClassifier(model_dir=str(tmp_path))
    assert new_classifier.load() is True
    assert new_classifier.is_trained is True

    # Predictions should be identical
    sample = np.array([[0.7, 0.7, 0.7, 0.7, 0.7]])
    assert classifier.predict_proba(sample) == new_classifier.predict_proba(sample)


def test_load_returns_false_when_no_model(tmp_path):
    classifier = BreakoutClassifier(model_dir=str(tmp_path / "nonexistent"))
    assert classifier.load() is False


def test_feature_importances(classifier, synthetic_data):
    assert classifier.feature_importances() is None

    X, y = synthetic_data
    classifier.train(X, y)
    importances = classifier.feature_importances()
    assert importances is not None
    assert len(importances) == 5
    assert all(v >= 0 for v in importances.values())
