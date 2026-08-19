#!/usr/bin/env python3
"""Audit a validation-only RCDA sweep and freeze the paper recipe."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BASELINE_VAL_EVENT_MACRO_IOU = 0.15688960608552976
FINAL_SEEDS = (11, 29, 47)
RCDA_ARCHIVE_MD5 = "d7856d77dcb823d0bdb5e10c6bac4f87"
PROTOCOL_SEED = "wfd_rcda_event_split_v1"


def validate_tuning_report(report: dict[str, Any]) -> None:
    """Enforce report-level TEST isolation before ranking or adaptive gates."""

    if report.get("test_evaluated") is not False or "test_once" in report:
        raise ValueError("a tuning report evaluated TEST")
    if report.get("threshold_selected_on") != "val":
        raise ValueError("a tuning report did not select threshold on VAL")
    if report.get("test_used_for_selection") is not False:
        raise ValueError("a tuning report does not assert TEST isolation")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def merge_tuning_summaries(paths: list[Path], output_path: Path) -> dict[str, Any]:
    """Merge preregistered VAL-only stages without observing TEST."""

    if len(paths) < 2:
        raise ValueError("at least two tuning stages are required")
    documents = [json.loads(Path(path).read_text(encoding="utf-8")) for path in paths]
    for document in documents:
        if document.get("schema") != "wfd_rcda_paper_tune_v1":
            raise ValueError("unexpected RCDA tuning schema")
        if document.get("selection_split") != "val":
            raise ValueError("a tuning stage was not selected on VAL")
        if document.get("test_evaluated") is not False:
            raise ValueError("a tuning stage evaluated TEST")
    reports = [report for document in documents for report in document.get("reports") or []]
    for report in reports:
        validate_tuning_report(report)
    if len({str(row["config"]["run_name"]) for row in reports}) != len(reports):
        raise ValueError("duplicate run_name across tuning stages")
    ranked = sorted(
        reports,
        key=lambda row: float(row["val"]["selected"]["event_macro_iou"]),
        reverse=True,
    )
    merged = {
        "schema": "wfd_rcda_paper_tune_v1",
        "stage": "combined",
        "selection_split": "val",
        "selection_metric": "event_macro_iou",
        "test_evaluated": False,
        "test_used_for_selection": False,
        "source_summaries": [str(path) for path in paths],
        "source_summary_sha256": [_sha256(Path(path)) for path in paths],
        "reports": reports,
        "ranking": [
            {
                "rank": index + 1,
                "run_name": row["config"]["run_name"],
                "val_event_macro_iou": row["val"]["selected"]["event_macro_iou"],
                "val_pooled_iou": row["val"]["selected"]["iou"],
            }
            for index, row in enumerate(ranked)
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    return merged


def freeze_recipe(summary_path: Path, output_path: Path) -> dict[str, Any]:
    summary_path = Path(summary_path)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("schema") != "wfd_rcda_paper_tune_v1":
        raise ValueError("unexpected RCDA tuning schema")
    if summary.get("selection_split") != "val" or summary.get("test_evaluated") is not False:
        raise ValueError("tuning summary is not validation-only")
    reports = list(summary.get("reports") or [])
    if not reports:
        raise ValueError("tuning summary contains no reports")
    for report in reports:
        validate_tuning_report(report)
    ranked = sorted(
        reports,
        key=lambda row: float(row["val"]["selected"]["event_macro_iou"]),
        reverse=True,
    )
    winner = ranked[0]
    winner_config = dict(winner["config"])
    allowed_config = {
        key: winner_config[key]
        for key in (
            "run_name",
            "model_name",
            "target_mode",
            "lr",
            "weight_decay",
            "epochs",
            "batch_size",
            "patience",
            "loss_name",
            "tversky_alpha",
            "tversky_beta",
            "tversky_gamma",
            "extent_loss_weight",
            "growth_loss_weight",
            "base_channels",
            "scheduler_name",
            "selection_metric",
            "sampling_strategy",
            "event_balance_power",
        )
        if key in winner_config
    }
    allowed_config["weighted_sampling"] = bool(winner_config.get("weighted_sampling", True))
    allowed_config["sampling_strategy"] = str(
        winner_config.get("sampling_strategy", "size_event_power")
    )
    allowed_config["event_balance_power"] = float(
        winner_config.get("event_balance_power", 0.5)
    )
    winner_score = float(winner["val"]["selected"]["event_macro_iou"])
    decoder_path = summary_path.parent / "LOW_LR_POSTPROCESS_VAL.json"
    secondary_decoder = None
    if decoder_path.is_file():
        decoder_report = json.loads(decoder_path.read_text(encoding="utf-8"))
        decoder_best = decoder_report.get("best") or {}
        if not (
            decoder_report.get("schema") == "wfd_rcda_val_postprocess_tune_v1"
            and decoder_report.get("selection_split") == "val"
            and decoder_report.get("test_evaluated") is False
            and decoder_report.get("test_used_for_selection") is False
        ):
            raise ValueError("spatial decoder artifact is not validation-only")
        if (
            decoder_report.get("run_name") == allowed_config.get("run_name")
            and decoder_report.get("model_name") == allowed_config.get("model_name")
            and decoder_report.get("target_mode") == allowed_config.get("target_mode")
        ):
            secondary_decoder = {
                "role": "preregistered_secondary_spatial_decoder",
                "applied_to": "mean_seed_probability",
                "source_run_name": decoder_report.get("run_name"),
                "source_artifact_sha256": _sha256(decoder_path),
                "threshold": float(decoder_best["threshold"]),
                "dilation_radius_px": int(decoder_best["dilation_radius_px"]),
                "require_t0_connection": bool(
                    decoder_best["require_t0_connection"]
                ),
                "threshold_and_geometry_selected_on": "val",
                "test_evaluated_once_after_recipe_freeze": True,
                "changes_primary_endpoint_or_gate": False,
            }
    protocol_root = ROOT / "data/external/rcda_net_full/protocol"
    protocol_hashes = {
        name: _sha256(protocol_root / name)
        for name in (
            "train.json",
            "val.json",
            "test.json",
            "normalization_train_only.json",
        )
        if (protocol_root / name).is_file()
    }
    pretest_decision_path = Path(summary_path).parent / "PRETEST_DECISION_LOG.json"
    if not pretest_decision_path.is_file():
        raise FileNotFoundError(
            f"cannot freeze without pre-TEST decision log: {pretest_decision_path}"
        )
    frozen = {
        "schema": "wfd_rcda_paper_frozen_recipe_v1",
        "frozen_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "source_summary": str(summary_path),
        "source_summary_sha256": _sha256(summary_path),
        "selection_split": "val",
        "selection_metric": "event_macro_iou",
        "test_observed_during_tuning": False,
        "data_contract": {
            "rcda_archive_md5": RCDA_ARCHIVE_MD5,
            "event_split_seed": PROTOCOL_SEED,
            "normalization_fit_split": "train",
            "protocol_sha256": protocol_hashes,
            "pretest_decision_log_sha256": (
                _sha256(pretest_decision_path)
            ),
        },
        "winner": {
            "rank": 1,
            "val_event_macro_iou": winner_score,
            "val_pooled_iou": float(winner["val"]["selected"]["iou"]),
            "selected_threshold": float(winner["selected_threshold"]),
            "best_epoch": int(winner["best_epoch"]),
            "config": allowed_config,
        },
        "comparison_to_previous_validation_champion": {
            "previous_val_event_macro_iou": BASELINE_VAL_EVENT_MACRO_IOU,
            "absolute_delta": winner_score - BASELINE_VAL_EVENT_MACRO_IOU,
        },
        "final_evaluation": {
            "seeds": list(FINAL_SEEDS),
            "recipe_changes_after_test_forbidden": True,
            "threshold_and_epoch_selected_on_val_per_seed": True,
            "test_evaluated_once_per_preregistered_seed": True,
            "primary_test_metric": "event_macro_iou_mean_across_seeds",
            "secondary_probability_ensemble": {
                "aggregation": "mean_seed_probability",
                "threshold_selected_on": "val",
                "test_evaluated_once_after_threshold_freeze": True,
                "changes_primary_endpoint_or_gate": False,
            },
            "secondary_spatial_decoder": secondary_decoder,
            "secondary_metrics": [
                "pooled_iou",
                "growth_average_precision_macro",
                "growth_fcer_iou",
                "growth_fcer_ece_macro",
                "growth_fcer_selective_error_80_macro",
                "growth_fcer_aurc_macro",
                "observed_growth_fcer_capture_macro",
                "front_boundary_f1_macro",
                "far_gt_10_5px_recall",
            ],
        },
        "ranking": [
            {
                "rank": index + 1,
                "run_name": row["config"]["run_name"],
                "val_event_macro_iou": row["val"]["selected"]["event_macro_iou"],
                "val_pooled_iou": row["val"]["selected"]["iou"],
            }
            for index, row in enumerate(ranked)
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(frozen, indent=2) + "\n", encoding="utf-8")
    return frozen


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summary", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "outputs/ml_eval/rcda_paper/FROZEN_RECIPE.json",
    )
    args = parser.parse_args()
    frozen = freeze_recipe(args.summary, args.output)
    print(json.dumps(frozen["winner"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
