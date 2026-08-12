"""E2-P2 spatial_v1 schema, terrain, never-channel gate tests."""

from __future__ import annotations

import numpy as np
import pytest

from wildfire_front.ml.feature_schema import (
    SPATIAL_V1_N_CHANNELS,
    SPATIAL_V1_NAMES,
    NeverChannelTrainError,
    _terrain_from_elevation,
    assert_no_never_train_channels,
    build_channels_from_fields,
    build_spatial_v1_channels,
    channel_stats_from_tensor,
    label_channel_signal,
    never_gate_default_for_schema,
    schema_channel_count,
    schema_channel_names,
    spatial_v1_schema_map,
    work_class_for_schema,
)


def _synthetic_spatial_fields(h: int = 16, w: int = 16) -> dict[str, np.ndarray]:
    yy, xx = np.mgrid[0:h, 0:w]
    elevation = (400.0 + 2.0 * xx + 1.5 * yy).astype(np.float32)
    wind_dir = (np.linspace(0, 350, h * w).reshape(h, w)).astype(np.float32)
    wind_speed = (2.0 + 0.2 * xx).astype(np.float32)
    max_temp = (300.0 + 0.05 * yy).astype(np.float32)
    min_temp = (285.0 + 0.03 * xx).astype(np.float32)
    humidity = (20.0 + 0.1 * xx).astype(np.float32)
    precip = (0.01 * yy).astype(np.float32)
    veg = np.clip(0.2 + 0.02 * xx + 0.01 * yy, 0, 1).astype(np.float32)
    erc = (40.0 + 0.5 * xx).astype(np.float32)
    return {
        "elevation": elevation,
        "wind_dir": wind_dir,
        "wind_speed": wind_speed,
        "max_temp": max_temp,
        "min_temp": min_temp,
        "humidity": humidity,
        "precip": precip,
        "veg": veg,
        "erc": erc,
    }


def test_terrain_from_elevation_varies_with_dem():
    h, w = 12, 12
    flat = np.full((h, w), 500.0, dtype=np.float32)
    # Non-linear DEM: quadratic bowl → spatially varying slope (linear ramp has const slope)
    yy, xx = np.mgrid[0:h, 0:w]
    bowl = (0.5 * (xx - w / 2) ** 2 + 0.3 * (yy - h / 2) ** 2).astype(np.float32)
    _e0, s0, a0 = _terrain_from_elevation(flat)
    _e1, s1, a1 = _terrain_from_elevation(bowl)
    assert float(np.std(s0)) < 1e-5
    assert float(np.std(s1)) > 1e-3
    # aspect varies around bowl
    assert float(np.std(np.sin(a1))) > 1e-3 or float(np.std(np.cos(a1))) > 1e-3


def test_spatial_v1_schema_registered():
    assert schema_channel_count("spatial_v1") == 14
    assert schema_channel_count("physics14_spatial") == 14
    assert len(schema_channel_names("spatial_v1")) == SPATIAL_V1_N_CHANNELS
    assert len(SPATIAL_V1_NAMES) == 14
    m = spatial_v1_schema_map()
    assert m["feature_schema"] == "spatial_v1"
    assert m["schema_path_id"] == "E2-P2"
    assert m["physics14_claim_on_legacy17"] is False
    assert m["clean12_subset_projector"] is False
    assert m["full_spatial_reemit"] is True


def test_build_spatial_v1_shape_and_terrain_variance():
    fields = _synthetic_spatial_fields()
    # Bowl DEM so slope channel has spatial variance after norm
    h, w = 16, 16
    yy, xx = np.mgrid[0:h, 0:w]
    fields["elevation"] = (400.0 + 0.8 * (xx - 8) ** 2 + 0.5 * (yy - 8) ** 2).astype(np.float32)
    ch, meta = build_spatial_v1_channels(
        **fields,
        weather_is_spatial=True,
        fuel_is_spatial=True,
        dem_is_spatial=True,
    )
    assert ch.shape == (14, 16, 16)
    assert meta["feature_schema"] == "spatial_v1"
    assert meta["dem_is_spatial"] is True
    assert np.isfinite(ch).all()
    # elevation channel (normed) varies; aspect_sin/cos vary on bowl
    assert float(np.std(ch[0])) > 1e-4  # elevation
    assert float(np.std(ch[2])) > 1e-4 or float(np.std(ch[3])) > 1e-4  # aspect
    dead = sum(1 for i in range(14) if float(np.std(ch[i])) < 1e-4)
    assert dead < 6


