#!/usr/bin/env python3
"""Ensure dual-product weight files are in models/production and models/clm_specialist."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

NDWS_TARGETS = [
    (ROOT / "kaggle_outputs_v21" / "weights_pretrained_best.pt", ROOT / "models" / "production" / "weights_v21_best.pt"),
]
CLM_TARGETS = [
    (ROOT / "outputs" / "ml_eval" / "v28_clm_ft" / "weights_pretrained_best.pt", ROOT / "models" / "clm_specialist" / "weights_v28_clm_ft.pt"),
    (ROOT / "models" / "clm_specialist" / "weights_v28_clm_ft.pt", ROOT / "models" / "clm_specialist" / "weights_v28_clm_ft.pt"),
]


def _ensure(src: Path, dst: Path) -> str:
    if dst.is_file() and dst.stat().st_size > 1000:
        return f"OK exists {dst.relative_to(ROOT)} ({dst.stat().st_size} bytes)"
    if src.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.resolve() != dst.resolve():
            shutil.copy2(src, dst)
        return f"COPIED {src} -> {dst}"
    return f"MISSING {dst} (source {src} not found)"


def main() -> int:
    lines = []
    ok = True
    for src, dst in NDWS_TARGETS:
        msg = _ensure(src, dst)
        lines.append(msg)
        if msg.startswith("MISSING"):
            ok = False
    for src, dst in CLM_TARGETS:
        if dst.is_file() and dst.stat().st_size > 1000:
            lines.append(f"OK exists {dst.relative_to(ROOT)}")
            break
        msg = _ensure(src, dst)
        lines.append(msg)
        if msg.startswith("MISSING") and src == CLM_TARGETS[-1][0]:
            ok = False
    for line in lines:
        print(line)
    # Verify catalog
    sys.path.insert(0, str(ROOT))
    from wildfire_front.ml.product_catalog import list_products

    print(json_dumps := __import__("json").dumps(list_products(), indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
