#!/usr/bin/env python3
"""Align multi-frame LWIR + masks to chain-local common grids (W3).

Usage::

    $env:PYTHONPATH = "."
    python scripts/align_lwir_common_grid.py \\
        --images-dir artifacts/hellin_2024_reprojected_lwir \\
        --masks-dir artifacts/hellin_2024_lwir_masks \\
        --out-root outputs/ml_eval/w3/hellin_2024/aligned
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.ml.align_geotiff_stack import align_fire_chains  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--images-dir", type=Path, required=True)
    p.add_argument("--masks-dir", type=Path, required=True)
    p.add_argument("--out-root", type=Path, required=True)
    p.add_argument("--min-overlap", type=float, default=0.4)
    p.add_argument("--mode", choices=["intersection", "union"], default="intersection")
    p.add_argument("--resolution-m", type=float, default=None)
    p.add_argument("--max-side-px", type=int, default=4096)
    p.add_argument("--no-pair-fallback", action="store_true")
    args = p.parse_args(argv)

    manifest = align_fire_chains(
        args.images_dir,
        args.masks_dir,
        args.out_root,
        min_overlap=float(args.min_overlap),
        mode=args.mode,  # type: ignore[arg-type]
        resolution_m=args.resolution_m,
        max_side_px=int(args.max_side_px),
        pair_fallback=not args.no_pair_fallback,
    )
    print(
        json.dumps(
            {
                "ok": manifest.get("ok"),
                "n_matched": manifest.get("n_matched_frames"),
                "n_aligned_ok": manifest.get("n_aligned_ok"),
                "raw_chain_lengths": manifest.get("raw_chain_lengths"),
                "manifest": str(args.out_root / "align_manifest.json"),
            },
            indent=2,
        )
    )
    return 0 if manifest.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
