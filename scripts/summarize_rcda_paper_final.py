#!/usr/bin/env python3
"""Build a paired event-bootstrap RCDA paper scorecard after frozen TEST evaluation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import wilcoxon

ROOT = Path(__file__).resolve().parents[1]


def _bootstrap_ci(
    values: np.ndarray, *, n_resamples: int = 10_000, seed: int = 20260819
) -> tuple[float, float]:
    if values.size == 0:
        raise ValueError("cannot bootstrap an empty array")
    rng = np.random.default_rng(seed)
    means = np.empty(n_resamples, dtype=np.float64)
    for start in range(0, n_resamples, 500):
        count = min(500, n_resamples - start)
        indices = rng.integers(0, values.size, size=(count, values.size))
        means[start : start + count] = values[indices].mean(axis=1)
    low, high = np.quantile(means, [0.025, 0.975])
    return float(low), float(high)


def build_scorecard(
    final_summary_path: Path,
    baseline_path: Path,
    output_dir: Path,
    learned_baselines_path: Path | None = None,
) -> dict[str, Any]:
    final_summary = json.loads(Path(final_summary_path).read_text(encoding="utf-8"))
    baseline = json.loads(Path(baseline_path).read_text(encoding="utf-8"))
    baseline_validation = baseline.get("validation") or {}
    baseline_protocol = baseline.get("protocol") or {}
    if baseline_validation.get("selection_metric") != "event_macro_growth_iou":
        raise ValueError("baseline was not selected on the primary VAL metric")
    if (
        baseline_validation.get("test_used_for_selection") is not False
        or baseline_protocol.get("test_used_for_selection") is not False
    ):
        raise ValueError("baseline used TEST for selection")
    if final_summary.get("schema") not in {
        "wfd_rcda_paper_final_v1",
        "wfd_rcda_paper_final_metrics_v1",
    }:
        raise ValueError("unexpected final summary schema")
    if final_summary.get("test_used_for_selection") is not False:
        raise ValueError("final summary does not preserve TEST isolation")
    frozen = final_summary.get("frozen_recipe") or {}
    expected_seeds = set((frozen.get("final_evaluation") or {}).get("seeds") or [])
    reports = list(final_summary.get("reports") or [])
    observed_seeds = {int(row["config"]["seed"]) for row in reports}
    if observed_seeds != expected_seeds:
        raise ValueError("final reports do not match preregistered seeds")
    if any(row.get("test_used_for_selection") is not False for row in reports):
        raise ValueError("a final report used TEST for selection")

    baseline_events = baseline["test"]["per_event_growth"]
    model_events_by_seed = [row["test_once"]["per_event"] for row in reports]
    common_events = sorted(
        set(baseline_events).intersection(*(set(rows) for rows in model_events_by_seed))
    )
    if len(common_events) != int(baseline["test"]["events"]):
        raise ValueError("model and baseline event sets differ")
    baseline_iou = np.asarray(
        [float(baseline_events[event]["iou"]) for event in common_events], dtype=np.float64
    )
    seed_event_iou = np.asarray(
        [[float(rows[event]["iou"]) for event in common_events] for rows in model_events_by_seed],
        dtype=np.float64,
    )
    model_iou = seed_event_iou.mean(axis=0)
    paired_delta = model_iou - baseline_iou
    model_ci = _bootstrap_ci(model_iou)
    delta_ci = _bootstrap_ci(paired_delta)
    statistic, p_value = wilcoxon(paired_delta, alternative="greater", zero_method="zsplit")

    def paired_comparison(label: str, reference: np.ndarray) -> dict[str, Any]:
        delta = model_iou - reference
        if np.allclose(delta, 0.0):
            local_statistic, local_p = 0.0, 1.0
        else:
            local_statistic, local_p = wilcoxon(delta, alternative="greater", zero_method="zsplit")
        return {
            "label": label,
            "event_macro_iou": float(reference.mean()),
            "paired_delta": float(delta.mean()),
            "paired_delta_event_bootstrap_95_ci": list(_bootstrap_ci(delta)),
            "events_improved_fraction": float((delta > 0).mean()),
            "one_sided_wilcoxon_statistic": float(local_statistic),
            "one_sided_wilcoxon_p": float(local_p),
        }

    comparator_arrays = {
        "dilated_copy": baseline_iou,
    }
    comparators = {
        "dilated_copy": paired_comparison("Dilated copy", baseline_iou),
    }
    learned_required = learned_baselines_path is not None
    if learned_required:
        learned_path = Path(learned_baselines_path)
        if not learned_path.is_file():
            raise FileNotFoundError(f"learned baseline artifact missing: {learned_path}")
        learned = json.loads(learned_path.read_text(encoding="utf-8"))
        if learned.get("schema") != "wfd_rcda_learned_baselines_v1":
            raise ValueError("unexpected learned baseline schema")
        if learned.get("test_used_for_selection") is not False:
            raise ValueError("learned baseline used TEST for selection")
        for report in learned.get("reports") or []:
            if report.get("test_used_for_selection") is not False:
                raise ValueError("a learned baseline used TEST for selection")
            per_event = (report.get("test") or {}).get("per_event") or {}
            if set(per_event) != set(common_events):
                raise ValueError("learned baseline and final model event sets differ")
            values = np.asarray(
                [float(per_event[event]["iou"]) for event in common_events],
                dtype=np.float64,
            )
            key = str(report.get("model_name") or "learned_baseline")
            comparator_arrays[key] = values
            comparators[key] = paired_comparison(key.upper(), values)
    strongest_key = max(
        comparators,
        key=lambda key: float(comparators[key]["event_macro_iou"]),
    )
    strongest = comparators[strongest_key]

    ensemble_score = None
    ensemble_report = final_summary.get("ensemble")
    if ensemble_report:
        if ensemble_report.get("aggregation") != "mean_seed_probability":
            raise ValueError("unexpected ensemble aggregation")
        if ensemble_report.get("threshold_selected_on") != "val":
            raise ValueError("ensemble threshold was not selected on VAL")
        if ensemble_report.get("test_used_for_selection") is not False:
            raise ValueError("ensemble used TEST for selection")
        if ensemble_report.get("test_evaluated") is not True:
            raise ValueError("ensemble TEST evaluation is not sealed")
        ensemble_events = (ensemble_report.get("test_once") or {}).get("per_event") or {}
        if set(ensemble_events) != set(common_events):
            raise ValueError("ensemble and final model event sets differ")
        ensemble_iou = np.asarray(
            [float(ensemble_events[event]["iou"]) for event in common_events],
            dtype=np.float64,
        )

        def ensemble_delta(reference: np.ndarray) -> dict[str, Any]:
            delta = ensemble_iou - reference
            if np.allclose(delta, 0.0):
                local_statistic, local_p = 0.0, 1.0
            else:
                local_statistic, local_p = wilcoxon(
                    delta, alternative="greater", zero_method="zsplit"
                )
            return {
                "paired_delta": float(delta.mean()),
                "paired_delta_event_bootstrap_95_ci": list(_bootstrap_ci(delta)),
                "events_improved_fraction": float((delta > 0).mean()),
                "one_sided_wilcoxon_statistic": float(local_statistic),
                "one_sided_wilcoxon_p": float(local_p),
            }

        ensemble_test = ensemble_report["test_once"]
        ensemble_score = {
            "role": "preregistered_secondary_probability_ensemble",
            "aggregation": ensemble_report.get("aggregation"),
            "threshold": float(ensemble_report["selected_threshold"]),
            "threshold_selected_on": "val",
            "event_macro_iou": float(ensemble_iou.mean()),
            "event_bootstrap_95_ci": list(_bootstrap_ci(ensemble_iou)),
            "pooled_iou": float(ensemble_test["iou"]),
            "vs_primary_seed_mean": ensemble_delta(model_iou),
            "vs_dilated_copy": ensemble_delta(baseline_iou),
            "vs_strongest_baseline": ensemble_delta(comparator_arrays[strongest_key]),
        }
        paper_metrics = ensemble_test.get("paper_metrics") or {}
        if paper_metrics:
            ensemble_score["paper_metrics"] = paper_metrics

    decoder_score = None
    decoder_report = final_summary.get("decoder")
    if decoder_report:
        if decoder_report.get("role") != "preregistered_secondary_spatial_decoder":
            raise ValueError("unexpected spatial decoder role")
        if decoder_report.get("threshold_and_geometry_selected_on") != "val":
            raise ValueError("spatial decoder was not selected on VAL")
        if decoder_report.get("test_used_for_selection") is not False:
            raise ValueError("spatial decoder used TEST for selection")
        if decoder_report.get("test_evaluated") is not True:
            raise ValueError("spatial decoder TEST evaluation is not sealed")
        decoder_test = decoder_report.get("test_once") or {}
        decoder_events = decoder_test.get("per_event") or {}
        if set(decoder_events) != set(common_events):
            raise ValueError("spatial decoder and final model event sets differ")
        decoder_iou = np.asarray(
            [float(decoder_events[event]["iou"]) for event in common_events],
            dtype=np.float64,
        )

        def decoder_delta(reference: np.ndarray) -> dict[str, Any]:
            delta = decoder_iou - reference
            if np.allclose(delta, 0.0):
                local_statistic, local_p = 0.0, 1.0
            else:
                local_statistic, local_p = wilcoxon(
                    delta, alternative="greater", zero_method="zsplit"
                )
            return {
                "paired_delta": float(delta.mean()),
                "paired_delta_event_bootstrap_95_ci": list(_bootstrap_ci(delta)),
                "events_improved_fraction": float((delta > 0).mean()),
                "one_sided_wilcoxon_statistic": float(local_statistic),
                "one_sided_wilcoxon_p": float(local_p),
            }

        decoder_score = {
            "role": decoder_report.get("role"),
            "applied_to": decoder_report.get("applied_to"),
            "threshold": float(decoder_report["threshold"]),
            "dilation_radius_px": int(decoder_report["dilation_radius_px"]),
            "require_t0_connection": bool(
                decoder_report["require_t0_connection"]
            ),
            "threshold_and_geometry_selected_on": "val",
            "event_macro_iou": float(decoder_iou.mean()),
            "event_bootstrap_95_ci": list(_bootstrap_ci(decoder_iou)),
            "pooled_iou": float(decoder_test["iou"]),
            "vs_primary_seed_mean": decoder_delta(model_iou),
            "vs_dilated_copy": decoder_delta(baseline_iou),
            "vs_strongest_baseline": decoder_delta(
                comparator_arrays[strongest_key]
            ),
        }

    seed_metrics = [
        {
            "seed": int(row["config"]["seed"]),
            "checkpoint_sha256": str(row["checkpoint_sha256"]),
            "best_epoch": int(row["best_epoch"]),
            "threshold": float(row["selected_threshold"]),
            "test_event_macro_iou": float(row["test_once"]["event_macro_iou"]),
            "test_pooled_iou": float(row["test_once"]["iou"]),
            "far_gt_10_5px_recall": float(row["test_once"]["far_gt_10_5px_recall"]),
            "growth_average_precision_macro": float(
                row["test_once"]["paper_metrics"]["model_growth_average_precision_macro"]
            ),
            "growth_fcer_iou": float(row["test_once"]["paper_metrics"]["model_growth_fcer_iou"]),
            "growth_fcer_ece_macro": float(
                row["test_once"]["paper_metrics"]["model_growth_fcer_ece_macro"]
            ),
            "growth_fcer_selective_error_80_macro": float(
                row["test_once"]["paper_metrics"]["model_growth_fcer_selective_error_80_macro"]
            ),
            "growth_fcer_aurc_macro": float(
                row["test_once"]["paper_metrics"]["model_growth_fcer_aurc_macro"]
            ),
            "observed_growth_fcer_capture_macro": float(
                row["test_once"]["paper_metrics"]["observed_growth_fcer_capture_macro"]
            ),
            "front_boundary_f1_macro": float(
                row["test_once"]["paper_metrics"]["model_front_boundary_f1_macro"]
            ),
        }
        for row in reports
    ]

    def mean_std(key: str) -> dict[str, float]:
        values = np.asarray([row[key] for row in seed_metrics], dtype=np.float64)
        return {
            "mean": float(values.mean()),
            "sample_std": float(values.std(ddof=1)),
        }

    mean_event_macro = float(model_iou.mean())
    baseline_event_macro = float(baseline_iou.mean())
    gate = {
        "three_or_more_preregistered_seeds": len(reports) >= 3,
        "event_macro_iou_at_least_0_20": mean_event_macro >= 0.20,
        "paired_bootstrap_delta_ci_above_zero": delta_ci[0] > 0.0,
        "all_seed_event_macro_above_dilated_copy": all(
            row["test_event_macro_iou"] > baseline_event_macro for row in seed_metrics
        ),
        "learned_baselines_reproduced": (not learned_required) or len(comparators) >= 3,
        "mean_event_macro_above_strongest_baseline": mean_event_macro
        > float(strongest["event_macro_iou"]),
        "paired_bootstrap_delta_vs_strongest_ci_above_zero": float(
            strongest["paired_delta_event_bootstrap_95_ci"][0]
        )
        > 0.0,
        "all_seed_event_macro_above_strongest_baseline": all(
            row["test_event_macro_iou"] > float(strongest["event_macro_iou"])
            for row in seed_metrics
        ),
        "test_not_used_for_selection": True,
    }
    scorecard = {
        "schema": "wfd_rcda_paper_scorecard_v1",
        "status": "paper_model_candidate" if all(gate.values()) else "continue_model_improvement",
        "frozen_recipe": frozen,
        "events": len(common_events),
        "seeds": seed_metrics,
        "primary": {
            "metric": "event_macro_growth_iou",
            "model_mean": mean_event_macro,
            "event_bootstrap_95_ci": list(model_ci),
            "dilated_copy": baseline_event_macro,
            "paired_delta": float(paired_delta.mean()),
            "paired_delta_event_bootstrap_95_ci": list(delta_ci),
            "events_improved_fraction": float((paired_delta > 0).mean()),
            "one_sided_wilcoxon_statistic": float(statistic),
            "one_sided_wilcoxon_p": float(p_value),
        },
        "comparators": comparators,
        "strongest_baseline": {"id": strongest_key, **strongest},
        "baseline_contract": {
            "id": "dilated_copy",
            "selected_radius_pixels": int(
                baseline_validation["selected_radius_pixels"]
            ),
            "selection_split": "val",
            "selection_metric": "event_macro_growth_iou",
            "test_used_for_selection": False,
        },
        "ensemble": ensemble_score,
        "decoder": decoder_score,
        "secondary": {
            key: mean_std(key)
            for key in (
                "test_pooled_iou",
                "far_gt_10_5px_recall",
                "growth_average_precision_macro",
                "growth_fcer_iou",
                "growth_fcer_ece_macro",
                "growth_fcer_selective_error_80_macro",
                "growth_fcer_aurc_macro",
                "observed_growth_fcer_capture_macro",
                "front_boundary_f1_macro",
            )
        },
        "gate": gate,
        "claims": {
            "event_disjoint_protocol": True,
            "normalization_train_only": True,
            "architecture_selected_on_validation_only": True,
            "test_evaluated_after_recipe_freeze": True,
            "uncertainty_unit": "fire_event",
            "single_dataset_external_generalization_not_proven": True,
            "wfigs_external_validation_pending": True,
        },
    }
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "PAPER_SCORECARD.json").write_text(
        json.dumps(scorecard, indent=2) + "\n", encoding="utf-8"
    )
    primary = scorecard["primary"]
    strongest_row = scorecard["strongest_baseline"]
    markdown = f"""# RCDA paper scorecard

