#!/usr/bin/env python3
"""Build frozen CLM train/val/test holdout from flat train pool.

Rule v1 (docs/ML_TRANSFER_PROTOCOL.md):
  - Group by event prefix clm_<EVENT>_ when present
  - Else content-hash singleton groups
  - Seed 42 → 70/15/15 by group
  - Copy (not move) into train/val/test; write holdout_manifest.json

Usage:
  python scripts/build_clm_holdout_splits.py --seed 42
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POOL = ROOT / "artifacts" / "clm_ndws_patches" / "train"
DEFAULT_OUT = ROOT / "artifacts" / "clm_ndws_patches"


def _event_key(path: Path) -> str:
    m = re.match(r"clm_([A-Za-z0-9]+)_", path.name)
    if m:
        return m.group(1).upper()
    return path.stem


def _content_hash(path: Path) -> str:
    with np.load(path) as z:
        h = hashlib.sha256()
        for key in ("sequence", "current_fire", "target_fire"):
            if key in z.files:
                h.update(np.ascontiguousarray(z[key]).tobytes())
        return h.hexdigest()[:16]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", type=Path, default=DEFAULT_POOL)
    ap.add_argument("--out-root", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--train-frac", type=float, default=0.70)
    ap.add_argument("--val-frac", type=float, default=0.15)
    args = ap.parse_args()

    files = sorted(args.pool.glob("*.npz"))
    if not files:
        print(f"No NPZ in {args.pool}")
        return 1

    # Dedupe by content hash; keep first path
    by_hash: dict[str, Path] = {}
    for fp in files:
        ch = _content_hash(fp)
        by_hash.setdefault(ch, fp)
    unique = list(by_hash.values())

    groups: dict[str, list[Path]] = defaultdict(list)
    for fp in unique:
        groups[_event_key(fp)].append(fp)

    rng = np.random.default_rng(args.seed)
    keys = sorted(groups.keys())
    rng.shuffle(keys)

    n = len(keys)
    n_train = max(1, int(round(n * args.train_frac)))
    n_val = max(1, int(round(n * args.val_frac)))
    if n_train + n_val >= n:
        n_val = max(1, n // 6)
        n_train = max(1, n - n_val - max(1, n // 6))
    train_keys = set(keys[:n_train])
    val_keys = set(keys[n_train : n_train + n_val])
    test_keys = set(keys[n_train + n_val :])

    assignment: dict[str, list[str]] = {"train": [], "val": [], "test": []}
    for k, paths in groups.items():
        if k in train_keys:
            split = "train"
        elif k in val_keys:
            split = "val"
        else:
            split = "test"
        for p in paths:
            assignment[split].append(p.name)

    # Materialize under holdout/ to avoid clobbering raw train pool layout
    holdout_root = args.out_root / "holdout_v1"
    for split, names in assignment.items():
        d = holdout_root / split
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True, exist_ok=True)
        for name in names:
            src = args.pool / name
            if src.is_file():
                shutil.copy2(src, d / name)

    manifest = {
        "protocol": "clm_holdout_test_seed42_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "seed": args.seed,
        "train_frac": args.train_frac,
        "val_frac": args.val_frac,
        "pool": str(args.pool),
        "holdout_root": str(holdout_root),
        "n_files_pool": len(files),
        "n_unique_content": len(unique),
        "n_events": n,
        "counts": {s: len(assignment[s]) for s in assignment},
        "events": {
            "train": sorted(train_keys),
            "val": sorted(val_keys),
            "test": sorted(test_keys),
        },
        "rule": "event_prefix_or_stem; 70/15/15 by event; content-hash dedup",
    }
    man_path = holdout_root / "holdout_manifest.json"
    man_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest["counts"], indent=2))
    print("events", {k: len(v) for k, v in manifest["events"].items()})
    print("Wrote", man_path)
    # Disjoint check
    sets = {s: set(assignment[s]) for s in assignment}
    assert sets["train"].isdisjoint(sets["test"])
    assert sets["train"].isdisjoint(sets["val"])
    assert sets["val"].isdisjoint(sets["test"])
    print("Disjoint OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
