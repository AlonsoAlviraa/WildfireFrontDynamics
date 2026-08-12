"""HTML renderer — industrial C2 / EOC ops console (Stitch WFD Industrial C2).

Industry refs: EOC density · Esri map-first · SOC chips · dual-mode (Fácil/Pro).
Stress UX (nuclear/hospital EMNS research): priority acts first, ≥48px taps,
progressive disclosure — full power in Pro, never feature-cut.
Stitch: projects/6685398829230236101 · docs/design/EMERGENCY_UX_INDUSTRY.md

Maintainability (PR03): CSS / shell / JS live in ``_css()`` · ``_shell()`` · ``_js()``.
"""

from __future__ import annotations

import json
from typing import Any


def _esc(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _css() -> str:
    """Industrial C2 tokens + shell layout (markers: #0B1220, primary-acts, --tap)."""
    return """
:root {
  --bg:#0B1220; --panel:#111827; --panel2:#0f1623; --line:#1F2937; --line2:#374151;
  --text:#F9FAFB; --muted:#9CA3AF; --faint:#6B7280;
  --cyan:#0EA5E9; --local:#38BDF8; --firms:#FB7185;
  --go:#22C55E; --hold:#F59E0B; --abstain:#EF4444;
  --top:48px; --rail:min(380px, 34vw); --r:4px; --tap:48px;
  --font:"IBM Plex Sans",system-ui,-apple-system,sans-serif;
  --mono:ui-monospace,"IBM Plex Mono",Consolas,monospace;
}
*,*::before,*::after{box-sizing:border-box}
html,body{height:100%;margin:0;overflow:hidden;background:var(--bg);color:var(--text);font:13px/1.3 var(--font)}
button,select,input{font:inherit;color:inherit}
body.mode-simple .adv{display:none!important}
body.mode-advanced .simp{display:none!important}

/* ── Shell ── */
.shell{
  height:100dvh;height:100vh;
  display:grid;grid-template-rows:var(--top) minmax(0,1fr);
}
.top{
  display:flex;align-items:center;gap:12px;padding:0 12px;
  background:var(--bg);border-bottom:1px solid var(--line);min-width:0;z-index:20;
}
.brand{display:flex;align-items:center;gap:8px;flex:0 0 auto}
.mark{
  width:26px;height:26px;border-radius:var(--r);background:var(--cyan);
  color:#041018;font-weight:700;font-size:12px;display:grid;place-items:center;
}
.brand b{font-size:14px;font-weight:700;letter-spacing:.02em}
.brand em{font-style:normal;font-size:10px;font-weight:600;color:var(--muted);letter-spacing:.08em;margin-left:2px}
.vdiv{width:1px;height:20px;background:var(--line);flex:0 0 auto}
.top-mid{display:flex;align-items:center;gap:8px;flex:1 1 auto;min-width:0}
.top select{
  max-width:min(260px,40vw);min-height:32px;background:transparent;border:0;
  color:var(--text);font-weight:500;padding:0 4px;outline:none;cursor:pointer;
}
.top select option{background:var(--panel)}
.chips{display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.chip{
  display:inline-flex;align-items:center;gap:6px;
  padding:3px 8px;border:1px solid var(--line);border-radius:var(--r);
  background:var(--panel);font:10px/1 var(--mono);letter-spacing:.06em;
  text-transform:uppercase;color:var(--muted);white-space:nowrap;
}
.chip i{width:6px;height:6px;border-radius:50%;background:var(--faint);flex:0 0 auto}
.chip.ok i{background:var(--go)}
.chip.warn i{background:var(--hold)}
.chip.err i{background:var(--abstain)}
.chip.live i{background:var(--local)}
.top-right{display:flex;align-items:center;gap:8px;flex:0 0 auto;margin-left:auto;flex-wrap:wrap;justify-content:flex-end}
.seg{
  display:inline-flex;background:var(--panel);border:1px solid var(--line);
  border-radius:var(--r);padding:2px;
}
.seg button{
  appearance:none;border:0;background:transparent;color:var(--muted);
  min-height:26px;padding:0 10px;border-radius:2px;cursor:pointer;
  font-size:10px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;
}
.seg button.on{background:var(--line2);color:var(--text)}
.role-seg button{padding:0 7px;font-size:9px}
.icon-btn{
  appearance:none;border:0;background:transparent;color:var(--muted);
  width:32px;height:32px;cursor:pointer;font-size:16px;border-radius:var(--r);
}
.icon-btn:hover{color:var(--text);background:var(--panel)}

/* ── Main ── */
.main{
  min-height:0;display:grid;
  grid-template-columns:minmax(0,1fr) var(--rail);
}
@media (max-width:900px){
  .main{grid-template-columns:1fr;grid-template-rows:minmax(45vh,1fr) minmax(42vh,1fr)}
  :root{--rail:auto}
  .chips{display:none}
  .role-seg{display:none}
}

/* ── Map ── */
.map-wrap{position:relative;min-width:0;min-height:0;background:#050914}
#map{position:absolute;inset:0}
.hud{
  position:absolute;z-index:500;top:10px;left:10px;
  display:flex;flex-wrap:wrap;gap:6px;pointer-events:none;
}
.hud .chip{pointer-events:auto;backdrop-filter:blur(8px);background:#111827cc}
.legend{
  position:absolute;z-index:500;left:12px;bottom:12px;
  background:#111827cc;border:1px solid var(--line);border-radius:var(--r);
  padding:8px 10px;backdrop-filter:blur(8px);font:10px/1.4 var(--mono);
  letter-spacing:.05em;text-transform:uppercase;color:var(--muted);
}
.legend .row{display:flex;align-items:center;gap:8px;margin:3px 0}
.sw-line{width:14px;height:2px;background:var(--local)}
.sw-pt{width:8px;height:8px;border-radius:2px;background:var(--firms)}
.fab{
  position:absolute;z-index:500;right:12px;bottom:12px;
  width:44px;height:44px;border-radius:var(--r);
  border:1px solid var(--line);background:var(--panel);color:var(--text);
  cursor:pointer;font-size:18px;box-shadow:0 8px 24px #0008;
  display:grid;place-items:center;
}
.fab:hover{border-color:var(--cyan);color:var(--cyan)}
.leaflet-control-zoom a{
  background:var(--panel)!important;color:var(--text)!important;border-color:var(--line)!important;
}
.leaflet-control-attribution{
  background:#0B1220cc!important;color:var(--faint)!important;font-size:9px!important;
}

/* ── Rail ── */
.rail{
  min-width:0;min-height:0;overflow:hidden;
  display:grid;grid-template-rows:auto auto auto auto auto auto minmax(0,1fr);
  border-left:1px solid var(--line);background:var(--panel2);
}
@media (max-width:900px){.rail{border-left:0;border-top:1px solid var(--line)}}

.decision{
  padding:14px 14px 12px;text-align:center;border-bottom:1px solid var(--line);
  background:radial-gradient(80% 100% at 50% 0%, #1e293b55, transparent 70%);
}
.decision.go{--d:var(--go)}
.decision.hold,.decision.brief{--d:var(--hold)}
.decision.abstain{--d:var(--d,var(--abstain));--d:var(--abstain)}
.decision .word{
  font-size:clamp(2rem,4.5vw,2.75rem);font-weight:700;letter-spacing:.06em;
  color:var(--d,#94a3b8);line-height:1;margin:0;
}
.decision .one{margin:4px 0 0;font-size:12px;color:var(--muted)}
.decision .pct{margin-top:4px;font-size:12px;font-weight:600;color:var(--cyan);font-variant-numeric:tabular-nums}
/* Uncertainty bar (UI only): existing conf bands — never invent scores; IoU ≠ ROS */
.unc-bar{margin-top:8px}
.unc-bar .unc-track{
  height:8px;border-radius:999px;background:var(--line);overflow:hidden;
  border:1px solid var(--line2);
}
.unc-bar .unc-fill{
  height:100%;width:0;background:linear-gradient(90deg,var(--abstain),var(--hold),var(--go));
  transition:width .2s ease;
}
.unc-bar .unc-meta{
  display:flex;justify-content:space-between;gap:8px;margin-top:4px;
  font:10px/1.2 var(--mono);color:var(--muted);letter-spacing:.02em;
}
.unc-bar .unc-note{color:var(--faint);font-size:10px;margin-top:4px;line-height:1.25}
.unc-bar .unc-note b{color:var(--hold);font-weight:600}

.kpis{
  display:grid;grid-template-columns:1fr 1fr;gap:1px;background:var(--line);
  border-bottom:1px solid var(--line);
}
.kpi{background:var(--panel);padding:10px 12px;min-width:0}
.kpi .k{
  font-size:10px;font-weight:600;letter-spacing:.07em;text-transform:uppercase;color:var(--faint);
}
.kpi .v{
  margin-top:2px;font-size:16px;font-weight:600;font-variant-numeric:tabular-nums;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
}

.next{
  margin:10px 12px;padding:8px 10px;border-left:3px solid var(--cyan);
  background:var(--panel);border-radius:0 var(--r) var(--r) 0;
  font-size:12px;color:var(--muted);
}
.next b{
  display:block;font-size:10px;letter-spacing:.07em;text-transform:uppercase;
  color:var(--text);margin-bottom:2px;font-weight:600;
}

.last-act{
  margin:0 12px 8px;padding:8px 10px;border:1px solid var(--line);
  border-radius:var(--r);background:var(--panel);font-size:11px;color:var(--muted);
}
.last-act b{
  display:block;font-size:10px;letter-spacing:.07em;text-transform:uppercase;
  color:var(--cyan);margin-bottom:2px;font-weight:600;
}
.last-act .cmd{
  font-family:var(--mono);font-size:10px;color:var(--text);
  word-break:break-all;margin:4px 0 2px;
}
.last-act .meta{font-size:10px;color:var(--faint)}
.last-act .paths{font-family:var(--mono);font-size:9px;color:var(--local);margin-top:4px;word-break:break-all}
.last-act .preview{font-size:10px;color:var(--muted);margin-top:4px;max-height:4.5em;overflow:hidden;white-space:pre-wrap}
.last-act .row-btns{display:flex;gap:4px;margin-top:6px;flex-wrap:wrap}
.last-act .row-btns .btn{min-height:28px;font-size:10px;padding:0 8px}
/* A4 decision-log UI (display only; ACK backend is Agent B) */
.decision-log{
  margin:8px 12px;padding:8px 10px;border:1px solid var(--line);border-radius:var(--r);
  background:var(--panel2);font-size:11px;
}
.decision-log b{display:block;font-size:10px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin-bottom:6px}
.decision-log .dlog-id{font-family:var(--mono);font-size:10px;color:var(--local);word-break:break-all}
.decision-log .dlog-meta{font-size:10px;color:var(--faint);margin-top:4px;line-height:1.35}
.decision-log .dlog-ack{
  margin-top:6px;display:flex;gap:6px;flex-wrap:wrap;align-items:center;
}
.decision-log .dlog-ack .btn{min-height:28px;font-size:10px;padding:0 8px}
.decision-log .dlog-note{font-size:9px;color:var(--faint);margin-top:4px}
/* A5 split conf: ML conf ≠ ROS conf */
.split-conf{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:6px}
.split-conf .sc-box{
  border:1px solid var(--line);border-radius:var(--r);padding:6px 8px;background:var(--panel);
}
.split-conf .sc-box .sc-k{font-size:9px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.split-conf .sc-box .sc-v{font-size:12px;font-weight:600;margin-top:2px;font-variant-numeric:tabular-nums}
.split-conf .sc-box .sc-h{font-size:9px;color:var(--faint);margin-top:2px;line-height:1.25}
.split-conf .sc-box.ros .sc-v{color:var(--hold)}
.split-conf .sc-box.ml .sc-v{color:var(--cyan)}
/* A6 H1 eng rehearsal · A7 SR ladder */
.h1-rehearsal,.sr-ladder{
  margin:8px 12px;padding:8px 10px;border:1px solid var(--line);border-radius:var(--r);
  background:var(--panel2);font-size:11px;
}
.h1-rehearsal b,.sr-ladder b{
  display:block;font-size:10px;letter-spacing:.06em;text-transform:uppercase;
  color:var(--muted);margin-bottom:6px;
}
.h1-rehearsal .h1-flag{
  display:inline-flex;align-items:center;gap:6px;padding:3px 8px;border-radius:var(--r);
  border:1px solid var(--hold);color:var(--hold);font:10px/1 var(--mono);margin-bottom:6px;
}
.h1-rehearsal ol{margin:4px 0 0;padding-left:1.15rem;color:var(--muted);font-size:10px}
.h1-rehearsal li{margin:3px 0}
.h1-rehearsal .h1-cmd{font-family:var(--mono);font-size:9px;color:var(--local);word-break:break-all}
.h1-rehearsal .h1-note{font-size:9px;color:var(--faint);margin-top:6px;line-height:1.3}
.sr-ladder .sr-levels{display:grid;gap:4px;margin-top:4px}
.sr-ladder .sr-lv{
  display:grid;grid-template-columns:36px 1fr;gap:6px;padding:5px 6px;
  border:1px solid var(--line);border-radius:var(--r);background:var(--panel);
}
.sr-ladder .sr-lv.on{border-color:var(--cyan);box-shadow:inset 0 0 0 1px var(--cyan)}
.sr-ladder .sr-id{font:10px/1.2 var(--mono);color:var(--cyan);font-weight:700}
.sr-ladder .sr-lab{font-size:11px;font-weight:600;color:var(--text)}
.sr-ladder .sr-why{font-size:9px;color:var(--faint);margin-top:2px;line-height:1.25}
.sr-ladder .sr-claims{font-size:9px;color:var(--hold);margin-top:6px;line-height:1.3}

/* Primary 3 acts — industry stress pattern: priority first, full power later */
.primary-acts{
  display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;padding:0 12px 10px;
}
.pact{
  appearance:none;border:1px solid var(--line);background:var(--panel);
  color:var(--text);border-radius:var(--r);min-height:var(--tap);
  padding:6px 4px;cursor:pointer;display:flex;flex-direction:column;
  align-items:center;justify-content:center;gap:2px;text-align:center;
}
.pact:hover,.pact:focus-visible{border-color:var(--cyan);color:var(--cyan);outline:none}
.pact.main{background:#0c4a6e;border-color:#0369a1;color:#e0f2fe}
.pact.main:hover{filter:brightness(1.1);color:#fff}
.pact .ico{font-size:16px;line-height:1}
.pact .lbl{font-size:11px;font-weight:700;letter-spacing:.02em}
.pact .sub{font-size:9px;color:var(--faint);text-transform:uppercase;letter-spacing:.05em}
.pact.main .sub{color:#7dd3fc}
.actions-row{
  display:grid;grid-template-columns:1fr 1fr;gap:8px;padding:0 12px 10px;
}
.actions-row.triple{grid-template-columns:1fr 1fr 1fr}
.btn{
  appearance:none;border:1px solid var(--line);background:var(--panel);
  color:var(--text);border-radius:var(--r);min-height:var(--tap);
  padding:0 10px;cursor:pointer;font-size:12px;font-weight:600;
}
.btn:hover,.btn:focus-visible{border-color:var(--cyan);color:var(--cyan);outline:none}
.btn.primary{background:#0c4a6e;border-color:#0369a1;color:#e0f2fe}
.btn.primary:hover{filter:brightness(1.1);color:#fff}
.btn.block{width:100%}
.btn.sm{min-height:36px;font-size:11px}

/* Tabs + pane */
.tabs{
  display:flex;gap:0;border-bottom:1px solid var(--line);overflow-x:auto;
  scrollbar-width:none;padding:0 4px;
}
.tabs::-webkit-scrollbar{display:none}
.tab{
  appearance:none;border:0;background:transparent;color:var(--muted);
  min-height:34px;padding:0 12px;cursor:pointer;font-size:11px;font-weight:600;
  letter-spacing:.04em;text-transform:uppercase;white-space:nowrap;flex:0 0 auto;
  border-bottom:2px solid transparent;margin-bottom:-1px;
}
.tab.on{color:var(--cyan);border-bottom-color:var(--cyan)}
.pane-host{min-height:0;overflow:auto;overflow-y:auto;padding:10px 12px 18px;scroll-padding-bottom:24px}
.pane{display:none}
.pane.on{display:block}

.grid2{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.metric{
  background:var(--panel);border:1px solid var(--line);border-radius:var(--r);padding:8px 10px;
}
.metric .k{font-size:10px;letter-spacing:.06em;text-transform:uppercase;color:var(--faint);font-weight:600}
.metric .v{font-size:14px;font-weight:600;margin-top:2px;font-variant-numeric:tabular-nums}

.filters{display:flex;gap:4px;overflow-x:auto;margin-bottom:8px;scrollbar-width:none}
.filters::-webkit-scrollbar{display:none}
.filters button{
  appearance:none;border:1px solid var(--line);background:var(--panel);color:var(--muted);
  border-radius:var(--r);min-height:28px;padding:0 8px;cursor:pointer;
  font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.04em;white-space:nowrap;
}
.filters button.on{border-color:var(--cyan);color:var(--cyan)}

.act{border:1px solid var(--line);border-radius:var(--r);background:var(--panel);margin-bottom:4px}
.act summary{
  list-style:none;cursor:pointer;padding:8px 10px;display:flex;align-items:center;
  min-height:var(--tap);font-weight:600;font-size:12px;gap:8px;
}
.act summary::-webkit-details-marker{display:none}
.act summary::after{content:"›";margin-left:auto;color:var(--faint)}
.act[open] summary::after{transform:rotate(90deg)}
.act .body{padding:0 10px 10px;font-size:11px;color:var(--muted)}
.act .body p{margin:0 0 4px}
.act .cmd{
  font-family:var(--mono);font-size:10px;color:var(--cyan);
  background:#060a12;border:1px solid var(--line);border-radius:var(--r);
  padding:6px 8px;margin:6px 0;word-break:break-all;
}

.fcard{
  display:flex;align-items:center;gap:8px;padding:8px 10px;margin-bottom:4px;
  background:var(--panel);border:1px solid transparent;border-radius:var(--r);cursor:pointer;
}
.fcard.on,.fcard:hover{border-color:var(--cyan)}
.fcard .id{font-weight:600;font-size:12px;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.fcard .badge{font-size:10px;color:var(--faint);font-family:var(--mono)}

.gitem{padding:6px 0;border-bottom:1px solid var(--line)}
.gitem b{display:block;color:var(--cyan);font-size:12px}
.gitem span{display:block;color:var(--muted);font-size:11px;margin-top:2px}

.step{display:grid;grid-template-columns:24px 1fr;gap:8px;margin-bottom:8px}
.step .n{
  width:24px;height:24px;border-radius:50%;display:grid;place-items:center;
  border:1px solid var(--line);background:var(--panel);color:var(--cyan);
  font-size:11px;font-weight:700;
}
.step b{font-size:12px}
.step p{margin:2px 0 0;font-size:11px;color:var(--muted)}

.empty{color:var(--muted);font-size:12px;padding:6px 0}
.src{
  display:flex;justify-content:space-between;gap:8px;padding:5px 0;
  border-bottom:1px solid var(--line);font-size:11px;color:var(--muted);
}
.src span:last-child{color:var(--cyan);font-variant-numeric:tabular-nums}

.toast{
  position:fixed;z-index:9999;left:50%;bottom:16px;transform:translateX(-50%) translateY(8px);
  background:#E0F2FE;color:#0C4A6E;font-weight:600;font-size:12px;
  padding:8px 14px;border-radius:999px;opacity:0;pointer-events:none;
  transition:opacity .12s,transform .12s;box-shadow:0 8px 24px #0008;max-width:90vw;
}
.toast.show{opacity:1;transform:translateX(-50%) translateY(0)}

.modal-bg{
  position:fixed;inset:0;z-index:8000;background:#000a;display:none;place-items:center;padding:16px;
}
.modal-bg.on{display:grid}
.modal{
  width:min(400px,100%);background:var(--panel);border:1px solid var(--line);
  border-radius:8px;padding:16px;box-shadow:0 20px 50px #000a;
}
.modal h3{margin:0 0 8px;font-size:14px}
.modal ol{margin:0 0 12px;padding-left:1.15rem;color:var(--muted);font-size:12px}
.modal li{margin:4px 0}
#role-hint{font-size:10px;color:var(--faint);max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
""".strip()


def _shell() -> str:
    """Static HTML shell (markers: mode-toggle, primary-acts, last-act, role-seg)."""
    return """
<div class="shell">
  <header class="top">
    <div class="brand">
      <div class="mark">W</div>
      <b>WFD</b><em>OPS</em>
    </div>
    <div class="vdiv"></div>
    <div class="top-mid">
      <select id="fire-select" aria-label="Incidente"></select>
      <div class="chips" id="top-chips"></div>
    </div>
    <div class="top-right">
      <div class="seg role-seg" id="role-seg" role="group" aria-label="Rol playbook">
        <button type="button" data-role="operator" class="on">Ops</button>
        <button type="button" data-role="field">Campo</button>
        <button type="button" data-role="lab">Lab</button>
        <button type="button" data-role="decision">Decisión</button>
      </div>
      <span id="role-hint" class="simp" title="Rol actual"></span>
      <div class="seg mode-toggle" id="mode-toggle" role="group" aria-label="Modo Fácil o Pro">
        <button type="button" id="btn-mode-simple" class="on">Fácil</button>
        <button type="button" id="btn-mode-advanced">Pro</button>
      </div>
      <button type="button" class="icon-btn" id="btn-help" title="Ayuda" aria-label="Ayuda">?</button>
    </div>
  </header>

  <div class="main">
    <section class="map-wrap" aria-label="Mapa">
      <div id="map"></div>
      <div class="hud">
        <div class="chip live"><i></i><span id="map-layer-n">—</span></div>
        <div class="chip" id="map-conn-chip"><i></i><span id="map-conn">—</span></div>
      </div>
      <div class="legend">
        <div class="row"><span class="sw-line"></span>Frente local</div>
        <div class="row"><span class="sw-pt"></span>FIRMS NRT ≠ perímetro</div>
      </div>
      <button type="button" class="fab" id="btn-fit" title="Centrar mapa" aria-label="Centrar">◎</button>
    </section>

    <aside class="rail" aria-label="Panel operativo">
      <div class="decision brief" id="hero">
        <div class="word" id="hero-word">—</div>
        <p class="one" id="hero-plain"></p>
        <div class="pct" id="hero-conf"></div>
        <div class="unc-bar" id="uncertainty-bar" data-marker="uncertainty-bar" aria-label="Banda de incertidumbre (no es ROS)">
          <div class="unc-track" role="presentation"><div class="unc-fill" id="unc-fill"></div></div>
          <div class="unc-meta">
            <span id="unc-label">Conf. predicción</span>
            <span id="unc-band">—</span>
          </div>
          <div class="unc-note" id="unc-note" data-marker="uncertainty-no-ros"><b>no es ROS</b> · IoU ≠ ROS · banda de calidad existente, sin inventar scores</div>
        </div>
      </div>

      <div class="kpis" id="brief-kv"></div>

      <div class="next" id="next-box"></div>

      <div class="last-act" id="last-act" aria-live="polite">
        <b>Último acto</b>
        <div class="cmd" id="last-act-cmd">—</div>
        <div class="meta" id="last-act-meta">Copie Estado / Decidir / Acta (sin shell en browser).</div>
        <div class="paths" id="last-act-paths" hidden></div>
        <div class="preview" id="last-act-preview" hidden></div>
        <div class="row-btns" id="last-act-btns" hidden>
          <button type="button" class="btn sm" id="btn-copy-act-path">Copiar path</button>
          <button type="button" class="btn sm adv" id="btn-live-replay" title="Replay pack third-party (consistencia forense)">Replay pack</button>
        </div>
      </div>

      <div class="decision-log" id="decision-log" data-marker="decision-log" aria-label="Decision log">
        <b>Decision log</b>
        <div class="dlog-id" id="dlog-id">id: — (stub UI · backend B opcional)</div>
        <div class="dlog-meta" id="dlog-meta">Última decisión mostrada aquí. ACK es superficie UI; no inventa backend si B no shippea.</div>
        <div class="dlog-ack">
          <button type="button" class="btn sm" id="btn-dlog-ack" title="ACK local (UI only)">ACK UI</button>
          <span class="dlog-meta" id="dlog-ack-state">ack: pending</span>
        </div>
        <div class="dlog-note">fusion OFF · no GO_Q invent · ACK local ≠ acta H1</div>
      </div>

      <div class="split-conf" id="split-conf" data-marker="split-conf" aria-label="Confianza ML vs ROS">
        <div class="sc-box ml">
          <div class="sc-k">Conf. ML / predicción</div>
          <div class="sc-v" id="sc-ml">—</div>
          <div class="sc-h">calidad de card · <b>no es ROS</b></div>
        </div>
        <div class="sc-box ros">
          <div class="sc-k">Conf. ROS / ops</div>
          <div class="sc-v" id="sc-ros">—</div>
          <div class="sc-h">métrica ops si existe · IoU ≠ ROS</div>
        </div>
      </div>

      <div class="h1-rehearsal" id="h1-rehearsal" data-marker="h1-rehearsal" aria-label="Ensayo H1 eng">
        <b>Ensayo H1 eng (12 min)</b>
        <div class="h1-flag" id="h1-goq-flag">go_q_met=false · no es demo tercero</div>
        <ol id="h1-steps"></ol>
        <div class="h1-cmd" id="h1-serve-cmd">—</div>
        <div class="h1-note" id="h1-note">fusion OFF · eng dry-run · acta H1 es humana</div>
      </div>

      <div class="sr-ladder" id="sr-ladder" data-marker="sr-ladder" aria-label="Escala SR">
        <b>Escala SR (soporte / recomendación)</b>
        <div class="sr-levels" id="sr-levels"></div>
        <div class="sr-claims" id="sr-claims">Claims Guardian: no field GO · no fusion ON · no GO_Q invent</div>
      </div>

      <!-- 3 actos prioritarios (Everbridge/InformaCast pattern: critical path first) -->
      <div class="primary-acts" role="group" aria-label="Actos prioritarios">
        <button type="button" class="pact" id="btn-act-status" title="Estado del outbox">
          <span class="ico">▣</span><span class="lbl">Estado</span><span class="sub">outbox</span>
        </button>
        <button type="button" class="pact main" id="btn-act-decide" title="Decision Card field_ops">
          <span class="ico">◆</span><span class="lbl">Decidir</span><span class="sub">GO/HOLD</span>
        </button>
        <button type="button" class="pact" id="btn-act-acta" title="Exportar acta forense">
          <span class="ico">▤</span><span class="lbl">Acta</span><span class="sub">auditoría</span>
        </button>
      </div>
      <div class="actions-row" id="actions-row">
        <button type="button" class="btn primary" id="btn-copy-rebuild">Abrir consola</button>
        <button type="button" class="btn" id="btn-copy-map">Solo mapa</button>
        <button type="button" class="btn adv" id="btn-bridge-refresh" style="display:none" title="Refrescar Decision Card vía bridge local">Refrescar card</button>
      </div>

      <div style="display:grid;grid-template-rows:auto minmax(0,1fr);min-height:0;border-top:1px solid var(--line)">
        <div class="tabs" id="main-tabs" role="tablist">
          <button type="button" class="tab on" data-tab="brief">Overview</button>
          <button type="button" class="tab" data-tab="decision">Decisión</button>
          <button type="button" class="tab" data-tab="actions">Acciones</button>
          <button type="button" class="tab" data-tab="newfire">Nuevo</button>
          <button type="button" class="tab" data-tab="glossary">Términos</button>
          <button type="button" class="tab" data-tab="fires">Lista</button>
        </div>
        <div class="pane-host">
          <div class="pane on" id="tab-brief">
            <div class="grid2" id="ops-kv"></div>
            <div class="chips" id="rails" style="margin-top:10px"></div>
            <div class="adv" style="margin-top:10px">
              <button type="button" class="btn sm block" id="btn-copy">Copiar next cmd</button>
              <ol id="seq" style="padding-left:1.1rem;margin:8px 0 0;color:var(--muted);font-size:11px"></ol>
            </div>
          </div>
          <div class="pane" id="tab-decision">
            <div id="decision-body" class="empty">Sin tarjeta</div>
          </div>
          <div class="pane" id="tab-actions">
            <div class="filters" id="actions-filters"></div>
            <div id="actions-list"></div>
          </div>
          <div class="pane" id="tab-newfire">
            <div id="intake-steps"></div>
          </div>
          <div class="pane" id="tab-glossary">
            <div id="glossary-list"></div>
          </div>
          <div class="pane" id="tab-fires">
            <div id="fire-list"></div>
          </div>
        </div>
      </div>
    </aside>
  </div>
</div>

<div class="modal-bg" id="help-modal">
  <div class="modal" role="dialog">
    <h3>WFD OPS</h3>
    <ol>
      <li>Palabra grande = lectura del sistema (no es orden de extinción).</li>
      <li><b>Estado · Decidir · Acta</b> — tres actos prioritarios (siempre visibles).</li>
      <li>Selector de incidente → empaquetados cambian mapa/decisión en cliente; si no, <b>Abrir consola</b>.</li>
      <li>Rol (Ops/Campo/Lab/Decisión) actualiza hints; Pro copia rebuild con <code>--role</code>.</li>
      <li><b>Último acto</b> con <code>--serve</code> muestra resultado live; sin serve, comando copiado.</li>
    </ol>
    <button type="button" class="btn primary block" id="btn-help-close">Cerrar</button>
  </div>
</div>
<div class="toast" id="toast" role="status" aria-live="polite"></div>
""".strip()


def _js() -> str:
    """Client logic: dual-mode, primary acts, role switch, pack switch, optional bridge."""
    return r"""
const brief = P.brief || {};
const mapP0 = P.map || {};
let mapP = mapP0;
let card = P.decision_card || null;
let ops = P.ops_metrics || null;
let hero = P.hero || {};
const rails = P.rails || {};
const h1Eng = P.h1_eng_rehearsal || {};
const srLadder = P.sr_ladder || {};
const decisionLog = P.decision_log || {};
let uncertaintyBar = P.uncertainty_bar || {};
const fires = P.fires || [];
const actions = P.product_actions || [];
const intake = P.new_fire_intake || [];
const rebuild = P.rebuild || {};
const plain = P.plain_language || {};
const glossary = P.glossary || plain.glossary || [];
const roleHints = P.role_hints || {};
const pack = P.pack || null;
const bridge = P.bridge_decide || {};
const liveOps = P.live_ops || {};
// Live Ops default same-origin paths (payload may override):
// /live/v1/status · /live/v1/decide · /live/v1/export-acta · /live/v1/replay-third-party
const outboxSnap = P.outbox_last_run || null;

const SHORT = { GO:'Propone orientación', HOLD:'Espera / revisa', ABSTAIN:'Se calla a propósito', BRIEF:'Sin tarjeta local' };
let uiMode = P.ui_mode === 'advanced' ? 'advanced' : 'simple';
let activeGroup = 'Todos';
let currentRole = P.role || 'operator';
let lastAct = Object.assign({ act:null, cmd:null, ts:null, hint:null }, P.last_act || {});
let mapLayers = [];
let bounds = [];

function toast(msg) {
  const el = document.getElementById('toast');
  el.textContent = msg || 'OK';
  el.classList.add('show');
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.remove('show'), 1500);
}
function copyText(t, ok, actMeta) {
  t = (t || '').trim();
  if (!t) { toast('Nada que copiar'); return; }
  const done = () => {
    toast(ok || 'Copiado');
    if (actMeta) recordAct(actMeta.act || ok || 'acto', t, actMeta.hint);
  };
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(t).then(done).catch(() => fb(t, done));
  } else fb(t, done);
}
function fb(t, done) {
  try {
    const ta = document.createElement('textarea');
    ta.value = t; document.body.appendChild(ta); ta.select();
    document.execCommand('copy'); document.body.removeChild(ta); done();
  } catch (e) { toast('No se pudo copiar'); }
}
function recordAct(act, cmd, hint, resultSummary, extra) {
  lastAct = {
    act: act,
    cmd: cmd,
    ts: new Date().toISOString(),
    hint: hint || 'Comando copiado — ejecútelo en terminal (no shell en browser).',
    result: resultSummary || null,
    path: (extra && extra.path) || null,
    preview: (extra && extra.preview) || null
  };
  renderLastAct();
}
function renderLastAct() {
  const cmdEl = document.getElementById('last-act-cmd');
  const metaEl = document.getElementById('last-act-meta');
  const pathsEl = document.getElementById('last-act-paths');
  const prevEl = document.getElementById('last-act-preview');
  const btnsEl = document.getElementById('last-act-btns');
  if (lastAct.cmd || lastAct.result) {
    const body = lastAct.result
      ? String(lastAct.result)
      : String(lastAct.cmd || '—');
    cmdEl.textContent = body;
    const t = lastAct.ts ? new Date(lastAct.ts).toLocaleTimeString() : '—';
    metaEl.textContent = (lastAct.act || 'acto') + ' · ' + t + ' · ' + (lastAct.hint || '');
    if (pathsEl) {
      if (lastAct.path) {
        pathsEl.hidden = false;
        pathsEl.textContent = lastAct.path;
      } else {
        pathsEl.hidden = true;
        pathsEl.textContent = '';
      }
    }
    if (prevEl) {
      if (lastAct.preview) {
        prevEl.hidden = false;
        prevEl.textContent = String(lastAct.preview).slice(0, 400);
      } else {
        prevEl.hidden = true;
        prevEl.textContent = '';
      }
    }
    if (btnsEl) btnsEl.hidden = !(liveOpsOn() || lastAct.path || lastAct.cmd);
  } else if (outboxSnap) {
    cmdEl.textContent = 'Outbox: ' + (outboxSnap.decision || '—') +
      (outboxSnap.quality_grade ? ' · grade ' + outboxSnap.quality_grade : '');
    metaEl.textContent = outboxSnap.hint || 'Snapshot outbox al regenerar.';
    if (pathsEl) pathsEl.hidden = true;
    if (prevEl) prevEl.hidden = true;
    if (btnsEl) btnsEl.hidden = !liveOpsOn();
  } else {
    cmdEl.textContent = '—';
    metaEl.textContent = liveOps.enabled
      ? 'Pulse Estado / Decidir / Acta (live loopback).'
      : 'Copie Estado / Decidir / Acta (sin shell en browser).';
    if (pathsEl) pathsEl.hidden = true;
    if (prevEl) prevEl.hidden = true;
    if (btnsEl) btnsEl.hidden = !liveOpsOn();
  }
}
function liveOpsOn() {
  return !!(liveOps && liveOps.enabled && location.protocol.indexOf('http') === 0);
}
function liveUrl(key) {
  const ep = (liveOps.endpoints || {})[key];
  if (!ep) return null;
  return location.origin + ep;
}
function currentWorkDirRel() {
  const f = fireById(fireSel.value);
  return (f && f.work_dir_rel) || P.work_dir_rel || null;
}
function cliCmdFor(kind) {
  if (kind === 'status') {
    return fireCmd('status_cmd', 'python -m wildfire_front incident status --work-dir "DIR"');
  }
  if (kind === 'decide') {
    return fireCmd('decide_cmd', 'python -m wildfire_front decide --policy field_ops --work-dir "DIR" --explain');
  }
  if (kind === 'export_acta') {
    return fireCmd('acta_cmd', 'python -m wildfire_front export-acta --work-dir "DIR"');
  }
  if (kind === 'replay_third_party') {
    return 'python scripts/run_third_party_replay.py';
  }
  return '';
}
function copyCliQuiet(cmd) {
  const t = (cmd || '').trim();
  if (!t) return;
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(t).catch(() => {});
  } else {
    try {
      const ta = document.createElement('textarea');
      ta.value = t; document.body.appendChild(ta); ta.select();
      document.execCommand('copy'); document.body.removeChild(ta);
    } catch (e) {}
  }
}
function liveUnavailableFallback(kind, label, why) {
  const cmd = cliCmdFor(kind);
  const reason = String(why || 'Sin Live Ops').slice(0, 160);
  recordAct(
    label,
    cmd || '—',
    'Live Ops no activo (hace falta app --serve en loopback). CLI abajo — péguelo en terminal.',
    reason
  );
  const btnsEl = document.getElementById('last-act-btns');
  if (btnsEl) btnsEl.hidden = false;
  const btn = document.getElementById('btn-copy-act-path');
  if (btn) btn.textContent = 'Copiar CLI';
  if (cmd) {
    copyCliQuiet(cmd);
    toast('CLI copiado · sin serve');
  } else {
    toast(reason);
  }
  return true;
}
async function runLiveAct(kind) {
  if (!liveOpsOn()) return false;
  const urlKey = kind === 'export_acta' ? 'export_acta'
    : (kind === 'replay_third_party' ? 'replay_third_party' : kind);
  const url = liveUrl(urlKey);
  const wd = currentWorkDirRel();
  if (!url) {
    return liveUnavailableFallback(kind, 'Live', 'Live offline');
  }
  if (kind !== 'replay_third_party' && !wd) {
    toast('Sin work-dir');
    return true;
  }
  const labels = {
    status: 'Estado', decide: 'Decidir', export_acta: 'Acta',
    replay_third_party: 'Replay'
  };
  const label = labels[kind] || kind;
  toast(label + '…');
  try {
    const body = kind === 'replay_third_party'
      ? { bundle: 'outputs/demo_third_party' }
      : {
          work_dir: wd,
          policy_id: 'field_ops',
          event_id: (card && card.event_id) || (fireById(fireSel.value) && fireById(fireSel.value).id) || 'SPA_LIVE'
        };
    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok || data.ok === false) {
      const err = (data && (data.detail || data.error)) || ('HTTP ' + resp.status);
      const code = resp.status;
      const absent = code === 501 || code === 503 || code === 404
        || err === 'live_ops_disabled'
        || /not implemented/i.test(String(err));
      if (absent) {
        return liveUnavailableFallback(
          kind,
          label,
          'Sin Live Ops (HTTP ' + code + ')'
        );
      }
      recordAct(label, url, 'Live error · fusion OFF', String(err).slice(0, 200));
      toast(label + ' error');
      return true;
    }
    const s = data.summary || {};
    let resultLine = '';
    if (kind === 'status') {
      resultLine = 'status=' + (s.status || '—') +
        (s.quality_grade != null ? ' · grade ' + s.quality_grade : '') +
        (s.primary_ros_m_min != null ? ' · ROS ' + s.primary_ros_m_min : '') +
        (s.message ? ' · ' + s.message : '');
    } else if (kind === 'decide') {
      resultLine = String(s.decision || '—').toUpperCase() +
        (s.confidence_pred != null ? ' · conf ' + s.confidence_pred : '') +
        ' · fusion ' + ((data.honesty_rails || {}).field_ops_ml_live_fusion || 'OFF') +
        (s.outbox_decision ? ' · outbox ' + String(s.outbox_decision).toUpperCase() : '');
      if (s.decision || s.event_id) {
        card = {
          decision: s.decision,
          confidence_pred: s.confidence_pred,
          confidence_pred_label: s.confidence_pred_label,
          event_id: s.event_id,
          system_reliability_pass: s.system_reliability_pass,
          sources: (data.result || {}).sources,
          reasons: (data.result || {}).reasons
        };
        applyHero({
          decision: String(card.decision || 'ABSTAIN').toUpperCase(),
          confidence_pred: card.confidence_pred,
          plain: SHORT[String(card.decision || '').toUpperCase()] || ''
        });
        renderDecisionTab();
      }
    } else if (kind === 'export_acta') {
      resultLine = 'acta ' + (s.decision || '—') +
        (s.acta ? ' · ' + String(s.acta).split(/[/\\\\]/).slice(-2).join('/') : '');
    } else if (kind === 'replay_third_party') {
      resultLine = 'replay_ok=' + (s.replay_ok ? 'true' : 'false') +
        ' · exp=' + (s.expected || '—') + ' got=' + (s.got || '—') +
        ' · (consistencia, no crypto)';
    }
    const extra = {};
    if (kind === 'export_acta') {
      extra.path = s.acta || s.card || null;
      const res = data.result || {};
      extra.preview = res.acta_preview || res.radio_preview || null;
    }
    if (kind === 'decide' && s.reasons_head && s.reasons_head.length) {
      extra.preview = s.reasons_head.join(' · ');
    }
    recordAct(
      label + ' LIVE',
      url,
      'Live Ops · fusion OFF · no shell',
      resultLine || JSON.stringify(s).slice(0, 180),
      extra
    );
    toast(label + ' OK');
  } catch (e) {
    return liveUnavailableFallback(kind, label, 'Live Ops no alcanzable');
  }
  return true;
}
const btnCopyPath = document.getElementById('btn-copy-act-path');
if (btnCopyPath) {
  btnCopyPath.onclick = () => {
    const cli = (lastAct.cmd && String(lastAct.cmd).indexOf('python') === 0) ? lastAct.cmd : null;
    const p = cli || lastAct.path || lastAct.cmd || lastAct.result;
    const ok = cli ? 'CLI copiado' : 'Path';
    copyText(String(p || ''), ok, { act: ok, hint: cli ? 'comando CLI (terminal)' : 'artifact path' });
  };
}
const btnReplay = document.getElementById('btn-live-replay');
if (btnReplay) {
  btnReplay.onclick = () => {
    if (!liveOpsOn()) {
      copyText('python scripts/run_third_party_replay.py', 'Replay cmd');
      return;
    }
    runLiveAct('replay_third_party');
  };
  btnReplay.style.display = liveOps.enabled ? '' : 'none';
}
// A4: ACK is UI-only until Agent B decision-log backend ships
const btnDlogAck = document.getElementById('btn-dlog-ack');
if (btnDlogAck) {
  btnDlogAck.onclick = () => {
    const st = document.getElementById('dlog-ack-state');
    const ts = new Date().toISOString().slice(0, 19) + 'Z';
    if (st) st.textContent = 'ack: UI ' + ts + ' (local · no backend)';
    recordAct('ACK UI', 'decision-log', 'ACK local only — not H1 acta', 'ack_ui');
    toast('ACK UI · no backend');
  };
}
function actStatus() {
  if (liveOpsOn()) { runLiveAct('status'); return; }
  copyText(cliCmdFor('status'), 'CLI copiado', { act: 'Estado', hint: 'sin serve — péguelo en terminal' });
}
function actDecide() {
  if (liveOpsOn()) { runLiveAct('decide'); return; }
  copyText(cliCmdFor('decide'), 'CLI copiado', { act: 'Decidir', hint: 'sin serve — péguelo en terminal' });
}
function actActa() {
  if (liveOpsOn()) { runLiveAct('export_acta'); return; }
  copyText(cliCmdFor('export_acta'), 'CLI copiado', { act: 'Acta', hint: 'sin serve — péguelo en terminal' });
}

function setMode(mode, quiet) {
  uiMode = mode === 'advanced' ? 'advanced' : 'simple';
  document.body.classList.toggle('mode-simple', uiMode === 'simple');
  document.body.classList.toggle('mode-advanced', uiMode === 'advanced');
  document.getElementById('btn-mode-simple').classList.toggle('on', uiMode === 'simple');
  document.getElementById('btn-mode-advanced').classList.toggle('on', uiMode === 'advanced');
  renderActions(); renderIntake(); updateRoleUi(true);
  syncBridgeBtn();
  if (!quiet) toast(uiMode === 'simple' ? 'Fácil' : 'Pro');
}
document.getElementById('btn-mode-simple').onclick = () => setMode('simple');
document.getElementById('btn-mode-advanced').onclick = () => setMode('advanced');
document.getElementById('btn-help').onclick = () => document.getElementById('help-modal').classList.add('on');
document.getElementById('btn-help-close').onclick = () => document.getElementById('help-modal').classList.remove('on');
document.getElementById('help-modal').onclick = (e) => { if (e.target.id === 'help-modal') e.currentTarget.classList.remove('on'); };

// Role switcher (UI label + Pro rebuild --role; no invent gates)
function updateRoleUi(quiet) {
  document.querySelectorAll('#role-seg button').forEach(b => {
    b.classList.toggle('on', b.dataset.role === currentRole);
  });
  const h = roleHints[currentRole] || {};
  const hintEl = document.getElementById('role-hint');
  if (hintEl) {
    hintEl.textContent = h.title || currentRole;
    hintEl.title = h.hint || h.audience || currentRole;
  }
  // Pro: rebuild cmd includes --role
  if (uiMode === 'advanced') {
    const base = rebuildCmdBase();
    // inject --role if missing
    let cmd = base;
    if (!/--role\s+\w+/.test(cmd)) {
      cmd = cmd.replace(/(\s--open)?\s*$/, ' --role ' + currentRole + '$1');
      if (!/--role\s+\w+/.test(cmd)) cmd = cmd + ' --role ' + currentRole;
    } else {
      cmd = cmd.replace(/--role\s+\w+/, '--role ' + currentRole);
    }
    rebuild._role_cmd = cmd;
  } else {
    rebuild._role_cmd = rebuildCmdBase();
  }
  // short next-line role hint without inventing GO_Q
  const nxt = brief.next_action || {};
  const nextSum = (nxt.summary || '—').toString();
  const nextShort = nextSum.length > 120 ? nextSum.slice(0, 117) + '…' : nextSum;
  const roleBit = (h.hint || h.audience || '');
  const roleShort = roleBit.length > 80 ? roleBit.slice(0, 77) + '…' : roleBit;
  document.getElementById('next-box').innerHTML =
    '<b>Siguiente · ' + (nxt.priority || 'P?') + ' · ' + (currentRole || '') + '</b>' +
    nextShort + (roleShort ? '<div style="margin-top:4px;font-size:10px;color:var(--faint)">' + roleShort + '</div>' : '');
  if (!quiet) toast('Rol: ' + (h.title || currentRole));
}
document.querySelectorAll('#role-seg button').forEach(btn => {
  btn.onclick = () => {
    currentRole = btn.dataset.role || 'operator';
    updateRoleUi(false);
  };
});

// Top chips
const topChips = document.getElementById('top-chips');
function addTop(text, cls) {
  const s = document.createElement('div');
  s.className = 'chip' + (cls ? ' ' + cls : '');
  s.innerHTML = '<i></i>' + text;
  topChips.appendChild(s);
}
addTop('Fusion OFF', 'ok');
addTop((P.fire_count || fires.length || 0) + ' IF', 'live');
if (liveOps && liveOps.enabled) addTop('Live Ops', 'live');
const light = hero.overall_light || brief.overall_light || '—';
addTop(light, light === 'VERDE' ? 'ok' : (light === 'ROJO' ? 'err' : 'warn'));
if (pack && pack.enabled) addTop('Pack ' + (pack.n || 0), 'live');

// Tabs
document.querySelectorAll('#main-tabs .tab').forEach(btn => {
  btn.onclick = () => {
    document.querySelectorAll('#main-tabs .tab').forEach(b => b.classList.remove('on'));
    document.querySelectorAll('.pane').forEach(p => p.classList.remove('on'));
    btn.classList.add('on');
    const pane = document.getElementById('tab-' + btn.dataset.tab);
    if (pane) pane.classList.add('on');
  };
});

// Fires + multi-pack client switch
const fireSel = document.getElementById('fire-select');
const fireList = document.getElementById('fire-list');
function fireById(id) { return fires.find(f => f.id === id); }
function packEntry(id) {
  return pack && pack.enabled && pack.by_id ? pack.by_id[id] : null;
}
function rebuildCmdBase() {
  const f = fireById(fireSel.value);
  return (f && f.rebuild_cmd) || rebuild.selected_cmd || 'python -m wildfire_front app --open';
}
function rebuildCmd() {
  if (uiMode === 'advanced' && rebuild._role_cmd) return rebuild._role_cmd;
  const base = rebuildCmdBase();
  if (uiMode !== 'advanced') return base;
  if (!/--role\s+\w+/.test(base)) {
    return base.replace(/(\s--open)?\s*$/, ' --role ' + currentRole + '$1');
  }
  return base.replace(/--role\s+\w+/, '--role ' + currentRole);
}

function applyHero(h) {
  hero = h || {};
  const word = String(hero.decision || 'BRIEF').toUpperCase();
  const heroEl = document.getElementById('hero');
  heroEl.className = 'decision ' + ({GO:'go',HOLD:'hold',ABSTAIN:'abstain',BRIEF:'brief'}[word] || 'brief');
  document.getElementById('hero-word').textContent = word;
  document.getElementById('hero-plain').textContent = SHORT[word] || (hero.plain || '');
  const confEl = document.getElementById('hero-conf');
  const fill = document.getElementById('unc-fill');
  const bandEl = document.getElementById('unc-band');
  const labelEl = document.getElementById('unc-label');
  let conf = null;
  if (hero.confidence_pred != null && !Number.isNaN(+hero.confidence_pred)) {
    conf = Math.max(0, Math.min(1, +hero.confidence_pred));
    confEl.textContent = Math.round(conf * 100) + '%';
  } else confEl.textContent = '';
  // Existing bands only (label from card / heuristic) — never invent numeric ROS.
  let band = String(hero.confidence_label || hero.confidence_pred_label || '').trim();
  if (!band && conf != null) {
    if (conf < 0.34) band = 'baja';
    else if (conf < 0.67) band = 'media';
    else band = 'alta';
  }
  if (!band) band = 'sin conf';
  // Conf fill only from existing hero.confidence_pred — never invent ROS/scores.
  // Prefer server uncertainty_bar.fill_pct when present and conf matches.
  const ub = uncertaintyBar || {};
  let fillPct = (conf != null ? Math.round(conf * 100) : 0);
  if (ub && ub.confidence_pred != null && conf != null
      && Math.abs(+ub.confidence_pred - conf) < 1e-9
      && typeof ub.fill_pct === 'number') {
    fillPct = Math.max(0, Math.min(100, +ub.fill_pct));
  }
  if (fill) fill.style.width = fillPct + '%';
  if (bandEl) bandEl.textContent = 'banda ' + band;
  if (labelEl) labelEl.textContent = (ub && ub.label) || 'Conf. predicción (no es ROS)';
  const noteEl = document.getElementById('unc-note');
  if (noteEl) {
    // Keep bold **no es ROS** emphasis for honesty pin (Mes2 PR1-A)
    noteEl.innerHTML = '<b>no es ROS</b> · IoU ≠ ROS · banda de calidad existente, sin inventar scores';
  }
  // A5 split conf UI: ML conf ≠ ROS conf labels
  const scMl = document.getElementById('sc-ml');
  const scRos = document.getElementById('sc-ros');
  if (scMl) {
    scMl.textContent = conf != null
      ? (Math.round(conf * 100) + '% · ' + band)
      : '—';
  }
  if (scRos) {
    let rosConf = null;
    if (ops && ops.ros_confidence != null && !Number.isNaN(+ops.ros_confidence)) {
      rosConf = +ops.ros_confidence;
    } else if (ops && ops.quality_grade) {
      rosConf = String(ops.quality_grade);
    }
    if (typeof rosConf === 'number') {
      scRos.textContent = Math.round(rosConf * 100) + '% (ops)';
    } else if (rosConf) {
      scRos.textContent = 'grade ' + rosConf + ' (ops · no ML)';
    } else {
      scRos.textContent = '— (sin conf ROS)';
    }
  }
  // A4/A8 decision-log surface (sidecar read or stub; never invent GO_Q)
  const dlogId = document.getElementById('dlog-id');
  const dlogMeta = document.getElementById('dlog-meta');
  const dlog = decisionLog || {};
  if (dlogId) {
    const eid = dlog.id || (card && card.event_id) || hero.event_id
      || (hero.decision ? ('stub-' + String(hero.decision).toLowerCase()) : null);
    const mode = dlog.mode === 'sidecar_read' ? 'sidecar B' : 'stub UI';
    dlogId.textContent = eid ? ('id: ' + eid + ' · ' + mode) : ('id: — (' + mode + ' · backend B opcional)');
  }
  if (dlogMeta) {
    const dec = dlog.decision || (card && card.decision) || hero.decision || '—';
    const fus = 'fusion OFF';
    const gq = 'go_q_met=' + String(dlog.go_q_met === true ? true : false);
    dlogMeta.textContent = 'decisión ' + String(dec).toUpperCase() + ' · ' + fus + ' · ' + gq
      + ' · conf ML ≠ conf ROS · ' + (dlog.note || 'ACK UI only');
  }
  renderH1Eng();
  renderSrLadder();
}

function renderH1Eng() {
  const flag = document.getElementById('h1-goq-flag');
  const stepsEl = document.getElementById('h1-steps');
  const cmdEl = document.getElementById('h1-serve-cmd');
  const noteEl = document.getElementById('h1-note');
  const h1 = h1Eng || {};
  if (flag) {
    flag.textContent = 'go_q_met=' + String(h1.go_q_met === true ? true : false)
      + ' · eng dry-run · no es demo tercero';
  }
  if (stepsEl) {
    stepsEl.innerHTML = '';
    (h1.steps || []).slice(0, 6).forEach(s => {
      const li = document.createElement('li');
      const title = s.title || ('Paso ' + (s.n || ''));
      const detail = s.detail || '';
      li.textContent = title + (detail ? ' — ' + detail : '');
      stepsEl.appendChild(li);
    });
  }
  if (cmdEl) {
    const live = !!(liveOps && liveOps.enabled);
    cmdEl.textContent = live
      ? (h1.serve_cmd || 'python -m wildfire_front app --serve')
      : ((h1.offline_cmd || 'python -m wildfire_front app --open') + ' · sin serve → copy-CLI');
  }
  if (noteEl) {
    noteEl.textContent = (h1.non_claims || []).slice(0, 3).join(' · ')
      || 'fusion OFF · go_q_met=false · acta H1 es humana';
  }
}

function renderSrLadder() {
  const host = document.getElementById('sr-levels');
  const claims = document.getElementById('sr-claims');
  const sr = srLadder || {};
  if (host) {
    host.innerHTML = '';
    const active = String(sr.active_id || 'S0');
    (sr.levels || []).forEach(lv => {
      const row = document.createElement('div');
      row.className = 'sr-lv' + (lv.id === active ? ' on' : '');
      row.setAttribute('data-sr-id', lv.id || '');
      row.innerHTML = '<div class="sr-id">' + (lv.id || '?') + '</div>'
        + '<div><div class="sr-lab">' + (lv.label || '') + '</div>'
        + '<div class="sr-why">' + (lv.why || '') + '</div></div>';
      host.appendChild(row);
    });
  }
  if (claims) {
    const nc = (sr.non_claims || []).slice(0, 4).join(' · ');
    claims.textContent = (sr.claims_guardian || 'Claims Guardian')
      + (nc ? ' · ' + nc : '')
      + ' · fusion ' + (sr.field_ops_ml_live_fusion || 'OFF');
  }
}

function renderOpsKv() {
  const okv = document.getElementById('ops-kv');
  okv.innerHTML = '';
  if (ops && Object.keys(ops).length) {
    const ros = ops.primary_ros_m_min != null ? ops.primary_ros_m_min : ops.speed_median_m_min;
    const ha = ops.area_ha_max != null ? ops.area_ha_max : ops.area_ha_last;
    const n = ops.n_frames != null ? ops.n_frames : ops.num_observations || ops.observation_count;
    metric(okv, 'Calidad', ops.quality_grade);
    metric(okv, 'ROS m/min', typeof ros === 'number' ? Math.round(ros * 100) / 100 : ros);
    metric(okv, 'Área ha', typeof ha === 'number' ? Math.round(ha * 10) / 10 : ha);
    metric(okv, 'Frames', n);
  } else okv.innerHTML = '<div class="empty" style="grid-column:1/-1">Sin métricas</div>';
}

function renderDecisionTab() {
  const dbody = document.getElementById('decision-body');
  if (card) {
    dbody.className = '';
    dbody.innerHTML = '<div class="grid2" id="dec-kv"></div><div id="src-list" style="margin-top:8px"></div>' +
      ((card.reasons || []).length ? '<ul id="dec-reasons" style="padding-left:1.1rem;margin:8px 0;color:var(--muted);font-size:11px"></ul>' : '') +
      '<button type="button" class="btn primary block" id="btn-copy-decision" style="margin-top:8px">Copiar</button>';
    const dkv = document.getElementById('dec-kv');
    metric(dkv, 'Decisión', card.decision);
    metric(dkv, 'Conf.', card.confidence_pred != null ? Math.round(card.confidence_pred * 100) + '%' : '—');
    metric(dkv, 'Evento', card.event_id || '—');
    metric(dkv, 'Sistema', card.system_reliability_pass === true ? 'OK' : (card.system_reliability_pass === false ? 'FAIL' : '—'));
    (card.sources || []).slice(0, 6).forEach(s => {
      const row = document.createElement('div');
      row.className = 'src';
      row.innerHTML = '<span>' + (s.id || '?') + '</span><span>' + Math.round(Number(s.confidence || 0) * 100) + '%</span>';
      document.getElementById('src-list').appendChild(row);
    });
    const ur = document.getElementById('dec-reasons');
    if (ur) (card.reasons || []).slice(0, 4).forEach(r => {
      const li = document.createElement('li'); li.textContent = r; ur.appendChild(li);
    });
    document.getElementById('btn-copy-decision').onclick = () => copyText([
      'Decisión: ' + (card.decision || '—'),
      'Confianza: ' + (card.confidence_pred != null ? Math.round(card.confidence_pred * 100) + '%' : '—'),
      ...(card.reasons || []).slice(0, 4).map(r => '- ' + r),
    ].join('\n'), 'Decisión', { act: 'Decisión', hint: 'Resumen Decision Card copiado' });
  } else {
    dbody.className = 'empty';
    dbody.textContent = P.work_dir ? 'Sin tarjeta en outbox.' : 'Selecciona un IF con datos.';
  }
}

function clearMapLayers() {
  mapLayers.forEach(l => { try { map.removeLayer(l); } catch (e) {} });
  mapLayers = [];
  bounds = [];
}
function paintMapLayers(mp) {
  clearMapLayers();
  (mp.layers || []).forEach(Lyr => {
    if (!Lyr.geojson) return;
    const firms = isFirms(Lyr);
    const col = firms ? '#FB7185' : '#38BDF8';
    const layer = L.geoJSON(Lyr.geojson, {
      style: () => ({ color: col, weight: firms ? 1.5 : 2.5, fillColor: col, fillOpacity: firms ? 0.75 : 0.12 }),
      pointToLayer: (f, ll) => L.circleMarker(ll, {
        radius: firms ? 5 : 4, color: col, fillColor: col, fillOpacity: 0.9, weight: 1
      }),
      onEachFeature: (f, l) => {
        const p = f.properties || {};
        const lines = Object.keys(p).slice(0, 6).map(k => '<b>' + k + '</b>: ' + p[k]);
        l.bindPopup('<div style="font:12px/1.3 IBM Plex Sans,system-ui"><b>' + (Lyr.name || Lyr.id) + '</b><br/>' + lines.join('<br/>') + '</div>');
      }
    }).addTo(map);
    mapLayers.push(layer);
    touchBounds(layer);
  });
  document.getElementById('map-layer-n').textContent = ((mp.layers || []).length) + ' capas';
  const conn = (P.connectivity && P.connectivity.status) || (mp.connectivity && mp.connectivity.status) || 'skipped';
  document.getElementById('map-conn').textContent =
    conn + (mp.firms && mp.firms.n_hotspots != null ? ' · ' + mp.firms.n_hotspots + ' focos' : '');
  if (bounds.length) fitAll(true);
}

// Baseline snapshot = payload for the SPA-selected fire (not another pack entry)
const baselineSnap = {
  id: P.selected_fire_id || null,
  hero: Object.assign({}, P.hero || {}),
  decision_card: P.decision_card || null,
  ops_metrics: P.ops_metrics || null,
  map: mapP0,
  outbox_last_run: P.outbox_last_run || null,
};
function showPackBanner(msg) {
  let el = document.getElementById('pack-banner');
  if (!el) {
    el = document.createElement('div');
    el.id = 'pack-banner';
    el.className = 'next';
    el.style.borderLeftColor = 'var(--hold)';
    const host = document.getElementById('next-box');
    if (host && host.parentNode) host.parentNode.insertBefore(el, host.nextSibling);
  }
  if (!msg) { el.style.display = 'none'; el.textContent = ''; return; }
  el.style.display = '';
  el.innerHTML = '<b>Pack</b>' + msg;
}
function applyFireView(snap, clearBanner) {
  applyHero(snap.hero || {});
  card = snap.decision_card || null;
  ops = snap.ops_metrics || null;
  mapP = snap.map || { layers: [], center: { lon: -3.7, lat: 40.4 }, zoom: 7 };
  renderOpsKv();
  renderDecisionTab();
  if (typeof map !== 'undefined' && map) paintMapLayers(mapP);
  renderKpis();
  if (clearBanner) showPackBanner(null);
}
function selectFire(id, quiet) {
  const f = fireById(id);
  if (!f) return;
  fireSel.value = f.id;
  fireList.querySelectorAll('.fcard').forEach(el => el.classList.toggle('on', el.dataset.id === f.id));
  const pe = packEntry(f.id);
  const packOn = !!(pack && pack.enabled);
  if (pe) {
    // Client-side switch: hero / decision / ops / map without re-running Python
    applyFireView({
      hero: pe.hero || {},
      decision_card: pe.decision_card || null,
      ops_metrics: pe.ops_metrics || null,
      map: pe.map || mapP0,
    }, true);
    if (!quiet) toast((f.label || f.id) + ' (pack)');
  } else if (packOn) {
    // Pack active but this IF is outside — never leave previous pack data visible
    if (baselineSnap.id && f.id === baselineSnap.id) {
      applyFireView(baselineSnap, true);
      if (!quiet) toast((f.label || f.id) + ' (baseline)');
    } else {
      applyFireView({
        hero: {
          decision: 'BRIEF',
          confidence_pred: null,
          plain: 'IF no empaquetado — regenerar con Abrir consola',
        },
        decision_card: null,
        ops_metrics: null,
        map: { layers: [], center: mapP0.center || { lon: -3.7, lat: 40.4 }, zoom: 7, connectivity: { status: 'skipped' } },
      }, false);
      showPackBanner(
        'IF no empaquetado — mapa/decisión limpios. Pulse «Abrir consola» para regenerar este incendio.'
      );
      if (!quiet) toast((f.label || f.id) + ' · no pack · Abrir consola');
    }
  } else {
    // No multi-pack: keep baseline embedded view; only toast rebuild hint
    if (!quiet) toast((f.label || f.id) + ' · copiar Abrir consola');
  }
  updateRoleUi(true);
}
if (!fires.length) {
  fireSel.innerHTML = '<option value="">(sin IF)</option>';
  fireList.innerHTML = '<div class="empty">Catálogo vacío</div>';
} else {
  fires.forEach(f => {
    const o = document.createElement('option');
    o.value = f.id;
    const inPack = !!packEntry(f.id);
    const packOn = !!(pack && pack.enabled);
    o.textContent = (f.label || f.id) + (packOn ? (inPack ? ' · PACK' : ' · rebuild') : '');
    if (f.selected) o.selected = true;
    fireSel.appendChild(o);
    const el = document.createElement('div');
    el.className = 'fcard' + (f.selected ? ' on' : '');
    el.dataset.id = f.id;
    el.innerHTML = '<div class="id">' + (f.label || f.id) + '</div><div class="badge">' +
      [f.decision, f.has_geojson ? 'MAP' : null, packOn ? (inPack ? 'PACK' : 'REBUILD') : null].filter(Boolean).join(' · ') + '</div>';
    el.onclick = () => selectFire(f.id);
    fireList.appendChild(el);
  });
}
fireSel.onchange = () => selectFire(fireSel.value);

function fireCmd(key, fallback) {
  const f = fireById(fireSel.value);
  if (f && f[key]) return f[key];
  const pe = packEntry(fireSel.value);
  if (pe && pe.cmds && pe.cmds[key]) return pe.cmds[key];
  const wd = (f && f.work_dir_rel) || P.work_dir_rel || 'DIR';
  return fallback.replace(/DIR/g, wd);
}
document.getElementById('btn-copy-rebuild').onclick = () =>
  copyText(rebuildCmd(), 'Consola copiada', { act: 'Abrir consola', hint: 'Rebuild SPA (ejecutar en terminal)' });
document.getElementById('btn-copy-map').onclick = () =>
  copyText(fireCmd('map_cmd', 'python -m wildfire_front map --work-dir DIR --no-live --open'), 'Mapa', { act: 'Mapa', hint: 'Mapa solo' });
document.getElementById('btn-act-status').onclick = () => actStatus();
document.getElementById('btn-act-decide').onclick = () => actDecide();
document.getElementById('btn-act-acta').onclick = () => actActa();

// Decision hero (initial — selectFire may re-apply pack)
applyHero(hero);

// KPI strip
const gates = brief.gates || {};
const bkv = document.getElementById('brief-kv');
function yn(v) {
  if (v === true || v === 'GO' || v === 'PASS' || v === 'yes') return 'Sí';
  if (v === false || v === 'NO' || v === 'FAIL') return 'No';
  if (v == null || v === '' || v === 'partial') return v === 'partial' ? 'parcial' : '—';
  return String(v);
}
function kpi(parent, k, v) {
  const d = document.createElement('div');
  d.className = 'kpi';
  d.innerHTML = '<div class="k">' + k + '</div><div class="v">' + (v == null || v === '' ? '—' : v) + '</div>';
  parent.appendChild(d);
}
function renderKpis() {
  bkv.innerHTML = '';
  const rosKpi = ops && (ops.primary_ros_m_min != null ? ops.primary_ros_m_min : ops.speed_median_m_min);
  kpi(bkv, 'Producto', yn(gates.GO_MES));
  kpi(bkv, 'Demo', yn(gates.GO_Q));
  kpi(bkv, 'Lab', yn(gates.ml_product_go));
  kpi(bkv, 'ROS', typeof rosKpi === 'number' ? Math.round(rosKpi * 100) / 100 : (rosKpi != null ? rosKpi : '—'));
}
renderKpis();
renderLastAct();
updateRoleUi(true);

// Overview metrics
function metric(parent, k, v) {
  const d = document.createElement('div');
  d.className = 'metric';
  d.innerHTML = '<div class="k">' + k + '</div><div class="v">' + (v == null || v === '' ? '—' : v) + '</div>';
  parent.appendChild(d);
}
renderOpsKv();

const railsEl = document.getElementById('rails');
[
  ['Fusion OFF', rails.field_ops_ml_live_fusion === 'OFF' || rails.field_ops_ml_live_fusion === false],
  ['No despacho', !!rails.not_tactical_dispatch],
  ['NRT ≠ perímetro', !!rails.nrt_not_official_perimeter],
].forEach(([label, on]) => {
  const s = document.createElement('div');
  s.className = 'chip' + (on ? ' ok' : '');
  s.innerHTML = '<i></i>' + label;
  railsEl.appendChild(s);
});

(brief.recommended_sequence || []).forEach(cmd => {
  const li = document.createElement('li');
  li.textContent = cmd;
  document.getElementById('seq').appendChild(li);
});
const nxt0 = brief.next_action || {};
document.getElementById('btn-copy').onclick = () =>
  copyText(nxt0.command || brief.primary_command || '', 'Comando', { act: 'Next', hint: 'next_action brief' });

renderDecisionTab();

// Actions
const groups = [];
actions.forEach(a => { if (a.group && !groups.includes(a.group)) groups.push(a.group); });
const af = document.getElementById('actions-filters');
const al = document.getElementById('actions-list');
function actionText(a) {
  if (uiMode === 'advanced' && a.cmd) return a.cmd;
  return [a.simple_cta || a.title, a.plain || a.why, a.cmd].filter(Boolean).join('\n');
}
function renderActions() {
  al.innerHTML = '';
  const list = actions.filter(a => activeGroup === 'Todos' || a.group === activeGroup);
  if (!list.length) { al.innerHTML = '<div class="empty">—</div>'; return; }
  list.forEach(a => {
    const d = document.createElement('details');
    d.className = 'act';
    const title = a.simple_cta || a.title || a.id;
    d.innerHTML = '<summary>' + title + '</summary><div class="body">' +
      (a.plain || a.why ? '<p>' + (a.plain || a.why) + '</p>' : '') +
      (uiMode === 'advanced' && a.cmd ? '<div class="cmd">' + a.cmd + '</div>' : '') +
      '<button type="button" class="btn primary sm copy">Copiar</button></div>';
    d.querySelector('.copy').onclick = (e) => {
      e.preventDefault();
      copyText(actionText(a), 'Copiado', { act: a.simple_cta || a.id, hint: 'product action' });
    };
    al.appendChild(d);
  });
}
['Todos', ...groups].forEach(g => {
  const b = document.createElement('button');
  b.type = 'button'; b.textContent = g;
  if (g === 'Todos') b.className = 'on';
  b.onclick = () => {
    activeGroup = g;
    af.querySelectorAll('button').forEach(x => x.classList.remove('on'));
    b.classList.add('on'); renderActions();
  };
  af.appendChild(b);
});

function renderIntake() {
  const el = document.getElementById('intake-steps');
  el.innerHTML = '';
  if (!intake.length) { el.innerHTML = '<div class="empty">—</div>'; return; }
  intake.forEach(s => {
    const row = document.createElement('div');
    row.className = 'step';
    row.innerHTML = '<div class="n">' + (s.step || '·') + '</div><div><b>' + (s.title || '') +
      '</b><p>' + (s.plain || s.detail || '') + '</p>' +
      (uiMode === 'advanced' && s.cmd ? '<div class="cmd" style="font-family:var(--mono);font-size:10px;color:var(--cyan);margin-top:4px;word-break:break-all">' + s.cmd + '</div>' : '') +
      '<button type="button" class="btn sm" style="margin-top:6px">Copiar</button></div>';
    row.querySelector('button').onclick = () =>
      copyText(uiMode === 'advanced' && s.cmd ? s.cmd : [s.title, s.plain || s.detail, s.cmd].filter(Boolean).join('\n'));
    el.appendChild(row);
  });
}

const glossEl = document.getElementById('glossary-list');
if (!glossary.length) glossEl.innerHTML = '<div class="empty">—</div>';
else glossary.forEach(g => {
  const d = document.createElement('div');
  d.className = 'gitem';
  d.innerHTML = '<b>' + (g.term || g.id || '') + '</b><span>' + (g.plain || '') + '</span>';
  glossEl.appendChild(d);
});

// Optional live Decision Card bridge (loopback only; silent offline fallback)
// Prefer same-origin proxy when SPA is served (http://127.0.0.1:8766/bridge/v1/decide)
// so browser CORS never blocks cross-port serve-decide on :8765.
function bridgeDecideUrl() {
  if (!bridge || !bridge.enabled) return null;
  const proxyPath = bridge.proxy_path || '/bridge/v1/decide';
  const prefer = bridge.prefer_proxy !== false;
  if (prefer && location.protocol.indexOf('http') === 0 && proxyPath) {
    return location.origin + proxyPath;
  }
  if (bridge.url) {
    return String(bridge.url).replace(/\/$/, '') + (bridge.endpoint || '/v1/decide');
  }
  return null;
}
function syncBridgeBtn() {
  const btn = document.getElementById('btn-bridge-refresh');
  const row = document.getElementById('actions-row');
  const on = !!(bridge && bridge.enabled && (bridge.url || bridge.proxy_path));
  if (btn) {
    btn.style.display = on && uiMode === 'advanced' ? '' : 'none';
  }
  if (row) row.classList.toggle('triple', on && uiMode === 'advanced');
}
async function refreshCardBridge() {
  if (!bridge || !bridge.enabled) return;
  const url = bridgeDecideUrl();
  if (!url) {
    toast('Bridge offline · card embebida');
    return;
  }
  const f = fireById(fireSel.value);
  const body = {
    policy_id: 'field_ops',
    work_dir: (f && f.work_dir_rel) || P.work_dir_rel || undefined,
    event_id: (card && card.event_id) || (f && f.id) || 'SPA_BRIDGE',
  };
  try {
    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    const data = await resp.json();
    // Real serve-decide returns Decision Card at top level (decision, event_id, …)
    // plus optional latency_ms; accept nested card for tests only.
    const newCard = (data && data.decision != null) ? data
      : (data.card || data.decision_card || data);
    if (newCard && (newCard.decision || newCard.event_id)) {
      card = {
        decision: newCard.decision,
        confidence_pred: newCard.confidence_pred,
        confidence_pred_label: newCard.confidence_pred_label,
        event_id: newCard.event_id,
        system_reliability_pass: newCard.system_reliability_pass,
        sources: newCard.sources,
        reasons: newCard.reasons,
      };
      applyHero({
        decision: String(card.decision || 'ABSTAIN').toUpperCase(),
        confidence_pred: card.confidence_pred,
        plain: SHORT[String(card.decision || '').toUpperCase()] || '',
      });
      renderDecisionTab();
      recordAct('Bridge', url, 'Card live (same-origin proxy o bridge) — fusion OFF');
      toast('Card actualizada');
    }
  } catch (e) {
    // Silent fallback to embedded card (CORS, file://, or upstream down)
    toast('Bridge offline · card embebida');
  }
}
const bridgeBtn = document.getElementById('btn-bridge-refresh');
if (bridgeBtn) bridgeBtn.onclick = () => refreshCardBridge();
syncBridgeBtn();

// Map (create before initial fire select so pack paint can use it)
const center = mapP.center || { lon: -3.7, lat: 40.4 };
const map = L.map('map', { zoomControl: true }).setView([center.lat, center.lon], mapP.zoom || 7);
L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
  maxZoom: 18, attribution: '&copy; OSM &copy; CARTO'
}).addTo(map);

function touchBounds(layer) {
  try {
    const b = layer.getBounds && layer.getBounds();
    if (b && b.isValid && b.isValid()) bounds.push(b);
  } catch (e) {}
}
function isFirms(Lyr) {
  return /firms|hotspot|public_europe|area_api|fixture/i.test(
    (Lyr.id || '') + ' ' + (Lyr.name || '') + ' ' + (Lyr.source || '')
  );
}

// Initial fire selection after map exists (pack may repaint layers)
if (fires.length) {
  selectFire((fires.find(f => f.selected) || fires[0]).id, true);
} else {
  paintMapLayers(mapP);
}

function fitAll(quiet) {
  if (!bounds.length) { if (!quiet) toast('Sin capas'); return; }
  const b = bounds[0];
  bounds.slice(1).forEach(x => b.extend(x));
  map.fitBounds(b.pad(0.14));
  if (!quiet) toast('Centrado');
}
document.getElementById('btn-fit').onclick = () => fitAll(false);

setMode(uiMode, true);
const resize = () => map.invalidateSize({ animate: false });
setTimeout(resize, 50);
window.addEventListener('resize', resize);
if (window.ResizeObserver) new ResizeObserver(resize).observe(document.querySelector('.map-wrap'));
""".strip()


def render_product_app_html(payload: dict[str, Any]) -> str:
    """Self-contained industrial SPA: map-first, dense KPIs, no essay text."""
    data_js = json.dumps(payload, ensure_ascii=False)
    title = _esc(str(payload.get("title") or "WFD OPS"))
    return (
        "<!DOCTYPE html>\n"
        '<html lang="es" class="dark">\n'
        "<head>\n"
        '<meta charset="utf-8"/>\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"/>\n'
        '<meta name="description" content="WFD OPS — industrial fire status console. Not tactical dispatch."/>\n'
        f"<title>{title}</title>\n"
        '<link rel="preconnect" href="https://fonts.googleapis.com"/>\n'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>\n'
        '<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&display=swap" rel="stylesheet"/>\n'
        '<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>\n'
        '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>\n'
        "<style>\n"
        f"{_css()}\n"
        "</style>\n"
        "</head>\n"
        '<body class="mode-simple">\n'
        f"{_shell()}\n"
        "<script>\n"
        f"const P = {data_js};\n"
        f"{_js()}\n"
        "</script>\n"
        "</body>\n"
        "</html>\n"
    )
