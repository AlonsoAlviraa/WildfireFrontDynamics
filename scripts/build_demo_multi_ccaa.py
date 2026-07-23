#!/usr/bin/env python3
"""Build the multi-CCAA demo hub (Tobarra OPS + Níjar AND + Caminomorisco EXT).

One-command:

    python scripts/build_demo_multi_ccaa.py
    start outputs/demo_multi_ccaa/index.html

Idempotent. Fails soft if optional assets missing (SKIP flags in demo_manifest.json).
Does not invent Vp/ha or pack dates. Embeds key numbers from anchors + pack scorecards.
"""

from __future__ import annotations

import html as html_lib
import json
import os
import re
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "demo_multi_ccaa"

# Pack / source paths (repo-relative)
TOBARRA_ANCHOR_KEY = "tobarra_20240802"
AND_PACK_ID = "and_2024040053_20240606"
EXT_PACK_ID = "ext_2025100393_20250729"

AND_PACK = ROOT / "outputs" / "open_if" / AND_PACK_ID
EXT_PACK = ROOT / "outputs" / "open_if" / EXT_PACK_ID
ANCHORS_PATH = ROOT / "data" / "infocam_anchors.json"
TEMPORAL_TOBARRA = ROOT / "outputs" / "temporal_windows" / "tobarra_20240802"

TOBARRA_FIGS = {
    "ros": ROOT / "docs" / "entrega_cma" / "fig_tobarra_ros.png",
    "area": ROOT / "docs" / "entrega_cma" / "fig_tobarra_area.png",
}
ACTA_GOLD = ROOT / "docs" / "GOLD_IF_E2E_VERIFICATION.md"
ACTA_AND = ROOT / "docs" / "AND_INDUSTRIAL_E2E_VERIFICATION.md"
ACTA_EXT = ROOT / "docs" / "EXT_INDUSTRIAL_E2E_VERIFICATION.md"
PLAN_DOC = ROOT / "docs" / "design" / "DEMO_MULTI_CCAA_TOBARRA_NIJAR_CAMINOMORISCO.md"


def _load(p: Path) -> dict[str, Any] | None:
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _rel(from_dir: Path, target: Path) -> str | None:
    if not target.exists():
        return None
    try:
        return Path(os.path.relpath(str(target.resolve()), str(from_dir.resolve()))).as_posix()
    except ValueError:
        return None


def _safe_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _flag_true(v: Any) -> bool:
    """Only explicit JSON boolean True (not string 'false', not missing)."""
    return v is True


def _esc(s: Any) -> str:
    """HTML-escape dynamic text for element content and attributes."""
    if s is None:
        return ""
    return html_lib.escape(str(s), quote=True)


def _safe_href(href: str | None) -> str | None:
    """Allow only relative paths (from _rel). Reject schemes / absolute Windows paths."""
    if not href:
        return None
    h = str(href).strip().replace("\\", "/")
    if not h or h.startswith("/") or h.startswith("\\"):
        return None
    low = h.lower()
    if "://" in h or low.startswith("javascript:") or h.startswith("//"):
        return None
    if len(h) >= 2 and h[1] == ":":  # C:/...
        return None
    if ".." in h.split("/")[0] and not h.startswith("../"):
        # odd; still allow normal ../ relative
        pass
    return h


