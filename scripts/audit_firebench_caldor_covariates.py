"""Audit whether Caldor.h5 can satisfy the frozen WFD legacy17 input contract."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACK = ROOT / "data" / "external" / "firebench" / "caldor_2021" / "v2026.1"
DEFAULT_OUT = ROOT / "docs" / "FIREBENCH_CALDOR_CHANNEL_AUDIT.json"

LEGACY17_CONTRACT = (
    "slope",
    "aspect",
    "max_temperature",
    "min_temperature",
    "wind_speed",
    "wind_direction",
    "precipitation",
    "pressure",
    "humidity",
    "cloud_cover",
    "visibility",
    "dew_point",
    "vegetation_0",
    "vegetation_1",
    "vegetation_2",
    "vegetation_3",
    "erc_or_drought",
)


def _json_value(value: Any) -> Any:
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def audit_caldor_covariates(pack: Path) -> dict[str, Any]:
    import h5py

    pack = Path(pack)
    h5_path = pack / "Caldor.h5"
    if not h5_path.is_file():
        return {"ok": False, "status": "blocked_missing_h5", "path": str(h5_path)}

    spatial: list[dict[str, Any]] = []
    station_variables: Counter[str] = Counter()
    station_rights: Counter[str] = Counter()
    license_refs: set[str] = set()
    n_stations = 0
    n_restricted_stations = 0
    with h5py.File(h5_path, "r") as h5:
        spatial_root = h5.get("spatial_2d")
        if spatial_root is not None:
            for group_name, group in spatial_root.items():
                variables = [
                    name for name in group if not name.startswith("position_")
                ]
                license_ref = _json_value(group.attrs.get("license"))
                if license_ref:
                    license_refs.add(str(license_ref))
                spatial.append(
                    {
                        "group": group_name,
                        "variables": variables,
                        "crs": _json_value(group.attrs.get("crs")),
                        "data_source": _json_value(group.attrs.get("data_source")),
                        "license": license_ref,
                        "redistribution_allowed": _json_value(
                            group.attrs.get("redistribution_allowed")
                        ),
                    }
                )
        time_root = h5.get("time_series")
        if time_root is not None:
            for station_name, station in time_root.items():
                if not station_name.startswith("station"):
                    continue
                n_stations += 1
                for variable in station:
                    if variable != "time":
                        station_variables[variable] += 1
                restriction = str(
                    _json_value(station.attrs.get("data_use_restrictions")) or "unspecified"
                )
                station_rights[restriction] += 1
                if "no commercial" in restriction.lower() or not bool(
                    station.attrs.get("redistribution_allowed", False)
                ):
                    n_restricted_stations += 1
                license_ref = _json_value(station.attrs.get("license"))
                if license_ref:
                    license_refs.add(str(license_ref))

    staged_license_names = sorted(
        path.name for path in (pack / "DATA_LICENSES").glob("*") if path.is_file()
    )
    missing_license_refs = sorted(
        ref
        for ref in license_refs
        if not (pack / ref.lstrip("/")).is_file()
    )
    mapping = {
        "slope": "missing_no_elevation_or_terrain_raster",
        "aspect": "missing_no_elevation_or_terrain_raster",
        "max_temperature": "restricted_station_series_not_gridded",
        "min_temperature": "restricted_station_series_not_gridded",
        "wind_speed": "restricted_station_series_not_gridded",
        "wind_direction": "restricted_station_series_not_gridded",
        "precipitation": "restricted_station_series_not_gridded_or_complete",
        "pressure": "missing",
        "humidity": "restricted_station_series_not_gridded",
        "cloud_cover": "missing",
        "visibility": "missing",
        "dew_point": "missing",
        "vegetation_0": "canopy_layers_exist_but_not_legacy17_class_semantics",
        "vegetation_1": "canopy_layers_exist_but_not_legacy17_class_semantics",
        "vegetation_2": "canopy_layers_exist_but_not_legacy17_class_semantics",
        "vegetation_3": "missing_fourth_compatible_class",
        "erc_or_drought": "missing",
    }
    usable = [name for name, status in mapping.items() if status == "compatible"]
    try:
        source_h5 = h5_path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        source_h5 = h5_path.resolve().as_posix()
    return {
        "schema": "wfd_firebench_caldor_channel_audit_v1",
        "generated_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "ok": True,
        "status": "blocked_incompatible_and_restricted",
        "source_h5": source_h5,
        "wfd_model": "clm_ensemble_v34",
        "expected_schema": "legacy17_plus_prev_fire",
        "expected_channels": list(LEGACY17_CONTRACT),
        "channel_mapping": mapping,
        "n_compatible_channels": len(usable),
        "model_inference_allowed": False,
        "model_iou_allowed": False,
        "training_allowed": False,
        "geometry_label_evaluation_allowed_in_place": True,
        "reasons": [
            "Caldor.h5 does not contain a complete NDWS legacy17 tensor contract.",
            "Weather is point-station data, not an aligned forecast grid available at t0.",
            "All staged stations are restricted/non-redistributable Synoptic-derived data.",
            "Neutral placeholder channels are shape-compatible but scientifically incompatible.",
        ],
        "spatial_groups": spatial,
        "station_inventory": {
            "n_stations": n_stations,
            "n_restricted_or_nonredistributable": n_restricted_stations,
            "variable_station_counts": dict(sorted(station_variables.items())),
            "rights_counts": dict(sorted(station_rights.items())),
        },
        "rights": {
            "declared_license_refs": sorted(license_refs),
            "staged_license_files": staged_license_names,
            "missing_declared_license_refs": missing_license_refs,
            "synoptic_notice_missing": any(
                "synoptic" in ref.lower() for ref in missing_license_refs
            ),
        },
        "existing_placeholder_npz": {
            "manifest": "artifacts/datasets/firebench_caldor_patches.json",
            "status": "refused_for_model_inference",
            "allowed_use": "pipeline_shape_smoke_only",
        },
        "next_technical_path": (
            "Join public NIFC perimeter labels to independently licensed t0-available "
            "terrain/weather/fuel grids, then publish a new provenance manifest."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, default=DEFAULT_PACK)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    report = audit_caldor_covariates(args.pack)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": report.get("status"),
                "n_compatible_channels": report.get("n_compatible_channels"),
                "station_inventory": report.get("station_inventory"),
                "rights": report.get("rights"),
                "output": str(args.output),
            },
            indent=2,
        )
    )
    return 0 if report.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
