"""Tests for WildfireMetaLabeler.

Covers:
- Entropy computation (extremes + vectorized consistency)
- Feature matrix shape and stacking order
- Train/predict lifecycle (2-class)
- Degenerate single-class guard (no IndexError)
- Untrained guard raises ValueError
- Save/load round-trip via joblib (preferred) + pickle allowlist
- Determinism (random_state reproducibility)
"""

from __future__ import annotations

import pickle
import tempfile
import warnings
from pathlib import Path

import numpy as np
import pytest

from wildfire_front.ml.meta_labeler import WildfireMetaLabeler


def _make_dummy_features(n: int = 100, seed: int = 0) -> np.ndarray:
    """Build a deterministic (n, 7) feature matrix matching build_features output."""
    rng = np.random.default_rng(seed)
    prob = rng.random(n).clip(1e-06, 1 - 1e-06)
    entropy = -(prob * np.log2(prob) + (1 - prob) * np.log2(1 - prob))
    slope = rng.uniform(0, 45, n)
    aspect = rng.uniform(0, 360, n)
    wind = rng.uniform(0, 20, n)
    hum = rng.uniform(10, 90, n)
    temp = rng.uniform(15, 45, n)
    return np.column_stack([prob, entropy, slope, aspect, wind, hum, temp])


class TestEntropy:
    """Shannon entropy correctness."""

    def test_entropy_extremes(self):
        ml = WildfireMetaLabeler()
        assert float(ml.compute_entropy(np.array([1e-07]))[0]) == pytest.approx(0.0, abs=10 ** (-5))
        assert float(ml.compute_entropy(np.array([1 - 1e-07]))[0]) == pytest.approx(
            0.0, abs=10 ** (-5)
        )
        assert float(ml.compute_entropy(np.array([0.5]))[0]) == pytest.approx(1.0, abs=10 ** (-5))

    def test_entropy_vector_shape_preserved(self):
        ml = WildfireMetaLabeler()
        p = np.linspace(0.01, 0.99, 50)
        e = ml.compute_entropy(p)
        assert e.shape == p.shape
        assert np.all(e >= -1e-09)
        assert np.all(e <= 1.0 + 1e-09)


class TestBuildFeatures:
    """Feature matrix construction."""

    def test_feature_matrix_shape_and_columns(self):
        ml = WildfireMetaLabeler()
        prob = np.full((4, 4), 0.3)
        slope = np.full((4, 4), 10.0)
        aspect = np.full((4, 4), 180.0)
        X = ml.build_features(prob, slope, aspect, wind_speed=5.0, humidity=50.0, temp=30.0)
        assert X.shape == (16, 7)
        assert X[0, 0] == pytest.approx(0.3)
        assert X[0, 2] == pytest.approx(10.0)
        assert X[0, 3] == pytest.approx(180.0)
        assert X[0, 4] == pytest.approx(5.0)
        assert X[0, 5] == pytest.approx(50.0)
        assert X[0, 6] == pytest.approx(30.0)

    def test_scalar_broadcast_vs_array_equivalent(self):
        """Scalar meteorological values must broadcast identically to arrays."""
        ml = WildfireMetaLabeler()
        prob = np.full((2, 2), 0.4)
        slope = np.full((2, 2), 5.0)
        aspect = np.full((2, 2), 90.0)
        X_scalar = ml.build_features(prob, slope, aspect, 5.0, 50.0, 30.0)
        X_array = ml.build_features(
            prob, slope, aspect, np.full(4, 5.0), np.full(4, 50.0), np.full(4, 30.0)
        )
        np.testing.assert_allclose(X_scalar, X_array)


class TestTrainPredict:
    """Lifecycle: train → predict_trustworthiness / predict_probability."""

    def test_train_sets_trained_flag(self):
        ml = WildfireMetaLabeler(n_estimators=5)
        X = _make_dummy_features(50)
        y = (X[:, 0] > 0.5).astype(int)
        assert not ml.is_trained
        ml.train(X, y)
        assert ml.is_trained

    def test_predict_shapes_after_train(self):
        ml = WildfireMetaLabeler(n_estimators=5)
        X = _make_dummy_features(80)
        y = (X[:, 0] > 0.5).astype(int)
        ml.train(X, y)
        trust = ml.predict_trustworthiness(X)
        proba = ml.predict_probability(X)
        assert trust.shape == (80,)
        assert proba.shape == (80,)
        assert np.all((trust == 0) | (trust == 1))
        assert np.all((proba >= 0.0) & (proba <= 1.0))

    def test_predict_before_train_raises(self):
        ml = WildfireMetaLabeler()
        X = _make_dummy_features(10)
        with pytest.raises(ValueError):
            ml.predict_trustworthiness(X)
        with pytest.raises(ValueError):
            ml.predict_probability(X)