def collect_sites() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Read anchors/packs/scorecards and return site dicts + skip flags."""
    skips: dict[str, Any] = {}
    sites: list[dict[str, Any]] = []

    # --- Tobarra (OPS) ---
    anchors = _load(ANCHORS_PATH) or {}
    tb = (anchors.get("anchors") or {}).get(TOBARRA_ANCHOR_KEY) or {}
    tb_status = tb.get("status")
    tb_present = bool(tb_status == "confirmed" and tb.get("vp_m_min") is not None)
    skips["tobarra_anchor"] = "OK" if tb_present else "SKIP_missing_or_unconfirmed"
    fig_ros_ok = TOBARRA_FIGS["ros"].is_file()
    fig_area_ok = TOBARRA_FIGS["area"].is_file()
    skips["tobarra_fig_ros"] = "OK" if fig_ros_ok else "SKIP"
    skips["tobarra_fig_area"] = "OK" if fig_area_ok else "SKIP"
    skips["acta_gold"] = "OK" if ACTA_GOLD.is_file() else "SKIP"
    temporal_ok = TEMPORAL_TOBARRA.is_dir()
    skips["tobarra_temporal"] = "OK" if temporal_ok else "SKIP"

    # Fire-id date is identity of the demo slot (not invented pack metric)
    year_tb = "2024-08-02"
    # Publish Vp/ha only when anchor is confirmed (honesty: no provisional numbers as tactical)
    if tb_status == "confirmed":
        vp_tb = _safe_float(tb.get("vp_m_min"))
        ha_tb = _safe_float(tb.get("area_ha"))
    else:
        vp_tb = None
        ha_tb = None

    sites.append(
        {
            "id": "tobarra",
            "panel": "tobarra",
            "name": "Tobarra",
            "name_display": "Tobarra",
            "ccaa": "Castilla-La Mancha",
            "ccaa_short": "CLM",
            "year_label": year_tb,
            "track": "OPS",
            "track_label": "A · OPS gold",
            "verdict": "Grade A / OPS gold" if tb_present else "PENDING",
            "decision_open": "GO_OPS" if tb_present else "HOLD",
            "key_numbers": {
                "vp_m_min": vp_tb,
                "area_ha": ha_tb,
                "vp_invented": False,
            },
            "headline": (
                f"LWIR + Vp {vp_tb if vp_tb is not None else '—'} m/min · "
                f"{ha_tb if ha_tb is not None else '—'} ha"
                if tb_status == "confirmed"
                else f"LWIR OPS · ancla {tb_status or 'SKIP'} (Vp/ha no publicados)"
            ),
            "source": tb.get("source") or "INFOCAM ancla",
            "attribution": "INFOCAM 2024 parte operativo · material Heligrafics/CMA (LWIR)",
            "what_shows": "ROS multi-estimador + ancla real confirmada"
            if tb_present
            else "OPS slot — ancla no confirmada en anchors",
            "what_not": "“Funciona en toda España sin datos”",
            "links": {
                "map": None,  # figures instead
                "fig_ros": _rel(OUT, TOBARRA_FIGS["ros"]) if fig_ros_ok else None,
                "fig_area": _rel(OUT, TOBARRA_FIGS["area"]) if fig_area_ok else None,
                "brief": None,
                "scorecard": None,
                "acta": _rel(OUT, ACTA_GOLD) if ACTA_GOLD.is_file() else None,
                "anchor": _rel(OUT, ANCHORS_PATH) if ANCHORS_PATH.is_file() else None,
                "temporal": _rel(OUT, TEMPORAL_TOBARRA) if temporal_ok else None,
            },
            "pack_id": TOBARRA_ANCHOR_KEY,
            "status_anchor": tb_status,
            "firms_hull_is_official_burned_area": False,
            "lwir": True,
            "vp_invented": False,
            "scorecard_present": False,
        }
    )

    # --- Níjar (AND) ---
    and_man_raw = _load(AND_PACK / "manifest.json")
    and_sc_raw = _load(AND_PACK / "scorecard_and_industrial.json")
    and_man = and_man_raw or {}
    and_sc = and_sc_raw or {}
    and_map = AND_PACK / "map.html"
    and_brief = AND_PACK / "operator_brief_open_if.md"
    and_ok = bool(and_man.get("pack_id") or and_man.get("codigo"))
    and_sc_present = and_sc_raw is not None
    skips["and_pack"] = "OK" if and_ok else "SKIP_missing_pack"
    skips["and_map"] = "OK" if and_map.is_file() else "SKIP"
    skips["and_scorecard"] = "OK" if and_sc_present else "SKIP"
    skips["and_brief"] = "OK" if and_brief.is_file() else "SKIP"
    skips["acta_and"] = "OK" if ACTA_AND.is_file() else "SKIP"

    area_and = _safe_float(and_man.get("area_rediam_ha")) if and_ok else None
    fecha_and = and_man.get("fecha_inc") if and_ok else None
    year_and = fecha_and if fecha_and else "—"
    vp_and_inv = _flag_true(and_sc.get("vp_invented")) if and_sc_present else False
    hull_and = _flag_true(and_sc.get("firms_hull_is_official_burned_area")) if and_sc_present else False

    sites.append(
        {
            "id": "nijar",
            "panel": "nijar",
            "name": "Níjar",
            "name_display": "Níjar",
            "aliases": ["Nijar", "NIJAR"],
            "ccaa": "Andalucía",
            "ccaa_short": "AND",
            "year_label": year_and,
            "track": "OPEN_O2",
            "track_label": "B+ · OPEN O2 REDIAM",
            "verdict": (and_sc.get("verdict") or and_man.get("scorecard_verdict") or "—")
            if and_ok
            else "—",
            "decision_open": (and_sc.get("decision_open") or "HOLD") if and_ok else "HOLD",
            "key_numbers": {
                "area_ha": area_and,
                "vp_m_min": None,
                "vp_invented": vp_and_inv,
                "codigo": and_man.get("codigo") if and_ok else None,
            },
            "headline": (
                f"Perímetro REDIAM ~{area_and:.0f} ha"
                if area_and is not None
                else ("Perímetro REDIAM" if and_ok else "Pack AND no disponible (SKIP)")
            ),
            "source": "REDIAM — Junta de Andalucía",
            "attribution": (
                and_sc.get("attribution")
                or and_man.get("attribution")
                or "Fuente: REDIAM — Junta de Andalucía"
            ),
            "what_shows": "O2 institucional multi-IF + satélite (FIRMS/dNBR)",
            "what_not": "“Vp táctico AND”",
            "links": {
                "map": _rel(OUT, and_map) if and_map.is_file() else None,
                "fig_ros": None,
                "fig_area": None,
                "brief": _rel(OUT, and_brief) if and_brief.is_file() else None,
                "scorecard": _rel(OUT, AND_PACK / "scorecard_and_industrial.json")
                if (AND_PACK / "scorecard_and_industrial.json").is_file()
                else None,
                "acta": _rel(OUT, ACTA_AND) if ACTA_AND.is_file() else None,
                "anchor": None,
                "temporal": None,
            },
            "pack_id": (and_man.get("pack_id") or AND_PACK_ID) if and_ok else AND_PACK_ID,
            "gates": and_sc.get("gates") or {},
            "firms_hull_is_official_burned_area": hull_and,
            "lwir": False,
            "vp_invented": vp_and_inv,
            "scorecard_present": and_sc_present,
            "municipio": and_man.get("municipio") if and_ok else None,
        }
    )

    # --- Caminomorisco (EXT) ---
    ext_man_raw = _load(EXT_PACK / "manifest.json")
    ext_sc_raw = _load(EXT_PACK / "scorecard_ext_industrial.json")
    ext_man = ext_man_raw or {}
    ext_sc = ext_sc_raw or {}
    ext_map = EXT_PACK / "map.html"
    ext_brief = EXT_PACK / "operator_brief_open_if.md"
    ext_ok = bool(ext_man.get("pack_id") or ext_man.get("id_incen"))
    ext_sc_present = ext_sc_raw is not None
    skips["ext_pack"] = "OK" if ext_ok else "SKIP_missing_pack"
    skips["ext_map"] = "OK" if ext_map.is_file() else "SKIP"
    skips["ext_scorecard"] = "OK" if ext_sc_present else "SKIP"
    skips["ext_brief"] = "OK" if ext_brief.is_file() else "SKIP"
    skips["acta_ext"] = "OK" if ACTA_EXT.is_file() else "SKIP"

    area_ext = (
        _safe_float(ext_man.get("area_rai_ha") or ext_man.get("hectareas_attr"))
        if ext_ok
        else None
    )
    # Only use dates from loaded manifest — never invent plan defaults when pack SKIP
    fecha_det = ext_man.get("fecha_det") if ext_ok else None
    fecha_ext = ext_man.get("fecha_ext") if ext_ok else None
    if fecha_det and fecha_ext:
        year_ext = f"{fecha_det} → {fecha_ext}"
    elif fecha_det:
        year_ext = str(fecha_det)
    elif fecha_ext:
        year_ext = str(fecha_ext)
    else:
        year_ext = "—"

    vp_ext_inv = _flag_true(ext_sc.get("vp_invented")) if ext_sc_present else False
    hull_ext = _flag_true(ext_sc.get("firms_hull_is_official_burned_area")) if ext_sc_present else False

    if area_ext is not None and fecha_det:
        headline_ext = f"Perímetro RAI ~{area_ext:.0f} ha · det {fecha_det}"
    elif area_ext is not None:
        headline_ext = f"Perímetro RAI ~{area_ext:.0f} ha"
    elif ext_ok:
        headline_ext = "Perímetro RAI"
    else:
        headline_ext = "Pack EXT no disponible (SKIP)"

    sites.append(
        {
            "id": "camino",
            "panel": "camino",
            "name": "Caminomorisco",
            "name_display": "Caminomorisco",
            "ccaa": "Extremadura",
            "ccaa_short": "EXT",
            "year_label": year_ext,
            "track": "OPEN_O2",
            "track_label": "B+ · OPEN O2 RAI",
            "verdict": (ext_sc.get("verdict") or ext_man.get("verdict") or "—") if ext_ok else "—",
            "decision_open": (ext_sc.get("decision_open") or "HOLD") if ext_ok else "HOLD",
            "key_numbers": {
                "area_ha": area_ext,
                "vp_m_min": None,
                "vp_invented": vp_ext_inv,
                "id_incen": ext_man.get("id_incen") if ext_ok else None,
                "fecha_det": fecha_det,
                "fecha_ext": fecha_ext,
            },
            "headline": headline_ext,
            "source": "RAI / INFOEX — Junta de Extremadura",
            "attribution": (
                ext_sc.get("attribution")
                or ext_man.get("attribution")
                or "Fuente: RAI — Junta de Extremadura / INFOEX"
            ),
            "what_shows": "O2 CCAA con ventana det–ext oficiales",
            "what_not": "“Ha satélite = quemado oficial”",
            "links": {
                "map": _rel(OUT, ext_map) if ext_map.is_file() else None,
                "fig_ros": None,
                "fig_area": None,
                "brief": _rel(OUT, ext_brief) if ext_brief.is_file() else None,
                "scorecard": _rel(OUT, EXT_PACK / "scorecard_ext_industrial.json")
                if (EXT_PACK / "scorecard_ext_industrial.json").is_file()
                else None,
                "acta": _rel(OUT, ACTA_EXT) if ACTA_EXT.is_file() else None,
                "anchor": None,
                "temporal": None,
            },
            "pack_id": (ext_man.get("pack_id") or EXT_PACK_ID) if ext_ok else EXT_PACK_ID,
            "gates": ext_sc.get("gates") or {},
            "firms_hull_is_official_burned_area": hull_ext,
            "lwir": False,
            "vp_invented": vp_ext_inv,
            "scorecard_present": ext_sc_present,
            "municipio": ext_man.get("municipio") if ext_ok else None,
        }
    )

    return sites, skips


def _fmt_ha(v: float | None) -> str:
    if v is None:
        return "—"
    if v >= 100:
        return f"{v:.0f}"
    return f"{v:g}"


def _fmt_vp(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v:g}"


def _verdict_class(verdict: str) -> str:
    """Map verdict/decision strings to CSS pill class without GO⊂GOLD false positives."""
    u = (verdict or "").upper().strip()
    if not u or u in {"—", "-", "N/A"}:
        return "muted"
    # Fail / abstain first
    if "NO_GO" in u or re.search(r"\bNOGO\b", u):
        return "bad"
    if "PENDING" in u or "FAIL" in u or "ABSTAIN" in u:
        return "bad"
    if "PARTIAL" in u or "HOLD" in u:
        return "warn"
    # Explicit GO tokens (not GOLD)
    if u == "GO" or u.startswith("GO_") or u.startswith("GO "):
        return "ok"
    if re.search(r"(?:^|[^A-Z])GO(?:[^A-Z]|$)", u) and "GOLD" not in u:
        return "ok"
    # OPS grade language (no substring GO trap)
    if "GRADE A" in u or "OPS GOLD" in u:
        return "ok"
    return "muted"


def render_html(sites: list[dict[str, Any]], manifest: dict[str, Any]) -> str:
    """Deprecated: use demo_portal_html.render_portal via build()."""
    raise RuntimeError(
        "render_html is deprecated; regenerate with demo_portal_html.render_portal"
    )


def _write_guion_12min(sites: list[dict[str, Any]], path: Path) -> None:
    """Timed 12-min sales script (same steps as interactive portal)."""
    by_id = {s["id"]: s for s in sites}
    tb = by_id.get("tobarra") or {}
    nj = by_id.get("nijar") or {}
    cm = by_id.get("camino") or {}
    kn_tb = tb.get("key_numbers") or {}
    kn_nj = nj.get("key_numbers") or {}
    kn_cm = cm.get("key_numbers") or {}
    if tb.get("status_anchor") == "confirmed":
        tb_line = (
            f"ancla INFOCAM Vp ≈ {_fmt_vp(kn_tb.get('vp_m_min'))} m/min · "
            f"≈ {_fmt_ha(kn_tb.get('area_ha'))} ha confirmed"
        )
    else:
        tb_line = f"ancla status {tb.get('status_anchor') or 'SKIP'} (Vp no publicados)"
    lines = [
        "# Guion 12 min — demo multi-CCAA (Tobarra · Níjar · Caminomorisco)",
        "",
        "Misma secuencia que el portal interactivo (`#guion`).",
        "Claim: decision support multi-CCAA; HOLD es feature; no inventar Vp/ha.",
        "",
        "## 0:00 – 0:45 · Gancho",
        "Tres contratos de datos, un criterio de calidad. HOLD/ABSTAIN sin ancla.",
        "No tres mapas bonitos: OPS gold · O2 REDIAM · O2 RAI.",
        "",
        "## 1–4 min · Tobarra OPS",
        f"LWIR + {tb_line}.",
        f"Verdict: {tb.get('verdict')} · decisión: {tb.get('decision_open')}.",
        "ROS multi-estimador. Sin este material no inventamos el número.",
        "",
        "## 4–7 min · Níjar AND (REDIAM O2)",
        f"Perímetro oficial ~{_fmt_ha(kn_nj.get('area_ha'))} ha · "
        f"verdict {nj.get('verdict')} · decisión {nj.get('decision_open')}.",
        "FIRMS + dNBR cuando hay. Sin ancla ASEMA de Vp → no Vp táctico.",
        "",
        "## 7–10 min · Caminomorisco EXT (RAI O2)",
        f"Perímetro RAI ~{_fmt_ha(kn_cm.get('area_ha'))} ha · "
        f"det {kn_cm.get('fecha_det') or '—'} → ext {kn_cm.get('fecha_ext') or '—'}"
        + (
            f" · {kn_cm.get('duration_days')} días"
            if kn_cm.get("duration_days") is not None
            else ""
        )
        + ".",
        f"Verdict: {cm.get('verdict')}. PARTIAL si FIRMS SKIP — no hotspots inventados.",
        "",
        "## 10–12 min · Síntesis + ask",
        "Dual track + scoreboard + reliability (residual silent-GO).",
        "Ask: 30 min feedback · ancla Vp/ha (1 IF) · carta interés UE.",
        "Contacto: alonso.alvbal@gmail.com",
        "",
        "## No decir",
        "- Apagamos incendios con IA / 99% precisión / sustituimos INFOCA",
        "- Hull FIRMS = ha quemadas / inventamos Vp",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def copy_summaries(sites: list[dict[str, Any]]) -> dict[str, str]:
    """Copy lightweight JSON snapshots into OUT for offline reading."""
    OUT.mkdir(parents=True, exist_ok=True)
    copied: dict[str, str] = {}

    anchors = _load(ANCHORS_PATH) or {}
    tb = (anchors.get("anchors") or {}).get(TOBARRA_ANCHOR_KEY)
    if tb:
        p = OUT / "snapshot_tobarra.json"
        p.write_text(
            json.dumps(
                {
                    "id": "tobarra",
                    "anchor_key": TOBARRA_ANCHOR_KEY,
                    "anchor": tb,
                    "vp_invented": False,
                    "source_file": "data/infocam_anchors.json",
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        copied["tobarra"] = p.name

    for pack_root, pack_id_fallback, label, score_name in (
        (AND_PACK, AND_PACK_ID, "nijar", "scorecard_and_industrial.json"),
        (EXT_PACK, EXT_PACK_ID, "camino", "scorecard_ext_industrial.json"),
    ):
        # Use module pack roots so monkeypatched paths stay consistent with collect_sites
        pack = pack_root
        man = _load(pack / "manifest.json")
        sc = _load(pack / score_name)
        if not man and not sc:
            continue
        pack_id = (man or {}).get("pack_id") or pack_id_fallback
        snap = {
            "id": label,
            "pack_id": pack_id,
            "manifest": man,
            "scorecard": sc,
            "vp_invented": _flag_true((sc or {}).get("vp_invented")),
            "firms_hull_is_official_burned_area": _flag_true(
                (sc or {}).get("firms_hull_is_official_burned_area")
            ),
        }
        p = OUT / f"snapshot_{label}.json"
        p.write_text(json.dumps(snap, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        copied[label] = p.name

        if sc:
            shutil.copy2(pack / score_name, OUT / f"{label}_{score_name}")
            copied[f"{label}_scorecard"] = f"{label}_{score_name}"
        if man:
            shutil.copy2(pack / "manifest.json", OUT / f"{label}_manifest.json")
            copied[f"{label}_manifest"] = f"{label}_manifest.json"

    return copied


def _enrich_sites_with_metrics(sites: list[dict[str, Any]]) -> None:
    """Attach metrics_o2 from pack dirs when present."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("demo_kpi_board", ROOT / "scripts" / "demo_kpi_board.py")
    if spec is None or spec.loader is None:
        return
    kpi_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(kpi_mod)

    pack_map = {"nijar": AND_PACK, "camino": EXT_PACK}
    for s in sites:
        pack = pack_map.get(s.get("id") or "")
        if not pack:
            continue
        m = kpi_mod.load_metrics(pack)
        if m:
            s["metrics"] = m
            kn = s.setdefault("key_numbers", {})
            if kn.get("firms_n") is None and m.get("n_firms_hotspots") is not None:
                kn["firms_n"] = m.get("n_firms_hotspots")


