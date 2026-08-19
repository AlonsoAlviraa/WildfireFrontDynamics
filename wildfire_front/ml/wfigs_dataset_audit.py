"""Independent integrity audit for a materialized WFIGS tensor dataset."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any

import numpy as np

from wildfire_front.ml.wfigs_tensor_dataset import WFIGS_CHANNELS
from wildfire_front.open_if.regional.base import _atomic_write_json, utc_now


def _is_binary(array: np.ndarray) -> bool:
    values = np.unique(array)
    return bool(np.all(np.isin(values, (0, 1))))


def audit_wfigs_tensor_dataset(dataset_root: Path) -> dict[str, Any]:
    """Audit samples and leakage controls without changing the dataset."""

    root = Path(dataset_root).resolve()
    issues: list[dict[str, str]] = []
    manifests: dict[str, dict[str, Any]] = {}
    rows: list[tuple[str, dict[str, Any]]] = []
    event_sets: dict[str, set[str]] = defaultdict(set)

    for split in ("train", "validation", "test"):
        path = root / f"{split}.json"
        if not path.is_file():
            continue
        document = json.loads(path.read_text(encoding="utf-8"))
        manifests[split] = document
        if document.get("split") != split:
            issues.append({"code": "manifest_split_mismatch", "detail": split})
        for row in document.get("samples") or []:
            rows.append((split, row))
            event_sets[split].add(str(row.get("event_id", "")))

    if "train" not in manifests:
        issues.append({"code": "missing_train_manifest", "detail": "train.json"})
    if "validation" not in manifests:
        issues.append(
            {"code": "missing_validation_manifest", "detail": "validation.json"}
        )

    split_names = sorted(event_sets)
    for index, first in enumerate(split_names):
        for second in split_names[index + 1 :]:
            overlap = sorted(event_sets[first] & event_sets[second])
            if overlap:
                issues.append(
                    {
                        "code": "event_split_overlap",
                        "detail": f"{first}/{second}: {overlap[:5]}",
                    }
                )

    pair_counts = Counter(str(row.get("pair_id", "")) for _split, row in rows)
    duplicate_pairs = sorted(pair for pair, count in pair_counts.items() if count > 1)
    if duplicate_pairs:
        issues.append(
            {"code": "duplicate_pair_id", "detail": str(duplicate_pairs[:5])}
        )

    observed_min = np.full(len(WFIGS_CHANNELS), np.inf, dtype=np.float64)
    observed_max = np.full(len(WFIGS_CHANNELS), -np.inf, dtype=np.float64)
    train_min = np.full(len(WFIGS_CHANNELS), np.inf, dtype=np.float64)
    train_max = np.full(len(WFIGS_CHANNELS), -np.inf, dtype=np.float64)
    by_split: Counter[str] = Counter()
    growth_pixels = 0
    extent_pixels = 0
    shapes: Counter[str] = Counter()
    split_horizons: dict[str, list[float]] = defaultdict(list)
    split_valid_fractions: dict[str, list[float]] = defaultdict(list)
    split_growth_pixels: Counter[str] = Counter()
    split_extent_pixels: Counter[str] = Counter()
    split_previous_pixels: Counter[str] = Counter()
    split_zero_growth: Counter[str] = Counter()

    for split, row in rows:
        relative = Path(str(row.get("sample", "")))
        sample = (root / relative).resolve()
        try:
            sample.relative_to(root)
        except ValueError:
            issues.append({"code": "sample_path_escape", "detail": str(relative)})
            continue
        if not sample.is_file():
            issues.append({"code": "missing_sample", "detail": str(relative)})
            continue
        try:
            with np.load(sample, allow_pickle=False) as artifact:
                inputs = np.asarray(artifact["inputs"])
                growth = np.asarray(artifact["target_growth"])
                extent = np.asarray(artifact["target_extent"])
                horizon = float(np.asarray(artifact["horizon_hours"]).item())
        except (OSError, KeyError, TypeError, ValueError) as exc:
            issues.append(
                {"code": "unreadable_sample", "detail": f"{relative}: {exc}"}
            )
            continue
        shapes[str(tuple(inputs.shape))] += 1
        if inputs.ndim != 3 or inputs.shape[0] != len(WFIGS_CHANNELS):
            issues.append({"code": "invalid_input_shape", "detail": str(relative)})
            continue
        if growth.shape != inputs.shape[1:] or extent.shape != inputs.shape[1:]:
            issues.append({"code": "target_shape_mismatch", "detail": str(relative)})
            continue
        if not np.isfinite(inputs).all():
            issues.append({"code": "nonfinite_inputs", "detail": str(relative)})
            continue
        if not np.isfinite(horizon) or not 0.0 < horizon <= 48.0:
            issues.append({"code": "invalid_horizon", "detail": str(relative)})
        if not _is_binary(growth) or not _is_binary(extent):
            issues.append({"code": "nonbinary_target", "detail": str(relative)})
        if not _is_binary(inputs[0]) or not _is_binary(inputs[6]):
            issues.append({"code": "nonbinary_mask_input", "detail": str(relative)})
        expected_growth = np.logical_and(extent > 0, inputs[0] <= 0.5)
        if not np.array_equal(growth > 0, expected_growth):
            issues.append({"code": "growth_target_mismatch", "detail": str(relative)})

        flat = inputs.reshape(inputs.shape[0], -1)
        sample_min = flat.min(axis=1)
        sample_max = flat.max(axis=1)
        observed_min = np.minimum(observed_min, sample_min)
        observed_max = np.maximum(observed_max, sample_max)
        if split == "train":
            train_min = np.minimum(train_min, sample_min)
            train_max = np.maximum(train_max, sample_max)
        by_split[split] += 1
        sample_growth = int((growth > 0).sum())
        sample_extent = int((extent > 0).sum())
        sample_previous = int((inputs[0] > 0.5).sum())
        growth_pixels += sample_growth
        extent_pixels += sample_extent
        split_horizons[split].append(horizon)
        split_valid_fractions[split].append(float((inputs[6] > 0.5).mean()))
        split_growth_pixels[split] += sample_growth
        split_extent_pixels[split] += sample_extent
        split_previous_pixels[split] += sample_previous
        if sample_growth == 0:
            split_zero_growth[split] += 1

    normalization_path = root / "normalization_train_only.json"
    normalization_ok = False
    if not normalization_path.is_file():
        issues.append(
            {"code": "missing_train_normalization", "detail": normalization_path.name}
        )
    else:
        normalization = json.loads(normalization_path.read_text(encoding="utf-8"))
        try:
            stored_min = np.asarray(normalization["channel_min"], dtype=np.float64)
            stored_max = np.asarray(normalization["channel_max"], dtype=np.float64)
            normalization_ok = bool(
                normalization.get("fit_split") == "train"
                and normalization.get("test_used") is False
                and normalization.get("channel_names") == list(WFIGS_CHANNELS)
                and int(normalization.get("samples_used", -1)) == by_split["train"]
                and np.allclose(stored_min, train_min, rtol=1e-6, atol=1e-6)
                and np.allclose(stored_max, train_max, rtol=1e-6, atol=1e-6)
            )
        except (KeyError, TypeError, ValueError):
            normalization_ok = False
        if not normalization_ok:
            issues.append(
                {
                    "code": "train_normalization_mismatch",
                    "detail": "stored statistics differ from recomputed TRAIN statistics",
                }
            )

    cohort_by_split = {}
    for split in sorted(by_split):
        horizons = split_horizons[split]
        valid_fractions = split_valid_fractions[split]
        cohort_by_split[split] = {
            "samples": by_split[split],
            "events": len(event_sets[split]),
            "horizon_hours": {
                "min": min(horizons),
                "median": median(horizons),
                "mean": mean(horizons),
                "max": max(horizons),
                "n_6_12h": sum(6.0 <= value < 12.0 for value in horizons),
                "n_12_24h": sum(12.0 <= value < 24.0 for value in horizons),
                "n_24_48h": sum(24.0 <= value <= 48.0 for value in horizons),
            },
            "valid_data_fraction": {
                "min": min(valid_fractions),
                "median": median(valid_fractions),
                "mean": mean(valid_fractions),
            },
            "target": {
                "previous_pixels": split_previous_pixels[split],
                "growth_pixels": split_growth_pixels[split],
                "extent_pixels": split_extent_pixels[split],
                "zero_growth_samples": split_zero_growth[split],
                "growth_fraction_of_extent": (
                    split_growth_pixels[split] / split_extent_pixels[split]
                    if split_extent_pixels[split]
                    else None
                ),
            },
        }

    report = {
        "schema": "wfd_wfigs_tensor_dataset_audit_v1",
        "generated_at": utc_now(),
        "dataset_root": str(root),
        "status": "pass" if not issues else "fail",
        "counts": {
            "samples_declared": len(rows),
            "samples_audited": int(sum(by_split.values())),
            "by_split": dict(sorted(by_split.items())),
            "events_by_split": {
                split: len(events) for split, events in sorted(event_sets.items())
            },
            "issues": len(issues),
        },
        "tensor_shapes": dict(sorted(shapes.items())),
        "cohort_by_split": cohort_by_split,
        "channel_names": list(WFIGS_CHANNELS),
        "channel_min_all_splits": observed_min.tolist(),
        "channel_max_all_splits": observed_max.tolist(),
        "target_pixels": {
            "growth": growth_pixels,
            "extent": extent_pixels,
            "growth_fraction_of_extent": (
                growth_pixels / extent_pixels if extent_pixels else None
            ),
        },
        "checks": {
            "event_disjoint": not any(
                issue["code"] == "event_split_overlap" for issue in issues
            ),
            "unique_pair_ids": not duplicate_pairs,
            "normalization_recomputed_from_train_only": normalization_ok,
            "test_used_for_selection": False,
        },
        "issues": issues,
    }
    _atomic_write_json(root / "DATASET_AUDIT.json", report)
    return report


__all__ = ["audit_wfigs_tensor_dataset"]
