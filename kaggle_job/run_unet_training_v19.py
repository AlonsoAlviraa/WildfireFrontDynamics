#!/usr/bin/env python3
"""U-Net training v19 — Changed-pixel pivot (consolidated module).

Scientific pivot after v14–v18 plateau:
  - Train with upweighted loss on pixels where fire mask changes
  - Early-stop on improvement_vs_copy_iou_changed (not raw val_loss)
  - Preprocess with --filter-mode any_fire (removes biased both_fire filter)
  - WeightedRandomSampler favors high-change patches

All training logic lives in ``wildfire_front.ml.unet_train``.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

parser = argparse.ArgumentParser(description="Wildfire U-Net v19 — changed-pixel pivot")
parser.add_argument("--epochs", type=int, default=50)
parser.add_argument("--batch-size", type=int, default=32)
parser.add_argument("--lr", type=float, default=1e-3)
parser.add_argument("--loss", choices=["combined", "composite", "tversky", "focal", "bce"],
                    default="composite")
parser.add_argument("--pos-weight", type=float, default=5.0)
parser.add_argument("--model", choices=["full", "small"], default="small")
parser.add_argument("--architecture", choices=["standard", "residual"], default="standard")
parser.add_argument("--target-mode", choices=["absolute", "delta", "changed_weighted"],
                    default="changed_weighted")
parser.add_argument("--change-loss-weight", type=float, default=5.0)
parser.add_argument("--weighted-sampler", action="store_true", default=True)
parser.add_argument("--no-weighted-sampler", action="store_false", dest="weighted_sampler")
parser.add_argument(
    "--early-stop-metric",
    choices=["improvement_vs_copy_iou_changed", "improvement_vs_copy_iou", "val_loss"],
    default="improvement_vs_copy_iou_changed",
)
parser.add_argument("--se-attention", action="store_true", default=False)
parser.add_argument("--norm", choices=["group", "batch", "instance"], default="group")
parser.add_argument("--grad-accum", type=int, default=1)
parser.add_argument("--ema-decay", type=float, default=0.0)
parser.add_argument("--patience", type=int, default=10)
parser.add_argument("--deterministic", action="store_true", default=False)
parser.add_argument("--smoke-test", action="store_true", default=False)
parser.add_argument("--data-dir", type=str, default="/tmp/ndws_npz")
parser.add_argument("--output-dir", type=str, default=None)
parser.add_argument("--version-tag", type=str, default="v19")
parser.add_argument(
    "--filter-mode",
    choices=["both_fire", "any_fire", "changed", "none"],
    default="any_fire",
)
parser.add_argument(
    "--clm-data-dir",
    type=str,
    default=None,
    help="Castilla-La Mancha NPZ patches to merge into NDWS splits.",
)
args, _ = parser.parse_known_args()

# Auto-detect CLM dataset on Kaggle
if args.clm_data_dir is None:
    for candidate in (
        "/kaggle/input/clm-wildfire-patches",
        "/kaggle/input/datasets/alonsoalviraaaa/clm-wildfire-patches",
    ):
        if os.path.isdir(candidate):
            args.clm_data_dir = candidate
            print(f"[clm] Found dataset at {candidate}")
            break

print("=" * 70)
print("WILDFIRE U-NET v19 — CHANGED-PIXEL PIVOT")
print("=" * 70)
print(f"Config: {vars(args)}")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kaggle_common import (  # noqa: E402
    default_output_dir,
    install_pytorch_p100_compat,
    run_preprocess_ndws,
)

install_pytorch_p100_compat()

if not Path("WildfireFrontDynamics").exists():
    print("Cloning repository...")
    subprocess.run(
        [
            "git", "clone", "--depth", "1",
            "https://github.com/AlonsoAlviraa/WildfireFrontDynamics.git",
        ],
        check=True,
    )

if Path("WildfireFrontDynamics").exists():
    os.chdir("WildfireFrontDynamics")
    sys.path.insert(0, os.getcwd())

if args.output_dir is None:
    args.output_dir = default_output_dir()

data_root = Path(args.data_dir)
if not args.smoke_test:
    script = Path("kaggle_job/preprocess_ndws.py")
    if not script.exists():
        script = Path(__file__).resolve().parent / "preprocess_ndws.py"
    total = sum(
        len(list((data_root / s).glob("*.npz")))
        for s in ("train", "val", "test")
        if (data_root / s).exists()
    )
    if total < 100:
        print(f"\n=== PREPROCESSING (filter-mode={args.filter_mode}) ===")
        for split in ("train", "val", "test"):
            out_split = data_root / split
            existing = len(list(out_split.glob("*.npz"))) if out_split.exists() else 0
            if existing > 10:
                print(f"  {split}: {existing} patches exist, skipping")
                continue
            cmd = [
                sys.executable, str(script),
                "--split", split,
                "--patch-size", "64",
                "--filter-mode", args.filter_mode,
            ]
            subprocess.run(cmd, check=True)
    else:
        print(f"Data already preprocessed ({total} patches)")

from wildfire_front.ml.unet_train import config_from_namespace, run_training  # noqa: E402

config = config_from_namespace(args)
summary = run_training(config)
print("\n=== U-NET v19 COMPLETED ===")
print(f"  Model IoU: {summary['test_iou']:.4f}")
print(f"  Copy baseline IoU: {summary['copy_baseline_iou']:.4f}")
print(f"  Δ vs copy (changed pixels): {summary['improvement_vs_copy_iou_changed']:+.4f}")