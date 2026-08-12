#!/usr/bin/env python3
"""Kaggle: spatial_v1 LOFO ERA5-Land — longer train (goal +0.05 vs W0 0.5576).

Same as era5_bridge but epochs=64 patience=24. Residual-small + bridge init.
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
EPOCHS = int(os.environ.get("WF_EPOCHS", "64"))
LR = float(os.environ.get("WF_LR", "8e-5"))
PATIENCE = int(os.environ.get("WF_PATIENCE", "24"))
BATCH = int(os.environ.get("WF_BATCH", "8"))
EMA = float(os.environ.get("WF_EMA_DECAY", "0.999"))

PRIOR_BRIDGE_MEAN = 0.5575550981918408
PRIOR_BRIDGE_MIN = 0.48528418760127023
PRIOR_SPATIAL_KILL_MEAN = 0.39175937148336887
PRIOR_SPATIAL_KILL_MIN = 0.27647174861104806
WEATHER_LIFT_THR = 0.01
GOAL_DELTA = 0.05

FIRST_CONV_SPATIAL_TO_LEGACY: list[int | None] = [
    None,
    0,
    None,
    None,
    2,
    2,
    3,
    4,
    None,
    None,
    6,
    11,
    12,
    16,
    17,
]


def _working() -> Path:
    return Path("/kaggle/working") if Path("/kaggle/working").is_dir() else Path(".")


def _looks(root: Path) -> bool:
    return all((root / f / "train").is_dir() for f in CORE3)


def _maybe_zip(zpath: Path) -> Path | None:
    dest = Path("/tmp/lofo_spatial_era5")
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
        Path("/kaggle/input/wfd-lofo-spatial-era5-v1/lofo_mix_spatial_era5_v1"),
        Path(
            "/kaggle/input/datasets/alonsoalviraaaa/wfd-lofo-spatial-era5-v1/"
            "lofo_mix_spatial_era5_v1"
        ),
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
    raise FileNotFoundError("spatial ERA5 LOFO pack missing")


def _find_file(names: tuple[str, ...]) -> str:
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


def _unwrap_sd(obj):
    if not isinstance(obj, dict):
        raise TypeError(type(obj))
    if "model" in obj and isinstance(obj["model"], dict):
        obj = obj["model"]
    elif "state_dict" in obj and isinstance(obj["state_dict"], dict):
        obj = obj["state_dict"]
    return {str(k).replace("module.", ""): v for k, v in obj.items()}


def _ensure_adapted(torch, build_model, UNetTrainConfig, multi_if: str, adapted: Path) -> dict:
    if adapted.is_file():
        m = build_model(UNetTrainConfig(model="small", architecture="residual"), 15)
        m.load_state_dict(
            torch.load(str(adapted), map_location="cpu", weights_only=True), strict=True
        )
        return {"source": "prebuilt", "path": str(adapted), "strict_ok": True}

    raw = torch.load(multi_if, map_location="cpu", weights_only=False)
    src = _unwrap_sd(raw)
    spatial = build_model(UNetTrainConfig(model="small", architecture="residual"), 15)
    dst = spatial.state_dict()

    def fc_key(sd, want_in):
        for k, v in sd.items():
            if hasattr(v, "ndim") and v.ndim == 4 and "weight" in k and v.shape[1] == want_in:
                return k
        for k, v in sd.items():
            if hasattr(v, "ndim") and v.ndim == 4 and "weight" in k:
                return k
        return None

    src_fc, dst_fc = fc_key(src, 18), fc_key(dst, 15)
    mapped = 0
    if src_fc and dst_fc:
        sw, dw = src[src_fc], dst[dst_fc]
        new_w = dw.clone()
        for s_i, l_i in enumerate(FIRST_CONV_SPATIAL_TO_LEGACY):
            if l_i is None or s_i >= dw.shape[1] or l_i >= sw.shape[1]:
                continue
            new_w[:, s_i, :, :] = sw[:, l_i, :, :]
            mapped += 1
        dst[dst_fc] = new_w
    for k, v in src.items():
        if k == src_fc:
            continue
        if k in dst and hasattr(v, "shape") and tuple(v.shape) == tuple(dst[k].shape):
            dst[k] = v
    spatial.load_state_dict(dst, strict=True)
    adapted.parent.mkdir(parents=True, exist_ok=True)
    torch.save(spatial.state_dict(), str(adapted))
    return {
        "source": "built_on_kaggle",
        "path": str(adapted),
        "mapped_input_channels": mapped,
        "strict_ok": True,
    }


def main() -> int:
    print("=" * 70, flush=True)
    print("SPATIAL_V1 ERA5-LAND LONG + BRIDGE (goal +0.05 vs W0)", flush=True)
    print(f"epochs={EPOCHS} lr={LR} patience={PATIENCE} ema={EMA}", flush=True)
    print(f"prior W0 mean={PRIOR_BRIDGE_MEAN:.4f} goal_delta={GOAL_DELTA}", flush=True)
    print("=" * 70, flush=True)

    data_root = _data_root()
    multi_if = _find_file(("weights_multi_if.pt", "weights_multi_if_r8.pt"))
    prebuilt = _find_file(("weights_spatial15_from_multi_if.pt",))
    print("data", data_root, flush=True)
    if not multi_if and not prebuilt:
        print("[error] need multi_if or adapted spatial15 weights", flush=True)
        return 2

    if REPO_DIR.exists():
        shutil.rmtree(REPO_DIR)
    subprocess.run(["git", "clone", "--depth", "1", REPO_URL, str(REPO_DIR)], check=True)
    os.chdir(REPO_DIR)
    sys.path.insert(0, str(REPO_DIR.resolve()))

    import torch

    from wildfire_front.ml.unet_train import UNetTrainConfig, build_model, run_training

    adapted = Path(prebuilt) if prebuilt else (_working() / "weights_spatial15_from_multi_if.pt")
    adapt_rep = _ensure_adapted(
        torch,
        build_model,
        UNetTrainConfig,
        multi_if or prebuilt,
        Path(adapted) if not prebuilt else Path(prebuilt),
    )
    adapted_path = str(Path(adapt_rep["path"]))
    print(json.dumps(adapt_rep, indent=2), flush=True)

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
            data_dir=str(data_root / held),
            output_dir=str(out),
            version_tag=f"spatial_era5_long_{held}",
            early_stop_metric="model_iou",
            init_weights_path=adapted_path,
        )
        print(f"=== held={held} ch={ch} pos={pos} ===", flush=True)
        run_training(cfg)
        ts = out / "training_summary.json"
        row: dict = {
            "held": held,
            "status": "ok",
            "experiment_id": "E_spatial_v1_era5_long",
            "feature_schema": "spatial_v1",
            "work_class": "feature_spatial_v1+weather_era5_land+bridge_init+long",
            "weather_provenance": "era5_land_cds_v1",
            "init_weights_path": adapted_path,
            "change_loss_weight": ch,
            "pos_weight": pos,
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
    delta_mean = (mean_iou - PRIOR_BRIDGE_MEAN) if mean_iou is not None else None
    weather_lift = bool(delta_mean is not None and delta_mean >= WEATHER_LIFT_THR)
    weather_reg = bool(delta_mean is not None and delta_mean <= -WEATHER_LIFT_THR)
    weather_null = bool(delta_mean is not None and abs(delta_mean) < WEATHER_LIFT_THR)
    goal_met = bool(delta_mean is not None and delta_mean >= GOAL_DELTA)

    board = {
        "schema": "wfd_kaggle_spatial_v1_era5_long_v1",
        "created_utc": datetime.now(UTC).isoformat(),
        "experiment_id": "E_spatial_v1_era5_long",
        "work_class": "feature_spatial_v1+weather_era5_land+bridge_init+long",
        "feature_schema": "spatial_v1",
        "weather_provenance": "era5_land_cds_v1",
        "architecture": "residual_small",
        "epochs": EPOCHS,
        "lr": LR,
        "patience": PATIENCE,
        "ema_decay": EMA,
        "adapt_report": adapt_rep,
        "folds": results,
        "core3_mean_iou": mean_iou,
        "core3_min_iou": min_iou,
        "vs_prior_spatial_bridge": {
            "mean": PRIOR_BRIDGE_MEAN,
            "min": PRIOR_BRIDGE_MIN,
            "delta_mean": delta_mean,
            "delta_min": (min_iou - PRIOR_BRIDGE_MIN) if min_iou is not None else None,
        },
        "WEATHER_LIFT": weather_lift,
        "WEATHER_NULL": weather_null,
        "WEATHER_REGRESSION": weather_reg,
        "GOAL_DELTA_MEAN": GOAL_DELTA,
        "GOAL_MET_PLUS_0_05": goal_met,
        "rails": {
            "field_ops_allow_ml_live_in_fusion": False,
            "ml_product_go": True,
            "iou_is_not_ros": True,
            "tobarra_keep_reopen": False,
            "lab_only": True,
            "era5_cds": True,
        },
    }
    (out_root / "spatial_v1_era5_long_board.json").write_text(
        json.dumps(board, indent=2), encoding="utf-8"
    )
    print(json.dumps(board, indent=2), flush=True)
    return 0 if len(results) == 3 else 1


if __name__ == "__main__":
    raise SystemExit(main())
