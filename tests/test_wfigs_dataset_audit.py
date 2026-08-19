"""Integrity checks for assembled WFIGS ML tensors."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from wildfire_front.ml.wfigs_dataset_audit import audit_wfigs_tensor_dataset
from wildfire_front.ml.wfigs_tensor_dataset import WFIGS_CHANNELS


def _write_sample(root: Path, split: str, event: str, value: float) -> dict:
    relative = Path("samples") / split / f"{event}.npz"
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    inputs = np.full((len(WFIGS_CHANNELS), 8, 8), value, dtype=np.float32)
    inputs[0] = 0
    inputs[6] = 1
    extent = np.eye(8, dtype=np.uint8)
    np.savez_compressed(
        path,
        inputs=inputs,
        target_growth=extent,
        target_extent=extent,
        horizon_hours=np.asarray(24.0, dtype=np.float32),
    )
    return {"pair_id": f"pair-{event}", "event_id": event, "sample": relative.as_posix()}


def test_audit_recomputes_train_normalization_and_split_integrity(tmp_path: Path) -> None:
    train = _write_sample(tmp_path, "train", "train-event", 2.0)
    val = _write_sample(tmp_path, "validation", "val-event", 1000.0)
    for split, row in (("train", train), ("validation", val)):
        (tmp_path / f"{split}.json").write_text(
            json.dumps({"split": split, "events": [row["event_id"]], "samples": [row]}),
            encoding="utf-8",
        )
    with np.load(tmp_path / train["sample"], allow_pickle=False) as artifact:
        flat = artifact["inputs"].reshape(len(WFIGS_CHANNELS), -1)
        channel_min = flat.min(axis=1).tolist()
        channel_max = flat.max(axis=1).tolist()
    (tmp_path / "normalization_train_only.json").write_text(
        json.dumps(
            {
                "fit_split": "train",
                "test_used": False,
                "channel_names": list(WFIGS_CHANNELS),
                "channel_min": channel_min,
                "channel_max": channel_max,
                "samples_used": 1,
            }
        ),
        encoding="utf-8",
    )
    report = audit_wfigs_tensor_dataset(tmp_path)
    assert report["status"] == "pass"
    assert report["checks"]["event_disjoint"] is True
    assert report["checks"]["normalization_recomputed_from_train_only"] is True
    assert report["channel_max_all_splits"][1] == 1000.0


def test_audit_rejects_event_leakage(tmp_path: Path) -> None:
    train = _write_sample(tmp_path, "train", "same-event", 2.0)
    val = _write_sample(tmp_path, "validation", "same-event", 3.0)
    val["pair_id"] = "different-pair"
    for split, row in (("train", train), ("validation", val)):
        (tmp_path / f"{split}.json").write_text(
            json.dumps({"split": split, "events": ["same-event"], "samples": [row]}),
            encoding="utf-8",
        )
    report = audit_wfigs_tensor_dataset(tmp_path)
    assert report["status"] == "fail"
    assert report["checks"]["event_disjoint"] is False
    assert "event_split_overlap" in {issue["code"] for issue in report["issues"]}
