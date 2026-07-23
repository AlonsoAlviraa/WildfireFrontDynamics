#!/usr/bin/env python3
"""Dedicated print-friendly pitch one-pager for multi-CCAA demo."""

from __future__ import annotations

import html as html_lib
from pathlib import Path
from typing import Any


def _esc(s: Any) -> str:
    if s is None:
        return ""
    return html_lib.escape(str(s), quote=True)


def _fmt_ha(v: Any) -> str:
    if v is None:
        return "—"
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "—"
    return f"{f:.0f}" if f >= 100 else f"{f:g}"


def _fmt_vp(v: Any) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):g}"
    except (TypeError, ValueError):
        return "—"


def render_pitch_html(
    *,
    sites: list[dict[str, Any]],
    kpi: dict[str, Any],
    manifest: dict[str, Any],
    version: str = "2.1.0",
    git_hash: str | None = None,
) -> str:
    """One-page print-friendly HTML pitch (no Leaflet, minimal JS)."""
    by_id = {s["id"]: s for s in sites if s.get("id")}
    tb = by_id.get("tobarra") or {}
    nj = by_id.get("nijar") or {}
    cm = by_id.get("camino") or {}
    built = _esc(manifest.get("built_at_utc") or "")
    gh = _esc(git_hash or manifest.get("git_short") or "n/a")
    kn_tb = tb.get("key_numbers") or {}
    kn_nj = nj.get("key_numbers") or {}
    kn_cm = cm.get("key_numbers") or {}

    rows = []
    for s in sites:
        if s.get("optional"):
            continue
        kn = s.get("key_numbers") or {}
        rows.append(
            "<tr>"
            f"<td>{_esc(s.get('name_display') or s.get('name'))}</td>"
            f"<td>{_esc(s.get('ccaa_short') or s.get('ccaa'))}</td>"
            f"<td>{_esc(s.get('track'))}</td>"
            f"<td>{_esc(_fmt_ha(kn.get('area_ha')))}</td>"
            f"<td>{_esc(_fmt_vp(kn.get('vp_m_min')))}</td>"
            f"<td>{_esc(s.get('decision_open'))}</td>"
            f"<td>{_esc(s.get('verdict'))}</td>"
            "</tr>"
        )

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>WFD · Pitch multi-CCAA one-pager</title>
<style>
  :root {{ --ink:#111; --muted:#444; --line:#ccc; --accent:#0a5; }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: "Segoe UI", system-ui, sans-serif;
    color: var(--ink); background: #fff; margin: 0; padding: 1.25rem 1.5rem;
    line-height: 1.45; font-size: 11.5pt;
  }}
  h1 {{ font-size: 1.35rem; margin: 0 0 .35rem; letter-spacing: -0.02em; }}
  h2 {{ font-size: .95rem; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); margin: 1rem 0 .4rem; border-bottom: 1px solid var(--line); padding-bottom: .2rem; }}
  .claim {{ font-size: 1.05rem; max-width: 40rem; margin: .4rem 0 .8rem; }}
  .no {{ color: #a20; font-size: .9rem; }}
  .meta {{ color: var(--muted); font-size: .8rem; margin-bottom: .8rem; }}
  table {{ width: 100%; border-collapse: collapse; font-size: .88rem; margin: .4rem 0; }}
  th, td {{ border-bottom: 1px solid var(--line); padding: .35rem .3rem; text-align: left; }}
  th {{ color: var(--muted); font-size: .72rem; text-transform: uppercase; }}
  ul {{ margin: .3rem 0; padding-left: 1.2rem; }}
  .cta {{ display: flex; gap: 1rem; flex-wrap: wrap; margin-top: .6rem; }}
  .cta div {{ border: 1px solid var(--line); border-radius: 8px; padding: .55rem .75rem; flex: 1; min-width: 140px; }}
  .cta strong {{ display: block; margin-bottom: .2rem; }}
  footer {{ margin-top: 1.2rem; font-size: .75rem; color: var(--muted); border-top: 1px solid var(--line); padding-top: .5rem; }}
  @media print {{
    body {{ padding: .6rem .9rem; font-size: 10.5pt; }}
    h1 {{ font-size: 1.2rem; }}
    .no-print {{ display: none !important; }}
    a {{ color: inherit; text-decoration: none; }}
  }}
</style>
</head>
<body>
  <p class="meta no-print"><button onclick="window.print()">Imprimir / PDF</button> ·
    <a href="../index.html">← Volver al portal</a></p>
  <h1>Wildfire Front Dynamics · Demo multi-CCAA</h1>
  <p class="claim"><b>Decision support multi-CCAA:</b> térmico validado donde hay datos,
    perímetro oficial donde hay Junta, <b>abstención cuando no se puede mentir</b>.</p>
  <p class="no"><b>No claim:</b> no apagamos incendios con IA · no 99% precisión del fuego · no sustituimos INFOCA/INFOEX · hull FIRMS ≠ área quemada oficial.</p>

  <h2>Tres sitios · un criterio</h2>
  <table>
    <thead><tr><th>IF</th><th>CCAA</th><th>Track</th><th>ha</th><th>Vp</th><th>Decisión</th><th>Verdict</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
  <ul>
    <li><b>Tobarra OPS:</b> {_esc(_fmt_vp(kn_tb.get('vp_m_min')))} m/min · {_esc(_fmt_ha(kn_tb.get('area_ha')))} ha · {_esc(tb.get('status_anchor') or '—')}</li>
    <li><b>Níjar AND O2:</b> ~{_esc(_fmt_ha(kn_nj.get('area_ha')))} ha REDIAM · {_esc(nj.get('verdict'))}</li>
    <li><b>Caminomorisco EXT O2:</b> ~{_esc(_fmt_ha(kn_cm.get('area_ha')))} ha RAI · det {_esc(kn_cm.get('fecha_det') or '—')} → {_esc(kn_cm.get('fecha_ext') or '—')}</li>
  </ul>

  <h2>KPIs demo</h2>
  <ul>
    <li>CCAA: {_esc(kpi.get('n_ccaa'))} · IF demo: {_esc(kpi.get('n_sites'))} · ha O2: {_esc(kpi.get('sum_ha_o2'))}</li>
    <li>Catálogo AND: {_esc(kpi.get('n_and_catalog'))} IF · EXT entregados: {_esc(kpi.get('n_ext_delivery'))}</li>
    <li>Anclas confirmed: {_esc(kpi.get('n_confirmed_anchors'))} · Gates PASS: {_esc(kpi.get('gate_pass'))}/{_esc(kpi.get('gate_total'))}</li>
  </ul>

  <h2>Por qué HOLD vende</h2>
  <p>Reliability gate: el sistema <b>no emite GO táctico</b> si faltan fuentes.
    Residual silent-GO controlado por diseño (suite de abstención/gates).
    Audit trail + provenance + actas E2E (GOLD · AND · EXT).</p>

  <h2>CTAs</h2>
  <div class="cta">
    <div><strong>Feedback 30 min</strong>alonso.alvbal@gmail.com</div>
    <div><strong>Ancla Vp/ha (1 IF)</strong>ASEMA / RAI / INFOCAM</div>
    <div><strong>Carta interés UE</strong>UCPM / SUDOE / Horizon</div>
  </div>

  <footer>
    Built {built} · demo_version {_esc(version)} · git {gh} · schema {_esc(manifest.get('schema'))}<br/>
    Atribuciones: INFOCAM · REDIAM Junta Andalucía · RAI/INFOEX Junta Extremadura · material Heligrafics/CMA (LWIR Tobarra)
  </footer>
</body>
</html>
"""


def write_pitch_exports(
    out_dir: Path,
    *,
    sites: list[dict[str, Any]],
    kpi: dict[str, Any],
    manifest: dict[str, Any],
    version: str = "2.1.0",
    git_hash: str | None = None,
) -> dict[str, str]:
    """Write pitch HTML + refresh pitch markdown. Returns relative paths written."""
    export = out_dir / "export"
    export.mkdir(parents=True, exist_ok=True)
    html = render_pitch_html(
        sites=sites, kpi=kpi, manifest=manifest, version=version, git_hash=git_hash
    )
    (export / "pitch_onepager.html").write_text(html, encoding="utf-8")

    by_id = {s["id"]: s for s in sites if s.get("id")}
    tb = by_id.get("tobarra") or {}
    nj = by_id.get("nijar") or {}
    cm = by_id.get("camino") or {}
    kn_tb = tb.get("key_numbers") or {}
    kn_nj = nj.get("key_numbers") or {}
    kn_cm = cm.get("key_numbers") or {}
    gh = git_hash or manifest.get("git_short") or "n/a"

    pitch_md = "\n".join(
        [
            "# WFD multi-CCAA pitch (one-pager)",
            "",
            str(manifest.get("title") or "Demo multi-CCAA"),
            "",
            f"Built: {manifest.get('built_at_utc')}",
            f"demo_version: {version} · git: {gh}",
            f"schema: {manifest.get('schema')}",
            "",
            "## Claim",
            "Decision support multi-CCAA: validated thermal where data exists,",
            "official perimeters where agencies share them, abstention when we cannot invent.",
            "",
            "## No claim",
            "- No apagamos incendios con IA",
            "- No 99% fire accuracy",
            "- No sustituimos INFOCA/INFOEX",
            "- FIRMS hull ≠ official burned area",
            "",
            "## Numbers",
            f"- Tobarra OPS: Vp={kn_tb.get('vp_m_min')} m/min · ha={kn_tb.get('area_ha')} · status={tb.get('status_anchor')}",
            f"- Níjar AND O2: ha={kn_nj.get('area_ha')} · verdict={nj.get('verdict')}",
            f"- Caminomorisco EXT O2: ha={kn_cm.get('area_ha')} · det={kn_cm.get('fecha_det')} → ext={kn_cm.get('fecha_ext')}",
            f"- AND catalog IF: {kpi.get('n_and_catalog')}",
            f"- EXT delivered IF: {kpi.get('n_ext_delivery')}",
            f"- Gates PASS: {kpi.get('gate_pass')}/{kpi.get('gate_total')}",
            "",
            "## Reliability",
            "- HOLD/ABSTAIN without ops anchor is a product feature",
            "- Residual silent-GO controlled by design (abstention/gates suite)",
            "- Audit trail + provenance + E2E actas",
            "",
            "## CTAs",
            "- alonso.alvbal@gmail.com — feedback 30 min / anchor / EU letter",
            "",
            "## Contacts provenance",
            "- REDIAM: rediam.atiende.csma@juntadeandalucia.es",
            "- RAI/INFOEX: rai@juntaex.es",
            "- INFOCAM anchors: data/infocam_anchors.json",
            "",
            "## HTML print",
            "- export/pitch_onepager.html",
            "",
        ]
    )
    (export / "pitch_onepager.md").write_text(pitch_md, encoding="utf-8")
    return {
        "pitch_html": "export/pitch_onepager.html",
        "pitch_md": "export/pitch_onepager.md",
    }