def _simplified_perimeter_fc(path: Path, max_chars: int = 80000) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        fc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    try:
        from shapely.geometry import mapping, shape

        feats = []
        for f in fc.get("features") or []:
            g = shape(f.get("geometry"))
            gs = g.simplify(0.00035, preserve_topology=True)
            feats.append(
                {
                    "type": "Feature",
                    "properties": {
                        k: f.get("properties", {}).get(k)
                        for k in ("id_incen", "codigo", "municipio", "attribution")
                        if f.get("properties")
                    },
                    "geometry": mapping(gs),
                }
            )
        out = {"type": "FeatureCollection", "features": feats}
        raw = json.dumps(out, separators=(",", ":"))
        if len(raw) > max_chars:
            # coarser simplify
            feats2 = []
            for f in feats:
                g = shape(f["geometry"]).simplify(0.001, preserve_topology=True)
                feats2.append({**f, "geometry": mapping(g)})
            out = {"type": "FeatureCollection", "features": feats2}
        return out
    except Exception:
        return fc


def _collect_silver_ext() -> list[dict[str, Any]]:
    inv = ROOT / "data" / "open_if" / "extremadura_rai_2025" / "inventory" / "selection_gold.json"
    sel = _load(inv) or {}
    events = sel.get("events") or {}
    silver_ids = sel.get("silver") or []
    out = []
    for eid in silver_ids:
        ev = events.get(eid) or {}
        pack_candidates = list((ROOT / "outputs" / "open_if").glob(f"ext_{eid}_*"))
        pack = pack_candidates[0] if pack_candidates else None
        map_href = _rel(OUT, pack / "map.html") if pack and (pack / "map.html").is_file() else None
        out.append(
            {
                "id": eid,
                "name": ev.get("municipio") or eid,
                "area_ha": ev.get("area_geom_ha") or ev.get("hectareas_attr"),
                "map": map_href,
                "fecha_det": ev.get("fecha_det"),
            }
        )
    return out


