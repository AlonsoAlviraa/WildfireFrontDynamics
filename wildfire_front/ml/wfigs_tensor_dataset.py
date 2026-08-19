"""Build an event-disjoint ML dataset from audited WFIGS tensor campaigns."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from wildfire_front.open_if.regional.base import _atomic_write_json, utc_now
from wildfire_front.open_if.regional.wfigs_materialize import _atomic_savez
from wildfire_front.open_if.regional.wfigs_rights import wfigs_rights_summary

WFIGS_DATASET_SCHEMA = "wfd_wfigs_tensor_dataset_v1"
WFIGS_CHANNELS = (
    "previous_fire",
    "dem",
    "blue",
    "green",
    "red",
    "ndvi",
    "valid_data",
    "wind_speed",
    "wind_direction_rad",
    "temperature_k",
    "precipitation_mm",
    "humidity_pct",
    "air_density",
)


def _artifact_path(inventory_path: Path, row: dict[str, Any]) -> Path:
    relative = row.get("campaign_relative_path") or row.get("relative_path")
    if not relative:
        raise ValueError("materialized row has no relative artifact path")
    return inventory_path.parent / str(relative)


def _validate_arrays(
    artifact: np.lib.npyio.NpzFile,
) -> tuple[np.ndarray, np.ndarray, float]:
    missing = [
        name
        for name in (*WFIGS_CHANNELS, "target_fire", "horizon_hours")
        if name not in artifact
    ]
    if missing:
        raise ValueError(f"artifact missing arrays: {', '.join(missing)}")
    inputs = np.stack(
        [np.asarray(artifact[name], dtype=np.float32) for name in WFIGS_CHANNELS]
    )
    target = np.asarray(artifact["target_fire"], dtype=np.uint8)
    if inputs.ndim != 3 or target.shape != inputs.shape[1:]:
        raise ValueError("inconsistent WFIGS tensor shapes")
    if not np.isfinite(inputs).all():
        raise ValueError("WFIGS inputs contain non-finite values")
    horizon_hours = float(np.asarray(artifact["horizon_hours"]).item())
    if not np.isfinite(horizon_hours) or not 0.0 < horizon_hours <= 48.0:
        raise ValueError("invalid WFIGS horizon_hours")
    return inputs, target, horizon_hours


class WFIGSTensorDatasetBuilder:
    """Merge campaign artifacts without fitting any statistic on VAL or TEST."""

    def __init__(self, *, inventory_paths: list[Path], output_root: Path) -> None:
        if not inventory_paths:
            raise ValueError("at least one campaign inventory is required")
        self.inventory_paths = [Path(path) for path in inventory_paths]
        self.output_root = Path(output_root)

    def _rows(self) -> list[tuple[Path, dict[str, Any]]]:
        rows: list[tuple[Path, dict[str, Any]]] = []
        for path in self.inventory_paths:
            document = json.loads(path.read_text(encoding="utf-8"))
            for row in document.get("rows") or []:
                if row.get("status") == "materialized" and row.get("training_ready") is True:
                    rows.append((path, row))
        return rows

    def build(self) -> dict[str, Any]:
        rows = self._rows()
        if not rows:
            raise ValueError("campaigns contain no training-ready tensors")
        by_split_events: dict[str, set[str]] = defaultdict(set)
        for _path, row in rows:
            by_split_events[str(row["split"])].add(str(row["event_id"]))
        splits = sorted(by_split_events)
        for index, first in enumerate(splits):
            for second in splits[index + 1 :]:
                overlap = by_split_events[first] & by_split_events[second]
                if overlap:
                    raise ValueError(f"event overlap between {first} and {second}: {sorted(overlap)[:3]}")

        output_rows: list[dict[str, Any]] = []
        failure_counts: Counter[str] = Counter()
        channel_min = np.full(len(WFIGS_CHANNELS), np.inf, dtype=np.float64)
        channel_max = np.full(len(WFIGS_CHANNELS), -np.inf, dtype=np.float64)
        train_count = 0
        for inventory_path, row in rows:
            source = _artifact_path(inventory_path, row)
            try:
                with np.load(source, allow_pickle=False) as artifact:
                    inputs, target_extent, horizon_hours = _validate_arrays(artifact)
                previous = inputs[0] > 0.5
                growth = np.logical_and(target_extent > 0, ~previous).astype(np.uint8)
                split = str(row["split"])
                destination = (
                    self.output_root / "samples" / split / f"{row['pair_id']}.npz"
                )
                _atomic_savez(
                    destination,
                    inputs=inputs,
                    target_growth=growth,
                    target_extent=target_extent,
                    horizon_hours=np.asarray(horizon_hours, dtype=np.float32),
                )
                if split == "train":
                    flat = inputs.reshape(inputs.shape[0], -1)
                    channel_min = np.minimum(channel_min, flat.min(axis=1))
                    channel_max = np.maximum(channel_max, flat.max(axis=1))
                    train_count += 1
                output_rows.append(
                    {
                        "pair_id": row["pair_id"],
                        "event_id": row["event_id"],
                        "split": split,
                        "sample": destination.relative_to(self.output_root).as_posix(),
                        "growth_pixels": int(growth.sum()),
                        "extent_pixels": int(target_extent.sum()),
                        "horizon_hours": horizon_hours,
                        "source_sha256": row.get("sha256"),
                    }
                )
            except (OSError, KeyError, TypeError, ValueError) as exc:
                failure_counts[type(exc).__name__] += 1
        if train_count == 0:
            raise ValueError("no usable TRAIN tensors; normalization cannot be fitted")

        normalization = {
            "schema": "wfd_wfigs_train_only_normalization_v1",
            "fit_split": "train",
            "test_used": False,
            "channel_names": list(WFIGS_CHANNELS),
            "channel_min": channel_min.tolist(),
            "channel_max": channel_max.tolist(),
            "samples_used": train_count,
        }
        _atomic_write_json(self.output_root / "normalization_train_only.json", normalization)
        for split in sorted({row["split"] for row in output_rows}):
            split_rows = [row for row in output_rows if row["split"] == split]
            _atomic_write_json(
                self.output_root / f"{split}.json",
                {
                    "schema": WFIGS_DATASET_SCHEMA,
                    "split": split,
                    "events": sorted({str(row["event_id"]) for row in split_rows}),
                    "samples": split_rows,
                },
            )
        report = {
            "schema": WFIGS_DATASET_SCHEMA,
            "generated_at": utc_now(),
            "channel_names": list(WFIGS_CHANNELS),
            "counts": {
                "campaign_rows_eligible": len(rows),
                "samples_written": len(output_rows),
                "samples_failed": len(rows) - len(output_rows),
                "failure_types": dict(sorted(failure_counts.items())),
                "by_split": dict(sorted(Counter(row["split"] for row in output_rows).items())),
                "events_by_split": {
                    split: len({row["event_id"] for row in output_rows if row["split"] == split})
                    for split in sorted({row["split"] for row in output_rows})
                },
            },
            "protocol": {
                "event_disjoint": True,
                "normalization_fit_on_train_only": True,
                "test_used_for_selection": False,
                "target_growth_is_t1_minus_t0": True,
                "cloud_validity_is_explicit_input_channel": True,
            },
            "rights": wfigs_rights_summary(),
            "claims": {
                "dataset_ready_for_internal_noncommercial_training": len(output_rows) > 0,
                "public_redistribution_allowed": False,
                "model_trained": False,
            },
        }
        _atomic_write_json(self.output_root / "DATASET_REPORT.json", report)
        return report


__all__ = ["WFIGS_CHANNELS", "WFIGS_DATASET_SCHEMA", "WFIGSTensorDatasetBuilder"]
