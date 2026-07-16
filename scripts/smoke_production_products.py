#!/usr/bin/env python3
"""Industrial smoke: dual ML products ready + optional CLM eval."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.ml.ndws_metrics import evaluate_sample  # noqa: E402
from wildfire_front.ml.product_catalog import list_products  # noqa: E402
from wildfire_front.ml.product_catalog import get_product  # noqa: E402
from wildfire_front.ml.spread_predictor import SpreadPredictor  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clm-max", type=int, default=10)
    args = ap.parse_args()

    products = list_products()
    not_ready = [p for p in products if not p.get("ready")]
    print(json.dumps(products, indent=2))
    if not_ready:
        print("FAIL: products not ready", [p["id"] for p in not_ready], file=sys.stderr)
        return 1

    # CLM smoke
    test_dir = ROOT / "artifacts" / "clm_ndws_patches" / "holdout_v1" / "test"
    paths = sorted(test_dir.glob("*.npz"))[: args.clm_max]
    if not paths:
        print("WARN: no CLM test patches; skip eval")
        return 0

    spec = get_product("clm_v28")
    pred = SpreadPredictor.from_manifest(spec.manifest_path, weights_path=str(spec.weights_path))
    ious = []
    copies = []
    for path in paths:
        with np.load(path) as d:
            pp = pred.predict(d["sequence"], d["current_fire"])
            s = evaluate_sample(pp, d["current_fire"], d["target_fire"])
            ious.append(s["model_full"].iou)
            copies.append(s["copy_full"].iou)
    report = {
        "product": "clm_v28",
        "n": len(ious),
        "mean_iou": float(np.mean(ious)),
        "mean_delta": float(np.mean(np.array(ious) - np.array(copies))),
        "pass": bool(np.mean(np.array(ious) - np.array(copies)) > 0),
    }
    print(json.dumps(report, indent=2))
    return 0 if report["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
