from __future__ import annotations

from datetime import UTC, datetime

from scripts.acquire_caldor_clean17 import (
    CLEAN17_CHANNELS,
    choose_hrrr_cycle,
    parse_hrrr_index,
)
from wildfire_front.open_if.caldor_temporal import (
    choose_hrrr_leads,
    last_available_gridmet_day,
)


def test_choose_hrrr_cycle_requires_operational_availability_lag() -> None:
    t0 = datetime(2021, 8, 18, 3, 20, tzinfo=UTC)
    assert choose_hrrr_cycle(t0) == datetime(2021, 8, 18, 0, 0, tzinfo=UTC)
    early = datetime(2021, 8, 18, 0, 20, tzinfo=UTC)
    assert choose_hrrr_cycle(early) == datetime(2021, 8, 17, 18, 0, tzinfo=UTC)


def test_parse_hrrr_index_selects_accumulated_precipitation_once() -> None:
    records = [
        ("VIS", "surface", "3 hour fcst"),
        ("PRES", "surface", "3 hour fcst"),
        ("TMP", "2 m above ground", "3 hour fcst"),
        ("DPT", "2 m above ground", "3 hour fcst"),
        ("RH", "2 m above ground", "3 hour fcst"),
        ("UGRD", "10 m above ground", "3 hour fcst"),
        ("VGRD", "10 m above ground", "3 hour fcst"),
        ("APCP", "surface", "0-3 hour acc fcst"),
        ("APCP", "surface", "2-3 hour acc fcst"),
        ("TCDC", "entire atmosphere", "3 hour fcst"),
        ("REFC", "entire atmosphere", "3 hour fcst"),
    ]
    text = "\n".join(
        f"{index + 1}:{index * 100}:d=2021081800:{element}:{level}:{descriptor}:"
        for index, (element, level, descriptor) in enumerate(records)
    )
    selected = parse_hrrr_index(text)
    assert len(selected) == 9
    precipitation = [row for row in selected if row["element"] == "APCP"]
    assert len(precipitation) == 1
    assert precipitation[0]["descriptor"].startswith("0-")


def test_acquire_helpers_use_repaired_temporal_contract() -> None:
    t0 = datetime(2021, 8, 18, 3, 20, tzinfo=UTC)
    t1 = datetime(2021, 8, 19, 3, 30, tzinfo=UTC)
    cycle = choose_hrrr_cycle(t0)
    leads = choose_hrrr_leads(cycle, t0, t1)
    assert min(leads) >= 4
    assert max(leads) >= 28
    assert last_available_gridmet_day(t0).isoformat() == "2021-08-16"


def test_clean17_is_real_schema_not_legacy_placeholder_contract() -> None:
    assert len(CLEAN17_CHANNELS) == 17
    assert "surface_pressure_hpa" in CLEAN17_CHANNELS
    assert "total_cloud_cover_pct" in CLEAN17_CHANNELS
    assert "visibility_km" in CLEAN17_CHANNELS
    assert "dew_point_c" in CLEAN17_CHANNELS
