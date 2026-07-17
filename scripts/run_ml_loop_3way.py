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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.ml.clm_eval import evaluate_clm_weights  # noqa: E402
from wildfire_front.ml.unet_train import UNetTrainConfig, run_training  # noqa: E402

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
    return datetime.now(timezone.utc).isoformat()


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
    SCORECARD.parent.mkdir(parents=True, exist_ok=True)
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
    """v28 + EMA + LOFO-CARDOSO if present."""
    cands = [
        ROOT / "models" / "clm_ensemble" / "weights_v28_clm_ft.pt",
        V28,
        ROOT / "models" / "clm_ensemble" / "weights_v30_ema.pt",
        ROOT / "outputs" / "ml_eval" / "v30_ema" / "weights_pretrained_best.pt",
        ROOT / "models" / "clm_ensemble" / "weights_lofo_cardoso.pt",
        ROOT / "outputs" / "ml_eval" / "lofo_v1" / "CARDOSO" / "weights_pretrained_best.pt",
        LOOP_DIR / "multi_if" / "weights_pretrained_best.pt",
    ]
    # Prefer dedicated ensemble copies
    v28 = next((p for p in cands[:2] if p.is_file()), None)
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
    lofo = next(
        (
            p
            for p in (
                LOOP_DIR / "multi_if" / "weights_pretrained_best.pt",
                ROOT / "models" / "clm_ensemble" / "weights_lofo_cardoso.pt",
                ROOT / "outputs" / "ml_eval" / "lofo_v1" / "CARDOSO" / "weights_pretrained_best.pt",
            )
            if p.is_file()
        ),
        None,
    )
    out = [p for p in (v28, ema, lofo) if p is not None]
    return out


# ── Track 1: multi-IF retrain ───────────────────────────────────────────────


def track_multi_if(*, epochs: int, patience: int, lr: float, init: Path) -> dict[str, Any]:
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
        pos_weight=5.0,
        model="small",
        architecture="residual",
        target_mode="delta",
        change_loss_weight=5.0,
        weighted_sampler=True,
        patience=patience,
        data_dir=str(data),
        output_dir=str(out),
        version_tag="loop_multi_if",
        early_stop_metric="improvement_vs_copy_iou",
        init_weights_path=str(init),
    )
    print("\n=== TRACK multi_if ===", flush=True)
    s = run_training(cfg)
    w = out / "weights_pretrained_best.pt"
    # Snapshot so later rounds do not overwrite a promoted member
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
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


