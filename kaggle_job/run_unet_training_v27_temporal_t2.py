#!/usr/bin/env python3
"""v27 — temporal rail T=2 on production stack (legacy17 residual+delta).

Single change vs v21 protocol: sequence_length=2 (real consecutive frames).
G1 attempt after physics14/15 feature rail failed to beat v21.
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

parser = argparse.ArgumentParser(description="v27 temporal T=2")
parser.add_argument("--epochs", type=int, default=50)
parser.add_argument("--batch-size", type=int, default=32)
parser.add_argument("--lr", type=float, default=1e-3)
parser.add_argument("--loss", default="composite")
parser.add_argument("--pos-weight", type=float, default=5.0)
parser.add_argument("--model", default="small")
parser.add_argument("--architecture", default="residual")
parser.add_argument("--target-mode", default="delta")
parser.add_argument("--change-loss-weight", type=float, default=5.0)
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
parser.add_argument("--data-dir", type=str, default="/tmp/ndws_npz_legacy17_t2")
parser.add_argument("--output-dir", type=str, default=None)
parser.add_argument("--version-tag", type=str, default="v27_temporal_t2")
parser.add_argument("--schema", default="legacy17")
parser.add_argument("--filter-mode", default="any_fire")
parser.add_argument("--sequence-length", type=int, default=2)
parser.add_argument("--clm-data-dir", type=str, default="")
args, _ = parser.parse_known_args()


def _clone() -> None:
    if REPO_DIR.exists():
        shutil.rmtree(REPO_DIR)
    subprocess.run(["git", "clone", "--depth", "1", REPO_URL, str(REPO_DIR)], check=True)
    os.chdir(REPO_DIR)
    sys.path.insert(0, str(REPO_DIR))


print("=" * 70)
print("V27 TEMPORAL T=2 — sequence_length=2 on legacy17 residual+delta")
print("=" * 70)
_clone()

from kaggle_job.kaggle_common import default_output_dir, run_preprocess_ndws, verify_residual_imports

verify_residual_imports(REPO_DIR)
args.clm_data_dir = None
if args.output_dir is None:
    args.output_dir = default_output_dir()
if not args.smoke_test:
    run_preprocess_ndws(
        Path(args.data_dir),
        filter_mode=args.filter_mode,
        schema=args.schema,
        sequence_length=int(args.sequence_length),
        min_total=50,
    )

from wildfire_front.ml.unet_train import config_from_namespace, run_training

config = config_from_namespace(args)
config.clm_data_dir = None
summary = run_training(config)
print(
    "v27 IoU",
    summary.get("test_iou"),
    "delta",
    summary.get("improvement_vs_copy_iou"),
    "T=",
    args.sequence_length,
)
