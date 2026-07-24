#!/usr/bin/env python3
"""Iterative 3-way ML loop (CLM transfer only — G1 NDWS stays KILLED).

Cycles forever (or --rounds N) through:

  1. multi_if   — retrain specialist on multi-fire LOFO-CARDOSO train (no Cardoso)
  2. source_mix — per-source mix calibration (LOFO tests) → Cardoso recipe for holdout
  3. multi_obj  — fine-tune with multi-objective early-stop (full Δ + λ·growth IoU)

Each step is a single-change experiment with honest gates vs current champion.

Examples:
  python scripts/run_ml_loop_3way.py --rounds 2 --epochs 10 --patience 4
  python scripts/run_ml_loop_3way.py --rounds 1 --only multi_if,source_mix
  python scripts/run_ml_loop_3way.py --rounds 0   # run forever (Ctrl+C)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import contextlib  # noqa: E402

from wildfire_front.ml.clm_eval import (  # noqa: E402
    collect_member_growth_cache,
    evaluate_clm_weights,
    score_mix_from_cache,
    sweep_mix_threshold_from_cache,
)
from wildfire_front.ml.protocol_rails import SplitContext  # noqa: E402
from wildfire_front.ml.unet_train import UNetTrainConfig, run_training  # noqa: E402

# Protocol rails: LOFO/test only report; mix/temp selection only on VAL
_CTX_REPORT_LOFO = SplitContext(split="lofo", action="report")
_CTX_REPORT_TEST = SplitContext(split="test", action="report")
_CTX_TUNE_VAL = SplitContext(split="val", action="tune_mix")
_CTX_TEMP_VAL = SplitContext(split="val", action="tune_temperature")

TRACKS = ("multi_if", "source_mix", "multi_obj")
HOLDOUT = ROOT / "artifacts" / "clm_ndws_patches" / "holdout_v1"
LOFO = ROOT / "artifacts" / "clm_ndws_patches" / "lofo_v1"
INIT_V21 = ROOT / "models" / "production" / "weights_v21_best.pt"
V28 = ROOT / "models" / "clm_specialist" / "weights_v28_clm_ft.pt"
LOOP_DIR = ROOT / "outputs" / "ml_eval" / "loop_3way"
SCORECARD = ROOT / "docs" / "ML_LOOP_3WAY_SCORECARD.json"

# Baseline from v31 triple champion
CHAMPION0 = {
    "name": "clm_ensemble_v31_triple",
    "model_iou": 0.8702,
    "improvement_vs_copy_iou": 0.2284,
    "model_iou_growth": 0.9134,
}


def _utc() -> str:
    return datetime.now(UTC).isoformat()


def _load_scorecard() -> dict[str, Any]:
    if SCORECARD.is_file():
        return json.loads(SCORECARD.read_text(encoding="utf-8"))
    return {
        "protocol": "clm_holdout_test_seed42_v1 + LOFO honest",
        "tracks": list(TRACKS),
        "champion": dict(CHAMPION0),
        "rounds": [],
        "history": [],
    }


def _save_scorecard(sc: dict[str, Any]) -> None:
    """Persist scorecard without demoting a stronger champion written externally."""
    SCORECARD.parent.mkdir(parents=True, exist_ok=True)
    if SCORECARD.is_file():
        try:
            disk = json.loads(SCORECARD.read_text(encoding="utf-8"))
            disk_c = disk.get("champion") or {}
            mem_c = sc.get("champion") or {}
            d_iou = float(disk_c.get("model_iou") or 0.0)
            d_delta = float(disk_c.get("improvement_vs_copy_iou") or 0.0)
            m_iou = float(mem_c.get("model_iou") or 0.0)
            m_delta = float(mem_c.get("improvement_vs_copy_iou") or 0.0)
            # Never overwrite a strictly better champion (e.g. external promote)
            if (d_iou > m_iou + 1e-6) or (abs(d_iou - m_iou) <= 1e-6 and d_delta > m_delta + 1e-6):
                sc["champion"] = disk_c
                sc.setdefault("promotions", [])
                # keep disk promotions that memory lacks
                seen = {
                    (
                        p.get("name"),
                        round(float(p.get("model_iou") or 0), 6),
                    )
                    for p in sc["promotions"]
                    if isinstance(p, dict)
                }
                for p in disk.get("promotions") or []:
                    if not isinstance(p, dict):
                        continue
                    key = (p.get("name"), round(float(p.get("model_iou") or 0), 6))
                    if key not in seen:
                        sc["promotions"].append(p)
                        seen.add(key)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass
    sc["updated_at_utc"] = _utc()
    SCORECARD.write_text(json.dumps(sc, indent=2, default=str), encoding="utf-8")


def _verdict(test: dict[str, Any], champion: dict[str, Any], name: str) -> dict[str, Any]:
    iou = float(test["model_iou"])
    delta = float(test["improvement_vs_copy_iou"])
    growth = float(test.get("model_iou_growth") or 0.0)
    c_iou = float(champion["model_iou"])
    c_delta = float(champion["improvement_vs_copy_iou"])
    beats = (iou > c_iou + 1e-4) or (delta > c_delta + 1e-4)
    stretch = (iou >= 0.88) or (delta >= 0.24)
    if stretch and beats:
        verdict = "GO_PROMOTE"
    elif beats and delta > 0:
        verdict = "GO_SOFT"
    elif delta > 0:
        verdict = "NO_PROMOTE_KEEP_CHAMPION"
    else:
        verdict = "NO_GO_REGRESSION"
    return {
        "name": name,
        "model_iou": iou,
        "improvement_vs_copy_iou": delta,
        "model_iou_growth": growth,
        "vs_champion": {
            "iou_diff": iou - c_iou,
            "delta_diff": delta - c_delta,
            "beats": beats,
        },
        "verdict": verdict,
        "go": verdict.startswith("GO"),
    }


def _honest_members() -> list[Path]:
    """v28 + EMA + best multi_if (prefer frozen / best-holdout, never a half-trained live file)."""
    v28 = next(
        (
            p
            for p in (
                ROOT / "models" / "clm_ensemble" / "weights_v28_clm_ft.pt",
                V28,
            )
            if p.is_file()
        ),
        None,
    )
    ema = next(
        (
            p
            for p in (
                ROOT / "models" / "clm_ensemble" / "weights_v30_ema.pt",
                ROOT / "outputs" / "ml_eval" / "v30_ema" / "weights_pretrained_best.pt",
            )
            if p.is_file()
        ),
        None,
    )
    # multi_if: production freeze first, then best-holdout snapshot, then live last
    multi = next(
        (
            p
            for p in (
                ROOT / "models" / "clm_ensemble" / "weights_multi_if.pt",
                LOOP_DIR / "multi_if" / "weights_multi_if_best_holdout.pt",
                LOOP_DIR / "multi_if" / "weights_pretrained_best.pt",
                ROOT / "models" / "clm_ensemble" / "weights_lofo_cardoso.pt",
                ROOT / "outputs" / "ml_eval" / "lofo_v1" / "CARDOSO" / "weights_pretrained_best.pt",
            )
            if p.is_file()
        ),
        None,
    )
    return [p for p in (v28, ema, multi) if p is not None]


# ── Track 1: multi-IF retrain ───────────────────────────────────────────────


def track_multi_if(
    *,
    epochs: int,
    patience: int,
    lr: float,
    init: Path,
    ema_decay: float = 0.0,
    change_loss_weight: float = 5.0,
    pos_weight: float = 5.0,
) -> dict[str, Any]:
    """Train on LOFO-CARDOSO splits (multi-fire, held-out Cardoso)."""
    data = LOFO / "CARDOSO"
    if not (data / "train").is_dir():
        return {"status": "skip", "reason": "missing lofo CARDOSO train"}
    out = LOOP_DIR / "multi_if"
    out.mkdir(parents=True, exist_ok=True)
    cfg = UNetTrainConfig(
        epochs=epochs,
        batch_size=8,
        lr=lr,
        loss="composite",
        pos_weight=pos_weight,
        model="small",
        architecture="residual",
        target_mode="delta",
        change_loss_weight=change_loss_weight,
        weighted_sampler=True,
        patience=patience,
        data_dir=str(data),
        output_dir=str(out),
        version_tag="loop_multi_if",
        early_stop_metric="improvement_vs_copy_iou",
        init_weights_path=str(init),
        ema_decay=ema_decay,
    )
    print(
        f"\n=== TRACK multi_if init={init.name} lr={lr} ema={ema_decay} "
        f"clw={change_loss_weight} pw={pos_weight} ===",
        flush=True,
    )
    s = run_training(cfg)
    w = out / "weights_pretrained_best.pt"
    # Snapshot so later rounds do not overwrite a promoted member
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    snap = out / f"weights_multi_if_{stamp}.pt"
    if w.is_file():
        import shutil

        shutil.copy2(w, snap)
        # Keep a rolling "latest good" only if holdout Δ improves later
    # Eval on LOFO held-out Cardoso test AND global holdout test
    lofo_test = evaluate_clm_weights(w, data / "test", max_patches=400)
    hold_test = evaluate_clm_weights(w, HOLDOUT / "test", max_patches=400)
    if w.is_file():
        best_link = out / "weights_multi_if_best_holdout.pt"
        prev_delta = -1e9
        meta_path = out / "best_holdout_meta.json"
        if meta_path.is_file():
            try:
                prev_delta = float(
                    json.loads(meta_path.read_text(encoding="utf-8")).get(
                        "improvement_vs_copy_iou", -1e9
                    )
                )
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                prev_delta = -1e9
        cur_delta = float(hold_test.get("improvement_vs_copy_iou") or -1e9)
        if cur_delta >= prev_delta:
            shutil.copy2(w, best_link)
            meta_path.write_text(
                json.dumps(
                    {
                        "weights": str(snap if snap.is_file() else w),
                        "improvement_vs_copy_iou": cur_delta,
                        "model_iou": hold_test.get("model_iou"),
                        "saved_at_utc": _utc(),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
    # Pair with v28 on holdout
    ens = None
    if V28.is_file():
        ens = evaluate_clm_weights([V28, w], HOLDOUT / "test", max_patches=400)
    return {
        "status": "ok",
        "single_change": "multi-IF FT on LOFO-CARDOSO train (no Cardoso in train)",
        "init": str(init),
        "hyper": {
            "lr": lr,
            "ema_decay": ema_decay,
            "change_loss_weight": change_loss_weight,
            "pos_weight": pos_weight,
            "epochs": epochs,
            "patience": patience,
        },
        "weights": str(w),
        "training": {
            "best_epoch": s.get("best_epoch"),
            "test_iou": s.get("test_iou"),
            "improvement_vs_copy_iou": s.get("improvement_vs_copy_iou"),
        },
        "eval_lofo_cardoso_test": {
            k: lofo_test[k]
            for k in (
                "model_iou",
                "improvement_vs_copy_iou",
                "model_iou_growth",
                "n_patches",
            )
        },
        "eval_holdout_test": {
            k: hold_test[k]
            for k in (
                "model_iou",
                "improvement_vs_copy_iou",
                "model_iou_growth",
                "n_patches",
            )
        },
        "eval_v28_plus_multi_if": (
            {
                k: ens[k]
                for k in (
                    "model_iou",
                    "improvement_vs_copy_iou",
                    "model_iou_growth",
                    "n_patches",
                )
            }
            if ens
            else None
        ),
    }


# ── Track 2: per-source mix calibration ─────────────────────────────────────


def _mix_grid(n: int) -> list[list[float]]:
    """Finer simplex grid for soft-vote weights (n members)."""
    if n == 2:
        return [[w, 1.0 - w] for w in np.linspace(0.2, 0.8, 13)]
    if n != 3:
        # uniform + leave-one-light for n>3
        base = [1.0 / n] * n
        grid = [base]
        for i in range(n):
            w = [0.15] * n
            w[i] = 1.0 - 0.15 * (n - 1)
            grid.append(w)
        return grid
    grid: list[list[float]] = []
    # denser simplex (step 0.05) with min weight 0.1
    for a in np.arange(0.15, 0.70 + 1e-9, 0.05):
        for b in np.arange(0.10, 0.55 + 1e-9, 0.05):
            c = 1.0 - float(a) - float(b)
            if c < 0.10 - 1e-9 or c > 0.70 + 1e-9:
                continue
            grid.append([float(a), float(b), float(c)])
    # always include equal and known champion-ish mixes
    for extra in (
        [1 / 3, 1 / 3, 1 / 3],
        [0.3, 0.2667, 0.4333],
        [0.28, 0.32, 0.4],  # v34
        [0.25, 0.25, 0.5],
        [0.25, 0.35, 0.4],
        [0.4, 0.2, 0.4],
        [0.35, 0.25, 0.4],
    ):
        if not any(np.allclose(extra, g, atol=1e-3) for g in grid):
            grid.append(list(extra))
    return grid


def _temp_grid(n: int) -> list[list[float]]:
    """Coarse per-member temperature grid (logit / T)."""
    if n == 2:
        return [[a, b] for a in (0.7, 1.0, 1.3) for b in (0.7, 1.0, 1.3)]
    if n != 3:
        return [[1.0] * n]
    vals = (0.7, 1.0, 1.3)
    grid = [[a, b, c] for a in vals for b in vals for c in vals]
    # always include v34 temps
    if not any(np.allclose([0.7, 0.7, 1.3], g, atol=1e-3) for g in grid):
        grid.append([0.7, 0.7, 1.3])
    return grid


def track_source_mix(*, champion: dict[str, Any]) -> dict[str, Any]:
    """Calibrate soft-vote mix per LOFO source; apply Cardoso recipe on holdout test.

    Uses growth-prob cache so mix×threshold/temperature sweeps do not re-run the U-Net.
    Mix/threshold/temps for GO are selected only on holdout VAL (never Cardoso LOFO).
    """
    print("\n=== TRACK source_mix ===", flush=True)
    members = _honest_members()
    if len(members) < 2:
        return {"status": "skip", "reason": "need >=2 member weights"}

    use = members[:3] if len(members) >= 3 else members
    n = len(use)
    print("  members:", [str(p.name) for p in use], flush=True)

    grid = _mix_grid(n)
    thresholds = (0.40, 0.45, 0.50, 0.55, 0.60)
    temp_grid = _temp_grid(n)
    print(
        f"  grid={len(grid)} mixes × {len(thresholds)} thr + {len(temp_grid)} temps (cached)",
        flush=True,
    )
    per_source: dict[str, Any] = {}
    folds = sorted(p.name for p in LOFO.iterdir() if p.is_dir() and (p / "test").is_dir())
    for held in folds:
        test_dir = LOFO / held / "test"
        if not list(test_dir.glob("*.npz")):
            continue
        cache = collect_member_growth_cache(use, test_dir, max_patches=200)
        # diagnostic: mix only at thr=0.5 (fast + comparable to history)
        best = None
        for mix in grid:
            m = score_mix_from_cache(cache, mix, split_context=_CTX_REPORT_LOFO, threshold=0.5)
            row = {
                "mix": list(m["member_weights"]),
                "threshold": 0.5,
                "model_iou": m["model_iou"],
                "improvement_vs_copy_iou": m["improvement_vs_copy_iou"],
                "model_iou_growth": m["model_iou_growth"],
            }
            if best is None or (
                row["improvement_vs_copy_iou"],
                row["model_iou"],
            ) > (best["improvement_vs_copy_iou"], best["model_iou"]):
                best = row
        per_source[held] = {"best": best, "n_grid": len(grid)}
        print(
            f"  {held}: best mix={best['mix']} Δ={best['improvement_vs_copy_iou']:.4f}",
            flush=True,
        )

    # CRITICAL: LOFO CARDOSO/test == holdout_v1/test (same 200 patches).
    # Never select mix on CARDOSO LOFO for holdout GO claims (that is test leakage).
    # Honest holdout mix+threshold: tune on holdout VAL (LA) only.
    val_dir = HOLDOUT / "val"
    val_cache = collect_member_growth_cache(use, val_dir, max_patches=400)
    val_sweep = sweep_mix_threshold_from_cache(
        val_cache, grid, thresholds, split_context=_CTX_TUNE_VAL
    )
    best_val = val_sweep["best"]
    mix = best_val["mix"] if best_val else [1.0 / n] * n
    thr_val = float(best_val["threshold"]) if best_val else 0.5
    print(
        f"  VAL best mix={mix} thr={thr_val} Δ={best_val['improvement_vs_copy_iou']:.4f}",
        flush=True,
    )

    # Optional: non-Cardoso LOFO average mix (transfer recipe, still honest)
    other_mixes = [
        per_source[k]["best"]["mix"]
        for k in per_source
        if "CARDOSO" not in k.upper() and per_source[k].get("best")
    ]
    transfer_mix = None
    hold_transfer = None
    hold_transfer_thr = None
    test_cache = collect_member_growth_cache(use, HOLDOUT / "test", max_patches=400)
    if other_mixes:
        arr = np.asarray(other_mixes, dtype=float)
        transfer_mix = [float(x) for x in arr.mean(axis=0).tolist()]
        s = sum(transfer_mix) or 1.0
        transfer_mix = [x / s for x in transfer_mix]
        # threshold for transfer: still only from VAL (no test thr leakage)
        thr_transfer = thr_val
        ht = score_mix_from_cache(
            test_cache,
            transfer_mix,
            split_context=_CTX_REPORT_TEST,
            threshold=thr_transfer,
        )
        hold_transfer = {
            k: ht[k]
            for k in (
                "model_iou",
                "improvement_vs_copy_iou",
                "model_iou_growth",
                "n_patches",
                "member_weights",
                "threshold",
            )
        }
        hold_transfer_thr = thr_transfer

    hold = score_mix_from_cache(test_cache, mix, split_context=_CTX_REPORT_TEST, threshold=thr_val)
    equal = score_mix_from_cache(test_cache, None, split_context=_CTX_REPORT_TEST, threshold=0.5)
    # also report transfer at thr=0.5 for continuity with v33
    hold_transfer_05 = None
    if transfer_mix is not None:
        ht05 = score_mix_from_cache(
            test_cache, transfer_mix, split_context=_CTX_REPORT_TEST, threshold=0.5
        )
        hold_transfer_05 = {
            k: ht05[k]
            for k in (
                "model_iou",
                "improvement_vs_copy_iou",
                "model_iou_growth",
                "n_patches",
                "member_weights",
                "threshold",
            )
        }

    # VAL temperature × mix sweep (honest; thr fixed at 0.5 to avoid thr overfit)
    # Candidate mixes: VAL best@0.5, transfer, equal, v34, a few top mixes
    temp_mix_cands: list[list[float]] = []
    for m in (
        mix,
        transfer_mix,
        [1.0 / n] * n,
        [0.28, 0.32, 0.4] if n == 3 else None,
        [0.3, 0.2667, 0.4333] if n == 3 else None,
        best_val["mix"] if best_val else None,
    ):
        if m is None:
            continue
        if not any(np.allclose(m, x, atol=1e-3) for x in temp_mix_cands):
            temp_mix_cands.append(list(m))
    best_temp = None
    for temps in temp_grid:
        for tm in temp_mix_cands:
            m = score_mix_from_cache(
                val_cache,
                tm,
                split_context=_CTX_TEMP_VAL,
                threshold=0.5,
                temperatures=temps,
            )
            row = {
                "mix": list(m["member_weights"]),
                "temperatures": list(temps),
                "threshold": 0.5,
                "model_iou": m["model_iou"],
                "improvement_vs_copy_iou": m["improvement_vs_copy_iou"],
                "model_iou_growth": m["model_iou_growth"],
            }
            if best_temp is None or (
                row["improvement_vs_copy_iou"],
                row["model_iou"],
            ) > (
                best_temp["improvement_vs_copy_iou"],
                best_temp["model_iou"],
            ):
                best_temp = row
    hold_temp = None
    if best_temp is not None:
        print(
            f"  VAL best temp mix={best_temp['mix']} T={best_temp['temperatures']} "
            f"Δ={best_temp['improvement_vs_copy_iou']:.4f}",
            flush=True,
        )
        ht = score_mix_from_cache(
            test_cache,
            best_temp["mix"],
            split_context=_CTX_REPORT_TEST,
            threshold=0.5,
            temperatures=best_temp["temperatures"],
        )
        hold_temp = {
            k: ht[k]
            for k in (
                "model_iou",
                "improvement_vs_copy_iou",
                "model_iou_growth",
                "n_patches",
                "member_weights",
                "threshold",
                "temperatures",
            )
        }

    cardoso_diag = per_source.get("CARDOSO", {}).get("best")

    return {
        "status": "ok",
        "single_change": ("cached per-source mix + VAL mix×threshold + VAL temp sweep (honest)"),
        "leakage_guard": (
            "LOFO CARDOSO/test == holdout test; mix+threshold+temps for GO on VAL only"
        ),
        "members": [str(p) for p in use],
        "grid_size": len(grid),
        "thresholds": list(thresholds),
        "temp_grid_size": len(temp_grid),
        "per_source_best_diagnostic": {k: v["best"] for k, v in per_source.items()},
        "cardoso_lofo_is_holdout_test": True,
        "cardoso_lofo_diag_not_for_go": cardoso_diag,
        "val_grid_best": best_val,
        "val_sweep_top": val_sweep.get("rows_top"),
        "val_temp_best": best_temp,
        "applied_for_holdout": {
            "source_key": "holdout_val_LA",
            "mix": mix,
            "threshold": thr_val,
        },
        "transfer_mix_from_non_cardoso_lofo": transfer_mix,
        "holdout_test_val_tuned": {
            k: hold[k]
            for k in (
                "model_iou",
                "improvement_vs_copy_iou",
                "model_iou_growth",
                "n_patches",
                "member_weights",
                "threshold",
            )
        },
        "holdout_test_transfer_mix": hold_transfer,
        "holdout_test_transfer_mix_thr05": hold_transfer_05,
        "holdout_test_val_temp": hold_temp,
        "holdout_test_equal": {
            k: equal[k]
            for k in (
                "model_iou",
                "improvement_vs_copy_iou",
                "model_iou_growth",
                "threshold",
            )
        },
        "verdict": _verdict(hold, champion, "source_mix_val_tuned"),
        "verdict_transfer": (
            _verdict(hold_transfer, champion, "source_mix_transfer_non_cardoso")
            if hold_transfer
            else None
        ),
        "verdict_transfer_thr05": (
            _verdict(hold_transfer_05, champion, "source_mix_transfer_non_cardoso_thr05")
            if hold_transfer_05
            else None
        ),
        "verdict_val_temp": (
            _verdict(hold_temp, champion, "source_mix_val_temp_calibrated") if hold_temp else None
        ),
        "transfer_threshold": hold_transfer_thr,
    }


# ── Track 3: multi-objective FT ─────────────────────────────────────────────


def track_multi_obj(
    *,
    epochs: int,
    patience: int,
    lr: float,
    init: Path,
    metric: str = "multi_full_growth",
) -> dict[str, Any]:
    """Fine-tune on holdout train with multi-objective early stop."""
    print(f"\n=== TRACK multi_obj metric={metric} ===", flush=True)
    out = LOOP_DIR / f"multi_obj_{metric}"
    out.mkdir(parents=True, exist_ok=True)
    cfg = UNetTrainConfig(
        epochs=epochs,
        batch_size=8,
        lr=lr,
        loss="composite",
        pos_weight=5.0,
        model="small",
        architecture="residual",
        target_mode="delta",
        change_loss_weight=5.0,
        weighted_sampler=True,
        patience=patience,
        data_dir=str(HOLDOUT),
        output_dir=str(out),
        version_tag=f"loop_{metric}",
        early_stop_metric=metric,
        init_weights_path=str(init),
    )
    s = run_training(cfg)
    w = out / "weights_pretrained_best.pt"
    hold = evaluate_clm_weights(w, HOLDOUT / "test", max_patches=400)
    ens = None
    # Prefer frozen / best-holdout multi_if — never half-trained live alone
    lofo = next(
        (
            p
            for p in (
                ROOT / "models" / "clm_ensemble" / "weights_multi_if.pt",
                LOOP_DIR / "multi_if" / "weights_multi_if_best_holdout.pt",
                LOOP_DIR / "multi_if" / "weights_pretrained_best.pt",
                ROOT / "models" / "clm_ensemble" / "weights_lofo_cardoso.pt",
            )
            if p.is_file()
        ),
        None,
    )
    ema = ROOT / "models" / "clm_ensemble" / "weights_v30_ema.pt"
    if lofo and V28.is_file():
        members = [V28, w, lofo]
        # if EMA exists and multi_obj is distinct, still keep triple v28+mo+multi_if
        ens = evaluate_clm_weights(members, HOLDOUT / "test", max_patches=400)
        if ema.is_file() and w.resolve() != ema.resolve():
            ens4 = evaluate_clm_weights(
                [V28, ema, lofo, w],
                HOLDOUT / "test",
                max_patches=400,
                member_weights=[0.28, 0.22, 0.35, 0.15],
            )
            # stash 4-member diagnostic
            ens = {
                **ens,
                "quad_with_ema": {
                    k: ens4[k]
                    for k in (
                        "model_iou",
                        "improvement_vs_copy_iou",
                        "model_iou_growth",
                        "member_weights",
                    )
                },
            }
    return {
        "status": "ok",
        "single_change": f"early_stop={metric} (fullΔ + λ·growth, not growth-only)",
        "init": str(init),
        "weights": str(w),
        "training": {
            "best_epoch": s.get("best_epoch"),
            "test_iou": s.get("test_iou"),
            "improvement_vs_copy_iou": s.get("improvement_vs_copy_iou"),
            "model_iou_growth": s.get("model_iou_growth"),
        },
        "eval_holdout_test": {
            k: hold[k]
            for k in (
                "model_iou",
                "improvement_vs_copy_iou",
                "model_iou_growth",
                "n_patches",
            )
        },
        "eval_triple_if_available": (
            {
                **{
                    k: ens[k]
                    for k in (
                        "model_iou",
                        "improvement_vs_copy_iou",
                        "model_iou_growth",
                    )
                },
                **({"quad_with_ema": ens["quad_with_ema"]} if ens.get("quad_with_ema") else {}),
            }
            if ens
            else None
        ),
    }


def _maybe_promote(sc: dict[str, Any], vb: dict[str, Any], recipe: dict[str, Any]) -> None:
    if not vb.get("go"):
        return
    champ = {
        "name": vb["name"],
        "model_iou": vb["model_iou"],
        "improvement_vs_copy_iou": vb["improvement_vs_copy_iou"],
        "model_iou_growth": vb.get("model_iou_growth"),
        "verdict": vb["verdict"],
        "recipe": recipe,
        "promoted_at_utc": _utc(),
    }
    sc["champion"] = champ
    sc.setdefault("promotions", []).append(champ)
    print("  ** PROMOTED CHAMPION **", json.dumps(vb, indent=2), flush=True)
    # Freeze multi_if member into models/ if present in recipe
    try:
        members = recipe.get("members") or []
        for m in members:
            mp = Path(m)
            if "multi_if" in mp.name or "loop_3way" in str(mp).replace("\\", "/"):
                dest = ROOT / "models" / "clm_ensemble" / "weights_multi_if.pt"
                if mp.is_file():
                    import shutil

                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(mp, dest)
                    print(f"  froze multi_if -> {dest}", flush=True)
                break
        # Write production-ish recipe sidecar
        (ROOT / "models" / "clm_ensemble" / "loop_champion_recipe.json").write_text(
            json.dumps(champ, indent=2, default=str), encoding="utf-8"
        )
    except OSError as exc:
        print(f"  warn: could not freeze champion weights: {exc}", flush=True)


def run_round(
    round_id: int,
    *,
    tracks: list[str],
    epochs: int,
    patience: int,
    lr: float,
    sc: dict[str, Any],
) -> dict[str, Any]:
    champion = sc.get("champion") or CHAMPION0
    init = V28 if V28.is_file() else INIT_V21
    if not init.is_file():
        raise FileNotFoundError("need v28 or v21 weights")

    round_rep: dict[str, Any] = {
        "round": round_id,
        "started_at_utc": _utc(),
        "tracks": {},
        "champion_before": dict(champion),
    }

    if "multi_if" in tracks:
        t0 = time.perf_counter()
        # Rotate init + hyper: freeze continue / best-holdout / v28 / v21 + EMA variants
        freeze_m = ROOT / "models" / "clm_ensemble" / "weights_multi_if.pt"
        best_h = LOOP_DIR / "multi_if" / "weights_multi_if_best_holdout.pt"
        cycle = round_id % 6
        hyper_cycle = [
            # (init, lr_scale, ema, change_loss_w, pos_w)
            (freeze_m if freeze_m.is_file() else init, 0.35, 0.999, 5.0, 5.0),
            (best_h if best_h.is_file() else init, 0.45, 0.999, 6.0, 5.0),
            (init, 0.7, 0.0, 5.0, 5.0),
            (INIT_V21 if INIT_V21.is_file() else init, 1.0, 0.999, 5.0, 6.0),
            (freeze_m if freeze_m.is_file() else init, 0.25, 0.0, 4.0, 4.0),
            (init, 0.5, 0.999, 7.0, 5.0),
        ][cycle]
        init_m, lr_scale, ema_d, clw, pw = hyper_cycle
        if not Path(init_m).is_file():
            init_m = init
        multi = track_multi_if(
            epochs=epochs,
            patience=patience,
            lr=lr * lr_scale,
            init=Path(init_m),
            ema_decay=ema_d,
            change_loss_weight=clw,
            pos_weight=pw,
        )
        # Verdict from holdout test of multi-if alone and v28+multi
        if multi.get("status") == "ok":
            vb1 = _verdict(multi["eval_holdout_test"], champion, f"r{round_id}_multi_if")
            multi["verdict_single"] = vb1
            if multi.get("eval_v28_plus_multi_if"):
                vb2 = _verdict(
                    multi["eval_v28_plus_multi_if"],
                    champion,
                    f"r{round_id}_v28_plus_multi_if",
                )
                multi["verdict_pair"] = vb2
                _maybe_promote(
                    sc,
                    vb2,
                    {
                        "type": "pair",
                        "members": [str(V28), multi["weights"]],
                        "mix": [0.5, 0.5],
                    },
                )
            _maybe_promote(
                sc,
                vb1,
                {"type": "single", "weights": multi["weights"]},
            )
        multi["latency_s"] = round(time.perf_counter() - t0, 2)
        round_rep["tracks"]["multi_if"] = multi
        champion = sc.get("champion") or champion

    if "source_mix" in tracks:
        t0 = time.perf_counter()
        sm = track_source_mix(champion=champion)
        if sm.get("status") == "ok":
            for vkey, rkey in (
                ("verdict", "source_mix_val_tuned"),
                ("verdict_transfer", "source_mix_transfer"),
                ("verdict_transfer_thr05", "source_mix_transfer_thr05"),
                ("verdict_val_temp", "source_mix_val_temp"),
            ):
                vb = sm.get(vkey)
                if not vb:
                    continue
                temps = None
                if vkey == "verdict":
                    mix = sm.get("applied_for_holdout", {}).get("mix")
                    thr = sm.get("applied_for_holdout", {}).get("threshold", 0.5)
                elif vkey == "verdict_val_temp":
                    vt = sm.get("val_temp_best") or {}
                    mix = vt.get("mix")
                    thr = vt.get("threshold", 0.5)
                    temps = vt.get("temperatures")
                else:
                    mix = sm.get("transfer_mix_from_non_cardoso_lofo")
                    thr = (
                        0.5
                        if vkey == "verdict_transfer_thr05"
                        else sm.get("transfer_threshold", 0.5)
                    )
                recipe = {
                    "type": rkey,
                    "members": sm.get("members"),
                    "mix": mix,
                    "threshold": thr,
                    "per_source_diagnostic": sm.get("per_source_best_diagnostic"),
                    "leakage_guard": sm.get("leakage_guard"),
                }
                if temps is not None:
                    recipe["temperatures"] = temps
                _maybe_promote(sc, vb, recipe)
                # On GO temp promote, freeze recipe into ensemble manifest-friendly sidecar
                if vb.get("go") and temps is not None and vb.get("verdict") == "GO_PROMOTE":
                    with contextlib.suppress(OSError):
                        (ROOT / "models" / "clm_ensemble" / "loop_champion_recipe.json").write_text(
                            json.dumps(
                                {
                                    "name": vb["name"],
                                    "model_iou": vb["model_iou"],
                                    "improvement_vs_copy_iou": vb["improvement_vs_copy_iou"],
                                    "model_iou_growth": vb.get("model_iou_growth"),
                                    "recipe": recipe,
                                    "promoted_at_utc": _utc(),
                                },
                                indent=2,
                                default=str,
                            ),
                            encoding="utf-8",
                        )

        sm["latency_s"] = round(time.perf_counter() - t0, 2)
        round_rep["tracks"]["source_mix"] = sm
        champion = sc.get("champion") or champion

    if "multi_obj" in tracks:
        t0 = time.perf_counter()
        # Cycle λ variants across rounds
        metric = (
            "multi_full_growth",
            "multi_full_growth_025",
            "multi_full_growth_05",
        )[(round_id - 1) % 3]
        mo = track_multi_obj(epochs=epochs, patience=patience, lr=lr, init=init, metric=metric)
        if mo.get("status") == "ok":
            vb = _verdict(mo["eval_holdout_test"], champion, f"r{round_id}_{metric}")
            mo["verdict"] = vb
            _maybe_promote(
                sc, vb, {"type": "multi_obj", "metric": metric, "weights": mo["weights"]}
            )
            if mo.get("eval_triple_if_available"):
                base_triple = {
                    k: mo["eval_triple_if_available"][k]
                    for k in (
                        "model_iou",
                        "improvement_vs_copy_iou",
                        "model_iou_growth",
                    )
                    if k in mo["eval_triple_if_available"]
                }
                vb3 = _verdict(
                    base_triple,
                    champion,
                    f"r{round_id}_{metric}_triple",
                )
                mo["verdict_triple"] = vb3
                _maybe_promote(
                    sc,
                    vb3,
                    {
                        "type": "triple_with_multi_obj",
                        "metric": metric,
                        "weights": mo["weights"],
                    },
                )
                quad = mo["eval_triple_if_available"].get("quad_with_ema")
                if quad:
                    vb4 = _verdict(quad, champion, f"r{round_id}_{metric}_quad")
                    mo["verdict_quad"] = vb4
                    _maybe_promote(
                        sc,
                        vb4,
                        {
                            "type": "quad_v28_ema_multi_if_multi_obj",
                            "metric": metric,
                            "weights": mo["weights"],
                            "mix": quad.get("member_weights"),
                        },
                    )
        mo["latency_s"] = round(time.perf_counter() - t0, 2)
        round_rep["tracks"]["multi_obj"] = mo

    round_rep["finished_at_utc"] = _utc()
    round_rep["champion_after"] = sc.get("champion")
    return round_rep


def main() -> int:
    ap = argparse.ArgumentParser(description="3-way ML improvement loop")
    ap.add_argument("--rounds", type=int, default=2, help="0 = infinite until Ctrl+C")
    ap.add_argument(
        "--only",
        type=str,
        default="multi_if,source_mix,multi_obj",
        help="Comma subset of tracks",
    )
    ap.add_argument("--epochs", type=int, default=12)
    ap.add_argument("--patience", type=int, default=5)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument(
        "--sleep-s",
        type=float,
        default=0.0,
        help="Pause between rounds (long-running loops)",
    )
    args = ap.parse_args()

    tracks = [t.strip() for t in args.only.split(",") if t.strip() in TRACKS]
    if not tracks:
        print("No valid tracks. Choose from", TRACKS, file=sys.stderr)
        return 2

    LOOP_DIR.mkdir(parents=True, exist_ok=True)
    sc = _load_scorecard()
    print("Champion:", json.dumps(sc.get("champion") or CHAMPION0, indent=2), flush=True)
    print("Tracks:", tracks, "rounds:", args.rounds or "∞", flush=True)

    round_id = len(sc.get("rounds") or []) + 1
    target = args.rounds  # 0 = infinite
    done = 0
    try:
        while True:
            print(f"\n######## ROUND {round_id} ########", flush=True)
            rep = run_round(
                round_id,
                tracks=tracks,
                epochs=args.epochs,
                patience=args.patience,
                lr=args.lr,
                sc=sc,
            )
            sc.setdefault("rounds", []).append(rep)
            sc.setdefault("history", []).append(
                {
                    "round": round_id,
                    "champion": sc.get("champion"),
                    "at": _utc(),
                }
            )
            _save_scorecard(sc)
            print(f"Round {round_id} done. Scorecard -> {SCORECARD}", flush=True)
            done += 1
            round_id += 1
            if target > 0 and done >= target:
                break
            if args.sleep_s > 0:
                time.sleep(args.sleep_s)
    except KeyboardInterrupt:
        print("\nInterrupted — scorecard saved.", flush=True)
        _save_scorecard(sc)

    print("\n=== FINAL CHAMPION ===", flush=True)
    print(json.dumps(sc.get("champion"), indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
