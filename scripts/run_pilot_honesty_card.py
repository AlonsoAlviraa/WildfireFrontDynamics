#!/usr/bin/env python3
"""P1 Pilot: multi-pack honesty Decision Cards (Tobarra OPS + Níjar AND + Caminomorisco EXT).

Offline CI path (no weights, no outputs/ packs)::

  python scripts/run_pilot_honesty_card.py --fixture-root tests/fixtures/pilot

Honesty (non-negotiable)
------------------------
* Dual product: Ops ≠ ML; fuse only at Decision Card.
* No invented tactical ROS/Vp from open packs or FIRMS hulls.
* Catalog holdout IoU 0.8963 is provenance only — not live certainty.
* field_ops.allow_ml_live_in_fusion stays false; no fake R1–R4 for GO.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import warnings
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_PRODUCT = "clm_ensemble_v34"
DEFAULT_POLICY = "research_open"
DEFAULT_OUT = PROJECT_ROOT / "outputs" / "pilot_honesty_card"
DOCS_REPORT = PROJECT_ROOT / "docs" / "PILOT_HONESTY_CARD.md"
FIXTURE_ROOT_DEFAULT = PROJECT_ROOT / "tests" / "fixtures" / "pilot"

# Production catalog (§3.3) — used when no fixture-root pilot_sites.json
BUILTIN_PRODUCTION_CATALOG: dict[str, Any] = {
    "schema": "pilot_sites_catalog_v1",
    "sites": [
        {
            "site_id": "tobarra",
            "display_name": "Tobarra",
            "track": "OPS",
            "event_id": "pilot_tobarra_20240802",
            "work_dir": "outputs/temporal_windows/tobarra_20240802/mid",
            "open_pack": None,
            "anchor_key": "tobarra_20240802",
            "anchors_path": "data/infocam_anchors.json",
            "ml_scenario": "hold",
            "ml_prediction": None,
        },
        {
            "site_id": "nijar",
            "display_name": "Níjar",
            "track": "OPEN_AND",
            "event_id": "pilot_nijar_and_2024040053",
            "work_dir": None,
            "open_pack": "outputs/open_if/and_2024040053_20240606",
            "anchor_key": None,
            "anchors_path": None,
            "ml_scenario": "hold",
            "ml_prediction": None,
        },
        {
            "site_id": "caminomorisco",
            "display_name": "Caminomorisco",
            "track": "OPEN_EXT",
            "event_id": "pilot_camino_ext_2025100393",
            "work_dir": None,
            "open_pack": "outputs/open_if/ext_2025100393_20250729",
            "anchor_key": None,
            "anchors_path": None,
            "ml_scenario": "abstain",
            "ml_prediction": None,
        },
    ],
}

OPEN_METRICS_KEYS = frozenset(
    {
        "max_area_ha",
        "n_timeline_steps",
        "activation",
        "O2_cems_delineation",
        "pack_id",
        "source_scorecard",
        "track",
        "decision_open",
        "verdict",
        "vp_invented",
        "firms_hull_is_official_burned_area",
        "attribution",
        "area_source",
    }
)
OPS_METRICS_KEYS = frozenset(
    {
        "quality_grade",
        "primary_ros_m_min",
        "n_frames_staged",
        "area_ha_max",
        "speed_vs_ref_ratio",
        "engine",
        "window",
        "fire_id",
        "anchor_vp_m_min",
        "anchor_area_ha",
        "anchor_status",
        "anchor_source",
        "ros_source",
    }
)
ML_LIVE_KEYS = frozenset(
    {
        "schema",
        "product_id",
        "confidence",
        "abstain",
        "mean_entropy",
        "member_disagreement",
        "mean_margin",
        "calibrator_id",
        "n_members",
    }
)

REPORT_MAX_NONEMPTY_LINES = 90
REPORT_MAX_WORDS = 1200


def _load_demo_mod():
    script = PROJECT_ROOT / "scripts" / "run_ml_live_card_demo.py"
    spec = importlib.util.spec_from_file_location("run_ml_live_card_demo", script)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {script}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _rel_posix(path: Path, base: Path = PROJECT_ROOT) -> str:
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def load_catalog(
    *,
    sites_config: Path | None,
    fixture_root: Path | None,
) -> tuple[dict[str, Any], str]:
    """Catalog load total function (§3.3.1). Returns (catalog, source_label)."""
    if sites_config is not None:
        path = Path(sites_config)
        if not path.is_file():
            raise FileNotFoundError(f"--sites-config not found: {path}")
        data = _load_json(path)
        if data is None or not isinstance(data.get("sites"), list):
            raise ValueError(f"invalid sites catalog: {path}")
        return data, f"sites_config:{path.as_posix()}"

    if fixture_root is not None:
        auto = Path(fixture_root) / "pilot_sites.json"
        if auto.is_file():
            data = _load_json(auto)
            if data is None or not isinstance(data.get("sites"), list):
                raise ValueError(f"invalid sites catalog: {auto}")
            return data, f"fixture_root:{auto.as_posix()}"
        warnings.warn(
            "fixture_root_without_pilot_sites_json",
            UserWarning,
            stacklevel=2,
        )

    return dict(BUILTIN_PRODUCTION_CATALOG), "builtin_production"


def resolve_path_base(
    *,
    fixture_root: Path | None,
    catalog: dict[str, Any],
    sites_config: Path | None,
    catalog_source: str,
) -> Path:
    """Path base total function (§3.3.1)."""
    if fixture_root is not None:
        return Path(fixture_root)
    cat_base = catalog.get("base")
    if isinstance(cat_base, str) and cat_base.strip():
        p = Path(cat_base)
        return p if p.is_absolute() else (PROJECT_ROOT / p)
    if sites_config is not None and catalog_source.startswith("sites_config:"):
        return Path(sites_config).parent
    return PROJECT_ROOT


def resolve_site_path(value: Any, base: Path) -> Path | None:
    if value is None or value == "":
        return None
    p = Path(str(value))
    if p.is_absolute():
        return p
    return base / p


def allowlist_open(metrics: dict[str, Any] | None) -> dict[str, Any] | None:
    if not metrics:
        return None
    return {k: metrics[k] for k in OPEN_METRICS_KEYS if k in metrics}


def allowlist_ops(metrics: dict[str, Any] | None) -> dict[str, Any] | None:
    if not metrics:
        return None
    return {k: metrics[k] for k in OPS_METRICS_KEYS if k in metrics}


def allowlist_ml_live(metrics: dict[str, Any] | None) -> dict[str, Any] | None:
    if not metrics:
        return None
    return {k: metrics[k] for k in ML_LIVE_KEYS if k in metrics}


def _source_by_id(card: dict[str, Any], *ids: str) -> dict[str, Any] | None:
    for s in card.get("sources") or []:
        if isinstance(s, dict) and s.get("id") in ids:
            return s
    return None


def _card_fail_closed_reason(card: dict[str, Any]) -> str:
    reasons = card.get("reasons") or []
    return (
        " ".join(str(r) for r in reasons)
        if isinstance(reasons, list)
        else str(reasons)
    )


def build_facts_row(
    site: dict[str, Any],
    summary: dict[str, Any],
    open_m: dict[str, Any] | None,
    ops_m: dict[str, Any] | None,
) -> dict[str, Any]:
    sources_bits: list[str] = []
    resolved = summary.get("sources_resolved") or {}
    if resolved.get("ops"):
        sources_bits.append("ops")
    if resolved.get("open"):
        sources_bits.append("open")
    if resolved.get("ml_live"):
        sources_bits.append("ml_live")
    sources_s = "+".join(sources_bits) if sources_bits else "none"

    key_label = "—"
    key_value: Any = None
    key_source = "—"
    pack_verdict = None
    if ops_m and ops_m.get("primary_ros_m_min") is not None:
        key_label = "primary_ros_m_min"
        key_value = ops_m.get("primary_ros_m_min")
        key_source = str(ops_m.get("ros_source") or "ops")
    elif open_m and open_m.get("max_area_ha") is not None:
        key_label = "area_ha"
        key_value = open_m.get("max_area_ha")
        key_source = str(open_m.get("area_source") or "open")
        pack_verdict = open_m.get("verdict")

    contrast = summary.get("contrast_field_ops") or {}
    honesty = summary.get("honesty_flags") or {}
    note_parts = []
    if honesty.get("vp_invented"):
        note_parts.append("vp_invented")
    else:
        note_parts.append("Sin Vp táctica")
    if open_m and open_m.get("decision_open"):
        note_parts.append(f"open {open_m.get('decision_open')}")
    if honesty.get("sources_incomplete"):
        note_parts.append("fuentes_incompletas")

    return {
        "site_id": site.get("site_id"),
        "display_name": site.get("display_name"),
        "track": site.get("track"),
        "sources": sources_s,
        "decision_research_open": summary.get("decision"),
        "confidence_pred": summary.get("confidence_pred"),
        "live_ok": summary.get("live_ok"),
        "live_available": summary.get("live_available"),
        "live_abstained": summary.get("live_abstained"),
        "allow_ml_live_in_fusion": summary.get("allow_ml_live_in_fusion"),
        "decision_field_ops": contrast.get("decision"),
        "key_number_label": key_label,
        "key_number_value": key_value,
        "key_number_source": key_source,
        "pack_verdict": pack_verdict,
        "honesty_note": "; ".join(note_parts),
    }


def _fmt_bool_es(v: Any) -> str:
    if v is True:
        return "sí"
    if v is False:
        return "no"
    return "—"


def _key_number_label_es(label: Any) -> str:
    """Human Spanish label for key-number machine keys; keep raw in fuente chips."""
    raw = str(label or "").strip()
    if not raw or raw == "—":
        return "—"
    mapping = {
        "primary_ros_m_min": "ROS primario (m/min)",
        "area_ha": "área (ha)",
        "max_area_ha": "área (ha)",
    }
    return mapping.get(raw, raw)


def render_report(
    facts: dict[str, Any],
    site_summaries: list[dict[str, Any]],
    u1: dict[str, Any],
    *,
    generated_at: str,
    pilot_manifest: dict[str, Any] | None = None,
) -> str:
    """MD determinista en español. Sin reloj. Cifras solo de facts/summaries/u1."""
    rows = list(facts.get("rows") or [])
    site_names = [str(r.get("display_name") or r.get("site_id") or "") for r in rows]
    site_names_joined = " · ".join(n for n in site_names if n)
    policy = (pilot_manifest or {}).get("policy_id") or DEFAULT_POLICY
    product_id = (pilot_manifest or {}).get("product_id") or DEFAULT_PRODUCT
    u1_source = str(u1.get("u1_source") or "fallback")
    mean_iou = u1.get("mean_iou_eval")
    sel80 = u1.get("selective_iou_at_80")
    ece = u1.get("ece_patch_conf")
    catalog_iou = u1.get("catalog_holdout_iou_provenance")

    def _fmt(v: Any, nd: int = 3) -> str:
        if v is None:
            return "—"
        try:
            return f"{float(v):.{nd}f}"
        except (TypeError, ValueError):
            return str(v)

    lines: list[str] = [
        "# Piloto de honestidad — tarjeta de decisión multi-fuente",
        site_names_joined,
        (
            f"Generado: {generated_at} · política: {policy} · "
            f"producto: {product_id}"
        ),
        "",
        "## 0. Banner de honestidad (producto dual)",
        "- Ops (front_dynamics_v1) ≠ ML (máscara + fiabilidad de parche)",
        "- Fusión solo en tarjeta de decisión; field_ops fusión live = OFF",
        "- No es orden táctica de despacho",
        (
            f"- U1 TEST honest ({u1_source}): IoU eval ≈ {_fmt(mean_iou)} · "
            f"sel@80 ≈ {_fmt(sel80)} · ECE ≈ {_fmt(ece)}"
        ),
        (
            f"- Catalog holdout {_fmt(catalog_iou, 4)} = provenance only "
            "(no es certeza en vivo)"
        ),
        "",
        "## 1. Tabla de hechos",
        (
            "| Sitio | Pista | Fuentes | Decisión (research_open) | confianza | "
            "ML live | Decisión (field_ops) | Cifra clave | Notas |"
        ),
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]

    for r in rows:
        kn = r.get("key_number_label")
        kv = r.get("key_number_value")
        kn_es = _key_number_label_es(kn)
        key_cell = f"{kn_es}={_fmt(kv, 3)}" if kn and kn != "—" else "—"
        lines.append(
            f"| {r.get('display_name')} | {r.get('track')} | {r.get('sources')} | "
            f"{r.get('decision_research_open')} | {_fmt(r.get('confidence_pred'))} | "
            f"{_fmt_bool_es(r.get('live_ok'))} | {r.get('decision_field_ops')} | "
            f"{key_cell} | {r.get('honesty_note')} |"
        )

    lines.extend(["", "## 2. Lectura por incendio"])
    by_id = {s.get("site_id"): s for s in site_summaries if isinstance(s, dict)}
    for r in rows:
        sid = r.get("site_id")
        summ = by_id.get(sid) or {}
        contrast = summ.get("contrast_field_ops") or {}
        honesty = summ.get("honesty_flags") or {}
        conf_v = (
            summ.get("confidence_pred")
            if summ.get("confidence_pred") is not None
            else r.get("confidence_pred")
        )
        live_v = (
            summ.get("live_ok") if summ.get("live_ok") is not None else r.get("live_ok")
        )
        kn = r.get("key_number_label")
        kn_es = _key_number_label_es(kn)
        lines.append(f"### {r.get('display_name')} ({r.get('track')})")
        lines.append(
            f"- Cifra clave: {kn_es} = "
            f"{_fmt(r.get('key_number_value'), 4)} "
            f"(fuente: {r.get('key_number_source')}; clave: {kn})"
        )
        lines.append(
            f"- Tarjeta research_open: "
            f"{summ.get('decision') or r.get('decision_research_open')} "
            f"· confianza={_fmt(conf_v)} · ML live={_fmt_bool_es(live_v)}"
        )
        lines.append(
            f"- Contraste field_ops: "
            f"{contrast.get('decision') or r.get('decision_field_ops')} "
            "(sin R1–R4 inventados; fusión OFF)"
        )
        lines.append(
            f"- Honestidad: Vp inventada={_fmt_bool_es(honesty.get('vp_invented', False))}; "
            f"casco FIRMS≠quemado; "
            f"fuentes incompletas="
            f"{_fmt_bool_es(honesty.get('sources_incomplete', False))}"
        )
        lines.append("")

    lines.extend(
        [
            "## 3. Contraste de políticas",
            (
                "- research_open: laboratorio / amigable con open (HOLD); "
                "fusión live experimental"
            ),
            (
                "- field_ops: require_ops_for_go; fusión live OFF; ABSTAIN fail-closed "
                "(cierre seguro) si GO sin fiabilidad verificada "
                "(reason field_ops_fail_closed_reliability_unverified) — "
                "el piloto no inventa gates"
            ),
            "",
            "## 4. Límites y no-claims",
            "- No es multi-CCAA «funciona en toda España»",
            "- Casco FIRMS ≠ área quemada oficial",
            "- Sin reentrenamiento en este piloto",
            "- ml_product_go sigue en false hasta gates de producto",
            "",
            "## 5. Modo presentación (1 página)",
            (
                "- Tres sitios · un criterio: GO / HOLD / ABSTAIN con audit trail"
            ),
            (
                "- research_open puede ir a GO experimental; field_ops se calla "
                "(ABSTAIN/HOLD) — fusión OFF"
            ),
            (
                "- Cifras solo de OPS (ROS) u open (ha); sin Vp táctica inventada"
            ),
            (
                f"- Holdout catálogo {_fmt(catalog_iou, 4)} = provenance only, "
                "no certeza del incendio"
            ),
            "",
            "## 6. Artefactos",
        ]
    )
    art_root = (pilot_manifest or {}).get("out_dir") or "outputs/pilot_honesty_card"
    lines.append(f"- Raíz piloto: `{art_root}`")
    lines.append(
        "- Por sitio: `decision_card.json`, `decision_card_field_ops.json`, "
        "`site_summary.json`"
    )
    lines.append(
        "- `facts_table.json` · `pilot_summary.json` · `index.html` · este informe"
    )
    lines.append("")

    body = "\n".join(lines)
    nonempty = [ln for ln in body.splitlines() if ln.strip()]
    words = body.split()
    if len(nonempty) > REPORT_MAX_NONEMPTY_LINES:
        raise ValueError(
            f"report budget exceeded: nonempty_lines={len(nonempty)} > "
            f"{REPORT_MAX_NONEMPTY_LINES}"
        )
    if len(words) > REPORT_MAX_WORDS:
        raise ValueError(
            f"report budget exceeded: words={len(words)} > {REPORT_MAX_WORDS}"
        )
    return body


def _decision_pill_class(decision: Any) -> str:
    u = str(decision or "").upper().strip()
    if u == "GO" or u.startswith("GO_") or u.startswith("GO "):
        return "go"
    if u == "HOLD" or "HOLD" in u:
        return "hold"
    if u == "ABSTAIN" or "ABSTAIN" in u:
        return "abstain"
    return "muted"


def _html_esc(s: Any) -> str:
    import html as html_lib

    if s is None:
        return ""
    return html_lib.escape(str(s), quote=True)


def _fmt_num(v: Any, nd: int = 3) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):.{nd}f}"
    except (TypeError, ValueError):
        return str(v)


def render_pilot_portal_html(
    facts: dict[str, Any],
    site_summaries: list[dict[str, Any]],
    u1: dict[str, Any],
    *,
    generated_at: str,
    pilot_manifest: dict[str, Any] | None = None,
    pilot_summary: dict[str, Any] | None = None,
) -> str:
    """Portal HTML español, scannable, sin solapes; listo para presentación."""
    rows = list(facts.get("rows") or [])
    by_id = {s.get("site_id"): s for s in site_summaries if isinstance(s, dict)}
    policy = (pilot_manifest or {}).get("policy_id") or DEFAULT_POLICY
    product_id = (pilot_manifest or {}).get("product_id") or DEFAULT_PRODUCT
    u1_source = str(u1.get("u1_source") or "fallback")
    catalog_iou = u1.get("catalog_holdout_iou_provenance")
    mean_iou = u1.get("mean_iou_eval")
    sel80 = u1.get("selective_iou_at_80")
    ece = u1.get("ece_patch_conf")
    n_ok = (pilot_summary or {}).get("n_ok")
    n_sites = (pilot_summary or {}).get("n_sites") or len(rows)
    if n_ok is None:
        n_ok = sum(
            1
            for s in site_summaries
            if isinstance(s, dict) and not s.get("skipped") and not s.get("failed")
        )

    track_label = {
        "OPS": "OPS · térmico",
        "OPEN_AND": "OPEN · AND",
        "OPEN_EXT": "OPEN · EXT",
    }

    site_cards: list[str] = []
    for r in rows:
        sid = r.get("site_id")
        summ = by_id.get(sid) or {}
        contrast = summ.get("contrast_field_ops") or {}
        honesty = summ.get("honesty_flags") or {}
        dec_ro = summ.get("decision") or r.get("decision_research_open") or "—"
        dec_fo = contrast.get("decision") or r.get("decision_field_ops") or "—"
        conf = (
            summ.get("confidence_pred")
            if summ.get("confidence_pred") is not None
            else r.get("confidence_pred")
        )
        live_ok = (
            summ.get("live_ok") if summ.get("live_ok") is not None else r.get("live_ok")
        )
        kn = r.get("key_number_label") or "—"
        kn_es = _key_number_label_es(kn)
        kv = r.get("key_number_value")
        ks = r.get("key_number_source") or "—"
        track = str(r.get("track") or "")
        tlab = track_label.get(track, track)
        track_cls = "ops" if track == "OPS" else "open"
        # Single "se calla" badge next to field_ops pill (no duplicate in chips)
        se_calla_badge = (
            '<span class="chip silence" title="field_ops se calla">se calla</span>'
            if str(dec_fo).upper() == "ABSTAIN"
            else ""
        )
        incomplete = bool(honesty.get("sources_incomplete"))
        site_cards.append(
            f"""
