#!/usr/bin/env python3
"""Kaggle: schema bridge partial_init LONG — goal +0.05 vs prior partial mean 0.6692.

Pack: alonsoalviraaaa/wfd-lofo-physics14-ab (projected physics14)
Prior: schema_bridge_ab_v2 partial_init mean≈0.6692 min≈0.6205
Target: mean ≥ 0.7192 (Δ≥0.05)

Rails: lab · fusion OFF · residual-small · not sealed T1.
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

PRIOR_PARTIAL_MEAN = 0.669188429287695
PRIOR_PARTIAL_MIN = 0.6205450797955965
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


def _root() -> Path:
    if Path("/kaggle/input").is_dir():
        for z in Path("/kaggle/input").rglob("*.zip"):
            dest = Path("/tmp/physics14_ab")
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
        for d in Path("/kaggle/input").rglob("*"):
            if d.is_dir() and _looks(d):
                return d
    raise FileNotFoundError("physics14 projected LOFO missing")


def _find_multi_if() -> str:
    for name in ("weights_multi_if.pt", "weights_multi_if_r8.pt"):
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


def _unwrap_sd(obj):
    if not isinstance(obj, dict):
        raise TypeError(type(obj))
    if "model" in obj and isinstance(obj["model"], dict):
        obj = obj["model"]
    elif "state_dict" in obj and isinstance(obj["state_dict"], dict):
        obj = obj["state_dict"]
    return {str(k).replace("module.", ""): v for k, v in obj.items()}


def _export_adapted(
    torch, build_model, UNetTrainConfig, multi_if_path: str, out_path: Path
) -> dict:
    raw = torch.load(multi_if_path, map_location="cpu", weights_only=False)
    src = _unwrap_sd(raw)
    cfg = UNetTrainConfig(model="small", architecture="residual")
    spatial = build_model(cfg, 15)
    dst = spatial.state_dict()

    def first_conv_key(sd, want_in):
        for k, v in sd.items():
            if hasattr(v, "ndim") and v.ndim == 4 and "weight" in k and v.shape[1] == want_in:
                return k
        for k, v in sd.items():
            if hasattr(v, "ndim") and v.ndim == 4 and "weight" in k:
                return k
        return None

    src_fc, dst_fc = first_conv_key(src, 18), first_conv_key(dst, 15)
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
    out_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(spatial.state_dict(), str(out_path))
    return {"mapped_input_channels": mapped, "out_path": str(out_path), "strict_ok": True}


def main() -> int:
    print("=" * 70, flush=True)
    print("SCHEMA BRIDGE PARTIAL_INIT LONG — goal +0.05 vs 0.6692", flush=True)
    print(f"epochs={EPOCHS} lr={LR} patience={PATIENCE} ema={EMA}", flush=True)
    print("=" * 70, flush=True)

    data = _root()
    multi_if = _find_multi_if()
    print("data", data, "multi_if", multi_if or "(NONE)", flush=True)
    if not multi_if:
        return 2

    if REPO_DIR.exists():
        shutil.rmtree(REPO_DIR)
    subprocess.run(["git", "clone", "--depth", "1", REPO_URL, str(REPO_DIR)], check=True)
    os.chdir(REPO_DIR)
    sys.path.insert(0, str(REPO_DIR.resolve()))

    import torch

    from wildfire_front.ml.unet_train import UNetTrainConfig, build_model, run_training

    adapted_path = _working() / "weights_spatial15_from_multi_if.pt"
    try:
        from wildfire_front.ml.schema_bridge import export_spatial_init_from_multi_if

        adapt_rep = export_spatial_init_from_multi_if(
            multi_if, adapted_path, legacy_in_channels=18, spatial_in_channels=15
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[adapt] vendored ({exc})", flush=True)
        adapt_rep = _export_adapted(torch, build_model, UNetTrainConfig, multi_if, adapted_path)

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
            version_tag=f"schema_long_{held}",
            early_stop_metric="model_iou",
            init_weights_path=str(adapted_path),
        )
        print(f"=== held={held} ch={ch} pos={pos} ===", flush=True)
        run_training(cfg)
        ts = out / "training_summary.json"
        row: dict = {
            "held": held,
            "status": "ok",
            "experiment_id": "E_schema_bridge_long",
            "feature_schema": "physics14",
            "work_class": "schema_bridge_partial_init_long",
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
    delta = (mean_iou - PRIOR_PARTIAL_MEAN) if mean_iou is not None else None
    goal = bool(delta is not None and delta >= GOAL_DELTA)

    board = {
        "schema": "wfd_kaggle_schema_bridge_long_v1",
        "created_utc": datetime.now(UTC).isoformat(),
        "experiment_id": "E_schema_bridge_long",
        "work_class": "schema_bridge_partial_init_long",
        "feature_schema": "physics14",
        "architecture": "residual_small",
        "epochs": EPOCHS,
        "lr": LR,
        "patience": PATIENCE,
        "ema_decay": EMA,
        "adapt_report": adapt_rep,
        "folds": results,
        "core3_mean_iou": mean_iou,
        "core3_min_iou": min_iou,
        "vs_prior_partial_init": {
            "mean": PRIOR_PARTIAL_MEAN,
            "min": PRIOR_PARTIAL_MIN,
            "delta_mean": delta,
            "delta_min": (min_iou - PRIOR_PARTIAL_MIN) if min_iou is not None else None,
        },
        "GOAL_DELTA_MEAN": GOAL_DELTA,
        "GOAL_MET_PLUS_0_05": goal,
        "rails": {
            "field_ops_allow_ml_live_in_fusion": False,
            "ml_product_go": True,
            "lab_only": True,
            "comparability_sealed_t1": False,
        },
    }
    (out_root / "schema_bridge_long_board.json").write_text(
        json.dumps(board, indent=2), encoding="utf-8"
    )
    print(json.dumps(board, indent=2), flush=True)
    return 0 if len(results) == 3 else 1


if __name__ == "__main__":
    raise SystemExit(main())
