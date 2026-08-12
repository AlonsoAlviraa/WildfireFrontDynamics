"""Multi-fire weather/fuel inventory, resolve, staging, CLI exit codes."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

try:
    import rasterio
    from rasterio.transform import from_origin
except ModuleNotFoundError:  # pragma: no cover
    rasterio = None  # type: ignore[assignment]
    from_origin = None  # type: ignore[assignment]

from wildfire_front.fuel.spatial_v1_sources import (
    EXIT_BLOCKED,
    EXIT_ERROR,
    EXIT_OK,
    EXIT_PARTIAL,
    ConstantRasterRefused,
    default_weather_scalars,
    exit_code_from_inventory,
    get_fire_spec,
    inventory_all_fires,
    inventory_fire,
    inventory_weather_dir,
    list_core_source_ids,
    resolve_fuel_path,
    resolve_weather_dir,
    stage_weather_dir_from_sources,
    stage_weather_raster,
)
from wildfire_front.ml.feature_schema import (
    NeverChannelTrainError,
    assert_no_never_train_channels,
    never_gate_default_for_schema,
)

pytestmark = [pytest.mark.skipif(rasterio is None, reason="rasterio not installed")]

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def _write_tif(path: Path, arr: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    h, w = arr.shape
    transform = from_origin(0, h, 1, 1)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=h,
        width=w,
        count=1,
        dtype="float32",
        transform=transform,
        crs="EPSG:4326",
    ) as dst:
        dst.write(arr.astype(np.float32), 1)


def test_core_catalog_has_expected_fires():
    ids = list_core_source_ids()
    assert "CARDOSO" in ids
    assert "tobarra_20240802" in ids
    assert "LA_ESTRELLA_ACOM1" in ids
    spec = get_fire_spec("tobarra_20240802")
    assert spec.fuel_key == "tobarra"
    assert spec.weather_key == "tobarra"
    assert spec.date == "2024-08-02"


def test_inventory_weather_dir_missing(tmp_path: Path):
    inv = inventory_weather_dir(None)
    assert inv["weather_spatial_available"] is False
    assert "weather_rasters_missing" in inv["gaps"]

    inv2 = inventory_weather_dir(tmp_path / "nope")
    assert inv2["present"] is False
    assert "weather_rasters_missing" in inv2["gaps"]


def test_inventory_weather_partial_spatial(tmp_path: Path):
    wx = tmp_path / "wx"
    yy, xx = np.mgrid[0:8, 0:8]
    _write_tif(wx / "precip.tif", (0.1 * xx).astype(np.float32))
    inv = inventory_weather_dir(wx)
    assert inv["present"] is True
    assert inv["weather_spatial_available"] is True
    assert inv["weather_full_core"] is False
    assert "weather_partial_rasters" in inv["gaps"]
    assert "precip" in inv["spatial_keys"]


def test_inventory_weather_constant_only_is_gap(tmp_path: Path):
    """Constant geotiffs must NOT count as spatial weather."""
    wx = tmp_path / "wx"
    const = np.full((6, 6), 20.0, dtype=np.float32)
    for name in (
        "tmin.tif",
        "tmax.tif",
        "humidity.tif",
        "wind_speed.tif",
        "wind_dir.tif",
        "precip.tif",
    ):
        _write_tif(wx / name, const)
    inv = inventory_weather_dir(wx)
    assert inv["weather_spatial_available"] is False
    assert "weather_rasters_missing" in inv["gaps"] or "weather_constant_only" in inv["gaps"]
    assert inv["weather_full_core"] is False


def test_stage_refuses_constant(tmp_path: Path):
    src = tmp_path / "const.tif"
    _write_tif(src, np.full((4, 4), 5.0, dtype=np.float32))
    dest = tmp_path / "weather" / "demo"
    with pytest.raises(ConstantRasterRefused):
        stage_weather_raster(src, dest, "tmin.tif", refuse_constant=True)


def test_stage_accepts_spatial_and_inventory(tmp_path: Path):
    yy, xx = np.mgrid[0:8, 0:8]
    sources = {}
    for key, arr in {
        "tmin": 10 + 0.5 * xx,
        "tmax": 20 + 0.5 * xx,
        "humidity": 30 + 0.2 * yy,
        "wind_speed": 2 + 0.1 * xx,
        "wind_dir": 90 + 5 * yy,
        "precip": 0.05 * xx,
    }.items():
        p = tmp_path / "src" / f"{key}.tif"
        _write_tif(p, arr.astype(np.float32))
        sources[key] = p
    dest = tmp_path / "data" / "weather" / "demo"
    report = stage_weather_dir_from_sources(dest, sources, refuse_constant=True)
    assert report["ok"] is True
    assert len(report["staged"]) == 6
    inv = report["inventory"]
    assert inv["weather_full_core"] is True
    assert inv["weather_spatial_available"] is True


def test_resolve_fuel_path_discovers_cache(tmp_path: Path):
    # Build mini repo layout
    fuel_dir = tmp_path / "data" / "fuel_map" / "tobarra"
    _write_tif(
        fuel_dir / "worldcover_window.tif",
        (10 + np.arange(16, dtype=np.float32).reshape(4, 4)),
    )
    p = resolve_fuel_path("tobarra_20240802", repo_root=tmp_path)
    assert p is not None
    assert p.name == "worldcover_window.tif"

    assert resolve_fuel_path("CARDOSO", repo_root=tmp_path) is None


def test_resolve_weather_dir_require_raster(tmp_path: Path):
    empty = tmp_path / "data" / "weather" / "cardoso"
    empty.mkdir(parents=True)
    assert resolve_weather_dir("CARDOSO", repo_root=tmp_path) is not None
    assert resolve_weather_dir("CARDOSO", repo_root=tmp_path, require_any_raster=True) is None
    _write_tif(empty / "precip.tif", (np.arange(9, dtype=np.float32).reshape(3, 3)))
    assert resolve_weather_dir("CARDOSO", repo_root=tmp_path, require_any_raster=True) is not None
    assert resolve_weather_dir("CARDOSO", repo_root=tmp_path, require_spatial=True) is not None


def test_resolve_weather_dir_require_spatial_rejects_constant(tmp_path: Path):
    """Constant-only weather dirs must not auto-discover as spatial."""
    wx = tmp_path / "data" / "weather" / "cardoso"
    const = np.full((6, 6), 12.0, dtype=np.float32)
    for name in (
        "tmin.tif",
        "tmax.tif",
        "humidity.tif",
        "wind_speed.tif",
        "wind_dir.tif",
        "precip.tif",
    ):
        _write_tif(wx / name, const)
    assert resolve_weather_dir("CARDOSO", repo_root=tmp_path, require_any_raster=True) is not None
    assert resolve_weather_dir("CARDOSO", repo_root=tmp_path, require_spatial=True) is None


def test_reemit_constant_weather_not_field_spatial(tmp_path: Path):
    """build_fields_from_sources must not stamp constant geotiffs as spatial."""
    import sys

    scripts = ROOT / "scripts"
    sys.path.insert(0, str(scripts))
    from reemit_spatial_v1_patches import build_fields_from_sources

    dem_p = tmp_path / "dem.tif"
    wx = tmp_path / "wx"
    yy, xx = np.mgrid[0:8, 0:8]
    dem = (400 + xx + yy).astype(np.float32)
    _write_tif(dem_p, dem)
    const = np.full((8, 8), 25.0, dtype=np.float32)
    for name in (
        "tmin.tif",
        "tmax.tif",
        "humidity.tif",
        "wind_speed.tif",
        "wind_dir.tif",
        "precip.tif",
    ):
        _write_tif(wx / name, const)

    fields, meta = build_fields_from_sources(
        (8, 8),
        dem_path=dem_p,
        weather_dir=wx,
        fuel_path=None,
        ndvi_path=None,
    )
    assert fields
    assert meta["weather_is_spatial"] is False
    assert not any(
        meta["weather_field_spatial"].get(k)
        for k in ("tmin", "tmax", "humidity", "wind_speed", "wind_dir", "precip")
    )
    assert "weather_rasters_missing" in meta["gaps"] or "weather_partial_rasters" in meta["gaps"]


def test_inventory_fire_gaps_and_scalars():
    # Use real repo root — offline inventory should report weather GAP for most fires
    inv = inventory_fire("CARDOSO", repo_root=ROOT)
    assert inv.source_id == "CARDOSO"
    # weather almost always missing spatial offline
    assert isinstance(inv.gaps, list)
    sc = default_weather_scalars("CARDOSO")
    assert "temp" in sc and "humidity" in sc


def test_exit_code_from_inventory_require_flags():
    man = {
        "fires": {
            "A": {
                "gaps": ["weather_rasters_missing", "fuel_or_ndvi_missing"],
                "weather": {
                    "weather_spatial_available": False,
                    "weather_full_core": False,
                },
                "fuel": {"fuel_or_ndvi_spatial": False},
            }
        }
    }
    assert exit_code_from_inventory(man) == EXIT_PARTIAL
    assert exit_code_from_inventory(man, require_weather_spatial=True) == EXIT_BLOCKED
    assert exit_code_from_inventory(man, require_fuel_spatial=True) == EXIT_BLOCKED
    assert exit_code_from_inventory(man, require_full_weather_core=True) == EXIT_BLOCKED

    man_ok = {
        "fires": {
            "A": {
                "gaps": [],
                "weather": {
                    "weather_spatial_available": True,
                    "weather_full_core": True,
                },
                "fuel": {"fuel_or_ndvi_spatial": True},
            }
        }
    }
    assert exit_code_from_inventory(man_ok) == EXIT_OK
    assert exit_code_from_inventory({}) == EXIT_ERROR


def test_never_gate_still_blocks_fake_spatial():
    """Never-gate remains on for spatial_v1 (no fake weather train by default)."""
    assert never_gate_default_for_schema("spatial_v1") is True
    rows = [
        {
            "index": 7,
            "name": "wind_speed",
            "label": "never",
            "std": 0.0,
            "frac_near_constant": 1.0,
        },
    ]
    with pytest.raises(NeverChannelTrainError):
        assert_no_never_train_channels(rows, raise_on_block=True)


def _run_script(script: str, args: list[str]) -> tuple[int, str, str]:
    import subprocess

    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env={
            **dict(**dict(__import__("os").environ.items())),
            "PYTHONPATH": str(ROOT),
        },
    )
    return proc.returncode, proc.stdout, proc.stderr


def test_cli_weather_inventory_exit_partial(tmp_path: Path):
    man = tmp_path / "inv.json"
    code, out, err = _run_script(
        "build_spatial_v1_weather_rasters.py",
        ["--inventory-only", "--manifest-out", str(man)],
    )
    # Offline: GAPs expected → exit 1 (PARTIAL)
    assert code == EXIT_PARTIAL, f"code={code} out={out} err={err}"
    assert man.is_file()
    data = json.loads(man.read_text(encoding="utf-8"))
    assert data["schema"] == "wfd_spatial_v1_weather_fuel_inventory_v1"
    assert data["n_fires"] >= 5
    # Tobarra may have fuel spatial; weather still missing for all offline
    assert data["n_weather_full_core"] == 0


def test_cli_weather_require_spatial_exit_blocked(tmp_path: Path):
    man = tmp_path / "inv.json"
    code, out, err = _run_script(
        "build_spatial_v1_weather_rasters.py",
        [
            "--inventory-only",
            "--fire",
            "CARDOSO",
            "--require-weather-spatial",
            "--manifest-out",
            str(man),
        ],
    )
    assert code == EXIT_BLOCKED, f"code={code} out={out} err={err}"


def test_cli_stage_then_inventory(tmp_path: Path):
    yy, xx = np.mgrid[0:6, 0:6]
    src_dir = tmp_path / "src"
    paths = {}
    for key, arr in {
        "tmin": 10 + xx,
        "tmax": 20 + xx,
        "humidity": 40 + yy,
        "wind_speed": 3 + 0.2 * xx,
        "wind_dir": 100 + yy,
        "precip": 0.1 * xx,
    }.items():
        p = src_dir / f"{key}.tif"
        _write_tif(p, arr.astype(np.float32))
        paths[key] = p

    weather_out = tmp_path / "weather_out"
    man = tmp_path / "inv.json"
    code, out, err = _run_script(
        "build_spatial_v1_weather_rasters.py",
        [
            "--fire",
            "tobarra_20240802",
            "--weather-out-dir",
            str(weather_out),
            "--stage-tmin",
            str(paths["tmin"]),
            "--stage-tmax",
            str(paths["tmax"]),
            "--stage-humidity",
            str(paths["humidity"]),
            "--stage-wind-speed",
            str(paths["wind_speed"]),
            "--stage-wind-dir",
            str(paths["wind_dir"]),
            "--stage-precip",
            str(paths["precip"]),
            "--manifest-out",
            str(man),
        ],
    )
    # staging full core for one fire, but inventory is only that fire —
    # fuel may still GAP → PARTIAL (1) is ok; full core weather → not BLOCKED
    assert code in (EXIT_OK, EXIT_PARTIAL), f"code={code} out={out} err={err}"
    assert (weather_out / "tmin.tif").is_file()
    assert (weather_out / "precip.tif").is_file()
    data = json.loads(man.read_text(encoding="utf-8"))
    fire = data["fires"]["tobarra_20240802"]
    # Override dest is re-inventoried so weather full core reflects staged path
    assert fire.get("weather_dir_override") is not None
    assert (fire.get("weather") or {}).get("weather_full_core") is True
    # weather GAP should not list weather_rasters_missing for this fire
    assert "weather_rasters_missing" not in (fire.get("gaps") or [])
    inv_staged = inventory_weather_dir(weather_out)
    assert inv_staged["weather_full_core"] is True


def test_cli_fuel_resolve_only_exit_codes():
    # Repo fixture includes Tobarra WorldCover under data/fuel_map/tobarra/
    tobarra_wc = ROOT / "data" / "fuel_map" / "tobarra" / "worldcover_window.tif"
    code, out, err = _run_script(
        "build_fuel_map.py",
        ["--fire", "tobarra", "--resolve-only"],
    )
    payload = json.loads(out)
    assert payload["source_id"] == "tobarra_20240802"
    if tobarra_wc.is_file():
        assert code == EXIT_OK, f"code={code} out={out} err={err}"
        assert payload["present"] is True
    else:
        # Fixture absent (e.g. clean CI without gitignored cache) → blocked
        assert code == EXIT_BLOCKED, f"code={code} out={out} err={err}"
        assert payload["present"] is False

    code2, out2, err2 = _run_script(
        "build_fuel_map.py",
        ["--fire", "CARDOSO", "--resolve-only"],
    )
    # CARDOSO fuel usually missing offline
    assert code2 == EXIT_BLOCKED, f"code={code2} out={out2} err={err2}"
    assert json.loads(out2)["present"] is False


def test_cli_full_reemit_inventory_only(tmp_path: Path):
    inv = tmp_path / "inv.json"
    code, out, err = _run_script(
        "run_spatial_v1_full_reemit.py",
        [
            "--inventory-only",
            "--fire",
            "CARDOSO,tobarra_20240802",
            "--inventory-out",
            str(inv),
        ],
    )
    assert code in (EXIT_OK, EXIT_PARTIAL), f"code={code} out={out} err={err}"
    assert inv.is_file()
    data = json.loads(inv.read_text(encoding="utf-8"))
    assert "CARDOSO" in data["fires"]
    assert "tobarra_20240802" in data["fires"]


def test_cli_full_reemit_require_weather_blocked(tmp_path: Path):
    inv = tmp_path / "inv.json"
    code, out, err = _run_script(
        "run_spatial_v1_full_reemit.py",
        [
            "--inventory-only",
            "--fire",
            "CARDOSO",
            "--require-weather-spatial",
            "--inventory-out",
            str(inv),
        ],
    )
    assert code == EXIT_BLOCKED, f"code={code} out={out} err={err}"


def test_inventory_all_fires_schema():
    man = inventory_all_fires(repo_root=ROOT, source_ids=["CARDOSO", "tobarra_20240802"])
    assert man["n_fires"] == 2
    assert man["honesty"]["no_invented_constant_weather_as_spatial"] is True