<article class="site-card" id="site-{_html_esc(sid)}">
  <header class="card-head">
    <div class="card-title">
      <span class="track track-{track_cls}">{_html_esc(tlab)}</span>
      <h2>{_html_esc(r.get("display_name") or sid)}</h2>
      <p class="meta-line">{_html_esc(r.get("sources") or "—")}</p>
    </div>
    <div class="pills">
      <div class="pill-stack">
        <span class="pill-lbl">research_open</span>
        <span class="pill {_decision_pill_class(dec_ro)}">{_html_esc(dec_ro)}</span>
      </div>
      <div class="pill-stack">
        <span class="pill-lbl">field_ops</span>
        <span class="pill {_decision_pill_class(dec_fo)}">{_html_esc(dec_fo)}</span>
        {se_calla_badge}
      </div>
    </div>
  </header>
  <div class="metrics">
    <div class="metric">
      <span class="m-val">{_html_esc(_fmt_num(conf, 3))}</span>
      <span class="m-lbl">confianza</span>
    </div>
    <div class="metric">
      <span class="m-val">{_html_esc(_fmt_num(kv, 3) if kn != "—" else "—")}</span>
      <span class="m-lbl">{_html_esc(kn_es)}</span>
    </div>
    <div class="metric">
      <span class="m-val m-small">{_html_esc(_fmt_bool_es(live_ok))}</span>
      <span class="m-lbl">ML live</span>
    </div>
  </div>
  <div class="chips">
    <span class="chip">fuente · {_html_esc(ks)}</span>
    <span class="chip">clave · {_html_esc(kn)}</span>
    <span class="chip {"warn" if incomplete else "ok"}">
      {"fuentes incompletas" if incomplete else "fuentes OK"}
    </span>
    <span class="chip">Sin Vp táctica</span>
  </div>
