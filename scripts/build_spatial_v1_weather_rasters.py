#!/usr/bin/env python3
"""Multi-fire weather inventory + staging for spatial_v1 re-emit.

Default is **offline inventory** of ``data/weather/<fire>/``. Does **not** invent
constant geotiffs and stamp them as spatial.

Usage::

    $env:PYTHONPATH = "."
    # Inventory all core fires (writes manifest; exit 1 if any GAP)
    python scripts/build_spatial_v1_weather_rasters.py --inventory-only

    # Stage real gridded geotiffs into canonical weather_dir
    python scripts/build_spatial_v1_weather_rasters.py --fire tobarra_20240802 \\
        --stage-tmin path/tmin.tif --stage-tmax path/tmax.tif \\
        --stage-humidity path/rh.tif --stage-wind-speed path/ws.tif \\
        --stage-wind-dir path/wd.tif --stage-precip path/pr.tif

    # Require spatial weather present (exit 2 if missing)
    python scripts/build_spatial_v1_weather_rasters.py --inventory-only --require-weather-spatial

Exit codes:
  0 — all inventoried fires have no weather/fuel GAPs (rare offline)
  1 — inventory written; honest GAPs remain (default expected offline)
  2 — blocked: --require-* condition failed
  3 — hard error (unknown fire, stage failure with nothing written)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.fuel.spatial_v1_sources import (  # noqa: E402
    CORE_SPATIAL_FIRES,
    EXIT_ERROR,
    EXIT_OK,
    EXIT_PARTIAL,
    exit_code_from_inventory,
    get_fire_spec,
    inventory_all_fires,
    inventory_fire,
    list_core_source_ids,
    stage_weather_dir_from_sources,
    weather_dir_for,
    write_inventory_manifest,
)

DEFAULT_MANIFEST = ROOT / "outputs" / "ml_eval" / "spatial_v1_weather_fuel_inventory.json"


def _parse_fires(raw: str | None) -> list[str]:
    if not raw:
        return list_core_source_ids()
    out: list[str] = []
    for part in raw.replace(";", ",").split(","):
        p = part.strip()
        if not p:
            continue
        # allow dem_key / weather_key aliases
        if p in CORE_SPATIAL_FIRES:
            out.append(p)
            continue
        matched = None
        for sid, spec in CORE_SPATIAL_FIRES.items():
            if p in {spec.dem_key, spec.weather_key, spec.fuel_key}:
                matched = sid
                break
        if matched is None:
            raise SystemExit(f"unknown fire {p!r}; known={list_core_source_ids()}")
        out.append(matched)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--fire",
        type=str,
        default=None,
        help="Comma-separated source_id or dem_key (default: all core fires)",
    )
    ap.add_argument(
        "--inventory-only",
        action="store_true",
        help="Only inventory; do not stage (default when no --stage-* given)",
    )
    ap.add_argument(
        "--manifest-out",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Inventory JSON path",
    )
    ap.add_argument(
        "--require-weather-spatial",
        action="store_true",
        help="Exit 2 if any fire lacks ≥1 spatial weather raster",
    )
    ap.add_argument(
        "--require-full-weather-core",
        action="store_true",
        help="Exit 2 if any fire lacks full core spatial weather set",
    )
    ap.add_argument(
        "--require-fuel-spatial",
        action="store_true",
        help="Exit 2 if any fire lacks spatial fuel/NDVI",
    )
    ap.add_argument(
        "--allow-constant-stage",
        action="store_true",
        help="Allow staging near-constant geotiffs (still stamped; NOT recommended)",
    )
    # Stage inputs (real geotiffs only)
    ap.add_argument("--stage-tmin", type=Path, default=None)
    ap.add_argument("--stage-tmax", type=Path, default=None)
    ap.add_argument("--stage-temp", type=Path, default=None)
    ap.add_argument("--stage-humidity", type=Path, default=None)
    ap.add_argument("--stage-rh", type=Path, default=None)
    ap.add_argument("--stage-wind-speed", type=Path, default=None)
    ap.add_argument("--stage-wind-dir", type=Path, default=None)
    ap.add_argument("--stage-precip", type=Path, default=None)
    ap.add_argument("--stage-erc", type=Path, default=None)
    ap.add_argument(
        "--weather-out-dir",
        type=Path,
        default=None,
        help="Override weather_dir (default data/weather/<weather_key>/)",
    )
    ap.add_argument(
        "--allow-download",
        action="store_true",
        help=(
            "Opt-in network (reserved). Gridded reanalysis download is not auto-"
            "implemented; use --stage-* with operator-provided geotiffs. "
            "AEMET station JSON remains scalar (non-spatial)."
        ),
    )
    args = ap.parse_args(argv)

    try:
        fires = _parse_fires(args.fire)
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_ERROR

    stage_map_template: dict[str, Path] = {}
    for key, attr in (
        ("tmin", "stage_tmin"),
        ("tmax", "stage_tmax"),
        ("temp", "stage_temp"),
        ("humidity", "stage_humidity"),
        ("rh", "stage_rh"),
        ("wind_speed", "stage_wind_speed"),
        ("wind_dir", "stage_wind_dir"),
        ("precip", "stage_precip"),
        ("erc", "stage_erc"),
    ):
        val = getattr(args, attr)
        if val is not None:
            stage_map_template[key] = Path(val)

    do_stage = bool(stage_map_template) and not args.inventory_only
    if args.inventory_only and stage_map_template:
        print(
            "NOTE: --inventory-only set; ignoring --stage-* paths",
            file=sys.stderr,
        )
        do_stage = False

    if args.allow_download:
        print(
            json.dumps(
                {
                    "allow_download": True,
                    "status": "gap_gridded_download_not_auto",
                    "note": (
                        "No automatic gridded weather download. Provide ERA5/"
                        "reanalysis/AEMET gridded geotiffs via --stage-* . "
                        "AEMET open-data station API is scalar-only "
                        "(scripts/build_aemet_weather_scenario.py)."
                    ),
                },
                indent=2,
            ),
            file=sys.stderr,
        )

    stage_reports: dict[str, Any] = {}
    if do_stage:
        if len(fires) != 1:
            print(
                "Staging requires exactly one --fire (got "
                f"{len(fires)}). Run per-fire with --stage-* paths.",
                file=sys.stderr,
            )
            return EXIT_ERROR
        sid = fires[0]
        spec = get_fire_spec(sid)
        dest = args.weather_out_dir or weather_dir_for(spec, repo_root=ROOT)
        try:
            report = stage_weather_dir_from_sources(
                dest,
                stage_map_template,
                refuse_constant=not bool(args.allow_constant_stage),
            )
        except Exception as exc:  # noqa: BLE001
            print(f"stage failed: {exc}", file=sys.stderr)
            return EXIT_ERROR
        stage_reports[sid] = report
        if not report.get("staged") and report.get("refused"):
            print(json.dumps(report, indent=2, default=str))
            return EXIT_ERROR
        print(json.dumps({"stage": report}, indent=2, default=str))

    manifest = inventory_all_fires(repo_root=ROOT, source_ids=fires)
    if stage_reports:
        manifest["stage_reports"] = stage_reports
        # When staged to a non-canonical --weather-out-dir, re-inventory that
        # path so exit codes / per_fire_gaps match what was just staged.
        for sid, report in stage_reports.items():
            dest_s = report.get("dest_dir")
            if not dest_s:
                continue
            dest = Path(dest_s)
            canonical = weather_dir_for(get_fire_spec(sid), repo_root=ROOT)
            inv = inventory_fire(sid, repo_root=ROOT, weather_dir=dest)
            inv_d = inv.to_dict()
            inv_d["weather_dir_override"] = str(dest.as_posix())
            inv_d["weather_dir_canonical"] = str(canonical.as_posix())
            if dest.resolve() != canonical.resolve():
                inv_d["notes"] = list(inv_d.get("notes") or []) + [
                    "inventory_uses_weather_out_dir_override_not_canonical"
                ]
                print(
                    f"NOTE: inventory for {sid} uses --weather-out-dir "
                    f"{dest.as_posix()} (canonical would be {canonical.as_posix()})",
                    file=sys.stderr,
                )
            manifest["fires"][sid] = inv_d
        # Recompute aggregate weather/fuel counts after override merge
        n_full = n_partial = n_fuel = 0
        for _sid, finv in (manifest.get("fires") or {}).items():
            wx = finv.get("weather") or {}
            fuel = finv.get("fuel") or {}
            if wx.get("weather_full_core"):
                n_full += 1
            elif wx.get("weather_spatial_available"):
                n_partial += 1
            if fuel.get("fuel_or_ndvi_spatial"):
                n_fuel += 1
        manifest["n_weather_full_core"] = n_full
        manifest["n_weather_partial"] = n_partial
        manifest["n_fuel_spatial"] = n_fuel
    man_path = write_inventory_manifest(manifest, args.manifest_out)
    manifest["manifest_out"] = str(man_path.as_posix())

    # Compact stdout summary
    summary = {
        "manifest_out": str(man_path.as_posix()),
        "n_fires": manifest["n_fires"],
        "n_weather_full_core": manifest["n_weather_full_core"],
        "n_weather_partial": manifest["n_weather_partial"],
        "n_fuel_spatial": manifest["n_fuel_spatial"],
        "per_fire_gaps": {sid: (manifest["fires"][sid].get("gaps") or []) for sid in fires},
    }
    print(json.dumps(summary, indent=2))
    print(f"Wrote {man_path}", file=sys.stderr)

    code = exit_code_from_inventory(
        manifest,
        require_weather_spatial=bool(args.require_weather_spatial),
        require_fuel_spatial=bool(args.require_fuel_spatial),
        require_full_weather_core=bool(args.require_full_weather_core),
    )
    # After successful stage of partial rasters, still partial (1) unless full core
    if do_stage and code == EXIT_OK:
        return EXIT_OK
    if do_stage and code == EXIT_PARTIAL:
        # staging succeeded but gaps remain → 1 is honest
        return EXIT_PARTIAL
    return code


if __name__ == "__main__":
    raise SystemExit(main())
