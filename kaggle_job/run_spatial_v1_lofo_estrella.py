#!/usr/bin/env python3
"""Kaggle: E2-P2 spatial_v1 + estrella_floor_v1 LOFO residual-small train.

Data: alonsoalviraaaa/wfd-lofo-spatial-estrella-v1 (core-3 LOFO mix).
Schema: spatial_v1 (14 feats + prev_fire); DEM-backed terrain has real variance.
Weather rasters GAP → scalar per fire (honest non-spatial); never-channels for
wind/precip/veg allowed with stamp (not sold as full weather spatial).

Recipe (higher-EV than blind thrash; still honest):
  residual + small · no larger U-Net · no multi_if/legacy17 init (14≠17 ch)
  Same estrella mix; fold-specific change/pos weights for weak ACOM folds.

Rails: lab only · fusion OFF · IoU≠ROS · no Tobarra KEEP · residual small.

Target stamp (comparability, not auto-KEEP):
  vs sealed recover_v2 force_train multi_if mean 0.7857 / min 0.7071
  E2 L1 mean +0.010 on sealed baseline 0.7581 → 0.7681; L2 min≥0.700

Local operator (Windows short path + score)::
  python scripts/run_kaggle_spatial_v1_estrella.py
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
# force_train-style + EMA-long (matches sealed champion recipe direction;
# spatial is from-scratch 14ch — no multi_if init)
EPOCHS = int(os.environ.get("WF_EPOCHS", "48"))
LR = float(os.environ.get("WF_LR", "2.5e-5"))
PATIENCE = int(os.environ.get("WF_PATIENCE", "28"))
BATCH = int(os.environ.get("WF_BATCH", "8"))
EMA_DECAY = float(os.environ.get("WF_EMA_DECAY", "0.999"))
# Current sealed champion (exact_force_ema_long) — recipe bar for comparison
SEALED_T1_MEAN = 0.7877704721329809
SEALED_T1_MIN = 0.7071461821856562
# Prior historic force_train_multi_if (immutable reference)
PRIOR_FORCE_TRAIN_MEAN = 0.7857091284390876
PRIOR_FORCE_TRAIN_MIN = 0.7070728142438604
SEALED_BASELINE_MEAN = 0.7580534465179306
E2_TARGET_MEAN = SEALED_BASELINE_MEAN + 0.010


def _working() -> Path:
    return Path("/kaggle/working") if Path("/kaggle/working").is_dir() else Path(".")


def _install_p100() -> None:
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode != 0 or "P100" not in (r.stdout or ""):
            return
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "-q",
                "torch==2.1.2",
                "torchvision==0.16.2",
            ],
            check=False,
            timeout=600,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] p100: {exc}", flush=True)


def _looks_like_lofo(root: Path) -> bool:
    return any((root / f / "train").is_dir() for f in CORE3)


def _extract_zip(z: Path) -> Path | None:
    dest = Path("/tmp/lofo_spatial_v1")
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    print(f"[data] extracting {z} → {dest}", flush=True)
    with zipfile.ZipFile(z) as zf:
        zf.extractall(dest)
    # zip may contain folds at root OR one nested folder
    if _looks_like_lofo(dest):
        return dest
    for child in dest.iterdir():
        if child.is_dir() and _looks_like_lofo(child):
            return child
    # one more level (Compress-Archive / nested)
    for child in dest.rglob("train"):
        parent = child.parent  # .../CARDOSO/train
        fold_root = parent.parent  # .../CARDOSO's parent
        if _looks_like_lofo(fold_root):
            return fold_root
    return None


def _root() -> Path:
    input_root = Path("/kaggle/input")
    print(f"[data] scanning {input_root} for LOFO folds / zips...", flush=True)

    # Known mount layouts (Kaggle unpacks zip → nested lofo_mix_... folder)
    hard = [
        Path("/kaggle/input/wfd-lofo-spatial-estrella-v1"),
        Path("/kaggle/input/wfd-lofo-spatial-estrella-v1/lofo_mix_spatial_estrella_v1"),
        Path("/kaggle/input/datasets/alonsoalviraaaa/wfd-lofo-spatial-estrella-v1"),
        Path(
            "/kaggle/input/datasets/alonsoalviraaaa/wfd-lofo-spatial-estrella-v1"
            "/lofo_mix_spatial_estrella_v1"
        ),
    ]
    for c in hard:
        if c.is_dir() and _looks_like_lofo(c):
            print(f"[data] using fold root {c}", flush=True)
            return c

    # Bounded BFS over directories only (depth ≤ 5) — avoid walking every npz
    if input_root.is_dir():
        from collections import deque

        q: deque[tuple[Path, int]] = deque([(input_root, 0)])
        while q:
            cur, depth = q.popleft()
            if depth > 5:
                continue
            try:
                children = list(cur.iterdir())
            except OSError:
                continue
            if _looks_like_lofo(cur):
                print(f"[data] using fold root {cur}", flush=True)
                return cur
            for z in children:
                if z.is_file() and z.suffix.lower() == ".zip":
                    got = _extract_zip(z)
                    if got is not None:
                        print(f"[data] using extracted root {got}", flush=True)
                        return got
            if depth < 5:
                for ch in children:
                    if ch.is_dir():
                        q.append((ch, depth + 1))

        # Debug top levels
        for p in sorted(input_root.iterdir()):
            print(f"  top: {p}", flush=True)
            if p.is_dir():
                for c in sorted(p.iterdir())[:30]:
                    tag = "/" if c.is_dir() else ""
                    print(f"    {c.name}{tag}", flush=True)

    raise FileNotFoundError(
        "spatial estrella LOFO missing "
        "(expect folds under /kaggle/input/**/CARDOSO/train or a pack zip)"
    )


def _fold_hparams(held: str) -> tuple[float, float]:
    if held == "LA_ESTRELLA_ACOM2":
        return 10.0, 8.0
    if held == "LA_ESTRELLA_ACOM1":
        return 7.0, 6.5
    return 6.5, 6.0


def main() -> int:
    print("=" * 70, flush=True)
    print("SPATIAL_V1 + ESTRELLA + DEM-LAPSE LOFO residual-small (E2-P2)", flush=True)
    print(
        f"epochs={EPOCHS} lr={LR} patience={PATIENCE} batch={BATCH} ema={EMA_DECAY}",
        flush=True,
    )
    print(
        f"historic bar force_train mean={SEALED_T1_MEAN:.6f} min={SEALED_T1_MIN:.6f}",
        flush=True,
    )
    print("=" * 70, flush=True)
    _install_p100()

    data_root = _root()
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
        out = out_root / held
        out.mkdir(parents=True, exist_ok=True)
        change_w, pos_w = _fold_hparams(held)
        # No legacy17 init — channel mismatch (14 vs 17)
        cfg = UNetTrainConfig(
            epochs=EPOCHS,
            batch_size=BATCH,
            lr=LR,
            loss="composite",
            pos_weight=pos_w,
            model="small",
            architecture="residual",
            target_mode="delta",
            change_loss_weight=change_w,
            weighted_sampler=True,
            patience=PATIENCE,
            ema_decay=EMA_DECAY,
            data_dir=str(data_root / held),
            output_dir=str(out),
            version_tag=f"spatial_v1_dem_lapse_{held}",
            early_stop_metric="improvement_vs_copy_iou",
            init_weights_path=None,
        )
        print(
            f"=== spatial_v1 dem_lapse held={held} change_w={change_w} pos_w={pos_w} ===",
            flush=True,
        )
        run_training(cfg)
        ts = out / "training_summary.json"
        row = {
            "held": held,
            "status": "ok",
            "experiment_id": "E2_P2_spatial_v1_weather_fuel_estrella",
            "feature_schema": "spatial_v1",
            "schema_path_id": "E2-P2",
            "work_class": "feature_spatial_v1+dem_lapse_weather+fuel_worldcover+data_mix_estrella_floor_v1",
            "mix_policy": "estrella_floor_v1",
            "weather_provenance": "dem_lapse_v1",
            "fuel_provenance": "worldcover_multi_fire",
            "change_loss_weight": change_w,
            "pos_weight": pos_w,
            "lr": LR,
            "epochs": EPOCHS,
            "patience": PATIENCE,
            "ema_decay": EMA_DECAY,
            "init_weights_path": None,
            "init_weights_channel_match": False,
        }
        if ts.is_file():
            prev = json.loads(ts.read_text(encoding="utf-8"))
            if isinstance(prev, dict):
                prev.update(
                    {
                        "schema_path_id": "E2-P2",
                        "feature_schema": "spatial_v1",
                        "work_class": (
                            "feature_spatial_v1+dem_lapse_weather+fuel_worldcover"
                            "+data_mix_estrella_floor_v1"
                        ),
                        "mix_policy": "estrella_floor_v1",
                        "weather_provenance": "dem_lapse_v1",
                        "fuel_provenance": "worldcover_multi_fire",
                        "held_out": held,
                        "experiment_id": "E2_P2_spatial_v1_weather_fuel_estrella",
                        "change_loss_weight": change_w,
                        "pos_weight": pos_w,
                        "never_allowlist_honesty": (
                            "weather_dem_lapse_v1_not_reanalysis;"
                            "fuel_worldcover_multi_fire;"
                            "terrain_dem_glo30_spatial_real"
                        ),
                    }
                )
                ts.write_text(json.dumps(prev, indent=2), encoding="utf-8")
                row["model_iou"] = prev.get("model_iou") or prev.get("test_iou")
                row["copy_baseline_iou"] = prev.get("copy_baseline_iou")
                row["improvement_vs_copy_iou"] = prev.get("improvement_vs_copy_iou")
                em = out / "evaluation_metrics.json"
                if not em.is_file():
                    em.write_text(json.dumps(prev, indent=2), encoding="utf-8")
        results.append(row)
        print(json.dumps(row, indent=2), flush=True)

    ious = [float(r["model_iou"]) for r in results if r.get("model_iou") is not None]
    mean_iou = (sum(ious) / len(ious)) if ious else None
    min_iou = min(ious) if ious else None
    beats_historic = bool(
        mean_iou is not None
        and min_iou is not None
        and mean_iou > SEALED_T1_MEAN
        and min_iou > SEALED_T1_MIN
    )
    board = {
        "schema": "wfd_kaggle_spatial_v1_estrella_lofo_v1",
        "created_utc": datetime.now(UTC).isoformat(),
        "experiment_id": "E2_P2_spatial_v1_weather_fuel_estrella",
        "feature_schema": "spatial_v1",
        "schema_path_id": "E2-P2",
        "work_class": (
            "feature_spatial_v1+dem_lapse_weather+fuel_worldcover+data_mix_estrella_floor_v1"
        ),
        "mix_policy": "estrella_floor_v1",
        "weather_provenance": "dem_lapse_v1",
        "fuel_provenance": "worldcover_multi_fire",
        "architecture": "residual_small",
        "epochs": EPOCHS,
        "lr": LR,
        "patience": PATIENCE,
        "ema_decay": EMA_DECAY,
        "init_weights_path": None,
        "folds": results,
        "core3_mean_iou": mean_iou,
        "core3_min_iou": min_iou,
        "beats_historic_force_train": beats_historic,
        "comparability": {
            "sealed_t1_recipe_mean": SEALED_T1_MEAN,
            "sealed_t1_recipe_min": SEALED_T1_MIN,
            "sealed_t1_config": "exact_force_ema_long",
            "prior_force_train_multi_if_mean": PRIOR_FORCE_TRAIN_MEAN,
            "prior_force_train_multi_if_min": PRIOR_FORCE_TRAIN_MIN,
            "sealed_baseline_mean": SEALED_BASELINE_MEAN,
            "e2_target_mean": E2_TARGET_MEAN,
            "e2_target_min": 0.700,
            "note": (
                "Sealed T1 is recipe-on-legacy17; this board is feature+mix work "
                "with honest dem_lapse_v1 weather (not reanalysis). "
                "Do not auto-promote KEEP without kill scorecard."
            ),
        },
        "e2_vs_sealed_baseline": {
            "mean_ge": E2_TARGET_MEAN,
            "min_ge": 0.700,
            "l1_pass": bool(mean_iou is not None and mean_iou >= E2_TARGET_MEAN),
            "l2_pass": bool(min_iou is not None and min_iou >= 0.700),
        },
        "gaps": [
            "weather_dem_lapse_v1_not_reanalysis",
            "acom2_thin_120_test",
            "no_legacy17_init_channel_mismatch",
        ],
        "rails": {
            "field_ops_allow_ml_live_in_fusion": False,
            "iou_is_not_ros": True,
            "tobarra_keep_reopen": False,
            "larger_unet_default": False,
            "lab_only": True,
        },
        "never_auto_keep": True,
        "operator_note": (
            "Download board + score via "
            "scripts/run_kaggle_spatial_v1_estrella.py --score-only; "
            "do not claim KEEP without E2 kill scorecard."
        ),
    }
    (out_root / "spatial_v1_estrella_lofo_board.json").write_text(
        json.dumps(board, indent=2), encoding="utf-8"
    )
    print(json.dumps(board, indent=2), flush=True)
    return 0 if len(ious) == 3 else 1


if __name__ == "__main__":
    raise SystemExit(main())
