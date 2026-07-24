"""Tests for production spread predictor."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")


@pytest.fixture
def manifest_path(tmp_path: Path) -> Path:
    manifest = {
        "version": "v21-test",
        "architecture": "residual",
        "target_mode": "delta",
        "in_channels": 18,
        "sequence_timesteps": 1,
        "sequence_channels": 17,
        "patch_size": 64,
        "threshold": 0.5,
        "filter_mode": "any_fire",
        "weights_file": "weights.pt",
        "metrics": {"test_iou": 0.22},
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


@pytest.fixture
def weights_path(tmp_path: Path, manifest_path: Path) -> Path:
    from models.unet_model import ResidualWildfireUNetSmall

    model = ResidualWildfireUNetSmall(in_channels=18)
    out = tmp_path / "weights.pt"
    torch.save(model.state_dict(), out)
    return out


class TestSpreadPredictor:
    def test_from_manifest_predicts_finite(self, manifest_path: Path, weights_path: Path):
        from wildfire_front.ml.spread_predictor import SpreadPredictor

        predictor = SpreadPredictor.from_manifest(manifest_path, weights_path=weights_path)
        seq = np.random.randn(1, 17, 64, 64).astype(np.float32) * 0.1
        current_fire = np.zeros((64, 64), dtype=np.float32)
        current_fire[20:40, 20:40] = 1.0
        pred = predictor.predict(seq, current_fire)
        assert pred.shape == (64, 64)
        assert np.isfinite(pred).all()
        assert pred.min() >= 0.0 and pred.max() <= 1.0

    def test_delta_mode_anchors_to_prev_fire(self, manifest_path: Path, weights_path: Path):
        from wildfire_front.ml.spread_predictor import SpreadPredictor

        predictor = SpreadPredictor.from_manifest(manifest_path, weights_path=weights_path)
        seq = np.zeros((1, 17, 64, 64), dtype=np.float32)
        current_fire = np.zeros((64, 64), dtype=np.float32)
        current_fire[25:35, 25:35] = 1.0
        pred = predictor.predict_binary(seq, current_fire, threshold=0.5)
        assert pred[30, 30] == 1.0

    def test_ensemble_soft_vote(self, manifest_path: Path, weights_path: Path, tmp_path: Path):
        # second random member
        from models.unet_model import ResidualWildfireUNetSmall
        from wildfire_front.ml.spread_predictor import (
            EnsembleSpreadPredictor,
            SpreadModelManifest,
        )

        w2 = tmp_path / "weights2.pt"
        torch.save(ResidualWildfireUNetSmall(in_channels=18).state_dict(), w2)

        manifest = SpreadModelManifest.from_json(manifest_path)
        ens = EnsembleSpreadPredictor(manifest, [weights_path, w2], ensemble_mode="mean_prob")
        assert ens.n_members == 2
        seq = np.random.randn(1, 17, 64, 64).astype(np.float32) * 0.1
        fire = np.zeros((64, 64), dtype=np.float32)
        fire[10:20, 10:20] = 1.0
        pred = ens.predict(seq, fire)
        assert pred.shape == (64, 64)
        assert np.isfinite(pred).all()
        assert pred.min() >= 0.0 and pred.max() <= 1.0

    def test_predict_uncertainty_parity_mean_prob(
        self, manifest_path: Path, weights_path: Path, tmp_path: Path
    ):
        from models.unet_model import ResidualWildfireUNetSmall
        from wildfire_front.ml.spread_predictor import (
            EnsembleSpreadPredictor,
            SpreadModelManifest,
        )

        w2 = tmp_path / "weights2.pt"
        torch.save(ResidualWildfireUNetSmall(in_channels=18).state_dict(), w2)
        manifest = SpreadModelManifest.from_json(manifest_path)
        ens = EnsembleSpreadPredictor(manifest, [weights_path, w2], ensemble_mode="mean_prob")
        rng = np.random.default_rng(0)
        seq = rng.standard_normal((1, 17, 64, 64), dtype=np.float32) * 0.1
        fire = np.zeros((64, 64), dtype=np.float32)
        fire[15:30, 15:30] = 1.0
        pred = ens.predict(seq, fire)
        unc = ens.predict_with_uncertainty(seq, fire)
        assert np.allclose(pred, unc.prob, atol=1e-5)
        assert unc.binary.shape == pred.shape
        # Head A diagnostics present on abs domain
        assert "mean_entropy" in unc.diagnostics
        assert "mean_margin" in unc.diagnostics
        assert unc.diagnostics["n_members"] == 2.0

    def test_predict_uncertainty_parity_mean_abs(
        self, manifest_path: Path, weights_path: Path, tmp_path: Path
    ):
        from models.unet_model import ResidualWildfireUNetSmall
        from wildfire_front.ml.spread_predictor import (
            EnsembleSpreadPredictor,
            SpreadModelManifest,
        )

        w2 = tmp_path / "weights2b.pt"
        torch.save(ResidualWildfireUNetSmall(in_channels=18).state_dict(), w2)
        manifest = SpreadModelManifest.from_json(manifest_path)
        ens = EnsembleSpreadPredictor(manifest, [weights_path, w2], ensemble_mode="mean_abs")
        rng = np.random.default_rng(1)
        seq = rng.standard_normal((1, 17, 64, 64), dtype=np.float32) * 0.1
        fire = np.zeros((64, 64), dtype=np.float32)
        fire[20:40, 20:40] = 1.0
        pred = ens.predict(seq, fire)
        unc = ens.predict_with_uncertainty(seq, fire)
        assert np.allclose(pred, unc.prob, atol=1e-5)

    def test_uncertainty_threshold_only_affects_binary(
        self, manifest_path: Path, weights_path: Path, tmp_path: Path
    ):
        from models.unet_model import ResidualWildfireUNetSmall
        from wildfire_front.ml.spread_predictor import (
            EnsembleSpreadPredictor,
            SpreadModelManifest,
        )

        w2 = tmp_path / "weights2c.pt"
        torch.save(ResidualWildfireUNetSmall(in_channels=18).state_dict(), w2)
        manifest = SpreadModelManifest.from_json(manifest_path)
        ens = EnsembleSpreadPredictor(manifest, [weights_path, w2], ensemble_mode="mean_prob")
        rng = np.random.default_rng(2)
        seq = rng.standard_normal((1, 17, 64, 64), dtype=np.float32) * 0.1
        fire = np.zeros((64, 64), dtype=np.float32)
        fire[10:50, 10:50] = 1.0
        base = ens.predict_with_uncertainty(seq, fire)
        # Non-manifest threshold must not change absolute prob (decode uses manifest thr)
        alt = ens.predict_with_uncertainty(seq, fire, threshold=0.9)
        assert np.allclose(base.prob, alt.prob, atol=1e-5)
        # Binary may differ when threshold differs
        assert alt.binary.shape == base.binary.shape

    def test_single_model_predict_with_uncertainty(self, manifest_path: Path, weights_path: Path):
        from wildfire_front.ml.spread_predictor import SpreadPredictor
        from wildfire_front.ml.uncertainty import LogisticCalibrator

        predictor = SpreadPredictor.from_manifest(manifest_path, weights_path=weights_path)
        rng = np.random.default_rng(3)
        seq = rng.standard_normal((1, 17, 64, 64), dtype=np.float32) * 0.1
        fire = np.zeros((64, 64), dtype=np.float32)
        fire[12:28, 12:28] = 1.0
        pred = predictor.predict(seq, fire)
        cal = LogisticCalibrator(weights=np.array([-2.5, -3.0, 4.0, 0.2], dtype=np.float64))
        unc = predictor.predict_with_uncertainty(
            seq, fire, calibrator=cal, product_id="single_test"
        )
        assert np.allclose(pred, unc.prob, atol=1e-5)
        assert unc.diagnostics["n_members"] == 1.0
        assert unc.diagnostics["member_disagreement"] == 0.0
        assert "mean_entropy" in unc.diagnostics
        assert "mean_margin" in unc.diagnostics
        assert np.isfinite(unc.confidence)
        live = unc.to_ml_live_metrics()
        assert live["schema"] == "ml_live_metrics_v1"
        assert live["n_members"] == 1
        from wildfire_front.ml.uncertainty import build_ml_prediction_document

        doc = build_ml_prediction_document(unc)
        blob = json.dumps(doc).lower()
        for forbidden in (
            "primary_ros",
            "ros_m_min",
            "ros_area_m_min",
            "vp_tactical",
            "speed_median_m_min",
        ):
            assert forbidden not in blob
        # Artifact abstain_threshold is honored when abstain_below omitted
        cal_hi = LogisticCalibrator(
            weights=np.array([-2.5, -3.0, 4.0, 0.2], dtype=np.float64),
            abstain_threshold=0.99,
        )
        unc_hi = predictor.predict_with_uncertainty(seq, fire, calibrator=cal_hi)
        assert unc_hi.abstain is True  # conf almost always < 0.99
