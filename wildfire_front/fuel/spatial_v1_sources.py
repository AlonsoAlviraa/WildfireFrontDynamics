"""Multi-fire spatial_v1 weather + fuel path resolution and honest inventory.

Layout (canonical)::

    data/dem/<dem_key>/glo30_window.tif
    data/weather/<weather_key>/{tmin,tmax,humidity|rh,wind_speed,wind_dir,precip}.tif
    data/fuel_map/<fuel_key>/worldcover_window.tif
    data/fuel_map/<fuel_key>/ndvi.tif   (optional)

Honesty rails:
- Never invent constant weather grids and stamp them as spatial variance.
- Scalar AEMET / map-note scenarios may feed re-emit as non-spatial fallbacks only.
- Download paths are opt-in (``allow_download``); default is offline inventory/resolve.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

# Expected weather geotiff basenames consumed by reemit_spatial_v1_patches
WEATHER_CORE_FILES: tuple[str, ...] = (
    "tmin.tif",
    "tmax.tif",
    "humidity.tif",  # or rh.tif (alias)
    "wind_speed.tif",
    "wind_dir.tif",
    "precip.tif",
)
WEATHER_OPTIONAL_FILES: tuple[str, ...] = (
    "temp.tif",
    "rh.tif",
    "erc.tif",
)
# Canonical names after staging (rh → humidity when humidity missing)
WEATHER_CANONICAL_KEYS: tuple[str, ...] = (
    "tmin",
    "tmax",
    "humidity",
    "wind_speed",
    "wind_dir",
    "precip",
)

# Minimum spatial std to accept a staged raster as truly spatial
_SPATIAL_STD_MIN = 1e-6

# Scalar weather used by full re-emit when rasters missing (non-spatial stamp)
DEFAULT_WEATHER_SCALARS: dict[str, dict[str, float]] = {
    "CARDOSO": {
        "temp": 35.0,
        "humidity": 18.0,
        "wind_speed": 5.0,
        "wind_dir": 90.0,
        "precip": 0.0,
    },
    "LA_ESTRELLA_ACOM1": {
        "temp": 37.0,
        "humidity": 16.0,
        "wind_speed": 5.0,
        "wind_dir": 90.0,
        "precip": 0.0,
    },
    "LA_ESTRELLA_ACOM2": {
        "temp": 37.0,
        "humidity": 16.0,
        "wind_speed": 5.0,
        "wind_dir": 90.0,
        "precip": 0.0,
    },
    "hellin_2024": {
        "temp": 36.0,
        "humidity": 20.0,
        "wind_speed": 5.0,
        "wind_dir": 90.0,
        "precip": 0.0,
    },
    "tobarra_20240802": {
        "temp": 36.0,
        "humidity": 18.0,
        "wind_speed": 4.4,
        "wind_dir": 270.0,
        "precip": 0.0,
    },
    "brazatortas_2025": {
        "temp": 28.0,
        "humidity": 35.0,
        "wind_speed": 5.0,
        "wind_dir": 90.0,
        "precip": 0.0,
    },
    "retuerta_2025": {
        "temp": 32.0,
        "humidity": 25.0,
        "wind_speed": 5.0,
        "wind_dir": 90.0,
        "precip": 0.0,
    },
}


@dataclass(frozen=True)
class SpatialFireSpec:
    """One core fire in the spatial_v1 multi-fire set."""

    source_id: str
    dem_key: str
    weather_key: str
    fuel_key: str
    date: str  # primary fire day YYYY-MM-DD (for AEMET / operator fetch)
    aemet_station: str | None = None
    notes: tuple[str, ...] = ()

    @property
    def keys(self) -> dict[str, str]:
        return {
            "source_id": self.source_id,
            "dem_key": self.dem_key,
            "weather_key": self.weather_key,
            "fuel_key": self.fuel_key,
        }


# Source ids match run_spatial_v1_full_reemit / LOFO pack names
CORE_SPATIAL_FIRES: dict[str, SpatialFireSpec] = {
    "CARDOSO": SpatialFireSpec(
        source_id="CARDOSO",
        dem_key="cardoso",
        weather_key="cardoso",
        fuel_key="cardoso",
        date="2025-09-22",
        notes=("Guadalajara / Cardoso de la Sierra multi-day IF",),
    ),
    "LA_ESTRELLA_ACOM1": SpatialFireSpec(
        source_id="LA_ESTRELLA_ACOM1",
        dem_key="la_estrella_acom1",
        weather_key="la_estrella_acom1",
        fuel_key="la_estrella_acom1",
        date="2024-08-06",
        notes=("La Estrella ACOM1 LWIR pack",),
    ),
    "LA_ESTRELLA_ACOM2": SpatialFireSpec(
        source_id="LA_ESTRELLA_ACOM2",
        dem_key="la_estrella_acom2",
        weather_key="la_estrella_acom2",
        fuel_key="la_estrella_acom2",
        date="2024-08-06",
        notes=("La Estrella ACOM2 thin chain set",),
    ),
    "hellin_2024": SpatialFireSpec(
        source_id="hellin_2024",
        dem_key="hellin",
        weather_key="hellin",
        fuel_key="hellin",
        date="2024-07-19",
        aemet_station="8175",
        notes=("Hellín 2024; Albacete region station hint 8175",),
    ),
    "tobarra_20240802": SpatialFireSpec(
        source_id="tobarra_20240802",
        dem_key="tobarra",
        weather_key="tobarra",
        fuel_key="tobarra",
        date="2024-08-02",
        aemet_station="8175",
        notes=("Tobarra; WorldCover fuel may already be cached",),
    ),
    "brazatortas_2025": SpatialFireSpec(
        source_id="brazatortas_2025",
        dem_key="brazatortas",
        weather_key="brazatortas",
        fuel_key="brazatortas",
        date="2025-10-05",
    ),
    "retuerta_2025": SpatialFireSpec(
        source_id="retuerta_2025",
        dem_key="retuerta",
        weather_key="retuerta",
        fuel_key="retuerta",
        date="2025-09-04",
    ),
}


def list_core_source_ids() -> list[str]:
    return list(CORE_SPATIAL_FIRES.keys())


def get_fire_spec(source_id: str) -> SpatialFireSpec:
    if source_id not in CORE_SPATIAL_FIRES:
        raise KeyError(
            f"unknown spatial_v1 source_id={source_id!r}; known={list_core_source_ids()}"
        )
    return CORE_SPATIAL_FIRES[source_id]


def repo_data_root(repo_root: Path | str | None = None) -> Path:
    if repo_root is not None:
        return Path(repo_root)
    # wildfire_front/fuel/spatial_v1_sources.py → parents[2] = repo root
    return Path(__file__).resolve().parents[2]


def dem_dir(spec: SpatialFireSpec, *, repo_root: Path | str | None = None) -> Path:
    root = repo_data_root(repo_root)
    return root / "data" / "dem" / spec.dem_key


def weather_dir_for(spec: SpatialFireSpec, *, repo_root: Path | str | None = None) -> Path:
    root = repo_data_root(repo_root)
    return root / "data" / "weather" / spec.weather_key


def fuel_dir_for(spec: SpatialFireSpec, *, repo_root: Path | str | None = None) -> Path:
    root = repo_data_root(repo_root)
    return root / "data" / "fuel_map" / spec.fuel_key


def resolve_dem_path(
    source_id: str,
    *,
    repo_root: Path | str | None = None,
    explicit: Path | str | None = None,
) -> Path | None:
    if explicit is not None:
        p = Path(explicit)
        return p if p.is_file() else None
    spec = get_fire_spec(source_id)
    candidate = dem_dir(spec, repo_root=repo_root) / "glo30_window.tif"
    return candidate if candidate.is_file() else None


def resolve_weather_dir(
    source_id: str,
    *,
    repo_root: Path | str | None = None,
    explicit: Path | str | None = None,
    require_any_raster: bool = False,
    require_spatial: bool = False,
) -> Path | None:
    """Return weather_dir if present.

    ``require_any_raster``: dir must contain ≥1 known weather geotiff name.
    ``require_spatial``: dir must pass ``inventory_weather_dir`` spatial check
    (at least one raster with non-trivial variance). Constant-only dirs return
    None — they must not be auto-discovered as spatial weather sources.
    """
    if explicit is not None:
        p = Path(explicit)
        if not p.is_dir():
            return None
        d = p
    else:
        spec = get_fire_spec(source_id)
        d = weather_dir_for(spec, repo_root=repo_root)
        if not d.is_dir():
            return None

    if require_spatial:
        inv = inventory_weather_dir(d)
        if not inv.get("weather_spatial_available"):
            return None
        return d
    if require_any_raster and not _weather_raster_names(d):
        return None
    return d


def resolve_source_id(raw: str) -> str:
    """Accept source_id or dem/weather/fuel key alias → canonical source_id."""
    p = str(raw).strip()
    if p in CORE_SPATIAL_FIRES:
        return p
    for sid, spec in CORE_SPATIAL_FIRES.items():
        if p in {spec.dem_key, spec.weather_key, spec.fuel_key}:
            return sid
    raise KeyError(f"unknown spatial_v1 fire {raw!r}; known={list_core_source_ids()}")


def resolve_fuel_path(
    source_id: str,
    *,
    repo_root: Path | str | None = None,
    explicit: Path | str | None = None,
) -> Path | None:
    """WorldCover / landcover window used as vegetation proxy for re-emit."""
    if explicit is not None:
        p = Path(explicit)
        return p if p.is_file() else None
    spec = get_fire_spec(source_id)
    fdir = fuel_dir_for(spec, repo_root=repo_root)
    for name in (
        "worldcover_window.tif",
        "landcover_code.tif",
        "vegetation.tif",
        "fuel_height_m.tif",
    ):
        cand = fdir / name
        if cand.is_file():
            return cand
    return None


def resolve_ndvi_path(
    source_id: str,
    *,
    repo_root: Path | str | None = None,
    explicit: Path | str | None = None,
) -> Path | None:
    if explicit is not None:
        p = Path(explicit)
        return p if p.is_file() else None
    spec = get_fire_spec(source_id)
    root = repo_data_root(repo_root)
    candidates = [
        fuel_dir_for(spec, repo_root=root) / "ndvi.tif",
        root / "data" / "ndvi" / spec.fuel_key / "ndvi.tif",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def default_weather_scalars(source_id: str) -> dict[str, float]:
    return dict(
        DEFAULT_WEATHER_SCALARS.get(
            source_id,
            {
                "temp": 30.0,
                "humidity": 30.0,
                "wind_speed": 5.0,
                "wind_dir": 90.0,
                "precip": 0.0,
            },
        )
    )


def load_bbox_wgs84(
    source_id: str,
    *,
    repo_root: Path | str | None = None,
) -> list[float] | None:
    """Load bbox from dem_manifest.json when present."""
    spec = get_fire_spec(source_id)
    man = dem_dir(spec, repo_root=repo_root) / "dem_manifest.json"
    if not man.is_file():
        return None
    try:
        data = json.loads(man.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    bbox = data.get("bbox_wgs84")
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return None
    return [float(x) for x in bbox]


def _weather_raster_names(weather_dir: Path) -> list[str]:
    names: list[str] = []
    for name in (
        "tmin.tif",
        "tmax.tif",
        "temp.tif",
        "humidity.tif",
        "rh.tif",
        "wind_speed.tif",
        "wind_dir.tif",
        "precip.tif",
        "erc.tif",
    ):
        if (weather_dir / name).is_file():
            names.append(name)
    return names


def _core_keys_present(raster_names: Sequence[str]) -> dict[str, bool]:
    names = set(raster_names)
    return {
        "tmin": "tmin.tif" in names or "temp.tif" in names,
        "tmax": "tmax.tif" in names or "temp.tif" in names,
        "humidity": "humidity.tif" in names or "rh.tif" in names,
        "wind_speed": "wind_speed.tif" in names,
        "wind_dir": "wind_dir.tif" in names,
        "precip": "precip.tif" in names,
    }


def geotiff_spatial_stats(path: Path) -> dict[str, Any]:
    """Return min/max/std and whether the grid has non-trivial spatial variance."""
    out: dict[str, Any] = {
        "path": str(path.as_posix()),
        "exists": path.is_file(),
        "is_spatial": False,
        "std": None,
        "min": None,
        "max": None,
        "error": None,
    }
    if not path.is_file():
        out["error"] = "missing"
        return out
    try:
        import rasterio
    except ImportError:
        out["error"] = "rasterio_missing"
        return out
    try:
        with rasterio.open(path) as src:
            arr = src.read(1).astype(np.float64)
        finite = arr[np.isfinite(arr)]
        if finite.size == 0:
            out["error"] = "all_nodata"
            return out
        std = float(np.std(finite))
        out["std"] = std
        out["min"] = float(np.min(finite))
        out["max"] = float(np.max(finite))
        out["is_spatial"] = std >= _SPATIAL_STD_MIN
        if not out["is_spatial"]:
            out["error"] = "constant_or_near_constant"
    except Exception as exc:  # noqa: BLE001
        out["error"] = f"read_failed:{exc}"
    return out


def inventory_weather_dir(weather_dir: Path | None) -> dict[str, Any]:
    """Honest presence + spatial-variance check for one weather_dir."""
    if weather_dir is None or not Path(weather_dir).is_dir():
        return {
            "weather_dir": str(weather_dir) if weather_dir else None,
            "present": False,
            "rasters": [],
            "core_keys_present": dict.fromkeys(WEATHER_CANONICAL_KEYS, False),
            "weather_spatial_available": False,
            "weather_full_core": False,
            "gaps": ["weather_rasters_missing"],
            "raster_stats": {},
        }
    wdir = Path(weather_dir)
    rasters = _weather_raster_names(wdir)
    core = _core_keys_present(rasters)
    stats: dict[str, Any] = {}
    spatial_keys: list[str] = []
    constant_keys: list[str] = []
    for name in rasters:
        st = geotiff_spatial_stats(wdir / name)
        stats[name] = st
        key = name.replace(".tif", "")
        if key == "rh":
            key = "humidity"
        if st.get("is_spatial"):
            spatial_keys.append(key)
        elif st.get("exists"):
            constant_keys.append(key)

    any_spatial = len(spatial_keys) > 0
    # Full core only if all core files exist AND are spatial (not constant stamps)
    full_core = all(core.values()) and all(
        (k in spatial_keys) or (k in ("tmin", "tmax") and "temp" in spatial_keys)
        for k in WEATHER_CANONICAL_KEYS
    )
    # tmin/tmax via temp.tif spatial counts
    if "temp" in spatial_keys:
        for k in ("tmin", "tmax"):
            if k not in spatial_keys:
                spatial_keys.append(k)

    gaps: list[str] = []
    if not rasters:
        gaps.append("weather_rasters_missing")
    elif not full_core:
        if any_spatial:
            gaps.append("weather_partial_rasters")
        else:
            # files exist but all constant → still missing real spatial weather
            gaps.append("weather_rasters_missing")
            gaps.append("weather_constant_only")
    if constant_keys:
        gaps.append("weather_constant_files")

    return {
        "weather_dir": str(wdir.as_posix()),
        "present": True,
        "rasters": rasters,
        "core_keys_present": core,
        "spatial_keys": sorted(set(spatial_keys)),
        "constant_keys": sorted(set(constant_keys)),
        "weather_spatial_available": any_spatial,
        "weather_full_core": full_core,
        "gaps": gaps,
        "raster_stats": stats,
    }


def inventory_fuel_paths(
    *,
    fuel_path: Path | None,
    ndvi_path: Path | None,
) -> dict[str, Any]:
    fuel_ok = bool(fuel_path and Path(fuel_path).is_file())
    ndvi_ok = bool(ndvi_path and Path(ndvi_path).is_file())
    fuel_spatial = False
    ndvi_spatial = False
    stats: dict[str, Any] = {}
    if fuel_ok:
        st = geotiff_spatial_stats(Path(fuel_path))  # type: ignore[arg-type]
        stats["fuel"] = st
        fuel_spatial = bool(st.get("is_spatial"))
    if ndvi_ok:
        st = geotiff_spatial_stats(Path(ndvi_path))  # type: ignore[arg-type]
        stats["ndvi"] = st
        ndvi_spatial = bool(st.get("is_spatial"))
    gaps: list[str] = []
    if not fuel_ok and not ndvi_ok:
        gaps.append("fuel_or_ndvi_missing")
    elif not fuel_spatial and not ndvi_spatial:
        gaps.append("fuel_or_ndvi_non_spatial")
    return {
        "fuel_path": str(fuel_path.as_posix()) if fuel_path else None,
        "fuel_present": fuel_ok,
        "fuel_is_spatial": fuel_spatial,
        "ndvi_path": str(ndvi_path.as_posix()) if ndvi_path else None,
        "ndvi_present": ndvi_ok,
        "ndvi_is_spatial": ndvi_spatial,
        "fuel_or_ndvi_spatial": fuel_spatial or ndvi_spatial,
        "gaps": gaps,
        "stats": stats,
    }


@dataclass
class FireSourceInventory:
    source_id: str
    dem_path: str | None
    dem_present: bool
    bbox_wgs84: list[float] | None
    date: str
    weather: dict[str, Any]
    fuel: dict[str, Any]
    gaps: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def inventory_fire(
    source_id: str,
    *,
    repo_root: Path | str | None = None,
    weather_dir: Path | str | None = None,
    fuel_path: Path | str | None = None,
    ndvi_path: Path | str | None = None,
) -> FireSourceInventory:
    """Inventory DEM + weather + fuel for one fire (no downloads)."""
    spec = get_fire_spec(source_id)
    root = repo_data_root(repo_root)
    dem = resolve_dem_path(source_id, repo_root=root)
    wx_dir = resolve_weather_dir(
        source_id,
        repo_root=root,
        explicit=weather_dir,
    )
    fuel = resolve_fuel_path(source_id, repo_root=root, explicit=fuel_path)
    ndvi = resolve_ndvi_path(source_id, repo_root=root, explicit=ndvi_path)
    wx_inv = inventory_weather_dir(wx_dir)
    fuel_inv = inventory_fuel_paths(fuel_path=fuel, ndvi_path=ndvi)
    gaps: list[str] = []
    if dem is None:
        gaps.append("dem_missing")
    gaps.extend(wx_inv.get("gaps") or [])
    gaps.extend(fuel_inv.get("gaps") or [])
    # de-dupe preserve order
    gaps = list(dict.fromkeys(gaps))
    notes = list(spec.notes)
    if wx_inv.get("weather_spatial_available") is False:
        notes.append("weather_scalar_fallback_only — do not claim spatial weather variance")
    return FireSourceInventory(
        source_id=source_id,
        dem_path=str(dem.as_posix()) if dem else None,
        dem_present=dem is not None,
        bbox_wgs84=load_bbox_wgs84(source_id, repo_root=root),
        date=spec.date,
        weather=wx_inv,
        fuel=fuel_inv,
        gaps=gaps,
        notes=notes,
    )


def inventory_all_fires(
    *,
    repo_root: Path | str | None = None,
    source_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Build multi-fire weather/fuel inventory manifest."""
    root = repo_data_root(repo_root)
    ids = list(source_ids) if source_ids is not None else list_core_source_ids()
    fires: dict[str, Any] = {}
    n_full_wx = 0
    n_partial_wx = 0
    n_fuel = 0
    for sid in ids:
        inv = inventory_fire(sid, repo_root=root)
        fires[sid] = inv.to_dict()
        if inv.weather.get("weather_full_core"):
            n_full_wx += 1
        elif inv.weather.get("weather_spatial_available"):
            n_partial_wx += 1
        if inv.fuel.get("fuel_or_ndvi_spatial"):
            n_fuel += 1
    return {
        "schema": "wfd_spatial_v1_weather_fuel_inventory_v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "repo_root": str(Path(root).resolve().as_posix()),
        "n_fires": len(ids),
        "n_weather_full_core": n_full_wx,
        "n_weather_partial": n_partial_wx,
        "n_fuel_spatial": n_fuel,
        "layout": {
            "weather": "data/weather/<weather_key>/{tmin,tmax,humidity,wind_speed,wind_dir,precip}.tif",
            "fuel": "data/fuel_map/<fuel_key>/worldcover_window.tif",
            "ndvi": "data/fuel_map/<fuel_key>/ndvi.tif or data/ndvi/<key>/ndvi.tif",
            "dem": "data/dem/<dem_key>/glo30_window.tif",
        },
        "honesty": {
            "no_invented_constant_weather_as_spatial": True,
            "download_default_off": True,
            "scalar_aemet_is_not_spatial": True,
        },
        "fires": fires,
    }


