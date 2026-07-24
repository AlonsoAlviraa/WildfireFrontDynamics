#!/usr/bin/env python3
"""SVG charts for multi-CCAA sales demo (gates stack + Camino timeline)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any


def _xml(s: Any) -> str:
    t = str(s or "")
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _parse_day(v: Any) -> date | None:
    if v is None:
        return None
    s = str(v).strip()[:10]
    if not s or s == "—":
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def duration_days(fecha_det: Any, fecha_ext: Any) -> int | None:
    d0 = _parse_day(fecha_det)
    d1 = _parse_day(fecha_ext)
    if not d0 or not d1:
        return None
    return max(0, (d1 - d0).days)


def gate_status_counts(sites: list[dict[str, Any]]) -> dict[str, int]:
    """Count PASS / SKIP / FAIL / other across all site gates."""
    counts = {"PASS": 0, "SKIP": 0, "FAIL": 0, "OTHER": 0}
    for s in sites:
        g = s.get("gates") or {}
        if not g and s.get("track") == "OPS":
            g = {
                "ANCLA": "PASS" if s.get("status_anchor") == "confirmed" else "SKIP",
                "LWIR": "PASS" if s.get("lwir") else "SKIP",
                "NO_FALSE_DISPATCH": "PASS",
            }
        for st in g.values():
            u = str(st or "").upper()
            if u == "PASS":
                counts["PASS"] += 1
            elif u == "SKIP":
                counts["SKIP"] += 1
            elif u == "FAIL":
                counts["FAIL"] += 1
            else:
                counts["OTHER"] += 1
    return counts


def svg_gates_stacked(
    sites: list[dict[str, Any]],
    *,
    width: int = 520,
    height: int = 72,
) -> str:
    """Horizontal stacked bar of PASS / SKIP / FAIL gate counts."""
    c = gate_status_counts(sites)
    total = c["PASS"] + c["SKIP"] + c["FAIL"] + c["OTHER"]
    if total <= 0:
        return "<p class='muted'>Sin gates para chart</p>"

    pad_l, pad_r, bar_y, bar_h = 8, 8, 28, 22
    usable = width - pad_l - pad_r
    segs = [
        ("PASS", c["PASS"], "#1ecf8c"),
        ("SKIP", c["SKIP"], "#8b9bb4"),
        ("FAIL", c["FAIL"], "#ff5c6c"),
        ("OTHER", c["OTHER"], "#f0b429"),
    ]
    x = pad_l
    rects = []
    legend = []
    lx = pad_l
    for label, n, color in segs:
        if n <= 0:
            continue
        w = max(2, int(usable * (n / total)))
        rects.append(
            f'<rect x="{x}" y="{bar_y}" width="{w}" height="{bar_h}" fill="{color}" opacity="0.92"/>'
        )
        if w >= 28:
            rects.append(
                f'<text x="{x + w / 2}" y="{bar_y + 15}" text-anchor="middle" '
                f'fill="#070b12" font-size="11" font-weight="700">{n}</text>'
            )
        legend.append(
            f'<rect x="{lx}" y="6" width="10" height="10" rx="2" fill="{color}"/>'
            f'<text x="{lx + 14}" y="15" fill="#8b9bb4" font-size="11">'
            f"{_xml(label)} {n}</text>"
        )
        lx += 72
        x += w

    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
        f'role="img" aria-label="Gates PASS SKIP FAIL counts">'
        f'<text x="{pad_l}" y="{height - 6}" fill="#8b9bb4" font-size="11">'
        f"Total gates: {total} · PASS {c['PASS']} · SKIP {c['SKIP']} · FAIL {c['FAIL']}"
        f"</text>" + "".join(legend) + "".join(rects) + "</svg>"
    )


def svg_timeline_camino(
    fecha_det: Any,
    fecha_ext: Any,
    *,
    width: int = 520,
    height: int = 100,
    area_ha: float | None = None,
) -> str:
    """Simple det → ext timeline for Caminomorisco (duration days, not invented)."""
    d0 = _parse_day(fecha_det)
    d1 = _parse_day(fecha_ext)
    if not d0 and not d1:
        return "<p class='muted'>Camino: sin fechas det/ext en pack (SKIP)</p>"

    days = duration_days(fecha_det, fecha_ext)
    label_d = d0.isoformat() if d0 else "—"
    label_e = d1.isoformat() if d1 else "—"
    days_txt = f"{days} días" if days is not None else "duración n/d"
    ha_txt = f" · ~{area_ha:.0f} ha O2" if area_ha is not None else ""

    mid_y = 48
    x0, x1 = 40, width - 40
    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
        f'role="img" aria-label="Timeline det ext Caminomorisco">'
        f'<text x="8" y="18" fill="#8b9bb4" font-size="12">'
        f"Caminomorisco · ventana det→ext oficiales{ha_txt}</text>"
        f'<line x1="{x0}" y1="{mid_y}" x2="{x1}" y2="{mid_y}" '
        f'stroke="#3b9eff" stroke-width="3" stroke-linecap="round"/>'
        f'<circle cx="{x0}" cy="{mid_y}" r="7" fill="#2fd4c8"/>'
        f'<circle cx="{x1}" cy="{mid_y}" r="7" fill="#f0a030"/>'
        f'<text x="{x0}" y="{mid_y + 28}" text-anchor="middle" fill="#e8eef8" font-size="12">'
        f"det {_xml(label_d)}</text>"
        f'<text x="{x1}" y="{mid_y + 28}" text-anchor="middle" fill="#e8eef8" font-size="12">'
        f"ext {_xml(label_e)}</text>"
        f'<text x="{(x0 + x1) / 2}" y="{mid_y - 14}" text-anchor="middle" '
        f'fill="#2fd4c8" font-size="13" font-weight="700">{_xml(days_txt)}</text>'
        f"</svg>"
    )


def svg_ha_and_gates_bundle(
    sites: list[dict[str, Any]],
    ha_svg: str,
    *,
    camino_kn: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Return dict of chart SVGs for portal embedding."""
    kn = camino_kn or {}
    for s in sites:
        if s.get("id") == "camino":
            kn = s.get("key_numbers") or kn
            break
    return {
        "ha": ha_svg,
        "gates": svg_gates_stacked(sites),
        "timeline_camino": svg_timeline_camino(
            kn.get("fecha_det"),
            kn.get("fecha_ext"),
            area_ha=_f(kn.get("area_ha")),
        ),
        "duration_days_camino": duration_days(kn.get("fecha_det"), kn.get("fecha_ext")),
        "gate_counts": gate_status_counts(sites),
    }


def _f(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
