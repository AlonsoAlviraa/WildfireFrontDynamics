#!/usr/bin/env python3
"""Kaggle T4: large residual LOFO hyperparameter / init GRID (sealed core-3).

Maximizes GPU use: many full core-3 trainings in one kernel session.
No Hellín primary (E3a KILL). No larger U-Net. Fusion OFF.

Strategy
--------
* Dataset: sealed lofo_v1 core-3 + multi init checkpoints
* Each config trains CARDOSO + ACOM1 + ACOM2 (residual small)
* Leaderboard by: (1) E2 KEEP (mean≥base+0.01, min≥0.700)
                 (2) G1 (mean≥0.780) (3) G2 (min≥0.720) (4) mean then min

Env overrides:
  WF_MAX_CONFIGS=N   limit configs (debug)
  WF_FOLDS=CARDOSO,LA_ESTRELLA_ACOM2
  WF_SKIP_EARLY=1    force more epochs (patience high)
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_URL = "https://github.com/AlonsoAlviraa/WildfireFrontDynamics.git"
REPO_DIR = Path("/tmp/WildfireFrontDynamics")
CORE3 = ("CARDOSO", "LA_ESTRELLA_ACOM1", "LA_ESTRELLA_ACOM2")
BASELINE_MEAN = 0.7580534465179306
BASELINE_MIN = 0.6931861844919686
E2_MEAN = BASELINE_MEAN + 0.010
G1_MEAN = 0.780
G2_MIN = 0.720
L2_HARD = 0.700

# Curated grid — not full cartesian (would explode). ~12 full core-3 runs.
# Prior: push ACOM2 floor toward 0.720 while keeping mean ≥ 0.780 (T2 path).
GRID: list[dict[str, Any]] = [
    # --- v2-like anchors ---
    {
        "id": "v2_anchor",
        "init": "weights_multi_if.pt",
        "epochs": 28,
        "lr": 1e-4,
        "patience": 10,
        "batch": 8,
        "change_w": 6.0,
        "pos_w": 6.0,
        "acom2_change_w": 10.0,
        "acom2_pos_w": 8.0,
        "note": "recover_v2 recipe baseline",
    },
    # --- longer / lower LR (less early-stop on multi_if VAL peak) ---
    {
        "id": "long_lowlr_multi_if",
        "init": "weights_multi_if.pt",
        "epochs": 40,
        "lr": 5e-5,
        "patience": 14,
        "batch": 8,
        "change_w": 6.0,
        "pos_w": 6.0,
        "acom2_change_w": 10.0,
        "acom2_pos_w": 8.0,
        "note": "longer train lower lr",
    },
    {
        "id": "long_lowlr_acom2_heavy",
        "init": "weights_multi_if.pt",
        "epochs": 40,
        "lr": 5e-5,
        "patience": 14,
        "batch": 8,
        "change_w": 8.0,
        "pos_w": 7.0,
        "acom2_change_w": 14.0,
        "acom2_pos_w": 12.0,
        "note": "ACOM2-heavy growth curriculum",
    },
    # --- alternate Spain inits ---
    {
        "id": "v30_ema_mid",
        "init": "weights_v30_ema.pt",
        "epochs": 30,
        "lr": 1e-4,
        "patience": 12,
        "batch": 8,
        "change_w": 7.0,
        "pos_w": 6.0,
        "acom2_change_w": 11.0,
        "acom2_pos_w": 9.0,
        "note": "init v30 EMA",
    },
    {
        "id": "v28_clm_ft",
        "init": "weights_v28_clm_ft.pt",
        "epochs": 30,
        "lr": 1e-4,
        "patience": 12,
        "batch": 8,
        "change_w": 7.0,
        "pos_w": 6.0,
        "acom2_change_w": 11.0,
        "acom2_pos_w": 9.0,
        "note": "init v28 CLM FT",
    },
    {
        "id": "multi_if_r8",
        "init": "weights_multi_if_r8.pt",
        "epochs": 30,
        "lr": 1e-4,
        "patience": 12,
        "batch": 8,
        "change_w": 6.0,
        "pos_w": 6.0,
        "acom2_change_w": 10.0,
        "acom2_pos_w": 8.0,
        "note": "init multi_if_r8",
    },
    # --- continue from recover_v2 fold weights (warm start) ---
    {
        "id": "warm_recover_v2",
        "init": "per_fold_recover_v2",  # special
        "epochs": 24,
        "lr": 5e-5,
        "patience": 12,
        "batch": 8,
        "change_w": 6.0,
        "pos_w": 6.0,
        "acom2_change_w": 12.0,
        "acom2_pos_w": 10.0,
        "note": "warm-start from E_recover_v2 fold weights",
    },
    # --- batch / lr axes ---
    {
        "id": "batch16_lr1e4",
        "init": "weights_multi_if.pt",
        "epochs": 32,
        "lr": 1e-4,
        "patience": 12,
        "batch": 16,
        "change_w": 6.0,
        "pos_w": 6.0,
        "acom2_change_w": 10.0,
        "acom2_pos_w": 8.0,
        "note": "larger batch",
    },
    {
        "id": "lr2e4_short_patience",
        "init": "weights_multi_if.pt",
        "epochs": 24,
        "lr": 2e-4,
        "patience": 8,
        "batch": 8,
        "change_w": 6.0,
        "pos_w": 6.0,
        "acom2_change_w": 10.0,
        "acom2_pos_w": 8.0,
        "note": "higher lr",
    },
    # --- growth extreme for ACOM2 floor ---
    {
        "id": "growth_extreme_acom2",
        "init": "weights_multi_if.pt",
        "epochs": 36,
        "lr": 7e-5,
        "patience": 14,
        "batch": 8,
        "change_w": 10.0,
        "pos_w": 8.0,
        "acom2_change_w": 16.0,
        "acom2_pos_w": 14.0,
        "note": "extreme growth weight ACOM2",
    },
    {
        "id": "mild_growth_balanced",
        "init": "weights_multi_if.pt",
        "epochs": 32,
        "lr": 8e-5,
        "patience": 12,
        "batch": 8,
        "change_w": 5.0,
        "pos_w": 5.0,
        "acom2_change_w": 8.0,
        "acom2_pos_w": 7.0,
        "note": "milder growth — less overfit VAL",
    },
    {
        "id": "v21_ndws_init",
        "init": "weights_v21_best.pt",
        "epochs": 32,
        "lr": 1e-4,
        "patience": 12,
        "batch": 8,
        "change_w": 6.0,
        "pos_w": 6.0,
        "acom2_change_w": 10.0,
        "acom2_pos_w": 8.0,
        "note": "NDWS v21 init control",
    },
    # --- longer patience from multi_if (force past epoch-1 stop) ---
    {
        "id": "force_train_multi_if",
        "init": "weights_multi_if.pt",
        "epochs": 36,
        "lr": 3e-5,
        "patience": 20,
        "batch": 8,
        "change_w": 6.0,
        "pos_w": 6.0,
        "acom2_change_w": 10.0,
        "acom2_pos_w": 8.0,
        "note": "very low lr high patience — more epochs of true update",
    },
    {
        "id": "warm_v2_acom2_extreme",
        "init": "per_fold_recover_v2",
        "epochs": 30,
        "lr": 3e-5,
        "patience": 15,
        "batch": 8,
        "change_w": 8.0,
        "pos_w": 7.0,
        "acom2_change_w": 16.0,
        "acom2_pos_w": 14.0,
        "note": "warm v2 + extreme ACOM2 growth",
    },
]


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
            [sys.executable, "-m", "pip", "install", "-q", "torch==2.1.2", "torchvision==0.16.2"],
            check=False,
            timeout=600,
        )
    except Exception as exc:
        print(f"[warn] p100: {exc}", flush=True)


def _extract_and_find_data() -> Path:
    """Locate sealed core-3 folds + inits under /kaggle/input."""
    candidates = [
        Path("/kaggle/input/wfd-lofo-grid-inits"),
        Path("/kaggle/input/datasets/alonsoalviraaaa/wfd-lofo-grid-inits"),
        Path("/kaggle/input/wfd-lofo-v1-core3"),
        Path("/kaggle/input/datasets/alonsoalviraaaa/wfd-lofo-v1-core3"),
    ]
    for c in candidates:
        if not c.is_dir():
            continue
        if any((c / f / "train").is_dir() for f in CORE3):
            return c
        for zname in (
            "lofo_grid_bundle.zip",
            "lofo_v1_core3.zip",
            "lofo_v1_core3_with_inits.zip",
        ):
            z = c / zname
            if not z.is_file():
                continue
            dest = Path("/tmp/lofo_grid")
            if dest.exists():
                shutil.rmtree(dest)
            dest.mkdir(parents=True)
            print(f"[data] extract {z}", flush=True)
            with zipfile.ZipFile(z) as zf:
                zf.extractall(dest)
            for cand in (dest, dest / "lofo_v1", dest / "packs"):
                if any((cand / f / "train").is_dir() for f in CORE3):
                    return cand
    raise FileNotFoundError("sealed core-3 LOFO packs not found")


def _resolve_init(data_root: Path, name: str, held: str) -> str:
    if name == "per_fold_recover_v2":
        # prefer fold-specific warm weight
        for p in (
            data_root / "recover_v2" / held / "weights_pretrained_best.pt",
            data_root / f"recover_v2_{held}.pt",
            data_root / "recover_v2" / f"{held}.pt",
            Path("/tmp/lofo_grid") / "recover_v2" / held / "weights_pretrained_best.pt",
        ):
            if p.is_file():
                return str(p)
        # fallback multi_if
        name = "weights_multi_if.pt"
    for base in (data_root, Path("/tmp/lofo_grid"), Path("/tmp")):
        p = base / name
        if p.is_file():
            return str(p)
        for hit in base.rglob(name):
            if hit.is_file():
                return str(hit)
    print(f"[warn] init {name} missing — empty init", flush=True)
    return ""


def _clone_repo() -> None:
    if REPO_DIR.exists():
        shutil.rmtree(REPO_DIR)
    subprocess.run(["git", "clone", "--depth", "1", REPO_URL, str(REPO_DIR)], check=True)
    os.chdir(REPO_DIR)
    sys.path.insert(0, str(REPO_DIR.resolve()))


def _folds() -> tuple[str, ...]:
    raw = os.environ.get("WF_FOLDS", "").strip()
    if raw:
        return tuple(x.strip() for x in raw.split(",") if x.strip())
    return CORE3


def _rank_key(row: dict[str, Any]) -> tuple:
    mean = row.get("core3_mean_iou")
    mn = row.get("core3_min_iou")
    if mean is None or mn is None:
        return (0, 0, 0, 0, -1.0, -1.0)
    e2 = int(mean >= E2_MEAN and mn >= L2_HARD)
    g1 = int(mean >= G1_MEAN)
    g2 = int(mn >= G2_MIN)
    t2 = int(g1 and g2)
    return (t2, e2, g1, g2, float(mean), float(mn))


def main() -> int:
    print("=" * 72, flush=True)
    print("METRICS LIFT LOFO GRID — sealed core-3 · residual small · multi-config", flush=True)
    print("Rails: lab_ml · fusion OFF · IoU≠ROS · no Tobarra KEEP · no larger U-Net", flush=True)
    print("=" * 72, flush=True)
    t0 = time.time()
    _install_p100()
    data_root = _extract_and_find_data()
    print(f"[data] root={data_root}", flush=True)
    _clone_repo()

    from wildfire_front.ml.unet_train import UNetTrainConfig, run_training

    out_root = _working()
    grid_dir = out_root / "grid"
    grid_dir.mkdir(parents=True, exist_ok=True)

    folds = _folds()
    max_cfg = int(os.environ.get("WF_MAX_CONFIGS", "0") or "0")
    id_filter = os.environ.get("WF_CONFIG_IDS", "").strip()
    grid = list(GRID)
    if id_filter:
        wanted = {x.strip() for x in id_filter.split(",") if x.strip()}
        grid = [c for c in grid if str(c.get("id")) in wanted]
        print(
            f"[grid] WF_CONFIG_IDS -> {len(grid)}: {[c['id'] for c in grid]}",
            flush=True,
        )
    if max_cfg:
        grid = grid[:max_cfg]
    skip_early = os.environ.get("WF_SKIP_EARLY", "").strip() in {"1", "true", "yes"}

    results: list[dict[str, Any]] = []
    for ci, cfg in enumerate(grid):
        cid = str(cfg["id"])
        print(f"\n{'#' * 72}\n# CONFIG {ci + 1}/{len(grid)}: {cid}\n{'#' * 72}", flush=True)
        cfg_out = grid_dir / cid
        cfg_out.mkdir(parents=True, exist_ok=True)
        fold_rows: list[dict[str, Any]] = []
        for held in folds:
            data = data_root / held
            if not (data / "train").is_dir():
                fold_rows.append({"held": held, "status": "missing_split"})
                continue
            out = cfg_out / held
            out.mkdir(parents=True, exist_ok=True)
            init = _resolve_init(data_root, str(cfg["init"]), held)
            change_w = float(
                cfg["acom2_change_w"] if held == "LA_ESTRELLA_ACOM2" else cfg["change_w"]
            )
            pos_w = float(cfg["acom2_pos_w"] if held == "LA_ESTRELLA_ACOM2" else cfg["pos_w"])
            patience = int(cfg["patience"])
            if skip_early:
                patience = max(patience, 18)
            train_cfg = UNetTrainConfig(
                epochs=int(cfg["epochs"]),
                batch_size=int(cfg["batch"]),
                lr=float(cfg["lr"]),
                loss="composite",
                pos_weight=pos_w,
                model="small",
                architecture="residual",
                target_mode="delta",
                change_loss_weight=change_w,
                weighted_sampler=True,
                patience=patience,
                data_dir=str(data),
                output_dir=str(out),
                version_tag=f"grid_{cid}_{held}",
                early_stop_metric="improvement_vs_copy_iou",
                init_weights_path=init,
            )
            print(
                f"=== {cid} held={held} lr={cfg['lr']} ch={change_w} pos={pos_w} init={Path(init).name if init else None} ===",
                flush=True,
            )
            try:
                run_training(train_cfg)
            except Exception as exc:
                fold_rows.append({"held": held, "status": "error", "error": str(exc)})
                print(f"[error] {cid}/{held}: {exc}", flush=True)
                continue
            ts = out / "training_summary.json"
            row: dict[str, Any] = {
                "held": held,
                "status": "ok",
                "config_id": cid,
                "init": init,
                "change_loss_weight": change_w,
                "pos_weight": pos_w,
            }
            if ts.is_file():
                prev = json.loads(ts.read_text(encoding="utf-8"))
                if isinstance(prev, dict):
                    prev.update(
                        {
                            "grid_config_id": cid,
                            "schema_path_id": "E_grid",
                            "feature_schema": "legacy17",
                            "held_out": held,
                            "no_hellin": True,
                        }
                    )
                    ts.write_text(json.dumps(prev, indent=2), encoding="utf-8")
                    row["model_iou"] = prev.get("model_iou") or prev.get("test_iou")
                    row["copy_baseline_iou"] = prev.get("copy_baseline_iou")
                    row["improvement_vs_copy_iou"] = prev.get("improvement_vs_copy_iou")
                    row["best_epoch"] = prev.get("best_epoch")
                    em = out / "evaluation_metrics.json"
                    if not em.is_file():
                        em.write_text(json.dumps(prev, indent=2), encoding="utf-8")
                    elif "model_iou" not in json.loads(em.read_text(encoding="utf-8")):
                        emj = json.loads(em.read_text(encoding="utf-8"))
                        emj["model_iou"] = emj.get("test_iou") or row.get("model_iou")
                        em.write_text(json.dumps(emj, indent=2), encoding="utf-8")
            fold_rows.append(row)
            print(json.dumps(row, indent=2), flush=True)

        ious = [float(r["model_iou"]) for r in fold_rows if r.get("model_iou") is not None]
        mean = sum(ious) / len(ious) if ious else None
        mn = min(ious) if ious else None
        summary = {
            "config_id": cid,
            "config": cfg,
            "folds": fold_rows,
            "n_folds_ok": len(ious),
            "core3_mean_iou": mean,
            "core3_min_iou": mn,
            "delta_mean": (mean - BASELINE_MEAN) if mean is not None else None,
            "delta_min": (mn - BASELINE_MIN) if mn is not None else None,
            "e2_keep": bool(
                mean is not None and mn is not None and mean >= E2_MEAN and mn >= L2_HARD
            ),
            "g1_met": bool(mean is not None and mean >= G1_MEAN),
            "g2_met": bool(mn is not None and mn >= G2_MIN),
            "t2_closed": bool(
                mean is not None and mn is not None and mean >= G1_MEAN and mn >= G2_MIN
            ),
            "elapsed_s_so_far": time.time() - t0,
        }
        (cfg_out / "config_summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        results.append(summary)
        print(
            f"[summary] {cid} mean={mean} min={mn} e2={summary['e2_keep']} g1={summary['g1_met']} g2={summary['g2_met']}",
            flush=True,
        )
        # checkpoint leaderboard after each config (crash-safe)
        ranked = sorted(results, key=_rank_key, reverse=True)
        board = {
            "schema": "wfd_kaggle_metrics_lift_lofo_grid_v1",
            "created_utc": datetime.now(UTC).isoformat(),
            "experiment_id": "E_lofo_grid_sealed",
            "product_rail": "lab_ml",
            "architecture": "residual_small",
            "n_configs_planned": len(grid),
            "n_configs_done": len(results),
            "folds": list(folds),
            "baselines": {"lofo_mean_iou": BASELINE_MEAN, "lofo_min_iou": BASELINE_MIN},
            "thresholds": {
                "e2_mean": E2_MEAN,
                "l2_hard_min": L2_HARD,
                "g1_mean": G1_MEAN,
                "g2_min": G2_MIN,
            },
            "leaderboard": [
                {
                    "rank": i + 1,
                    "config_id": r["config_id"],
                    "mean": r.get("core3_mean_iou"),
                    "min": r.get("core3_min_iou"),
                    "delta_mean": r.get("delta_mean"),
                    "delta_min": r.get("delta_min"),
                    "e2_keep": r.get("e2_keep"),
                    "g1_met": r.get("g1_met"),
                    "g2_met": r.get("g2_met"),
                    "t2_closed": r.get("t2_closed"),
                    "note": (r.get("config") or {}).get("note"),
                }
                for i, r in enumerate(ranked)
            ],
            "results": results,
            "rails": {
                "field_ops_allow_ml_live_in_fusion": False,
                "iou_is_not_ros": True,
                "tobarra_keep_reopen": False,
                "larger_unet_default": False,
                "no_hellin_primary": True,
            },
            "elapsed_s": time.time() - t0,
            "honesty": [
                "Grid residual LOFO only — not ML IoU as ROS",
                "No field fusion",
                "No Tobarra KEEP reopen",
                "No larger U-Net default",
                "Champion promote is human-gated PR4 only",
            ],
        }
        (out_root / "metrics_lift_grid_board.json").write_text(
            json.dumps(board, indent=2), encoding="utf-8"
        )
        (grid_dir / "leaderboard_latest.json").write_text(
            json.dumps(board["leaderboard"], indent=2), encoding="utf-8"
        )

    print("\n=== FINAL LEADERBOARD ===", flush=True)
    board_path = out_root / "metrics_lift_grid_board.json"
    if board_path.is_file():
        print(board_path.read_text(encoding="utf-8")[:4000], flush=True)
    return 0 if results else 1


if __name__ == "__main__":
    raise SystemExit(main())
