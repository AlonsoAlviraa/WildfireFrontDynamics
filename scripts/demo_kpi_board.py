#!/usr/bin/env python3
"""KPI board + compare matrix for multi-CCAA demo (sales stats)."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


def _f(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def count_csv_rows(path: Path) -> int:
    if not path.is_file():
        return 0
    with path.open(encoding="utf-8", newline="") as f:
        return max(0, sum(1 for _ in csv.DictReader(f)))


def load_metrics(pack_dir: Path) -> dict[str, Any]:
    p = pack_dir / "metrics_o2.json"
    if not p.is_file():
        return {}
    try:
        import json

        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def compute_kpi_board(
    sites: list[dict[str, Any]],
    *,
    root: Path,
    skips: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Aggregate KPIs for the sales strip + dashboard."""
    n_sites = len(sites)
    ccaa = sorted({s.get("ccaa_short") or s.get("ccaa") for s in sites if s.get("ccaa")})
    ha_list = []
    n_hold = 0
    n_partial = 0
    n_go_open = 0
    n_ops = 0
    n_confirmed = 0
    firms_ok = 0
    dnbr_ok = 0
    gate_pass = 0
    gate_total = 0

    for s in sites:
        kn = s.get("key_numbers") or {}
        ha = _f(kn.get("area_ha"))
        if ha is not None and s.get("track") != "OPS":
            ha_list.append(ha)
        dec = str(s.get("decision_open") or "").upper()
        verd = str(s.get("verdict") or "").upper()
        if "HOLD" in dec or "HOLD" in verd:
            n_hold += 1
        if "PARTIAL" in verd:
            n_partial += 1
        if verd.startswith("GO_") or verd == "GO":
            n_go_open += 1
        if s.get("track") == "OPS":
            n_ops += 1
            if s.get("status_anchor") == "confirmed":
                n_confirmed += 1
        gates = s.get("gates") or {}
        for g, st in gates.items():
            gate_total += 1
            if st == "PASS":
                gate_pass += 1
            if g in {"OPEN_FIRMS"} and st == "PASS":
                firms_ok += 1
            if g in {"OPEN_DNBR"} and st == "PASS":
                dnbr_ok += 1

    and_cat = root / "data" / "open_if" / "rediam_andalucia" / "inventory" / "event_catalog.csv"
    ext_cat = root / "data" / "open_if" / "extremadura_rai_2025" / "inventory" / "event_catalog.csv"
    n_and_catalog = count_csv_rows(and_cat)
    n_ext_delivery = count_csv_rows(ext_cat)

    sum_ha = round(sum(ha_list), 1) if ha_list else 0.0
    open_sites = max(1, n_sites - n_ops)

    kpis = [
        {"id": "ccaa", "label": "CCAA", "label_en": "Regions", "value": len(ccaa), "unit": "", "hint": ", ".join(str(c) for c in ccaa)},
        {"id": "sites", "label": "IF demo", "label_en": "Demo fires", "value": n_sites, "unit": "", "hint": "Tobarra · Níjar · Caminomorisco"},
        {"id": "ha_o2", "label": "ha O2 oficiales", "label_en": "Official O2 ha", "value": sum_ha, "unit": "ha", "hint": "Suma perímetros Junta (OPEN)"},
        {"id": "and_cat", "label": "Catálogo AND", "label_en": "AND catalog", "value": n_and_catalog, "unit": "IF", "hint": "REDIAM WFS 2022–25"},
        {"id": "ext_n", "label": "EXT entregados", "label_en": "EXT delivered", "value": n_ext_delivery, "unit": "IF", "hint": "RAI shapes 2025"},
        {"id": "anchors", "label": "Anclas confirmed", "label_en": "Confirmed anchors", "value": n_confirmed, "unit": "", "hint": "Vp/ha INFOCAM-class"},
        {"id": "hold", "label": "HOLD / cautela", "label_en": "HOLD posture", "value": n_hold, "unit": "", "hint": "Abstención sin ancla ops"},
        {
            "id": "gates",
            "label": "Gates PASS",
            "label_en": "Gates PASS",
            "value": f"{gate_pass}/{gate_total}" if gate_total else "—",
            "unit": "",
            "hint": "Scorecards industriales",
        },
    ]

    return {
        "schema": "demo_kpi_board_v1",
        "n_sites": n_sites,
        "n_ccaa": len(ccaa),
        "ccaa_list": ccaa,
        "sum_ha_o2": sum_ha,
        "n_and_catalog": n_and_catalog,
        "n_ext_delivery": n_ext_delivery,
        "n_confirmed_anchors": n_confirmed,
        "n_hold": n_hold,
        "n_partial": n_partial,
        "n_go_open": n_go_open,
        "n_ops": n_ops,
        "firms_pass": firms_ok,
        "dnbr_pass": dnbr_ok,
        "firms_coverage_ratio": round(firms_ok / open_sites, 3),
        "dnbr_coverage_ratio": round(dnbr_ok / open_sites, 3),
        "gate_pass": gate_pass,
        "gate_total": gate_total,
        "kpis": kpis,
        "skips": skips or {},
    }


