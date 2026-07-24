#!/usr/bin/env python3
"""v31 — Push CLM metrics without train-on-test leakage.

Experiments (single change each vs equal-weight v28+LOFO-CARDOSO = v30 champion):
  A) Weighted soft-vote: mix w on VAL, freeze, report TEST
  B) Decision threshold sweep on VAL, freeze, report TEST
  C) Continue fine-tune from clm_v28 (not v21) with lower LR
  D) Honest triple: v28 + EMA + LOFO-CARDOSO (equal and best weighted)

Baseline champion: equal soft-vote IoU 0.8683 / Δ +0.2265 on holdout test.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.ml.clm_eval import evaluate_clm_weights  # noqa: E402

V30 = {
    "model_iou": 0.8683,
    "improvement_vs_copy_iou": 0.2265,
    "model_iou_growth": 0.8860,
}
V28 = {
    "model_iou": 0.8382,
    "improvement_vs_copy_iou": 0.1964,
}


def _paths() -> dict[str, Path]:
    return {
        "v28": ROOT / "models" / "clm_specialist" / "weights_v28_clm_ft.pt",
        "v28_ens": ROOT / "models" / "clm_ensemble" / "weights_v28_clm_ft.pt",
        "lofo": ROOT / "models" / "clm_ensemble" / "weights_lofo_cardoso.pt",
        "ema": ROOT / "outputs" / "ml_eval" / "v30_ema" / "weights_pretrained_best.pt",
        "val": ROOT / "artifacts" / "clm_ndws_patches" / "holdout_v1" / "val",
        "test": ROOT / "artifacts" / "clm_ndws_patches" / "holdout_v1" / "test",
    }


def _pick(*cands: Path) -> Path | None:
    for p in cands:
        if p.is_file():
            return p
    return None


def _verdict(test: dict, *, name: str) -> dict:
    iou = test["model_iou"]
    delta = test["improvement_vs_copy_iou"]
    growth = test["model_iou_growth"]
    beats_v30 = (iou > V30["model_iou"] + 1e-6) or (delta > V30["improvement_vs_copy_iou"] + 1e-6)
    stretch = (iou >= 0.875) or (delta >= 0.235)
    if stretch and beats_v30:
        verdict = "GO_PROMOTE_V31"
    elif beats_v30 and delta > 0:
        verdict = "GO_SOFT_BEATS_V30"
    elif delta > V28["improvement_vs_copy_iou"]:
        verdict = "NO_PROMOTE_KEEP_V30"
    else:
        verdict = "NO_PROMOTE"
    return {
        "name": name,
        "model_iou": iou,
        "improvement_vs_copy_iou": delta,
        "model_iou_growth": growth,
        "vs_v30": {
            "iou_diff": iou - V30["model_iou"],
            "delta_diff": delta - V30["improvement_vs_copy_iou"],
            "growth_diff": growth - V30["model_iou_growth"],
            "beats_v30": beats_v30,
        },
        "verdict": verdict,
        "go": verdict.startswith("GO"),
    }


def exp_weighted_pair(v28: Path, lofo: Path, val: Path, test: Path) -> dict:
    """Tune mix weight of v28 vs LOFO on VAL; evaluate on TEST."""
    grid = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    val_rows = []
    for w28 in grid:
        mix = [w28, 1.0 - w28]
        m = evaluate_clm_weights([v28, lofo], val, max_patches=400, member_weights=mix)
        val_rows.append(
            {
                "w_v28": w28,
                "w_lofo": 1.0 - w28,
                "model_iou": m["model_iou"],
                "improvement_vs_copy_iou": m["improvement_vs_copy_iou"],
                "model_iou_growth": m["model_iou_growth"],
            }
        )
    best = max(val_rows, key=lambda r: (r["improvement_vs_copy_iou"], r["model_iou"]))
    mix = [best["w_v28"], best["w_lofo"]]
    test_m = evaluate_clm_weights([v28, lofo], test, max_patches=400, member_weights=mix)
    equal = evaluate_clm_weights([v28, lofo], test, max_patches=400)
    out = {
        "single_change": "weighted soft-vote tuned on VAL (w_v28 grid)",
        "val_grid": val_rows,
        "best_on_val": best,
        "test_weighted": test_m,
        "test_equal_weight": {
            "model_iou": equal["model_iou"],
            "improvement_vs_copy_iou": equal["improvement_vs_copy_iou"],
            "model_iou_growth": equal["model_iou_growth"],
        },
        "member_weights_applied": mix,
    }
    out["verdict_block"] = _verdict(test_m, name="v31_weighted_pair")
    return out


def exp_threshold(v28: Path, lofo: Path, val: Path, test: Path, mix: list[float]) -> dict:
    thr_grid = [0.35, 0.4, 0.45, 0.5, 0.55, 0.6]
    val_rows = []
    for thr in thr_grid:
        m = evaluate_clm_weights(
            [v28, lofo], val, max_patches=400, threshold=thr, member_weights=mix
        )
        val_rows.append(
            {
                "threshold": thr,
                "model_iou": m["model_iou"],
                "improvement_vs_copy_iou": m["improvement_vs_copy_iou"],
                "model_iou_growth": m["model_iou_growth"],
            }
        )
    best = max(val_rows, key=lambda r: (r["improvement_vs_copy_iou"], r["model_iou"]))
    thr = float(best["threshold"])
    test_m = evaluate_clm_weights(
        [v28, lofo], test, max_patches=400, threshold=thr, member_weights=mix
    )
    base = evaluate_clm_weights(
        [v28, lofo], test, max_patches=400, threshold=0.5, member_weights=mix
    )
    out = {
        "single_change": "decision threshold tuned on VAL (mix fixed)",
        "mix": mix,
        "val_grid": val_rows,
        "best_on_val": best,
        "test_tuned_threshold": test_m,
        "test_thr_0_5": {
            "model_iou": base["model_iou"],
            "improvement_vs_copy_iou": base["improvement_vs_copy_iou"],
        },
    }
    out["verdict_block"] = _verdict(test_m, name="v31_threshold")
    return out


def exp_triple(v28: Path, ema: Path | None, lofo: Path, val: Path, test: Path) -> dict:
    if ema is None or not ema.is_file():
        return {"skipped": True, "reason": "ema weights missing"}
    members = [v28, ema, lofo]
    equal = evaluate_clm_weights(members, test, max_patches=400)
    # small mix grid on val: w_v28, w_ema, rest lofo
    val_rows = []
    for w28 in (0.4, 0.5, 0.6):
        for w_ema in (0.2, 0.3, 0.4):
            if w28 + w_ema >= 0.95:
                continue
            mix = [w28, w_ema, 1.0 - w28 - w_ema]
            m = evaluate_clm_weights(members, val, max_patches=400, member_weights=mix)
            val_rows.append(
                {
                    "mix": mix,
                    "model_iou": m["model_iou"],
                    "improvement_vs_copy_iou": m["improvement_vs_copy_iou"],
                }
            )
    best = max(val_rows, key=lambda r: (r["improvement_vs_copy_iou"], r["model_iou"]))
    test_w = evaluate_clm_weights(members, test, max_patches=400, member_weights=best["mix"])
    out = {
        "single_change": "honest triple soft-vote (v28+EMA+LOFO-CARDOSO)",
        "test_equal": {
            "model_iou": equal["model_iou"],
            "improvement_vs_copy_iou": equal["improvement_vs_copy_iou"],
            "model_iou_growth": equal["model_iou_growth"],
        },
        "best_on_val": best,
        "test_weighted": test_w,
    }
    out["verdict_equal"] = _verdict(equal, name="v31_triple_equal")
    out["verdict_weighted"] = _verdict(test_w, name="v31_triple_weighted")
    return out


def exp_continue_ft(v28: Path, data: Path, epochs: int, patience: int) -> dict:
    from wildfire_front.ml.clm_eval import evaluate_clm_weights as ev
    from wildfire_front.ml.unet_train import UNetTrainConfig, run_training

    out_dir = ROOT / "outputs" / "ml_eval" / "v31_continue_v28"
    cfg = UNetTrainConfig(
        epochs=epochs,
        batch_size=8,
        lr=1e-4,
        loss="composite",
        pos_weight=5.0,
        model="small",
        architecture="residual",
        target_mode="delta",
        change_loss_weight=5.0,
        weighted_sampler=True,
        patience=patience,
        data_dir=str(data),
        output_dir=str(out_dir),
        version_tag="v31_continue_v28",
        early_stop_metric="improvement_vs_copy_iou",
        init_weights_path=str(v28),
        ema_decay=0.0,
    )
    print("=" * 70)
    print("TRAIN v31_continue_v28  init=v28  lr=1e-4")
    print("=" * 70)
    summary = run_training(cfg)
    w = out_dir / "weights_pretrained_best.pt"
    test = ev(w, data / "test", max_patches=400)
    # honest ensemble with new weights + LOFO
    p = _paths()
    lofo = _pick(
        p["lofo"],
        ROOT / "outputs" / "ml_eval" / "lofo_v1" / "CARDOSO" / "weights_pretrained_best.pt",
    )
    ens = None
    if lofo:
        ens = evaluate_clm_weights([w, lofo], data / "test", max_patches=400)
    report = {
        "single_change": "continue FT from clm_v28 weights (lr=1e-4), not from v21",
        "training_summary": {
            "test_iou": summary.get("test_iou"),
            "improvement_vs_copy_iou": summary.get("improvement_vs_copy_iou"),
            "model_iou_growth": summary.get("model_iou_growth"),
            "best_epoch": summary.get("best_epoch"),
        },
        "holdout_test": test,
        "with_lofo_equal": ens,
        "weights": str(w),
    }
    report["verdict_single"] = _verdict(test, name="v31_continue_v28")
    if ens:
        report["verdict_ens"] = _verdict(ens, name="v31_continue_v28+lofo")
    (out_dir / "v31_continue_verdict.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--only",
        default="weighted,threshold,triple",
        help="Comma: weighted,threshold,triple,continue_ft  or all",
    )
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--patience", type=int, default=5)
    args = ap.parse_args()
    only = args.only.strip().lower()
    jobs = (
        ["weighted", "threshold", "triple", "continue_ft"]
        if only == "all"
        else [j.strip() for j in only.split(",") if j.strip()]
    )

    p = _paths()
    v28 = _pick(p["v28"], p["v28_ens"])
    lofo = _pick(
        p["lofo"],
        ROOT / "outputs" / "ml_eval" / "lofo_v1" / "CARDOSO" / "weights_pretrained_best.pt",
    )
    if v28 is None or lofo is None:
        print("ERROR: need v28 and LOFO-CARDOSO weights")
        return 1
    if not p["val"].is_dir() or not p["test"].is_dir():
        print("ERROR: missing holdout val/test")
        return 1

    report: dict = {
        "batch": "v31_metric_push",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "baseline_v30": V30,
        "jobs": jobs,
        "experiments": {},
    }

    mix_for_thr = [0.5, 0.5]
    if "weighted" in jobs:
        print(">>> weighted pair")
        wrep = exp_weighted_pair(v28, lofo, p["val"], p["test"])
        report["experiments"]["weighted_pair"] = wrep
        mix_for_thr = wrep.get("member_weights_applied") or mix_for_thr
        print(json.dumps(wrep.get("verdict_block"), indent=2))

    if "threshold" in jobs:
        print(">>> threshold")
        trep = exp_threshold(v28, lofo, p["val"], p["test"], mix_for_thr)
        report["experiments"]["threshold"] = trep
        print(json.dumps(trep.get("verdict_block"), indent=2))

    if "triple" in jobs:
        print(">>> triple")
        trep = exp_triple(v28, p["ema"], lofo, p["val"], p["test"])
        report["experiments"]["triple"] = trep
        print(
            json.dumps(
                {k: trep.get(k) for k in ("verdict_equal", "verdict_weighted", "skipped")}, indent=2
            )
        )

    if "continue_ft" in jobs:
        print(">>> continue FT from v28")
        crep = exp_continue_ft(
            v28,
            ROOT / "artifacts" / "clm_ndws_patches" / "holdout_v1",
            args.epochs,
            args.patience,
        )
        report["experiments"]["continue_ft"] = crep
        print(json.dumps(crep.get("verdict_single"), indent=2))
        if crep.get("verdict_ens"):
            print(json.dumps(crep.get("verdict_ens"), indent=2))

    # Champion selection
    candidates = []
    for exp in report["experiments"].values():
        for key in (
            "verdict_block",
            "verdict_equal",
            "verdict_weighted",
            "verdict_single",
            "verdict_ens",
        ):
            vb = exp.get(key) if isinstance(exp, dict) else None
            if isinstance(vb, dict) and "model_iou" in vb:
                candidates.append(vb)
    if candidates:
        champ = max(
            candidates,
            key=lambda r: (r["improvement_vs_copy_iou"], r["model_iou"]),
        )
        report["champion"] = champ
        # If beats v30, write mix into ensemble manifest note file
        if champ.get("beats_v30") or champ.get("vs_v30", {}).get("beats_v30"):
            out_dir = ROOT / "outputs" / "ml_eval" / "v31_metric_push"
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "champion.json").write_text(json.dumps(champ, indent=2), encoding="utf-8")

    out = ROOT / "docs" / "V31_ML_SCORECARD.json"
    # strip bulky aggregates
    slim = json.loads(json.dumps(report, default=str))
    for exp in slim.get("experiments", {}).values():
        if not isinstance(exp, dict):
            continue
        for k in list(exp.keys()):
            if isinstance(exp[k], dict) and "aggregate" in exp[k]:
                exp[k] = {kk: vv for kk, vv in exp[k].items() if kk != "aggregate"}
    out.write_text(json.dumps(slim, indent=2), encoding="utf-8")
    print("SCORECARD", out)
    if slim.get("champion"):
        print("CHAMPION", json.dumps(slim["champion"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
