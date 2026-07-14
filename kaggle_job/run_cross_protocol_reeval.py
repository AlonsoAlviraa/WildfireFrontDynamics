#!/usr/bin/env python3
"""Cross-protocol re-eval: v14/v19/v20 on identical v19 test split (Kaggle-safe)."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_URL = "https://github.com/AlonsoAlviraa/WildfireFrontDynamics.git"
REPO_DIR = Path("WildfireFrontDynamics")

parser = argparse.ArgumentParser(description="Cross-protocol NDWS checkpoint evaluation")
parser.add_argument("--data-dir", type=str, default="/tmp/ndws_npz")
parser.add_argument("--output-dir", type=str, default=None)
parser.add_argument("--filter-mode", choices=["both_fire", "any_fire", "changed", "none"],
                    default="any_fire")
parser.add_argument("--clm-data-dir", type=str,
                    default="/kaggle/input/datasets/alonsoalviraaaa/clm-wildfire-patches")
parser.add_argument("--v14-weights", type=str, default=None)
parser.add_argument("--v19-weights", type=str, default=None)
parser.add_argument("--v20-weights", type=str, default=None)
parser.add_argument("--smoke-test", action="store_true", default=False)
args, _ = parser.parse_known_args()


def _default_output_dir() -> str:
    if os.path.isdir("/kaggle/working"):
        return "/kaggle/working"
    return "."


def _install_pytorch_p100_compat() -> None:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0 or "P100" not in result.stdout:
            return
        print("[gpu] P100 detected — installing PyTorch 2.1.2+cu118")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q",
             "torch==2.1.2", "torchvision==0.16.2",
             "--index-url", "https://download.pytorch.org/whl/cu118"],
            check=True,
        )
    except Exception as exc:
        print(f"[gpu] P100 compat check skipped: {exc}")


def _clone_repo_fresh() -> None:
    if REPO_DIR.exists():
        shutil.rmtree(REPO_DIR)
    print("Cloning repository...")
    subprocess.run(["git", "clone", "--depth", "1", REPO_URL], check=True)


def _resolve_weights(version: str, explicit: str | None) -> Path | None:
    if explicit and Path(explicit).is_file():
        return Path(explicit)
    search_roots = [
        Path("/kaggle/input/wildfire-checkpoint-weights"),
        Path("/kaggle/input"),
        Path("/kaggle/working"),
    ]
    for root in search_roots:
        if not root.exists():
            continue
        direct = root / version / "weights_pretrained_best.pt"
        if direct.is_file():
            return direct
        matches = sorted(root.glob(f"**/{version}/weights_pretrained_best.pt"))
        if matches:
            return matches[0]
    return None


_install_pytorch_p100_compat()
_clone_repo_fresh()
os.chdir(REPO_DIR)
sys.path.insert(0, os.getcwd())

if args.output_dir is None:
    args.output_dir = _default_output_dir()

data_root = Path(args.data_dir)
if not args.smoke_test:
    script = Path("kaggle_job/preprocess_ndws.py")
    for split in ("train", "val", "test"):
        out_split = data_root / split
        existing = len(list(out_split.glob("*.npz"))) if out_split.exists() else 0
        if existing > 10:
            print(f"  {split}: {existing} patches exist, skipping preprocess")
            continue
        cmd = [
            sys.executable, str(script),
            "--split", split,
            "--patch-size", "64",
            "--filter-mode", args.filter_mode,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"preprocess failed for {split}:\n{(result.stderr or result.stdout)[-800:]}")
        print(f"  {split}: {len(list(out_split.glob('*.npz')))} patches")

from wildfire_front.ml.cross_protocol_eval import run_cross_protocol_eval  # noqa: E402
from wildfire_front.ml.unet_train import merge_clm_patches  # noqa: E402

if args.clm_data_dir and Path(args.clm_data_dir).exists():
    merge_clm_patches(data_root, Path(args.clm_data_dir))

checkpoints: dict[str, dict] = {}
weight_args = {"v14": args.v14_weights, "v19": args.v19_weights, "v20": args.v20_weights}
for name, arch, mode in [
    ("v14", "standard", "absolute"),
    ("v19", "standard", "changed_weighted"),
    ("v20", "residual", "changed_weighted"),
]:
    weights = _resolve_weights(name, weight_args[name])
    if weights is None:
        print(f"[skip] {name}: no weights found")
        continue
    checkpoints[name] = {"weights": weights, "architecture": arch, "target_mode": mode}

if not checkpoints:
    raise RuntimeError("No checkpoint weights available — attach wildfire-checkpoint-weights dataset")

out = Path(args.output_dir) / "cross_protocol_report.json"
report = run_cross_protocol_eval(checkpoints, data_root, out)

print("\n=== CROSS-PROTOCOL RE-EVAL ===")
for name, row in report["results"].items():
    print(
        f"{name}: IoU={row['test_iou']:.4f}  copy={row['copy_baseline_iou']:.4f}  "
        f"dilated={row['dilated_copy_baseline_iou']:.4f}  "
        f"delta_full={row['improvement_vs_copy_iou']:+.4f}  "
        f"delta_changed={row['improvement_vs_copy_iou_changed']:+.4f}  "
        f"legacy={row['legacy_improvement_vs_naive_copy_iou_changed']:+.4f}"
    )
print(f"Report: {out}")