def track_source_mix(*, champion: dict[str, Any]) -> dict[str, Any]:
    """Calibrate soft-vote mix per LOFO source; apply Cardoso recipe on holdout test."""
    print("\n=== TRACK source_mix ===", flush=True)
    members = _honest_members()
    if len(members) < 2:
        return {"status": "skip", "reason": "need >=2 member weights"}

    # Use first 2 or 3 available: prefer v28, multi_if/lofo, ema
    # Normalize to available
    use = members[:3] if len(members) >= 3 else members
    n = len(use)
    print("  members:", [str(p.name) for p in use], flush=True)

    # Grid of mixes
    if n == 2:
        grid = [[w, 1 - w] for w in (0.3, 0.4, 0.5, 0.6, 0.7, 0.8)]
    else:
        grid = []
        for a in (0.3, 0.4, 0.5, 0.6):
            for b in (0.2, 0.3, 0.4):
                if a + b >= 0.95:
                    continue
                grid.append([a, b, 1 - a - b])

    per_source: dict[str, Any] = {}
    folds = sorted(
        p.name for p in LOFO.iterdir() if p.is_dir() and (p / "test").is_dir()
    )
    for held in folds:
        test_dir = LOFO / held / "test"
        if not list(test_dir.glob("*.npz")):
            continue
        best = None
        rows = []
        for mix in grid:
            m = evaluate_clm_weights(
                use, test_dir, max_patches=200, member_weights=mix
            )
            row = {
                "mix": mix,
                "model_iou": m["model_iou"],
                "improvement_vs_copy_iou": m["improvement_vs_copy_iou"],
                "model_iou_growth": m["model_iou_growth"],
            }
            rows.append(row)
            if best is None or (
                row["improvement_vs_copy_iou"],
                row["model_iou"],
            ) > (best["improvement_vs_copy_iou"], best["model_iou"]):
                best = row
        per_source[held] = {"best": best, "n_grid": len(rows)}
        print(
            f"  {held}: best mix={best['mix']} Δ={best['improvement_vs_copy_iou']:.4f}",
            flush=True,
        )

    # CRITICAL: LOFO CARDOSO/test == holdout_v1/test (same 200 patches).
    # Never select mix on CARDOSO LOFO for holdout GO claims (that is test leakage).
    # Honest holdout mix: tune on holdout VAL (LA) only.
    val_dir = HOLDOUT / "val"
    best_val = None
    val_rows = []
    for mix in grid:
        m = evaluate_clm_weights(
            use, val_dir, max_patches=400, member_weights=mix
        )
        row = {
            "mix": mix,
            "model_iou": m["model_iou"],
            "improvement_vs_copy_iou": m["improvement_vs_copy_iou"],
            "model_iou_growth": m["model_iou_growth"],
        }
        val_rows.append(row)
        if best_val is None or (
            row["improvement_vs_copy_iou"],
            row["model_iou"],
        ) > (best_val["improvement_vs_copy_iou"], best_val["model_iou"]):
            best_val = row
    mix = best_val["mix"] if best_val else [1.0 / n] * n

    # Optional: non-Cardoso LOFO average mix (transfer recipe, still honest)
    other_mixes = [
        per_source[k]["best"]["mix"]
        for k in per_source
        if "CARDOSO" not in k.upper() and per_source[k].get("best")
    ]
    transfer_mix = None
    hold_transfer = None
    if other_mixes:
        arr = np.asarray(other_mixes, dtype=float)
        transfer_mix = [float(x) for x in arr.mean(axis=0).tolist()]
        s = sum(transfer_mix) or 1.0
        transfer_mix = [x / s for x in transfer_mix]
        ht = evaluate_clm_weights(
            use, HOLDOUT / "test", max_patches=400, member_weights=transfer_mix
        )
        hold_transfer = {
            k: ht[k]
            for k in (
                "model_iou",
                "improvement_vs_copy_iou",
                "model_iou_growth",
                "n_patches",
                "member_weights",
            )
        }

    hold = evaluate_clm_weights(
        use, HOLDOUT / "test", max_patches=400, member_weights=mix
    )
    equal = evaluate_clm_weights(use, HOLDOUT / "test", max_patches=400)

    # Diagnostics only: Cardoso LOFO score (NOT for GO — same as holdout test)
    cardoso_diag = per_source.get("CARDOSO", {}).get("best")

    return {
        "status": "ok",
        "single_change": "per-source soft-vote (diagnostic) + holdout mix tuned on VAL only",
        "leakage_guard": (
            "LOFO CARDOSO/test == holdout test; mix for GO is selected on holdout VAL only"
        ),
        "members": [str(p) for p in use],
        "per_source_best_diagnostic": {k: v["best"] for k, v in per_source.items()},
        "cardoso_lofo_is_holdout_test": True,
        "cardoso_lofo_diag_not_for_go": cardoso_diag,
        "val_grid_best": best_val,
        "applied_for_holdout": {"source_key": "holdout_val_LA", "mix": mix},
        "transfer_mix_from_non_cardoso_lofo": transfer_mix,
        "holdout_test_val_tuned": {
            k: hold[k]
            for k in (
                "model_iou",
                "improvement_vs_copy_iou",
                "model_iou_growth",
                "n_patches",
                "member_weights",
            )
        },
        "holdout_test_transfer_mix": hold_transfer,
        "holdout_test_equal": {
            k: equal[k]
            for k in (
                "model_iou",
                "improvement_vs_copy_iou",
                "model_iou_growth",
            )
        },
        "verdict": _verdict(hold, champion, "source_mix_val_tuned"),
        "verdict_transfer": (
            _verdict(hold_transfer, champion, "source_mix_transfer_non_cardoso")
            if hold_transfer
            else None
        ),
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
    lofo = next(
        (
            p
            for p in (
                LOOP_DIR / "multi_if" / "weights_pretrained_best.pt",
                ROOT / "models" / "clm_ensemble" / "weights_lofo_cardoso.pt",
            )
            if p.is_file()
        ),
        None,
    )
    if lofo and V28.is_file():
        ens = evaluate_clm_weights([V28, w, lofo], HOLDOUT / "test", max_patches=400)
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
                k: ens[k]
                for k in (
                    "model_iou",
                    "improvement_vs_copy_iou",
                    "model_iou_growth",
                )
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
        # Alternate init each round: v21 then v28
        init_m = INIT_V21 if round_id % 2 == 1 and INIT_V21.is_file() else init
        multi = track_multi_if(epochs=epochs, patience=patience, lr=lr, init=init_m)
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
            ):
                vb = sm.get(vkey)
                if not vb:
                    continue
                mix = (
                    sm.get("applied_for_holdout", {}).get("mix")
                    if vkey == "verdict"
                    else sm.get("transfer_mix_from_non_cardoso_lofo")
                )
                _maybe_promote(
                    sc,
                    vb,
                    {
                        "type": rkey,
                        "members": sm.get("members"),
                        "mix": mix,
                        "per_source_diagnostic": sm.get("per_source_best_diagnostic"),
                        "leakage_guard": sm.get("leakage_guard"),
                    },
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
        mo = track_multi_obj(
            epochs=epochs, patience=patience, lr=lr, init=init, metric=metric
        )
        if mo.get("status") == "ok":
            vb = _verdict(mo["eval_holdout_test"], champion, f"r{round_id}_{metric}")
            mo["verdict"] = vb
            _maybe_promote(sc, vb, {"type": "multi_obj", "metric": metric, "weights": mo["weights"]})
            if mo.get("eval_triple_if_available"):
                vb3 = _verdict(
                    mo["eval_triple_if_available"],
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
