#!/usr/bin/env python3
"""Copy v21 Kaggle weights into models/production/."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEST = PROJECT_ROOT / "models" / "production"
CANDIDATES = [
    PROJECT_ROOT / "kaggle_outputs_v21" / "_top" / "weights_pretrained_best.pt",
    PROJECT_ROOT / "kaggle_outputs_v21" / "weights_pretrained_best.pt",
]


def main() -> int:
    for src in CANDIDATES:
        if src.is_file():
            DEST.mkdir(parents=True, exist_ok=True)
            dst = DEST / "weights_v21_best.pt"
            shutil.copy2(src, dst)
            print(f"Installed {dst} ({dst.stat().st_size // 1024} KB)")
            return 0
    print("v21 weights not found. Download from Kaggle kernel output first.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())