"""Shared helpers for Kaggle training scripts."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def default_output_dir() -> str:
    """Write artifacts to /kaggle/working on Kaggle, cwd locally."""
    if os.path.isdir("/kaggle/working"):
        return "/kaggle/working"
    return "."


def install_pytorch_p100_compat() -> None:
    """Downgrade PyTorch on P100 (sm_60) before importing torch."""
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
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "-q",
                "torch==2.1.2",
                "torchvision==0.16.2",
            ],
            capture_output=True,
            text=True,
            timeout=600,
        )
        if pip_result.returncode == 0:
            print("  PyTorch 2.1.2 installed.")
        else:
            tail = (pip_result.stderr or pip_result.stdout or "")[-400:]
            print(f"  [WARN] PyTorch 2.1.2 install failed (continuing with preinstalled): {tail}")
    except Exception as exc:
        print(f"  [WARN] P100 PyTorch fix failed (continuing): {exc}")


def run_preprocess_ndws(
    data_root: Path,
    *,
    patch_size: int = 64,
    filter_mode: str = "any_fire",
    min_total: int = 100,
    log=print,
) -> int:
    """Run preprocess_ndws.py for train/val/test if data is missing."""
    data_root = Path(data_root)
    total_existing = sum(
        len(list((data_root / split).glob("*.npz")))
        for split in ("train", "val", "test")
        if (data_root / split).exists()
    )
    if total_existing >= min_total:
        log(f"  Data already preprocessed ({total_existing} patches)")
        return total_existing

    script = Path("kaggle_job/preprocess_ndws.py")
    if not script.exists():
        script = Path(__file__).resolve().parent / "preprocess_ndws.py"

    log("\n=== PREPROCESSING via preprocess_ndws.py ===")
    for split in ("train", "val", "test"):
        out_split = data_root / split
        existing = len(list(out_split.glob("*.npz"))) if out_split.exists() else 0
        if existing > 10:
            log(f"  {split}: {existing} patches exist, skipping")
            continue
        log(f"  Preprocessing {split}...")
        cmd = [
            sys.executable,
            str(script),
            "--split",
            split,
            "--patch-size",
            str(patch_size),
            "--filter-mode",
            filter_mode,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            tail = (result.stderr or result.stdout)[-800:]
            raise RuntimeError(f"preprocess_ndws.py failed for {split}:\n{tail}")
        count = len(list(out_split.glob("*.npz")))
        log(f"  {split}: {count} patches")

    total = sum(
        len(list((data_root / split).glob("*.npz")))
        for split in ("train", "val", "test")
        if (data_root / split).exists()
    )
    if total < min_total:
        raise RuntimeError(
            f"Insufficient data after preprocessing: {total} patches "
            f"(expected >= {min_total})"
        )
    return total


def validate_dataset_sizes(train_n: int, val_n: int, test_n: int) -> None:
    """Fail fast when preprocessing produced empty splits."""
    if train_n == 0 or val_n == 0 or test_n == 0:
        raise RuntimeError(
            f"Empty dataset split(s): train={train_n} val={val_n} test={test_n}. "
            "Preprocessing failed — aborting before training."
        )