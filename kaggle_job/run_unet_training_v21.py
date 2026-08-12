#!/usr/bin/env python3
"""U-Net training v21 — Delta target + residual (Kaggle-safe).

Single variable vs v20: --target-mode delta (growth-only loss target).
Hypothesis: predicting only new fire pixels reduces full-grid false positives.
Early-stop: improvement_vs_copy_iou (honest full-grid metric).
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

REPO_URL = "https://github.com/AlonsoAlviraa/WildfireFrontDynamics.git"
REPO_DIR = Path("WildfireFrontDynamics")

parser = argparse.ArgumentParser(description="Wildfire U-Net v21 — delta target + residual")
parser.add_argument("--epochs", type=int, default=50)
parser.add_argument("--batch-size", type=int, default=32)
parser.add_argument("--lr", type=float, default=1e-3)
parser.add_argument(
    "--loss", choices=["combined", "composite", "tversky", "focal", "bce"], default="composite"
)
parser.add_argument("--pos-weight", type=float, default=5.0)
parser.add_argument("--model", choices=["full", "small"], default="small")
parser.add_argument("--architecture", choices=["standard", "residual"], default="residual")
parser.add_argument(
    "--target-mode", choices=["absolute", "delta", "changed_weighted"], default="delta"
)
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
parser.add_argument("--version-tag", type=str, default="v21")
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


def _default_output_dir() -> str:
    if os.path.isdir("/kaggle/working"):
        return "/kaggle/working"
    return "."


def _install_pytorch_p100_compat() -> None:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0 or "P100" not in result.stdout:
            return
        print("  P100 detected — attempting PyTorch 2.1.2 (sm_60 support)...")
        pip_result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", "torch==2.1.2", "torchvision==0.16.2"],
            capture_output=True,
            text=True,
            timeout=600,
        )
        if pip_result.returncode == 0:
            print("  PyTorch 2.1.2 installed.")
        else:
            print("  [WARN] PyTorch 2.1.2 unavailable — using preinstalled PyTorch.")
    except Exception as exc:
        print(f"  [WARN] P100 PyTorch fix skipped: {exc}")


def _detect_clm_dataset() -> str | None:
    for candidate in (
        "/kaggle/input/clm-wildfire-patches",
        "/kaggle/input/datasets/alonsoalviraaaa/clm-wildfire-patches",
    ):
        root = Path(candidate)
        if not root.is_dir():
            continue
        train_zip = root / "train.zip"
        if train_zip.exists() and not (root / "train").is_dir():
            print(f"[clm] Extracting {train_zip} ...")
            with zipfile.ZipFile(train_zip, "r") as zf:
                zf.extractall(root)
        if (root / "train").is_dir():
            print(f"[clm] Found dataset at {candidate}")
            return candidate
    return None


if args.clm_data_dir is None:
    args.clm_data_dir = _detect_clm_dataset()

print("=" * 70)
print("WILDFIRE U-NET v21 — DELTA TARGET + RESIDUAL")
print("=" * 70)
print(f"Config: {vars(args)}")

_install_pytorch_p100_compat()


def _clone_repo_fresh() -> None:
    if REPO_DIR.exists():
        print("Removing stale WildfireFrontDynamics clone...")
        shutil.rmtree(REPO_DIR)
    print("Cloning repository...")
    subprocess.run(["git", "clone", "--depth", "1", REPO_URL], check=True)
    rev = subprocess.run(
        ["git", "-C", str(REPO_DIR), "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    print(f"  Repo at commit {rev.stdout.strip()}")


def _verify_repo_imports() -> None:
    unet_model = REPO_DIR / "models" / "unet_model.py"
    unet_train = REPO_DIR / "wildfire_front" / "ml" / "unet_train.py"
    if not unet_model.is_file() or not unet_train.is_file():
        raise RuntimeError(f"Repo layout invalid under {REPO_DIR.resolve()}")
    model_src = unet_model.read_text(encoding="utf-8")
    train_src = unet_train.read_text(encoding="utf-8")
    if "ResidualWildfireUNetSmall" in train_src.split("def build_model", 1)[0]:
        raise RuntimeError(
            "unet_train.py still top-level-imports ResidualWildfireUNetSmall; "
            "push lazy-import fix to GitHub main."
        )
    if "class ResidualWildfireUNetSmall" not in model_src:
        raise RuntimeError(
            "models/unet_model.py missing ResidualWildfireUNetSmall; "
            "push model class to GitHub main."
        )


_clone_repo_fresh()
_verify_repo_imports()
os.chdir(REPO_DIR)
sys.path.insert(0, os.getcwd())

if args.output_dir is None:
    args.output_dir = _default_output_dir()

data_root = Path(args.data_dir)
if not args.smoke_test:
    script = Path("kaggle_job/preprocess_ndws.py")
    if not script.exists():
        raise FileNotFoundError(f"preprocess_ndws.py not found at {script}")
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
                sys.executable,
                str(script),
                "--split",
                split,
                "--patch-size",
                "64",
                "--filter-mode",
                args.filter_mode,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                tail = (result.stderr or result.stdout)[-800:]
                raise RuntimeError(f"preprocess_ndws failed for {split}:\n{tail}")
            count = len(list(out_split.glob("*.npz")))
            print(f"  {split}: {count} patches")
    else:
        print(f"Data already preprocessed ({total} patches)")

from wildfire_front.ml.unet_train import config_from_namespace, run_training  # noqa: E402

config = config_from_namespace(args)
summary = run_training(config)
print("\n=== U-NET v21 COMPLETED ===")
print(f"  Model IoU (full): {summary['test_iou']:.4f}")
print(f"  Copy baseline IoU: {summary['copy_baseline_iou']:.4f}")
print(f"  delta vs copy (full): {summary['improvement_vs_copy_iou']:+.4f}")
print(
    f"  delta vs dilated copy (changed): {summary['improvement_vs_copy_iou_changed']:+.4f}  "
    f"(legacy naive: {summary['legacy_improvement_vs_naive_copy_iou_changed']:+.4f})"
)
