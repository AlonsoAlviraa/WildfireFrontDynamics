#!/usr/bin/env python3
"""Dual-product CLI — NDWS v21 or CLM v28 spread prediction from NPZ patches.

Examples:
  python scripts/predict_spread.py --list-products
  python scripts/predict_spread.py --product ndws_v21 --npz path/to/patch.npz --output pred.npz
  python scripts/predict_spread.py --product clm_v28 --npz artifacts/clm_ndws_patches/holdout_v1/test --eval
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from wildfire_front.ml.ndws_metrics import evaluate_sample  # noqa: E402
from wildfire_front.ml.product_catalog import get_product, list_products  # noqa: E402
from wildfire_front.ml.spread_predictor import SpreadPredictor  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Dual product spread prediction (NDWS v21 | CLM v28)"
    )
    parser.add_argument(
        "--product",
        choices=["ndws_v21", "clm_v28"],
        default="clm_v28",
        help="Which production product to load (default: emergency CLM specialist)",
    )
    parser.add_argument("--list-products", action="store_true")
    parser.add_argument("--manifest", type=str, default=None, help="Override manifest path")
    parser.add_argument("--weights", type=str, default=None, help="Override weights path")
    parser.add_argument("--npz", type=str, default=None, help="Input patch NPZ or directory")
    parser.add_argument("--output", type=str, default=None, help="Write prediction NPZ (single file)")
    parser.add_argument("--eval", action="store_true", help="Metrics if target_fire present")
    parser.add_argument("--max-patches", type=int, default=0, help="0 = all")
    args = parser.parse_args()

    if args.list_products:
        print(json.dumps(list_products(), indent=2))
        return 0

    if not args.npz:
        print("--npz required unless --list-products", file=sys.stderr)
        return 2

    if args.manifest:
        manifest_path = Path(args.manifest)
        weights_path = args.weights
    else:
        spec = get_product(args.product)
        ok, msg = spec.resolve_existing()
        if not ok:
            print(f"Product {args.product} not ready: {msg}", file=sys.stderr)
            return 1
        manifest_path = spec.manifest_path
        weights_path = str(spec.weights_path)
        print(f"Product: {spec.id} ({spec.domain})")
        print(f"  use_when: {spec.use_when}")
        print(f"  not_for:  {spec.not_for}")

    predictor = SpreadPredictor.from_manifest(manifest_path, weights_path=weights_path)

    npz_path = Path(args.npz)
    paths = sorted(npz_path.glob("*.npz")) if npz_path.is_dir() else [npz_path]
    if args.max_patches and args.max_patches > 0:
        paths = paths[: args.max_patches]
    if not paths:
        print(f"No NPZ under {npz_path}", file=sys.stderr)
        return 1

    metrics_rows: list[dict] = []
    for path in paths:
        with np.load(path) as data:
            seq = data["sequence"]
            current_fire = data["current_fire"]
            target_fire = data["target_fire"] if "target_fire" in data else None

        pred_prob = predictor.predict(seq, current_fire)
        pred_bin = (pred_prob >= predictor.manifest.threshold).astype(np.float32)

        if args.eval and target_fire is not None:
            sample = evaluate_sample(pred_prob, current_fire, target_fire)
            metrics_rows.append(
                {
                    "file": path.name,
                    "iou": float(sample["model_full"].iou),
                    "copy_iou": float(sample["copy_full"].iou),
                }
            )

        if args.output and len(paths) == 1:
            out = Path(args.output)
            out.parent.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(
                out,
                prediction=pred_prob,
                prediction_binary=pred_bin,
                current_fire=current_fire,
                target_fire=target_fire if target_fire is not None else np.array([]),
                product=args.product,
                model_version=predictor.manifest.version,
            )
            print(f"Wrote {out}")

    if metrics_rows:
        ious = np.asarray([r["iou"] for r in metrics_rows], dtype=float)
        copy_ious = np.asarray([r["copy_iou"] for r in metrics_rows], dtype=float)
        report = {
            "product": args.product,
            "model_version": predictor.manifest.version,
            "n_patches": len(metrics_rows),
            "mean_iou": float(ious.mean()),
            "mean_copy_iou": float(copy_ious.mean()),
            "mean_delta_vs_copy": float((ious - copy_ious).mean()),
        }
        print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