def compute_compare_matrix(sites: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for s in sites:
        kn = s.get("key_numbers") or {}
        metrics = s.get("metrics") or {}
        rows.append(
            {
                "id": s.get("id"),
                "name": s.get("name_display") or s.get("name"),
                "ccaa": s.get("ccaa_short") or s.get("ccaa"),
                "track": s.get("track"),
                "area_ha": kn.get("area_ha"),
                "vp_m_min": kn.get("vp_m_min"),
                "lwir": bool(s.get("lwir")),
                "decision": s.get("decision_open"),
                "verdict": s.get("verdict"),
                "source": s.get("source"),
                "firms_n": metrics.get("n_firms_hotspots") or kn.get("firms_n"),
                "hausdorff_m": metrics.get("hausdorff_m"),
                "iou": metrics.get("iou_firms_buffer_vs_rediam")
                or metrics.get("iou_firms_buffer_vs_rai"),
                "risk": (
                    "OPS depends on partner thermal"
                    if s.get("track") == "OPS"
                    else "OPEN O2 without tactical Vp"
                ),
            }
        )
    return {
        "schema": "demo_compare_matrix_v1",
        "columns": [
            "name",
            "ccaa",
            "track",
            "area_ha",
            "vp_m_min",
            "lwir",
            "decision",
            "verdict",
            "source",
            "risk",
        ],
        "rows": rows,
    }


def scoreboard_rows(sites: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize gates across AND/EXT naming for a single table.

    Honesty: never synthesize industrial O2/NO_FALSE_DISPATCH PASS for OPS
    (Tobarra has no Junta O2 scorecard). O2 column = perímetro Junta only.
    """
    out = []
    for s in sites:
        g = s.get("gates") or {}
        track = s.get("track")
        if track == "OPS":
            # OPS LWIR + ancla — not an O2 industrial pack
            o2 = "n/a (OPS)"
            nfd = g.get("NO_FALSE_DISPATCH") or "—"  # only real scorecard field
            haus = g.get("O2_METHOD_HAUSDORFF") or "—"
            firms = g.get("OPEN_FIRMS") or "—"
            dnbr = g.get("OPEN_DNBR") or "—"
            prov = g.get("PROVENANCE") or "—"
            repro = g.get("REPRO") or "—"
        else:
            o2 = g.get("O2_REDIAM") or g.get("O2_RAI") or "—"
            nfd = g.get("NO_FALSE_DISPATCH") or "—"
            haus = g.get("O2_METHOD_HAUSDORFF") or "—"
            firms = g.get("OPEN_FIRMS") or "—"
            dnbr = g.get("OPEN_DNBR") or "—"
            prov = g.get("PROVENANCE") or "—"
            repro = g.get("REPRO") or "—"
        out.append(
            {
                "id": s.get("id"),
                "name": s.get("name_display") or s.get("name"),
                "O2": o2,
                "HAUSDORFF": haus,
                "FIRMS": firms,
                "DNBR": dnbr,
                "NO_FALSE_DISPATCH": nfd,
                "PROVENANCE": prov,
                "REPRO": repro,
                "verdict": s.get("verdict"),
                # OPS-native note (not an industrial O2 gate)
                "ops_anchor": (
                    "PASS"
                    if track == "OPS" and s.get("status_anchor") == "confirmed"
                    else ("SKIP" if track == "OPS" else None)
                ),
            }
        )
    return out


def svg_ha_bars(sites: list[dict[str, Any]], *, width: int = 520, height: int = 180) -> str:
    """Simple horizontal bar chart for official ha (OPEN) + Tobarra ha."""
    items = []
    for s in sites:
        ha = _f((s.get("key_numbers") or {}).get("area_ha"))
        if ha is None:
            continue
        items.append((s.get("name_display") or s.get("name") or s.get("id"), ha, s.get("track")))
    if not items:
        return "<p class='muted'>Sin ha para chart</p>"
    max_ha = max(h for _, h, _ in items) or 1.0
    pad_l, pad_r, pad_t, row_h = 110, 48, 12, 36
    bars = []
    for i, (name, ha, track) in enumerate(items):
        y = pad_t + i * row_h
        bw = int((width - pad_l - pad_r) * (ha / max_ha))
        color = "#f0a030" if track == "OPS" else "#3b9eff"
        bars.append(
            f'<text x="0" y="{y + 16}" fill="#8b9bb4" font-size="12">{_xml(name)}</text>'
            f'<rect x="{pad_l}" y="{y}" width="{max(bw, 2)}" height="22" rx="4" fill="{color}" opacity="0.9"/>'
            f'<text x="{pad_l + bw + 6}" y="{y + 16}" fill="#e8eef8" font-size="12">{ha:.0f} ha</text>'
        )
    h = pad_t + len(items) * row_h + 8
    return (
        f'<svg viewBox="0 0 {width} {h}" width="100%" height="{h}" '
        f'role="img" aria-label="Hectáreas por incendio demo">'
        + "".join(bars)
        + "</svg>"
    )


def _xml(s: Any) -> str:
    t = str(s or "")
    return (
        t.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
