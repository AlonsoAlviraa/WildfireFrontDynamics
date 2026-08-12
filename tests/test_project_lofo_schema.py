"""E2-P1 clean12_subset projector tests."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from wildfire_front.ml.feature_schema import (
    CLEAN12_SUBSET_N_CHANNELS,
    legacy17_to_clean12_subset_map,
    project_legacy17_to_clean12_subset,
    project_sequence_legacy17_to_clean12_subset,
)

ROOT = Path(__file__).resolve().parents[1]


def test_map_honesty_fields():
    m = legacy17_to_clean12_subset_map()
    assert m["feature_schema"] == "clean12_subset"
    assert m["schema_path_id"] == "E2-P1"
    assert m["in_channels_features"] == 12
    assert m["in_channels_with_prev_fire"] == 13
    assert m["physics14_claim"] is False
    assert m["full_clean12_reemit"] is False
    assert len(m["legacy17_to_clean12_subset"]) == 12


def test_project_shape_and_zeros():
    rng = np.random.default_rng(0)
    ch = rng.standard_normal((17, 8, 8)).astype(np.float32)
    out = project_legacy17_to_clean12_subset(ch)
    assert out.shape == (12, 8, 8)
    # elevation slot 0 is None → zeros
    assert np.allclose(out[0], 0.0)
    # slope maps from legacy 0
    assert np.allclose(out[1], ch[0])
    # vegetation from legacy 11
    assert np.allclose(out[10], ch[11])


def test_project_sequence():
    seq = np.zeros((2, 17, 4, 4), dtype=np.float32)
    seq[:, 0] = 1.0
    seq[:, 11] = 2.0
    out = project_sequence_legacy17_to_clean12_subset(seq)
    assert out.shape == (2, 12, 4, 4)
    assert float(out[0, 1, 0, 0]) == 1.0  # slope
    assert float(out[0, 10, 0, 0]) == 2.0  # veg


def test_rejects_wrong_channels():
    with pytest.raises(ValueError):
        project_sequence_legacy17_to_clean12_subset(np.zeros((1, 12, 4, 4)))


def test_project_script_dry_run(tmp_path):
    from scripts.project_lofo_schema_packs import main, training_summary_stub

    stub = training_summary_stub(tmp_path)
    assert stub["feature_schema"] == "clean12_subset"
    assert stub["schema_path_id"] == "E2-P1"
    assert stub["in_channels"] == 13

    src = ROOT / "artifacts" / "clm_ndws_patches" / "lofo_v1"
    if not src.is_dir():
        pytest.skip("no sealed lofo_v1 packs")
    rc = main(
        [
            "--src-lofo",
            str(src),
            "--out-root",
            str(tmp_path / "out"),
            "--dry-run",
            "--max-files-per-split",
            "2",
            "--folds",
            "CARDOSO",
        ]
    )
    assert rc == 0


def test_project_one_file_if_pack(tmp_path):
    from scripts.project_lofo_schema_packs import _project_one, training_summary_stub

    src_root = ROOT / "artifacts" / "clm_ndws_patches" / "lofo_v1" / "CARDOSO" / "test"
    if not src_root.is_dir():
        pytest.skip("no CARDOSO test npz")
    files = sorted(src_root.glob("*.npz"))
    if not files:
        pytest.skip("empty")
    dst = tmp_path / "x.npz"
    row = _project_one(files[0], dst)
    assert row["in_channels"] == CLEAN12_SUBSET_N_CHANNELS
    assert dst.is_file()
    z = np.load(dst, allow_pickle=True)
    assert z["sequence"].shape[1] == 12
    assert str(z["feature_schema"]) == "clean12_subset"
    stub = training_summary_stub(tmp_path)
    assert stub["in_channels"] == 13