def _tobarra_point_fc() -> dict[str, Any]:
    """Minimal geometry for Tobarra mini-map (centroid approx from known fire)."""
    # Approx Tobarra AB area center (Albacete province)
    lon, lat = -1.69, 38.59
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "Tobarra", "note": "OPS center proxy — not official perimeter"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [lon - 0.04, lat - 0.03],
                            [lon + 0.04, lat - 0.03],
                            [lon + 0.04, lat + 0.03],
                            [lon - 0.04, lat + 0.03],
                            [lon - 0.04, lat - 0.03],
                        ]
                    ],
                },
            }
        ],
    }


def _git_short() -> str | None:
    """Optional short hash; never fails the build."""
    import subprocess

    try:
        r = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()[:12]
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    return None


# Patchable for tests (soft-skip-all). kind: live | schema_sample
DECISION_CARD_CANDIDATES: list[tuple[str, Path, str, str]] = [
    ("gold_e2e", ROOT / "outputs" / "gold_e2e" / "fire_decision_card.json", "Tobarra gold E2E", "live"),
    (
        "forensic_demo",
        ROOT / "outputs" / "forensic_demo" / "fire_decision_card.json",
        "Forensic demo",
        "live",
    ),
    # Schema sample last — labeled SAMPLE in UI, not a third field GO
    (
        "docs_schema",
        ROOT / "docs" / "FIRE_DECISION_CARD.json",
        "Hub schema sample",
        "schema_sample",
    ),
]