class TestSingleClassGuard:
    """Degenerate single-class training must not crash on predict_proba[:, 1]."""

    def test_all_ones_does_not_crash(self):
        ml = WildfireMetaLabeler(n_estimators=5)
        X = _make_dummy_features(40)
        y = np.ones(40, dtype=int)
        ml.train(X, y)
        proba = ml.predict_probability(X)
        trust = ml.predict_trustworthiness(X)
        assert proba.shape == (40,)
        assert np.all(proba == 1.0)
        assert np.all(trust == 1)

    def test_all_zeros_does_not_crash(self):
        ml = WildfireMetaLabeler(n_estimators=5)
        X = _make_dummy_features(40)
        y = np.zeros(40, dtype=int)
        ml.train(X, y)
        proba = ml.predict_probability(X)
        assert np.all(proba == 0.0)


class TestSaveLoad:
    """Joblib round-trip under allowlist; joblib/pickle both path-gated."""

    def test_save_load_roundtrip(self):
        ml = WildfireMetaLabeler(n_estimators=5)
        X = _make_dummy_features(60)
        y = (X[:, 0] > 0.5).astype(int)
        ml.train(X, y)
        before = ml.predict_probability(X)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "meta.pkl"
            written = ml.save(path)
            assert written.suffix == ".joblib"
            assert written.is_file()
            meta_sidecar = written.parent / f"{written.name}.meta.json"
            assert meta_sidecar.is_file()
            loaded = WildfireMetaLabeler.load(path, allowlisted_roots=[root])
            after = loaded.predict_probability(X)
        np.testing.assert_allclose(before, after)
        assert loaded.is_trained

    def test_load_joblib_explicit(self):
        ml = WildfireMetaLabeler(n_estimators=5, random_state=0)
        X = _make_dummy_features(40)
        y = (X[:, 0] > 0.5).astype(int)
        ml.train(X, y)
        before = ml.predict_probability(X)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "meta.joblib"
            ml.save(path)
            loaded = WildfireMetaLabeler.load(path, allowlisted_roots=[root])
            np.testing.assert_allclose(before, loaded.predict_probability(X))

    def test_joblib_outside_allowlist_refused(self):
        """Genuine joblib artifacts outside allowlisted roots must not load."""
        ml = WildfireMetaLabeler(n_estimators=3, random_state=1)
        X = _make_dummy_features(20)
        y = (X[:, 0] > 0.5).astype(int)
        ml.train(X, y)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "meta.joblib"
            ml.save(path)
            with pytest.raises(PermissionError):
                WildfireMetaLabeler.load(path, allowlisted_roots=[root / "not_here"])

    def test_pickle_renamed_as_joblib_still_needs_allowlist(self):
        """Renaming pickle → .joblib must not bypass the path allowlist."""
        ml = WildfireMetaLabeler(n_estimators=3, random_state=1)
        X = _make_dummy_features(20)
        y = (X[:, 0] > 0.5).astype(int)
        ml.train(X, y)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_joblib = root / "evil.joblib"
            with open(fake_joblib, "wb") as f:
                pickle.dump(ml, f)
            with pytest.raises(PermissionError):
                WildfireMetaLabeler.load(fake_joblib, allowlisted_roots=[root / "not_here"])
            loaded = WildfireMetaLabeler.load(fake_joblib, allowlisted_roots=[root])
            assert loaded.is_trained

    def test_pickle_outside_allowlist_refused(self):
        """Legacy pickle must not load from arbitrary temp paths."""
        ml = WildfireMetaLabeler(n_estimators=3, random_state=1)
        X = _make_dummy_features(20)
        y = (X[:, 0] > 0.5).astype(int)
        ml.train(X, y)
        with tempfile.TemporaryDirectory() as tmp:
            pkl_path = Path(tmp) / "legacy.pkl"
            with open(pkl_path, "wb") as f:
                pickle.dump(ml, f)
            with pytest.raises(PermissionError):
                WildfireMetaLabeler.load(pkl_path, allowlisted_roots=[Path(tmp) / "not_here"])

    def test_pickle_under_allowlist_loads_with_warning(self):
        ml = WildfireMetaLabeler(n_estimators=3, random_state=2)
        X = _make_dummy_features(20)
        y = (X[:, 0] > 0.5).astype(int)
        ml.train(X, y)
        before = ml.predict_probability(X)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "models"
            root.mkdir()
            pkl_path = root / "legacy.pkl"
            with open(pkl_path, "wb") as f:
                pickle.dump(ml, f)
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                loaded = WildfireMetaLabeler.load(pkl_path, allowlisted_roots=[root])
            assert any("pickle" in str(w.message).lower() for w in caught)
            np.testing.assert_allclose(before, loaded.predict_probability(X))

    def test_allow_pickle_false_refuses_pkl(self):
        """allow_pickle=False blocks .pkl even under an allowlisted root."""
        ml = WildfireMetaLabeler(n_estimators=3, random_state=3)
        X = _make_dummy_features(20)
        y = (X[:, 0] > 0.5).astype(int)
        ml.train(X, y)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pkl_path = root / "legacy.pkl"
            with open(pkl_path, "wb") as f:
                pickle.dump(ml, f)
            with pytest.raises(PermissionError):
                WildfireMetaLabeler.load(pkl_path, allowlisted_roots=[root], allow_pickle=False)
            joblib_path = root / "ok.joblib"
            ml.save(joblib_path)
            loaded = WildfireMetaLabeler.load(
                joblib_path, allowlisted_roots=[root], allow_pickle=False
            )
            assert loaded.is_trained


