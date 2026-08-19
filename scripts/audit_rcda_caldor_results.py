"""Audit why RCDA scores are weak and whether Caldor is model-ready."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
from scipy.ndimage import distance_transform_edt

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RCDA_ROOT = ROOT / "data/external/rcda_net_full"
DEFAULT_CALDOR_ROOT = (
    ROOT / "data/open_if/external_bridge/US_FIREBENCH_CALDOR_2021"
)
DEFAULT_OUTPUT = ROOT / "docs/RCDA_CALDOR_RESULTS_AUDIT.json"

UPSTREAM_MIN = np.array(
    [
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        -1.0,
        0.0163726806640625,
        -np.pi,
        270.5065612792969,
        0.0,
        0.002109996974468231,
        0.9423993229866028,
    ],
    dtype=np.float64,
)
UPSTREAM_MAX = np.array(
    [
        1.0,
        3413.0,
        1.0,
        1.0,
        1.0,
        1.0,
        13.046875,
        np.pi,
        300.23919677734375,
        0.0012839797418564558,
        0.015439476817846298,
        1.270668625831604,
    ],
    dtype=np.float64,
)
CHANNELS = (
    "previous_fire",
    "dem",
    "blue",
    "green",
    "red",
    "ndvi",
    "wind_speed",
    "wind_direction",
    "temperature",
    "precipitation",
    "humidity",
    "air_density",
)
RING_NAMES = (
    "inside_previous_fire",
    "distance_0_to_1_5_px",
    "distance_1_5_to_3_5_px",
    "distance_3_5_to_5_5_px",
    "distance_5_5_to_10_5_px",
    "distance_gt_10_5_px",
)
SIZE_BINS = (
    ("empty", 0, 0),
    ("1_to_99", 1, 99),
    ("100_to_499", 100, 499),
    ("500_to_1999", 500, 1999),
    ("2000_plus", 2000, None),
)


def confusion(prediction: np.ndarray, target: np.ndarray) -> np.ndarray:
    pred = prediction.astype(bool)
    truth = target.astype(bool)
    return np.array(
        [
            np.logical_and(pred, truth).sum(),
            np.logical_and(~pred, ~truth).sum(),
            np.logical_and(pred, ~truth).sum(),
            np.logical_and(~pred, truth).sum(),
        ],
        dtype=np.int64,
    )


def metrics(row: np.ndarray) -> dict[str, float | int]:
    tp, tn, fp, fn = (int(value) for value in row)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    iou = tp / (tp + fp + fn) if tp + fp + fn else 0.0
    return {
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "iou": iou,
    }


def quantiles(values: list[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=np.float64)
    return {
        name: float(np.quantile(array, q))
        for name, q in (
            ("min", 0.0),
            ("p05", 0.05),
            ("p10", 0.10),
            ("p25", 0.25),
            ("median", 0.50),
            ("p75", 0.75),
            ("p90", 0.90),
            ("p95", 0.95),
            ("max", 1.0),
        )
    }


def size_bin(support: int) -> str:
    for name, lower, upper in SIZE_BINS:
        if support >= lower and (upper is None or support <= upper):
            return name
    raise AssertionError("unreachable")


def _calibration_result(
    counts: np.ndarray,
    probability_sums: np.ndarray,
    target_sums: np.ndarray,
) -> dict[str, Any]:
    total = int(counts.sum())
    rows = []
    ece = 0.0
    for index, count_value in enumerate(counts):
        count = int(count_value)
        confidence = float(probability_sums[index] / count) if count else 0.0
        frequency = float(target_sums[index] / count) if count else 0.0
        if total:
            ece += count / total * abs(confidence - frequency)
        rows.append(
            {
                "lower": index / len(counts),
                "upper": (index + 1) / len(counts),
                "pixels": count,
                "mean_probability": confidence,
                "positive_frequency": frequency,
            }
        )
    return {"ece_20_bins": ece, "bins": rows}


def audit_rcda(rcda_root: Path) -> dict[str, Any]:
    reproduction = json.loads(
        (ROOT / "outputs/ml_eval/rcda_full_upstream/reproduction.json").read_text(
            encoding="utf-8"
        )
    )
    protocol = json.loads(
        (ROOT / "docs/RCDA_NET_FULL_PROTOCOL.json").read_text(encoding="utf-8")
    )
    sealed_baseline = json.loads(
        (
            ROOT / "outputs/ml_eval/rcda_sealed_baselines/dilated_copy.json"
        ).read_text(encoding="utf-8")
    )
    dataset_root = rcda_root / "dataset"
    input_root = dataset_root / "test/inputs"
    label_root = dataset_root / "test/labels"
    cache_root = ROOT / "outputs/ml_eval/rcda_full_upstream/predictions"
    threshold = float(reproduction["threshold_search_on_test"]["selected_threshold"])

    global_confusion = np.zeros(4, dtype=np.int64)
    year_confusions: dict[str, np.ndarray] = defaultdict(
        lambda: np.zeros(4, dtype=np.int64)
    )
    size_confusions: dict[str, np.ndarray] = {
        name: np.zeros(4, dtype=np.int64) for name, _low, _high in SIZE_BINS
    }
    size_counts = {name: 0 for name, _low, _high in SIZE_BINS}
    ring_confusions = {name: np.zeros(4, dtype=np.int64) for name in RING_NAMES}
    dilation_confusions = {
        radius: np.zeros(4, dtype=np.int64) for radius in range(1, 9)
    }
    sample_ious: list[float] = []
    sample_f1s: list[float] = []
    empty_growth_samples = 0

    calibration_counts = np.zeros(20, dtype=np.int64)
    calibration_probability = np.zeros(20, dtype=np.float64)
    calibration_target = np.zeros(20, dtype=np.float64)
    brier_sum = 0.0
    probability_sum_positive = 0.0
    probability_sum_negative = 0.0
    positive_pixels = 0
    negative_pixels = 0
    saturation = {"lte_0_01": 0, "between_0_2_and_0_6": 0, "gte_0_99": 0}

    observed_min = np.full(12, np.inf, dtype=np.float64)
    observed_max = np.full(12, -np.inf, dtype=np.float64)
    below_upstream = np.zeros(12, dtype=np.int64)
    above_upstream = np.zeros(12, dtype=np.int64)
    constant_samples = np.zeros(12, dtype=np.int64)
    values_per_channel = 0

    names = sorted(path.name for path in input_root.glob("*.npy"))
    for index, name in enumerate(names, start=1):
        inputs = np.load(input_root / name, mmap_mode="r", allow_pickle=False)
        next_extent = np.load(
            label_root / name, mmap_mode="r", allow_pickle=False
        ) > 0.5
        previous = np.asarray(inputs[0]) > 0.5
        target = np.logical_and(next_extent, ~previous)
        with np.load(cache_root / f"{Path(name).stem}.npz", allow_pickle=False) as data:
            probability = data["probability"].astype(np.float32, copy=False)
        prediction = probability >= threshold
        row = confusion(prediction, target)
        global_confusion += row
        year = name.rsplit("_", 1)[-1][:4]
        year_confusions[year] += row

        sample_metrics = metrics(row)
        sample_ious.append(float(sample_metrics["iou"]))
        sample_f1s.append(float(sample_metrics["f1"]))
        support = int(target.sum())
        empty_growth_samples += int(support == 0)
        group = size_bin(support)
        size_counts[group] += 1
        size_confusions[group] += row

        flat_probability = probability.ravel()
        flat_target = target.ravel()
        probability_bins = np.minimum(
            (flat_probability * 20).astype(np.int16), 19
        )
        calibration_counts += np.bincount(probability_bins, minlength=20)
        calibration_probability += np.bincount(
            probability_bins, weights=flat_probability, minlength=20
        )
        calibration_target += np.bincount(
            probability_bins, weights=flat_target, minlength=20
        )
        difference = probability - target.astype(np.float32)
        brier_sum += float(np.square(difference).sum(dtype=np.float64))
        positive_pixels += support
        negative_pixels += int(target.size - support)
        probability_sum_positive += float(
            probability[target].sum(dtype=np.float64)
        )
        probability_sum_negative += float(
            probability[~target].sum(dtype=np.float64)
        )
        saturation["lte_0_01"] += int((probability <= 0.01).sum())
        saturation["between_0_2_and_0_6"] += int(
            np.logical_and(probability >= 0.2, probability < 0.6).sum()
        )
        saturation["gte_0_99"] += int((probability >= 0.99).sum())

        for channel_index in range(12):
            channel_array = np.asarray(inputs[channel_index])
            observed_min[channel_index] = min(
                observed_min[channel_index], float(channel_array.min())
            )
            observed_max[channel_index] = max(
                observed_max[channel_index], float(channel_array.max())
            )
            below_upstream[channel_index] += int(
                (channel_array < UPSTREAM_MIN[channel_index]).sum()
            )
            above_upstream[channel_index] += int(
                (channel_array > UPSTREAM_MAX[channel_index]).sum()
            )
            constant_samples[channel_index] += int(
                float(channel_array.min()) == float(channel_array.max())
            )
        values_per_channel += int(inputs.shape[1] * inputs.shape[2])

        distance = distance_transform_edt(~previous)
        ring_masks = (
            previous,
            np.logical_and(~previous, distance <= 1.5),
            np.logical_and(distance > 1.5, distance <= 3.5),
            np.logical_and(distance > 3.5, distance <= 5.5),
            np.logical_and(distance > 5.5, distance <= 10.5),
            distance > 10.5,
        )
        for ring_name, mask in zip(RING_NAMES, ring_masks, strict=True):
            ring_confusions[ring_name] += confusion(prediction[mask], target[mask])
        for radius in dilation_confusions:
            ring_prediction = np.logical_and(~previous, distance <= radius)
            dilation_confusions[radius] += confusion(ring_prediction, target)
        if index % 250 == 0 or index == len(names):
            print(f"[results-audit] RCDA {index}/{len(names)}", flush=True)

    total_pixels = int(global_confusion.sum())
    selected = metrics(global_confusion)
    all_negative_accuracy = 1.0 - positive_pixels / total_pixels
    upstream_accuracy = (
        int(selected["tp"]) + int(selected["tn"])
    ) / total_pixels
    calibration = _calibration_result(
        calibration_counts, calibration_probability, calibration_target
    )
    calibration["brier_score"] = brier_sum / total_pixels
    calibration["mean_probability_on_positive_pixels"] = (
        probability_sum_positive / positive_pixels if positive_pixels else 0.0
    )
    calibration["mean_probability_on_negative_pixels"] = (
        probability_sum_negative / negative_pixels if negative_pixels else 0.0
    )
    calibration["fractions"] = {
        key: value / total_pixels for key, value in saturation.items()
    }

    normalization = []
    train_min = np.asarray(protocol["normalization"]["channel_min"])
    train_max = np.asarray(protocol["normalization"]["channel_max"])
    for index, channel_name in enumerate(CHANNELS):
        normalization.append(
            {
                "channel": channel_name,
                "upstream_min": float(UPSTREAM_MIN[index]),
                "upstream_max": float(UPSTREAM_MAX[index]),
                "sealed_train_min": float(train_min[index]),
                "sealed_train_max": float(train_max[index]),
                "official_test_observed_min": float(observed_min[index]),
                "official_test_observed_max": float(observed_max[index]),
                "official_test_fraction_below_upstream_min": float(
                    below_upstream[index] / values_per_channel
                ),
                "official_test_fraction_above_upstream_max": float(
                    above_upstream[index] / values_per_channel
                ),
                "official_test_spatially_constant_samples": int(
                    constant_samples[index]
                ),
            }
        )

    threshold_rows = reproduction["threshold_search_on_test"]["results"]
    threshold_f1s = [float(row["f1"]) for row in threshold_rows.values()]
    event_rows = reproduction["per_event_at_selected_threshold"]
    event_ious = [float(row["iou"]) for row in event_rows.values()]
    candidate_leaked_max_channels = [
        index
        for index in range(12)
        if not np.isclose(UPSTREAM_MAX[index], train_max[index])
        and np.isclose(UPSTREAM_MAX[index], observed_max[index])
    ]
    original_train_min = dict.fromkeys(candidate_leaked_max_channels, np.inf)
    original_train_max = dict.fromkeys(candidate_leaked_max_channels, -np.inf)
    original_train_root = dataset_root / "train/inputs"
    original_train_files = sorted(original_train_root.glob("*.npy"))
    for scan_index, path in enumerate(original_train_files, start=1):
        inputs = np.load(path, mmap_mode="r", allow_pickle=False)
        for channel_index in candidate_leaked_max_channels:
            channel_array = np.asarray(inputs[channel_index])
            original_train_min[channel_index] = min(
                original_train_min[channel_index], float(channel_array.min())
            )
            original_train_max[channel_index] = max(
                original_train_max[channel_index], float(channel_array.max())
            )
        if scan_index % 1000 == 0 or scan_index == len(original_train_files):
            print(
                f"[results-audit] original TRAIN bounds "
                f"{scan_index}/{len(original_train_files)}",
                flush=True,
            )
    for channel_index, norm_row in enumerate(normalization):
        if channel_index in original_train_max:
            norm_row["original_upstream_train_observed_min"] = original_train_min[
                channel_index
            ]
            norm_row["original_upstream_train_observed_max"] = original_train_max[
                channel_index
            ]
            norm_row["upstream_max_equals_test_but_not_original_train"] = bool(
                np.isclose(UPSTREAM_MAX[channel_index], observed_max[channel_index])
                and not np.isclose(
                    UPSTREAM_MAX[channel_index], original_train_max[channel_index]
                )
            )
    return {
        "verdict": {
            "checkpoint_quality": "weak_to_moderate_growth_localization",
            "published_result_reproduced": True,
            "independent_test_evidence": False,
            "sealed_retraining_completed": False,
        },
        "class_balance": {
            "pixels": total_pixels,
            "growth_positive_pixels": positive_pixels,
            "growth_prevalence": positive_pixels / total_pixels,
            "empty_growth_samples": empty_growth_samples,
            "all_negative_accuracy": all_negative_accuracy,
            "checkpoint_accuracy": upstream_accuracy,
            "checkpoint_accuracy_minus_all_negative": upstream_accuracy
            - all_negative_accuracy,
        },
        "selected_threshold_result": selected,
        "threshold_stability": {
            "selection_split": "official_test",
            "thresholds": threshold_rows,
            "f1_range_0_2_to_0_6": max(threshold_f1s) - min(threshold_f1s),
        },
        "sample_macro": {
            "iou": quantiles(sample_ious),
            "f1": quantiles(sample_f1s),
            "zero_iou_samples": sum(value == 0.0 for value in sample_ious),
            "samples_below_iou_0_1": sum(value < 0.1 for value in sample_ious),
        },
        "event_macro": {
            "iou": quantiles(event_ious),
            "zero_iou_events": sum(value == 0.0 for value in event_ious),
            "events_below_iou_0_1": sum(value < 0.1 for value in event_ious),
        },
        "by_year": {
            year: metrics(row) for year, row in sorted(year_confusions.items())
        },
        "by_growth_size": {
            name: {"samples": size_counts[name], "metrics": metrics(row)}
            for name, row in size_confusions.items()
        },
        "by_distance_from_previous_front": {
            name: metrics(row) for name, row in ring_confusions.items()
        },
        "official_test_dilated_copy_diagnostic": {
            "protocol_is_sealed": False,
            "results": {
                str(radius): metrics(row)
                for radius, row in dilation_confusions.items()
            },
        },
        "calibration": calibration,
        "normalization_and_channel_audit": normalization,
        "protocol": {
            "upstream_train_test_event_overlap": protocol["upstream_leakage"],
            "checkpoint_selected_on_test": True,
            "threshold_selected_on_test": True,
            "training_seed_declared": False,
            "deterministic_training_declared": False,
            "checkpoint_epoch_and_optimizer_state_published": False,
            "documented_loss": "DiceLoss",
            "normalization_uses_test_extrema": any(
                bool(
                    row.get(
                        "upstream_max_equals_test_but_not_original_train", False
                    )
                )
                for row in normalization
            ),
            "normalization_test_extrema_channels": [
                row["channel"]
                for row in normalization
                if row.get("upstream_max_equals_test_but_not_original_train", False)
            ],
            "sealed_split_ready": protocol["sealed_protocol"],
            "sealed_baseline": sealed_baseline["test"]["growth_ring_result"],
        },
    }


def audit_caldor(caldor_root: Path) -> dict[str, Any]:
    acquisition = json.loads(
        (ROOT / "docs/CALDOR_CLEAN17_ACQUISITION.json").read_text(
            encoding="utf-8"
        )
    )
    spatial_audit = json.loads(
        (ROOT / "docs/CALDOR_CLEAN17_AUDIT.json").read_text(encoding="utf-8")
    )
    window_rows = []
    erc_future_count = 0
    exact_windows = 0
    for row in acquisition["dynamic"]:
        t0 = datetime.fromisoformat(row["t0_utc"].replace("Z", "+00:00"))
        t1 = datetime.fromisoformat(row["t1_utc"].replace("Z", "+00:00"))
        cycle = datetime.fromisoformat(
            row["hrrr_cycle_utc"].replace("Z", "+00:00")
        )
        weather_end = cycle + timedelta(hours=24)
        pre_target = max(0.0, (t0 - cycle).total_seconds() / 3600.0)
        after_target = max(0.0, (weather_end - t1).total_seconds() / 3600.0)
        uncovered_target = max(0.0, (t1 - weather_end).total_seconds() / 3600.0)
        exact = pre_target == 0.0 and after_target == 0.0 and uncovered_target == 0.0
        exact_windows += int(exact)
        erc = row["channels"]["erc_g"]
        erc_future = "ending 07:00 UTC next day" in erc["day_definition"]
        erc_future_count += int(erc_future)
        window_rows.append(
            {
                "t0_utc": row["t0_utc"],
                "t1_utc": row["t1_utc"],
                "delta_hours": row["delta_hours"],
                "hrrr_cycle_utc": row["hrrr_cycle_utc"],
                "hrrr_summary_hours_before_t0": pre_target,
                "hrrr_summary_hours_after_t1": after_target,
                "target_hours_not_covered_by_hrrr_0_24": uncovered_target,
                "hrrr_window_exact": exact,
                "gridmet_day": erc["gridmet_day"],
                "gridmet_day_definition": erc["day_definition"],
                "gridmet_value_not_available_at_t0_under_declared_day_definition": erc_future,
            }
        )
    canopy_finite = [
        float(acquisition["static"][name]["finite_fraction"])
        for name in (
            "canopy_height_m",
            "canopy_base_height_m",
            "canopy_bulk_density_kg_m3",
            "canopy_presence",
        )
    ]
    clean_npz = list((caldor_root / "covariates").rglob("*.npz"))
    return {
        "verdict": {
            "spatial_materialization": "pass",
            "temporal_availability": "fail",
            "model_ready": False,
            "model_score_exists": False,
            "legacy17_checkpoint_compatible": False,
        },
        "spatial_audit_passed": spatial_audit["ok"],
        "pairs": acquisition["n_pairs"],
        "events": 1,
        "real_channels": acquisition["n_real_channels"],
        "unique_materialized_files": spatial_audit[
            "unique_materialized_channel_files"
        ],
        "horizon_hours": quantiles(
            [float(row["delta_hours"]) for row in acquisition["dynamic"]]
        ),
        "temporal_findings": {
            "pairs_with_exact_hrrr_target_window": exact_windows,
            "pairs_with_gridmet_value_unavailable_at_t0_under_declared_definition": erc_future_count,
            "rows": window_rows,
        },
        "missing_data": {
            "canopy_finite_fraction": min(canopy_finite),
            "canopy_nodata_fraction": 1.0 - min(canopy_finite),
            "imputation_policy_declared": False,
            "missingness_mask_declared": False,
        },
        "tensorization": {
            "stacked_clean17_npz_files": len(clean_npz),
            "normalization_fit_declared": False,
            "circular_wind_encoding": False,
            "circular_aspect_encoding": False,
            "forecast_horizon_input_channel": False,
        },
        "use_constraint": (
            "One event and 15 correlated pairs are suitable for external evaluation, "
            "not standalone model training or event-disjoint validation."
        ),
    }


def build_recommendations(rcda: dict[str, Any], caldor: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "priority": "P0",
            "action": "repair_caldor_temporal_contract",
            "why": "The current spatial audit passes but ERC availability and HRRR target-window alignment fail.",
            "acceptance": [
                "choose the latest ERC value whose declared availability is <= t0",
                "aggregate HRRR valid times over [t0,t1], extending leads beyond 24 h when required",
                "rerun temporal audit with zero unavailable inputs and 15 exact forecast windows",
            ],
        },
        {
            "priority": "P0",
            "action": "train_rcda_from_scratch_on_event_disjoint_split",
            "why": "The checkpoint, threshold and two normalization maxima use TEST, and one event crosses TRAIN/TEST.",
            "acceptance": [
                "normalization and sampling fit on TRAIN only",
                "checkpoint and threshold selected on VAL only",
                "TEST evaluated once after freezing all choices",
                "report at least three seeds and confidence intervals",
            ],
        },
        {
            "priority": "P0",
            "action": "establish_same_split_baselines_and_failure_metrics",
            "why": "One-percent growth prevalence makes accuracy misleading and global IoU hides event failures.",
            "acceptance": [
                "compare copy, tuned dilation, U-Net and RCDA on the same sealed TEST",
                "report event-macro and pixel-micro growth IoU/F1/AP",
                "report boundary F1, distance-stratified recall, calibration and empty-growth cases",
            ],
        },
        {
            "priority": "P1",
            "action": "improve_target_and_loss",
            "why": "Growth is sparse and spatial displacement dominates errors.",
            "acceptance": [
                "benchmark Dice against focal-Tversky plus boundary or signed-distance loss",
                "handle empty-growth samples explicitly",
                "balance events and growth-size strata instead of only shuffling days",
            ],
        },
        {
            "priority": "P1",
            "action": "add_temporal_and_physical_conditioning",
            "why": "A single mask plus daily summaries cannot represent acceleration, direction changes or variable horizon.",
            "acceptance": [
                "use multiple previous perimeters or arrival-time history",
                "supply the exact forecast horizon",
                "encode wind/aspect as sin-cos and use forecast sequences instead of only 24 h aggregates",
                "add distance-to-front or front-aligned features without using t1",
            ],
        },
        {
            "priority": "P1",
            "action": "finish_caldor_tensor_contract",
            "why": "GeoTIFF acquisition is complete, but no stacked, normalized, imputed clean17 tensor exists.",
            "acceptance": [
                "declare TRAIN-fitted normalization from a multi-fire corpus",
                "define canopy nodata imputation and an explicit missingness mask",
                "train a clean17-native checkpoint; never reuse legacy17 weights silently",
                "keep Caldor as one-fire external evaluation, not a training split",
            ],
        },
    ]


def audit(rcda_root: Path, caldor_root: Path) -> dict[str, Any]:
    rcda = audit_rcda(rcda_root)
    caldor = audit_caldor(caldor_root)
    return {
        "schema": "wfd_rcda_caldor_results_audit_v1",
        "generated_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "status": "complete",
        "executive_verdict": {
            "rcda": "published score reproduced but weak-to-moderate and not independent",
            "caldor": "no poor model score exists; the current blocker is temporal/tensor contract validity",
            "main_bottleneck": "data protocol and target formulation before architecture",
        },
        "rcda": rcda,
        "caldor": caldor,
        "recommendations": build_recommendations(rcda, caldor),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rcda-root", type=Path, default=DEFAULT_RCDA_ROOT)
    parser.add_argument("--caldor-root", type=Path, default=DEFAULT_CALDOR_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = audit(args.rcda_root, args.caldor_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": report["status"],
                "rcda_iou": report["rcda"]["selected_threshold_result"]["iou"],
                "rcda_growth_prevalence": report["rcda"]["class_balance"]["growth_prevalence"],
                "caldor_temporal_availability": report["caldor"]["verdict"]["temporal_availability"],
                "output": str(args.output),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
