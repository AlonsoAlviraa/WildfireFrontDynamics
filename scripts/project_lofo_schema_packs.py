#!/usr/bin/env python3
"""E2-P1: project sealed legacy17 LOFO packs → clean12_subset NPZ packs.

Default path for metrics-lift feature cleanup without re-emitting from geotiff.
Does **not** claim physics14. Does **not** mutate sealed holdout_v1 / lofo_v1
in place — writes under a new root.

Usage::

    $env:PYTHONPATH = "."
    python scripts/project_lofo_schema_packs.py --dry-run
    python scripts/project_lofo_schema_packs.py \\
        --src-lofo artifacts/clm_ndws_patches/lofo_v1 \\
        --out-root outputs/ml_eval/lofo_schema_clean12_subset
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

from wildfire_front.ml.feature_schema import (  # noqa: E402
    CLEAN12_SUBSET_HONESTY,
    CLEAN12_SUBSET_N_CHANNELS,
    legacy17_to_clean12_subset_map,
    project_sequence_legacy17_to_clean12_subset,
)

DEFAULT_SRC = ROOT / "artifacts" / "clm_ndws_patches" / "lofo_v1"
DEFAULT_OUT = ROOT / "outputs" / "ml_eval" / "lofo_schema_clean12_subset"


def _project_one(src: Path, dst: Path) -> dict[str, Any]:
    with np.load(src, allow_pickle=True) as z:
        files = list(z.files)
        seq = np.asarray(z["sequence"], dtype=np.float32)
        out_seq = project_sequence_legacy17_to_clean12_subset(seq)
        payload: dict[str, Any] = {"sequence": out_seq}
        for k in files:
            if k == "sequence":
                continue
            payload[k] = z[k]
        # honesty stamps inside NPZ
        payload["feature_schema"] = np.asarray("clean12_subset")
        payload["schema_path_id"] = np.asarray("E2-P1")
        payload["source_schema"] = np.asarray("legacy17")
        payload["in_channels"] = np.asarray(CLEAN12_SUBSET_N_CHANNELS, dtype=np.int32)
    dst.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(dst, **payload)
    return {
        "src": str(src.as_posix()),
        "dst": str(dst.as_posix()),
        "in_channels": CLEAN12_SUBSET_N_CHANNELS,
        "sequence_shape": list(out_seq.shape),
    }


def project_fold(
    src_fold: Path,
    dst_fold: Path,
    *,
    dry_run: bool = False,
    max_files: int | None = None,
) -> dict[str, Any]:
    counts = {"train": 0, "val": 0, "test": 0, "projected": 0, "skipped": 0}
    samples: list[dict[str, Any]] = []
    for split in ("train", "val", "test"):
        sdir = src_fold / split
        if not sdir.is_dir():
            continue
        files = sorted(sdir.glob("*.npz"))
        if max_files is not None:
            files = files[: max(0, int(max_files))]
        counts[split] = len(list((src_fold / split).glob("*.npz")))
        for p in files:
            d = dst_fold / split / p.name
            if dry_run:
                counts["projected"] += 1
                if len(samples) < 3:
                    samples.append({"src": str(p.as_posix()), "dst": str(d.as_posix())})
                continue
            try:
                row = _project_one(p, d)
                counts["projected"] += 1
                if len(samples) < 3:
                    samples.append(row)
            except (OSError, ValueError, KeyError) as exc:
                counts["skipped"] += 1
                if len(samples) < 5:
                    samples.append({"src": str(p.as_posix()), "error": str(exc)})
    return {
        "fold": src_fold.name,
        "src": str(src_fold.as_posix()),
        "dst": str(dst_fold.as_posix()),
        "counts": counts,
        "samples": samples,
    }


def training_summary_stub(out_root: Path) -> dict[str, Any]:
    m = legacy17_to_clean12_subset_map()
    return {
        "feature_schema": "clean12_subset",
        "schema_path_id": "E2-P1",
        "in_channels": m["in_channels_with_prev_fire"],
        "in_channels_features": m["in_channels_features"],
        "init_weights_path": None,
        "init_weights_channel_match": False,
        "note": (
            "Init weights only when channel count matches; "
            "else residual random init or matching-schema NDWS init"
        ),
        "schema_map": m,
        "honesty": CLEAN12_SUBSET_HONESTY,
        "out_root": str(out_root.as_posix()),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--src-lofo", type=Path, default=DEFAULT_SRC)
    p.add_argument("--out-root", type=Path, default=DEFAULT_OUT)
    p.add_argument("--schema", type=str, default="clean12", choices=["clean12"])
    p.add_argument("--dry-run", action="store_true")
    p.add_argument(
        "--max-files-per-split",
        type=int,
        default=None,
        help="Cap files per split (smoke / CI)",
    )
    p.add_argument("--folds", type=str, default=None, help="Comma-separated fold names")
    args = p.parse_args(argv)

    src_root = args.src_lofo.resolve()
    out_root = args.out_root.resolve()
    if not src_root.is_dir():
        print(json.dumps({"ok": False, "error": f"missing src-lofo: {src_root}"}))
        return 1

    fold_filter = None
    if args.folds:
        fold_filter = {x.strip() for x in args.folds.split(",") if x.strip()}

    folds = sorted(d for d in src_root.iterdir() if d.is_dir() and (d / "train").is_dir())
    if fold_filter:
        folds = [d for d in folds if d.name in fold_filter]

    fold_rows: list[dict[str, Any]] = []
    for fd in folds:
        fold_rows.append(
            project_fold(
                fd,
                out_root / fd.name,
                dry_run=bool(args.dry_run),
                max_files=args.max_files_per_split,
            )
        )

    stub = training_summary_stub(out_root)
    manifest = {
        "schema": "wfd_ml_lofo_schema_project_v1",
        "created_utc": datetime.now(UTC).isoformat(),
        "schema_path_id": "E2-P1",
        "feature_schema": "clean12_subset",
        "source_schema": "legacy17",
        "src_lofo": str(src_root.as_posix()),
        "out_root": str(out_root.as_posix()),
        "dry_run": bool(args.dry_run),
        "folds": fold_rows,
        "training_summary_stub": stub,
        "schema_map": legacy17_to_clean12_subset_map(),
        "honesty": CLEAN12_SUBSET_HONESTY,
        "physics14_claim": False,
        "mutated_sealed_holdout_v1": False,
    }
    if not args.dry_run:
        out_root.mkdir(parents=True, exist_ok=True)
        (out_root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        (out_root / "training_summary_stub.json").write_text(
            json.dumps(stub, indent=2), encoding="utf-8"
        )

    print(
        json.dumps(
            {
                "ok": True,
                "n_folds": len(fold_rows),
                "dry_run": args.dry_run,
                "out_root": str(out_root),
                "feature_schema": "clean12_subset",
                "schema_path_id": "E2-P1",
                "in_channels_features": 12,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