</article>"""
        )

    contrast_cells: list[str] = []
    for r in rows:
        sid = r.get("site_id")
        summ = by_id.get(sid) or {}
        contrast = summ.get("contrast_field_ops") or {}
        dec_ro = summ.get("decision") or r.get("decision_research_open") or "—"
        dec_fo = contrast.get("decision") or r.get("decision_field_ops") or "—"
        contrast_cells.append(
            f"""
<div class="contrast-cell">
  <div class="contrast-name">{_html_esc(r.get("display_name") or sid)}</div>
  <div class="contrast-pair">
    <span class="pill {_decision_pill_class(dec_ro)}" title="research_open">{_html_esc(dec_ro)}</span>
    <span class="arrow" aria-hidden="true">→</span>
    <span class="pill {_decision_pill_class(dec_fo)}" title="field_ops">{_html_esc(dec_fo)}</span>
  </div>
</div>"""
        )

    sites_joined = " · ".join(
        str(r.get("display_name") or r.get("site_id") or "") for r in rows
    )

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>WFD · Piloto de honestidad — Tobarra · Níjar · Caminomorisco</title>
<meta name="description" content="Tarjetas de decisión multi-fuente con honestidad (producto dual). GO/HOLD/ABSTAIN. field_ops fusión OFF."/>
<style>
:root {{
  --bg:#070b12; --card:#111925; --card-hi:#152032; --line:rgba(100,140,190,.22);
  --text:#e8eef8; --muted:#8b9bb4; --accent:#3b9eff; --cyan:#2fd4c8; --ops:#f0a030;
  --go:#1ecf8c; --hold:#f0b429; --abstain:#ff5c6c; --radius:14px;
  --font:"Segoe UI",system-ui,-apple-system,sans-serif;
  --shadow:0 8px 28px rgba(0,0,0,.28);
}}
*{{box-sizing:border-box}}
html{{scroll-behavior:smooth}}
body{{margin:0;font-family:var(--font);background:var(--bg);color:var(--text);
  line-height:1.45;min-height:100vh;-webkit-font-smoothing:antialiased}}
.bg-fx{{position:fixed;inset:0;z-index:0;pointer-events:none;background:
  radial-gradient(ellipse 70% 45% at 12% -8%,rgba(45,100,180,.28),transparent 55%),
  radial-gradient(ellipse 50% 35% at 92% 12%,rgba(200,80,40,.12),transparent 50%),
  linear-gradient(180deg,#080d16,#070b12)}}
.wrap{{position:relative;z-index:1;max-width:1100px;margin:0 auto;padding:0 1.1rem 2.5rem}}
.topnav{{position:sticky;top:0;z-index:40;backdrop-filter:blur(14px);
  background:rgba(7,11,18,.9);display:flex;align-items:center;justify-content:space-between;
  gap:.75rem;flex-wrap:wrap;padding:.7rem 0;border-bottom:1px solid var(--line);margin-bottom:.85rem}}
.brand{{display:flex;align-items:center;gap:.6rem;min-width:0}}
.brand-mark{{flex:0 0 auto;width:32px;height:32px;border-radius:10px;
  background:conic-gradient(from 200deg,var(--cyan),var(--accent),var(--ops),var(--cyan))}}
.brand h1{{margin:0;font-size:.88rem;letter-spacing:.06em;font-weight:800}}
.brand .sub{{color:var(--muted);font-size:.7rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:48vw}}
.nav-links{{display:flex;gap:.28rem;flex-wrap:wrap}}
.nav-links a{{font-size:.7rem;font-weight:650;padding:.28rem .5rem;border-radius:999px;
  border:1px solid var(--line);color:var(--muted);text-decoration:none}}
.nav-links a:hover{{color:var(--text);border-color:rgba(59,158,255,.45)}}
.hero{{padding:.6rem 0 .4rem}}
.eyebrow{{color:var(--cyan);font-size:.72rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase}}
.hero h2{{margin:.35rem 0 .55rem;font-size:clamp(1.2rem,2.6vw,1.65rem);font-weight:750;
  max-width:40rem;letter-spacing:-.02em}}
.hero p{{margin:0;color:var(--muted);max-width:42rem;font-size:.92rem}}
.hero p b{{color:var(--text)}}
.kpi-strip{{display:grid;grid-template-columns:repeat(4,1fr);gap:.6rem;margin:1rem 0 1.1rem}}
@media(max-width:900px){{.kpi-strip{{grid-template-columns:repeat(2,1fr)}}}}
@media(max-width:480px){{.kpi-strip{{grid-template-columns:1fr}}}}
.kpi{{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);
  padding:.7rem .85rem;min-width:0}}
.kpi-val{{font-size:1.25rem;font-weight:800;font-variant-numeric:tabular-nums;letter-spacing:-.02em;
  overflow-wrap:anywhere}}
.kpi-lbl{{font-size:.7rem;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;margin-top:.12rem}}
.cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:.9rem;margin:.4rem 0 1rem;
  align-items:stretch}}
@media(max-width:960px){{.cards{{grid-template-columns:1fr}}}}
.site-card{{background:var(--card);border:1px solid var(--line);border-radius:16px;
  padding:1rem;display:flex;flex-direction:column;gap:.55rem;min-width:0;
  box-shadow:var(--shadow);transition:border-color .15s ease,transform .15s ease}}
@media (hover:hover) and (pointer:fine){{
  .site-card:hover{{border-color:rgba(59,158,255,.4);transform:translateY(-1px)}}
}}
.card-head{{display:flex;justify-content:space-between;align-items:flex-start;gap:.6rem;min-width:0}}
.card-title{{min-width:0;flex:1}}
.card-title h2{{margin:.28rem 0 0;font-size:1.2rem;line-height:1.2;overflow-wrap:anywhere}}
.meta-line{{margin:.2rem 0 0;color:var(--muted);font-size:.75rem;overflow-wrap:anywhere}}
.track{{display:inline-block;font-size:.7rem;font-weight:700;letter-spacing:.05em;
  padding:.14rem .42rem;border-radius:6px;text-transform:uppercase}}
.track-ops{{background:rgba(240,160,48,.15);color:var(--ops);border:1px solid rgba(240,160,48,.35)}}
.track-open{{background:rgba(47,212,200,.1);color:var(--cyan);border:1px solid rgba(47,212,200,.3)}}
.pills{{display:flex;flex-direction:column;align-items:flex-end;gap:.35rem;flex:0 0 auto}}
.pill-stack{{display:flex;flex-direction:column;align-items:flex-end;gap:.12rem}}
.pill-lbl{{font-size:.7rem;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}}
.pill{{display:inline-flex;align-items:center;justify-content:center;min-width:4.4rem;
  font-size:.72rem;font-weight:800;letter-spacing:.04em;padding:.28rem .55rem;
  border-radius:999px;border:1px solid var(--line);text-transform:uppercase}}
.pill.go{{color:var(--go);background:rgba(30,207,140,.14);border-color:rgba(30,207,140,.5);
  box-shadow:0 0 0 1px rgba(30,207,140,.12)}}
.pill.hold{{color:var(--hold);background:rgba(240,180,41,.16);border-color:rgba(240,180,41,.5)}}
.pill.abstain{{color:var(--abstain);background:rgba(255,92,108,.14);border-color:rgba(255,92,108,.5);
  box-shadow:0 0 12px rgba(255,92,108,.12)}}
.pill.muted{{color:var(--muted)}}
.metrics{{display:grid;grid-template-columns:repeat(3,1fr);gap:.45rem;
  padding:.55rem 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}}
.metric{{min-width:0}}
.m-val{{display:block;font-size:1.2rem;font-weight:750;font-variant-numeric:tabular-nums;
  overflow-wrap:anywhere}}
.m-val.m-small{{font-size:1.05rem}}
.m-lbl{{font-size:.7rem;color:var(--muted);text-transform:uppercase;letter-spacing:.03em}}
.chips{{display:flex;flex-wrap:wrap;gap:.28rem}}
.chip{{font-size:.7rem;font-weight:650;padding:.16rem .4rem;border-radius:6px;
  border:1px solid var(--line);color:var(--muted);max-width:100%;overflow-wrap:anywhere}}
.chip.ok{{color:var(--go);border-color:rgba(30,207,140,.35)}}
.chip.warn{{color:var(--hold);border-color:rgba(240,180,41,.4)}}
.chip.silence{{color:var(--abstain);border-color:rgba(255,92,108,.45);
  background:rgba(255,92,108,.08);font-weight:750}}
.block{{background:var(--card);border:1px solid var(--line);border-radius:16px;
  margin:1rem 0;padding:1rem 1.1rem;min-width:0}}
.block h3{{margin:0 0 .65rem;font-size:.78rem;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}}
.contrast-strip{{display:grid;grid-template-columns:repeat(3,1fr);gap:.65rem}}
@media(max-width:720px){{.contrast-strip{{grid-template-columns:1fr}}}}
.contrast-cell{{background:var(--card-hi);border:1px solid var(--line);border-radius:12px;
  padding:.7rem .75rem;min-width:0}}
.contrast-name{{font-weight:700;font-size:.9rem;margin-bottom:.4rem}}
.contrast-pair{{display:flex;align-items:center;gap:.4rem;flex-wrap:wrap}}
.arrow{{color:var(--muted);font-weight:700}}
.policy-grid{{display:grid;grid-template-columns:1fr 1fr;gap:.65rem}}
@media(max-width:720px){{.policy-grid{{grid-template-columns:1fr}}}}
.policy{{background:var(--card-hi);border:1px solid var(--line);border-radius:12px;padding:.75rem .85rem}}
.policy h4{{margin:0 0 .35rem;font-size:.92rem}}
.policy p{{margin:0;font-size:.8rem;color:var(--muted)}}
.policy ul{{margin:.4rem 0 0;padding-left:1.05rem;font-size:.78rem;color:var(--muted)}}
.policy.lab{{border-color:rgba(59,158,255,.3)}}
.policy.field{{border-color:rgba(255,92,108,.28)}}
.present{{display:grid;grid-template-columns:repeat(2,1fr);gap:.55rem;margin:0;padding:0}}
@media(max-width:720px){{.present{{grid-template-columns:1fr}}}}
.present li{{list-style:none;background:var(--card-hi);border:1px solid var(--line);
  border-radius:10px;padding:.55rem .7rem;font-size:.82rem;color:var(--muted)}}
.present li b{{color:var(--text)}}
.disclaimer-bar{{position:relative;z-index:2;margin:1rem 0 0;padding:.65rem .85rem;
  border-radius:12px;background:rgba(240,180,41,.08);border:1px solid rgba(240,180,41,.35);
  font-size:.75rem;color:var(--hold);display:flex;flex-wrap:wrap;gap:.35rem .75rem;align-items:center}}
.disclaimer-bar strong{{color:var(--text);font-weight:750}}
.disclaimer-bar span{{white-space:normal}}
.footer{{margin-top:1.4rem;padding-top:.85rem;border-top:1px solid var(--line);
  color:var(--muted);font-size:.72rem}}
.footer code{{font-size:.7rem;color:var(--cyan)}}
.skip-to{{position:absolute;left:-9999px}}
.skip-to:focus{{position:static;display:inline-block;padding:.35rem .6rem;
  background:var(--accent);color:#fff;border-radius:8px;z-index:100}}
:focus-visible{{outline:2px solid var(--cyan);outline-offset:2px}}
@media (prefers-reduced-motion:reduce){{
  html{{scroll-behavior:auto}}
  *{{animation:none!important;transition:none!important}}
}}
@media print {{
  .bg-fx,.nav-links{{display:none!important}}
  body{{background:#fff;color:#111}}
  .site-card,.block,.kpi{{background:#fff;border-color:#ccc;box-shadow:none;color:#111}}
  .pill.go{{color:#060}} .pill.hold{{color:#860}} .pill.abstain{{color:#900}}
  .disclaimer-bar{{color:#530;border-color:#ca0}}
}}
</style>
</head>
<body>
<a class="skip-to" href="#main">Saltar al contenido</a>
<div class="bg-fx" aria-hidden="true"></div>
<div class="wrap">
  <nav class="topnav" aria-label="Piloto">
    <div class="brand">
      <div class="brand-mark" aria-hidden="true"></div>
      <div>
        <h1>WFD · PILOTO DE HONESTIDAD</h1>
        <div class="sub">{_html_esc(sites_joined)} · {_html_esc(product_id)}</div>
      </div>
    </div>
    <div class="nav-links">
      <a href="#sitios">Sitios</a>
      <a href="#contraste">Contraste</a>
      <a href="#politicas">Políticas</a>
      <a href="#presentacion">Presentación</a>
    </div>
  </nav>

  <header class="hero" id="main">
    <div class="eyebrow">Producto dual · tarjeta de decisión multi-fuente</div>
    <h2>GO / HOLD / ABSTAIN con honestidad: Ops ≠ ML, y field_ops se calla.</h2>
    <p>
      Tres sitios, un criterio. <b>research_open</b> puede ser experimental;
      <b>field_ops</b> fusión live = <b>OFF</b>. No es orden táctica de despacho.
    </p>
  </header>

  <section class="kpi-strip" aria-label="Indicadores">
    <div class="kpi">
      <div class="kpi-val">{_html_esc(n_ok)}/{_html_esc(n_sites)}</div>
      <div class="kpi-lbl">sitios OK</div>
    </div>
    <div class="kpi">
      <div class="kpi-val">{_html_esc(_fmt_num(catalog_iou, 4))}</div>
      <div class="kpi-lbl">holdout · solo provenance</div>
    </div>
    <div class="kpi">
      <div class="kpi-val">{_html_esc(_fmt_num(mean_iou, 3))}</div>
      <div class="kpi-lbl">U1 IoU ({_html_esc(u1_source)})</div>
    </div>
    <div class="kpi">
      <div class="kpi-val">{_html_esc(policy)}</div>
      <div class="kpi-lbl">política primaria</div>
    </div>
  </section>

  <section id="sitios" class="cards" aria-label="Tarjetas por sitio">
    {"".join(site_cards)}
  </section>

  <section class="block" id="contraste">
    <h3>Contraste research_open → field_ops</h3>
    <div class="contrast-strip">
      {"".join(contrast_cells)}
    </div>
  </section>

  <section class="block" id="politicas">
    <h3>Políticas</h3>
    <div class="policy-grid">
      <div class="policy lab">
        <h4>research_open</h4>
        <p>Laboratorio / amigable con open. Fusión live experimental.</p>
        <ul>
          <li>Puede emitir GO con live</li>
          <li>Útil para demo de lab</li>
        </ul>
      </div>
      <div class="policy field">
        <h4>field_ops · fusión OFF</h4>
        <p>require_ops_for_go · ABSTAIN fail-closed (cierre seguro) sin fiabilidad verificada.</p>
        <ul>
          <li>No inventa R1–R4</li>
          <li>reason: field_ops_fail_closed_reliability_unverified</li>
        </ul>
      </div>
    </div>
  </section>

  <section class="block" id="presentacion">
    <h3>Modo presentación</h3>
    <ul class="present">
      <li><b>1.</b> Ops ≠ ML — fusión solo en tarjeta de decisión</li>
      <li><b>2.</b> field_ops fusión live = OFF — se calla (ABSTAIN/HOLD)</li>
      <li><b>3.</b> Cifras: ROS solo OPS; ha solo open; sin Vp táctica</li>
      <li><b>4.</b> Catalog holdout {_html_esc(_fmt_num(catalog_iou, 4))} = provenance only</li>
      <li><b>5.</b> U1 ({_html_esc(u1_source)}): IoU {_html_esc(_fmt_num(mean_iou))} · sel@80 {_html_esc(_fmt_num(sel80))} · ECE {_html_esc(_fmt_num(ece))}</li>
      <li><b>6.</b> No es multi-CCAA «funciona en toda España»</li>
    </ul>
  </section>

  <div class="disclaimer-bar" role="note">
    <strong>Honestidad</strong>
    <span>No es orden táctica</span>
    <span>· field_ops fusión OFF</span>
    <span>· provenance only (no certeza en vivo)</span>
    <span>· FIRMS ≠ quemado oficial</span>
  </div>

  <footer class="footer">
    Generado: {_html_esc(generated_at)} · producto {_html_esc(product_id)} ·
    informe <code>report/PILOT_HONESTY_CARD.md</code>
  </footer>
</div>
</body>
</html>
"""