class ConstantRasterRefused(ValueError):
    """Staging refused because source geotiff has no spatial variance."""


def stage_weather_raster(
    src: Path,
    dest_dir: Path,
    canonical_name: str,
    *,
    refuse_constant: bool = True,
) -> dict[str, Any]:
    """Copy a weather geotiff into canonical weather_dir with honesty checks.

    ``canonical_name`` e.g. ``tmin.tif``, ``humidity.tif``.
    Does **not** invent data — only stages real files.
    """
    src = Path(src)
    dest_dir = Path(dest_dir)
    if not src.is_file():
        raise FileNotFoundError(str(src))
    if not canonical_name.endswith(".tif"):
        canonical_name = f"{canonical_name}.tif"
    stats = geotiff_spatial_stats(src)
    if refuse_constant and not stats.get("is_spatial"):
        raise ConstantRasterRefused(
            f"refuse staging constant/non-spatial raster {src} → {canonical_name}: "
            f"{stats.get('error') or 'std~0'}"
        )
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / canonical_name
    shutil.copy2(src, dest)
    return {
        "src": str(src.as_posix()),
        "dest": str(dest.as_posix()),
        "canonical_name": canonical_name,
        "stats": stats,
        "staged": True,
    }


def stage_weather_dir_from_sources(
    dest_dir: Path,
    sources: Mapping[str, Path | str],
    *,
    refuse_constant: bool = True,
) -> dict[str, Any]:
    """Stage multiple named weather fields into ``dest_dir``.

    ``sources`` keys are canonical field names (tmin, tmax, humidity, rh,
    wind_speed, wind_dir, precip, temp, erc) mapping to existing geotiff paths.
    """
    dest_dir = Path(dest_dir)
    staged: list[dict[str, Any]] = []
    refused: list[dict[str, Any]] = []
    staged_names: set[str] = set()
    for key, path in sources.items():
        name = key if str(key).endswith(".tif") else f"{key}.tif"
        # Prefer humidity.tif as re-emit primary when only rh is provided
        if name == "rh.tif" and "humidity.tif" not in staged_names:
            name = "humidity.tif"
        try:
            rec = stage_weather_raster(
                Path(path),
                dest_dir,
                name,
                refuse_constant=refuse_constant,
            )
            staged.append(rec)
            staged_names.add(rec["canonical_name"])
        except ConstantRasterRefused as exc:
            refused.append({"key": key, "path": str(path), "error": str(exc)})
        except FileNotFoundError as exc:
            refused.append({"key": key, "path": str(path), "error": f"missing:{exc}"})
    inv = inventory_weather_dir(dest_dir if dest_dir.is_dir() else None)
    return {
        "dest_dir": str(dest_dir.as_posix()),
        "staged": staged,
        "refused": refused,
        "inventory": inv,
        "ok": len(staged) > 0 and len(refused) == 0,
        "partial": len(staged) > 0 and len(refused) > 0,
    }


