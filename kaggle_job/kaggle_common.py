"""Shared helpers for Kaggle training scripts."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_URL = "https://github.com/AlonsoAlviraa/WildfireFrontDynamics.git"
REPO_CLONE_DIR = Path("/tmp/WildfireFrontDynamics")


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
            "--output-root",
            str(data_root),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            tail = (result.stderr or result.stdout)[-800:]
            raise RuntimeError(f"preprocess_ndws.py failed for {split}:\n{tail}")
        count = len(list(out_split.glob("*.npz")))
        log(f"  {split}: {count} patches")
        if count == 0 and result.stdout:
            log(f"  [preprocess stdout tail]\n{(result.stdout or '')[-600:]}")

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


def clone_repo_fresh(
    url: str = REPO_URL,
    dest: Path | str = REPO_CLONE_DIR,
) -> Path:
    """Clone repo under /tmp so /kaggle/working stays artifact-only."""
    dest = Path(dest)
    if dest.exists():
        shutil.rmtree(dest)
    print("Cloning repository...")
    subprocess.run(["git", "clone", "--depth", "1", url, str(dest)], check=True)
    rev = subprocess.run(
        ["git", "-C", str(dest), "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    print(f"  Repo at commit {rev.stdout.strip()}")
    return dest


def enter_repo(repo_dir: Path | str) -> None:
    """Add repo to sys.path and chdir (never use /kaggle/working for clone)."""
    repo_dir = Path(repo_dir)
    os.chdir(repo_dir)
    root = str(repo_dir.resolve())
    if root not in sys.path:
        sys.path.insert(0, root)


def verify_residual_imports(repo_dir: Path | str) -> None:
    repo_dir = Path(repo_dir)
    unet_model = repo_dir / "models" / "unet_model.py"
    unet_train = repo_dir / "wildfire_front" / "ml" / "unet_train.py"
    if not unet_model.is_file() or not unet_train.is_file():
        raise RuntimeError(f"Repo layout invalid under {repo_dir}")
    model_src = unet_model.read_text(encoding="utf-8")
    train_src = unet_train.read_text(encoding="utf-8")
    if "ResidualWildfireUNetSmall" in train_src.split("def build_model", 1)[0]:
        raise RuntimeError("unet_train.py top-level-imports ResidualWildfireUNetSmall")
    if "class ResidualWildfireUNetSmall" not in model_src:
        raise RuntimeError("models/unet_model.py missing ResidualWildfireUNetSmall")


def detect_clm_dataset() -> str | None:
    import zipfile

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


def validate_dataset_sizes(train_n: int, val_n: int, test_n: int) -> None:
    """Fail fast when preprocessing produced empty splits."""
    if train_n == 0 or val_n == 0 or test_n == 0:
        raise RuntimeError(
            f"Empty dataset split(s): train={train_n} val={val_n} test={test_n}. "
            "Preprocessing failed — aborting before training."
        )