def _load_decision_cards(skips: dict[str, Any]) -> list[dict[str, Any]]:
    """Load GO/HOLD/ABSTAIN cards from known gold/decide paths (soft SKIP if absent)."""
    cards: list[dict[str, Any]] = []
    found_any = False
    for cid, path, label, kind in DECISION_CARD_CANDIDATES:
        raw = _load(path)
        if not raw:
            skips[f"decision_card_{cid}"] = "SKIP"
            continue
        found_any = True
        skips[f"decision_card_{cid}"] = "OK"
        decision = raw.get("decision") or raw.get("posture") or "—"
        reasons = raw.get("reasons") or []
        if isinstance(reasons, list):
            reasons_s = [str(x) for x in reasons[:8]]
        else:
            reasons_s = [str(reasons)]
        disclaimers = list(raw.get("disclaimers") or [])[:6]
        if not any("tactical dispatch" in str(d).lower() for d in disclaimers):
            disclaimers = ["Not a tactical dispatch order."] + disclaimers
        cards.append(
            {
                "id": cid,
                "label": label,
                "kind": kind,
                "event_id": raw.get("event_id"),
                "decision": decision,
                "confidence_pred": raw.get("confidence_pred"),
                "confidence_pred_label": raw.get("confidence_pred_label"),
                "system_reliability_pass": raw.get("system_reliability_pass"),
                "reasons": reasons_s,
                "disclaimers": disclaimers[:6],
                "href": _rel(OUT, path),
                "status": "OK",
            }
        )
    if not found_any:
        skips["decision_cards"] = "SKIP_none_found"
        cards.append(
            {
                "id": "none",
                "label": "Decision Card",
                "kind": "none",
                "decision": "SKIP",
                "reasons": ["No fire_decision_card.json in gold_e2e / forensic_demo / docs"],
                "disclaimers": ["Not a tactical dispatch order."],
                "status": "SKIP",
                "href": None,
            }
        )
    else:
        skips["decision_cards"] = "OK"
    return cards


