"""Offline tests for FlameForecast LST / harmonic-NDVI recipes."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.open_if.modis_ee import (  # noqa: E402
    ANNUAL_TAU_MS,
    EE_UNAVAILABLE,
    LST_COLLECTION,
    MIN_LST_COVERAGE,
    N_HARMONICS,
    NDVI_COLLECTION,
    NDVI_COLLECTION_FLAMEFORECAST,
    EarthEngineUnavailable,
    _finite_in_range_frac,
    _reproject_geotiff_bytes,
    apply_harmonic_coefs,
    array_from_sample_rectangle,
    empty_lst_point_doc,
    fetch_harmonic_ndvi,
    fetch_lst_point,
    fetch_lst_raster,
    fit_annual_sine,
    fit_harmonic_ndvi,
    harmonic_column_names,
    harmonic_design,
    initialize_earthengine,
    last_complete_month_bounds,
    lst_dn_to_celsius,
    lst_point_from_getregion,
    ndvi_to_veg_proxy,
    pack_fetch_recipe,
    qc_day_ok,
    scale_modis_ndvi,
    sine_anomaly_c,
    years_since_1970,
)


def test_lst_dn_matches_notebook_examples() -> None:
    assert lst_dn_to_celsius(14290) == pytest.approx(12.65, abs=1e-9)
    assert lst_dn_to_celsius(14565) == pytest.approx(18.15, abs=1e-9)
    assert lst_dn_to_celsius(14500) == pytest.approx(16.85, abs=1e-9)
    arr = lst_dn_to_celsius(np.array([14290.0, 14565.0]))
    assert arr[0] == pytest.approx(12.65, abs=1e-5)


def test_qc_day_accepts_only_good_by_default() -> None:
    assert qc_day_ok(0) is True
    assert qc_day_ok(1) is False
    assert qc_day_ok(1, allow_other_quality=True) is True
    assert qc_day_ok(2) is False
    assert qc_day_ok(3) is False
    assert qc_day_ok(2, allow_other_quality=True) is False
    assert qc_day_ok(None) is False
    # bits 2+ set, mandatory still 00
    assert qc_day_ok(0b00000100) is True


def test_fit_annual_sine_recovers_synthetic() -> None:
    rng = np.random.default_rng(0)
    t0 = 1_640_995_200_000.0
    times = t0 + np.arange(80) * (ANNUAL_TAU_MS / 80.0)
    lst0, delta, phi = 22.0, 16.0, 0.4
    clean = lst0 + (delta / 2.0) * np.sin(2.0 * np.pi * times / ANNUAL_TAU_MS + phi)
    noisy = clean + rng.normal(0.0, 0.05, size=times.size)
    fit = fit_annual_sine(times, noisy)
    assert fit is not None
    assert fit["n"] == 80
    assert fit["tau_pinned_annual"] is True
    assert fit["tau_ms"] == ANNUAL_TAU_MS
    assert fit["lst0"] == pytest.approx(lst0, abs=0.05)
    assert fit["delta_lst"] == pytest.approx(delta, abs=0.1)
    # phi is 2π-periodic
    dphi = abs((fit["phi"] - phi + math.pi) % (2 * math.pi) - math.pi)
    assert dphi < 0.05
    anom = sine_anomaly_c(float(times[3]), float(clean[3]), fit)
    assert anom is not None
    assert abs(anom) < 0.1


def test_fit_annual_sine_refuses_tiny_sample() -> None:
    times = np.array([1.0, 2.0, 3.0])
    vals = np.array([10.0, 11.0, 12.0])
    assert fit_annual_sine(times, vals) is None
    assert fit_annual_sine(times, vals, min_samples=3) is not None


def test_harmonic_design_has_eight_columns() -> None:
    names = harmonic_column_names(3)
    assert names == [
        "constant",
        "t",
        "cos_1",
        "cos_2",
        "cos_3",
        "sin_1",
        "sin_2",
        "sin_3",
    ]
    years = np.array([0.0, 0.25, 0.5, 1.0])
    design = harmonic_design(years, n_harmonics=3)
    assert design.shape == (4, 8)
    assert np.allclose(design[:, 0], 1.0)
    assert np.allclose(design[:, 1], years * 2.0 * np.pi)
    assert np.allclose(design[:, 2], np.cos(design[:, 1]))
    assert np.allclose(design[:, 5], np.sin(design[:, 1]))


def test_apply_harmonic_coefs_roundtrip() -> None:
    years = np.linspace(0.0, 2.0, 24)
    design = harmonic_design(years, n_harmonics=3)
    coefs = np.array([0.4, 0.01, 0.2, 0.05, 0.02, -0.1, 0.03, 0.01])
    series = apply_harmonic_coefs(design, coefs)
    fit = fit_harmonic_ndvi(years, series, n_harmonics=3, min_samples=8)
    assert fit is not None
    recovered = np.array([fit["coefs"][n] for n in fit["names"]])
    assert np.allclose(recovered, coefs, atol=1e-8)
    assert fit["rmse"] == pytest.approx(0.0, abs=1e-8)


def test_years_since_1970_epoch() -> None:
    assert years_since_1970(0.0) == pytest.approx(0.0)
    one_year_ms = 365.25 * 24 * 3600 * 1000
    assert years_since_1970(one_year_ms) == pytest.approx(1.0)


def test_empty_lst_doc_does_not_claim_meteo_or_ros() -> None:
    doc = empty_lst_point_doc(reason="ee_unavailable")
    assert doc["ok"] is False
    assert doc["collection"] == LST_COLLECTION
    assert doc["not_open_meteo_t2m"] is True
    assert doc["not_ros"] is True
    assert doc["sine_fit"] is None
    assert NDVI_COLLECTION != NDVI_COLLECTION_FLAMEFORECAST
    assert N_HARMONICS == 3


def test_module_import_does_not_require_earthengine() -> None:
    import wildfire_front.open_if.modis_ee as mod

    assert "ee" not in sys.modules or not hasattr(mod, "ee")
    assert not hasattr(mod, "ee")


def test_last_complete_month_and_ndvi_scale() -> None:
    bounds = last_complete_month_bounds("2023-08-01")
    assert bounds is not None
    start, end = bounds
    assert start.date().isoformat() == "2023-07-01"
    assert end.date().isoformat() == "2023-08-01"
    jan = last_complete_month_bounds("2023-01-15")
    assert jan is not None
    assert jan[0].date().isoformat() == "2022-12-01"
    assert jan[1].date().isoformat() == "2023-01-01"
    assert last_complete_month_bounds("not-a-date") is None
    assert scale_modis_ndvi(4000.0) == pytest.approx(0.4)
    assert scale_modis_ndvi(0.4) == pytest.approx(0.4)
    veg = ndvi_to_veg_proxy(np.array([[4000.0, -100.0]], dtype=np.float32))
    assert veg[0, 0] == pytest.approx(0.4)
    assert veg[0, 1] == pytest.approx(0.0)


def test_lst_point_from_getregion_applies_qc_and_formula() -> None:
    table = [
        ["id", "time", "LST_Day_1km", "QC_Day"],
        ["a", 1_640_995_200_000.0, 14500, 0],
        ["b", 1_640_995_200_000.0 + ANNUAL_TAU_MS / 4.0, 14290, 2],
    ]
    doc = lst_point_from_getregion(table, lon=-16.48, lat=28.35)
    assert doc["ok"] is True
    assert doc["n_qc_ok"] == 1
    assert doc["series"][0]["lst_c"] == pytest.approx(16.85)
    assert doc["series"][1]["qc_ok"] is False
    assert doc["not_open_meteo_t2m"] is True
    assert doc["not_ros"] is True


class _Info:
    def __init__(self, payload: object) -> None:
        self._payload = payload

    def getInfo(self) -> object:
        return self._payload


class _Geom:
    def __init__(self, kind: str, data: object) -> None:
        self.kind = kind
        self.data = data


class _FakeImg:
    def __init__(self, payload: object | None = None) -> None:
        self.payload = payload

    def select(self, *_a: object, **_k: object) -> _FakeImg:
        return self

    def updateMask(self, *_a: object, **_k: object) -> _FakeImg:
        return self

    def multiply(self, *_a: object, **_k: object) -> _FakeImg:
        return self

    def subtract(self, *_a: object, **_k: object) -> _FakeImg:
        return self

    def add(self, *_a: object, **_k: object) -> _FakeImg:
        return self

    def addBands(self, *_a: object, **_k: object) -> _FakeImg:
        return self

    def rename(self, *_a: object, **_k: object) -> _FakeImg:
        return self

    def toFloat(self) -> _FakeImg:
        return self

    def clip(self, *_a: object, **_k: object) -> _FakeImg:
        return self

    def cos(self) -> _FakeImg:
        return self

    def sin(self) -> _FakeImg:
        return self

    def bitwiseAnd(self, *_a: object, **_k: object) -> _FakeImg:
        return self

    def eq(self, *_a: object, **_k: object) -> _FakeImg:
        return self

    def Or(self, *_a: object, **_k: object) -> _FakeImg:
        return self

    def copyProperties(self, *_a: object, **_k: object) -> _FakeImg:
        return self

    def sampleRectangle(self, **_k: object) -> _Info:
        return _Info(self.payload)

    def reduce(self, *_a: object, **_k: object) -> _FakeImg:
        raise RuntimeError("force_monthly_fallback")

    def arrayProject(self, *_a: object, **_k: object) -> _FakeImg:
        return self

    def arrayFlatten(self, *_a: object, **_k: object) -> _FakeImg:
        return self

    def median(self) -> _FakeImg:
        return self

    def map(self, fn: object) -> _FakeImg:
        return self


class _FakeCol(_FakeImg):
    def __init__(self, name: str, payload: object | None = None) -> None:
        super().__init__(payload)
        self.name = name

    def filterDate(self, *_a: object, **_k: object) -> _FakeCol:
        return self

    def filterBounds(self, *_a: object, **_k: object) -> _FakeCol:
        return self

    def getRegion(self, *_a: object, **_k: object) -> _Info:
        return _Info(
            [
                ["id", "longitude", "latitude", "time", "LST_Day_1km", "QC_Day"],
                ["x", -16.48, 28.35, 1_640_995_200_000.0, 14500, 0],
            ]
        )


class _FakeEE:
    initialized_project: str | None = None

    class Geometry:
        @staticmethod
        def Point(coords: object) -> _Geom:
            return _Geom("point", coords)

        @staticmethod
        def Rectangle(bbox: object) -> _Geom:
            return _Geom("rect", bbox)

    class Date:
        def __init__(self, *_a: object, **_k: object) -> None:
            pass

        def difference(self, *_a: object, **_k: object) -> float:
            return 53.0

    class Image:
        def __init__(self, *_a: object, **_k: object) -> None:
            pass

        def rename(self, *_a: object, **_k: object) -> _FakeImg:
            return _FakeImg()

        def multiply(self, *_a: object, **_k: object) -> _FakeImg:
            return _FakeImg()

        def toFloat(self) -> _FakeImg:
            return _FakeImg()

        @staticmethod
        def constant(_v: object) -> _FakeImg:
            return _FakeImg()

    class Reducer:
        @staticmethod
        def linearRegression(**_k: object) -> str:
            return "lr"

    @staticmethod
    def Initialize(project: str | None = None) -> None:
        _FakeEE.initialized_project = project

    @staticmethod
    def ImageCollection(name: str) -> _FakeCol:
        payload = {"lst_c": [[16.85, 16.85], [16.85, 16.85]]}
        if "MOD13" in str(name) or "NDVI" in str(name):
            payload = {"NDVI": [[0.41, 0.42], [0.39, 0.40]]}
        return _FakeCol(name, payload)


def test_initialize_uses_env_project_never_flameforecast(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeEE.initialized_project = None
    monkeypatch.setenv("WFD_EE_PROJECT", "wfd-lab-project")
    ee = initialize_earthengine(ee_module=_FakeEE)
    assert ee is _FakeEE
    assert _FakeEE.initialized_project == "wfd-lab-project"
    monkeypatch.setenv("WFD_EE_PROJECT", "ee-alangtz51")
    with pytest.raises(EarthEngineUnavailable) as exc:
        initialize_earthengine(ee_module=_FakeEE)
    assert str(exc.value) == EE_UNAVAILABLE
    monkeypatch.delenv("WFD_EE_PROJECT", raising=False)
    with pytest.raises(EarthEngineUnavailable):
        initialize_earthengine(ee_module=_FakeEE)


def test_fetch_lst_point_uses_injected_ee() -> None:
    doc = fetch_lst_point(-16.48, 28.35, "2023-01-01", "2023-12-31", ee_module=_FakeEE)
    assert doc["ok"] is True
    assert doc["collection"] == LST_COLLECTION
    assert doc["series"][0]["lst_c"] == pytest.approx(16.85)
    assert doc["n_qc_ok"] == 1


def test_fetch_lst_raster_resamples_to_ref_grid() -> None:
    from rasterio.transform import from_origin

    ref = {
        "transform": from_origin(-1.0, 1.0, 0.5, 0.5),
        "crs": "EPSG:4326",
        "height": 4,
        "width": 4,
    }
    out = fetch_lst_raster([-1.0, -1.0, 1.0, 1.0], "2023-08-19", ref, ee_module=_FakeEE)
    assert out["ok"] is True
    assert out["array"].shape == (4, 4)
    assert out["not_temperature_c"] is True
    assert float(np.nanmean(out["array"])) == pytest.approx(16.85, abs=0.5)


def test_fetch_harmonic_ndvi_monthly_fallback() -> None:
    from rasterio.transform import from_origin

    ref = {
        "transform": from_origin(0.0, 10.0, 1.0, 1.0),
        "crs": "EPSG:4326",
        "height": 2,
        "width": 2,
    }
    out = fetch_harmonic_ndvi(
        [-1.0, -1.0, 1.0, 1.0],
        "2021-01-01",
        "2023-08-01",
        "2023-08-19",
        ee_module=_FakeEE,
        ref_grid=ref,
    )
    assert out["ok"] is True
    assert out["method"] == "monthly_median"
    assert out["veg_status"] == "modis_monthly"
    assert out["collection"] == NDVI_COLLECTION
    assert out["flameforecast_collection_cited"] == NDVI_COLLECTION_FLAMEFORECAST
    assert out["array"].shape == (2, 2)
    assert out["not_s2_nbr"] is True


def test_lst_coverage_frac_rejects_near_empty_day() -> None:
    almost_empty = np.full((100, 100), np.nan, dtype=np.float32)
    almost_empty[0, 0] = 33.0
    assert _finite_in_range_frac(almost_empty, -80.0, 80.0) < MIN_LST_COVERAGE
    full = np.full((10, 10), 28.0, dtype=np.float32)
    assert _finite_in_range_frac(full, -80.0, 80.0) == pytest.approx(1.0)


def test_reproject_geotiff_does_not_poison_neighbors_with_inf() -> None:
    from rasterio.io import MemoryFile
    from rasterio.transform import from_origin

    src = np.full((4, 4), -np.inf, dtype=np.float32)
    src[1:3, 1:3] = 28.5
    profile = {
        "driver": "GTiff",
        "height": 4,
        "width": 4,
        "count": 1,
        "dtype": "float32",
        "crs": "EPSG:4326",
        "transform": from_origin(-1.0, 1.0, 0.5, 0.5),
        "nodata": float("-inf"),
    }
    with MemoryFile() as mem:
        with mem.open(**profile) as ds:
            ds.write(src, 1)
        raw = mem.read()
    dest = _reproject_geotiff_bytes(
        raw,
        {
            "transform": from_origin(-1.0, 1.0, 0.25, 0.25),
            "crs": "EPSG:4326",
            "height": 8,
            "width": 8,
        },
    )
    finite = dest[np.isfinite(dest)]
    assert finite.size >= 8
    assert not np.isinf(dest).any()
    assert float(np.min(finite)) == pytest.approx(28.5, abs=0.6)
    assert float(np.max(finite)) == pytest.approx(28.5, abs=0.6)


def test_array_from_sample_rectangle_rejects_empty() -> None:
    with pytest.raises(ValueError, match="ee_sample_empty"):
        array_from_sample_rectangle({})
    arr = array_from_sample_rectangle({"NDVI": [[0.1, 0.2], [0.3, 0.4]]})
    assert arr.shape == (2, 2)


def test_recipe_documents_c61_and_never_flameforecast_project() -> None:
    rec = pack_fetch_recipe(
        "ES_EMSR685_TENERIFE",
        lon=-16.48,
        lat=28.35,
        bbox=[-16.6, 28.2, -16.3, 28.5],
        start="2022-08-01",
        end="2023-08-20",
        at_date="2023-08-19",
    )
    blob = json.dumps(rec)
    assert rec["ndvi"]["collection"] == NDVI_COLLECTION
    assert rec["ndvi"]["flameforecast_collection_cited"] == NDVI_COLLECTION_FLAMEFORECAST
    assert rec["ee_init"] == "ee.Initialize(project=os.environ.get('WFD_EE_PROJECT'))"
    assert rec["never_hardcode_project"] == "ee-alangtz51"
    assert "ee-alangtz51" in rec["never_hardcode_project"]
    assert rec["lst_point"]["formula"] == "dn * 0.02 - 273.15"
    assert "WFD_EE_PROJECT" in blob


def _run_fetch(*args: str, env_extra: dict[str, str] | None = None):
    import os
    import subprocess

    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    env.pop("WFD_EE_PROJECT", None)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "fetch_modis_ee_covariates.py"), *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
    )


def test_cli_dry_run_exit_0_no_tifs(tmp_path: Path) -> None:
    data_root = tmp_path / "latam_au"
    p = _run_fetch(
        "--event-id",
        "ES_EMSR685_TENERIFE",
        "--data-root",
        str(data_root),
        "--dry-run",
    )
    assert p.returncode == 0, p.stdout + p.stderr
    recipe = json.loads(p.stdout)
    assert recipe["lst_point"]["collection"] == LST_COLLECTION
    assert recipe["ndvi"]["collection"] == NDVI_COLLECTION
    assert recipe["ee_init"].startswith("ee.Initialize(project=os.environ.get('WFD_EE_PROJECT'))")
    pack = data_root / "es" / "ES_EMSR685_TENERIFE"
    assert not (pack / "covariates" / "lst_day_c.tif").exists()
    assert not (pack / "covariates" / "modis_ndvi.tif").exists()
    assert not (pack / "weather" / "modis_lst_point.json").exists()


def test_cli_no_project_exit_2_ee_unavailable_no_tifs(tmp_path: Path) -> None:
    data_root = tmp_path / "latam_au"
    pack = data_root / "es" / "ES_EMSR685_TENERIFE"
    (pack / "covariates").mkdir(parents=True)
    (pack / "weather").mkdir(parents=True)
    p = _run_fetch(
        "--event-id",
        "ES_EMSR685_TENERIFE",
        "--data-root",
        str(data_root),
    )
    assert p.returncode == 2, p.stdout + p.stderr
    text = p.stderr + p.stdout
    assert "ee_unavailable" in text
    assert not (pack / "covariates" / "lst_day_c.tif").exists()
    assert not (pack / "covariates" / "modis_ndvi.tif").exists()
    assert not (pack / "weather" / "modis_lst_point.json").exists()
    assert not list((pack / "covariates").glob("*.tif"))


def test_cli_rejects_path_escape_event_id(tmp_path: Path) -> None:
    p = _run_fetch("--event-id", "..\\etc\\passwd", "--data-root", str(tmp_path), "--dry-run")
    assert p.returncode == 2, p.stdout + p.stderr
    assert "invalid event-id" in (p.stderr + p.stdout)
    p2 = _run_fetch("--event-id", "NOT_A_PACK", "--data-root", str(tmp_path), "--dry-run")
    assert p2.returncode == 2
    assert "unknown event_id" in (p2.stderr + p2.stdout)


def test_cli_missing_pack_live_exit_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Live path (project set) still refuses to invent rasters when the pack is gone."""
    import wildfire_front.open_if.modis_ee as mod

    monkeypatch.setattr(mod, "earthengine_status", lambda **_k: {
        "ee_installed": True,
        "project": "wfd-lab",
        "available": True,
        "reason": None,
    })
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "fetch_modis_ee_covariates", ROOT / "scripts" / "fetch_modis_ee_covariates.py"
    )
    assert spec and spec.loader
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    monkeypatch.setattr(cli, "earthengine_status", lambda **_k: {
        "ee_installed": True,
        "project": "wfd-lab",
        "available": True,
        "reason": None,
    })
    rc = cli.main(
        [
            "--event-id",
            "ES_EMSR685_TENERIFE",
            "--data-root",
            str(tmp_path / "empty"),
        ]
    )
    assert rc == 1
    assert not list((tmp_path / "empty").rglob("*.tif"))