Status: **{scorecard["status"]}**

- Event-macro growth IoU: **{primary["model_mean"]:.4f}** (event bootstrap 95% CI {primary["event_bootstrap_95_ci"][0]:.4f}–{primary["event_bootstrap_95_ci"][1]:.4f})
- Dilated-copy baseline: **{primary["dilated_copy"]:.4f}**
- Paired delta: **{primary["paired_delta"]:+.4f}** (95% CI {primary["paired_delta_event_bootstrap_95_ci"][0]:+.4f}–{primary["paired_delta_event_bootstrap_95_ci"][1]:+.4f})
- Strongest sealed baseline: **{strongest_row["id"]} = {strongest_row["event_macro_iou"]:.4f}**; paired delta **{strongest_row["paired_delta"]:+.4f}** (95% CI {strongest_row["paired_delta_event_bootstrap_95_ci"][0]:+.4f}–{strongest_row["paired_delta_event_bootstrap_95_ci"][1]:+.4f})
- Fires improved: **{100.0 * primary["events_improved_fraction"]:.1f}%**
- Seeds: **{len(seed_metrics)}**; TEST was never used for selection.

External validation on WFIGS remains pending and is required before a generalization claim.
"""
    (output_dir / "PAPER_SCORECARD.md").write_text(markdown, encoding="utf-8")
    return scorecard


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("final_summary", type=Path)
    parser.add_argument(
        "--baseline",
        type=Path,
        default=ROOT / "outputs/ml_eval/rcda_sealed_baselines/dilated_copy.json",
    )
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs/ml_eval/rcda_paper")
    parser.add_argument("--learned-baselines", type=Path)
    args = parser.parse_args()
    scorecard = build_scorecard(
        args.final_summary,
        args.baseline,
        args.output_dir,
        args.learned_baselines,
    )
    print(json.dumps({"status": scorecard["status"], "primary": scorecard["primary"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
