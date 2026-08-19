"""Tests for WFIGS campaign-to-ML dataset conversion."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from wildfire_front.ml.wfigs_tensor_dataset import (
    WFIGS_CHANNELS,
    WFIGSTensorDatasetBuilder,
)


def _campaign(tmp_path: Path, split: str, event: str, offset: float) -> Path:
    root = tmp_path / split
    sample = root / "samples" / split / f"{event}.npz"
    sample.parent.mkdir(parents=True)
    size = 8
    arrays = {
        name: np.full((size, size), offset + index, dtype=np.float32)
        for index, name in enumerate(WFIGS_CHANNELS)
    }
    arrays["previous_fire"] = np.zeros((size, size), dtype=np.uint8)
    arrays["target_fire"] = np.eye(size, dtype=np.uint8)
    arrays["horizon_hours"] = np.asarray(24.0, dtype=np.float32)
    np.savez_compressed(sample, **arrays)
    inventory = root / "INVENTORY.json"
    inventory.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "pair_id": f"pair-{event}",
                        "event_id": event,
                        "split": split,
                        "status": "materialized",
                        "training_ready": True,
                        "relative_path": sample.relative_to(root).as_posix(),
                        "sha256": "fixture",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return inventory


def test_builder_fits_normalization_on_train_only(tmp_path: Path) -> None:
    train = _campaign(tmp_path, "train", "train-event", 1.0)
    validation = _campaign(tmp_path, "validation", "val-event", 1000.0)
    output = tmp_path / "dataset"
    report = WFIGSTensorDatasetBuilder(
        inventory_paths=[train, validation], output_root=output
    ).build()
    normalization = json.loads(
        (output / "normalization_train_only.json").read_text(encoding="utf-8")
    )
    assert report["counts"]["samples_written"] == 2
    assert normalization["fit_split"] == "train"
    assert normalization["test_used"] is False
    assert max(normalization["channel_max"]) < 1000.0
    assert set(json.loads((output / "train.json").read_text())["events"]) == {
        "train-event"
    }
    assert set(json.loads((output / "validation.json").read_text())["events"]) == {
        "val-event"
    }
