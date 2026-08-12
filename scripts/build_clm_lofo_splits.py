#!/usr/bin/env python3
"""Build leave-one-source-out CLM patch folders.

Default (legacy):
  src: artifacts/clm_ndws_patches/holdout_v1
  out: artifacts/clm_ndws_patches/lofo_v1

Metrics-lift E3a (do not mutate sealed holdout_v1)::

    python scripts/build_clm_lofo_splits.py \\
        --src-root artifacts/clm_ndws_patches/holdout_v1_plus_w3 \\
        --out-root artifacts/clm_ndws_patches/lofo_v2
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SRC = ROOT / "artifacts" / "clm_ndws_patches" / "holdout_v1"
DEFAULT_OUT = ROOT / "artifacts" / "clm_ndws_patches" / "lofo_v1"


def build_lofo_splits(src_root: Path, out_root: Path, *, clean: bool = True) -> dict:
    by_src: dict[str, list[Path]] = defaultdict(list)
    for split in ("train", "val", "test"):
        d = src_root / split
        if not d.is_dir():
            continue
        for p in d.glob("*.npz"):
            import numpy as np

            with np.load(p) as z:
                src = str(z["source"]) if "source" in z.files else "unknown"
            by_src[src].append(p)

    if len(by_src) < 2:
        raise SystemExit("Need >=2 sources")

    if clean and out_root.exists():
        # Never delete sealed default lofo_v1 unless explicitly the out_root
        shutil.rmtree(out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    manifest = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "src_root": str(src_root.as_posix()),
        "out_root": str(out_root.as_posix()),
        "sources": {k: len(v) for k, v in sorted(by_src.items())},
        "folds": {},
        "mutated_sealed_holdout_v1": False,
    }

    for held in sorted(by_src):
        fold = out_root / held
        train_dir = fold / "train"
        val_dir = fold / "val"
        test_dir = fold / "test"
        train_dir.mkdir(parents=True, exist_ok=True)
        val_dir.mkdir(parents=True, exist_ok=True)
        test_dir.mkdir(parents=True, exist_ok=True)

        train_pool: list[Path] = []
        for src, paths in by_src.items():
            if src == held:
                for p in sorted(paths):
                    shutil.copy2(p, test_dir / p.name)
            else:
                train_pool.extend(sorted(paths))

        train_pool = sorted(train_pool)
        n = len(train_pool)
        n_val = max(1, n // 10) if n else 0
        for p in train_pool[:-n_val] if n_val else train_pool:
            shutil.copy2(p, train_dir / p.name)
        for p in train_pool[-n_val:] if n_val else []:
            shutil.copy2(p, val_dir / p.name)

        manifest["folds"][held] = {
            "train": len(list(train_dir.glob("*.npz"))),
            "val": len(list(val_dir.glob("*.npz"))),
            "test": len(list(test_dir.glob("*.npz"))),
        }
        print(held, manifest["folds"][held])

    return manifest


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--src-root", type=Path, default=DEFAULT_SRC)
    p.add_argument("--out-root", type=Path, default=DEFAULT_OUT)
    p.add_argument(
        "--no-clean",
        action="store_true",
        help="Do not rmtree out-root before build",
    )
    p.add_argument(
        "--manifest-out",
        type=Path,
        default=None,
        help="Optional manifest JSON path (default docs/CLM_LOFO_SPLITS_MANIFEST.json for default out)",
    )
    p.add_argument(
        "--mix-policy",
        type=str,
        default=None,
        choices=["estrella_floor_v1"],
        help="If set, delegate to build_lofo_mix_v1 (capped multi-fire mix, not naive concat)",
    )
    p.add_argument("--external-cap", type=float, default=0.28)
    p.add_argument("--sibling-oversample", type=float, default=2.0)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    src_root = args.src_root.resolve()
    out_root = args.out_root.resolve()
    if not src_root.is_dir() and not args.dry_run:
        print(f"missing src-root: {src_root}", file=sys.stderr)
        return 1

    # Safety: refuse to write into sealed holdout_v1
    sealed = (ROOT / "artifacts" / "clm_ndws_patches" / "holdout_v1").resolve()
    if out_root == sealed:
        print("refuse: out-root must not be sealed holdout_v1", file=sys.stderr)
        return 2

    if args.mix_policy:
        # Priority B: multi-fire mix designer
        sys.path.insert(0, str(ROOT / "scripts"))
        from build_lofo_mix_v1 import build_mix_lofo  # noqa: WPS433

        manifest = build_mix_lofo(
            src_root,
            out_root,
            mix_policy=args.mix_policy,
            external_cap=float(args.external_cap),
            sibling_oversample=float(args.sibling_oversample),
            clean=not args.no_clean,
            dry_run=bool(args.dry_run),
        )
    else:
        if args.dry_run:
            print(
                "dry-run without --mix-policy: no-op (use mix policy or omit dry-run)",
                file=sys.stderr,
            )
            return 0
        manifest = build_lofo_splits(src_root, out_root, clean=not args.no_clean)

    man_path = args.manifest_out
    if man_path is None:
        if args.dry_run:
            # BUG-3: dry-run must not require out_root to exist
            man_path = (
                ROOT / "outputs" / "ml_eval" / "lofo_mix_estrella_v1_dry_run.json"
                if args.mix_policy
                else ROOT / "outputs" / "ml_eval" / "lofo_splits_dry_run.json"
            )
        elif out_root == DEFAULT_OUT.resolve():
            man_path = ROOT / "docs" / "CLM_LOFO_SPLITS_MANIFEST.json"
        else:
            man_path = out_root / "manifest.json"
    else:
        man_path = Path(man_path)
    man_path.parent.mkdir(parents=True, exist_ok=True)
    man_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if not args.dry_run:
        out_root.mkdir(parents=True, exist_ok=True)
        (out_root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("Wrote", man_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