class TestFailClosedDeserialization:
    """is_trained=True without model must raise (Issue 8 residual)."""

    def test_trained_without_model_raises(self):
        with pytest.raises(ValueError) as ctx:
            WildfireMetaLabeler._from_payload(
                {
                    "is_trained": True,
                    "model": None,
                    "single_class_label": None,
                    "n_estimators": 5,
                    "max_depth": 3,
                    "random_state": 0,
                }
            )
        assert "fail-closed" in str(ctx.value).lower()


class TestDeterminism:
    """Same random_state → identical predictions across instances."""

    def test_reproducible_with_same_seed(self):
        X = _make_dummy_features(70)
        y = (X[:, 0] > 0.5).astype(int)
        ml1 = WildfireMetaLabeler(n_estimators=8, random_state=123)
        ml2 = WildfireMetaLabeler(n_estimators=8, random_state=123)
        ml1.train(X, y)
        ml2.train(X, y)
        np.testing.assert_allclose(ml1.predict_probability(X), ml2.predict_probability(X))


class TestEnhancedFeatures:
    """Sprint 2: build_enhanced_features adds 4 spatial context columns."""

    def test_enhanced_shape_is_12_columns(self):
        ml = WildfireMetaLabeler()
        prob = np.full((4, 4), 0.3)
        slope = np.full((4, 4), 10.0)
        aspect = np.full((4, 4), 180.0)
        X = ml.build_enhanced_features(
            prob, slope, aspect, wind_speed=5.0, humidity=50.0, temp=30.0
        )
        assert X.shape == (16, 12)

    def test_enhanced_includes_base_columns(self):
        ml = WildfireMetaLabeler()
        prob = np.full((2, 2), 0.4)
        slope = np.full((2, 2), 5.0)
        aspect = np.full((2, 2), 90.0)
        X_base = ml.build_features(prob, slope, aspect, 5.0, 50.0, 30.0)
        X_enh = ml.build_enhanced_features(
            prob, slope, aspect, wind_speed=5.0, humidity=50.0, temp=30.0
        )
        np.testing.assert_allclose(X_enh[:, :7], X_base)

    def test_enhanced_burning_density_column(self):
        """Column 10 (index 10) = burning_density."""
        ml = WildfireMetaLabeler()
        prob = np.array([0.5] * 8)
        slope = np.array([10.0] * 8)
        aspect = np.array([180.0] * 8)
        bn = np.array([1, 1, 0, 0, 1, 0, 0, 1], dtype=np.float64)
        X = ml.build_enhanced_features(
            prob, slope, aspect, wind_speed=5.0, humidity=50.0, temp=30.0, burning_neighbors=bn
        )
        assert X[0, 10] == pytest.approx(0.5, abs=10 ** (-5))
        assert X[0, 11] == pytest.approx(0.0, abs=10 ** (-5))
        assert X[0, 9] == pytest.approx(0.5, abs=10 ** (-5))

    def test_enhanced_prob_gradient_nonzero(self):
        """When probabilities vary, prob_gradient must be > 0."""
        ml = WildfireMetaLabeler()
        prob = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8])
        slope = np.full(8, 10.0)
        aspect = np.full(8, 180.0)
        X = ml.build_enhanced_features(
            prob, slope, aspect, wind_speed=5.0, humidity=50.0, temp=30.0
        )
        assert X[0, 11] > 0.0

    def test_enhanced_train_predict_works(self):
        """Enhanced features must be trainable end-to-end."""
        ml = WildfireMetaLabeler(n_estimators=5, max_depth=3)
        rng = np.random.default_rng(42)
        n = 50
        X = rng.random((n, 12))
        y = (X[:, 0] > 0.5).astype(int)
        ml.train(X, y)
        assert ml.is_trained
        preds = ml.predict_trustworthiness(X)
        assert preds.shape == (n,)
