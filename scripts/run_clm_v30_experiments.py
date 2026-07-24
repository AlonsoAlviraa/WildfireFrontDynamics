#!/usr/bin/env python3
"""v30 CLM experiment batch (transfer rail only — G1 NDWS killed).

Experiments (single change each vs v28 recipe):
  A) ensemble LOFO soft-vote (eval only) — scripts/eval_clm_ensemble.py
  B) early-stop on growth metric
  C) EMA fine-tune ema_decay=0.999

Usage:
  python scripts/run_clm_v30_experiments.py --only ensemble
  python scripts/run_clm_v30_experiments.py --only growth_es,ema
  python scripts/run_clm_v30_experiments.py --all
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

V28 = {
    "model_iou": 0.8382,
    "improvement_vs_copy_iou": 0.1964,
    "model_iou_growth": 0.694,
}


def _run_ensemble(include_v28: bool = False) -> dict:
    cmd = [sys.executable, str(ROOT / "scripts" / "eval_clm_ensemble.py"), "--install-product"]
    if include_v28:
        cmd.append("--include-v28")
    subprocess.check_call(cmd, cwd=str(ROOT))
    path = ROOT / "docs" / "V30_ENSEMBLE_VERDICT.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _run_ft(
    *,
    version_tag: str,
    early_stop_metric: str,
    ema_decay: float,
    epochs: int,
    patience: int,
    batch_size: int,
) -> dict:
    from wildfire_front.ml.unet_train import UNetTrainConfig, run_training

    init = ROOT / "models" / "production" / "weights_v21_best.pt"
    data = ROOT / "artifacts" / "clm_ndws_patches" / "holdout_v1"
    out = ROOT / "outputs" / "ml_eval" / version_tag
    cfg = UNetTrainConfig(
        epochs=epochs,
        batch_size=batch_size,
        lr=3e-4,
        loss="composite",
        pos_weight=5.0,
        model="small",
        architecture="residual",
        target_mode="delta",
        change_loss_weight=5.0,
        weighted_sampler=True,
        patience=patience,
        data_dir=str(data),
        output_dir=str(out),
        version_tag=version_tag,
        early_stop_metric=early_stop_metric,
        init_weights_path=str(init),
        ema_decay=ema_decay,
        clm_data_dir=None,
    )
    print("=" * 70)
    print(f"TRAIN {version_tag}")
    print("  early_stop:", early_stop_metric)
    print("  ema_decay:", ema_decay)
    print("  out:", out)
    print("=" * 70)
    summary = run_training(cfg)
    weights = out / "weights_pretrained_best.pt"

    # Honest re-eval via shared metric stack
    from wildfire_front.ml.clm_eval import evaluate_clm_weights

    metrics = evaluate_clm_weights(
        weights,
        data / "test",
        max_patches=400,
    )
    report = {
        "version": version_tag,
        "rail": "transfer",
        "single_change": {
            "v30_growth_es": "early_stop_metric=model_iou_growth only",
            "v30_ema": "ema_decay=0.999 only",
        }.get(version_tag, "unknown"),
        "early_stop_metric": early_stop_metric,
        "ema_decay": ema_decay,
        "training_summary": {
            "test_iou": summary.get("test_iou"),
            "improvement_vs_copy_iou": summary.get("improvement_vs_copy_iou"),
            "model_iou_growth": summary.get("model_iou_growth"),
            "best_epoch": summary.get("best_epoch"),
            "epochs_ran": summary.get("epochs_ran") or summary.get("epochs"),
        },
        "holdout_test_eval": {
            "model_iou": metrics["model_iou"],
            "copy_baseline_iou": metrics["copy_baseline_iou"],
            "improvement_vs_copy_iou": metrics["improvement_vs_copy_iou"],
            "model_iou_growth": metrics["model_iou_growth"],
            "improvement_vs_dilated_copy_iou_growth": metrics[
                "improvement_vs_dilated_copy_iou_growth"
            ],
            "n_patches": metrics["n_patches"],
        },
        "vs_v28": {
            "iou_diff": metrics["model_iou"] - V28["model_iou"],
            "delta_diff": metrics["improvement_vs_copy_iou"] - V28["improvement_vs_copy_iou"],
            "growth_diff": metrics["model_iou_growth"] - V28["model_iou_growth"],
            "beats_v28_iou": metrics["model_iou"] > V28["model_iou"],
            "beats_v28_delta": metrics["improvement_vs_copy_iou"] > V28["improvement_vs_copy_iou"],
        },
        "weights": str(weights),
        "generated_at_utc": datetime.now(UTC).isoformat(),
    }
    iou = metrics["model_iou"]
    delta = metrics["improvement_vs_copy_iou"]
    growth = metrics["model_iou_growth"]
    if (iou >= 0.845 or delta >= 0.205) and growth >= 0.69:
        report["verdict"] = "GO_PROMOTE"
    elif metrics["improvement_vs_copy_iou"] > V28["improvement_vs_copy_iou"] and growth >= 0.68:
        report["verdict"] = "GO_SOFT"
    elif delta > 0:
        report["verdict"] = "NO_PROMOTE_KEEP_V28"
    else:
        report["verdict"] = "NO_GO_REGRESSION"
    report["go"] = report["verdict"].startswith("GO")

    out.mkdir(parents=True, exist_ok=True)
    report_path = out / f"{version_tag}_verdict.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    docs = ROOT / "docs" / f"{version_tag.upper()}_VERDICT.json"
    docs.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print("Wrote", report_path)
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--only",
        type=str,
        default="ensemble",
        help="Comma list: ensemble,growth_es,ema  or  all",
    )
    ap.add_argument("--epochs", type=int, default=20)
    ap.add_argument("--patience", type=int, default=6)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--include-v28-in-ensemble", action="store_true")
    args = ap.parse_args()

    only = args.only.strip().lower()
    if only == "all":
        jobs = ["ensemble", "growth_es", "ema"]
    else:
        jobs = [j.strip() for j in only.split(",") if j.strip()]

    results: dict = {
        "batch": "v30_clm",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "jobs": jobs,
        "baseline_v28": V28,
        "experiments": {},
    }

    if "ensemble" in jobs:
        results["experiments"]["v30_clm_ensemble"] = _run_ensemble(
            include_v28=args.include_v28_in_ensemble
        )
    if "growth_es" in jobs:
        results["experiments"]["v30_growth_es"] = _run_ft(
            version_tag="v30_growth_es",
            early_stop_metric="model_iou_growth",
            ema_decay=0.0,
            epochs=args.epochs,
            patience=args.patience,
            batch_size=args.batch_size,
        )
    if "ema" in jobs:
        results["experiments"]["v30_ema"] = _run_ft(
            version_tag="v30_ema",
            early_stop_metric="improvement_vs_copy_iou",
            ema_decay=0.999,
            epochs=args.epochs,
            patience=args.patience,
            batch_size=args.batch_size,
        )

    scorecard = ROOT / "docs" / "V30_ML_SCORECARD.json"
    scorecard.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print("SCORECARD", scorecard)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
