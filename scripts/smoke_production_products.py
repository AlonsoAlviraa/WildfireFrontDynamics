#!/usr/bin/env python3
"""Industrial smoke: all catalog ML products ready + CLM eval (single + ensemble)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.ml.ndws_metrics import evaluate_sample  # noqa: E402
from wildfire_front.ml.product_catalog import (  # noqa: E402
    get_product,
    list_products,
    load_predictor_for_product,
)


def _eval_product(product_id: str, paths: list[Path]) -> dict:
    pred = load_predictor_for_product(product_id)
    ious: list[float] = []
    copies: list[float] = []
    for path in paths:
        with np.load(path) as d:
            pp = pred.predict(d["sequence"], d["current_fire"])
            s = evaluate_sample(pp, d["current_fire"], d["target_fire"])
            ious.append(float(s["model_full"].iou))
            copies.append(float(s["copy_full"].iou))
    arr_i = np.asarray(ious, dtype=float)
    arr_c = np.asarray(copies, dtype=float)
    delta = float(np.mean(arr_i - arr_c)) if len(arr_i) else 0.0
    return {
        "product": product_id,
        "n": len(ious),
        "mean_iou": float(np.mean(arr_i)) if len(arr_i) else None,
        "mean_delta": delta,
        "pass": bool(delta > 0) if len(arr_i) else False,
        "n_members": getattr(pred, "n_members", 1),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clm-max", type=int, default=10)
    ap.add_argument(
        "--products",
        default="clm_v28,clm_ensemble_v34",
        help="Comma list of CLM products to eval (default: v28 + ensemble)",
    )
    args = ap.parse_args()

    products = list_products()
    not_ready = [p for p in products if not p.get("ready")]
    print(json.dumps({"catalog": products}, indent=2))
    if not_ready:
        print("FAIL: products not ready", [p["id"] for p in not_ready], file=sys.stderr)
        return 1

    test_dir = ROOT / "artifacts" / "clm_ndws_patches" / "holdout_v1" / "test"
    paths = sorted(test_dir.glob("*.npz"))[: args.clm_max]
    if not paths:
        print("WARN: no CLM test patches; catalog-only smoke")
        return 0

    reports = []
    all_pass = True
    for pid in [x.strip() for x in args.products.split(",") if x.strip()]:
        try:
            get_product(pid)  # validate id
            rep = _eval_product(pid, paths)
        except Exception as exc:  # noqa: BLE001
            rep = {"product": pid, "pass": False, "error": str(exc)}
            all_pass = False
        reports.append(rep)
        if not rep.get("pass"):
            all_pass = False

    # Ensemble should not be worse than single on mean_delta (soft gate)
    by_id = {r["product"]: r for r in reports if "mean_delta" in r}
    ens_id = "clm_ensemble_v34" if "clm_ensemble_v34" in by_id else "clm_ensemble_v30"
    if "clm_v28" in by_id and ens_id in by_id:
        soft = by_id[ens_id]["mean_delta"] >= by_id["clm_v28"]["mean_delta"] - 0.02
        comparison = {
            "ensemble_delta": by_id[ens_id]["mean_delta"],
            "v28_delta": by_id["clm_v28"]["mean_delta"],
            "ensemble_not_much_worse": soft,
        }
    else:
        comparison = None

    out = {
        "ok": all_pass,
        "evals": reports,
        "comparison": comparison,
    }
    print(json.dumps(out, indent=2))
    if not all_pass:
        return 2
    if comparison is not None and not comparison["ensemble_not_much_worse"]:
        print("WARN: ensemble mean_delta << v28 on this sample", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
