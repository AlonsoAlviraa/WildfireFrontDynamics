#!/usr/bin/env python3
"""Kaggle: ACOM2 regime — fixed recipe + sibling curriculum 3x (ONE lever).

Lever: data curriculum only — LOFO pack built with estrella sibling_oversample=3.0
(when held is ACOM2, ACOM1 is oversampled 3×; symmetric for ACOM1 held).

Recipe FROZEN exact_force_ema_long (no lr/batch/epoch thrash):
  epochs=48 lr=2.5e-5 patience=28 batch=8 EMA=0.999
  ACOM2 change_w/pos_w = 10/8

Init: multi_if (not specialist — lever is curriculum, not warmstart).

Baselines: specialist warmstart ACOM2=0.702085; sealed min=0.707146.

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
EPOCHS = 48
LR = 2.5e-5
PATIENCE = 28
BATCH = 8
EMA = 0.999
SEALED_MIN = 0.7071461821856562
SPECIALIST_ACOM2 = 0.7020846801343595
V3_ACOM2 = 0.6976247037297344


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
            dest = Path("/tmp/lofo_curriculum")
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
    raise FileNotFoundError("curriculum LOFO pack missing")


def _find(names: tuple[str, ...]) -> str:
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
    return 6.0, 6.0


def main() -> int:
    print("=" * 70, flush=True)
    print("ACOM2 REGIME — sibling curriculum 3x · exact_force_ema_long FIXED", flush=True)
    print(f"epochs={EPOCHS} lr={LR} patience={PATIENCE} ema={EMA}", flush=True)
    print(
        f"baselines specialist_acom2={SPECIALIST_ACOM2:.6f} sealed_min={SEALED_MIN:.6f}",
        flush=True,
    )
    print("=" * 70, flush=True)

    data = _data_root()
    init = _find(("weights_multi_if.pt", "weights_multi_if_r8.pt"))
    print("data", data, "init", init or "(none)", flush=True)
    if not init:
        print("[error] multi_if init required", flush=True)
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
            version_tag=f"acom2_curric_sib3_{held}",
            early_stop_metric="improvement_vs_copy_iou",
            init_weights_path=init,
        )
        print(f"=== held={held} lever=sibling_curriculum_3x ch={ch} pos={pos} ===", flush=True)
        run_training(cfg)
        ts = out / "training_summary.json"
        row: dict = {
            "held": held,
            "status": "ok",
            "experiment_id": "E_acom2_curriculum_sib3",
            "work_class": "regime_acom2_sibling_curriculum",
            "recipe": "exact_force_ema_long",
            "lever": "estrella_sibling_oversample_3x",
            "init_weights_path": init,
            "change_loss_weight": ch,
            "pos_weight": pos,
            "lr": LR,
            "epochs": EPOCHS,
            "patience": PATIENCE,
            "ema_decay": EMA,
            "architecture": "residual_small",
            "hparam_thrash": False,
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
        "schema": "wfd_kaggle_acom2_curriculum_sib3_v1",
        "created_utc": datetime.now(UTC).isoformat(),
        "experiment_id": "E_acom2_curriculum_sib3",
        "work_class": "regime_acom2_sibling_curriculum",
        "recipe": "exact_force_ema_long",
        "hparam_thrash": False,
        "primary_lever": "estrella_sibling_oversample_3x",
        "architecture": "residual_small",
        "folds": results,
        "core3_mean_iou": mean,
        "core3_min_iou": min_iou,
        "acom2_iou": acom2,
        "vs_baselines": {
            "specialist_warmstart_acom2": SPECIALIST_ACOM2,
            "lofo_v3_acom2": V3_ACOM2,
            "sealed_champion_min": SEALED_MIN,
            "delta_vs_specialist": (acom2 - SPECIALIST_ACOM2) if acom2 is not None else None,
            "delta_vs_v3": (acom2 - V3_ACOM2) if acom2 is not None else None,
            "delta_vs_sealed_min": (acom2 - SEALED_MIN) if acom2 is not None else None,
            "beats_specialist": bool(acom2 is not None and acom2 > SPECIALIST_ACOM2),
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
    (out_root / "acom2_curriculum_sib3_board.json").write_text(
        json.dumps(board, indent=2), encoding="utf-8"
    )
    print(json.dumps(board, indent=2), flush=True)
    return 0 if len(results) == 3 else 1


if __name__ == "__main__":
    raise SystemExit(main())
