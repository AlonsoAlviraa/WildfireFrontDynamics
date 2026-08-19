"""Leakage-safe Caldor temporal contract: ERC availability and HRRR valid times."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

GRIDMET_DAY_END_HOUR_UTC = 7
HRRR_MAX_LEAD_HOURS = 48


def parse_utc(stamp: str | datetime) -> datetime:
    if isinstance(stamp, datetime):
        value = stamp
    else:
        value = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def gridmet_day_end_utc(day: date) -> datetime:
    """gridMET calendar day D is complete at 07:00 UTC on D+1."""
    return datetime(day.year, day.month, day.day, tzinfo=UTC) + timedelta(
        days=1, hours=GRIDMET_DAY_END_HOUR_UTC
    )


def last_available_gridmet_day(t0: str | datetime) -> date:
    """Latest gridMET day whose declared end is at or before t0."""
    moment = parse_utc(t0)
    day = moment.date()
    while gridmet_day_end_utc(day) > moment:
        day = day - timedelta(days=1)
    return day


def choose_hrrr_leads(
    cycle: str | datetime,
    t0: str | datetime,
    t1: str | datetime,
    *,
    max_lead_hours: int = HRRR_MAX_LEAD_HOURS,
) -> list[int]:
    """Hourly HRRR leads whose valid times cover [t0, t1] and never start before t0.

    First lead is the first whole hour at or after t0. Last lead is the first
    whole hour at or after t1. Hours before t0 are excluded.
    """
    cycle_utc = parse_utc(cycle)
    start = parse_utc(t0)
    end = parse_utc(t1)
    if end < start:
        raise ValueError("t1 precedes t0")
    first = int((start - cycle_utc).total_seconds() // 3600)
    if cycle_utc + timedelta(hours=first) < start:
        first += 1
    last = int((end - cycle_utc).total_seconds() // 3600)
    if cycle_utc + timedelta(hours=last) < end:
        last += 1
    if first < 0:
        raise ValueError("HRRR cycle is after t0")
    if last > max_lead_hours:
        raise ValueError(
            f"HRRR lead {last}h exceeds cycle length {max_lead_hours}h; "
            "need a later cycle or a longer forecast"
        )
    if last < first:
        raise ValueError("HRRR window collapsed")
    return list(range(first, last + 1))


def hrrr_window_report(
    cycle: str | datetime,
    t0: str | datetime,
    t1: str | datetime,
    leads: list[int],
) -> dict[str, float | bool | int]:
    cycle_utc = parse_utc(cycle)
    start = parse_utc(t0)
    end = parse_utc(t1)
    if not leads:
        return {
            "first_valid_utc": None,
            "last_valid_utc": None,
            "hours_before_t0": None,
            "hours_after_t1": None,
            "target_hours_uncovered": (end - start).total_seconds() / 3600.0,
            "covers_target": False,
            "no_hours_before_t0": False,
            "hourly_contiguous": False,
            "window_ok": False,
        }
    first_valid = cycle_utc + timedelta(hours=min(leads))
    last_valid = cycle_utc + timedelta(hours=max(leads))
    expected = list(range(min(leads), max(leads) + 1))
    hours_before = max(0.0, (start - first_valid).total_seconds() / 3600.0)
    hours_after = max(0.0, (last_valid - end).total_seconds() / 3600.0)
    uncovered = max(0.0, (end - last_valid).total_seconds() / 3600.0)
    no_before = first_valid >= start
    covers = last_valid >= end and no_before
    contiguous = leads == expected
    return {
        "first_valid_utc": first_valid.isoformat().replace("+00:00", "Z"),
        "last_valid_utc": last_valid.isoformat().replace("+00:00", "Z"),
        "hours_before_t0": hours_before,
        "hours_after_t1": hours_after,
        "target_hours_uncovered": uncovered,
        "covers_target": covers,
        "no_hours_before_t0": no_before,
        "hourly_contiguous": contiguous,
        "window_ok": covers and contiguous,
    }


def erc_available_at_t0(gridmet_day: str | date, t0: str | datetime) -> bool:
    day = date.fromisoformat(gridmet_day) if isinstance(gridmet_day, str) else gridmet_day
    return gridmet_day_end_utc(day) <= parse_utc(t0)
