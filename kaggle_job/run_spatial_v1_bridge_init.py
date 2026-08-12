#!/usr/bin/env python3
"""Kaggle: spatial_v1 LOFO + adapted multi_if→15ch init (schema bridge transfer).

Data sources (dataset_sources):
  * alonsoalviraaaa/wfd-lofo-spatial-estrella-v1  (spatial_v1 geotiff pack)
  * alonsoalviraaaa/wfd-schema-bridge-ab-physics14 (multi_if + adapted weights)

Fixes from prior spatial KILL (~0.39 from-scratch):
  * Warm-start from adapted spatial15 state_dict (not legacy17 strict load)
  * early_stop_metric = model_iou (not improvement_vs_copy stuck at 0)

work_class: feature_spatial_v1+schema_bridge_adapted_init
Comparability: NOT sealed recipe_t1; vs prior spatial KILL board.
Rails: lab · fusion OFF · residual-small · ml_product_go lab true ≠ field fusion.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_URL = "https://github.com/AlonsoAlviraa/WildfireFrontDynamics.git"
REPO_DIR = Path("/tmp/WildfireFrontDynamics")
CORE3 = ("CARDOSO", "LA_ESTRELLA_ACOM1", "LA_ESTRELLA_ACOM2")
EPOCHS = int(os.environ.get("WF_EPOCHS", "40"))
LR = float(os.environ.get("WF_LR", "8e-5"))
PATIENCE = int(os.environ.get("WF_PATIENCE", "15"))
BATCH = int(os.environ.get("WF_BATCH", "8"))
EMA = float(os.environ.get("WF_EMA_DECAY", "0.999"))
# Prior spatial weather+fuel from-scratch kill (reference only)
PRIOR_SPATIAL_KILL_MEAN = 0.39175937148336887
PRIOR_SPATIAL_KILL_MIN = 0.27647174861104806
# Bridge A/B partial_init bar on projected pack (different data — reference)
BRIDGE_AB_PARTIAL_MEAN = 0.669188429287695

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


def _data_root() -> Path:
    if Path("/kaggle/input").is_dir():
        for d in Path("/kaggle/input").rglob("*"):
            if d.is_dir() and _looks(d):
                # Prefer spatial / estrella pack names
                return d
    raise FileNotFoundError("spatial LOFO pack missing under /kaggle/input")


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
        # validate load
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
    print("SPATIAL_V1 + BRIDGE ADAPTED INIT LOFO", flush=True)
    print(f"epochs={EPOCHS} lr={LR} patience={PATIENCE} ema={EMA}", flush=True)
    print(
        f"prior spatial KILL mean={PRIOR_SPATIAL_KILL_MEAN:.4f} min={PRIOR_SPATIAL_KILL_MIN:.4f}",
        flush=True,
    )
    print("=" * 70, flush=True)

    data_root = _data_root()
    multi_if = _find_file(("weights_multi_if.pt", "weights_multi_if_r8.pt"))
    prebuilt = _find_file(("weights_spatial15_from_multi_if.pt",))
    print("data", data_root, flush=True)
    print("multi_if", multi_if or "(none)", "prebuilt", prebuilt or "(none)", flush=True)
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
    # normalize path
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
            version_tag=f"spatial_bridge_init_{held}",
            early_stop_metric="model_iou",
            init_weights_path=adapted_path,
        )
        print(f"=== held={held} ch={ch} pos={pos} init=adapted15 ===", flush=True)
        run_training(cfg)
        ts = out / "training_summary.json"
        row: dict = {
            "held": held,
            "status": "ok",
            "experiment_id": "E_spatial_v1_bridge_adapted_init",
            "feature_schema": "spatial_v1",
            "work_class": "feature_spatial_v1+schema_bridge_adapted_init",
            "init_weights_path": adapted_path,
            "early_stop_metric": "model_iou",
            "change_loss_weight": ch,
            "pos_weight": pos,
        }
        if ts.is_file():
            prev = json.loads(ts.read_text(encoding="utf-8"))
            row["model_iou"] = prev.get("model_iou") or prev.get("test_iou")
            row["copy_baseline_iou"] = prev.get("copy_baseline_iou")
            row["improvement_vs_copy_iou"] = prev.get("improvement_vs_copy_iou")
            row["best_epoch"] = prev.get("best_epoch")
            em = out / "evaluation_metrics.json"
            if not em.is_file():
                em.write_text(json.dumps({**prev, **row}, indent=2), encoding="utf-8")
        results.append(row)
        print(json.dumps(row, indent=2), flush=True)

    ious = [float(r["model_iou"]) for r in results if r.get("model_iou") is not None]
    mean_iou = sum(ious) / len(ious) if ious else None
    min_iou = min(ious) if ious else None
    beats_prior_kill = bool(
        mean_iou is not None
        and min_iou is not None
        and mean_iou > PRIOR_SPATIAL_KILL_MEAN
        and min_iou > PRIOR_SPATIAL_KILL_MIN
    )
    lifts_copy = [
        float(r.get("improvement_vs_copy_iou") or 0)
        for r in results
        if r.get("improvement_vs_copy_iou") is not None
    ]
    n_folds_beat_copy_05 = sum(1 for x in lifts_copy if x >= 0.05)

    board = {
        "schema": "wfd_kaggle_spatial_v1_bridge_init_v1",
        "created_utc": datetime.now(UTC).isoformat(),
        "experiment_id": "E_spatial_v1_bridge_adapted_init",
        "work_class": "feature_spatial_v1+schema_bridge_adapted_init",
        "feature_schema": "spatial_v1",
        "architecture": "residual_small",
        "epochs": EPOCHS,
        "lr": LR,
        "patience": PATIENCE,
        "ema_decay": EMA,
        "early_stop_metric": "model_iou",
        "adapt_report": adapt_rep,
        "folds": results,
        "core3_mean_iou": mean_iou,
        "core3_min_iou": min_iou,
        "beats_prior_spatial_kill": beats_prior_kill,
        "prior_spatial_kill": {
            "mean": PRIOR_SPATIAL_KILL_MEAN,
            "min": PRIOR_SPATIAL_KILL_MIN,
        },
        "n_folds_improvement_vs_copy_ge_0_05": n_folds_beat_copy_05,
        "v2_6_gate_2_folds_copy_plus_0_05": n_folds_beat_copy_05 >= 2,
        "bridge_ab_partial_mean_ref": BRIDGE_AB_PARTIAL_MEAN,
        "rails": {
            "field_ops_allow_ml_live_in_fusion": False,
            "ml_product_go": True,
            "iou_is_not_ros": True,
            "tobarra_keep_reopen": False,
            "lab_only": True,
            "comparability_sealed_t1": False,
        },
        "note": (
            "Spatial geotiff pack + adapted multi_if init. Not sealed T1. "
            "Success vs prior from-scratch spatial KILL and vs copy+0.05 on ≥2 folds."
        ),
    }
    (out_root / "spatial_v1_bridge_init_board.json").write_text(
        json.dumps(board, indent=2), encoding="utf-8"
    )
    print(json.dumps(board, indent=2), flush=True)
    return 0 if len(results) == 3 else 1


if __name__ == "__main__":
    raise SystemExit(main())
