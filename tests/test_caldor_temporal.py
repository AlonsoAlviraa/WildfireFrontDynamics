from __future__ import annotations

from datetime import UTC, datetime

from wildfire_front.open_if.caldor_temporal import (
    choose_hrrr_leads,
    erc_available_at_t0,
    gridmet_day_end_utc,
    hrrr_window_report,
    last_available_gridmet_day,
)


def test_last_available_gridmet_day_is_before_t0_end() -> None:
    t0 = datetime(2021, 8, 18, 3, 20, tzinfo=UTC)
    day = last_available_gridmet_day(t0)
    assert day.isoformat() == "2021-08-16"
    assert gridmet_day_end_utc(day) <= t0
    assert erc_available_at_t0(day, t0)
    assert not erc_available_at_t0("2021-08-18", t0)
    assert not erc_available_at_t0("2021-08-17", t0)


def test_hrrr_leads_cover_target_and_exclude_hours_before_t0() -> None:
    cycle = datetime(2021, 8, 18, 0, 0, tzinfo=UTC)
    t0 = datetime(2021, 8, 18, 3, 20, tzinfo=UTC)
    t1 = datetime(2021, 8, 19, 3, 30, tzinfo=UTC)
    leads = choose_hrrr_leads(cycle, t0, t1)
    assert min(leads) == 4
    assert max(leads) == 28
    assert leads == list(range(4, 29))
    report = hrrr_window_report(cycle, t0, t1, leads)
    assert report["no_hours_before_t0"] is True
    assert report["covers_target"] is True
    assert report["hourly_contiguous"] is True
    assert report["window_ok"] is True
    assert report["hours_before_t0"] == 0.0
    assert report["target_hours_uncovered"] == 0.0


def test_old_fixed_0_24_window_is_rejected() -> None:
    cycle = datetime(2021, 8, 18, 0, 0, tzinfo=UTC)
    t0 = datetime(2021, 8, 18, 3, 20, tzinfo=UTC)
    t1 = datetime(2021, 8, 19, 3, 30, tzinfo=UTC)
    report = hrrr_window_report(cycle, t0, t1, list(range(0, 25, 3)))
    assert report["window_ok"] is False
    assert report["no_hours_before_t0"] is False
    assert report["covers_target"] is False