def _collect_la_mierla(skips: dict[str, Any]) -> dict[str, Any] | None:
    """Optional 4th open IF (HOLD live) — soft, does not dilute hero pitch."""
    pack = ROOT / "outputs" / "open_if" / "la_mierla_20260717"
    if not pack.is_dir():
        skips["la_mierla"] = "SKIP_missing_pack"
        return None
    man = _load(pack / "manifest.json") or {}
    card = (
        _load(pack / "fire_decision_card_field_ops.json")
        or _load(pack / "fire_decision_card_research.json")
        or {}
    )
    map_p = pack / "map.html"
    brief = pack / "operator_brief_open_if.md"
    decision = card.get("decision") or "HOLD"
    # Prefer pack fire-date fields / event_id; never hardcode plan date or use build UTC as IF date
    year_label = man.get("fecha") or man.get("fecha_inc") or man.get("date")
    if year_label:
        year_label = str(year_label)[:10]
    else:
        eid = str(man.get("event_id") or pack.name)
        m = re.search(r"(20\d{2})[_-]?(\d{2})[_-]?(\d{2})", eid)
        year_label = f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else "—"
    skips["la_mierla"] = "OK"
    return {
        "id": "la_mierla",
        "panel": "la_mierla",
        "name": "La Mierla",
        "name_display": "La Mierla",
        "ccaa": man.get("ccaa") or "Castilla-La Mancha",
        "ccaa_short": "CLM",
        "year_label": year_label,
        "track": "OPEN_LIVE",
        "track_label": "OPEN · HOLD live",
        "verdict": "OPEN HOLD live",
        "decision_open": decision,
        "optional": True,
        "headline": "Pack open FIRMS/CEMS partial · sin ancla OPS (HOLD)",
        "source": "FIRMS / open pack · no perímetro Junta confirmado",
        "attribution": "Open monitoring — no despacho táctico · HOLD sin ancla",
        "what_shows": "Postura HOLD en IF abierto en vivo (sin inventar Vp/ha)",
        "what_not": "No es el pitch principal de 3 sitios",
        "pack_id": man.get("event_id") or "la_mierla_20260717",
        "status_pack": man.get("status"),
        "blocked": man.get("blocked") or [],
        "links": {
            "map": _rel(OUT, map_p) if map_p.is_file() else None,
            "brief": _rel(OUT, brief) if brief.is_file() else None,
            "decision_card": _rel(OUT, pack / "fire_decision_card_field_ops.json")
            if (pack / "fire_decision_card_field_ops.json").is_file()
            else None,
        },
        "vp_invented": False,
        "lwir": False,
        "firms_hull_is_official_burned_area": False,
        "key_numbers": {"area_ha": None, "vp_m_min": None, "vp_invented": False},
    }


