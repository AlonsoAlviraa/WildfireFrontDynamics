#!/usr/bin/env python3
"""Per-source CLM transfer table for industrial G2+ (not train cherry-pick)."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.ml.ndws_metrics import evaluate_sample  # noqa: E402
from wildfire_front.ml.product_catalog import get_product  # noqa: E402
from wildfire_front.ml.spread_predictor import SpreadPredictor  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--product", default="clm_v28")
    ap.add_argument("--max-per-source", type=int, default=40)
    ap.add_argument(
        "--data-root",
        type=Path,
        default=ROOT / "artifacts" / "clm_ndws_patches" / "holdout_v1",
    )
    args = ap.parse_args()

    spec = get_product(args.product)
    ok, msg = spec.resolve_existing()
    if not ok:
        print(msg, file=sys.stderr)
        return 1
    pred = SpreadPredictor.from_manifest(spec.manifest_path, weights_path=str(spec.weights_path))

    by_src: dict[str, list[Path]] = defaultdict(list)
    for split in ("train", "val", "test"):
        d = args.data_root / split
        if not d.is_dir():
            continue
        for p in d.glob("*.npz"):
            with np.load(p) as z:
                src = str(z["source"]) if "source" in z.files else "unknown"
            by_src[src].append(p)

    by_source: dict[str, dict] = {}
    for src, paths in sorted(by_src.items()):
        paths = sorted(paths)[: args.max_per_source]
        ious: list[float] = []
        copies: list[float] = []
        for path in paths:
            with np.load(path) as d:
                pp = pred.predict(d["sequence"], d["current_fire"])
                s = evaluate_sample(pp, d["current_fire"], d["target_fire"])
                ious.append(float(s["model_full"].iou))
                copies.append(float(s["copy_full"].iou))
        i = np.asarray(ious, dtype=float)
        c = np.asarray(copies, dtype=float)
        by_source[src] = {
            "n": int(len(i)),
            "mean_iou": float(i.mean()),
            "mean_copy": float(c.mean()),
            "mean_delta": float((i - c).mean()),
            "frac_beat_copy": float((i > c).mean()),
        }

    deltas = [v["mean_delta"] for v in by_source.values()] or [0.0]
    report = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "product": args.product,
        "protocol": "clm_per_source_eval_holdout_v1",
        "by_source": by_source,
        "summary": {
            "n_sources": len(deltas),
            "mean_delta_across_sources": float(np.mean(deltas)),
            "min_delta": float(np.min(deltas)),
            "all_sources_delta_positive": bool(all(d > 0 for d in deltas)),
            "industrial_g2_plus": bool(
                all(d > 0 for d in deltas) and len(deltas) >= 2
            ),
        },
        "note": (
            "Tobarra may show ~0 delta if fine-tune saw similar patches; "
            "industrial bar is delta>0 on multi-source held patterns."
        ),
    }
    out = ROOT / "docs" / "CLM_SOURCE_TRANSFER_REPORT.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    for s, v in by_source.items():
        print(f"  {s}: IoU={v['mean_iou']:.3f} Δ={v['mean_delta']:.3f} n={v['n']}")
    print("Wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
