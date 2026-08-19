"""Stack Caldor clean17 GeoTIFFs into leakage-safe tensors with sin/cos encodings."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.open_if.caldor_temporal import (  # noqa: E402
    last_available_gridmet_day,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACK = ROOT / "data/open_if/external_bridge/US_FIREBENCH_CALDOR_2021"
DEFAULT_ACQUISITION = ROOT / "docs/CALDOR_CLEAN17_ACQUISITION.json"
CHANNEL_ORDER = (
    "slope_rad",
    "aspect_sin",
    "aspect_cos",
    "max_temperature_c",
    "min_temperature_c",
    "wind_speed_ms",
    "wind_sin",
    "wind_cos",
    "precipitation_mm_24h",
    "surface_pressure_hpa",
    "relative_humidity_pct",
    "total_cloud_cover_pct",
    "visibility_km",
    "dew_point_c",
    "canopy_height_m",
    "canopy_base_height_m",
    "canopy_bulk_density_kg_m3",
    "canopy_presence",
    "canopy_missing",
    "erc_g",
    "horizon_hours",
)


def _read(path: Path) -> np.ndarray:
    with rasterio.open(path) as dataset:
        return dataset.read(1).astype(np.float32)


def stack_pair(pack_root: Path, row: dict[str, Any]) -> dict[str, np.ndarray]:
    channels = row["channels"]
    slope = _read(pack_root / channels["slope_rad"]["path"])
    aspect = _read(pack_root / channels["aspect_rad"]["path"])
    wind_dir = _read(pack_root / channels["wind_direction_deg"]["path"])
    wind_rad = np.deg2rad(wind_dir)
    canopy = _read(pack_root / channels["canopy_height_m"]["path"])
    missing = (~np.isfinite(canopy)).astype(np.float32)
    arrays = {
        "slope_rad": slope,
        "aspect_sin": np.sin(aspect),
        "aspect_cos": np.cos(aspect),
        "max_temperature_c": _read(pack_root / channels["max_temperature_c"]["path"]),
        "min_temperature_c": _read(pack_root / channels["min_temperature_c"]["path"]),
        "wind_speed_ms": _read(pack_root / channels["wind_speed_ms"]["path"]),
        "wind_sin": np.sin(wind_rad),
        "wind_cos": np.cos(wind_rad),
        "precipitation_mm_24h": _read(
            pack_root / channels["precipitation_mm_24h"]["path"]
        ),
        "surface_pressure_hpa": _read(
            pack_root / channels["surface_pressure_hpa"]["path"]
        ),
        "relative_humidity_pct": _read(
            pack_root / channels["relative_humidity_pct"]["path"]
        ),
        "total_cloud_cover_pct": _read(
            pack_root / channels["total_cloud_cover_pct"]["path"]
        ),
        "visibility_km": _read(pack_root / channels["visibility_km"]["path"]),
        "dew_point_c": _read(pack_root / channels["dew_point_c"]["path"]),
        "canopy_height_m": np.nan_to_num(canopy, nan=0.0),
        "canopy_base_height_m": np.nan_to_num(
            _read(pack_root / channels["canopy_base_height_m"]["path"]), nan=0.0
        ),
        "canopy_bulk_density_kg_m3": np.nan_to_num(
            _read(pack_root / channels["canopy_bulk_density_kg_m3"]["path"]), nan=0.0
        ),
        "canopy_presence": np.nan_to_num(
            _read(pack_root / channels["canopy_presence"]["path"]), nan=0.0
        ),
        "canopy_missing": missing,
        "erc_g": _read(pack_root / channels["erc_g"]["path"]),
        "horizon_hours": np.full_like(slope, float(row["delta_hours"])),
    }
    stacked = np.stack([arrays[name] for name in CHANNEL_ORDER], axis=0)
    return {"features": stacked.astype(np.float32), "canopy_missing": missing}


def stack_pack(acquisition_path: Path, pack_root: Path) -> dict[str, Any]:
    acquisition = json.loads(acquisition_path.read_text(encoding="utf-8"))
    out_dir = pack_root / "tensors/clean17_physical_v1"
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[dict[str, Any]] = []
    for row in acquisition["dynamic"]:
        arrays = stack_pair(pack_root, row)
        name = f"{row['t0_utc'].replace(':', '')}_{row['t1_utc'].replace(':', '')}.npz"
        path = out_dir / name
        np.savez_compressed(
            path,
            features=arrays["features"],
            canopy_missing=arrays["canopy_missing"],
            t0_utc=row["t0_utc"],
            t1_utc=row["t1_utc"],
            delta_hours=float(row["delta_hours"]),
            channel_order=np.array(CHANNEL_ORDER),
            last_available_gridmet_day=last_available_gridmet_day(row["t0_utc"]).isoformat(),
            holdout_only=True,
        )
        written.append(
            {
                "path": path.relative_to(pack_root).as_posix(),
                "t0_utc": row["t0_utc"],
                "shape": list(arrays["features"].shape),
            }
        )
    report = {
        "schema": "wfd_caldor_clean17_tensors_v1",
        "n_tensors": len(written),
        "channel_order": list(CHANNEL_ORDER),
        "holdout_only": True,
        "legacy17_checkpoint_compatible": False,
        "files": written,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--acquisition", type=Path, default=DEFAULT_ACQUISITION)
    parser.add_argument("--pack-root", type=Path, default=DEFAULT_PACK)
    args = parser.parse_args()
    report = stack_pack(args.acquisition, args.pack_root)
    print(json.dumps({"n_tensors": report["n_tensors"], "holdout_only": True}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