def write_inventory_manifest(
    manifest: Mapping[str, Any],
    path: Path | str,
) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    return p


# Exit code convention for multi-fire weather/fuel CLIs
EXIT_OK = 0
EXIT_PARTIAL = 1  # inventory ok but gaps present / partial stage
EXIT_BLOCKED = 2  # required data missing when --require-* set
EXIT_ERROR = 3  # hard failure (bad args, unreadable, etc.)


def exit_code_from_inventory(
    manifest: Mapping[str, Any],
    *,
    require_weather_spatial: bool = False,
    require_fuel_spatial: bool = False,
    require_full_weather_core: bool = False,
) -> int:
    """Map inventory to CLI exit code (documented for operators/tests)."""
    fires = manifest.get("fires") or {}
    if not fires:
        return EXIT_ERROR
    any_gap = False
    for _sid, inv in fires.items():
        gaps = list(inv.get("gaps") or [])
        if gaps:
            any_gap = True
        wx = inv.get("weather") or {}
        fuel = inv.get("fuel") or {}
        if require_full_weather_core and not wx.get("weather_full_core"):
            return EXIT_BLOCKED
        if require_weather_spatial and not wx.get("weather_spatial_available"):
            return EXIT_BLOCKED
        if require_fuel_spatial and not fuel.get("fuel_or_ndvi_spatial"):
            return EXIT_BLOCKED
    return EXIT_PARTIAL if any_gap else EXIT_OK
