#!/usr/bin/env python3
"""L5 leak audit for LOFO packs (train/val must not contain held-out source).

Writes ``outputs/ml_eval/lab_loop/lofo_pack_leak_audit_latest.json``.
Exit code: 0 if all folds clean (or empty); 2 if any leak found.

Usage::

    $env:PYTHONPATH = "."
    python scripts/audit_lofo_pack_leak.py --lofo-root artifacts/clm_ndws_patches/lofo_v1
    python scripts/audit_lofo_pack_leak.py --lofo-root artifacts/clm_ndws_patches/lofo_v2
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_OUT = ROOT / "outputs" / "ml_eval" / "lab_loop" / "lofo_pack_leak_audit_latest.json"


def audit_fold(fold_dir: Path, held: str | None = None) -> dict[str, Any]:
    """Audit one LOFO fold directory.

    Held-out source defaults to the fold directory name.
    """
    held_out = held or fold_dir.name
    counts = {"train": 0, "val": 0, "test": 0}
    leaked: list[str] = []
    test_held = 0
    test_foreign = 0
    unreadable = 0
    for split in ("train", "val", "test"):
        d = fold_dir / split
        if not d.is_dir():
            continue
        for p in d.glob("*.npz"):
            counts[split] += 1
            src = "unknown"
            try:
                with np.load(p, allow_pickle=True) as z:
                    if "source" in z.files:
                        src = str(z["source"])
            except OSError:
                unreadable += 1
                continue
            if split in ("train", "val") and src == held_out:
                leaked.append(f"{split}:{p.name}")
            if split == "test":
                if src == held_out:
                    test_held += 1
                else:
                    test_foreign += 1
    n_leaked = len(leaked)
    ok = n_leaked == 0 and test_foreign == 0 and (test_held > 0 or counts["test"] == 0)
    return {
        "ok": bool(ok),
        "held_out": held_out,
        "fold_dir": str(fold_dir.as_posix()),
        "counts": counts,
        "n_leaked_train_val": n_leaked,
        "leaked_examples": leaked[:50],
        "test_held_out": test_held,
        "test_foreign": test_foreign,
        "unreadable": unreadable,
    }


def audit_lofo_root(lofo_root: Path) -> dict[str, Any]:
    folds: dict[str, Any] = {}
    total_leaked = 0
    if not lofo_root.is_dir():
        return {
            "schema": "wfd_ml_lofo_pack_leak_audit_v1",
            "ok": False,
            "error": f"missing lofo-root: {lofo_root}",
            "lofo_root": str(lofo_root.as_posix()),
            "folds": {},
            "n_leaked_train_val": 0,
            "n_folds": 0,
        }
    for d in sorted(p for p in lofo_root.iterdir() if p.is_dir()):
        # skip non-fold dirs
        if not any((d / s).is_dir() for s in ("train", "val", "test")):
            continue
        row = audit_fold(d)
        folds[d.name] = row
        total_leaked += int(row.get("n_leaked_train_val") or 0)
    all_ok = all(bool(r.get("ok")) for r in folds.values()) if folds else True
    return {
        "schema": "wfd_ml_lofo_pack_leak_audit_v1",
        "created_utc": datetime.now(UTC).isoformat(),
        "lofo_root": str(lofo_root.as_posix()),
        "ok": bool(all_ok) and total_leaked == 0,
        "n_folds": len(folds),
        "n_leaked_train_val": total_leaked,
        "folds": folds,
        "product_rail": "lab_ml",
        "note": (
            "L5 source of truth for metrics-lift kill scorer. "
            "train/val must not contain held-out source id; test must be held-out."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--lofo-root",
        type=Path,
        default=ROOT / "artifacts" / "clm_ndws_patches" / "lofo_v1",
    )
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--repo", type=Path, default=ROOT)
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Still audit and write JSON; alias for normal run (compat)",
    )
    args = p.parse_args(argv)

    report = audit_lofo_root(args.lofo_root.resolve())
    out = args.out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": report.get("ok"),
                "out": str(out),
                "n_folds": report.get("n_folds"),
                "n_leaked_train_val": report.get("n_leaked_train_val"),
                "lofo_root": report.get("lofo_root"),
            },
            indent=2,
        )
    )
    if report.get("error"):
        return 1
    if int(report.get("n_leaked_train_val") or 0) > 0 or not report.get("ok"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
