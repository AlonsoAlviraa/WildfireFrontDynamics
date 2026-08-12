#!/usr/bin/env python3
"""Flatten spatial_v1_openmeteo fire dirs → holdout train → estrella_floor LOFO pack.

Weather provenance: open_meteo_archive_interp_v1 (NOT ERA5).
Builds core-3 LOFO for WEATHER_LIFT vs prior spatial bridge board (~0.558).

Usage::

    $env:PYTHONPATH = "."
    python scripts/build_spatial_openmeteo_lofo_pack.py
    python scripts/build_spatial_openmeteo_lofo_pack.py --require-fires CARDOSO,LA_ESTRELLA_ACOM1,LA_ESTRELLA_ACOM2
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from build_lofo_mix_v1 import CORE_SOURCES, build_mix_lofo  # noqa: E402

DEFAULT_SRC = ROOT / "artifacts" / "clm_ndws_patches" / "spatial_v1_openmeteo"
DEFAULT_FLAT = ROOT / "artifacts" / "clm_ndws_patches" / "holdout_spatial_v1_openmeteo"
DEFAULT_OUT = ROOT / "artifacts" / "clm_ndws_patches" / "lofo_mix_spatial_openmeteo_v1"
DEFAULT_MANIFEST = ROOT / "outputs" / "ml_eval" / "lofo_mix_spatial_openmeteo_v1_manifest.json"
CORE3 = ("CARDOSO", "LA_ESTRELLA_ACOM1", "LA_ESTRELLA_ACOM2")
EXPECTED_SEQ = (1, 14, 64, 64)


def flatten_fire_dirs(
    src_root: Path,
    flat_root: Path,
    *,
    require_fires: list[str],
    max_per_fire: int | None = None,
) -> dict[str, int]:
    if flat_root.exists():
        shutil.rmtree(flat_root)
    train = flat_root / "train"
    train.mkdir(parents=True)

    counts: dict[str, int] = {}
    missing = []
    for fire in require_fires:
        fdir = src_root / fire
        if not fdir.is_dir():
            missing.append(fire)
            continue
        n = 0
        for p in sorted(fdir.rglob("*.npz")):
            with np.load(p, allow_pickle=True) as z:
                if "sequence" not in z.files:
                    continue
                shape = tuple(z["sequence"].shape)
                if shape != EXPECTED_SEQ:
                    raise RuntimeError(f"bad shape {p}: {shape} expected {EXPECTED_SEQ}")
                src = (
                    str(z["source"].item())
                    if "source" in z.files and hasattr(z["source"], "item")
                    else fire
                )
            # unique name
            dest = train / f"{src}__{p.name}"
            if dest.exists():
                dest = train / f"{src}__{p.parent.name}_{p.name}"
            shutil.copy2(p, dest)
            n += 1
            if max_per_fire is not None and n >= max_per_fire:
                break
        counts[fire] = n
    if missing:
        raise SystemExit(f"missing fire dirs under {src_root}: {missing}")
    for fire in require_fires:
        if counts.get(fire, 0) < 20:
            raise SystemExit(f"insufficient patches for {fire}: {counts.get(fire, 0)}")
    return counts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src-root", type=Path, default=DEFAULT_SRC)
    ap.add_argument("--flat-root", type=Path, default=DEFAULT_FLAT)
    ap.add_argument("--out-root", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--manifest-out", type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument(
        "--require-fires",
        type=str,
        default=",".join(CORE3),
        help="Comma-separated fire ids that must be present",
    )
    ap.add_argument("--max-per-fire", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    require = [x.strip() for x in args.require_fires.split(",") if x.strip()]
    if not args.src_root.is_dir():
        print(f"BLOCKED: src missing {args.src_root}", file=sys.stderr)
        return 2

    counts = flatten_fire_dirs(
        args.src_root,
        args.flat_root,
        require_fires=require,
        max_per_fire=args.max_per_fire,
    )
    print("flattened", counts, flush=True)

    # Also include any extra fires present under src (hellin, braz, …) if complete
    for d in sorted(args.src_root.iterdir()):
        if not d.is_dir() or d.name in counts:
            continue
        n_npz = len(list(d.rglob("*.npz")))
        if n_npz < 20:
            print(f"skip incomplete extra {d.name} n={n_npz}", flush=True)
            continue
        n = 0
        for p in sorted(d.rglob("*.npz")):
            with np.load(p, allow_pickle=True) as z:
                shape = tuple(z["sequence"].shape)
                if shape != EXPECTED_SEQ:
                    print(f"skip bad shape {p} {shape}", flush=True)
                    continue
                src = (
                    str(z["source"].item())
                    if "source" in z.files and hasattr(z["source"], "item")
                    else d.name
                )
            dest = args.flat_root / "train" / f"{src}__{p.name}"
            if dest.exists():
                dest = args.flat_root / "train" / f"{src}__{p.parent.name}_{p.name}"
            shutil.copy2(p, dest)
            n += 1
        counts[d.name] = n
        print(f"extra {d.name} n={n}", flush=True)

    folds = [f for f in require if f in CORE_SOURCES]
    if args.dry_run:
        print(json.dumps({"counts": counts, "folds": folds, "dry_run": True}, indent=2))
        return 0

    man = build_mix_lofo(
        args.flat_root,
        args.out_root,
        folds=folds,
        exclude_tobarra=True,
        clean=True,
        dry_run=False,
    )
    man["weather_provenance"] = "open_meteo_archive_interp_v1"
    man["not_era5"] = True
    man["feature_schema"] = "spatial_v1"
    man["sequence_shape"] = list(EXPECTED_SEQ)
    man["source_patch_counts"] = counts
    man["work_class"] = "feature_spatial_v1+weather_openmeteo+estrella_floor"
    man["comparability"] = {
        "prior_spatial_bridge_mean": 0.5575550981918408,
        "prior_spatial_bridge_min": 0.48528418760127023,
        "weather_lift_threshold": 0.01,
        "note": "Same residual-small + bridge adapted init; weather raster provenance differs",
    }
    man["ml_product_go"] = True
    man["field_ops_allow_ml_live_in_fusion"] = False
    man["built_utc"] = datetime.now(UTC).isoformat()

    args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_out.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    # also write next to out
    (args.out_root / "mix_manifest.json").write_text(
        json.dumps(man, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "out_root": str(args.out_root.as_posix()),
                "manifest": str(args.manifest_out.as_posix()),
                "counts": counts,
                "folds": list((man.get("folds") or {}).keys()),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
