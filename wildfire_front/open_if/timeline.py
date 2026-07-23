"""Durable daily timeline series for open IF packs (offline-mergeable)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Mapping, Sequence


TIMELINE_SCHEMA = "open_if_timeline_daily_v1"
_FRP_KEYS = ("frp_sum", "frp_mean", "frp_max")


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _has_frp(block: Mapping[str, Any]) -> bool:
    return any(block.get(k) is not None for k in _FRP_KEYS)


def daily_stats_from_hotspot_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    sensor: str = "viirs_n20",
    date_key: str = "acq_date",
    frp_keys: Sequence[str] = ("frp", "FRP"),
) -> dict[str, dict[str, Any]]:
    """Aggregate hotspot CSV/dict rows into per-date counts + FRP stats.

    Returns mapping date -> {date, n_hotspots, frp_sum, frp_mean, frp_max, sensor}.
    """
    buckets: dict[str, list[float]] = {}
    for r in rows:
        d = str(r.get(date_key) or "").strip()
        if not d:
            continue
        frp_val: float | None = None
        for k in frp_keys:
            if r.get(k) not in (None, ""):
                try:
                    frp_val = float(r[k])  # type: ignore[arg-type]
                    break
                except (TypeError, ValueError):
                    continue
        # Bad FRP → count the hotspot with 0 contribution (explicit, not silent drop)
        buckets.setdefault(d, []).append(0.0 if frp_val is None else frp_val)

    out: dict[str, dict[str, Any]] = {}
    for d, frps in sorted(buckets.items()):
        n = len(frps)
        s = float(sum(frps))
        out[d] = {
            "date": d,
            "n_hotspots": n,
            "frp_sum": round(s, 2),
            "frp_mean": round(s / n, 2) if n else None,
            "frp_max": round(max(frps), 2) if frps else None,
            "sensor": sensor,
        }
    return out


def daily_stats_from_geojson_features(
    features: Sequence[Mapping[str, Any]],
    *,
    sensor: str = "viirs_n20",
) -> dict[str, dict[str, Any]]:
    """Same aggregation from GeoJSON Feature list (properties.acq_date / frp)."""
    rows: list[dict[str, Any]] = []
    for ft in features:
        props = ft.get("properties") or {}
        if not isinstance(props, Mapping):
            continue
        rows.append(dict(props))
    return daily_stats_from_hotspot_rows(rows, sensor=sensor)


def empty_timeline(event_id: str, *, sensor_primary: str = "viirs_n20_7d") -> dict[str, Any]:
    return {
        "schema": TIMELINE_SCHEMA,
        "event_id": event_id,
        "sensor_primary": sensor_primary,
        "updated_at": _utc_now(),
        "days": {},
        "series": [],
        "n_days": 0,
    }


def merge_timeline_days(
    existing: Mapping[str, Any] | None,
    new_days: Mapping[str, Mapping[str, Any]],
    *,
    event_id: str,
    sensor_primary: str = "viirs_n20_7d",
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Merge *new_days* into existing timeline.

    Rules per date:
    - Prefer larger ``n_hotspots`` (partial re-scrape must not shrink a full day).
    - When new n is not strictly greater and new lacks FRP, preserve previous FRP.
    - When new n is equal and new has FRP, accept new (refresh).
    """
    ts = generated_at or _utc_now()
    base = empty_timeline(event_id, sensor_primary=sensor_primary)
    if existing and isinstance(existing, Mapping):
        if existing.get("event_id"):
            base["event_id"] = existing["event_id"]
        if existing.get("sensor_primary"):
            base["sensor_primary"] = existing["sensor_primary"]
        days_in = existing.get("days") or {}
        if isinstance(days_in, Mapping):
            for d, block in days_in.items():
                if isinstance(block, Mapping):
                    base["days"][str(d)] = dict(block)

    for d, block in new_days.items():
        if not isinstance(block, Mapping):
            continue
        day = dict(block)
        day.setdefault("date", str(d))
        day["generated_at"] = ts
        prev = base["days"].get(str(d))
        if prev and isinstance(prev, Mapping):
            try:
                prev_n = int(prev.get("n_hotspots") or 0)
                new_n = int(day.get("n_hotspots") or 0)
            except (TypeError, ValueError):
                prev_n, new_n = 0, 0

            if prev_n > new_n:
                kept = dict(prev)
                kept["last_seen_at"] = ts
                kept["merge_note"] = "kept_higher_n_hotspots"
                base["days"][str(d)] = kept
                continue

            # Equal (or higher) n: if new lacks FRP, keep prior FRP fields
            if not _has_frp(day) and _has_frp(prev):
                for k in _FRP_KEYS:
                    if prev.get(k) is not None:
                        day[k] = prev[k]
                if prev_n == new_n:
                    day["merge_note"] = "preserved_frp_equal_n"
                else:
                    day["merge_note"] = "preserved_frp_higher_n_without_frp"

        base["days"][str(d)] = day

    series = [base["days"][k] for k in sorted(base["days"].keys())]
    base["series"] = series
    base["updated_at"] = ts
    base["n_days"] = len(series)
    return base


def append_counts_by_date(
    existing: Mapping[str, Any] | None,
    counts_by_date: Mapping[str, int],
    *,
    event_id: str,
    sensor: str = "viirs_n20_7d",
    frp_by_date: Mapping[str, Mapping[str, Any]] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Convenience: merge simple date→count map (optional FRP blocks).

    Counts-only rows set FRP keys to None; merge preserves prior FRP when
    n is not strictly greater (see :func:`merge_timeline_days`).
    """
    new_days: dict[str, dict[str, Any]] = {}
    frp_by_date = frp_by_date or {}
    for d, n in counts_by_date.items():
        block: dict[str, Any] = {
            "date": str(d),
            "n_hotspots": int(n),
            "sensor": sensor,
            "frp_sum": None,
            "frp_mean": None,
            "frp_max": None,
        }
        extra = frp_by_date.get(str(d)) or frp_by_date.get(d)
        if isinstance(extra, Mapping):
            for k in ("frp_sum", "frp_mean", "frp_max", "n_hotspots", "sensor"):
                if k in extra and extra[k] is not None:
                    block[k] = extra[k]
        new_days[str(d)] = block
    return merge_timeline_days(
        existing,
        new_days,
        event_id=event_id,
        sensor_primary=sensor,
        generated_at=generated_at,
    )
