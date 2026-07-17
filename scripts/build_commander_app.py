#!/usr/bin/env python3
"""Build the Commander (sala de mando) web app — spectacular ops HUD.

  python scripts/build_commander_app.py
  # → docs/commander/index.html  (open in browser)

Embeds live metrics, Decision Card, open-pack perimeters (simplified).
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT_DIR = ROOT / "docs" / "commander"


def _load(p: Path) -> Any:
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _git() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT), text=True
        ).strip()
    except Exception:
        return "?"


def _simplify_fc(fc: dict, tol: float = 0.0015, max_features: int = 6) -> dict:
    try:
        from shapely.geometry import mapping, shape
    except ImportError:
        return fc
    feats = list(fc.get("features") or [])[-max_features:]
    out = []
    for ft in feats:
        g = ft.get("geometry")
        if not g:
            continue
        try:
            geom = shape(g).simplify(tol, preserve_topology=True)
            if geom.is_empty:
                continue
            props = dict(ft.get("properties") or {})
            # drop heavy props
            props = {
                k: props[k]
                for k in (
                    "activation",
                    "area_ha",
                    "timeline_index",
                    "kind",
                    "product_kind",
                )
                if k in props
            }
            out.append(
                {
                    "type": "Feature",
                    "properties": props,
                    "geometry": mapping(geom),
                }
            )
        except Exception:
            continue
    return {"type": "FeatureCollection", "features": out}


def _pack_payload(pack_dir: Path) -> dict[str, Any] | None:
    sc = _load(pack_dir / "scorecard_pista_b.json")
    if not sc:
        return None
    tl = pack_dir / "timeline_perimeters.geojson"
    fc = _load(tl) if tl.is_file() else None
    simp = _simplify_fc(fc) if fc else {"type": "FeatureCollection", "features": []}
    # centroid from last feature
    lat = lon = None
    try:
        from shapely.geometry import shape
        from shapely.ops import unary_union

        geoms = [shape(f["geometry"]) for f in simp.get("features") or [] if f.get("geometry")]
        if geoms:
            c = unary_union(geoms).centroid
            lon, lat = float(c.x), float(c.y)
    except Exception:
        pass
    dnbr = _load(pack_dir / "dnbr_status.json") or {}
    return {
        "id": pack_dir.name,
        "activation": sc.get("activation") or pack_dir.name.upper(),
        "max_area_ha": sc.get("max_area_ha"),
        "n_timeline_steps": sc.get("n_timeline_steps"),
        "O2_cems_delineation": sc.get("O2_cems_delineation"),
        "dnbr_status": dnbr.get("status") or sc.get("dnbr_stac_status"),
        "dnbr_mean": sc.get("dnbr_mean") or dnbr.get("severity_mean"),
        "status": sc.get("status"),
        "lat": lat,
        "lon": lon,
        "geojson": simp,
        "map_rel": f"../../outputs/open_if/{pack_dir.name}/map.html",
    }


def collect_data() -> dict[str, Any]:
    # refresh hub quietly
    try:
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_metrics_hub.py")],
            cwd=str(ROOT),
            env={**os.environ, "PYTHONPATH": str(ROOT)},
            capture_output=True,
            timeout=120,
        )
    except Exception:
        pass

    hub = _load(ROOT / "docs" / "METRICS_HUB.json") or {}
    card = hub.get("decision_card") or _load(ROOT / "docs" / "FIRE_DECISION_CARD.json") or {}

    # stronger fusion card for demo (ops+ml+open)
    try:
        from wildfire_front.product.decide_service import decide_from_request
        from wildfire_front.product.forensics import render_radio_bridge

        card = decide_from_request(
            {
                "event_id": "COMMAND_DEMO",
                "use_ml_v34": True,
                "open_pack": "outputs/open_if/emsr578",
                "ops_metrics": (hub.get("ops") or {}).get("representative_metrics")
                or {
                    "quality_grade": "A",
                    "primary_ros_m_min": 5.71,
                    "n_frames_staged": 35,
                    "area_ha_max": 39,
                    "speed_vs_ref_ratio": 0.82,
                },
                "require_ops_for_go": False,
                "policy_id": "demo",
                "channel": "commander_app",
            },
            base=ROOT,
        )
        radio = render_radio_bridge(card)
    except Exception:
        radio = "WFD: decision unavailable — run metrics hub."

    packs = []
    open_root = ROOT / "outputs" / "open_if"
    if open_root.is_dir():
        for d in sorted(open_root.iterdir()):
            if d.is_dir() and (d / "scorecard_pista_b.json").is_file():
                p = _pack_payload(d)
                if p:
                    packs.append(p)

    policies = []
    try:
        from wildfire_front.product.policy import list_policies

        policies = list_policies()
    except Exception:
        pass

    rel = _load(ROOT / "docs" / "RELIABILITY_GATE_REPORT.json") or {}
    sla = _load(ROOT / "docs" / "DECIDE_API_LATENCY.json") or {}
    plan = _load(ROOT / "docs" / "PLAN_3_MESES_STATUS.json") or {}

    return {
        "schema": "commander_app_data_v1",
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "git": _git(),
        "title": "WFD COMMAND",
        "subtitle": "Sala de mando · Decision Card · Open CEMS · Ops térmico",
        "decision_card": card,
        "radio": radio if isinstance(radio, str) else str(radio),
        "ml": (hub.get("ml") or {}),
        "ops": (hub.get("ops") or {}),
        "packs": packs,
        "policies": policies,
        "reliability_ok": bool(rel.get("ok")),
        "api_p95_ms": ((sla.get("http_api") or {}).get("p95_ms")),
        "plan_items_done": sum(
            1
            for v in (plan.get("items") or {}).values()
            if isinstance(v, dict) and v.get("status") == "DONE"
        ),
        "disclaimers": (card.get("disclaimers") or [])[:4]
        or [
            "Not a tactical dispatch order.",
            "ABSTAIN means the product refuses to recommend action.",
        ],
    }


def html_template(data_json: str) -> str:
    # Spectacular tactical HUD — single file
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1"/>
<title>WFD COMMAND — Sala de mando</title>
<link rel="preconnect" href="https://unpkg.com"/>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
:root {{
  --bg0: #05080e;
  --bg1: #0a101a;
  --panel: rgba(12, 18, 28, 0.82);
  --panel-solid: #0e1520;
  --line: rgba(90, 140, 200, 0.22);
  --text: #e8f1ff;
  --muted: #7f95b0;
  --cyan: #3de7ff;
  --blue: #4d8dff;
  --go: #00e39a;
  --hold: #ffb020;
  --abstain: #ff4d6a;
  --glow-go: 0 0 40px rgba(0, 227, 154, 0.35);
  --glow-hold: 0 0 40px rgba(255, 176, 32, 0.35);
  --glow-ab: 0 0 40px rgba(255, 77, 106, 0.35);
  --font: "Segoe UI", system-ui, -apple-system, sans-serif;
  --mono: "Cascadia Code", "Consolas", ui-monospace, monospace;
}}
* {{ box-sizing: border-box; }}
html, body {{ height: 100%; margin: 0; }}
body {{
  font-family: var(--font);
  color: var(--text);
  background: var(--bg0);
  overflow: hidden;
}}
/* starfield / tactical grid */
.bg-fx {{
  position: fixed; inset: 0; z-index: 0; pointer-events: none;
  background:
    radial-gradient(ellipse 80% 50% at 20% 0%, rgba(40,90,160,0.25), transparent 55%),
    radial-gradient(ellipse 60% 40% at 90% 80%, rgba(180,40,40,0.12), transparent 50%),
    linear-gradient(180deg, #070b12 0%, #05080e 100%);
}}
.bg-fx::after {{
  content: "";
  position: absolute; inset: 0;
  background-image:
    linear-gradient(rgba(80,140,200,0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(80,140,200,0.04) 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: radial-gradient(ellipse at center, black 30%, transparent 75%);
}}
.app {{
  position: relative; z-index: 1;
  height: 100%;
  display: grid;
  grid-template-rows: 56px 1fr 108px;
  gap: 0;
}}
/* TOP BAR */
.topbar {{
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 1rem;
  border-bottom: 1px solid var(--line);
  background: linear-gradient(180deg, rgba(14,22,36,0.95), rgba(10,16,26,0.75));
  backdrop-filter: blur(12px);
}}
.brand {{
  display: flex; align-items: center; gap: .75rem;
}}
.brand-mark {{
  width: 34px; height: 34px; border-radius: 10px;
  background: conic-gradient(from 210deg, var(--cyan), var(--blue), #ff6b4a, var(--cyan));
  box-shadow: 0 0 20px rgba(61,231,255,0.35);
  position: relative;
}}
.brand-mark::after {{
  content: "W";
  position: absolute; inset: 2px; border-radius: 8px;
  background: #0a101a; display: flex; align-items: center; justify-content: center;
  font-weight: 900; font-size: .9rem; color: var(--cyan);
  line-height: 34px; text-align: center;
}}
.brand h1 {{
  margin: 0; font-size: 1.05rem; letter-spacing: .12em; font-weight: 800;
}}
.brand .sub {{ color: var(--muted); font-size: .72rem; letter-spacing: .04em; }}
.top-meta {{
  display: flex; align-items: center; gap: .6rem; flex-wrap: wrap; justify-content: flex-end;
}}
.chip {{
  font-size: .7rem; font-weight: 700; letter-spacing: .06em;
  padding: .28rem .55rem; border-radius: 999px;
  border: 1px solid var(--line); background: rgba(0,0,0,.35);
  font-variant-numeric: tabular-nums;
}}
.chip.live {{
  border-color: rgba(0,227,154,.45); color: var(--go);
  animation: pulse 2.2s ease-in-out infinite;
}}
.chip.warn {{ border-color: rgba(255,176,32,.4); color: var(--hold); }}
.chip.ok {{ border-color: rgba(0,227,154,.35); color: var(--go); }}
@keyframes pulse {{
  0%, 100% {{ opacity: 1; }}
  50% {{ opacity: .65; }}
}}
/* MAIN */
.main {{
  display: grid;
  grid-template-columns: 1.35fr 0.95fr;
  min-height: 0;
}}
@media (max-width: 960px) {{
  .main {{ grid-template-columns: 1fr; grid-template-rows: 42vh 1fr; }}
  body {{ overflow: auto; }}
  .app {{ height: auto; min-height: 100%; grid-template-rows: 56px auto auto; }}
}}
.map-wrap {{
  position: relative; min-height: 0; border-right: 1px solid var(--line);
}}
#map {{
  position: absolute; inset: 0;
  background: #0a0e14;
}}
.map-overlay {{
  position: absolute; z-index: 500; left: .75rem; top: .75rem;
  display: flex; flex-direction: column; gap: .4rem; pointer-events: none;
}}
.map-overlay .tag {{
  pointer-events: auto;
  background: var(--panel); backdrop-filter: blur(10px);
  border: 1px solid var(--line); border-radius: 10px;
  padding: .45rem .65rem; font-size: .75rem; color: var(--muted);
  max-width: 260px;
}}
.map-overlay b {{ color: var(--text); }}
.side {{
  min-height: 0; overflow: auto;
  padding: .85rem;
  display: flex; flex-direction: column; gap: .75rem;
  background: linear-gradient(180deg, rgba(8,12,20,0.5), transparent);
}}
.panel {{
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: .9rem 1rem;
  backdrop-filter: blur(14px);
  box-shadow: 0 8px 32px rgba(0,0,0,.35);
}}
.panel h2 {{
  margin: 0 0 .65rem; font-size: .68rem; text-transform: uppercase;
  letter-spacing: .14em; color: var(--muted); font-weight: 700;
}}
/* DECISION HERO */
.decision-hero {{
  text-align: center; padding: 1.1rem .5rem 1rem;
  border-radius: 16px;
  border: 1px solid var(--line);
  background:
    radial-gradient(ellipse at 50% 0%, rgba(77,141,255,0.15), transparent 60%),
    var(--panel);
  position: relative; overflow: hidden;
}}
.decision-hero::before {{
  content: "";
  position: absolute; inset: -40%;
  background: conic-gradient(from 0deg, transparent, rgba(61,231,255,0.08), transparent 30%);
  animation: spin 12s linear infinite;
  pointer-events: none;
}}
@keyframes spin {{ to {{ transform: rotate(360deg); }} }}
.decision-hero > * {{ position: relative; z-index: 1; }}
.dec-label {{
  font-size: .7rem; letter-spacing: .2em; color: var(--muted); font-weight: 700;
}}
.dec-word {{
  font-size: clamp(2.6rem, 6vw, 3.6rem);
  font-weight: 900; letter-spacing: .08em;
  margin: .15rem 0 .25rem;
  text-shadow: 0 0 30px currentColor;
}}
.dec-word.GO {{ color: var(--go); filter: drop-shadow(var(--glow-go)); }}
.dec-word.HOLD {{ color: var(--hold); filter: drop-shadow(var(--glow-hold)); }}
.dec-word.ABSTAIN {{ color: var(--abstain); filter: drop-shadow(var(--glow-ab)); }}
.dec-conf {{
  font-size: 1.05rem; font-variant-numeric: tabular-nums;
}}
.dec-conf span {{ color: var(--cyan); font-weight: 800; }}
.ring {{
  width: 88px; height: 88px; margin: .75rem auto .2rem;
  border-radius: 50%;
  background: conic-gradient(var(--ring-color) calc(var(--pct) * 1%), rgba(255,255,255,0.08) 0);
  display: grid; place-items: center;
  box-shadow: 0 0 24px color-mix(in srgb, var(--ring-color) 40%, transparent);
}}
.ring-inner {{
  width: 68px; height: 68px; border-radius: 50%;
  background: var(--panel-solid);
  display: grid; place-items: center;
  font-weight: 800; font-size: .95rem; font-variant-numeric: tabular-nums;
}}
.radio-box {{
  margin-top: .75rem;
  font-family: var(--mono); font-size: .72rem; line-height: 1.4;
  color: #b8d4f0;
  background: rgba(0,0,0,.4);
  border-left: 3px solid var(--cyan);
  padding: .55rem .7rem; border-radius: 0 10px 10px 0;
  text-align: left;
}}
/* sources */
.src-row {{
  display: grid; grid-template-columns: 88px 1fr 42px; gap: .45rem;
  align-items: center; margin: .35rem 0; font-size: .78rem;
}}
.src-row .name {{ color: var(--muted); font-weight: 600; }}
.bar {{
  height: 8px; border-radius: 999px; background: rgba(255,255,255,0.06);
  overflow: hidden;
}}
.bar > i {{
  display: block; height: 100%; border-radius: 999px;
  background: linear-gradient(90deg, var(--blue), var(--cyan));
  box-shadow: 0 0 10px rgba(61,231,255,0.4);
  width: 0%; transition: width .8s cubic-bezier(.2,.8,.2,1);
}}
.src-row .pct {{ font-variant-numeric: tabular-nums; text-align: right; color: var(--cyan); font-weight: 700; }}
.src-row.off .bar > i {{ background: #334; box-shadow: none; }}
.src-row.off .name {{ opacity: .5; }}
/* metrics mini */
.kv {{
  display: grid; grid-template-columns: 1fr 1fr; gap: .5rem;
}}
.kv .cell {{
  background: rgba(0,0,0,.28); border-radius: 12px; padding: .55rem .65rem;
  border: 1px solid transparent;
}}
.kv .cell:hover {{ border-color: var(--line); }}
.kv .k {{ font-size: .65rem; color: var(--muted); text-transform: uppercase; letter-spacing: .08em; }}
.kv .v {{ font-size: 1.15rem; font-weight: 800; font-variant-numeric: tabular-nums; margin-top: .1rem; }}
.kv .v em {{ font-style: normal; color: var(--cyan); font-size: .75rem; font-weight: 600; }}
/* BOTTOM strip */
.bottom {{
  border-top: 1px solid var(--line);
  background: rgba(8,12,20,0.92);
  backdrop-filter: blur(12px);
  padding: .55rem .75rem;
  display: flex; gap: .55rem; overflow-x: auto;
  align-items: stretch;
}}
.pack-card {{
  min-width: 168px; flex: 0 0 auto;
  border: 1px solid var(--line); border-radius: 14px;
  padding: .55rem .7rem; cursor: pointer;
  background: rgba(14,22,36,0.9);
  transition: transform .15s, border-color .15s, box-shadow .15s;
}}
.pack-card:hover, .pack-card.active {{
  border-color: rgba(61,231,255,0.55);
  box-shadow: 0 0 20px rgba(61,231,255,0.15);
  transform: translateY(-2px);
}}
.pack-card .code {{ font-weight: 800; letter-spacing: .06em; font-size: .85rem; }}
.pack-card .ha {{ color: var(--hold); font-weight: 700; font-size: .9rem; font-variant-numeric: tabular-nums; }}
.pack-card .meta {{ color: var(--muted); font-size: .68rem; margin-top: .15rem; }}
.pill {{
  display: inline-block; font-size: .62rem; font-weight: 700;
  padding: .12rem .4rem; border-radius: 999px; margin-top: .25rem;
  border: 1px solid var(--line);
}}
.pill.go {{ color: var(--go); border-color: rgba(0,227,154,.35); }}
.pill.dnbr {{ color: #c4a0ff; border-color: rgba(180,120,255,.35); }}
.footer-note {{
  position: absolute; right: .75rem; bottom: 118px; z-index: 600;
  font-size: .62rem; color: var(--muted); max-width: 280px; text-align: right;
  pointer-events: none; opacity: .85;
}}
@media (max-width: 960px) {{
  .footer-note {{ display: none; }}
}}
.reasons {{
  font-size: .72rem; color: var(--muted); max-height: 72px; overflow: auto;
  margin: 0; padding-left: 1.1rem;
}}
.reasons li {{ margin: .15rem 0; }}
.btn-row {{ display: flex; gap: .4rem; flex-wrap: wrap; margin-top: .5rem; }}
.btn {{
  appearance: none; border: 1px solid var(--line); background: rgba(0,0,0,.35);
  color: var(--text); border-radius: 10px; padding: .4rem .65rem;
  font-size: .72rem; font-weight: 700; cursor: pointer; letter-spacing: .04em;
}}
.btn:hover {{ border-color: var(--cyan); color: var(--cyan); }}
.btn.primary {{
  background: linear-gradient(135deg, rgba(61,231,255,0.2), rgba(77,141,255,0.15));
  border-color: rgba(61,231,255,0.45);
}}
.scanline {{
  position: fixed; left: 0; right: 0; height: 2px; z-index: 9999; pointer-events: none;
  background: linear-gradient(90deg, transparent, rgba(61,231,255,0.35), transparent);
  animation: scan 5s linear infinite; opacity: .4;
}}
@keyframes scan {{
  0% {{ top: -2%; }}
  100% {{ top: 102%; }}
}}
</style>
</head>
<body>
<div class="bg-fx"></div>
<div class="scanline"></div>
<div class="app">
  <header class="topbar">
    <div class="brand">
      <div class="brand-mark"></div>
      <div>
        <h1>WFD COMMAND</h1>
        <div class="sub">WILDFIRE FRONT DYNAMICS · APOYO A LA DECISIÓN</div>
      </div>
    </div>
    <div class="top-meta">
      <span class="chip live" id="chip-live">● LIVE DEMO</span>
      <span class="chip" id="chip-utc">UTC —</span>
      <span class="chip ok" id="chip-rel">RELIABILITY —</span>
      <span class="chip" id="chip-git">git —</span>
    </div>
  </header>

  <div class="main">
    <div class="map-wrap">
      <div id="map"></div>
      <div class="map-overlay">
        <div class="tag"><b>Capa activa</b><br/><span id="map-layer-label">Open CEMS multi-día</span></div>
        <div class="tag"><b>Teclas</b><br/>1–4 packs · R radio · F fullscreen</div>
      </div>
      <div class="footer-note" id="disclaimer-float"></div>
    </div>

    <aside class="side">
      <div class="decision-hero" id="decision-hero">
        <div class="dec-label">DECISIÓN · FIRE DECISION CARD</div>
        <div class="dec-word" id="dec-word">—</div>
        <div class="ring" id="conf-ring" style="--pct:0;--ring-color:var(--cyan)">
          <div class="ring-inner" id="conf-inner">—</div>
        </div>
        <div class="dec-conf">confianza fenómeno <span id="conf-label">—</span></div>
        <div class="radio-box" id="radio-box">—</div>
        <div class="btn-row">
          <button class="btn primary" type="button" id="btn-copy-radio">COPIAR RADIO</button>
          <button class="btn" type="button" id="btn-cycle-pack">SIGUIENTE PACK</button>
          <button class="btn" type="button" id="btn-portal">PORTAL</button>
        </div>
      </div>

      <div class="panel">
        <h2>Fuentes fusionadas</h2>
        <div id="sources"></div>
      </div>

      <div class="panel">
        <h2>Ops · ML · Sistema</h2>
        <div class="kv" id="kv-metrics"></div>
      </div>

      <div class="panel">
        <h2>Motivos (audit)</h2>
        <ul class="reasons" id="reasons"></ul>
      </div>
    </aside>
  </div>

  <div class="bottom" id="packs"></div>
</div>

<script>
window.__WFD__ = {data_json};
</script>
<script>
(function () {{
  const D = window.__WFD__ || {{}};
  const card = D.decision_card || {{}};
  const packs = D.packs || [];
  let activeIdx = 0;
  let map, layerGroup;

  function $(id) {{ return document.getElementById(id); }}

  function tickUtc() {{
    const now = new Date();
    $("chip-utc").textContent = "UTC " + now.toISOString().slice(11, 19);
  }}
  setInterval(tickUtc, 1000);
  tickUtc();

  $("chip-git").textContent = "git " + (D.git || "?");
  $("chip-rel").textContent = D.reliability_ok ? "RELIABILITY PASS" : "RELIABILITY CHECK";
  $("chip-rel").className = "chip " + (D.reliability_ok ? "ok" : "warn");

  const dec = (card.decision || "ABSTAIN").toUpperCase();
  const conf = typeof card.confidence_pred === "number" ? card.confidence_pred : 0;
  $("dec-word").textContent = dec;
  $("dec-word").className = "dec-word " + dec;
  $("conf-label").textContent = (card.confidence_pred_label || "") + " · " + conf.toFixed(3);
  $("conf-inner").textContent = Math.round(conf * 100) + "%";
  const ring = $("conf-ring");
  ring.style.setProperty("--pct", String(Math.max(0, Math.min(100, conf * 100))));
  ring.style.setProperty("--ring-color",
    dec === "GO" ? "var(--go)" : dec === "HOLD" ? "var(--hold)" : "var(--abstain)");

  $("radio-box").textContent = D.radio || "—";
  const disc = (D.disclaimers || []).slice(0, 2).join(" · ");
  $("disclaimer-float").textContent = disc;

  // sources
  const srcBox = $("sources");
  srcBox.innerHTML = "";
  (card.sources || []).forEach((s) => {{
    const ok = !!s.available;
    const c = ok ? (Number(s.confidence) || 0) : 0;
    const row = document.createElement("div");
    row.className = "src-row" + (ok ? "" : " off");
    const id = (s.id || "").replace(/_/g, " ");
    row.innerHTML = `<span class="name">${{id}}</span>
      <div class="bar"><i style="width:${{Math.round(c*100)}}%"></i></div>
      <span class="pct">${{ok ? Math.round(c*100)+"%" : "off"}}</span>`;
    srcBox.appendChild(row);
  }});

  // metrics
  const ml = (D.ml && D.ml.metrics) || {{}};
  const ops = (D.ops && D.ops.representative_metrics) || {{}};
  const cells = [
    ["ROS m/min", ops.primary_ros_m_min != null ? Number(ops.primary_ros_m_min).toFixed(2) : "—", "ops"],
    ["Grade", ops.quality_grade || "—", "ops"],
    ["ML IoU", ml.test_iou != null ? Number(ml.test_iou).toFixed(4) : "—", "v34"],
    ["Δ vs copy", ml.improvement_vs_copy_iou != null ? "+" + Number(ml.improvement_vs_copy_iou).toFixed(4) : "—", ""],
    ["Packs open", String(packs.length), "CEMS"],
    ["API p95", D.api_p95_ms != null ? Number(D.api_p95_ms).toFixed(0) + " ms" : "—", ""],
    ["Plan DONE", String(D.plan_items_done ?? "—"), "items"],
    ["Policy", (card.audit && card.audit.policy_id) || card.policy_id || "demo", ""],
  ];
  $("kv-metrics").innerHTML = cells.map(([k,v,e]) =>
    `<div class="cell"><div class="k">${{k}}</div><div class="v">${{v}} ${{e?`<em>${{e}}</em>`:""}}</div></div>`
  ).join("");

  $("reasons").innerHTML = (card.reasons || []).slice(0, 10).map(r => `<li>${{r}}</li>`).join("")
    || "<li>sin motivos</li>";

  // map
  map = L.map("map", {{
    zoomControl: true,
    attributionControl: true,
  }}).setView([40.2, -3.7], 6);

  L.tileLayer("https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png", {{
    attribution: "&copy; OSM &copy; CARTO",
    maxZoom: 18,
  }}).addTo(map);

  layerGroup = L.layerGroup().addTo(map);

  const palette = ["#3de7ff", "#ffb020", "#ff6b4a", "#c4a0ff", "#00e39a"];

  function flyToPack(i) {{
    if (!packs.length) return;
    activeIdx = ((i % packs.length) + packs.length) % packs.length;
    const p = packs[activeIdx];
    layerGroup.clearLayers();
    document.querySelectorAll(".pack-card").forEach((el, j) => {{
      el.classList.toggle("active", j === activeIdx);
    }});
    $("map-layer-label").textContent = p.activation + " · " +
      (p.max_area_ha != null ? Math.round(p.max_area_ha) + " ha" : "—");
    if (p.geojson && p.geojson.features && p.geojson.features.length) {{
      const color = palette[activeIdx % palette.length];
      const layer = L.geoJSON(p.geojson, {{
        style: (feat) => {{
          const idx = (feat.properties && feat.properties.timeline_index) || 0;
          return {{
            color: color,
            weight: 2,
            fillColor: color,
            fillOpacity: 0.15 + Math.min(0.45, idx * 0.08),
          }};
        }},
        onEachFeature: (feat, lyr) => {{
          const pr = feat.properties || {{}};
          lyr.bindPopup(
            `<b>${{p.activation}}</b><br/>` +
            `área: ${{pr.area_ha != null ? Number(pr.area_ha).toFixed(0) : "—"}} ha<br/>` +
            `step: ${{pr.timeline_index ?? "—"}}`
          );
        }},
      }}).addTo(layerGroup);
      try {{
        map.fitBounds(layer.getBounds(), {{ padding: [36, 36], maxZoom: 12 }});
      }} catch (e) {{
        if (p.lat != null) map.setView([p.lat, p.lon], 10);
      }}
    }} else if (p.lat != null) {{
      L.circleMarker([p.lat, p.lon], {{
        radius: 10, color: "#3de7ff", fillColor: "#3de7ff", fillOpacity: 0.6,
      }}).addTo(layerGroup).bindPopup(p.activation);
      map.setView([p.lat, p.lon], 10);
    }}
  }}

  // pack cards
  const packBox = $("packs");
  packs.forEach((p, i) => {{
    const el = document.createElement("div");
    el.className = "pack-card";
    el.innerHTML = `
      <div class="code">${{p.activation}}</div>
      <div class="ha">${{p.max_area_ha != null ? Math.round(p.max_area_ha).toLocaleString("es-ES") + " ha" : "—"}}</div>
      <div class="meta">${{p.n_timeline_steps || "—"}} pasos timeline</div>
      <span class="pill go">${{p.O2_cems_delineation || "CEMS"}}</span>
      ${{p.dnbr_status === "GO" ? '<span class="pill dnbr">dNBR</span>' : ""}}
    `;
    el.addEventListener("click", () => flyToPack(i));
    packBox.appendChild(el);
  }});
  if (packs.length) flyToPack(0);
  else {{
    L.marker([39.0, -3.0]).addTo(map).bindPopup("Sin packs open — ejecuta build_open_if_pack");
  }}

  $("btn-cycle-pack").addEventListener("click", () => flyToPack(activeIdx + 1));
  $("btn-copy-radio").addEventListener("click", async () => {{
    try {{
      await navigator.clipboard.writeText(D.radio || "");
      $("btn-copy-radio").textContent = "COPIADO ✓";
      setTimeout(() => {{ $("btn-copy-radio").textContent = "COPIAR RADIO"; }}, 1500);
    }} catch (e) {{
      prompt("Copia el radio:", D.radio || "");
    }}
  }});
  $("btn-portal").addEventListener("click", () => {{
    window.open("../PORTAL.html", "_blank");
  }});

  window.addEventListener("keydown", (ev) => {{
    if (ev.key >= "1" && ev.key <= "9") {{
      flyToPack(Number(ev.key) - 1);
    }} else if (ev.key === "r" || ev.key === "R") {{
      $("btn-copy-radio").click();
    }} else if (ev.key === "f" || ev.key === "F") {{
      if (!document.fullscreenElement) document.documentElement.requestFullscreen?.();
      else document.exitFullscreen?.();
    }}
  }});

  // stagger bar animation
  requestAnimationFrame(() => {{
    document.querySelectorAll(".bar > i").forEach((el) => {{
      const w = el.style.width;
      el.style.width = "0%";
      requestAnimationFrame(() => {{ el.style.width = w; }});
    }});
  }});
}})();
</script>
</body>
</html>
"""


def main() -> int:
    data = collect_data()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    data_path = OUT_DIR / "app_data.json"
    data_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    # compact JSON for embed
    embedded = json.dumps(data, separators=(",", ":"), default=str)
    html = html_template(embedded)
    out = OUT_DIR / "index.html"
    out.write_text(html, encoding="utf-8")
    # small README
    (OUT_DIR / "README.md").write_text(
        """# WFD COMMAND — App de sala de mando

```powershell
cd C:\\Users\\Mariano\\Documents\\ALONSOO\\WildfireFrontDynamics
$env:PYTHONPATH = "."
python scripts\\build_commander_app.py
start docs\\commander\\index.html
```

O: `python scripts/show_all.py` (abre esta app).

UI táctica: Decision Card GO/HOLD/ABSTAIN, mapa Leaflet packs CEMS, radio-bridge, fuentes, métricas ops/ML.
No es orden táctica de despacho.
""",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "ok": True,
                "app": str(out),
                "data": str(data_path),
                "decision": (data.get("decision_card") or {}).get("decision"),
                "n_packs": len(data.get("packs") or []),
                "bytes_html": out.stat().st_size,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
