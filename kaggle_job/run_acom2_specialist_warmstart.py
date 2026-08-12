#!/usr/bin/env python3
"""Kaggle: ACOM2 regime attack — fixed champion recipe + specialist warm-start.

ONE non-hparam lever: init from acom2_recover_v2 (or acom2_recover) when
training the LA_ESTRELLA_ACOM2 held fold. Other folds use multi_if.

Recipe: exact_force_ema_long ONLY (no lr/batch/epoch thrash).
  epochs=48 lr=2.5e-5 patience=28 batch=8 EMA=0.999
  ACOM2 change_w/pos_w = 10/8 (champion fixed)

Data: sealed LOFO core-3 pack (wfd-lofo-v2-e3a or lofo_v3).
Comparability: ACOM2 IoU vs v3 min 0.6976 and sealed champ min 0.7071.

Rails: residual-small · fusion OFF · IoU≠ROS · no Tobarra KEEP · no larger U-Net.
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
# exact_force_ema_long — FROZEN
EPOCHS = 48
LR = 2.5e-5
PATIENCE = 28
BATCH = 8
EMA = 0.999
SEALED_MIN = 0.7071461821856562
V3_ACOM2 = 0.6976247037297344
CHAMP_MEAN = 0.7877704721329809


def _working() -> Path:
    return Path("/kaggle/working") if Path("/kaggle/working").is_dir() else Path(".")


def _looks(root: Path) -> bool:
    return all((root / f / "train").is_dir() for f in CORE3)


def _data_root() -> Path:
    if Path("/kaggle/input").is_dir():
        for d in Path("/kaggle/input").rglob("*"):
            if d.is_dir() and _looks(d):
                return d
        for z in Path("/kaggle/input").rglob("*.zip"):
            dest = Path("/tmp/lofo_pack")
            if dest.exists():
                shutil.rmtree(dest)
            dest.mkdir(parents=True)
            with zipfile.ZipFile(z) as zf:
                zf.extractall(dest)
            if _looks(dest):
                return dest
            for child in dest.rglob("train"):
                parent = child.parent.parent
                if _looks(parent):
                    return parent
    raise FileNotFoundError("LOFO core-3 pack missing")


def _find(names: tuple[str, ...]) -> str:
    for name in names:
        for p in Path("/kaggle/input").rglob(name):
            if p.is_file():
                return str(p)
        for p in Path("/kaggle/working").rglob(name) if Path("/kaggle/working").is_dir() else []:
            if p.is_file():
                return str(p)
    return ""


def _fold_hparams(held: str) -> tuple[float, float]:
    if held == "LA_ESTRELLA_ACOM2":
        return 10.0, 8.0
    if held == "LA_ESTRELLA_ACOM1":
        return 7.0, 6.5
    return 6.0, 6.0


def main() -> int:
    print("=" * 70, flush=True)
    print("ACOM2 REGIME — specialist warm-start · exact_force_ema_long FIXED", flush=True)
    print(f"epochs={EPOCHS} lr={LR} patience={PATIENCE} ema={EMA}", flush=True)
    print(f"baselines sealed_min={SEALED_MIN:.6f} v3_acom2={V3_ACOM2:.6f}", flush=True)
    print("=" * 70, flush=True)

    data = _data_root()
    multi_if = _find(("weights_multi_if.pt", "weights_multi_if_r8.pt"))
    acom2_init = _find(
        (
            "acom2_recover_v2.pt",
            "acom2_recover.pt",
            "weights_acom2_specialist.pt",
        )
    )
    print("data", data, flush=True)
    print("multi_if", multi_if or "(none)", "acom2_specialist", acom2_init or "(none)", flush=True)
    if not multi_if and not acom2_init:
        print("[error] need multi_if or acom2 specialist weights", flush=True)
        return 2

    if REPO_DIR.exists():
        shutil.rmtree(REPO_DIR)
    subprocess.run(["git", "clone", "--depth", "1", REPO_URL, str(REPO_DIR)], check=True)
    os.chdir(REPO_DIR)
    sys.path.insert(0, str(REPO_DIR.resolve()))
    from wildfire_front.ml.unet_train import UNetTrainConfig, run_training

    out_root = _working()
    results = []
    for held in CORE3:
        out = out_root / held
        out.mkdir(parents=True, exist_ok=True)
        ch, pos = _fold_hparams(held)
        # ONE lever: ACOM2 fold uses specialist warm-start when available
        if held == "LA_ESTRELLA_ACOM2" and acom2_init:
            init = acom2_init
            lever = "acom2_specialist_warmstart"
        else:
            init = multi_if or acom2_init
            lever = "multi_if_init"
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
            data_dir=str(data / held),
            output_dir=str(out),
            version_tag=f"acom2_regime_{held}",
            early_stop_metric="improvement_vs_copy_iou",
            init_weights_path=init,
        )
        print(f"=== held={held} lever={lever} ch={ch} pos={pos} ===", flush=True)
        run_training(cfg)
        ts = out / "training_summary.json"
        row: dict = {
            "held": held,
            "status": "ok",
            "experiment_id": "E_acom2_specialist_warmstart",
            "work_class": "regime_acom2_specialist_warmstart",
            "recipe": "exact_force_ema_long",
            "lever": lever,
            "init_weights_path": init,
            "change_loss_weight": ch,
            "pos_weight": pos,
            "lr": LR,
            "epochs": EPOCHS,
            "patience": PATIENCE,
            "ema_decay": EMA,
            "architecture": "residual_small",
        }
        if ts.is_file():
            prev = json.loads(ts.read_text(encoding="utf-8"))
            row["model_iou"] = prev.get("model_iou") or prev.get("test_iou")
            row["copy_baseline_iou"] = prev.get("copy_baseline_iou")
            row["improvement_vs_copy_iou"] = prev.get("improvement_vs_copy_iou")
            row["best_epoch"] = prev.get("best_epoch")
        results.append(row)
        print(json.dumps(row, indent=2), flush=True)

    ious = {r["held"]: float(r["model_iou"]) for r in results if r.get("model_iou") is not None}
    acom2 = ious.get("LA_ESTRELLA_ACOM2")
    mean = sum(ious.values()) / len(ious) if ious else None
    min_iou = min(ious.values()) if ious else None
    board = {
        "schema": "wfd_kaggle_acom2_specialist_warmstart_v1",
        "created_utc": datetime.now(UTC).isoformat(),
        "experiment_id": "E_acom2_specialist_warmstart",
        "work_class": "regime_acom2_specialist_warmstart",
        "recipe": "exact_force_ema_long",
        "hparam_thrash": False,
        "primary_lever": "acom2_specialist_warmstart",
        "architecture": "residual_small",
        "folds": results,
        "core3_mean_iou": mean,
        "core3_min_iou": min_iou,
        "acom2_iou": acom2,
        "vs_baselines": {
            "sealed_champion_min": SEALED_MIN,
            "lofo_v3_acom2": V3_ACOM2,
            "delta_acom2_vs_v3": (acom2 - V3_ACOM2) if acom2 is not None else None,
            "delta_acom2_vs_sealed_min": (acom2 - SEALED_MIN) if acom2 is not None else None,
            "beats_v3_acom2": bool(acom2 is not None and acom2 > V3_ACOM2),
            "beats_sealed_min": bool(acom2 is not None and acom2 > SEALED_MIN),
        },
        "rails": {
            "field_ops_allow_ml_live_in_fusion": False,
            "ml_product_go": True,
            "iou_is_not_ros": True,
            "tobarra_keep_reopen": False,
            "larger_unet_default": False,
            "lab_only": True,
        },
    }
    (out_root / "acom2_specialist_warmstart_board.json").write_text(
        json.dumps(board, indent=2), encoding="utf-8"
    )
    print(json.dumps(board, indent=2), flush=True)
    return 0 if len(results) == 3 else 1


if __name__ == "__main__":
    raise SystemExit(main())
