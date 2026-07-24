"""dNBR queue status from STAC search results (honest blocked/ready)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

DNBR_QUEUE_SCHEMA = "open_if_dnbr_queue_v1"


def _cloud(item: Mapping[str, Any]) -> float | None:
    if "eo:cloud_cover" in item:
        try:
            return float(item["eo:cloud_cover"])
        except (TypeError, ValueError):
            return None
    props = item.get("properties") or {}
    if isinstance(props, Mapping) and "eo:cloud_cover" in props:
        try:
            return float(props["eo:cloud_cover"])
        except (TypeError, ValueError):
            return None
    return None


def _item_id(item: Mapping[str, Any]) -> str | None:
    return item.get("id") if item.get("id") else None


def _is_clear(item: Mapping[str, Any], max_cloud: float) -> bool:
    """True only when cloud cover is known and ≤ max_cloud (unknown ≠ clear)."""
    c = _cloud(item)
    return c is not None and c <= max_cloud


def _item_day(item: Mapping[str, Any]) -> str:
    dt = str(item.get("datetime") or (item.get("properties") or {}).get("datetime") or "")
    return dt[:10] if len(dt) >= 10 else ""


def evaluate_dnbr_queue(
    *,
    pre_items: Sequence[Mapping[str, Any]] | None,
    post_items: Sequence[Mapping[str, Any]] | None,
    during_clear_items: Sequence[Mapping[str, Any]] | None = None,
    max_cloud: float = 30.0,
    event_date: str | None = None,
) -> dict[str, Any]:
    """Decide dNBR queue status from STAC item summaries.

    - ``ready``: **both** pre_clear and post_clear non-empty
    - ``blocked_clouds``: cloudy / incomplete post or no clear post with pre present
    - ``blocked_no_pre``: no pre scenes at all
    - ``blocked_no_clear_pre`` (detail): pre items exist but none clear; or incomplete_pre_only

    Unknown cloud cover is **not** treated as clear.
    When ``event_date`` is set, post scenes must be strictly **after** that date
    (filter always applied — no fallback to unfiltered posts).
    During-fire clear scenes do **not** count as post-fire.
    """
    pre = list(pre_items or [])
    post = list(post_items or [])
    during = list(during_clear_items or [])

    pre_clear = [i for i in pre if _is_clear(i, max_cloud)]
    post_clear = [i for i in post if _is_clear(i, max_cloud)]
    n_post_unknown_cloud = sum(1 for i in post if _cloud(i) is None)
    n_post_cloudy = 0
    for i in post:
        c = _cloud(i)
        if c is not None and c > max_cloud:
            n_post_cloudy += 1
    n_pre_unknown_cloud = sum(1 for i in pre if _cloud(i) is None)
    n_pre_cloudy = 0
    for i in pre:
        c = _cloud(i)
        if c is not None and c > max_cloud:
            n_pre_cloudy += 1

    # Always apply event_date filter when set (no unfiltered fallback).
    n_post_on_or_before_event = 0
    if event_date:
        filtered: list[Mapping[str, Any]] = []
        for i in post_clear:
            day = _item_day(i)
            if day and day > event_date:
                filtered.append(i)
            else:
                n_post_on_or_before_event += 1
        post_clear = list(filtered)

    reasons: list[str] = []
    if not pre:
        detail_status = "blocked_no_pre"
        reasons.append("no_pre_fire_stac_items")
    elif not pre_clear:
        # Pre exists but none clear — cannot be ready even with clear post
        detail_status = "blocked_no_clear_pre"
        reasons.append("no_clear_pre_fire_stac_items")
        if n_pre_cloudy:
            reasons.append(f"pre_cloudy_above_max={n_pre_cloudy}")
        if n_pre_unknown_cloud:
            reasons.append(f"pre_unknown_cloud_excluded={n_pre_unknown_cloud}")
        if not post_clear:
            reasons.append("also_missing_clear_post")
    elif not post_clear:
        detail_status = "incomplete_pre_only"
        reasons.append("clear_pre_only_missing_clear_post")
        reasons.append("dnbr_incomplete_without_post")
        if during:
            reasons.append(f"during_fire_clear_scenes={len(during)}_not_usable_as_post")
        if n_post_unknown_cloud:
            reasons.append(f"post_unknown_cloud_excluded={n_post_unknown_cloud}")
        if n_post_cloudy:
            reasons.append(f"post_cloudy_above_max={n_post_cloudy}")
        if event_date and n_post_on_or_before_event:
            reasons.append(f"post_on_or_before_event_date_excluded={n_post_on_or_before_event}")
        reasons.append("blocked_clouds_or_no_post_window")
    else:
        # Both pre_clear and post_clear non-empty
        detail_status = "ready"
        reasons.append("clear_pre_and_post_available")

    # Pack-level status
    if detail_status == "ready":
        queue_status = "ready"
    elif detail_status == "blocked_no_pre":
        queue_status = "blocked_no_pre"
    else:
        # blocked_no_clear_pre / incomplete_pre_only → not ready for full dNBR
        queue_status = "blocked_clouds"

    return {
        "schema": DNBR_QUEUE_SCHEMA,
        "status": queue_status,
        "detail_status": detail_status,
        "max_cloud": max_cloud,
        "event_date": event_date,
        "n_pre": len(pre),
        "n_pre_clear": len(pre_clear),
        "n_post": len(post),
        "n_post_clear": len(post_clear),
        "n_post_unknown_cloud": n_post_unknown_cloud,
        "n_post_on_or_before_event": n_post_on_or_before_event if event_date else 0,
        "n_during_clear": len(during),
        "pre_top": _item_id(pre_clear[0]) if pre_clear else None,
        "post_top": _item_id(post_clear[0]) if post_clear else None,
        "reasons": reasons,
        "updated_at": datetime.now(UTC).isoformat(),
        "not_official_severity": True,
        "note": (
            "Queue only — does not invent dNBR. Full product needs clear post-fire S2/HLS. "
            "Unknown cloud cover is excluded from clear lists. "
            "ready requires both clear pre and clear post (post strictly after event_date)."
        ),
    }


def stac_items_from_enrichment_doc(stac_doc: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Extract pre / during item lists from enrich_la_mierla sentinel2_stac_search.json."""
    searches = stac_doc.get("searches") or {}
    pre = list((searches.get("pre_fire_01_15_jul") or {}).get("items") or [])
    during = list((searches.get("during_fire_14_21_jul") or {}).get("items") or [])
    strict = list((searches.get("strict_clear_during") or {}).get("items") or [])
    post = list(
        (searches.get("post_fire") or searches.get("post_fire_clear") or {}).get("items") or []
    )
    return {"pre": pre, "during": during, "strict_clear_during": strict, "post": post}