def test_build_channels_from_fields_spatial_alias():
    fields = _synthetic_spatial_fields()
    a = build_channels_from_fields("spatial_v1", **fields)
    b = build_channels_from_fields("physics14_spatial", **fields)
    assert a.shape == b.shape == (14, 16, 16)
    assert np.allclose(a, b)


def test_scalar_weather_stamps_gap():
    fields = _synthetic_spatial_fields()
    # broadcast scalars → weather_is_spatial=False
    for k in ("wind_dir", "wind_speed", "max_temp", "min_temp", "humidity", "precip"):
        fields[k] = np.full((16, 16), float(fields[k].flat[0]), dtype=np.float32)
    ch, meta = build_spatial_v1_channels(
        **fields,
        weather_is_spatial=False,
        fuel_is_spatial=True,
        dem_is_spatial=True,
    )
    assert "weather_spatial" in meta["gaps"]
    assert ch.shape[0] == 14


def test_label_channel_signal_never_maybe_always():
    assert label_channel_signal(std=0.0, frac_const=1.0) == "never"
    assert label_channel_signal(std=1e-5, frac_const=0.995) == "never"
    assert label_channel_signal(std=0.5, frac_const=0.1) == "maybe"
    assert label_channel_signal(std=0.5, frac_const=0.1, corr_growth=0.1) == "always"
    assert label_channel_signal(std=0.5, frac_const=0.1, corr_change=-0.08) == "always"


def test_never_channel_gate_blocks():
    rows = [
        {"index": 0, "name": "elevation", "label": "maybe", "std": 1.0, "frac_near_constant": 0.0},
        {"index": 1, "name": "slope", "label": "never", "std": 0.0, "frac_near_constant": 1.0},
    ]
    with pytest.raises(NeverChannelTrainError):
        assert_no_never_train_channels(rows, raise_on_block=True)
    soft = assert_no_never_train_channels(rows, raise_on_block=False)
    assert soft["blocked"] is True
    assert soft["never_channels"][0]["name"] == "slope"


def test_never_channel_gate_allowlist_requires_honesty():
    rows = [
        {"index": 1, "name": "slope", "label": "never", "std": 0.0, "frac_near_constant": 1.0},
    ]
    with pytest.raises(NeverChannelTrainError):
        assert_no_never_train_channels(
            rows, allowlist={"slope"}, allowlist_honesty=None, raise_on_block=True
        )
    ok = assert_no_never_train_channels(
        rows,
        allowlist={"slope"},
        allowlist_honesty="research dead-channel keep for ablate only",
        raise_on_block=True,
    )
    assert ok["ok"] is True
    assert ok["never_allowlisted"]


def test_channel_stats_from_tensor_labels_constant():
    arr = np.zeros((4, 8, 8), dtype=np.float32)
    arr[0] = np.linspace(0, 1, 64).reshape(8, 8)
    rows = channel_stats_from_tensor(arr)
    assert rows[0]["label"] in ("maybe", "always")
    assert rows[1]["label"] == "never"


def test_reemit_dry_run_gap_without_dem(tmp_path):
    import sys
    from pathlib import Path

    scripts = Path(__file__).resolve().parents[1] / "scripts"
    sys.path.insert(0, str(scripts))
    from reemit_spatial_v1_patches import export_patches_spatial_v1

    plan = export_patches_spatial_v1(
        images_dir=tmp_path / "img",
        masks_dir=tmp_path / "msk",
        output_dir=tmp_path / "out",
        dem_path=None,
        dry_run=True,
        source_id="demo",
    )
    assert plan["blocked"] is True
    assert "dem_missing" in plan["gaps"] or "dem_missing" in str(plan.get("error", ""))


