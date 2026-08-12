"""Tests for legacy17 ↔ physics14/spatial_v1 schema bridge (honesty)."""

from __future__ import annotations

import numpy as np
import pytest

from wildfire_front.ml.feature_schema import (
    PHYSICS14_NAMES,
    build_legacy17_channels,
)
from wildfire_front.ml.schema_bridge import (
    BRIDGE_SPEC,
    FIRST_CONV_SPATIAL_TO_LEGACY,
    bridge_spec_table,
    project_legacy17_to_physics14,
    project_sequence_legacy17_to_physics14,
)


def _synthetic_fields(h: int = 32, w: int = 32):
    rng = np.random.default_rng(0)
    elev = 500.0 + 200.0 * rng.random((h, w)).astype(np.float32)
    wind_dir = (rng.random((h, w)) * 360.0).astype(np.float32)
    wind_speed = (1.0 + 5.0 * rng.random((h, w))).astype(np.float32)
    tmax = (25.0 + 10.0 * rng.random((h, w))).astype(np.float32)
    tmin = tmax - 8.0
    humidity = (20.0 + 40.0 * rng.random((h, w))).astype(np.float32)
    precip = (rng.random((h, w)) * 2.0).astype(np.float32)
    veg = rng.random((h, w)).astype(np.float32)
    erc = (rng.random((h, w)) * 80.0).astype(np.float32)
    return elev, wind_dir, wind_speed, tmax, tmin, humidity, precip, veg, erc


def test_bridge_spec_covers_14_channels():
    assert len(BRIDGE_SPEC) == 14
    assert len(bridge_spec_table()) == 14
    names = [r["name"] for r in BRIDGE_SPEC]
    assert names == list(PHYSICS14_NAMES)


def test_first_conv_map_length_15():
    # 14 features + prev_fire
    assert len(FIRST_CONV_SPATIAL_TO_LEGACY) == 15
    assert FIRST_CONV_SPATIAL_TO_LEGACY[0] is None  # elev gap
    assert FIRST_CONV_SPATIAL_TO_LEGACY[14] == 17  # prev_fire


def test_project_shape_and_elev_gap():
    elev, wind_dir, wind_speed, tmax, tmin, humidity, precip, veg, erc = _synthetic_fields()
    leg = build_legacy17_channels(
        elev, wind_dir, wind_speed, tmax, tmin, humidity, precip, veg, erc
    )
    p14, missing, stamp = project_legacy17_to_physics14(leg, already_normalized=True)
    assert p14.shape == (14, 32, 32)
    assert missing.shape == (14, 32, 32)
    assert stamp["elev_gap"] is True
    assert stamp["temp_split_proxy"] is True
    assert stamp["ml_product_go"] is False
    assert stamp["work_class"] == "schema_bridge_projected"
    assert float(missing[0].mean()) == 1.0
    # elev GAP is constant after norm (raw zeros → constant channel); not spatial DEM
    assert float(np.std(p14[0])) < 1e-6


def test_project_with_elev_override_clears_gap():
    elev, wind_dir, wind_speed, tmax, tmin, humidity, precip, veg, erc = _synthetic_fields()
    leg = build_legacy17_channels(
        elev, wind_dir, wind_speed, tmax, tmin, humidity, precip, veg, erc
    )
    p14, missing, stamp = project_legacy17_to_physics14(
        leg, elev_override=elev, already_normalized=True
    )
    assert stamp["elev_gap"] is False
    assert float(missing[0].max()) == 0.0
    assert float(np.std(p14[0])) > 0.0


def test_project_sequence():
    elev, wind_dir, wind_speed, tmax, tmin, humidity, precip, veg, erc = _synthetic_fields()
    leg = build_legacy17_channels(
        elev, wind_dir, wind_speed, tmax, tmin, humidity, precip, veg, erc
    )
    seq = np.stack([leg, leg], axis=0)
    out, missing, stamp = project_sequence_legacy17_to_physics14(seq)
    assert out.shape == (2, 14, 32, 32)
    assert missing.shape == (2, 14, 32, 32)
    assert stamp["comparability"] == "not_same_as_sealed_legacy17_t1"


def test_no_silent_const_weather_as_spatial_claim():
    """Bridge must not claim geotiff spatial_v1."""
    elev, wind_dir, wind_speed, tmax, tmin, humidity, precip, veg, erc = _synthetic_fields()
    leg = build_legacy17_channels(
        elev, wind_dir, wind_speed, tmax, tmin, humidity, precip, veg, erc
    )
    _, _, stamp = project_legacy17_to_physics14(leg)
    assert "spatial_v1" not in stamp["work_class"]
    assert "Projected" in stamp["honesty"] or "projected" in stamp["honesty"].lower()


def test_partial_init_maps_some_channels():
    pytest.importorskip("torch")
    from wildfire_front.ml.schema_bridge import map_first_conv_multi_if_to_spatial
    from wildfire_front.ml.unet_train import UNetTrainConfig, build_model

    legacy = build_model(UNetTrainConfig(model="small", architecture="residual"), 18)
    spatial = build_model(UNetTrainConfig(model="small", architecture="residual"), 15)
    report = map_first_conv_multi_if_to_spatial(
        legacy.state_dict(), spatial, legacy_in_channels=18, spatial_in_channels=15
    )
    d = report.as_dict()
    assert d["mapped_input_channels"] >= 8
    assert d["ml_product_go"] is False
    assert d["frac_mapped"] > 0.4


def test_export_spatial_init_from_multi_if(tmp_path):
    torch = pytest.importorskip("torch")
    from wildfire_front.ml.schema_bridge import export_spatial_init_from_multi_if
    from wildfire_front.ml.unet_train import UNetTrainConfig, build_model

    # Synthetic multi_if-shaped checkpoint
    legacy = build_model(UNetTrainConfig(model="small", architecture="residual"), 18)
    src = tmp_path / "multi_if_fake.pt"
    torch.save(legacy.state_dict(), src)
    out = tmp_path / "spatial15.pt"
    rep = export_spatial_init_from_multi_if(src, out, spatial_in_channels=15)
    assert out.is_file()
    assert rep["strict_reload_ok"] is True
    assert rep["mapped_input_channels"] >= 8
    spatial = build_model(UNetTrainConfig(model="small", architecture="residual"), 15)
    spatial.load_state_dict(torch.load(out, map_location="cpu", weights_only=True), strict=True)


def test_export_real_multi_if_if_present(tmp_path):
    torch = pytest.importorskip("torch")
    from pathlib import Path

    from wildfire_front.ml.schema_bridge import export_spatial_init_from_multi_if
    from wildfire_front.ml.unet_train import UNetTrainConfig, build_model

    w = Path("models/clm_ensemble/weights_multi_if.pt")
    if not w.is_file():
        pytest.skip("weights_multi_if.pt not in workspace")
    out = tmp_path / "spatial15_real.pt"
    rep = export_spatial_init_from_multi_if(w, out)
    assert rep["strict_reload_ok"]
    assert rep["frac_mapped"] > 0.5
    # Adapted first-conv must differ from random spatial init
    spatial_rand = build_model(UNetTrainConfig(model="small", architecture="residual"), 15)
    spatial_ad = build_model(UNetTrainConfig(model="small", architecture="residual"), 15)
    spatial_ad.load_state_dict(torch.load(out, map_location="cpu", weights_only=True), strict=True)
    k = "backbone.inc.double_conv.0.weight"
    assert not torch.allclose(spatial_rand.state_dict()[k], spatial_ad.state_dict()[k])