def _provenance_panel() -> dict[str, Any]:
    """Stronger provenance contacts for sales honesty."""
    return {
        "sources": [
            {
                "id": "infocam",
                "label": "INFOCAM anclas",
                "contact": "data/infocam_anchors.json (status confirmed only)",
                "role": "Vp/ha OPS gold Tobarra",
            },
            {
                "id": "rediam",
                "label": "REDIAM — Junta de Andalucía",
                "contact": "rediam.atiende.csma@juntadeandalucia.es",
                "role": "Perímetros O2 AND · catálogo multi-IF",
            },
            {
                "id": "asema",
                "label": "ASEMA (ancla Vp AND)",
                "contact": "gerencia.asema@juntadeandalucia.es",
                "role": "Solicitud ancla 1 IF (pipeline O1)",
            },
            {
                "id": "rai",
                "label": "RAI / INFOEX — Junta de Extremadura",
                "contact": "rai@juntaex.es",
                "role": "Perímetros O2 EXT + fechas det/ext",
            },
            {
                "id": "lwir",
                "label": "Heligrafics / CMA (LWIR)",
                "contact": "material entrega CMA (figs ROS/área)",
                "role": "Secuencia térmica Tobarra OPS",
            },
        ],
        "product_contact": "alonso.alvbal@gmail.com",
        "note": "Atribuciones visibles en cards y actas E2E; no se inventan Vp/ha.",
    }


