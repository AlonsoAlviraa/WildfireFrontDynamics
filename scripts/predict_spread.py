#!/usr/bin/env python3
"""Production CLI — predict next-day fire spread from NPZ patches."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from wildfire_front.ml.ndws_metrics import evaluate_sample  # noqa: E402
from wildfire_front.ml.spread_predictor import SpreadPredictor  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="NDWS spread prediction (production v21)")
    parser.add_argument(
        "--manifest",
        type=str,
        default=str(PROJECT_ROOT / "models" / "production" / "manifest.json"),
    )
    parser.add_argument("--weights", type=str, default=None)
    parser.add_argument("--npz", type=str, required=True, help="Input patch NPZ or directory")
    parser.add_argument("--output", type=str, default=None, help="Write prediction NPZ")
    parser.add_argument("--eval", action="store_true", help="Compute metrics if target_fire present")
    args = parser.parse_args()

    predictor = SpreadPredictor.from_manifest(
        args.manifest,
        weights_path=args.weights,
    )

    npz_path = Path(args.npz)
    paths = sorted(npz_path.glob("*.npz")) if npz_path.is_dir() else [npz_path]
    if not paths:
        print(f"No NPZ files under {npz_path}", file=sys.stderr)
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
                    "iou": sample["model_full"].iou,
                    "copy_iou": sample["copy_full"].iou,
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
            )
            print(f"Wrote {out}")

    if metrics_rows:
        ious = [r["iou"] for r in metrics_rows]
        copy_ious = [r["copy_iou"] for r in metrics_rows]
        report = {
            "n_patches": len(metrics_rows),
            "mean_iou": float(np.mean(ious)),
            "mean_copy_iou": float(np.mean(copy_ious)),
            "improvement_vs_copy": float(np.mean(ious) - np.mean(copy_ious)),
            "per_patch": metrics_rows,
        }
        print(json.dumps(report, indent=2))
    else:
        print(f"Predicted {len(paths)} patch(es) with {predictor.manifest.version}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())