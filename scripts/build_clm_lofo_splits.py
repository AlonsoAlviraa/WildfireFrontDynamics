#!/usr/bin/env python3
"""Build leave-one-source-out CLM patch folders under artifacts/clm_ndws_patches/lofo_v1/."""

from __future__ import annotations

import json
import shutil
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "artifacts" / "clm_ndws_patches" / "holdout_v1"
OUT_ROOT = ROOT / "artifacts" / "clm_ndws_patches" / "lofo_v1"


def main() -> int:
    by_src: dict[str, list[Path]] = defaultdict(list)
    for split in ("train", "val", "test"):
        d = SRC_ROOT / split
        if not d.is_dir():
            continue
        for p in d.glob("*.npz"):
            import numpy as np

            with np.load(p) as z:
                src = str(z["source"]) if "source" in z.files else "unknown"
            by_src[src].append(p)

    if len(by_src) < 2:
        print("Need >=2 sources", file=sys.stderr)
        return 1

    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)

    manifest = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "sources": {k: len(v) for k, v in sorted(by_src.items())},
        "folds": {},
    }

    for held in sorted(by_src):
        fold = OUT_ROOT / held
        train_dir = fold / "train"
        val_dir = fold / "val"
        test_dir = fold / "test"
        train_dir.mkdir(parents=True)
        val_dir.mkdir(parents=True)
        test_dir.mkdir(parents=True)

        train_pool: list[Path] = []
        for src, paths in by_src.items():
            if src == held:
                for _i, p in enumerate(sorted(paths)):
                    # held-out source → test only
                    shutil.copy2(p, test_dir / p.name)
            else:
                train_pool.extend(sorted(paths))

        train_pool = sorted(train_pool)
        n = len(train_pool)
        n_val = max(1, n // 10)
        for p in train_pool[:-n_val]:
            shutil.copy2(p, train_dir / p.name)
        for p in train_pool[-n_val:]:
            shutil.copy2(p, val_dir / p.name)

        manifest["folds"][held] = {
            "train": len(list(train_dir.glob("*.npz"))),
            "val": len(list(val_dir.glob("*.npz"))),
            "test": len(list(test_dir.glob("*.npz"))),
        }
        print(held, manifest["folds"][held])

    out = ROOT / "docs" / "CLM_LOFO_SPLITS_MANIFEST.json"
    out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (OUT_ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("Wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