def build() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "data").mkdir(exist_ok=True)
    (OUT / "export").mkdir(exist_ok=True)

    sites, skips = collect_sites()
    _enrich_sites_with_metrics(sites)
    # duration_days Camino when fechas present
    for s in sites:
        if s.get("id") == "camino":
            kn = s.setdefault("key_numbers", {})
            fd, fe = kn.get("fecha_det"), kn.get("fecha_ext")
            if fd and fe:
                try:
                    from datetime import datetime as _dt

                    d0 = _dt.strptime(str(fd)[:10], "%Y-%m-%d").date()
                    d1 = _dt.strptime(str(fe)[:10], "%Y-%m-%d").date()
                    kn["duration_days"] = max(0, (d1 - d0).days)
                except ValueError:
                    kn["duration_days"] = None

    snapshots = copy_summaries(sites)
    silver = _collect_silver_ext()
    decision_cards = _load_decision_cards(skips)
    la_mierla = _collect_la_mierla(skips)
    provenance = _provenance_panel()
    git_short = _git_short()

    import importlib.util

    spec = importlib.util.spec_from_file_location("demo_kpi_board", ROOT / "scripts" / "demo_kpi_board.py")
    assert spec and spec.loader
    kpi_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(kpi_mod)
    kpi = kpi_mod.compute_kpi_board(sites, root=ROOT, skips=skips)
    compare = kpi_mod.compute_compare_matrix(sites)
    scoreboard = kpi_mod.scoreboard_rows(sites)
    ha_svg = kpi_mod.svg_ha_bars(sites)

    spec_c = importlib.util.spec_from_file_location("demo_charts", ROOT / "scripts" / "demo_charts.py")
    assert spec_c and spec_c.loader
    charts_mod = importlib.util.module_from_spec(spec_c)
    spec_c.loader.exec_module(charts_mod)
    charts = charts_mod.svg_ha_and_gates_bundle(sites, ha_svg)

    perims: dict[str, Any] = {
        "nijar": _simplified_perimeter_fc(AND_PACK / "vectors" / "perimeter_rediam.geojson"),
        "camino": _simplified_perimeter_fc(EXT_PACK / "vectors" / "perimeter_rai.geojson"),
        "tobarra": _tobarra_point_fc(),
    }
    # drop Nones for JSON cleanliness
    perims = {k: v for k, v in perims.items() if v}

    any_vp_invented = any(s.get("vp_invented") is True for s in sites)
    any_hull_as_burned = any(s.get("firms_hull_is_official_burned_area") is True for s in sites)

    plan_href = _rel(OUT, PLAN_DOC)
    demo_version = "2.1.0"
    manifest: dict[str, Any] = {
        "schema": "demo_multi_ccaa_v3",
        "demo_version": demo_version,
        "git_short": git_short,
        "title": "Demo multi-CCAA — Tobarra · Níjar · Caminomorisco",
        "built_at_utc": datetime.now(UTC).isoformat(),
        "plan": "docs/design/DEMO_MULTI_CCAA_TOBARRA_NIJAR_CAMINOMORISCO.md",
        "plan_href": plan_href,
        "portal": "outputs/demo_multi_ccaa/index.html",
        "sites": sites,
        "skips": skips,
        "snapshots": snapshots,
        "silver_packs": silver,
        "decision_cards": decision_cards,
        "la_mierla": la_mierla,
        "provenance": provenance,
        "charts": {
            "gate_counts": charts.get("gate_counts"),
            "duration_days_camino": charts.get("duration_days_camino"),
        },
        "kpi_board": "data/kpi_board.json",
        "compare_matrix": "data/compare_matrix.json",
        "scoreboard": "data/scoreboard.json",
        "exports": {
            "pitch_md": "export/pitch_onepager.md",
            "pitch_html": "export/pitch_onepager.html",
            "guion": "export/guion_12min.md",
        },
        "honesty": {
            "any_vp_invented": any_vp_invented,
            "vp_invented": any_vp_invented,
            "firms_hull_is_official_burned_area": any_hull_as_burned,
            "no_tactical_dispatch": True,
            "hold_without_ops_anchor": True,
            "policy_never_invent_vp": True,
            "residual_silent_go_story": True,
        },
        "deep_links": {
            "tobarra": "?panel=tobarra",
            "nijar": "?panel=nijar",
            "camino": "?panel=camino",
            "pitch": "?mode=pitch",
            "guion": "?mode=guion",
            "decision": "?panel=decision",
        },
        "how_to_open": [
            "python scripts/build_demo_multi_ccaa.py",
            "start outputs/demo_multi_ccaa/index.html",
            "make demo-multi-ccaa",
            ".\\scripts\\open_demo_multi_ccaa.ps1",
        ],
        "sell_ctas": [
            "feedback_30min",
            "request_anchor",
            "eu_interest_letter",
        ],
        "commander_href": "../../docs/commander/index.html",
        "portal_href": "../../docs/PORTAL.html",
    }

    (OUT / "data" / "kpi_board.json").write_text(
        json.dumps(kpi, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (OUT / "data" / "compare_matrix.json").write_text(
        json.dumps(compare, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (OUT / "data" / "scoreboard.json").write_text(
        json.dumps(scoreboard, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (OUT / "data" / "decision_cards.json").write_text(
        json.dumps(decision_cards, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (OUT / "data" / "charts_meta.json").write_text(
        json.dumps(
            {
                "gate_counts": charts.get("gate_counts"),
                "duration_days_camino": charts.get("duration_days_camino"),
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    # Pitch export (HTML + MD)
    spec_p = importlib.util.spec_from_file_location(
        "demo_export_pitch", ROOT / "scripts" / "demo_export_pitch.py"
    )
    assert spec_p and spec_p.loader
    pitch_mod = importlib.util.module_from_spec(spec_p)
    spec_p.loader.exec_module(pitch_mod)
    pitch_mod.write_pitch_exports(
        OUT,
        sites=sites,
        kpi=kpi,
        manifest=manifest,
        version=demo_version,
        git_hash=git_short,
    )

    _write_guion_12min(sites, OUT / "export" / "guion_12min.md")

    spec_h = importlib.util.spec_from_file_location(
        "demo_portal_html", ROOT / "scripts" / "demo_portal_html.py"
    )
    assert spec_h and spec_h.loader
    html_mod = importlib.util.module_from_spec(spec_h)
    spec_h.loader.exec_module(html_mod)
    html = html_mod.render_portal(
        sites=sites,
        manifest=manifest,
        kpi=kpi,
        compare=compare,
        scoreboard=scoreboard,
        ha_chart_svg=ha_svg,
        perimeter_js=perims,
        version=demo_version,
        gates_chart_svg=str(charts.get("gates") or ""),
        timeline_chart_svg=str(charts.get("timeline_camino") or ""),
        decision_cards=decision_cards,
        la_mierla=la_mierla,
        git_short=git_short,
    )
    (OUT / "index.html").write_text(html, encoding="utf-8")
    (OUT / "demo_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    man = build()
    sites = man.get("sites") or []
    print(f"[demo-multi-ccaa] wrote {OUT / 'index.html'}")
    print(f"[demo-multi-ccaa] wrote {OUT / 'demo_manifest.json'}")
    print(f"[demo-multi-ccaa] sites: {len(sites)}")
    for s in sites:
        kn = s.get("key_numbers") or {}
        print(
            f"  - {s.get('name_display')}: verdict={s.get('verdict')} "
            f"ha={kn.get('area_ha')} vp={kn.get('vp_m_min')} "
            f"vp_invented={s.get('vp_invented')}"
        )
    skips = {k: v for k, v in (man.get("skips") or {}).items() if str(v).startswith("SKIP")}
    if skips:
        print(f"[demo-multi-ccaa] soft skips: {skips}")
    honesty = man.get("honesty") or {}
    if honesty.get("any_vp_invented") or honesty.get("vp_invented"):
        print(
            "[demo-multi-ccaa] WARNING: any_vp_invented=true — portal written with integrity banner",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
