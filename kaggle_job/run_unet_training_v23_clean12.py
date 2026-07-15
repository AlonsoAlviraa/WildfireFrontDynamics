#!/usr/bin/env python3
"""U-Net training v23-clean12 — informative feature schema (Kaggle-safe).

Single primary variable vs v21:
  --schema clean12  (12 channels, no constant padding; wind sin/cos; elevation)

Architecture/target remain Residual + delta (v21 winners).
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

parser = argparse.ArgumentParser(description="Wildfire U-Net v23 — clean12 feature schema")
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
parser.add_argument("--patience", type=int, default=12)
parser.add_argument("--deterministic", action="store_true", default=False)
parser.add_argument("--smoke-test", action="store_true", default=False)
parser.add_argument("--data-dir", type=str, default="/tmp/ndws_npz_clean12")
parser.add_argument("--output-dir", type=str, default=None)
parser.add_argument("--version-tag", type=str, default="v23_clean12")
parser.add_argument(
    "--filter-mode",
    choices=["both_fire", "any_fire", "changed", "none"],
    default="any_fire",
)
parser.add_argument(
    "--schema",
    choices=["legacy17", "clean12"],
    default="clean12",
)
parser.add_argument(
    "--clm-data-dir",
    type=str,
    default="",
    help="CLM patches path; empty = do not merge (clean12 channels ≠ legacy CLM 17ch).",
)
parser.add_argument(
    "--merge-clm",
    action="store_true",
    default=False,
    help="Force CLM merge (only if CLM patches match clean12 sequence shape).",
)
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
print("WILDFIRE U-NET v23 — CLEAN12 FEATURE SCHEMA")
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

# clean12 (12ch) is incompatible with existing CLM patches (17ch legacy).
# Only merge when explicitly requested AND a path is provided.
if args.merge_clm:
    if not args.clm_data_dir:
        args.clm_data_dir = detect_clm_dataset() or ""
else:
    args.clm_data_dir = None
    print("[v23] CLM merge disabled (schema clean12 ≠ legacy CLM 17-channel patches)")

if args.output_dir is None:
    args.output_dir = default_output_dir()

if not args.smoke_test:
    run_preprocess_ndws(
        Path(args.data_dir),
        filter_mode=args.filter_mode,
        schema=args.schema,
        min_total=50,
    )

from wildfire_front.ml.unet_train import config_from_namespace, run_training  # noqa: E402

config = config_from_namespace(args)
# Empty string from argparse must not enable merge.
if not config.clm_data_dir:
    config.clm_data_dir = None
summary = run_training(config)
print("\n=== U-NET v23 CLEAN12 COMPLETED ===")
print(f"  Model IoU (full): {summary['test_iou']:.4f}")
print(f"  Copy baseline:    {summary['copy_baseline_iou']:.4f}")
print(f"  Δ vs copy:        {summary['improvement_vs_copy_iou']:.4f}")
