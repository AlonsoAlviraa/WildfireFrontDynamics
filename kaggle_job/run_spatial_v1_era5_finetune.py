#!/usr/bin/env python3
"""Kaggle: spatial ERA5 LOFO finetune from era5_long fold weights — goal +0.05 vs W0.

Init: per-fold weights from E_spatial_v1_era5_long (mean 0.576).
Data: alonsoalviraaaa/wfd-lofo-spatial-era5-v1
Lower LR, more patience. Target mean ≥ 0.6076 (W0+0.05).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

REPO_URL = "https://github.com/AlonsoAlviraa/WildfireFrontDynamics.git"
REPO_DIR = Path("/tmp/WildfireFrontDynamics")
CORE3 = ("CARDOSO", "LA_ESTRELLA_ACOM1", "LA_ESTRELLA_ACOM2")
EPOCHS = int(os.environ.get("WF_EPOCHS", "48"))
LR = float(os.environ.get("WF_LR", "3e-5"))
PATIENCE = int(os.environ.get("WF_PATIENCE", "20"))
BATCH = int(os.environ.get("WF_BATCH", "8"))
EMA = float(os.environ.get("WF_EMA_DECAY", "0.999"))

PRIOR_BRIDGE_MEAN = 0.5575550981918408
PRIOR_BRIDGE_MIN = 0.48528418760127023
PRIOR_LONG_MEAN = 0.5762419848161516
GOAL_DELTA = 0.05
WEATHER_LIFT_THR = 0.01

FOLD_WEIGHT_NAMES = {
    "CARDOSO": ("weights_era5_long_cardoso.pt", "weights_spatial15_era5_long.pt"),
    "LA_ESTRELLA_ACOM1": ("weights_era5_long_acom1.pt", "weights_spatial15_era5_long.pt"),
    "LA_ESTRELLA_ACOM2": ("weights_era5_long_acom2.pt", "weights_spatial15_era5_long.pt"),
}


def _working() -> Path:
    return Path("/kaggle/working") if Path("/kaggle/working").is_dir() else Path(".")


def _looks(root: Path) -> bool:
    return all((root / f / "train").is_dir() for f in CORE3)


def _maybe_zip(zpath: Path) -> Path | None:
    dest = Path("/tmp/lofo_spatial_era5_ft")
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    with zipfile.ZipFile(zpath) as zf:
        zf.extractall(dest)
    if _looks(dest):
        return dest
    for child in dest.rglob("train"):
        parent = child.parent.parent
        if _looks(parent):
            return parent
    return None


def _data_root() -> Path:
    hard = [
        Path("/kaggle/input/wfd-lofo-spatial-era5-v1"),
        Path("/kaggle/input/datasets/alonsoalviraaaa/wfd-lofo-spatial-era5-v1"),
    ]
    for c in hard:
        if c.is_dir() and _looks(c):
            return c
    if Path("/kaggle/input").is_dir():
        for d in Path("/kaggle/input").rglob("*"):
            if d.is_dir() and _looks(d):
                return d
        for z in Path("/kaggle/input").rglob("*.zip"):
            got = _maybe_zip(z)
            if got is not None:
                return got
    raise FileNotFoundError("spatial ERA5 pack missing")


def _find_weight(names: tuple[str, ...]) -> str:
    for name in names:
        for p in Path("/kaggle/input").rglob(name):
            if p.is_file():
                return str(p)
    return ""


def _fold_hparams(held: str) -> tuple[float, float]:
    if held == "LA_ESTRELLA_ACOM2":
        return 10.0, 8.0
    if held == "LA_ESTRELLA_ACOM1":
        return 7.0, 6.5
    return 6.5, 6.0


def main() -> int:
    print("=" * 70, flush=True)
    print("SPATIAL ERA5 FINETUNE from long fold weights — goal +0.05 vs W0", flush=True)
    print(f"epochs={EPOCHS} lr={LR} patience={PATIENCE}", flush=True)
    print("=" * 70, flush=True)

    data_root = _data_root()
    print("data", data_root, flush=True)

    if REPO_DIR.exists():
        shutil.rmtree(REPO_DIR)
    subprocess.run(["git", "clone", "--depth", "1", REPO_URL, str(REPO_DIR)], check=True)
    os.chdir(REPO_DIR)
    sys.path.insert(0, str(REPO_DIR.resolve()))
    from wildfire_front.ml.unet_train import UNetTrainConfig, run_training

    out_root = _working()
    results = []
    for held in CORE3:
        init = _find_weight(FOLD_WEIGHT_NAMES[held])
        print(f"held={held} init={init or '(NONE)'}", flush=True)
        if not init:
            print("[error] missing fold init", flush=True)
            return 2
        out = out_root / held
        out.mkdir(parents=True, exist_ok=True)
        ch, pos = _fold_hparams(held)
        cfg = UNetTrainConfig(
            epochs=EPOCHS,
            batch_size=BATCH,
            lr=LR,
            loss="composite",
            pos_weight=pos,
            model="small",
            architecture="residual",
            target_mode="delta",
            change_loss_weight=ch,
            weighted_sampler=True,
            patience=PATIENCE,
            ema_decay=EMA,
            data_dir=str(data_root / held),
            output_dir=str(out),
            version_tag=f"spatial_era5_ft_{held}",
            early_stop_metric="model_iou",
            init_weights_path=init,
        )
        print(f"=== held={held} ch={ch} pos={pos} ===", flush=True)
        run_training(cfg)
        ts = out / "training_summary.json"
        row: dict = {
            "held": held,
            "status": "ok",
            "experiment_id": "E_spatial_v1_era5_finetune",
            "feature_schema": "spatial_v1",
            "work_class": "feature_spatial_v1+weather_era5_land+finetune_from_long",
            "init_weights_path": init,
        }
        if ts.is_file():
            prev = json.loads(ts.read_text(encoding="utf-8"))
            row["model_iou"] = prev.get("model_iou") or prev.get("test_iou")
            row["copy_baseline_iou"] = prev.get("copy_baseline_iou")
            row["improvement_vs_copy_iou"] = prev.get("improvement_vs_copy_iou")
            row["best_epoch"] = prev.get("best_epoch")
        results.append(row)
        print(json.dumps(row, indent=2), flush=True)

    ious = [float(r["model_iou"]) for r in results if r.get("model_iou") is not None]
    mean_iou = sum(ious) / len(ious) if ious else None
    min_iou = min(ious) if ious else None
    delta_w0 = (mean_iou - PRIOR_BRIDGE_MEAN) if mean_iou is not None else None
    delta_long = (mean_iou - PRIOR_LONG_MEAN) if mean_iou is not None else None
    goal = bool(delta_w0 is not None and delta_w0 >= GOAL_DELTA)

    board = {
        "schema": "wfd_kaggle_spatial_v1_era5_finetune_v1",
        "created_utc": datetime.now(UTC).isoformat(),
        "experiment_id": "E_spatial_v1_era5_finetune",
        "work_class": "feature_spatial_v1+weather_era5_land+finetune_from_long",
        "feature_schema": "spatial_v1",
        "weather_provenance": "era5_land_cds_v1",
        "architecture": "residual_small",
        "epochs": EPOCHS,
        "lr": LR,
        "patience": PATIENCE,
        "folds": results,
        "core3_mean_iou": mean_iou,
        "core3_min_iou": min_iou,
        "vs_prior_spatial_bridge": {
            "mean": PRIOR_BRIDGE_MEAN,
            "min": PRIOR_BRIDGE_MIN,
            "delta_mean": delta_w0,
            "delta_min": (min_iou - PRIOR_BRIDGE_MIN) if min_iou is not None else None,
        },
        "vs_era5_long": {
            "mean": PRIOR_LONG_MEAN,
            "delta_mean": delta_long,
        },
        "WEATHER_LIFT": bool(delta_w0 is not None and delta_w0 >= WEATHER_LIFT_THR),
        "GOAL_DELTA_MEAN": GOAL_DELTA,
        "GOAL_MET_PLUS_0_05": goal,
        "rails": {
            "field_ops_allow_ml_live_in_fusion": False,
            "ml_product_go": True,
            "lab_only": True,
            "era5_cds": True,
        },
    }
    (out_root / "spatial_v1_era5_finetune_board.json").write_text(
        json.dumps(board, indent=2), encoding="utf-8"
    )
    print(json.dumps(board, indent=2), flush=True)
    return 0 if len(results) == 3 else 1


if __name__ == "__main__":
    raise SystemExit(main())
