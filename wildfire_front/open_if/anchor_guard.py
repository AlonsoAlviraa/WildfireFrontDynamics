"""Guards for promoting INFOCAM-style anchors to ``confirmed``.

Hard honesty rule: press estimates (area_ha_press_provisional) never promote
an anchor. Confirmed requires operational Vp + ha + explicit operational source.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

REQUIRED_CONFIRMED_FIELDS = ("vp_m_min", "area_ha", "source")

# Source must contain at least one operational marker for confirmed.
_OPERATIONAL_MARKERS = (
    "egif",
    "parte operativo",
    "parte",
    "oficial",
    "fidias",
    "operativo",
)
# Reject when these appear without a strong operational marker.
_ESTIMATE_MARKERS = (
    "estimad",
    "estimate",
    "x post",
    "provisional",
    "prensa",
    "press only",
)
_PRESS_MEDIA = ("elpais", "europapress", "euronews", "datawrapper")


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    return bool(isinstance(value, str) and not value.strip())


def _source_operational(src: str) -> bool:
    s = src.lower()
    if any(m in s for m in _OPERATIONAL_MARKERS):
        # INFOCAM alone + estimate language is not enough — need parte/egif/oficial/etc.
        return not (
            ("infocam" in s or "info cam" in s)
            and any(m in s for m in _ESTIMATE_MARKERS)
            and not any(m in s for m in ("egif", "parte", "oficial", "operativo", "fidias"))
        )
    # Bare "INFOCAM" without estimate language and without other markers: allow if
    # it looks like an operational part reference (year + INFOCAM).
    return bool("infocam" in s and not any(m in s for m in _ESTIMATE_MARKERS))


def can_promote_to_confirmed(anchor: Mapping[str, Any]) -> tuple[bool, list[str]]:
    """Return (ok, reasons) for promoting *anchor* to status ``confirmed``.

    Refuses when:
    - vp_m_min missing / non-numeric / non-positive
    - area_ha missing / non-numeric / non-positive
    - source missing, press-only, or estimate/provisional without EGIF/parte
    - only press provisional ha is present (area_ha_press_provisional without area_ha)
    """
    reasons: list[str] = []
    fire_id = str(anchor.get("fire_id") or anchor.get("id") or "?")

    vp = anchor.get("vp_m_min")
    if _is_missing(vp):
        reasons.append("missing_vp_m_min")
    else:
        try:
            vp_f = float(vp)  # type: ignore[arg-type]
            if vp_f <= 0:
                reasons.append("vp_m_min_not_positive")
        except (TypeError, ValueError):
            reasons.append("vp_m_min_not_numeric")

    area = anchor.get("area_ha")
    press_only = not _is_missing(anchor.get("area_ha_press_provisional")) and _is_missing(area)
    if press_only:
        reasons.append("area_ha_press_provisional_only_not_egif")
    if _is_missing(area):
        reasons.append("missing_area_ha")
    else:
        try:
            ha_f = float(area)  # type: ignore[arg-type]
            if ha_f <= 0:
                reasons.append("area_ha_not_positive")
        except (TypeError, ValueError):
            reasons.append("area_ha_not_numeric")

    h1 = anchor.get("H1")
    if h1 is not None:
        try:
            if int(h1) == 0:
                reasons.append("h1_zero_no_cite")
        except (TypeError, ValueError):
            reasons.append("h1_not_numeric")

    source = anchor.get("source")
    if _is_missing(source):
        reasons.append("missing_source")
    else:
        src = str(source).lower()
        if any(m in src for m in _PRESS_MEDIA) and not _source_operational(src):
            reasons.append("source_is_press_media_not_operational")
        if any(m in src for m in _ESTIMATE_MARKERS) and not any(
            m in src for m in ("egif", "parte", "oficial", "operativo", "fidias")
        ):
            reasons.append("source_is_estimate_or_provisional_not_operational")
        if not _source_operational(src):
            reasons.append("source_lacks_operational_marker")

    # Explicit: never treat provisional press ha as confirmed ha without EGIF source
    if not _is_missing(anchor.get("area_ha_press_provisional")) and not _is_missing(area):
        try:
            if abs(float(area) - float(anchor["area_ha_press_provisional"])) < 1e-6:  # type: ignore[arg-type]
                src = str(source or "").lower()
                if (
                    "egif" not in src
                    and "oficial" not in src
                    and "parte" not in src
                    and any(m in src for m in _ESTIMATE_MARKERS)
                ):
                    reasons.append("area_ha_matches_press_provisional_without_egif_source")
        except (TypeError, ValueError):
            pass

    ok = len(reasons) == 0
    if not ok:
        reasons.insert(0, f"refuse_confirmed:{fire_id}")
    return ok, reasons


def promote_anchor_to_confirmed(
    anchor: Mapping[str, Any],
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Return a new dict with status confirmed, or raise ValueError if refused.

    ``force=True`` is intentionally **not** allowed to bypass guards — kept only
    for API symmetry; always validates. Callers that need draft status use
    pending_external instead.
    """
    del force  # never bypass
    ok, reasons = can_promote_to_confirmed(anchor)
    if not ok:
        raise ValueError("; ".join(reasons))
    out = dict(anchor)
    out["status"] = "confirmed"
    return out


def assert_not_fake_confirmed(anchor: Mapping[str, Any]) -> None:
    """Raise if *anchor* claims confirmed without required operational fields."""
    if str(anchor.get("status") or "").lower() != "confirmed":
        return
    ok, reasons = can_promote_to_confirmed(anchor)
    if not ok:
        raise ValueError(f"fake_confirmed_anchor: {'; '.join(reasons)}")
