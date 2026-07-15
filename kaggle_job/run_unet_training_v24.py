#!/usr/bin/env python3
"""U-Net v24 — clean12 schema + changed-filter train (single leap vs v21/v23).

Hypothesis H6 (M1):
  Train on changed patches with clean12 features; evaluate on any_fire protocol
  via cross-protocol later. Here we train+eval with filter_mode=changed for
  data loading, but report full-grid metrics on the same test split produced
  with --filter-mode any_fire when available.

Practical design:
  - Preprocess any_fire to data_dir (honest full test)
  - Optionally also build changed train — for simplicity: train on any_fire with
    weighted_sampler + change_loss, OR pure changed filter.

v24 single change vs v23_clean12: --filter-mode changed for train data root
  while keeping delta+residual.

Actually for M1 we need eval on any_fire 979. So:
  1. Preprocess any_fire → /tmp/ndws_npz_any_fire (val/test)
  2. Preprocess changed → /tmp/ndws_npz_changed (train only swap)
  Or train on changed and eval by loading any_fire test.

Simplest robust approach matching repo patterns:
  - data_dir = any_fire (full protocol)
  - weighted_sampler=True, change_loss_weight=5, target_mode=delta
  - schema=clean12
  - That is "changed emphasis" without broken split.

v24 flags: clean12 + higher change_loss_weight=8 + filter any_fire
  vs v23 which was clean12 any_fire change_loss 5.

User plan said: clean12 + filter_mode=changed train / eval any_fire.
Implement dual preprocess.
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

parser = argparse.ArgumentParser(description="Wildfire U-Net v24 clean12+changed emphasis")
parser.add_argument("--epochs", type=int, default=50)
parser.add_argument("--batch-size", type=int, default=32)
parser.add_argument("--lr", type=float, default=1e-3)
parser.add_argument("--loss", default="composite")
parser.add_argument("--pos-weight", type=float, default=5.0)
parser.add_argument("--model", default="small")
parser.add_argument("--architecture", default="residual")
parser.add_argument("--target-mode", default="delta")
parser.add_argument("--change-loss-weight", type=float, default=8.0)
parser.add_argument("--weighted-sampler", action="store_true", default=True)
parser.add_argument("--no-weighted-sampler", action="store_false", dest="weighted_sampler")
parser.add_argument("--early-stop-metric", default="improvement_vs_copy_iou")
parser.add_argument("--se-attention", action="store_true", default=False)
parser.add_argument("--norm", default="group")
parser.add_argument("--grad-accum", type=int, default=1)
parser.add_argument("--ema-decay", type=float, default=0.0)
parser.add_argument("--patience", type=int, default=12)
parser.add_argument("--deterministic", action="store_true", default=False)
parser.add_argument("--smoke-test", action="store_true", default=False)
parser.add_argument("--data-dir", type=str, default="/tmp/ndws_npz_v24")
parser.add_argument("--output-dir", type=str, default=None)
parser.add_argument("--version-tag", type=str, default="v24")
parser.add_argument("--schema", default="clean12")
parser.add_argument(
    "--train-filter",
    choices=["changed", "any_fire"],
    default="changed",
    help="Filter for training patches (eval always uses any_fire test if present).",
)
parser.add_argument("--clm-data-dir", type=str, default="")
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
print("WILDFIRE U-NET v24 — CLEAN12 + CHANGED TRAIN / ANY_FIRE EVAL")
print("=" * 70)
print(f"Config: {vars(args)}")

_install_pytorch_p100_compat()
_clone_and_enter()

from kaggle_job.kaggle_common import (  # noqa: E402
    default_output_dir,
    run_preprocess_ndws,
    verify_residual_imports,
)

verify_residual_imports(REPO_DIR)
args.clm_data_dir = None
print("[v24] CLM merge disabled (clean12 schema)")

if args.output_dir is None:
    args.output_dir = default_output_dir()

if not args.smoke_test:
    any_root = Path("/tmp/ndws_npz_any_fire_v24")
    chg_root = Path("/tmp/ndws_npz_changed_v24")
    run_preprocess_ndws(any_root, filter_mode="any_fire", schema=args.schema, min_total=50)
    run_preprocess_ndws(chg_root, filter_mode="changed", schema=args.schema, min_total=50)

    # Assemble hybrid data_dir: train from changed, val/test from any_fire
    data = Path(args.data_dir)
    if data.exists():
        shutil.rmtree(data)
    data.mkdir(parents=True)
    for split, src_root in (
        ("train", chg_root if args.train_filter == "changed" else any_root),
        ("val", any_root),
        ("test", any_root),
    ):
        src = src_root / split
        dst = data / split
        if src.is_dir():
            shutil.copytree(src, dst)
            print(f"  hybrid {split}: {len(list(dst.glob('*.npz')))} from {src_root.name}")
        else:
            print(f"  [WARN] missing {src}")

from wildfire_front.ml.unet_train import config_from_namespace, run_training  # noqa: E402

# expose filter_mode for logging only
args.filter_mode = "hybrid_changed_train_anyfire_eval"
config = config_from_namespace(args)
if not config.clm_data_dir:
    config.clm_data_dir = None
summary = run_training(config)
print("\n=== U-NET v24 COMPLETED ===")
print(f"  Model IoU (full): {summary.get('test_iou')}")
print(f"  Copy baseline:    {summary.get('copy_baseline_iou')}")
print(f"  Δ vs copy:        {summary.get('improvement_vs_copy_iou')}")
print(f"  Go M1 if IoU>=0.25 and delta>=0.09")
