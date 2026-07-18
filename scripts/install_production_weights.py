#!/usr/bin/env python3
"""Install v21 production weights into models/production/.

``.pt`` weight files are **gitignored** (see ``.gitignore`` and CONTRIBUTING).
This script copies from known sources into the canonical product path used by
``models/production/manifest.json`` and ``models/catalog.json``.

Source search order:
1. Existing ``models/production/weights_v21_best.pt`` (already installed)
2. ``models/production/weights_pretrained_best.pt`` (alternate local name)
3. Kaggle kernel output dirs (``kaggle_outputs_v21/``), if present locally
4. Other common export paths under ``outputs/``

Usage::

    python scripts/install_production_weights.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEST_DIR = PROJECT_ROOT / "models" / "production"
DEST = DEST_DIR / "weights_v21_best.pt"

# Prefer local production alternate names, then Kaggle outputs, then exports.
# (Canonical DEST is handled by the early-return below, not listed here.)
CANDIDATES = [
    DEST_DIR / "weights_pretrained_best.pt",
    PROJECT_ROOT / "kaggle_outputs_v21" / "_top" / "weights_pretrained_best.pt",
    PROJECT_ROOT / "kaggle_outputs_v21" / "weights_pretrained_best.pt",
    PROJECT_ROOT / "kaggle_outputs_v21" / "weights_v21_best.pt",
    PROJECT_ROOT / "outputs" / "ml_eval" / "v21" / "weights_pretrained_best.pt",
]


def main() -> int:
    if DEST.is_file() and DEST.stat().st_size > 1000:
        print(f"Already present {DEST} ({DEST.stat().st_size // 1024} KB)")
        return 0

    for src in CANDIDATES:
        if src.is_file() and src.stat().st_size > 1000:
            DEST_DIR.mkdir(parents=True, exist_ok=True)
            if src.resolve() != DEST.resolve():
                shutil.copy2(src, DEST)
            print(f"Installed {DEST} ({DEST.stat().st_size // 1024} KB) from {src}")
            return 0

    print(
        "v21 weights not found.\n"
        "  .pt files are gitignored — obtain weights from a Kaggle kernel output\n"
        "  or a release asset, place as models/production/weights_v21_best.pt,\n"
        "  or copy a known checkpoint and re-run this script.\n"
        "  For dual-product install (NDWS + CLM + ensemble), see:\n"
        "    python scripts/install_dual_weights.py",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
