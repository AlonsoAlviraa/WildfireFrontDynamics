#!/usr/bin/env python3
"""Full spatial_v1 re-emit from aligned chains + GLO-30 DEM.

Auto-discovers multi-fire weather/fuel under::

    data/weather/<weather_key>/
    data/fuel_map/<fuel_key>/

when present. Scalar weather fallback is non-spatial (honest GAP).

Usage::

    $env:PYTHONPATH = ".;scripts"
    python scripts/run_spatial_v1_full_reemit.py
    python scripts/run_spatial_v1_full_reemit.py --inventory-only
    python scripts/run_spatial_v1_full_reemit.py --require-weather-spatial
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from reemit_spatial_v1_patches import export_patches_spatial_v1  # noqa: E402

from wildfire_front.fuel.spatial_v1_sources import (  # noqa: E402
    EXIT_BLOCKED,
    EXIT_ERROR,
    EXIT_OK,
    EXIT_PARTIAL,
    default_weather_scalars,
    exit_code_from_inventory,
    inventory_all_fires,
    list_core_source_ids,
    resolve_dem_path,
    resolve_fuel_path,
    resolve_ndvi_path,
    resolve_source_id,
    resolve_weather_dir,
    write_inventory_manifest,
)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--fire",
        type=str,
        default=None,
        help="Comma-separated source_id or dem/weather/fuel key (default: all core)",
    )
    ap.add_argument(
        "--inventory-only",
        action="store_true",
        help="Only write weather/fuel discovery inventory; no patch emit",
    )
    ap.add_argument(
        "--require-weather-spatial",
        action="store_true",
        help="Exit 2 if any selected fire lacks spatial weather rasters",
    )
    ap.add_argument(
        "--require-full-weather-core",
        action="store_true",
        help="Exit 2 if any selected fire lacks full core spatial weather set",
    )
    ap.add_argument(
        "--require-fuel-spatial",
        action="store_true",
        help="Exit 2 if any selected fire lacks spatial fuel/NDVI",
    )
    ap.add_argument(
        "--refuse-scalar-weather",
        action="store_true",
        help="Pass through to re-emit: block when weather rasters missing",
    )
    ap.add_argument("--max-patches-per-chain", type=int, default=40)
    ap.add_argument(
        "--align-root",
        type=Path,
        default=ROOT / "artifacts" / "aligned_spatial_v1",
    )
    ap.add_argument(
        "--out-root",
        type=Path,
        default=ROOT / "artifacts" / "clm_ndws_patches" / "spatial_v1",
    )
    ap.add_argument(
        "--manifest-out",
        type=Path,
        default=ROOT / "outputs" / "ml_eval" / "spatial_v1_reemit_report.json",
    )
    ap.add_argument(
        "--inventory-out",
        type=Path,
        default=ROOT / "outputs" / "ml_eval" / "spatial_v1_weather_fuel_inventory.json",
    )
    args = ap.parse_args(argv)

    if args.fire:
        source_ids = []
        for part in args.fire.replace(";", ",").split(","):
            p = part.strip()
            if not p:
                continue
            try:
                source_ids.append(resolve_source_id(p))
            except KeyError as exc:
                print(str(exc), file=sys.stderr)
                return EXIT_ERROR
    else:
        source_ids = list_core_source_ids()

    # Always refresh multi-fire discovery inventory
    inv_manifest = inventory_all_fires(repo_root=ROOT, source_ids=source_ids)
    inv_path = write_inventory_manifest(inv_manifest, args.inventory_out)
    print(f"Inventory → {inv_path}", file=sys.stderr)

    if args.inventory_only:
        print(
            json.dumps(
                {
                    "inventory_out": str(inv_path.as_posix()),
                    "n_weather_full_core": inv_manifest["n_weather_full_core"],
                    "n_weather_partial": inv_manifest["n_weather_partial"],
                    "n_fuel_spatial": inv_manifest["n_fuel_spatial"],
                    "per_fire_gaps": {
                        sid: inv_manifest["fires"][sid].get("gaps") for sid in source_ids
                    },
                },
                indent=2,
            )
        )
        return exit_code_from_inventory(
            inv_manifest,
            require_weather_spatial=bool(args.require_weather_spatial),
            require_fuel_spatial=bool(args.require_fuel_spatial),
            require_full_weather_core=bool(args.require_full_weather_core),
        )

    # Preflight require-* before long emit
    pre = exit_code_from_inventory(
        inv_manifest,
        require_weather_spatial=bool(args.require_weather_spatial),
        require_fuel_spatial=bool(args.require_fuel_spatial),
        require_full_weather_core=bool(args.require_full_weather_core),
    )
    if pre == EXIT_BLOCKED:
        print(
            "BLOCKED: require-* spatial sources missing; see inventory",
            file=sys.stderr,
        )
        print(
            json.dumps(
                {
                    "inventory_out": str(inv_path.as_posix()),
                    "per_fire_gaps": {
                        sid: inv_manifest["fires"][sid].get("gaps") for sid in source_ids
                    },
                },
                indent=2,
            )
        )
        return EXIT_BLOCKED

    align_root = Path(args.align_root)
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    reports: dict = {}

    for sid in source_ids:
        chains_dir = align_root / sid / "chains"
        dem = resolve_dem_path(sid, repo_root=ROOT)
        # require_spatial: skip constant-only weather dirs (honest non-spatial)
        weather_dir = resolve_weather_dir(sid, repo_root=ROOT, require_spatial=True)
        fuel = resolve_fuel_path(sid, repo_root=ROOT)
        ndvi = resolve_ndvi_path(sid, repo_root=ROOT)
        scalars = default_weather_scalars(sid)
        fire_inv = inv_manifest["fires"].get(sid) or {}

        if not chains_dir.is_dir() or dem is None or not dem.is_file():
            reports[sid] = {
                "ok": False,
                "error": "missing_align_or_dem",
                "gaps": fire_inv.get("gaps"),
                "weather_dir": str(weather_dir.as_posix()) if weather_dir else None,
                "fuel_path": str(fuel.as_posix()) if fuel else None,
            }
            print(sid, "SKIP missing_align_or_dem")
            continue

        out_dir = out_root / sid
        out_dir.mkdir(parents=True, exist_ok=True)
        for old in out_dir.glob("*.npz"):
            old.unlink()
        for old in out_dir.glob("*_manifest.json"):
            old.unlink()

        total = 0
        chain_reports: list = []
        for chain in sorted(chains_dir.iterdir()):
            if not chain.is_dir():
                continue
            images = chain / "lwir"
            masks = chain / "masks"
            if not images.is_dir():
                images = chain / "images"
            n_i = len(list(images.glob("*.tif"))) if images.is_dir() else 0
            n_m = len(list(masks.glob("*.tif"))) if masks.is_dir() else 0
            if n_i < 2 or n_m < 1:
                chain_reports.append({"chain": chain.name, "skip": True, "n_i": n_i, "n_m": n_m})
                continue

            tmp = out_dir / f"_tmp_{chain.name}"
            try:
                plan = export_patches_spatial_v1(
                    images_dir=images,
                    masks_dir=masks,
                    output_dir=tmp,
                    dem_path=dem,
                    weather_dir=weather_dir,
                    fuel_path=fuel,
                    ndvi_path=ndvi,
                    weather_scalars=scalars,
                    source_id=sid,
                    patch_size=64,
                    # Cap per chain so full multi-fire re-emit finishes offline;
                    # dense sampling without cap can explode to thousands/chain.
                    max_patches=int(args.max_patches_per_chain),
                    dry_run=False,
                    refuse_scalar_weather=bool(args.refuse_scalar_weather),
                )
                n = int(plan.get("n_patches") or 0)
                if tmp.is_dir():
                    for p in tmp.glob("*.npz"):
                        dest = out_dir / f"{chain.name}_{p.name}"
                        p.replace(dest)
                        total += 1
                    man = tmp / "manifest.json"
                    if man.is_file():
                        man.replace(out_dir / f"{chain.name}_manifest.json")
                    shutil.rmtree(tmp, ignore_errors=True)

                gaps = plan.get("gaps")
                chain_reports.append(
                    {
                        "chain": chain.name,
                        "n_patches": n,
                        "gaps": gaps,
                        "ok": plan.get("ok"),
                        "blocked": plan.get("blocked"),
                        "error": plan.get("error"),
                        "dem_is_spatial": (plan.get("field_meta") or {}).get("dem_is_spatial"),
                        "weather_is_spatial": (plan.get("field_meta") or {}).get(
                            "weather_is_spatial"
                        ),
                        "fuel_is_spatial": (plan.get("field_meta") or {}).get("fuel_is_spatial"),
                    }
                )
                print(f"  {sid}/{chain.name}: n={n} gaps={gaps}")
            except Exception as exc:  # noqa: BLE001
                chain_reports.append({"chain": chain.name, "error": str(exc)})
                print(f"  {sid}/{chain.name}: FAIL {exc}")
                if tmp.exists():
                    shutil.rmtree(tmp, ignore_errors=True)

        reports[sid] = {
            "ok": total > 0,
            "n_patches": total,
            "n_chains": len(chain_reports),
            "chains": chain_reports,
            "feature_schema": "spatial_v1",
            "schema_path_id": "E2-P2",
            "work_class": "feature_spatial_v1",
            "weather_dir": str(weather_dir.as_posix()) if weather_dir else None,
            "fuel_path": str(fuel.as_posix()) if fuel else None,
            "ndvi_path": str(ndvi.as_posix()) if ndvi else None,
            "dem_path": str(dem.as_posix()) if dem else None,
            "inventory_gaps": fire_inv.get("gaps"),
            "weather_spatial_available": (fire_inv.get("weather") or {}).get(
                "weather_spatial_available"
            ),
            "fuel_or_ndvi_spatial": (fire_inv.get("fuel") or {}).get("fuel_or_ndvi_spatial"),
        }
        print(f"=== {sid} TOTAL {total} patches ===")

    man_out = Path(args.manifest_out)
    man_out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "fires": reports,
        "inventory_out": str(inv_path.as_posix()),
        "feature_schema": "spatial_v1",
        "schema_path_id": "E2-P2",
        "work_class": "feature_spatial_v1",
        "honesty": {
            "auto_discover_weather_fuel": True,
            "no_invented_constant_weather_as_spatial": True,
            "scalar_weather_is_non_spatial": True,
        },
    }
    man_out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    summary = {
        k: {
            "ok": v.get("ok"),
            "n": v.get("n_patches"),
            "weather_dir": v.get("weather_dir"),
            "fuel_path": v.get("fuel_path"),
            "gaps": v.get("inventory_gaps"),
        }
        for k, v in reports.items()
    }
    print("REEMIT DONE")
    print(json.dumps(summary, indent=2))
    print(f"Wrote {man_out}")
    if any(v.get("ok") for v in reports.values()):
        # Still partial if inventory had weather/fuel GAPs
        inv_code = exit_code_from_inventory(inv_manifest)
        return EXIT_OK if inv_code == EXIT_OK else EXIT_PARTIAL
    return EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
