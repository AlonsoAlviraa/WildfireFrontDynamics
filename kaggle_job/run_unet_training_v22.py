#!/usr/bin/env python3
"""U-Net training v22 — changed-only filter (Kaggle-safe).

Single variable vs v21: --filter-mode changed.
Clone lives under /tmp (not /kaggle/working) to avoid output bloat.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_URL = "https://github.com/AlonsoAlviraa/WildfireFrontDynamics.git"
REPO_DIR = Path("/tmp/WildfireFrontDynamics")

parser = argparse.ArgumentParser(description="Wildfire U-Net v22 — changed-only training filter")
parser.add_argument("--epochs", type=int, default=50)
parser.add_argument("--batch-size", type=int, default=32)
parser.add_argument("--lr", type=float, default=1e-3)
parser.add_argument("--loss", choices=["combined", "composite", "tversky", "focal", "bce"],
                    default="composite")
parser.add_argument("--pos-weight", type=float, default=5.0)
parser.add_argument("--model", choices=["full", "small"], default="small")
parser.add_argument("--architecture", choices=["standard", "residual"], default="residual")
parser.add_argument("--target-mode", choices=["absolute", "delta", "changed_weighted"],
                    default="delta")
parser.add_argument("--change-loss-weight", type=float, default=5.0)
parser.add_argument("--weighted-sampler", action="store_true", default=True)
parser.add_argument("--no-weighted-sampler", action="store_false", dest="weighted_sampler")
parser.add_argument(
    "--early-stop-metric",
    choices=[
        "improvement_vs_copy_iou",
        "improvement_vs_copy_iou_changed",
        "improvement_vs_dilated_copy_iou",
        "val_loss",
    ],
    default="improvement_vs_copy_iou",
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
parser.add_argument("--version-tag", type=str, default="v22")
parser.add_argument(
    "--filter-mode",
    choices=["both_fire", "any_fire", "changed", "none"],
    default="changed",
)
parser.add_argument("--clm-data-dir", type=str, default=None)
args, _ = parser.parse_known_args()


def _install_pytorch_p100_compat() -> None:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0 or "P100" not in result.stdout:
            return
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q",
             "torch==2.1.2", "torchvision==0.16.2"],
            check=False,
        )
    except Exception:
        pass


def _clone_and_enter() -> None:
    if REPO_DIR.exists():
        shutil.rmtree(REPO_DIR)
    print("Cloning repository to /tmp ...")
    subprocess.run(["git", "clone", "--depth", "1", REPO_URL, str(REPO_DIR)], check=True)
    os.chdir(REPO_DIR)
    sys.path.insert(0, str(REPO_DIR))


print("=" * 70)
print("WILDFIRE U-NET v22 — CHANGED-ONLY FILTER")
print("=" * 70)
print(f"Config: {vars(args)}")

_install_pytorch_p100_compat()
_clone_and_enter()

from kaggle_job.kaggle_common import (  # noqa: E402
    default_output_dir,
    detect_clm_dataset,
    run_preprocess_ndws,
    verify_residual_imports,
)

verify_residual_imports(REPO_DIR)

if args.clm_data_dir is None:
    args.clm_data_dir = detect_clm_dataset()

if args.output_dir is None:
    args.output_dir = default_output_dir()

if not args.smoke_test:
    run_preprocess_ndws(Path(args.data_dir), filter_mode=args.filter_mode, min_total=50)

from wildfire_front.ml.unet_train import config_from_namespace, run_training  # noqa: E402

config = config_from_namespace(args)
summary = run_training(config)
print("\n=== U-NET v22 COMPLETED ===")
print(f"  Model IoU (full): {summary['test_iou']:.4f}")
print(f"  Copy baseline IoU: {summary['copy_baseline_iou']:.4f}")
print(f"  delta vs copy (full): {summary['improvement_vs_copy_iou']:+.4f}")
print(
    f"  delta vs dilated copy (changed): {summary['improvement_vs_copy_iou_changed']:+.4f}  "
    f"(legacy naive: {summary['legacy_improvement_vs_naive_copy_iou_changed']:+.4f})"
)