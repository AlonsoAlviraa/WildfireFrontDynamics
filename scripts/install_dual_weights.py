#!/usr/bin/env python3
"""Install production ML products under models/ (NDWS + CLM + ensemble).

``.pt`` weight files are **gitignored** (see ``.gitignore`` and CONTRIBUTING).
This script copies known local sources into the canonical paths used by
``models/catalog.json``. If a destination already exists and is non-trivial
size, it is left alone.

Sources may be Kaggle output dirs (often deleted after CLEANUP), local
``models/production/`` / ``models/clm_*`` copies, or ``outputs/ml_eval/``
training runs. Clean clones without any of these will report MISSING and exit 1.

For v21-only install::

    python scripts/install_production_weights.py
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (source candidates in order, destination)
INSTALL_PLAN: list[tuple[list[Path], Path]] = [
    (
        [
            ROOT / "kaggle_outputs_v21" / "weights_pretrained_best.pt",
            ROOT / "models" / "production" / "weights_v21_best.pt",
        ],
        ROOT / "models" / "production" / "weights_v21_best.pt",
    ),
    (
        [
            ROOT / "outputs" / "ml_eval" / "v28_clm_ft" / "weights_pretrained_best.pt",
            ROOT / "models" / "clm_specialist" / "weights_v28_clm_ft.pt",
        ],
        ROOT / "models" / "clm_specialist" / "weights_v28_clm_ft.pt",
    ),
    # Ensemble members (vendored under models/clm_ensemble)
    (
        [
            ROOT / "models" / "clm_specialist" / "weights_v28_clm_ft.pt",
            ROOT / "outputs" / "ml_eval" / "v28_clm_ft" / "weights_pretrained_best.pt",
            ROOT / "models" / "clm_ensemble" / "weights_v28_clm_ft.pt",
        ],
        ROOT / "models" / "clm_ensemble" / "weights_v28_clm_ft.pt",
    ),
    (
        [
            ROOT / "outputs" / "ml_eval" / "lofo_v1" / "CARDOSO" / "weights_pretrained_best.pt",
            ROOT / "models" / "clm_ensemble" / "weights_lofo_cardoso.pt",
        ],
        ROOT / "models" / "clm_ensemble" / "weights_lofo_cardoso.pt",
    ),
    (
        [
            ROOT / "outputs" / "ml_eval" / "v30_ema" / "weights_pretrained_best.pt",
            ROOT / "models" / "clm_ensemble" / "weights_v30_ema.pt",
        ],
        ROOT / "models" / "clm_ensemble" / "weights_v30_ema.pt",
    ),
    (
        [
            ROOT / "outputs" / "ml_eval" / "loop_3way" / "multi_if" / "weights_multi_if_best_holdout.pt",
            ROOT / "outputs" / "ml_eval" / "loop_3way" / "multi_if" / "weights_pretrained_best.pt",
            ROOT / "models" / "clm_ensemble" / "weights_multi_if.pt",
        ],
        ROOT / "models" / "clm_ensemble" / "weights_multi_if.pt",
    ),
]


def _ensure(sources: list[Path], dst: Path) -> str:
    if dst.is_file() and dst.stat().st_size > 1000:
        return f"OK exists {dst.relative_to(ROOT)} ({dst.stat().st_size} bytes)"
    for src in sources:
        if src.is_file() and src.stat().st_size > 1000:
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.resolve() != dst.resolve():
                shutil.copy2(src, dst)
            return f"COPIED {src.relative_to(ROOT) if src.is_relative_to(ROOT) else src} -> {dst.relative_to(ROOT)}"
    return f"MISSING {dst.relative_to(ROOT)} (no source found)"


def main() -> int:
    lines: list[str] = []
    ok = True
    for sources, dst in INSTALL_PLAN:
        msg = _ensure(sources, dst)
        lines.append(msg)
        if msg.startswith("MISSING"):
            ok = False

    for line in lines:
        print(line)

    sys.path.insert(0, str(ROOT))
    from wildfire_front.ml.product_catalog import list_products

    products = list_products()
    print(json.dumps(products, indent=2))
    not_ready = [p["id"] for p in products if not p.get("ready")]
    if not_ready:
        print("NOT READY:", not_ready, file=sys.stderr)
        ok = False
    else:
        print("All catalog products ready.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
