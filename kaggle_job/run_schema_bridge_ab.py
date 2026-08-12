#!/usr/bin/env python3
"""Kaggle A/B v2: physics14 projected pack — scratch vs adapted multi_if init.

Root-cause fix vs v1
--------------------
* v1 monkeypatch of build_model was unreliable; both arms stayed at copy IoU.
* early_stop on improvement_vs_copy_iou froze epoch-1 (delta=0) forever.
* v2: pre-export full spatial state_dict via schema_bridge.export_spatial_init_from_multi_if
  (vendored here if git clone lacks module), load with strict=True.
* early_stop_metric = model_iou (absolute), not improvement_vs_copy.

Gate: partial mean − scratch mean ≥ 0.02 AND min_partial ≥ min_scratch.

Rails: lab · fusion OFF · residual small · not sealed T1 comparable.
work_class: schema_bridge_ab_v2
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

# First-conv map: spatial_in (15) ← legacy_in (18)
FIRST_CONV_SPATIAL_TO_LEGACY: list[int | None] = [
    None,  # elev GAP
    0,  # slope
    None,  # aspect_sin
    None,  # aspect_cos
    2,  # tmin ← temp
    2,  # tmax ← temp
    3,  # humidity
    4,  # wind_speed
    None,  # wind_sin
    None,  # wind_cos
    6,  # precip
    11,  # veg
    12,  # erc
    16,  # ffmc
    17,  # prev_fire
]


def _working() -> Path:
    return Path("/kaggle/working") if Path("/kaggle/working").is_dir() else Path(".")


def _looks(root: Path) -> bool:
    return all((root / f / "train").is_dir() for f in CORE3)


def _root() -> Path:
    if Path("/kaggle/input").is_dir():
        for d in Path("/kaggle/input").rglob("*"):
            if d.is_dir() and _looks(d):
                return d
    raise FileNotFoundError("projected physics14 LOFO missing")


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
    """Create full spatial state_dict from multi_if (no monkeypatch)."""
    raw = torch.load(multi_if_path, map_location="cpu", weights_only=False)
    src = _unwrap_sd(raw)
    cfg = UNetTrainConfig(model="small", architecture="residual")
    spatial = build_model(cfg, 15)
    dst = spatial.state_dict()
    loaded = []

    def first_conv_key(sd, want_in):
        for k, v in sd.items():
            if hasattr(v, "ndim") and v.ndim == 4 and "weight" in k and v.shape[1] == want_in:
                return k
        for k, v in sd.items():
            if hasattr(v, "ndim") and v.ndim == 4 and "weight" in k:
                return k
        return None

    src_fc = first_conv_key(src, 18)
    dst_fc = first_conv_key(dst, 15)
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
        loaded.append(dst_fc)
    for k, v in src.items():
        if k == src_fc:
            continue
        if k in dst and hasattr(v, "shape") and tuple(v.shape) == tuple(dst[k].shape):
            dst[k] = v
            loaded.append(k)
    spatial.load_state_dict(dst, strict=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(spatial.state_dict(), str(out_path))
    # verify
    m2 = build_model(cfg, 15)
    m2.load_state_dict(
        torch.load(str(out_path), map_location="cpu", weights_only=True), strict=True
    )
    rep = {
        "mapped_input_channels": mapped,
        "frac_mapped": mapped / 15.0,
        "n_keys_loaded": len(set(loaded)),
        "out_path": str(out_path),
        "strict_reload_ok": True,
        "work_class": "schema_bridge_adapted_init_v2",
    }
    print(json.dumps(rep, indent=2), flush=True)
    return rep


def main() -> int:
    print("=" * 70, flush=True)
    print("SCHEMA BRIDGE A/B v2 — adapted checkpoint + model_iou early-stop", flush=True)
    print(f"epochs={EPOCHS} lr={LR} patience={PATIENCE} ema={EMA}", flush=True)
    print("=" * 70, flush=True)

    data = _root()
    multi_if = _find_multi_if()
    print("data", data, "multi_if", multi_if or "(NONE)", flush=True)
    if not multi_if:
        print("[error] multi_if weights required", flush=True)
        return 2

    if REPO_DIR.exists():
        shutil.rmtree(REPO_DIR)
    subprocess.run(["git", "clone", "--depth", "1", REPO_URL, str(REPO_DIR)], check=True)
    os.chdir(REPO_DIR)
    sys.path.insert(0, str(REPO_DIR.resolve()))

    import torch

    from wildfire_front.ml.unet_train import UNetTrainConfig, build_model, run_training

    # Prefer in-repo export if present (post-merge); else vendored
    adapted_path = _working() / "weights_spatial15_from_multi_if.pt"
    try:
        from wildfire_front.ml.schema_bridge import export_spatial_init_from_multi_if

        adapt_rep = export_spatial_init_from_multi_if(
            multi_if, adapted_path, legacy_in_channels=18, spatial_in_channels=15
        )
        print("[adapt] used repo schema_bridge.export_spatial_init_from_multi_if", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"[adapt] repo export unavailable ({exc}); vendored export", flush=True)
        adapt_rep = _export_adapted(torch, build_model, UNetTrainConfig, multi_if, adapted_path)

    out_root = _working()
    arms = []
    for arm in ("scratch", "partial_init"):
        fold_rows = []
        for held in CORE3:
            out = out_root / arm / held
            out.mkdir(parents=True, exist_ok=True)
            ch, pos = _fold_hparams(held)
            init_path = str(adapted_path) if arm == "partial_init" else None
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
                ema_decay=EMA if arm == "partial_init" else 0.0,
                data_dir=str(data / held),
                output_dir=str(out),
                version_tag=f"bridge_v2_{arm}_{held}",
                # CRITICAL: do not use improvement_vs_copy (stays 0 on weak packs)
                early_stop_metric="model_iou",
                init_weights_path=init_path,
                # Note: init_weights_strict is local-only; remote main may lack the field.
                # Adapted checkpoint is a full 15ch state_dict → strict=True default works.
            )
            print(f"=== {arm} held={held} init={bool(init_path)} ===", flush=True)
            run_training(cfg)
            ts = out / "training_summary.json"
            row: dict = {
                "held": held,
                "arm": arm,
                "status": "ok",
                "init_weights_path": init_path,
                "early_stop_metric": "model_iou",
            }
            if ts.is_file():
                prev = json.loads(ts.read_text(encoding="utf-8"))
                row["model_iou"] = prev.get("model_iou") or prev.get("test_iou")
                row["copy_baseline_iou"] = prev.get("copy_baseline_iou")
                row["improvement_vs_copy_iou"] = prev.get("improvement_vs_copy_iou")
                row["best_epoch"] = prev.get("best_epoch")
            fold_rows.append(row)
            print(json.dumps(row, indent=2), flush=True)

        ious = [float(r["model_iou"]) for r in fold_rows if r.get("model_iou") is not None]
        arms.append(
            {
                "arm": arm,
                "mean": (sum(ious) / len(ious)) if ious else None,
                "min": min(ious) if ious else None,
                "folds": fold_rows,
            }
        )

    by = {a["arm"]: a for a in arms}
    s, p = by.get("scratch"), by.get("partial_init")
    delta_mean = (
        (p["mean"] - s["mean"])
        if s and p and s["mean"] is not None and p["mean"] is not None
        else None
    )
    gate = bool(
        delta_mean is not None
        and p is not None
        and s is not None
        and p["min"] is not None
        and s["min"] is not None
        and delta_mean >= 0.02
        and p["min"] >= s["min"]
    )
    board = {
        "schema": "wfd_kaggle_schema_bridge_ab_v2",
        "created_utc": datetime.now(UTC).isoformat(),
        "work_class": "schema_bridge_ab_v2",
        "feature_schema": "physics14",
        "adapt_report": adapt_rep,
        "arms": arms,
        "delta_mean_partial_minus_scratch": delta_mean,
        "gate_delta_mean_ge_0_02": gate,
        "early_stop_metric": "model_iou",
        "hparams": {
            "epochs": EPOCHS,
            "lr": LR,
            "patience": PATIENCE,
            "ema_partial": EMA,
        },
        "rails": {
            "field_ops_allow_ml_live_in_fusion": False,
            "ml_product_go": True,
            "comparability": "not_sealed_t1",
        },
        "v1_failure_notes": (
            "v1 used improvement_vs_copy early-stop (stuck at 0) and fragile monkeypatch; "
            "both arms matched copy. v2 uses adapted full state_dict + model_iou ES."
        ),
    }
    (_working() / "schema_bridge_ab_board.json").write_text(
        json.dumps(board, indent=2), encoding="utf-8"
    )
    print(json.dumps(board, indent=2), flush=True)
    return 0 if (s and p) else 1


if __name__ == "__main__":
    raise SystemExit(main())
