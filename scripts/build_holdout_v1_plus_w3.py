#!/usr/bin/env python3
"""Stage holdout_v1 + W3 (Hellín) train-pool expansion without mutating sealed holdout_v1.

E3a prep: materialize ``artifacts/clm_ndws_patches/holdout_v1_plus_w3/`` by
copying sealed holdout_v1 splits and optionally linking/copying Hellín patches
from ``outputs/ml_eval/w3/hellin_2024/patches``.

Does **not** overwrite holdout_v1. Downstream LOFO rebuild::

    python scripts/build_clm_lofo_splits.py \\
        --src-root artifacts/clm_ndws_patches/holdout_v1_plus_w3 \\
        --out-root artifacts/clm_ndws_patches/lofo_v2

Usage::

    $env:PYTHONPATH = "."
    python scripts/build_holdout_v1_plus_w3.py --dry-run
    python scripts/build_holdout_v1_plus_w3.py
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SEALED_HOLDOUT = ROOT / "artifacts" / "clm_ndws_patches" / "holdout_v1"
DEFAULT_OUT = ROOT / "artifacts" / "clm_ndws_patches" / "holdout_v1_plus_w3"
HELLIN_PATCHES = ROOT / "outputs" / "ml_eval" / "w3" / "hellin_2024" / "patches"
HELLIN_SOURCE_ID = "hellin_2024"


def _list_npz(d: Path) -> list[Path]:
    if not d.is_dir():
        return []
    return sorted(d.glob("*.npz"))


def inventory() -> dict[str, Any]:
    sealed = {s: len(_list_npz(SEALED_HOLDOUT / s)) for s in ("train", "val", "test")}
    hellin = _list_npz(HELLIN_PATCHES)
    return {
        "sealed_holdout_v1": str(SEALED_HOLDOUT.as_posix()),
        "sealed_counts": sealed,
        "sealed_exists": SEALED_HOLDOUT.is_dir(),
        "hellin_patches": str(HELLIN_PATCHES.as_posix()),
        "hellin_n_patches": len(hellin),
        "hellin_present": len(hellin) > 0,
        "hellin_source_id": HELLIN_SOURCE_ID,
        "mutates_sealed_holdout_v1": False,
    }


def stage(
    out_root: Path,
    *,
    dry_run: bool = False,
    copy_hellin_to: str = "train",
    max_hellin: int | None = None,
) -> dict[str, Any]:
    inv = inventory()
    plan: dict[str, Any] = {
        "schema": "wfd_ml_holdout_v1_plus_w3_stage_v1",
        "created_utc": datetime.now(UTC).isoformat(),
        "inventory": inv,
        "out_root": str(out_root.as_posix()),
        "dry_run": dry_run,
        "copy_hellin_to": copy_hellin_to,
        "actions": [],
        "ok": True,
    }
    if not inv["sealed_exists"]:
        plan["ok"] = False
        plan["error"] = "sealed holdout_v1 missing"
        return plan

    actions: list[dict[str, Any]] = []
    for split in ("train", "val", "test"):
        src = SEALED_HOLDOUT / split
        dst = out_root / split
        n = len(_list_npz(src))
        actions.append(
            {
                "action": "copy_tree_npz",
                "src": str(src.as_posix()),
                "dst": str(dst.as_posix()),
                "n": n,
            }
        )
        if not dry_run and src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
            for p in _list_npz(src):
                shutil.copy2(p, dst / p.name)

    hellin = _list_npz(HELLIN_PATCHES)
    if max_hellin is not None:
        hellin = hellin[: max(0, int(max_hellin))]
    if hellin:
        dst = out_root / copy_hellin_to
        actions.append(
            {
                "action": "add_w3_hellin_train_pool",
                "src": str(HELLIN_PATCHES.as_posix()),
                "dst": str(dst.as_posix()),
                "n": len(hellin),
                "source_id": HELLIN_SOURCE_ID,
                "note": (
                    "Hellín may be train-pool-only; D3 KEEP gate requires "
                    "new-fire LOFO fold with n_test>=50"
                ),
            }
        )
        if not dry_run:
            dst.mkdir(parents=True, exist_ok=True)
            for p in hellin:
                # prefix to avoid name collisions
                shutil.copy2(p, dst / f"w3_hellin_{p.name}")
    else:
        actions.append(
            {
                "action": "skip_hellin",
                "reason": "no patches under outputs/ml_eval/w3/hellin_2024/patches",
            }
        )

    plan["actions"] = actions
    if not dry_run:
        out_root.mkdir(parents=True, exist_ok=True)
        (out_root / "stage_manifest.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
    return plan


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out-root", type=Path, default=DEFAULT_OUT)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument(
        "--copy-hellin-to",
        type=str,
        default="train",
        choices=["train", "val"],
        help="Split to place Hellín train-pool patches (default train)",
    )
    p.add_argument("--max-hellin", type=int, default=None)
    args = p.parse_args(argv)

    plan = stage(
        args.out_root.resolve(),
        dry_run=bool(args.dry_run),
        copy_hellin_to=args.copy_hellin_to,
        max_hellin=args.max_hellin,
    )
    print(json.dumps(plan, indent=2))
    return 0 if plan.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
