#!/usr/bin/env python3
"""Audit RCDA sampler mass using TRAIN labels only."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.ml.rcda_sealed import growth_mask  # noqa: E402


def support_band(support: int) -> str:
    if support == 0:
        return "zero"
    if support < 100:
        return "1_99"
    if support < 500:
        return "100_499"
    if support < 2000:
        return "500_1999"
    return "2000_plus"


def size_weight(support: int) -> float:
    if support == 0:
        return 4.0
    if support < 100:
        return 3.0
    if support < 500:
        return 1.5
    if support < 2000:
        return 1.0
    return 2.0


def summarize_strategy(
    name: str,
    weights: np.ndarray,
    event_ids: list[str],
    bands: list[str],
) -> dict[str, Any]:
    weights = np.asarray(weights, dtype=np.float64)
    if np.any(weights <= 0) or not np.all(np.isfinite(weights)):
        raise ValueError(f"invalid weights for {name}")
    probabilities = weights / weights.sum()
    band_mass: dict[str, float] = defaultdict(float)
    event_mass: dict[str, float] = defaultdict(float)
    for probability, event_id, band in zip(
        probabilities, event_ids, bands, strict=True
    ):
        band_mass[band] += float(probability)
        event_mass[event_id] += float(probability)
    event_values = np.asarray(list(event_mass.values()), dtype=np.float64)
    return {
        "name": name,
        "effective_sample_size": float(weights.sum() ** 2 / np.square(weights).sum()),
        "expected_support_band_fraction": dict(sorted(band_mass.items())),
        "expected_zero_growth_fraction": float(band_mass.get("zero", 0.0)),
        "event_probability_mass_cv": float(event_values.std() / event_values.mean()),
        "event_probability_mass_min": float(event_values.min()),
        "event_probability_mass_max": float(event_values.max()),
    }


def audit_training_sampler(
    *, dataset_root: Path, train_manifest_path: Path
) -> dict[str, Any]:
    manifest = json.loads(Path(train_manifest_path).read_text(encoding="utf-8"))
    if manifest.get("split") != "train":
        raise ValueError("sampler audit may read TRAIN only")
    samples = manifest.get("samples") or []
    event_counts = Counter(str(row["uid"]) for row in samples)
    supports: list[int] = []
    lost_supports: list[int] = []
    retained_fractions: list[float] = []
    event_ids: list[str] = []
    bands: list[str] = []
    for row in samples:
        inputs = np.load(dataset_root / row["input"], mmap_mode="r", allow_pickle=False)
        label = np.load(dataset_root / row["label"], mmap_mode="r", allow_pickle=False)
        support = int(growth_mask(inputs, label).sum())
        previous = np.asarray(inputs[0]) > 0.5
        next_extent = np.asarray(label) > 0.5
        previous_support = int(previous.sum())
        lost_support = int(np.logical_and(previous, ~next_extent).sum())
        supports.append(support)
        lost_supports.append(lost_support)
        retained_fractions.append(
            float((previous_support - lost_support) / previous_support)
            if previous_support
            else 1.0
        )
        event_ids.append(str(row["uid"]))
        bands.append(support_band(support))
    support_array = np.asarray(supports, dtype=np.int64)
    lost_array = np.asarray(lost_supports, dtype=np.int64)
    retained_array = np.asarray(retained_fractions, dtype=np.float64)
    size_weights = np.asarray([size_weight(value) for value in supports])
    duration = np.asarray([event_counts[event_id] for event_id in event_ids])
    strategies = [
        summarize_strategy(
            "uniform_samples", np.ones(len(samples)), event_ids, bands
        ),
        summarize_strategy(
            "legacy_size_weighted", size_weights, event_ids, bands
        ),
        summarize_strategy(
            "default_size_event_half",
            size_weights / np.sqrt(duration),
            event_ids,
            bands,
        ),
        summarize_strategy(
            "size_event_full", size_weights / duration, event_ids, bands
        ),
        summarize_strategy(
            "uniform_events", 1.0 / duration, event_ids, bands
        ),
    ]
    counts = Counter(bands)
    return {
        "schema": "wfd_rcda_train_sampler_audit_v1",
        "analysis_split": "train",
        "validation_evaluated": False,
        "test_evaluated": False,
        "samples": len(samples),
        "events": len(event_counts),
        "observed_support_band_counts": dict(sorted(counts.items())),
        "observed_zero_growth_fraction": float(counts["zero"] / len(samples)),
        "growth_support_pixels": {
            "median": float(np.median(support_array)),
            "p90": float(np.quantile(support_array, 0.9)),
            "p99": float(np.quantile(support_array, 0.99)),
            "max": int(support_array.max()),
        },
        "transition_geometry": {
            "samples_with_any_t0_loss": int((lost_array > 0).sum()),
            "samples_with_retained_fraction_below_0_99": int(
                (retained_array < 0.99).sum()
            ),
            "samples_with_retained_fraction_below_0_95": int(
                (retained_array < 0.95).sum()
            ),
            "lost_pixels_total": int(lost_array.sum()),
            "lost_pixels_p99": float(np.quantile(lost_array, 0.99)),
            "retained_fraction_median": float(np.median(retained_array)),
            "retained_fraction_p01": float(np.quantile(retained_array, 0.01)),
        },
        "event_duration_samples": {
            "median": float(np.median(list(event_counts.values()))),
            "p90": float(np.quantile(list(event_counts.values()), 0.9)),
            "max": int(max(event_counts.values())),
        },
        "strategies": strategies,
        "interpretation_contract": (
            "TRAIN-only diagnostic. It may motivate a preregistered VAL ablation, "
            "but cannot select a model and contains no VAL or TEST outcome."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=ROOT / "data/external/rcda_net_full/dataset",
    )
    parser.add_argument(
        "--train-manifest",
        type=Path,
        default=ROOT / "data/external/rcda_net_full/protocol/train.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT
        / "outputs/ml_eval/rcda_paper_nightwatch_20260819/TRAIN_SAMPLER_AUDIT.json",
    )
    args = parser.parse_args()
    report = audit_training_sampler(
        dataset_root=args.dataset_root,
        train_manifest_path=args.train_manifest,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
