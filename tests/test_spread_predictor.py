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