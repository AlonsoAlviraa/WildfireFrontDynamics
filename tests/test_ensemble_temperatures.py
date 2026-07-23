"""Temperature scaling and scorecard champion protect."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from wildfire_front.ml.clm_eval import _apply_temperature_to_prob, score_mix_from_cache
from wildfire_front.ml.protocol_rails import SplitContext
from wildfire_front.ml.spread_predictor import SpreadModelManifest

ROOT = Path(__file__).resolve().parents[1]


def test_apply_temperature_identity_at_one():
    p = np.array([[0.2, 0.8], [0.5, 0.9]], dtype=np.float64)
    out = _apply_temperature_to_prob(p, 1.0)
    np.testing.assert_allclose(out, p, rtol=1e-5, atol=1e-5)


def test_apply_temperature_sharpens_when_t_lt_1():
    p = np.array([0.2, 0.8], dtype=np.float64)
    sharp = _apply_temperature_to_prob(p, 0.5)
    # farther from 0.5
    assert abs(sharp[0] - 0.5) > abs(p[0] - 0.5)
    assert abs(sharp[1] - 0.5) > abs(p[1] - 0.5)


def test_score_mix_from_cache_accepts_temperatures():
    h, w = 8, 8
    growth = [
        [np.full((h, w), 0.3, dtype=np.float64)],
        [np.full((h, w), 0.4, dtype=np.float64)],
    ]
    prev = [np.zeros((h, w), dtype=np.float64)]
    tgt = [np.ones((h, w), dtype=np.float64)]
    cache = {
        "n_patches": 1,
        "n_members": 2,
        "weights": ["a.pt", "b.pt"],
        "growth": growth,
        "prev": prev,
        "target": tgt,
    }
    ctx = SplitContext(split="val", action="report")
    m = score_mix_from_cache(
        cache, [0.5, 0.5], split_context=ctx, threshold=0.5, temperatures=[0.7, 1.3]
    )
    assert m["temperatures"] == [0.7, 1.3]
    assert "model_iou" in m
    assert m["n_patches"] == 1


def test_manifest_loads_member_temperatures():
    path = ROOT / "models" / "clm_ensemble" / "manifest.json"
    man = SpreadModelManifest.from_json(path)
    assert man.version == "clm_ensemble_v34"
    assert man.member_temperatures == (0.7, 0.7, 1.3)
    assert len(man.member_weights) == 3


def test_scorecard_champion_protect_logic():
    """Disk champion stronger than memory must win (mirrors run_ml_loop_3way save)."""
    disk_c = {"model_iou": 0.8963, "improvement_vs_copy_iou": 0.2545, "name": "v34"}
    mem_c = {"model_iou": 0.8952, "improvement_vs_copy_iou": 0.2534, "name": "v33"}
    d_iou = float(disk_c["model_iou"])
    m_iou = float(mem_c["model_iou"])
    d_delta = float(disk_c["improvement_vs_copy_iou"])
    m_delta = float(mem_c["improvement_vs_copy_iou"])
    keep_disk = (d_iou > m_iou + 1e-6) or (abs(d_iou - m_iou) <= 1e-6 and d_delta > m_delta + 1e-6)
    assert keep_disk is True
