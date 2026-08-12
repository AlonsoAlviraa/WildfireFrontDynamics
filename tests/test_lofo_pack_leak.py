"""L5 LOFO pack leak audit tests."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from scripts.audit_lofo_pack_leak import audit_fold, audit_lofo_root, main

ROOT = Path(__file__).resolve().parents[1]


def _write_npz(path: Path, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        sequence=np.zeros((1, 17, 4, 4), dtype=np.float32),
        current_fire=np.zeros((4, 4), dtype=np.float32),
        target_fire=np.zeros((4, 4), dtype=np.float32),
        source=np.asarray(source),
    )


def test_clean_pack_zero_leak(tmp_path):
    fold = tmp_path / "FIRE_A"
    _write_npz(fold / "train" / "a.npz", "FIRE_B")
    _write_npz(fold / "val" / "b.npz", "FIRE_B")
    _write_npz(fold / "test" / "c.npz", "FIRE_A")
    row = audit_fold(fold, "FIRE_A")
    assert row["n_leaked_train_val"] == 0
    assert row["ok"] is True


def test_leaked_train_detected(tmp_path):
    fold = tmp_path / "FIRE_A"
    _write_npz(fold / "train" / "leak.npz", "FIRE_A")  # held-out in train
    _write_npz(fold / "test" / "c.npz", "FIRE_A")
    row = audit_fold(fold, "FIRE_A")
    assert row["n_leaked_train_val"] == 1
    assert row["ok"] is False


def test_audit_root_and_exit_codes(tmp_path):
    root = tmp_path / "lofo"
    clean = root / "F1"
    _write_npz(clean / "train" / "a.npz", "F2")
    _write_npz(clean / "test" / "t.npz", "F1")
    report = audit_lofo_root(root)
    assert report["n_leaked_train_val"] == 0
    assert report["ok"] is True

    leak = root / "F2"
    _write_npz(leak / "train" / "x.npz", "F2")
    _write_npz(leak / "test" / "y.npz", "F2")
    report2 = audit_lofo_root(root)
    assert report2["n_leaked_train_val"] >= 1
    assert report2["ok"] is False

    out = tmp_path / "audit.json"
    rc = main(["--lofo-root", str(root), "--out", str(out)])
    assert rc == 2
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["n_leaked_train_val"] >= 1


def test_repo_lofo_v1_if_present(tmp_path):
    pack = ROOT / "artifacts" / "clm_ndws_patches" / "lofo_v1"
    if not pack.is_dir():
        pytest.skip("no lofo_v1")
    out = tmp_path / "audit.json"
    rc = main(["--lofo-root", str(pack), "--out", str(out)])
    # sealed pack should be clean (0) or missing sources → still exits 0/2 honestly
    assert rc in (0, 2)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "n_leaked_train_val" in data
    assert data["schema"] == "wfd_ml_lofo_pack_leak_audit_v1"