def process_site(
    site: dict[str, Any],
    *,
    base: Path,
    demo_mod: Any,
    mode: str,
    scenario_override: str | None,
    product_id: str,
    policy_id: str,
    include_field_ops: bool,
    allow_missing_pack: bool,
    out_sites: Path,
    u1: dict[str, Any],
    ml_prediction_global: Path | None,
    npz: Path | None,
    calibrator: str | None,
    tobarra_window: str | None,
) -> dict[str, Any]:
    from wildfire_front.product.decide_service import (
        attach_infocam_anchor_audit,
        load_infocam_anchor,
        load_open_metrics_from_pack,
        load_ops_metrics_from_work_dir,
    )

    site_id = str(site.get("site_id") or "site")
    display = str(site.get("display_name") or site_id)
    track = str(site.get("track") or "")
    event_id = str(site.get("event_id") or f"pilot_{site_id}")
    site_out = out_sites / site_id
    site_out.mkdir(parents=True, exist_ok=True)

    work_raw = site.get("work_dir")
    # production tobarra window override
    if (
        site_id == "tobarra"
        and tobarra_window
        and isinstance(work_raw, str)
        and "tobarra_20240802" in work_raw.replace("\\", "/")
    ):
        parts = Path(work_raw.replace("\\", "/")).parts
        if parts and parts[-1] in {"early", "mid", "late"}:
            work_raw = str(Path(*parts[:-1]) / tobarra_window)

    work_dir = resolve_site_path(work_raw, base)
    open_pack = resolve_site_path(site.get("open_pack"), base)
    anchors_path = resolve_site_path(site.get("anchors_path"), base)
    ml_pred_site = resolve_site_path(site.get("ml_prediction"), base)

    sources_requested = {
        "ops": work_dir is not None,
        "open": open_pack is not None,
        "ml_live": True,
        "ml_holdout": False,
    }

    missing: list[str] = []
    if work_dir is not None and not work_dir.exists():
        missing.append(f"work_dir={work_dir.as_posix()}")
    if open_pack is not None and not open_pack.exists():
        missing.append(f"open_pack={open_pack.as_posix()}")

    if missing and not allow_missing_pack:
        raise FileNotFoundError(
            f"site {site_id} missing paths: {', '.join(missing)}"
        )

    if missing and allow_missing_pack:
        skip_summary = {
            "schema": "pilot_honesty_site_summary_v1",
            "site_id": site_id,
            "event_id": event_id,
            "track": track,
            "policy_id": policy_id,
            "skipped": True,
            "skip_reason": "missing_pack: " + "; ".join(missing),
            "sources_requested": sources_requested,
            "sources_resolved": {"ops": False, "open": False, "ml_live": False},
            "paths": {
                "open_pack": open_pack.as_posix() if open_pack else None,
                "work_dir": work_dir.as_posix() if work_dir else None,
                "ml_prediction": None,
            },
            "honesty_flags": {
                "vp_invented": False,
                "firms_hull_is_official_burned_area": False,
                "catalog_iou_is_provenance_only": True,
                "tactical_dispatch": False,
                "sources_incomplete": True,
            },
            "field_ops_allow_ml_live_in_fusion": False,
        }
        _write_json(site_out / "site_summary.json", skip_summary)
        return skip_summary

    # Allow roots = {catalog path base, REPO_ROOT} so fixture-root outside
    # the repo tree still resolves (design §3.3.1).
    open_metrics = None
    if open_pack is not None and open_pack.exists():
        open_metrics = load_open_metrics_from_pack(
            open_pack, base=base, include_repo_root=True
        )
        if open_metrics is None and not allow_missing_pack:
            raise FileNotFoundError(
                f"site {site_id}: open_pack present but open metrics unresolved: {open_pack}"
            )

    ops_metrics = None
    if work_dir is not None and work_dir.exists():
        ops_metrics = load_ops_metrics_from_work_dir(
            work_dir, base=base, include_repo_root=True
        )
        if ops_metrics is None and not allow_missing_pack and sources_requested["ops"]:
            raise FileNotFoundError(
                f"site {site_id}: work_dir present but ops metrics unresolved "
                f"(ROS required): {work_dir}"
            )
        if ops_metrics is not None and anchors_path is not None and site.get("anchor_key"):
            anchor = load_infocam_anchor(
                anchors_path,
                str(site.get("anchor_key")),
                base=base,
                include_repo_root=True,
            )
            ops_metrics = attach_infocam_anchor_audit(
                ops_metrics, anchor, fire_id=str(site.get("anchor_key"))
            )

    scenario = scenario_override or str(site.get("ml_scenario") or "hold")
    site_mode = mode
    ml_path = ml_pred_site or ml_prediction_global
    if mode == "from-json" and ml_path is None:
        site_mode = "offline"

    if site_mode == "from-json":
        if ml_path is None or not Path(ml_path).is_file():
            raise FileNotFoundError(f"site {site_id}: ml prediction required for from-json")
        ml_doc = _load_json(Path(ml_path))
        if not ml_doc:
            raise ValueError(f"invalid ml prediction: {ml_path}")
        ml_doc = dict(ml_doc)
    elif site_mode == "live":
        if npz is None:
            raise ValueError("live mode requires --npz")
        ml_doc = demo_mod.predict_live_ml_document(
            Path(npz), product_id=product_id, calibrator_path=calibrator
        )
        ml_doc["event_id"] = event_id
    else:
        ml_doc = demo_mod.load_fixture_ml_prediction(
            scenario, product_id=product_id, event_id=event_id
        )

    card = demo_mod.build_card_from_ml_doc(
        ml_doc,
        event_id=event_id,
        policy_id=policy_id,
        open_metrics=open_metrics,
        ops_metrics=ops_metrics,
    )
    note = demo_mod.build_abstain_ece_note(ml_doc, card, u1, policy_id=policy_id)

    field_card = None
    if include_field_ops:
        field_card = demo_mod.build_card_from_ml_doc(
            ml_doc,
            event_id=event_id,
            policy_id="field_ops",
            open_metrics=open_metrics,
            ops_metrics=ops_metrics,
            allow_ml_live_in_fusion=False,
        )

    pred_path = site_out / "ml_prediction.json"
    card_path = site_out / "decision_card.json"
    note_path = site_out / "abstain_ece_note.json"
    field_path = site_out / "decision_card_field_ops.json"
    sources_path = site_out / "sources.json"
    summary_path = site_out / "site_summary.json"

    live_metrics = None
    nested = ml_doc.get("ml_live_metrics")
    if isinstance(nested, dict):
        live_metrics = nested
    else:
        live_metrics = {
            k: ml_doc[k]
            for k in ML_LIVE_KEYS
            if k in ml_doc
        } or None

    sources_payload = {
        "open": allowlist_open(open_metrics),
        "ops": allowlist_ops(ops_metrics),
        "ml_live": allowlist_ml_live(live_metrics if isinstance(live_metrics, dict) else None),
    }

    metrics = card.get("metrics") or {}
    live_src = _source_by_id(card, "ml_live_reliability", "ml_live") or {}
    open_src = _source_by_id(card, "open_cems_perimeter", "open_cems") or {}
    ops_src = _source_by_id(card, "ops_thermal_front", "ops") or {}

    honesty_flags = {
        "vp_invented": bool((open_metrics or {}).get("vp_invented", False)),
        "firms_hull_is_official_burned_area": bool(
            (open_metrics or {}).get("firms_hull_is_official_burned_area", False)
        ),
        "catalog_iou_is_provenance_only": True,
        "tactical_dispatch": False,
        "sources_incomplete": bool(
            (sources_requested["open"] and open_metrics is None)
            or (sources_requested["ops"] and ops_metrics is None)
        ),
    }

    contrast_block: dict[str, Any] | None = None
    if field_card is not None:
        field_reasons = _card_fail_closed_reason(field_card)
        contrast_block = {
            "decision": field_card.get("decision"),
            "path": _rel_posix(field_path),
            "reliability_gate_passed": False,
            "fail_closed_reason_expected_if_pre_go": (
                "field_ops_fail_closed_reliability_unverified"
            ),
            "reasons": field_card.get("reasons"),
            "reasons_text": field_reasons,
        }

    site_summary: dict[str, Any] = {
        "schema": "pilot_honesty_site_summary_v1",
        "site_id": site_id,
        "display_name": display,
        "event_id": event_id,
        "track": track,
        "policy_id": policy_id,
        "skipped": False,
        "sources_requested": sources_requested,
        "sources_resolved": {
            "ops": ops_metrics is not None,
            "open": open_metrics is not None,
            "ml_live": True,
        },
        "paths": {
            "open_pack": open_pack.as_posix() if open_pack else None,
            "work_dir": work_dir.as_posix() if work_dir else None,
            "ml_prediction": _rel_posix(pred_path),
        },
        "decision": card.get("decision"),
        "confidence_pred": card.get("confidence_pred"),
        "live_ok": metrics.get("live_ok"),
        "live_available": metrics.get("live_available"),
        "live_abstained": bool(live_src.get("abstained")),
        "allow_ml_live_in_fusion": metrics.get("allow_ml_live_in_fusion"),
        "field_ops_allow_ml_live_in_fusion": False,
        "open_max_area_ha": (open_metrics or {}).get("max_area_ha"),
        "ops_primary_ros_m_min": (ops_metrics or {}).get("primary_ros_m_min"),
        "honesty_flags": honesty_flags,
        "u1_ece_patch_conf": u1.get("ece_patch_conf"),
        "u1_source": u1.get("u1_source"),
        "card_path": _rel_posix(card_path),
        "contrast_field_ops": contrast_block,
        "open_available": bool(open_src.get("available")),
        "ops_available": bool(ops_src.get("available")),
    }

    _write_json(pred_path, ml_doc)
    _write_json(card_path, card)
    _write_json(note_path, note)
    _write_json(sources_path, sources_payload)
    if field_card is not None:
        _write_json(field_path, field_card)
    _write_json(summary_path, site_summary)
    return site_summary


