"""CRS helpers: UTM → WGS84 for web GeoJSON."""

from __future__ import annotations

from wildfire_front.geo_crs import geojson_to_wgs84, looks_projected_meters, utm_to_wgs84
from wildfire_front.emergency_products import (
    compute_short_horizon_envelope,
    envelope_to_geojson,
    write_envelope_geojson,
)


def test_utm_tobarra_region_is_spain():
    # Sample from Tobarra pack UTM 30N
    lon, lat = utm_to_wgs84(613000.0, 4277500.0, zone=30, northern=True)
    assert -3.0 < lon < 0.0
    assert 38.0 < lat < 40.0


def test_looks_projected():
    assert looks_projected_meters(613000.0, 4277500.0)
    assert not looks_projected_meters(-1.86, 38.6)


def test_geojson_to_wgs84_converts_polygon():
    fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [613000.0, 4277500.0],
                            [613100.0, 4277500.0],
                            [613100.0, 4277600.0],
                            [613000.0, 4277600.0],
                            [613000.0, 4277500.0],
                        ]
                    ],
                },
            }
        ],
    }
    out = geojson_to_wgs84(fc)
    pt = out["features"][0]["geometry"]["coordinates"][0][0]
    assert abs(pt[0]) <= 180 and abs(pt[1]) <= 90
    assert not looks_projected_meters(pt[0], pt[1])


def test_write_envelope_geojson_wgs84(tmp_path):
    env = compute_short_horizon_envelope(
        5.71, head_ros_m_min=6.9, flank_ros_m_min=5.71, rear_ros_m_min=2.8, expansion_bearing_deg=200.0
    )
    path = tmp_path / "emergency_envelope_guidance.geojson"
    # Tobarra-like UTM center
    write_envelope_geojson(
        env,
        path,
        center_xy=(612889.9, 4277300.4),
        fire_id="test",
        expansion_bearing_deg=200.0,
    )
    data = __import__("json").loads(path.read_text(encoding="utf-8"))
    pt = data["features"][0]["geometry"]["coordinates"][0][0]
    assert abs(pt[0]) <= 180
    assert (tmp_path / "emergency_envelope_guidance_utm.geojson").is_file()
