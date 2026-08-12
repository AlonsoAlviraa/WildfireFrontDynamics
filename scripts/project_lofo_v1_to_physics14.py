#!/usr/bin/env python3
"""Project sealed lofo_v1 (legacy17) → physics14 pack for schema-bridge A/B.

Writes ``artifacts/clm_ndws_patches/lofo_v1_projected_physics14`` with same
fold layout. Stamps work_class=schema_bridge_projected (NOT geotiff spatial_v1).

Usage::

    $env:PYTHONPATH = "."
    python scripts/project_lofo_v1_to_physics14.py
    python scripts/project_lofo_v1_to_physics14.py --max-per-split 32  # smoke
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.ml.schema_bridge import project_legacy17_to_physics14  # noqa: E402

CORE3 = ("CARDOSO", "LA_ESTRELLA_ACOM1", "LA_ESTRELLA_ACOM2")
DEFAULT_SRC = ROOT / "artifacts" / "clm_ndws_patches" / "lofo_v1"
DEFAULT_OUT = ROOT / "artifacts" / "clm_ndws_patches" / "lofo_v1_projected_physics14"


def project_file(src: Path, dst: Path) -> dict:
    with np.load(src, allow_pickle=True) as z:
        seq = np.asarray(z["sequence"], dtype=np.float32)
        if seq.ndim == 3:
            seq = seq[None, ...]
        frames = []
        masks = []
        stamp = {}
        for t in range(seq.shape[0]):
            p14, m, stamp = project_legacy17_to_physics14(seq[t])
            frames.append(p14)
            masks.append(m)
        out_seq = np.stack(frames, axis=0)
        out_mask = np.stack(masks, axis=0)
        payload = {
            "sequence": out_seq.astype(np.float32),
            "current_fire": np.asarray(z["current_fire"], dtype=np.float32),
            "target_fire": np.asarray(z["target_fire"], dtype=np.float32),
            "change_fraction": z["change_fraction"]
            if "change_fraction" in z.files
            else np.float32(0),
            "source": z["source"] if "source" in z.files else "unknown",
            "feature_schema": "physics14",
            "schema_path_id": "E2-P2-bridge",
            "work_class": "schema_bridge_projected",
            "missing_mask": out_mask.astype(np.float32),
            "bridge_stamp_json": np.asarray(json.dumps(stamp)),
            "in_channels": np.int32(14),
        }
    dst.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(dst, **payload)
    return {"ok": True, "shape": list(out_seq.shape)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src-root", type=Path, default=DEFAULT_SRC)
    ap.add_argument("--out-root", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--max-per-split", type=int, default=0, help="0 = all")
    ap.add_argument(
        "--manifest-out",
        type=Path,
        default=ROOT / "outputs" / "ml_eval" / "lofo_v1_projected_physics14_manifest.json",
    )
    args = ap.parse_args(argv)

    if not args.src_root.is_dir():
        print(f"missing {args.src_root}", file=sys.stderr)
        return 2

    n_ok = 0
    per_fold = {}
    for held in CORE3:
        per_fold[held] = {}
        for split in ("train", "val", "test"):
            src_d = args.src_root / held / split
            if not src_d.is_dir():
                continue
            files = sorted(src_d.glob("*.npz"))
            if args.max_per_split > 0:
                files = files[: args.max_per_split]
            for p in files:
                project_file(p, args.out_root / held / split / p.name)
                n_ok += 1
            per_fold[held][split] = len(files)

    man = {
        "schema": "wfd_lofo_v1_projected_physics14_v1",
        "created_utc": datetime.now(UTC).isoformat(),
        "work_class": "schema_bridge_projected",
        "feature_schema": "physics14",
        "source_schema": "legacy17",
        "src_root": str(args.src_root.as_posix()),
        "out_root": str(args.out_root.as_posix()),
        "n_files": n_ok,
        "folds": per_fold,
        "ml_product_go": False,
        "field_ops_allow_ml_live_in_fusion": False,
        "comparability": "not_same_as_sealed_legacy17_t1",
        "note": "Elevation GAP; temp_split_proxy. Use for partial multi_if init A/B only.",
    }
    args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_out.write_text(json.dumps(man, indent=2), encoding="utf-8")
    print(json.dumps(man, indent=2))
    return 0 if n_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
