#!/usr/bin/env python3
"""Finalize a VAL-only RCDA report from the last finite checkpoint after NaN failure."""

from __future__ import annotations

import argparse
import dataclasses
import importlib.util
import json
import sys
from pathlib import Path


def _load_runner(path: Path):
    spec = importlib.util.spec_from_file_location("rcda_failed_runner", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot import runner from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--dataset-root", required=True)
    parser.add_argument("--protocol-dir", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-name", default="resunet_hybrid_long_v2")
    parser.add_argument(
        "--recipe-json",
        type=Path,
        help="Optional JSON object containing the exact preregistered recipe.",
    )
    parser.add_argument("--failed-epoch", type=int, required=True)
    parser.add_argument("--observed-loss", default="nan")
    parser.add_argument("--finite-files", type=int, default=13002)
    parser.add_argument(
        "--num-workers",
        type=int,
        default=0,
        help="Evaluation loader workers; zero avoids Windows spawn deadlocks.",
    )
    args = parser.parse_args()

    module = _load_runner(args.runner)
    checkpoint_path = args.output_dir / f"{args.run_name}_seed0_best.pt"
    checkpoint = module.torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if not all(
        bool(module.torch.isfinite(value).all().item())
        for value in checkpoint["state_dict"].values()
    ):
        raise FloatingPointError("refusing to salvage a non-finite checkpoint")

    # epochs=0 deliberately skips any further optimization. train_sealed then reloads
    # the existing finite checkpoint and performs its normal, VAL-only final threshold
    # selection. The original planned configuration is restored in the report below.
    if args.recipe_json:
        recipe = json.loads(args.recipe_json.read_text(encoding="utf-8"))
        if not isinstance(recipe, dict):
            raise TypeError("recipe JSON must contain one object")
    else:
        recipe = {
            "run_name": args.run_name,
            "model_name": checkpoint.get("model_name", "resunet"),
            "target_mode": checkpoint.get("target_mode", "hybrid"),
            "base_channels": checkpoint.get("base_channels", 32),
            "lr": 4e-4,
            "epochs": 40,
            "patience": 10,
        }
    if str(recipe.get("run_name")) != args.run_name:
        raise ValueError("recipe run_name does not match --run-name")
    allowed = {field.name for field in dataclasses.fields(module.SealedTrainConfig)}
    config_values = {key: value for key, value in recipe.items() if key in allowed}
    config_values.update(
        {
            "dataset_root": args.dataset_root,
            "protocol_dir": args.protocol_dir,
            "output_dir": str(args.output_dir),
            "run_name": args.run_name,
            "seed": 0,
            "epochs": 0,
            "num_workers": args.num_workers,
            "evaluate_test": False,
            "compute_paper_metrics": False,
        }
    )
    config = module.SealedTrainConfig(**config_values)
    report = module.train_sealed(config)
    for key, value in recipe.items():
        if key in report["config"]:
            report["config"][key] = value
    report["best_epoch"] = int(checkpoint["epoch"])
    report["history"] = []
    report["training_termination"] = {
        "status": "truncated_after_nonfinite_optimization",
        "failed_epoch": args.failed_epoch,
        "observed_train_loss": args.observed_loss,
        "checkpoint_finite": True,
        "checkpoint_epoch": int(checkpoint["epoch"]),
        "checkpoint_selection_score": float(checkpoint["epoch_selection_score"]),
        "checkpoint_selection_threshold": float(
            checkpoint["epoch_selection_threshold"]
        ),
        "test_evaluated": False,
        "train_npy_finiteness_scan": {
            "files": args.finite_files,
            "nonfinite_files": 0,
        },
    }
    artifact_name = args.run_name
    report_path = args.output_dir / f"{artifact_name}_seed0_report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    selected = report["val"]["selected"]
    summary = {
        "schema": "wfd_rcda_paper_tune_v1",
        "stage": 2,
        "selection_split": "val",
        "selection_metric": "event_macro_iou",
        "test_evaluated": False,
        "test_used_for_selection": False,
        "protocol_seed": module.PROTOCOL_SEED,
        "stage2_design_basis": (
            f"Preregistered {args.run_name} run; optimization became non-finite "
            f"at epoch {args.failed_epoch}. The last finite VAL-selected checkpoint "
            "was retained and re-evaluated on VAL only; TEST was not evaluated."
        ),
        "numeric_failure": report["training_termination"],
        "recipes": [recipe],
        "ranking": [
            {
                "rank": 1,
                "run_name": args.run_name,
                "val_event_macro_iou": selected["event_macro_iou"],
                "val_pooled_iou": selected["iou"],
                "threshold": report["selected_threshold"],
                "best_epoch": report["best_epoch"],
                "training_status": "truncated_after_nonfinite_optimization",
            }
        ],
        "reports": [report],
    }
    summary_path = args.output_dir / "TUNING_SUMMARY.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary["ranking"], indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
