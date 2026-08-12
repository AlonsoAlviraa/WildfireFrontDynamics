#!/usr/bin/env python3
"""Kaggle: ACOM2 regime — champion-fold init (ONE lever) + ACOM1 collateral.

Lever: when held=LA_ESTRELLA_ACOM2, warm-start from sealed champion
exact_force_ema_long ACOM2 fold weights (not recover specialist, not curriculum).

Other folds: multi_if init (same as baseline boards).

Recipe FROZEN exact_force_ema_long:
  epochs=48 lr=2.5e-5 patience=28 batch=8 EMA=0.999
  ACOM2 ch/pos = 10/8

Report ACOM2 vs 0.702 specialist / 0.707 sealed min AND ACOM1 collateral.

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
CURRIC_ACOM2 = 0.7043405673740115
CURRIC_ACOM1 = 0.6956353833520992


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
    raise FileNotFoundError("LOFO pack missing")


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
    print("ACOM2 REGIME — champion fold init · exact_force_ema_long FIXED", flush=True)
    print(f"epochs={EPOCHS} lr={LR} patience={PATIENCE} ema={EMA}", flush=True)
    print(
        f"baselines specialist={SPECIALIST_ACOM2:.6f} curric={CURRIC_ACOM2:.6f} sealed_min={SEALED_MIN:.6f}",
        flush=True,
    )
    print("=" * 70, flush=True)

    data = _data_root()
    multi_if = _find(("weights_multi_if.pt", "weights_multi_if_r8.pt"))
    champ_acom2 = _find(
        (
            "weights_champion_acom2_exact_force_ema_long.pt",
            "champion_acom2_exact_force_ema_long.pt",
            "weights_pretrained_best.pt",  # may hit wrong fold — prefer named
        )
    )
    # Prefer explicitly named champion file
    for p in Path("/kaggle/input").rglob("weights_champion_acom2_exact_force_ema_long.pt"):
        champ_acom2 = str(p)
        break
    print("data", data, flush=True)
    print("multi_if", multi_if or "(none)", "champ_acom2", champ_acom2 or "(none)", flush=True)
    if not multi_if:
        print("[error] multi_if required for non-ACOM2 folds", flush=True)
        return 2
    if not champ_acom2:
        print("[error] champion ACOM2 weights missing", flush=True)
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
        if held == "LA_ESTRELLA_ACOM2":
            init = champ_acom2
            lever = "champion_fold_init_exact_force_ema_long"
        else:
            init = multi_if
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
            version_tag=f"acom2_champ_init_{held}",
            early_stop_metric="improvement_vs_copy_iou",
            init_weights_path=init,
        )
        print(f"=== held={held} lever={lever} ===", flush=True)
        run_training(cfg)
        ts = out / "training_summary.json"
        row: dict = {
            "held": held,
            "status": "ok",
            "experiment_id": "E_acom2_champion_fold_init",
            "work_class": "regime_acom2_champion_fold_init",
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
    acom1 = ious.get("LA_ESTRELLA_ACOM1")
    mean = sum(ious.values()) / len(ious) if ious else None
    min_iou = min(ious.values()) if ious else None
    board = {
        "schema": "wfd_kaggle_acom2_champion_fold_init_v1",
        "created_utc": datetime.now(UTC).isoformat(),
        "experiment_id": "E_acom2_champion_fold_init",
        "work_class": "regime_acom2_champion_fold_init",
        "recipe": "exact_force_ema_long",
        "hparam_thrash": False,
        "primary_lever": "champion_fold_init_exact_force_ema_long",
        "architecture": "residual_small",
        "folds": results,
        "core3_mean_iou": mean,
        "core3_min_iou": min_iou,
        "acom2_iou": acom2,
        "acom1_iou": acom1,
        "acom1_collateral_vs_curric": ((acom1 - CURRIC_ACOM1) if acom1 is not None else None),
        "vs_baselines": {
            "specialist_warmstart_acom2": SPECIALIST_ACOM2,
            "curriculum_sib3_acom2": CURRIC_ACOM2,
            "sealed_champion_min": SEALED_MIN,
            "delta_vs_specialist": (acom2 - SPECIALIST_ACOM2) if acom2 is not None else None,
            "delta_vs_curric": (acom2 - CURRIC_ACOM2) if acom2 is not None else None,
            "delta_vs_sealed_min": (acom2 - SEALED_MIN) if acom2 is not None else None,
            "beats_specialist": bool(acom2 is not None and acom2 > SPECIALIST_ACOM2),
            "beats_curric": bool(acom2 is not None and acom2 > CURRIC_ACOM2),
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
    (out_root / "acom2_champion_fold_init_board.json").write_text(
        json.dumps(board, indent=2), encoding="utf-8"
    )
    print(json.dumps(board, indent=2), flush=True)
    return 0 if len(results) == 3 else 1


if __name__ == "__main__":
    raise SystemExit(main())