def _mini_fill_pack(tmp_path: Path, event_id: str = "AU_EMSR500_PERTH") -> Path:
    from shapely.geometry import Polygon

    from wildfire_front.open_if.latam_au import (
        EMSR_PACK_SPECS,
        pack_dir_for,
        rasterize_geom_to_geotiff,
    )

    spec = EMSR_PACK_SPECS[event_id]
    pack = pack_dir_for(tmp_path / "latam_au", spec)
    labels = pack / "labels"
    labels.mkdir(parents=True)
    poly = Polygon(
        [(116.17, -31.79), (116.19, -31.79), (116.19, -31.77), (116.17, -31.77), (116.17, -31.79)]
    )
    dest = labels / f"{event_id}_20210205_203225.tif"
    rasterize_geom_to_geotiff(poly, dest, epsg=int(spec["crs_epsg"]), gsd_m=30.0)
    meta = {
        "schema": "wfd_open_if_pack_meta_v1",
        "event_id": event_id,
        "region": spec["region"],
        "activation": spec["activation"],
        "license_id": spec["license_id"],
        "crs": f"EPSG:{spec['crs_epsg']}",
        "gsd_m": 30.0,
        "class": "ml_weak",
        "label_level": "L2_proxy",
        "rights_doc": "docs/data_campaigns/LATAM_AU_RIGHTS.md",
        "geotiffs": [
            {
                "rel": f"labels/{dest.name}",
                "role": "label_burned_cems_rasterized",
                "kind": "delineation",
                "delivery_utc": "2021-02-05T20:32:25Z",
            }
        ],
        "labels": [{"rel": f"labels/{dest.name}"}],
        "not_national_cadastre": True,
        "not_lwir": True,
    }
    (pack / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    weather = pack / "weather"
    weather.mkdir(exist_ok=True)
    (weather / "open_meteo_era5_archive.json").write_text(
        json.dumps(
            {
                "elevation_m": 220.0,
                "hourly": {
                    "time": ["2021-02-05T20:00"],
                    "temperature_2m": [25.0],
                    "relative_humidity_2m": [40.0],
                    "wind_speed_10m": [15.0],
                    "wind_direction_10m": [180.0],
                    "precipitation": [0.0],
                },
            }
        ),
        encoding="utf-8",
    )
    return pack


def _write_label_aligned_tif(pack: Path, name: str, value: float, *, method: str | None = None) -> Path:
    import rasterio

    label = next((pack / "labels").glob("*.tif"))
    dest = pack / "covariates" / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(label) as src:
        arr = np.full((src.height, src.width), float(value), dtype=np.float32)
        profile = {
            "driver": "GTiff",
            "height": src.height,
            "width": src.width,
            "count": 1,
            "dtype": "float32",
            "crs": src.crs,
            "transform": src.transform,
            "compress": "deflate",
        }
        with rasterio.open(dest, "w", **profile) as ds:
            ds.write(arr, 1)
            if method:
                ds.update_tags(modis_method=method)
    return dest


def _load_fill():
    import importlib.util

    path = ROOT / "scripts" / "fill_latam_au_ndws_covariates.py"
    spec = importlib.util.spec_from_file_location("fill_latam_au_ndws_covariates", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_fill_pack_modis_ndvi_without_s2_marks_veg_ready(tmp_path: Path) -> None:
    pytest.importorskip("rasterio")
    import rasterio

    pack = _mini_fill_pack(tmp_path)
    _write_label_aligned_tif(pack, "modis_ndvi.tif", 0.33, method="harmonic_fitted")
    _write_label_aligned_tif(pack, "lst_day_c.tif", 41.0)
    fill = _load_fill()
    row = fill.fill_pack("AU_EMSR500_PERTH", pack, skip_dem_fetch=True)
    assert row["ok"] is True, row
    assert row["veg_status"] == "modis_harmonic"
    assert row["channels_ready"]["veg"] is True
    assert row["channels_ready"]["lst"] is True
    assert row["ready_for_real_proxy_ndws"] is True
    prov = json.loads((pack / "covariates" / "PROVENANCE.json").read_text(encoding="utf-8"))
    assert prov["channels_ready"]["veg"] is True
    assert prov["channels_ready"]["lst"] is True
    assert prov["vegetation"]["status"] == "modis_harmonic"
    with rasterio.open(pack / "covariates" / "vegetation_proxy.tif") as ds:
        assert float(np.mean(ds.read(1))) == pytest.approx(0.33, abs=0.02)
    with rasterio.open(pack / "covariates" / "temperature_c.tif") as ds:
        assert float(np.mean(ds.read(1))) == pytest.approx(25.0, abs=0.01)
    with rasterio.open(pack / "covariates" / "lst_day_c.tif") as ds:
        assert float(np.mean(ds.read(1))) == pytest.approx(41.0, abs=0.01)


def test_fill_pack_s2_nbr_wins_over_modis(tmp_path: Path) -> None:
    pytest.importorskip("rasterio")
    import rasterio

    pack = _mini_fill_pack(tmp_path)
    _write_label_aligned_tif(pack, "modis_ndvi.tif", 0.11, method="monthly_median")
    eo = pack / "eo"
    eo.mkdir()
    label = next((pack / "labels").glob("*.tif"))
    with rasterio.open(label) as src:
        nbr = np.full((src.height, src.width), 0.2, dtype=np.float32)
        s2 = eo / "AU_EMSR500_PERTH_S2NBR_20210121_022636.tif"
        profile = {
            "driver": "GTiff",
            "height": src.height,
            "width": src.width,
            "count": 1,
            "dtype": "float32",
            "crs": src.crs,
            "transform": src.transform,
        }
        with rasterio.open(s2, "w", **profile) as ds:
            ds.write(nbr, 1)
    fill = _load_fill()
    row = fill.fill_pack("AU_EMSR500_PERTH", pack, skip_dem_fetch=True)
    assert row["ok"] is True, row
    assert row["veg_status"] == "ok"
    assert row["channels_ready"]["veg"] is True
    prov = json.loads((pack / "covariates" / "PROVENANCE.json").read_text(encoding="utf-8"))
    assert prov["vegetation"]["status"] == "ok"
    assert prov["vegetation"].get("source") == "s2_nbr"
    with rasterio.open(pack / "covariates" / "vegetation_proxy.tif") as ds:
        mean = float(np.mean(ds.read(1)))
    assert mean == pytest.approx(0.6, abs=0.02)
    assert mean != pytest.approx(0.11, abs=0.02)