def run_pilot(
    *,
    mode: str = "offline",
    scenario: str | None = None,
    product_id: str = DEFAULT_PRODUCT,
    policy_id: str = DEFAULT_POLICY,
    include_field_ops_contrast: bool = True,
    sites_filter: list[str] | None = None,
    tobarra_window: str | None = "mid",
    fixture_root: Path | None = None,
    sites_config: Path | None = None,
    out_dir: Path | None = None,
    write_docs_report: bool = False,
    allow_missing_pack: bool = False,
    generated_at: str | None = None,
    npz: Path | None = None,
    ml_prediction: Path | None = None,
    calibrator: str | None = None,
) -> dict[str, Any]:
    demo_mod = _load_demo_mod()
    u1 = demo_mod.load_u1_honesty_snapshot()
    gen_at = generated_at or datetime.now(UTC).isoformat()

    catalog, catalog_source = load_catalog(
        sites_config=sites_config, fixture_root=fixture_root
    )
    base = resolve_path_base(
        fixture_root=fixture_root,
        catalog=catalog,
        sites_config=sites_config,
        catalog_source=catalog_source,
    )

    sites = [s for s in (catalog.get("sites") or []) if isinstance(s, dict)]
    if sites_filter:
        wanted = {s.strip() for s in sites_filter if s.strip()}
        sites = [s for s in sites if str(s.get("site_id")) in wanted]

    out = Path(out_dir) if out_dir else DEFAULT_OUT
    out.mkdir(parents=True, exist_ok=True)
    sites_dir = out / "sites"
    report_dir = out / "report"
    sites_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    site_summaries: list[dict[str, Any]] = []
    failed = False
    for site in sites:
        try:
            summary = process_site(
                site,
                base=base,
                demo_mod=demo_mod,
                mode=mode,
                scenario_override=scenario,
                product_id=product_id,
                policy_id=policy_id,
                include_field_ops=include_field_ops_contrast,
                allow_missing_pack=allow_missing_pack,
                out_sites=sites_dir,
                u1=u1,
                ml_prediction_global=ml_prediction,
                npz=npz,
                calibrator=calibrator,
                tobarra_window=tobarra_window,
            )
            site_summaries.append(summary)
            if summary.get("skipped") and not allow_missing_pack:
                failed = True
        except (FileNotFoundError, ValueError, OSError) as exc:
            failed = True
            site_summaries.append(
                {
                    "schema": "pilot_honesty_site_summary_v1",
                    "site_id": site.get("site_id"),
                    "skipped": False,
                    "failed": True,
                    "error": str(exc),
                    "honesty_flags": {
                        "sources_incomplete": True,
                        "catalog_iou_is_provenance_only": True,
                        "tactical_dispatch": False,
                        "vp_invented": False,
                        "firms_hull_is_official_burned_area": False,
                    },
                    "field_ops_allow_ml_live_in_fusion": False,
                }
            )

    # Rebuild facts from successful site data + re-read sources when possible
    facts_rows: list[dict[str, Any]] = []
    for site, summary in zip(sites, site_summaries, strict=False):
        if summary.get("skipped") or summary.get("failed"):
            facts_rows.append(
                {
                    "site_id": site.get("site_id"),
                    "display_name": site.get("display_name"),
                    "track": site.get("track"),
                    "sources": "incomplete",
                    "decision_research_open": summary.get("decision"),
                    "confidence_pred": None,
                    "live_ok": None,
                    "live_available": None,
                    "live_abstained": None,
                    "allow_ml_live_in_fusion": None,
                    "decision_field_ops": (summary.get("contrast_field_ops") or {}).get(
                        "decision"
                    ),
                    "key_number_label": "—",
                    "key_number_value": None,
                    "key_number_source": "—",
                    "pack_verdict": None,
                    "honesty_note": summary.get("skip_reason")
                    or summary.get("error")
                    or "incomplete",
                }
            )
            continue
        sid = str(site.get("site_id"))
        sources_doc = _load_json(sites_dir / sid / "sources.json") or {}
        open_m = sources_doc.get("open") if isinstance(sources_doc.get("open"), dict) else None
        ops_m = sources_doc.get("ops") if isinstance(sources_doc.get("ops"), dict) else None
        facts_rows.append(build_facts_row(site, summary, open_m, ops_m))

    facts_table = {
        "schema": "pilot_honesty_facts_table_v1",
        "rows": facts_rows,
    }
    pilot_manifest = {
        "schema": "pilot_honesty_manifest_v1",
        "generated_at": gen_at,
        "mode": mode,
        "policy_id": policy_id,
        "product_id": product_id,
        "catalog_source": catalog_source,
        "path_base": base.as_posix(),
        "fixture_root": fixture_root.as_posix() if fixture_root else None,
        "out_dir": _rel_posix(out),
        "include_field_ops_contrast": include_field_ops_contrast,
        "sites": [s.get("site_id") for s in sites],
        "u1_source": u1.get("u1_source"),
    }

    report_md = render_report(
        facts_table,
        site_summaries,
        u1,
        generated_at=gen_at,
        pilot_manifest=pilot_manifest,
    )

    pilot_summary = {
        "schema": "pilot_honesty_summary_v1",
        "generated_at": gen_at,
        "mode": mode,
        "policy_id": policy_id,
        "product_id": product_id,
        "n_sites": len(site_summaries),
        "n_ok": sum(
            1
            for s in site_summaries
            if not s.get("skipped") and not s.get("failed")
        ),
        "n_skipped": sum(1 for s in site_summaries if s.get("skipped")),
        "n_failed": sum(1 for s in site_summaries if s.get("failed")),
        "sites": site_summaries,
        "field_ops_allow_ml_live_in_fusion": False,
        "u1": {
            "mean_iou_eval": u1.get("mean_iou_eval"),
            "selective_iou_at_80": u1.get("selective_iou_at_80"),
            "ece_patch_conf": u1.get("ece_patch_conf"),
            "catalog_holdout_iou_provenance": u1.get("catalog_holdout_iou_provenance"),
            "u1_source": u1.get("u1_source"),
        },
        "honesty": [
            "Ops ≠ ML; fusión solo en Decision Card; nunca entrenar con etiquetas fusionadas.",
            "Sin Vp/ROS táctico inventado desde packs open o máscaras ML.",
            "Catalog holdout IoU es provenance only — no es certeza del incendio en vivo.",
            "research_open fusión live es superficie de lab experimental; field_ops fusión OFF.",
            "Contraste field_ops no inventa R1–R4; esperar HOLD/ABSTAIN, no GO falso.",
        ],
        "failed": failed,
    }

    portal_html = render_pilot_portal_html(
        facts_table,
        site_summaries,
        u1,
        generated_at=gen_at,
        pilot_manifest=pilot_manifest,
        pilot_summary=pilot_summary,
    )

    _write_json(out / "pilot_manifest.json", pilot_manifest)
    _write_json(out / "pilot_summary.json", pilot_summary)
    _write_json(out / "facts_table.json", facts_table)
    report_path = report_dir / "PILOT_HONESTY_CARD.md"
    report_path.write_text(report_md + "\n", encoding="utf-8")
    portal_path = out / "index.html"
    portal_path.write_text(portal_html, encoding="utf-8")

    readme = "\n".join(
        [
            "# Piloto de honestidad — tarjeta de decisión",
            "",
            "Tarjetas multi-fuente: Tobarra (OPS), Níjar (AND), Caminomorisco (EXT).",
            "",
            "## Abrir",
            "- Portal: `index.html`",
            "- Informe: `report/PILOT_HONESTY_CARD.md`",
            "",
            "## Honestidad",
            "- Producto dual: Ops ≠ ML",
            "- field_ops fusión live = OFF",
            "- Catalog holdout IoU = provenance only",
            "- No es orden táctica de despacho",
            "",
            f"Generado: {gen_at}",
            "",
        ]
    )
    (out / "README.md").write_text(readme, encoding="utf-8")

    # Publish docs when explicitly requested or when writing the default pilot out dir
    publish_docs = bool(write_docs_report)
    try:
        if out.resolve() == DEFAULT_OUT.resolve():
            publish_docs = True
    except OSError:
        pass
    if publish_docs:
        DOCS_REPORT.parent.mkdir(parents=True, exist_ok=True)
        DOCS_REPORT.write_text(report_md + "\n", encoding="utf-8")

    pilot_summary["_paths"] = {
        "out_dir": str(out),
        "report": str(report_path),
        "portal": str(portal_path),
        "docs_report": str(DOCS_REPORT) if publish_docs else None,
    }
    pilot_summary["_failed"] = failed
    return pilot_summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Pilot honesty Decision Cards for multi-source packs "
            "(offline fixtures by default)."
        )
    )
    parser.add_argument(
        "--mode",
        choices=("offline", "live", "from-json"),
        default="offline",
    )
    parser.add_argument(
        "--scenario",
        choices=("hold", "abstain", "identity"),
        default=None,
        help="Optional global override of per-site ml_scenario",
    )
    parser.add_argument("--policy", default=DEFAULT_POLICY)
    parser.add_argument(
        "--include-field-ops-contrast",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--sites",
        type=str,
        default=None,
        help="Comma-separated site ids (default: all in catalog)",
    )
    parser.add_argument(
        "--tobarra-window",
        choices=("early", "mid", "late"),
        default="mid",
        help="Production catalog Tobarra window override",
    )
    parser.add_argument(
        "--fixture-root",
        type=str,
        default=None,
        help="CI fixture root; auto-loads DIR/pilot_sites.json when present",
    )
    parser.add_argument(
        "--sites-config",
        type=str,
        default=None,
        help="Explicit pilot_sites.json catalog",
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default=str(DEFAULT_OUT),
    )
    parser.add_argument(
        "--write-docs-report",
        action="store_true",
        help=f"Also write {DOCS_REPORT.as_posix()}",
    )
    parser.add_argument(
        "--allow-missing-pack",
        action="store_true",
        help="SKIP incomplete sites instead of FAIL",
    )
    parser.add_argument(
        "--generated-at",
        type=str,
        default=None,
        help="Fixed ISO8601 timestamp for deterministic reports",
    )
    parser.add_argument("--product", default=DEFAULT_PRODUCT)
    parser.add_argument("--npz", type=str, default=None)
    parser.add_argument("--ml-prediction", type=str, default=None)
    parser.add_argument("--calibrator", type=str, default=None)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print pilot_summary JSON only",
    )
    args = parser.parse_args(argv)

    sites_filter = None
    if args.sites:
        sites_filter = [s.strip() for s in args.sites.split(",") if s.strip()]

    try:
        summary = run_pilot(
            mode=args.mode,
            scenario=args.scenario,
            product_id=args.product,
            policy_id=args.policy,
            include_field_ops_contrast=bool(args.include_field_ops_contrast),
            sites_filter=sites_filter,
            tobarra_window=args.tobarra_window,
            fixture_root=Path(args.fixture_root) if args.fixture_root else None,
            sites_config=Path(args.sites_config) if args.sites_config else None,
            out_dir=Path(args.out_dir),
            write_docs_report=bool(args.write_docs_report),
            allow_missing_pack=bool(args.allow_missing_pack),
            generated_at=args.generated_at,
            npz=Path(args.npz) if args.npz else None,
            ml_prediction=Path(args.ml_prediction) if args.ml_prediction else None,
            calibrator=args.calibrator,
        )
    except (FileNotFoundError, ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if summary.get("_failed"):
        print("ERROR: one or more pilot sites failed", file=sys.stderr)
        if args.json:
            print(
                json.dumps(
                    {k: v for k, v in summary.items() if not k.startswith("_")},
                    indent=2,
                    ensure_ascii=False,
                )
            )
        return 2

    if args.json:
        print(
            json.dumps(
                {k: v for k, v in summary.items() if not k.startswith("_")},
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        print("=== Pilot honesty card ===")
        print(
            f"sites_ok={summary.get('n_ok')}/{summary.get('n_sites')}  "
            f"policy={summary.get('policy_id')}  mode={summary.get('mode')}"
        )
        for s in summary.get("sites") or []:
            if s.get("skipped"):
                print(f"  {s.get('site_id')}: SKIP ({s.get('skip_reason')})")
            elif s.get("failed"):
                print(f"  {s.get('site_id')}: FAIL ({s.get('error')})")
            else:
                print(
                    f"  {s.get('site_id')}: {s.get('decision')}  "
                    f"conf={s.get('confidence_pred')}  "
                    f"field_ops={(s.get('contrast_field_ops') or {}).get('decision')}"
                )
        paths = summary.get("_paths") or {}
        print(f"report: {paths.get('report')}")
        if paths.get("portal"):
            print(f"portal: {paths.get('portal')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
