"""Tests for CLM ensemble eval helpers."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import torch

from wildfire_front.ml.clm_eval import evaluate_clm_weights
from wildfire_front.ml.unet_train import UNetTrainConfig, build_model

ROOT = Path(__file__).resolve().parents[1]


def _write_tiny_npz(path: Path, fire_frac: float = 0.2) -> None:
    """Match NpzWildfireDataset keys: sequence (T,C,H,W), current_fire, target_fire."""
    rng = np.random.default_rng(0)
    t, c, h, w = 1, 17, 16, 16
    seq = rng.normal(size=(t, c, h, w)).astype(np.float32)
    prev = (rng.random((h, w)) < fire_frac * 0.5).astype(np.float32)
    tgt = prev.copy()
    growth = (rng.random((h, w)) < fire_frac) & (prev < 0.5)
    tgt[growth] = 1.0
    np.savez_compressed(
        path,
        sequence=seq,
        current_fire=prev,
        target_fire=tgt,
        change_fraction=np.float32(float(growth.mean())),
        source=np.array("synthetic"),
    )


def test_evaluate_single_and_ensemble_smoke(tmp_path: Path) -> None:
    data = tmp_path / "test"
    data.mkdir()
    for i in range(6):
        _write_tiny_npz(data / f"p{i}.npz", fire_frac=0.15 + 0.02 * i)

    # Build two tiny random residual models and save weights
    cfg = UNetTrainConfig(architecture="residual", model="small", target_mode="delta")
    # in_ch = T*C+1 = 1*17+1 = 18
    w_paths = []
    for name in ("a.pt", "b.pt"):
        m = build_model(cfg, in_channels=18)
        p = tmp_path / name
        torch.save(m.state_dict(), p)
        w_paths.append(p)

    single = evaluate_clm_weights(w_paths[0], data, max_patches=6)
    assert single["n_patches"] == 6
    assert single["n_members"] == 1
    assert 0.0 <= single["model_iou"] <= 1.0

    ens = evaluate_clm_weights(w_paths, data, max_patches=6, ensemble_mode="mean_prob")
    assert ens["n_members"] == 2
    assert ens["ensemble_mode"] == "mean_prob"
    assert "model_iou_growth" in ens


@pytest.mark.requires_weights
@pytest.mark.skipif(
    not (ROOT / "models" / "clm_specialist" / "weights_v28_clm_ft.pt").is_file(),
    reason="requires_weights: clm_v28 weights missing",
)
def test_v28_baseline_smoke_real_holdout() -> None:
    test_dir = ROOT / "artifacts" / "clm_ndws_patches" / "holdout_v1" / "test"
    if not test_dir.is_dir() or not list(test_dir.glob("*.npz")):
        pytest.skip("holdout test missing")
    w = ROOT / "models" / "clm_specialist" / "weights_v28_clm_ft.pt"
    m = evaluate_clm_weights(w, test_dir, max_patches=20)
    assert m["n_patches"] == 20
    # Specialist should beat copy on average (Δ can be small on 20-patch subset)
    assert m["model_iou"] > 0.1