def test_never_gate_default_scopes_schemas():
    """BUG-1: sealed legacy17 must not gate-by-default; spatial_v1 must."""
    assert never_gate_default_for_schema("spatial_v1") is True
    assert never_gate_default_for_schema("physics14_spatial") is True
    assert never_gate_default_for_schema("physics14") is True
    assert never_gate_default_for_schema("legacy17") is False
    assert never_gate_default_for_schema("clean12_subset") is False
    assert never_gate_default_for_schema("clean12") is False


def test_work_class_stamps():
    assert work_class_for_schema("legacy17") == "recipe_t1_sealed"
    assert work_class_for_schema("spatial_v1") == "feature_spatial_v1"
    assert work_class_for_schema("legacy17", mix_policy="estrella_floor_v1") == (
        "data_mix_estrella_floor_v1"
    )
    assert work_class_for_schema("clean12_subset", schema_path_id="E2-P1").startswith(
        "feature_clean12"
    )


def test_partial_weather_field_spatial_not_bulk_true():
    """BUG-2: only precip spatial → weather_is_spatial False; precip not missing."""
    fields = _synthetic_spatial_fields()
    # Make all weather constant except precip (spatial gradient)
    for k in ("wind_dir", "wind_speed", "max_temp", "min_temp", "humidity"):
        fields[k] = np.full((16, 16), float(fields[k].flat[0]), dtype=np.float32)
    wfs = {
        "tmin": False,
        "tmax": False,
        "humidity": False,
        "wind_speed": False,
        "wind_dir": False,
        "precip": True,
        "erc": False,
    }
    ch, meta = build_spatial_v1_channels(
        **fields,
        weather_is_spatial=True,  # bulk claim overridden by weather_field_spatial
        fuel_is_spatial=True,
        dem_is_spatial=True,
        weather_field_spatial=wfs,
    )
    assert meta["weather_is_spatial"] is False
    assert "weather_partial_rasters" in meta["gaps"]
    # precip channel index 10 not fully missing
    assert float(meta["missing_mask_frac"]["precipitation"]) < 0.5
    # humidity is missing (scalar fill)
    assert float(meta["missing_mask_frac"]["humidity"]) > 0.5
    assert ch.shape[0] == 14


def test_partial_weather_reemit_fields(tmp_path):
    import sys
    from pathlib import Path

    import rasterio
    from rasterio.transform import from_origin

    scripts = Path(__file__).resolve().parents[1] / "scripts"
    sys.path.insert(0, str(scripts))
    from reemit_spatial_v1_patches import build_fields_from_sources

    dem_p = tmp_path / "dem.tif"
    wx = tmp_path / "wx"
    wx.mkdir()
    yy, xx = np.mgrid[0:8, 0:8]
    dem = (400 + xx + yy).astype(np.float32)
    precip = (0.1 * xx).astype(np.float32)
    transform = from_origin(0, 8, 1, 1)
    profile = {
        "driver": "GTiff",
        "height": 8,
        "width": 8,
        "count": 1,
        "dtype": "float32",
        "transform": transform,
        "crs": "EPSG:4326",
    }
    with rasterio.open(dem_p, "w", **profile) as dst:
        dst.write(dem, 1)
    with rasterio.open(wx / "precip.tif", "w", **profile) as dst:
        dst.write(precip, 1)

    fields, meta = build_fields_from_sources(
        (8, 8),
        dem_path=dem_p,
        weather_dir=wx,
        fuel_path=None,
        ndvi_path=None,
    )
    assert fields
    assert meta["weather_is_spatial"] is False
    assert meta["weather_field_spatial"]["precip"] is True
    assert meta["weather_field_spatial"]["humidity"] is False
    assert "weather_partial_rasters" in meta["gaps"]
    # ERC is FFMC proxy — not spatial when humidity etc. scalar
    assert meta["weather_field_spatial"]["erc"] is False
    assert meta.get("erc_source") == "ffmc_proxy"
