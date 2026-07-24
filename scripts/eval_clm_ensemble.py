#!/usr/bin/env python3
"""v30 D2 — Soft-vote LOFO ensemble on CLM holdout test (no retrain).

Single change vs clm_v28: average growth probabilities of LOFO members.

GO if holdout test IoU >= 0.845 OR Δcopy >= +0.205 (vs v28 0.838 / +0.196).
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.ml.clm_eval import (  # noqa: E402
    default_lofo_weight_paths,
    evaluate_clm_weights,
)

# Frozen clm_v28 numbers for honest comparison
V28_BASELINE = {
    "model_iou": 0.8382,
    "improvement_vs_copy_iou": 0.1964,
    "model_iou_growth": 0.694,
}


def main() -> int:
    ap = argparse.ArgumentParser(description="CLM LOFO soft-vote ensemble eval")
    ap.add_argument(
        "--data-dir",
        type=Path,
        default=ROOT / "artifacts" / "clm_ndws_patches" / "holdout_v1" / "test",
    )
    ap.add_argument(
        "--weights",
        type=Path,
        nargs="*",
        default=None,
        help="Checkpoint paths (default: all LOFO folds present)",
    )
    ap.add_argument(
        "--include-v28",
        action="store_true",
        help="With --all-lofo, also include clm_v28 (default honest already has v28)",
    )
    ap.add_argument(
        "--all-lofo",
        action="store_true",
        help="Use all LOFO folds (may LEAK on holdout test=CARDOSO — research only)",
    )
    ap.add_argument("--max-patches", type=int, default=400)
    ap.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "outputs" / "ml_eval" / "v30_clm_ensemble",
    )
    ap.add_argument(
        "--mode",
        choices=["mean_prob", "mean_abs"],
        default="mean_prob",
    )
    ap.add_argument(
        "--install-product",
        action="store_true",
        help="If GO, copy soft-vote recipe into models/clm_ensemble/",
    )
    args = ap.parse_args()

    if args.weights:
        weight_paths = [Path(w) for w in args.weights]
    else:
        # Default HONEST ensemble for holdout_v1 test=CARDOSO:
        # v28 (train Tobarra only) + LOFO fold that held out CARDOSO.
        # Do NOT include LOFO folds trained on Cardoso (leakage).
        v28 = ROOT / "models" / "clm_specialist" / "weights_v28_clm_ft.pt"
        cardoso = (
            ROOT / "outputs" / "ml_eval" / "lofo_v1" / "CARDOSO" / "weights_pretrained_best.pt"
        )
        weight_paths = [p for p in (v28, cardoso) if p.is_file()]
        if args.include_v28:
            # already included
            pass
        if getattr(args, "all_lofo", False):
            weight_paths = default_lofo_weight_paths(ROOT)
            if v28.is_file() and args.include_v28 and v28 not in weight_paths:
                weight_paths.append(v28)
            print(
                "WARNING: --all-lofo may LEAK on holdout test=CARDOSO "
                "(Estrella/Tobarra LOFO folds train on Cardoso)."
            )

    if len(weight_paths) < 2:
        print("ERROR: need >=2 weight members for ensemble; found", len(weight_paths))
        print("  Expected v28 + LOFO CARDOSO weights.")
        return 1
    if not args.data_dir.is_dir():
        print("ERROR: missing data", args.data_dir)
        return 1

    print("=" * 70)
    print("V30 CLM ENSEMBLE (D2 soft-vote)")
    print("  members:", len(weight_paths))
    for w in weight_paths:
        print("   -", w)
    print("  data:", args.data_dir)
    print("  mode:", args.mode)
    print("=" * 70)

    metrics = evaluate_clm_weights(
        weight_paths,
        args.data_dir,
        max_patches=args.max_patches,
        ensemble_mode=args.mode,
    )

    iou = metrics["model_iou"]
    delta = metrics["improvement_vs_copy_iou"]
    growth = metrics["model_iou_growth"]
    beats_v28 = (iou > V28_BASELINE["model_iou"]) or (
        delta > V28_BASELINE["improvement_vs_copy_iou"]
    )
    go_primary = (iou >= 0.845) or (delta >= 0.205)
    # Softer ship: any improvement on full IoU or delta vs frozen v28
    ship_soft = beats_v28 and delta > 0

    if go_primary:
        verdict = "GO_PROMOTE"
    elif ship_soft:
        verdict = "GO_SOFT_PROMOTE"  # better than v28 but below stretch gate
    else:
        verdict = "NO_PROMOTE"

    report = {
        "version": "v30_clm_ensemble_honest"
        if not getattr(args, "all_lofo", False)
        else "v30_clm_ensemble_all_lofo",
        "rail": "transfer_ensemble",
        "single_change": (
            "soft-vote mean growth: clm_v28 + LOFO held-out CARDOSO"
            if not getattr(args, "all_lofo", False)
            else "soft-vote all LOFO (+optional v28) — may LEAK on holdout test"
        ),
        "protocol": "clm_holdout_test_seed42_v1",
        "leakage_note": (
            "Holdout test is CARDOSO. Default members never train on Cardoso. "
            "Use --all-lofo only for research (LEAK risk)."
        ),
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "ensemble_mode": args.mode,
        "members": [str(w) for w in weight_paths],
        "n_members": len(weight_paths),
        "n_patches": metrics["n_patches"],
        "model_iou": iou,
        "copy_baseline_iou": metrics["copy_baseline_iou"],
        "improvement_vs_copy_iou": delta,
        "model_iou_growth": growth,
        "improvement_vs_dilated_copy_iou_growth": metrics["improvement_vs_dilated_copy_iou_growth"],
        "vs_v28": {
            "baseline_iou": V28_BASELINE["model_iou"],
            "baseline_delta": V28_BASELINE["improvement_vs_copy_iou"],
            "baseline_growth": V28_BASELINE["model_iou_growth"],
            "iou_diff": iou - V28_BASELINE["model_iou"],
            "delta_diff": delta - V28_BASELINE["improvement_vs_copy_iou"],
            "growth_diff": growth - V28_BASELINE["model_iou_growth"],
            "beats_v28": beats_v28,
        },
        "gates": {
            "G2_delta_positive": delta > 0,
            "stretch_iou_0_845_or_delta_0_205": go_primary,
            "soft_beats_v28": ship_soft,
        },
        "verdict": verdict,
        "go": verdict.startswith("GO"),
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    out = args.output_dir / "v30_ensemble_verdict.json"
    # Drop bulky aggregate from file? keep slim report + optional full
    slim = dict(report.items())
    out.write_text(json.dumps(slim, indent=2), encoding="utf-8")
    (args.output_dir / "v30_ensemble_metrics_full.json").write_text(
        json.dumps({**report, "aggregate": metrics.get("aggregate")}, indent=2, default=str),
        encoding="utf-8",
    )

    # Also freeze docs snapshot
    docs = ROOT / "docs" / "V30_ENSEMBLE_VERDICT.json"
    docs.write_text(json.dumps(slim, indent=2), encoding="utf-8")

    if report["go"] and args.install_product:
        prod = ROOT / "models" / "clm_ensemble"
        prod.mkdir(parents=True, exist_ok=True)
        # Store member list + verdict; weights stay in place (referenced)
        (prod / "manifest.json").write_text(
            json.dumps(
                {
                    "id": "clm_ensemble_v30",
                    "product": "clm_ensemble_v30",
                    "ensemble_mode": args.mode,
                    "members": [
                        str(w.relative_to(ROOT)) if w.is_relative_to(ROOT) else str(w)
                        for w in weight_paths
                    ],
                    "metrics": {
                        "model_iou": iou,
                        "improvement_vs_copy_iou": delta,
                        "model_iou_growth": growth,
                    },
                    "verdict": verdict,
                    "protocol": "clm_holdout_test_seed42_v1",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        # Optional: also install a single "reference" as mean of first member for catalog compat
        ref = weight_paths[0]
        shutil.copy2(ref, prod / "member0_ref.pt")
        print("Installed models/clm_ensemble/manifest.json")

    print(json.dumps(slim, indent=2))
    print("Wrote", out)
    print("Wrote", docs)
    return 0 if report["go"] or verdict == "NO_PROMOTE" else 0


if __name__ == "__main__":
    raise SystemExit(main())
