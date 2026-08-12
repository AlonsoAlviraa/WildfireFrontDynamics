#!/usr/bin/env python3
"""Build per-fire Head A feature caches for LOFO folds (W1).

Uses production ``clm_ensemble_v34`` on each fold's test patches.
Writes ``outputs/ml_eval/lofo_v1/<FOLD>/head_a_features.npz``.

Does **not** fit calibrators. Does **not** flip field rails.

Usage
-----
::

    $env:PYTHONPATH = "."
    python scripts/build_lofo_head_a_caches.py
    python scripts/build_lofo_head_a_caches.py --max-patches 20
    python scripts/build_lofo_head_a_caches.py --folds CARDOSO
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.ml.lab_lofo_head_a import (  # noqa: E402
    DEFAULT_PRODUCT,
    build_fold_head_a_cache,
    fold_cache_path,
    fold_test_dir,
    list_lofo_folds,
)
from wildfire_front.ml.product_catalog import load_predictor_for_product  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--patches-root",
        type=Path,
        default=ROOT / "artifacts" / "clm_ndws_patches" / "lofo_v1",
    )
    p.add_argument(
        "--out-root",
        type=Path,
        default=ROOT / "outputs" / "ml_eval" / "lofo_v1",
    )
    p.add_argument("--product", default=DEFAULT_PRODUCT)
    p.add_argument("--folds", nargs="*", default=None, help="Subset of fold names")
    p.add_argument("--max-patches", type=int, default=0, help="0 = all")
    p.add_argument("--device", default=None)
    p.add_argument("--skip-existing", action="store_true")
    p.add_argument("--mask-threshold", type=float, default=0.5)
    args = p.parse_args(argv)

    folds = args.folds or list_lofo_folds(args.patches_root)
    # Prefer primary lab folds + Tobarra when present
    preferred = [
        "CARDOSO",
        "LA_ESTRELLA_ACOM1",
        "LA_ESTRELLA_ACOM2",
        "tobarra_20240802",
    ]
    if not args.folds:
        folds = [f for f in preferred if f in folds] or folds
    if not folds:
        print(f"ERROR: no LOFO folds under {args.patches_root}", file=sys.stderr)
        return 2

    print(f"Loading product {args.product} …", flush=True)
    try:
        predictor = load_predictor_for_product(args.product, device=args.device)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: cannot load predictor: {exc}", file=sys.stderr)
        return 1

    results = []
    for fold in folds:
        test_dir = fold_test_dir(args.patches_root, fold)
        out_path = fold_cache_path(args.out_root, fold)
        if args.skip_existing and out_path.is_file():
            print(f"SKIP existing {out_path}", flush=True)
            results.append(
                {"fold": fold, "ok": True, "skipped_existing": True, "path": str(out_path)}
            )
            continue
        if not test_dir.is_dir():
            print(f"SKIP missing test dir {test_dir}", flush=True)
            results.append({"fold": fold, "ok": False, "error": "missing test dir"})
            continue
        print(f"Building Head A cache for {fold} ({test_dir}) …", flush=True)
        row = build_fold_head_a_cache(
            fold=fold,
            test_dir=test_dir,
            out_path=out_path,
            predictor=predictor,
            product_id=args.product,
            mask_threshold=float(args.mask_threshold),
            max_patches=int(args.max_patches),
        )
        results.append(row)
        print(json.dumps(row, indent=2), flush=True)

    n_ok = sum(1 for r in results if r.get("ok"))
    print(
        json.dumps(
            {
                "ok": n_ok == len(results) and n_ok > 0,
                "n_ok": n_ok,
                "n_folds": len(results),
                "results": results,
            },
            indent=2,
        ),
        flush=True,
    )
    return 0 if n_ok > 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
