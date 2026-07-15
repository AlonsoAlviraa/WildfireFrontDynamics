#!/usr/bin/env python3
"""v28 — CLM fine-tune from v21 on frozen holdout (rail: Transfer).

Train: holdout_v1/train
Val:   holdout_v1/val  (early-stop on improvement_vs_copy_iou)
Test:  holdout_v1/test (G2 report)

Single change vs zero-shot v21 eval: fine-tune weights on CLM train only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--data-dir",
        type=Path,
        default=ROOT / "artifacts" / "clm_ndws_patches" / "holdout_v1",
    )
    p.add_argument(
        "--init-weights",
        type=Path,
        default=None,
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "outputs" / "ml_eval" / "v28_clm_ft",
    )
    p.add_argument("--epochs", type=int, default=30)
    p.add_argument("--batch-size", type=int, default=8)
    p.add_argument("--lr", type=float, default=3e-4)
    p.add_argument("--patience", type=int, default=8)
    args = p.parse_args()

    weight_candidates = [
        args.init_weights,
        ROOT / "kaggle_outputs_v21" / "weights_pretrained_best.pt",
        ROOT / "models" / "production" / "weights_v21_best.pt",
    ]
    init = next((w for w in weight_candidates if w is not None and Path(w).is_file()), None)
    if init is None:
        print("No v21 weights found")
        return 1
    for split in ("train", "val", "test"):
        d = args.data_dir / split
        if not d.is_dir() or not list(d.glob("*.npz")):
            print(f"Missing holdout split {d} — run build_clm_holdout_splits.py")
            return 1

    from wildfire_front.ml.unet_train import UNetTrainConfig, run_training

    args.output_dir.mkdir(parents=True, exist_ok=True)
    config = UNetTrainConfig(
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        loss="composite",
        pos_weight=5.0,
        model="small",
        architecture="residual",
        target_mode="delta",
        change_loss_weight=5.0,
        weighted_sampler=True,
        patience=args.patience,
        data_dir=str(args.data_dir),
        output_dir=str(args.output_dir),
        version_tag="v28_clm_ft",
        early_stop_metric="improvement_vs_copy_iou",
        init_weights_path=str(init),
        clm_data_dir=None,
    )
    print("=" * 70)
    print("V28 CLM FINE-TUNE (transfer rail)")
    print("  init:", init)
    print("  data:", args.data_dir)
    print("  out:", args.output_dir)
    print("=" * 70)
    summary = run_training(config)

    # Zero-shot baseline on same test for comparison
    from scripts.eval_clm_transfer import main as _  # noqa: F401

    zero_shot_path = ROOT / "outputs" / "ml_eval" / "clm_transfer_report.json"
    zero = {}
    if zero_shot_path.is_file():
        zero = json.loads(zero_shot_path.read_text(encoding="utf-8"))

    report = {
        "version": "v28_clm_ft",
        "rail": "transfer",
        "single_change": "fine-tune v21 on CLM holdout train; eval test",
        "init_weights": str(init),
        "data_dir": str(args.data_dir),
        "test_iou": summary.get("test_iou"),
        "copy_baseline_iou": summary.get("copy_baseline_iou"),
        "improvement_vs_copy_iou": summary.get("improvement_vs_copy_iou"),
        "improvement_vs_copy_iou_changed": summary.get("improvement_vs_copy_iou_changed"),
        "best_epoch": summary.get("best_epoch"),
        "zero_shot_v21": {
            "model_iou": zero.get("model_iou"),
            "delta": zero.get("improvement_vs_copy_iou"),
            "protocol": zero.get("protocol"),
        },
        "g2": bool((summary.get("improvement_vs_copy_iou") or 0) > 0),
        "beats_zero_shot": (
            zero.get("improvement_vs_copy_iou") is not None
            and summary.get("improvement_vs_copy_iou") is not None
            and float(summary["improvement_vs_copy_iou"])
            > float(zero["improvement_vs_copy_iou"])
        ),
    }
    out = args.output_dir / "v28_transfer_report.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print("Wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
