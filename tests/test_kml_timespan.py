"""Shipped TimeSpan KML transform + exporter entry point (briefing, not MET)."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.emergency_products import (  # noqa: E402
    compute_short_horizon_envelope,
    envelope_to_geojson,
)
from wildfire_front.kml_timespan import (  # noqa: E402
    KML_NS,
    ROLE_ENVELOPE,
    ROLE_PERIMETER,
    TIMEZONE_CONVENTION,
    TimedRing,
    build_briefing_kml,
    contiguous_timespans,
    iter_placemarks,
    kml_z,
    local_cest_to_utc,
    perimeter_features_from_rings,
    placemark_timespan,
)
from wildfire_front.ops_perimeter import parse_ops_perimeter  # noqa: E402

DROP = ROOT / "data" / "real_if" / "pablo_geacam_20260730_tobarra"
KMZ_1830 = DROP / "2024020124_TOBARRA_20240802_1830.kmz"
KMZ_2143 = DROP / "2024020124_TOBARRA_20240802_2143.kmz"
KML_1830 = DROP / "2024020124_TOBARRA_20240802_1830.kml"
KML_2143 = DROP / "2024020124_TOBARRA_20240802_2143.kml"
ENVELOPE = ROOT / "outputs" / "fuel_stack" / "tobarra" / "envelope_v3_hybrid.geojson"
OFFICIAL_MET = ROOT / "outputs" / "ml_eval" / "mega_goal_model" / "complete_proxy_model_iou.json"
SCRIPT = ROOT / "scripts" / "export_tobarra_timespan_kml.py"

real_drop = pytest.mark.skipif(not KMZ_1830.is_file(), reason="Tobarra KMZ drop missing")

RING_A = (
    (-1.71, 38.63),
    (-1.70, 38.63),
    (-1.70, 38.64),
    (-1.71, 38.64),
    (-1.71, 38.63),
)
RING_B = (
    (-1.72, 38.62),
    (-1.69, 38.62),
    (-1.69, 38.65),
    (-1.72, 38.65),
    (-1.72, 38.62),
)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def test_cest_filename_instants_encode_as_utc_z() -> None:
    t0 = local_cest_to_utc(datetime(2024, 8, 2, 18, 30, 0))
    t1 = local_cest_to_utc(datetime(2024, 8, 2, 21, 43, 0))
    assert kml_z(t0) == "2024-08-02T16:30:00Z"
    assert kml_z(t1) == "2024-08-02T19:43:00Z"
    assert "CEST" in TIMEZONE_CONVENTION or "UTC+2" in TIMEZONE_CONVENTION


def test_contiguous_spans_abut_without_interior_overlap() -> None:
    t0 = local_cest_to_utc(datetime(2024, 8, 2, 18, 30, 0))
    t1 = local_cest_to_utc(datetime(2024, 8, 2, 21, 43, 0))
    spans = contiguous_timespans([t0, t1])
    assert len(spans) == 2
    (b0, e0), (b1, e1) = spans
    assert b0 == t0
    assert e0 == t1
    assert b1 == t1
    assert e1 > b1
    assert e0 == b1
    assert not (b0 < b1 < e0)  # second begin is not strictly inside first


def test_two_timed_rings_kml_has_exactly_two_perimeter_timespans() -> None:
    rings = [
        TimedRing("Perímetro 18:30", datetime(2024, 8, 2, 18, 30, 0), RING_A),
        TimedRing("Perímetro 21:43", datetime(2024, 8, 2, 21, 43, 0), RING_B),
    ]
    kml = build_briefing_kml(rings)
    assert 'xmlns="http://www.opengis.net/kml/2.2"' in kml
    assert "<?xml version=" in kml
    peri = iter_placemarks(kml, role=ROLE_PERIMETER)
    assert len(peri) == 2
    assert len(iter_placemarks(kml, role=ROLE_ENVELOPE)) == 0
    t0, t1 = placemark_timespan(peri[0]), placemark_timespan(peri[1])
    assert t0[0] == "2024-08-02T16:30:00Z"
    assert t0[1] == "2024-08-02T19:43:00Z"
    assert t1[0] == "2024-08-02T19:43:00Z"
    assert t1[1] is not None and t1[1] > t1[0]
    assert t0[1] == t1[0]
    assert TIMEZONE_CONVENTION in kml
    assert "16:30" in kml and "19:43" in kml
    coords = " ".join("".join(el.itertext()) for el in peri[0].iter(f"{{{KML_NS}}}coordinates"))
    assert "-1.71" in coords or "-1.71000000" in coords


def test_envelope_geojson_becomes_kml_with_honesty_flags() -> None:
    env = compute_short_horizon_envelope(
        5.71,
        head_ros_m_min=6.9,
        flank_ros_m_min=5.71,
        rear_ros_m_min=2.8,
        expansion_bearing_deg=204.0,
    )
    fc = envelope_to_geojson(
        env, center_xy=(500000.0, 4200000.0), fire_id="test", expansion_bearing_deg=204.0
    )
    assert fc["features"]
    for feat in fc["features"]:
        assert feat["properties"].get("not_official_perimeter") is True

    rings = [
        TimedRing("Perímetro 18:30", datetime(2024, 8, 2, 18, 30, 0), RING_A),
        TimedRing("Perímetro 21:43", datetime(2024, 8, 2, 21, 43, 0), RING_B),
    ]
    kml = build_briefing_kml(rings, fc)
    env_pms = iter_placemarks(kml, role=ROLE_ENVELOPE)
    assert len(env_pms) == len(fc["features"])
    assert len(iter_placemarks(kml, role=ROLE_PERIMETER)) == 2
    blob = kml.lower()
    assert "not_official_perimeter" in blob
    assert "not_tactical" in blob
    assert "not infocam" in blob
    for pm in env_pms:
        begin, end = placemark_timespan(pm)
        assert begin and end
        name_el = pm.find(f"{{{KML_NS}}}name")
        assert name_el is not None and name_el.text
        assert "INFOCAM" not in name_el.text or "not INFOCAM" in name_el.text
        assert "ENVELOPE" in name_el.text
    # UTM meters must not leak into KML coordinates (lon/lat only)
    for el in ET.fromstring(kml).iter(f"{{{KML_NS}}}coordinates"):
        for token in (el.text or "").split():
            lon_s, lat_s, *_rest = token.split(",")
            lon, lat = float(lon_s), float(lat_s)
            assert abs(lon) <= 180.0
            assert abs(lat) <= 90.0


def test_perimeter_features_from_rings_drives_timespan_elements() -> None:
    els = perimeter_features_from_rings(
        [
            TimedRing("a", datetime(2024, 8, 2, 18, 30, 0), RING_A),
            TimedRing("b", datetime(2024, 8, 2, 21, 43, 0), RING_B),
        ]
    )
    assert len(els) == 2
    begins = []
    ends = []
    for el in els:
        ts = el.find(f"{{{KML_NS}}}TimeSpan")
        assert ts is not None
        begins.append(ts.find(f"{{{KML_NS}}}begin").text)
        ends.append(ts.find(f"{{{KML_NS}}}end").text)
    assert begins[0] == "2024-08-02T16:30:00Z"
    assert ends[0] == begins[1]


def _run_export(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(cwd or ROOT),
        capture_output=True,
        text=True,
    )


@real_drop
def test_cli_two_launches_match_and_leave_sources_and_met_untouched(tmp_path: Path) -> None:
    before_sources = {p: _sha256(p) for p in (KMZ_1830, KMZ_2143, KML_1830, KML_2143) if p.is_file()}
    met_before = _sha256(OFFICIAL_MET) if OFFICIAL_MET.is_file() else None
    out1 = tmp_path / "tobarra_timespan_1.kml"
    out2 = tmp_path / "tobarra_timespan_2.kml"
    extra: list[str] = []
    if ENVELOPE.is_file():
        extra.extend(["--envelope", str(ENVELOPE)])
    r1 = _run_export("--out", str(out1), *extra)
    r2 = _run_export("--out", str(out2), *extra)
    assert r1.returncode == 0, r1.stderr + r1.stdout
    assert r2.returncode == 0, r2.stderr + r2.stdout
    rec = json.loads(r1.stdout)
    assert rec["n_perimeter_features"] == 2
    assert rec["wrote_official_met_json"] is False
    assert rec["briefing_only"] is True
    for out in (out1, out2):
        text = out.read_text(encoding="utf-8")
        assert 'xmlns="http://www.opengis.net/kml/2.2"' in text
        assert "<TimeSpan>" in text
        peri = iter_placemarks(text, role=ROLE_PERIMETER)
        assert len(peri) == 2
        b0, e0 = placemark_timespan(peri[0])
        b1, _e1 = placemark_timespan(peri[1])
        assert b0 == "2024-08-02T16:30:00Z"
        assert e0 == "2024-08-02T19:43:00Z"
        assert b1 == "2024-08-02T19:43:00Z"
        assert parse_ops_perimeter(KMZ_1830, root=ROOT).coords_wgs84[0][0] < 0
    assert _sha256(out1) == _sha256(out2)
    for p, digest in before_sources.items():
        assert _sha256(p) == digest
    if met_before is not None:
        assert OFFICIAL_MET.is_file()
        assert _sha256(OFFICIAL_MET) == met_before
    if ENVELOPE.is_file():
        assert rec["n_envelope_features"] > 0
        assert rec["n_envelope_features"] == len(iter_placemarks(out1.read_text(encoding="utf-8"), role=ROLE_ENVELOPE))


@real_drop
def test_cli_refuses_source_drop_and_official_met(tmp_path: Path) -> None:
    r = _run_export("--out", str(DROP / "should_not_write.kml"))
    assert r.returncode == 4
    assert "refuses_overwrite_source_drop" in (r.stderr + r.stdout)
    assert not (DROP / "should_not_write.kml").exists()
    r2 = _run_export("--out", str(OFFICIAL_MET))
    assert r2.returncode == 4
    assert "refuses_official_met_json" in (r2.stderr + r2.stdout)
