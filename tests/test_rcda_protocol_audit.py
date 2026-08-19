from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from scripts.audit_rcda_protocol import audit_sample


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_rcda_audit_detects_cumulative_label_and_test_leakage(tmp_path: Path) -> None:
    inputs_dir = tmp_path / "inputs"
    labels_dir = tmp_path / "labels"
    inputs_dir.mkdir()
    labels_dir.mkdir()
    name = "UID_FIRE_7_2018-01-01.npy"
    inputs = np.zeros((12, 256, 256), dtype=np.float32)
    inputs[0, 100:110, 100:110] = 1.0
    inputs[6:12] = 2.0
    label = inputs[0].astype(bool)
    label[110:112, 100:110] = True
    input_path = inputs_dir / name
    label_path = labels_dir / name
    np.save(input_path, inputs)
    np.save(label_path, label)
    meta = {
        "files": {
            f"inputs/{name}": _hash(input_path),
            f"labels/{name}": _hash(label_path),
        }
    }
    (tmp_path / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

    report = audit_sample(tmp_path)

    assert report["ok"] is True
    assert report["label_semantics"]["observed_public_sample"] == "next_cumulative_extent"
    assert report["label_semantics"]["subtraction_produces_binary_growth_on_public_sample"] is True
    assert report["protocol_findings"]["early_stopping_selects_best_epoch_on_test"] is True
    assert report["protocol_findings"]["eval_script_selects_threshold_on_test"] is True
    assert report["protocol_findings"]["published_test_result_is_sealed"] is False
    assert report["wfd_compatibility"]["numeric_comparison_allowed"] is False
