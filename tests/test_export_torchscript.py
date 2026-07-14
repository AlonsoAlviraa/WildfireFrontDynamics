"""TorchScript export smoke tests."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")


@pytest.fixture
def production_setup(tmp_path: Path) -> tuple[Path, Path]:
    from models.unet_model import ResidualWildfireUNetSmall

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
        "weights_file": "weights_v21_best.pt",
        "metrics": {},
    }
    prod = tmp_path / "production"
    prod.mkdir()
    (prod / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    model = ResidualWildfireUNetSmall(in_channels=18)
    torch.save(model.state_dict(), prod / "weights_v21_best.pt")
    return prod / "manifest.json", prod / "spread_export.pt"


class TestExportTorchScript:
    def test_export_and_run(self, production_setup: tuple[Path, Path]):
        from wildfire_front.ml.export_torchscript import export_torchscript

        manifest, out_pt = production_setup
        export_torchscript(manifest, out_pt)
        assert out_pt.is_file()
        assert out_pt.with_suffix(".json").is_file()

        loaded = torch.jit.load(str(out_pt))
        seq = torch.randn(1, 1, 17, 64, 64)
        fire = (torch.rand(1, 64, 64) > 0.5).float()
        with torch.no_grad():
            out = loaded(seq, fire)
        assert out.shape == (1, 1, 64, 64)
        assert torch.isfinite(out).all()

    def test_traced_matches_eager(self, production_setup: tuple[Path, Path]):
        from wildfire_front.ml.export_torchscript import export_torchscript
        from wildfire_front.ml.spread_predictor import SpreadPredictor

        manifest, out_pt = production_setup
        export_torchscript(manifest, out_pt)
        predictor = SpreadPredictor.from_manifest(manifest)
        traced = torch.jit.load(str(out_pt))

        seq_np = np.random.randn(1, 17, 64, 64).astype(np.float32) * 0.1
        fire_np = np.zeros((64, 64), dtype=np.float32)
        fire_np[20:40, 20:40] = 1.0

        eager = predictor.predict(seq_np, fire_np)
        with torch.no_grad():
            traced_out = traced(
                torch.from_numpy(seq_np).unsqueeze(0),
                torch.from_numpy(fire_np).unsqueeze(0),
            )
        np.testing.assert_allclose(eager, traced_out[0, 0].numpy(), atol=1e-4)