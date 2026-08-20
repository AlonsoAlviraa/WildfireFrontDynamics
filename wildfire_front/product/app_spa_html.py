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
  --top:48px; --rail:min(420px, 40vw); --r:4px; --tap:48px;
  --dock:0px; --safe-b:env(safe-area-inset-bottom,0px); --safe-t:env(safe-area-inset-top,0px);
  --font:"IBM Plex Sans",system-ui,-apple-system,sans-serif;
  --mono:ui-monospace,"IBM Plex Mono",Consolas,monospace;
}
*,*::before,*::after{box-sizing:border-box}
html,body{height:100%;margin:0;overflow:hidden;background:var(--bg);color:var(--text);font:13px/1.3 var(--font)}
button,select,input{font:inherit;color:inherit}
button:focus-visible,select:focus-visible,input:focus-visible,[tabindex]:focus-visible{
  outline:2px solid var(--cyan);outline-offset:2px
}
.skip-link{position:fixed;left:10px;top:8px;z-index:9999;transform:translateY(-180%);
  padding:8px 10px;background:var(--cyan);color:#041018;font-weight:700;border-radius:var(--r)}
.skip-link:focus{transform:translateY(0)}
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
  :root{--rail:auto;--dock:calc(56px + var(--safe-b));--top:44px}
  .main{
    grid-template-columns:minmax(0,1fr);
    grid-template-rows:minmax(22vh,28vh) minmax(0,1fr);
  }
  body.view-mapa .main{grid-template-rows:minmax(58vh,70vh) minmax(0,1fr)}
  body.view-fotos .main,body.view-mas .main{grid-template-rows:minmax(16vh,20vh) minmax(0,1fr)}
  .chips{display:none}
  .role-seg{display:none}
  .acts-dock{
    order:90;position:sticky;bottom:0;left:0;z-index:8;
    background:var(--panel2);border-top:1px solid var(--line);
    padding-bottom:6px;width:100%;max-width:100%;
  }
  .primary-acts{gap:4px;padding:6px 8px 4px;grid-template-columns:repeat(3,minmax(0,1fr))}
  .share-acts,.mando-tools{gap:4px;padding:0 8px 8px;grid-template-columns:repeat(2,minmax(0,1fr))}
  .acts-dock .pact,.share-acts .pact,.mando-tools .pact{max-width:none;width:100%}
  .pact .sub{letter-spacing:0}
  .decision{padding:10px 10px 8px}
  .decision .word{font-size:1.45rem}
  .unc-bar .unc-note{display:none}
  .brand em{display:none}
  .top{gap:6px;padding:0 8px;padding-top:var(--safe-t)}
  .top select{max-width:min(160px,42vw)}
  .shell,.main,.rail,.rail-stack,.pane-host,.map-wrap{
    min-width:0;max-width:100%;width:100%;
  }
  .rail{padding-bottom:var(--dock)}
  .dock-nav{display:flex}
  .legend{display:none}
  .hud{top:6px;left:6px}
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

/* ── Rail (scrolls as a column so acts stay reachable) ── */
.rail{
  min-width:0;min-height:0;max-width:100%;overflow-x:hidden;overflow-y:auto;
  display:flex;flex-direction:column;
  border-left:1px solid var(--line);background:var(--panel2);
  scroll-padding-bottom:24px;
}
@media (max-width:900px){.rail{border-left:0;border-top:1px solid var(--line)}}
.rail-stack{
  flex:1 1 auto;min-width:0;min-height:200px;max-width:100%;
  display:grid;grid-template-rows:auto minmax(0,1fr);
  border-top:1px solid var(--line);
}

.decision{
  padding:14px 14px 12px;text-align:center;border-bottom:1px solid var(--line);
  background:radial-gradient(80% 100% at 50% 0%, #1e293b55, transparent 70%);
}
.decision.go{--d:var(--go)}
.decision.hold,.decision.brief{--d:var(--hold)}
.decision.abstain{--d:var(--d,var(--abstain));--d:var(--abstain)}
.decision .word{
  font-size:clamp(1.55rem,4vw,2.35rem);font-weight:700;letter-spacing:.04em;
  color:var(--d,#94a3b8);line-height:1.05;margin:0;
}
.decision .code{
  margin-top:6px;font:11px/1 var(--mono);letter-spacing:.14em;
  text-transform:uppercase;color:var(--faint);
}
.decision .one{margin:6px 0 0;font-size:13px;color:var(--text);line-height:1.35}
.decision .kind{margin-top:4px;font-size:10px;color:var(--faint);letter-spacing:.02em;line-height:1.35}
.decision .banner{
  margin-top:8px;padding:7px 8px;border-radius:var(--r);
  border:1px solid var(--line2);background:#0B1220;
  font-size:11px;font-weight:600;color:var(--hold);line-height:1.35;
}
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
.kpi .v.cite{color:var(--cyan)}

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
.vv-scorecard{
  margin:8px 12px;padding:8px 10px;border:1px solid var(--line);border-radius:var(--r);
  background:var(--panel2);font-size:11px;
}
.vv-scorecard b{display:block;font-size:10px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin-bottom:6px}
.vv-scorecard .vv-status{font-family:var(--mono);font-size:10px;color:var(--local);word-break:break-all}
.vv-scorecard .vv-meta{font-size:10px;color:var(--faint);margin-top:4px;line-height:1.35}
.vv-scorecard .vv-note{font-size:9px;color:var(--faint);margin-top:4px}
.weakness-board .wb-fires{margin-top:6px;overflow:auto;max-height:160px}
.weakness-board table{width:100%;border-collapse:collapse;font-size:9px;font-family:var(--mono)}
.weakness-board th,.weakness-board td{text-align:left;padding:2px 4px;border-bottom:1px solid var(--line);color:var(--muted)}
.weakness-board th{color:var(--faint);letter-spacing:.04em;text-transform:uppercase}
.weakness-board .wb-second{margin-top:6px;font-size:10px;color:var(--hold)}
/* A5 split conf: ML conf ≠ ROS conf */
.split-conf{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:6px}
.split-conf .sc-banner{
  grid-column:1 / -1;font-size:9px;color:var(--hold);line-height:1.3;
}
.h1-rehearsal .h1-cmd-row{display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-top:6px}
.h1-rehearsal .h1-cmd-row .h1-cmd{flex:1;min-width:0}
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
  display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;padding:8px 12px 6px;
  width:100%;box-sizing:border-box;
}
.share-acts{
  display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px;padding:0 12px 10px;
  width:100%;box-sizing:border-box;
}
.need-know{
  margin:0 12px 8px;padding:10px 12px;border:1px solid var(--line);
  border-radius:var(--r);background:var(--panel);font-size:12px;
}
.need-know .nk-row{margin:0 0 8px}
.need-know .nk-k{
  font-size:10px;letter-spacing:.07em;text-transform:uppercase;color:var(--faint);font-weight:700;
}
.need-know .nk-v{margin-top:2px;color:var(--text);line-height:1.35}
.need-know .nk-miss{color:var(--hold)}
.need-know .nk-act{color:var(--cyan);font-weight:600}
.intake-hero{margin-bottom:10px}
.intake-hero p{margin:4px 0 0;color:var(--muted);font-size:12px;line-height:1.4}
.dropzone{
  border:1px dashed var(--line2);border-radius:var(--r);padding:18px 12px;text-align:center;
  color:var(--muted);font-size:13px;margin:8px 0;background:var(--panel);cursor:pointer;
}
.dropzone.on{border-color:var(--cyan);color:var(--cyan)}
.intake-files{font-size:11px;color:var(--muted);margin:6px 0 10px;line-height:1.4}
.intake-files .bad{color:var(--hold)}
.intake-name{width:100%;min-height:var(--tap);margin:6px 0 10px;padding:0 10px;
  background:var(--panel);border:1px solid var(--line);border-radius:var(--r)}
/* Non-decision tabs (Meter fotos, Términos…): give the form the rail, keep the word. */
body.tab-work .decision .one,
body.tab-work .decision .kind,
body.tab-work .decision .unc-bar,
body.tab-work .decision .pct,
body.tab-work .kpis,
body.tab-work .need-know,
body.tab-work .next,
body.tab-work .last-act,
body.tab-work .status-strip{display:none}
body.tab-work .decision{padding:10px 12px 8px}
body.tab-work .decision .word{font-size:1.25rem}
body.tab-work .rail-stack{min-height:58vh}
.acts-dock{flex:0 0 auto;min-width:0;max-width:100%;width:100%;box-sizing:border-box}
.pact{
  appearance:none;border:1px solid var(--line);background:var(--panel);
  color:var(--text);border-radius:var(--r);min-height:var(--tap);
  min-width:0;padding:6px 4px;cursor:pointer;display:flex;flex-direction:column;
  align-items:center;justify-content:center;gap:2px;text-align:center;
}
.pact:hover,.pact:focus-visible{border-color:var(--cyan);color:var(--cyan);outline:none}
.pact.main{background:#0c4a6e;border-color:#0369a1;color:#e0f2fe}
.pact.main:hover{filter:brightness(1.1);color:#fff}
.pact .ico{font-size:16px;line-height:1}
.pact .lbl{font-size:11px;font-weight:700;letter-spacing:.02em}
.pact .sub{font-size:9px;color:var(--faint);text-transform:uppercase;letter-spacing:.05em}
.pact.main .sub{color:#7dd3fc}
.src-board,.src-cmp{margin-top:10px;font-size:11px}
.src-board .sb-row{display:flex;justify-content:space-between;gap:8px;padding:4px 0;border-bottom:1px solid var(--line)}
.src-board .miss{color:var(--hold)}
.src-board .ok{color:var(--go)}
.src-cmp{color:var(--muted);margin-top:8px}
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
  scrollbar-width:none;padding:0 4px;min-width:0;max-width:100%;
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

/* ── Status · flip · tools · dock (all formats) ── */
.status-strip{
  display:flex;justify-content:space-between;gap:8px;align-items:center;
  padding:6px 12px;border-bottom:1px solid var(--line);
  font-size:11px;color:var(--muted);background:var(--panel);
}
.status-strip b{color:var(--text);font-weight:600}
.flip-banner{
  margin:8px 12px 0;padding:8px 10px;border:1px solid var(--line);
  border-radius:var(--r);background:var(--panel);color:var(--muted);font-size:12px;line-height:1.35;
}
.flip-banner.on{border-color:var(--hold);color:var(--hold);background:#1c1408}
.mando-tools{
  display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px;padding:0 12px 10px;
  width:100%;box-sizing:border-box;
}
.hud-layers{display:flex;flex-wrap:wrap;gap:6px}
.hud-layers .chip{cursor:pointer}
.hud-layers .chip.off{opacity:.45;text-decoration:line-through}
.dock-nav{
  display:none;position:fixed;left:0;right:0;bottom:0;z-index:30;
  background:var(--panel);border-top:1px solid var(--line);
  padding:4px 6px var(--safe-b);gap:2px;
}
.dock-nav button{
  appearance:none;border:0;background:transparent;color:var(--muted);
  flex:1;min-height:48px;padding:4px 2px;cursor:pointer;
  font-size:10px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;
  display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;
}
.dock-nav button.on{color:var(--cyan)}
.more-sheet{
  position:fixed;left:8px;right:8px;bottom:calc(var(--dock) + 8px);z-index:31;
  background:var(--panel);border:1px solid var(--line);border-radius:8px;
  padding:8px;display:none;grid-template-columns:1fr 1fr;gap:6px;
  box-shadow:0 12px 40px #000a;
}
.more-sheet.on{display:grid}
.more-sheet button{min-height:var(--tap)}
.gsearch{
  width:100%;min-height:var(--tap);margin:0 0 10px;padding:0 10px;
  background:var(--panel);border:1px solid var(--line);border-radius:var(--r);
}
.fcard .word{font-size:11px;font-weight:700;letter-spacing:.04em}
.fcard .word.go{color:var(--go)}
.fcard .word.hold{color:var(--hold)}
.fcard .word.abstain{color:var(--abstain)}

/* Sealed ML experiment: evidence, never an operational confidence score. */
.research-head{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;margin-bottom:10px}
.research-title{font-size:14px;font-weight:700;color:var(--text)}
.research-sub{margin-top:3px;font-size:10px;color:var(--faint);font-family:var(--mono)}
.research-state{display:inline-flex;align-items:center;gap:6px;white-space:nowrap;padding:5px 7px;
  border:1px solid var(--line2);border-radius:999px;color:var(--muted);font:9px/1 var(--mono);text-transform:uppercase}
.research-state i{width:7px;height:7px;border-radius:50%;background:var(--faint)}
.research-state.live i{background:var(--cyan);box-shadow:0 0 0 4px #0ea5e922;animation:research-pulse 1.8s ease-in-out infinite}
.research-state.done i{background:var(--go)}
.research-state.fail i{background:var(--abstain)}
@keyframes research-pulse{0%,100%{box-shadow:0 0 0 3px #0ea5e91c}50%{box-shadow:0 0 0 7px #0ea5e900}}
.research-progress{height:6px;background:var(--line);border-radius:999px;overflow:hidden;margin:8px 0 12px}
.research-progress span{display:block;height:100%;background:linear-gradient(90deg,var(--cyan),#818cf8);width:0}
.research-pipeline{display:grid;grid-template-columns:repeat(auto-fit,minmax(118px,1fr));gap:6px;margin:0 0 12px}
.research-stage{position:relative;min-width:0;padding:9px 8px;border:1px solid var(--line);border-radius:var(--r);background:linear-gradient(145deg,var(--panel),var(--panel2))}
.research-stage .top{display:flex;align-items:center;gap:6px;color:var(--faint);font:8px/1 var(--mono);text-transform:uppercase;letter-spacing:.05em}
.research-stage .top i{width:7px;height:7px;border-radius:50%;background:var(--faint);flex:0 0 auto}
.research-stage b{display:block;margin-top:6px;overflow:hidden;text-overflow:ellipsis;color:var(--text);font-size:10px;white-space:nowrap}
.research-stage small{display:block;margin-top:4px;min-height:22px;color:var(--muted);font:8px/1.35 var(--mono)}
.research-stage .mini{height:3px;margin-top:7px;overflow:hidden;border-radius:9px;background:var(--line)}
.research-stage .mini span{display:block;height:100%;width:0;background:var(--faint);border-radius:9px}
.research-stage.done{border-color:#22c55e44}.research-stage.done .top{color:var(--go)}.research-stage.done .top i,.research-stage.done .mini span{background:var(--go)}
.research-stage.active{border-color:#0ea5e966;box-shadow:inset 0 0 24px #0ea5e908}.research-stage.active .top{color:var(--cyan)}.research-stage.active .top i{background:var(--cyan);box-shadow:0 0 0 4px #0ea5e922}.research-stage.active .mini span{background:linear-gradient(90deg,var(--cyan),#818cf8)}
.research-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}
.research-figure{margin:12px 0 0}.research-figure img{display:block;width:100%;height:auto;border:1px solid var(--line);border-radius:var(--r);background:#fff}
.research-figure figcaption{margin-top:5px;font-size:9px;color:var(--muted)}
.research-stat{min-width:0;padding:9px;border:1px solid var(--line);border-radius:var(--r);background:var(--panel)}
.research-stat .k{font-size:9px;text-transform:uppercase;letter-spacing:.07em;color:var(--faint)}
.research-stat .v{margin-top:3px;font-size:15px;font-weight:700;color:var(--text);font-variant-numeric:tabular-nums}
.research-stat .h{margin-top:3px;font-size:9px;color:var(--muted);line-height:1.25}
.research-stat.accent .v{color:var(--cyan)}
.research-section{margin-top:12px;padding-top:10px;border-top:1px solid var(--line)}
.research-section h3{margin:0 0 7px;font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.research-checks{display:grid;gap:5px}
.research-check{display:flex;gap:7px;align-items:flex-start;font-size:11px;color:var(--muted);line-height:1.3}
.research-check i{flex:0 0 auto;width:15px;height:15px;border-radius:50%;display:grid;place-items:center;
  background:#22c55e1a;color:var(--go);font:10px/1 var(--mono)}
.research-check.pending i{background:#f59e0b1a;color:var(--hold)}
.research-warning{margin-top:10px;padding:8px 9px;border-left:3px solid var(--hold);background:#f59e0b0b;
  color:var(--muted);font-size:10px;line-height:1.35}
.research-path{margin-top:8px;color:var(--faint);font:9px/1.35 var(--mono);word-break:break-all}
.research-board{display:grid;gap:6px}
.research-rank{display:grid;grid-template-columns:24px minmax(0,1fr) 52px;gap:8px;align-items:center;
  padding:8px;border:1px solid var(--line);border-radius:var(--r);background:var(--panel)}
.research-rank.leader{border-color:#0ea5e955;background:linear-gradient(90deg,#0ea5e90d,transparent)}
.research-rank .pos{font:700 11px/1 var(--mono);color:var(--faint);text-align:center}
.research-rank.leader .pos,.research-rank.leader .score{color:var(--cyan)}
.research-rank .run{min-width:0;font-size:10px;font-weight:650;color:var(--text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.research-rank .meta{margin-top:4px;color:var(--faint);font:8px/1.25 var(--mono);white-space:normal}
.research-rank .track{height:3px;margin-top:6px;background:var(--line);border-radius:9px;overflow:hidden}
.research-rank .track i{display:block;height:100%;background:linear-gradient(90deg,var(--cyan),#818cf8);border-radius:9px}
.research-rank .score{text-align:right;font:700 12px/1 var(--mono);color:var(--text)}
.research-queue{display:flex;gap:6px;overflow-x:auto;padding-bottom:3px;scrollbar-width:thin}
.research-job{flex:0 0 auto;max-width:180px;padding:7px 8px;border:1px solid var(--line);border-radius:var(--r);background:var(--panel)}
.research-job b{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:9px;color:var(--muted)}
.research-job span{display:flex;align-items:center;gap:5px;margin-top:4px;color:var(--faint);font:8px/1 var(--mono);text-transform:uppercase}
.research-job span i{width:6px;height:6px;border-radius:50%;background:var(--faint)}
.research-job.active{border-color:#0ea5e955}.research-job.active span{color:var(--cyan)}
.research-job.active span i{background:var(--cyan);box-shadow:0 0 0 3px #0ea5e922}
.research-job.recovered span i{background:var(--go)}
.research-proof{margin-top:7px;display:flex;justify-content:space-between;gap:8px;color:var(--faint);font:8px/1.25 var(--mono)}

@media (min-width:901px){
  #btn-map-expand{display:none}
  #btn-fit{bottom:12px!important}
}
@media (min-width:901px) and (max-width:1199px){
  :root{--rail:min(380px,42vw)}
  .decision .word{font-size:1.6rem}
}
@media (min-width:1600px){
  :root{--rail:440px}
}
@media (orientation:landscape) and (max-height:520px){
  :root{--dock:0px}
  .main{grid-template-columns:minmax(0,1fr) minmax(260px,46vw);grid-template-rows:minmax(0,1fr)}
  .dock-nav,.more-sheet{display:none!important}
  .decision .one,.decision .kind,.unc-bar .unc-note,.legend{display:none}
  .decision .word{font-size:1.2rem}
  .kpis .kpi{padding:6px 8px}
  .rail{padding-bottom:0}
}
@media print{
  .top,.dock-nav,.more-sheet,.fab,.hud,.legend,.acts-dock,.mando-tools,
  .actions-row,.tabs,.toast,.modal-bg{display:none!important}
  .shell,.main{height:auto;display:block}
  .map-wrap{height:32vh;page-break-inside:avoid}
  .rail{border:0;overflow:visible}
  body{overflow:visible;background:#fff;color:#111}
  .decision .word{color:#111}
}
@media (prefers-reduced-motion:reduce){
  *{transition:none!important;animation:none!important}
}
/* Cascade win: dock + unstick acts so they never cover Qué hay / Meter fotos */
@media (max-width:900px){
  .dock-nav{display:flex!important}
  .acts-dock{position:static;order:0;width:100%;max-width:100%}
  body.tab-work .acts-dock,
  body.tab-work .mando-tools{display:none}
  .need-know .nk-row:last-child{margin-bottom:0}
}
@media (max-width:600px){
  .decision .kind,.decision .code{display:none}
  .decision .one{font-size:12px}
  .hud .chip{font-size:9px}
  .dock-nav button{font-size:9px;letter-spacing:.02em;padding:4px 0}
}
""".strip()


def _shell() -> str:
    """Static HTML shell (markers: mode-toggle, primary-acts, last-act, role-seg)."""
    return """
<a class="skip-link" href="#main-content">Saltar al contenido</a>
<div class="shell">
  <header class="top">
    <div class="brand">
      <div class="mark">W</div>
      <b>WFD</b><em>MANDO</em>
    </div>
    <div class="vdiv"></div>
    <div class="top-mid">
      <select id="fire-select" aria-label="Incidente"></select>
      <div class="chips" id="top-chips"></div>
    </div>
    <div class="top-right">
      <div class="seg role-seg adv" id="role-seg" role="group" aria-label="Rol playbook">
        <button type="button" data-role="operator" class="on">Mando</button>
        <button type="button" data-role="field">Campo</button>
        <button type="button" data-role="lab">Lab</button>
        <button type="button" data-role="decision">Analista</button>
      </div>
      <span id="role-hint" class="adv" title="Rol actual"></span>
      <div class="seg mode-toggle" id="mode-toggle" role="group" aria-label="Modo Fácil o Pro">
        <button type="button" id="btn-mode-simple" class="on">Fácil</button>
        <button type="button" id="btn-mode-advanced">Pro</button>
      </div>
      <button type="button" class="icon-btn" id="btn-help" title="Ayuda" aria-label="Ayuda">?</button>
    </div>
  </header>

  <main class="main" id="main-content">
    <section class="map-wrap" aria-label="Mapa">
      <div id="map"></div>
      <div class="hud">
        <div class="chip live"><i></i><span id="map-layer-n">—</span></div>
        <div class="chip" id="map-conn-chip"><i></i><span id="map-conn">—</span></div>
        <div class="hud-layers" id="map-layer-toggles" data-marker="map-layer-toggles"></div>
      </div>
      <div class="legend">
        <div class="row"><span class="sw-line"></span>Frente local</div>
        <div class="row"><span class="sw-pt"></span>FIRMS NRT ≠ perímetro</div>
      </div>
      <button type="button" class="fab" id="btn-map-expand" title="Ampliar mapa" aria-label="Ampliar mapa">▣</button>
      <button type="button" class="fab" id="btn-fit" title="Centrar mapa" aria-label="Centrar" style="bottom:64px">◎</button>
    </section>

    <aside class="rail" aria-label="Panel operativo">
      <div class="status-strip" id="status-strip" data-marker="status-strip">
        <span id="clock">—</span>
        <span id="conn-plain">—</span>
      </div>
      <div class="decision brief" id="hero">
        <div class="word" id="hero-word">—</div>
        <div class="code" id="hero-code"></div>
        <p class="one" id="hero-plain"></p>
        <div class="kind" id="hero-kind" data-marker="hero-orientation">orientación de card · no es GO_Q</div>
        <div class="banner" id="hero-banner">Apoyo a la decisión · no es orden de despacho</div>
        <div class="pct" id="hero-conf"></div>
        <div class="unc-bar" id="uncertainty-bar" data-marker="uncertainty-bar" aria-label="Banda de incertidumbre (no es ROS)">
          <div class="unc-track" role="presentation"><div class="unc-fill" id="unc-fill"></div></div>
          <div class="unc-meta">
            <span id="unc-label">Calidad de la lectura</span>
            <span id="unc-band">—</span>
          </div>
          <div class="unc-note" id="unc-note" data-marker="uncertainty-no-ros"><b>no es ROS</b> · no es la velocidad del frente<span class="adv"> · IoU ≠ ROS · sin inventar scores</span></div>
        </div>
      </div>

      <div class="kpis" id="brief-kv"></div>

      <div class="need-know" id="need-know" data-marker="need-to-know" aria-label="Qué hay y qué falta">
        <div class="nk-row"><div class="nk-k">Qué hay</div><div class="nk-v" id="nk-have">—</div></div>
        <div class="nk-row"><div class="nk-k">Qué falta</div><div class="nk-v nk-miss" id="nk-miss">—</div></div>
        <div class="nk-row"><div class="nk-k">Qué hacer ahora</div><div class="nk-v nk-act" id="nk-act">—</div></div>
      </div>

      <div class="acts-dock">
      <!-- 3 actos prioritarios (mando: Estado / Decidir / Acta bajo la lectura) -->
      <div class="primary-acts" role="group" aria-label="Actos prioritarios">
        <button type="button" class="pact" id="btn-act-status" title="Qué hay en el incendio ahora">
          <span class="ico">▣</span><span class="lbl">Estado</span><span class="sub">qué hay</span>
        </button>
        <button type="button" class="pact main" id="btn-act-decide" title="Leer la tarjeta de este incendio">
          <span class="ico">◆</span><span class="lbl">Decidir</span><span class="sub">leer ahora</span>
        </button>
        <button type="button" class="pact" id="btn-act-acta" title="Guardar acta de auditoría">
          <span class="ico">▤</span><span class="lbl">Acta</span><span class="sub">guardar</span>
        </button>
      </div>
      <div class="share-acts" role="group" aria-label="Congelar y comparar">
        <button type="button" class="pact" id="btn-act-snapshot" title="Congelar este momento (no es despacho)">
          <span class="ico">◉</span><span class="lbl">Congelar</span><span class="sub">momento</span>
        </button>
        <button type="button" class="pact" id="btn-act-compare" title="Qué cambió desde el momento congelado">
          <span class="ico">⇄</span><span class="lbl">Qué cambió</span><span class="sub">comparar</span>
        </button>
      </div>
      <div class="mando-tools" data-marker="mando-tools" role="group" aria-label="Copiar y enviar lectura">
        <button type="button" class="pact" id="btn-copy-lectura" title="Copiar la lectura en castellano">
          <span class="ico">⎘</span><span class="lbl">Copiar lectura</span><span class="sub">para el puesto</span>
        </button>
        <button type="button" class="pact" id="btn-share-lectura" title="Enviar o imprimir la lectura">
          <span class="ico">↗</span><span class="lbl">Enviar</span><span class="sub">o imprimir</span>
        </button>
      </div>
      </div>

      <div class="flip-banner" id="flip-banner" data-marker="flip-banner" hidden></div>
      <div class="next" id="next-box"></div>

      <div class="last-act" id="last-act" aria-live="polite">
        <b>Último acto</b>
        <div class="cmd" id="last-act-cmd">—</div>
        <div class="meta" id="last-act-meta">Pulsa Decidir para leer este incendio. Estado comprueba datos. Acta guarda la auditoría.</div>
        <div class="paths" id="last-act-paths" hidden></div>
        <div class="preview" id="last-act-preview" hidden></div>
        <div class="row-btns" id="last-act-btns" hidden>
          <button type="button" class="btn sm adv" id="btn-copy-act-path">Copiar path</button>
          <button type="button" class="btn sm adv" id="btn-live-replay" title="Replay pack third-party (consistencia forense)">Replay pack</button>
        </div>
      </div>
      <div class="actions-row adv" id="actions-row">
        <button type="button" class="btn primary" id="btn-copy-rebuild">Regenerar en consola</button>
        <button type="button" class="btn" id="btn-copy-map">Solo mapa</button>
        <button type="button" class="btn adv" id="btn-bridge-refresh" style="display:none" title="Refrescar Decision Card vía bridge local">Refrescar card</button>
      </div>

      <div class="rail-stack">
        <div class="tabs" id="main-tabs" role="tablist">
          <button type="button" class="tab on" data-tab="decision">Decisión</button>
          <button type="button" class="tab" data-tab="brief">Resumen</button>
          <button type="button" class="tab" data-tab="actions">Qué hacer</button>
          <button type="button" class="tab" data-tab="newfire">Meter fotos</button>
          <button type="button" class="tab" data-tab="glossary">Términos</button>
          <button type="button" class="tab" data-tab="fires">Incendios</button>
          <button type="button" class="tab adv" data-tab="modelo">Modelo</button>
          <button type="button" class="tab adv" data-tab="eng">Ingeniería</button>
        </div>
        <div class="pane-host">
          <div class="pane on" id="tab-decision">
            <div id="decision-body" class="empty">Sin tarjeta</div>
            <div id="source-board" data-marker="source-board" class="src-board" aria-label="Tablero de fuentes"></div>
            <div id="snapshot-compare" data-marker="snapshot-compare" class="src-cmp"></div>
          </div>
          <div class="pane" id="tab-brief">
            <div class="grid2" id="ops-kv"></div>
            <div class="chips" id="rails" style="margin-top:10px"></div>
            <div class="adv" style="margin-top:10px">
              <button type="button" class="btn sm block" id="btn-copy">Copiar next cmd</button>
              <ol id="seq" style="padding-left:1.1rem;margin:8px 0 0;color:var(--muted);font-size:11px"></ol>
            </div>
          </div>
          <div class="pane" id="tab-actions">
            <div class="filters" id="actions-filters"></div>
            <div id="actions-list"></div>
          </div>
          <div class="pane" id="tab-newfire">
            <div class="intake-hero">
              <b>Meter fotos del incendio</b>
              <p>Tres pasos. No hace falta terminal. Un JPG del móvil no sirve: tienen que ser fotos térmicas con mapa (<code>.tif</code>).</p>
            </div>
            <label class="nk-k" for="intake-fire">Nombre del incendio</label>
            <input id="intake-fire" class="intake-name" type="text" maxlength="40" placeholder="ej. tobarra_norte" autocomplete="off"/>
            <button type="button" class="btn primary block" id="btn-intake-open">1. Abrir carpeta de fotos</button>
            <div class="dropzone" id="intake-drop" tabindex="0">2. Suelta aquí los .tif · o pulsa para elegir</div>
            <input id="intake-file" type="file" accept=".tif,.tiff,image/tiff" multiple hidden/>
            <div class="intake-files" id="intake-files"></div>
            <button type="button" class="btn primary block" id="btn-intake-process">3. Procesar fotos</button>
            <p class="intake-files" id="intake-hint">Con la consola abierta (--serve) los botones hacen el trabajo. Si no, se copia la carpeta.</p>
            <div id="intake-steps" class="adv"></div>
          </div>
          <div class="pane" id="tab-glossary">
            <input id="glossary-search" class="gsearch" type="search" maxlength="40" placeholder="Buscar término…" autocomplete="off" aria-label="Buscar término"/>
            <div id="glossary-list"></div>
          </div>
          <div class="pane" id="tab-fires">
            <div id="fire-list"></div>
          </div>
          <div class="pane" id="tab-modelo">
            <div id="research-status" data-marker="research-status" aria-live="polite"></div>
          </div>
          <div class="pane" id="tab-eng">
            <div class="decision-log adv" id="decision-log" data-marker="decision-log" aria-label="Decision log sidecar">
              <b>Decision log (sidecar ACK)</b>
              <div class="dlog-id" id="dlog-id">id: — (sin sidecar decision_log.jsonl)</div>
              <div class="dlog-meta" id="dlog-meta">Sidecar #31 · no es hero orientación · ACK backend solo con app --serve.</div>
              <div class="dlog-ack">
                <button type="button" class="btn sm" id="btn-dlog-ack" title="ACK sidecar (loopback --serve)">ACK</button>
                <span class="dlog-meta" id="dlog-ack-state">ack: —</span>
              </div>
              <div class="dlog-note" id="dlog-note">fusion ON · no GO_Q invent · sidecar ACK ≠ hero orientación · conf ML ≠ ROS</div>
            </div>
            <div class="vv-scorecard adv" id="vv-scorecard" data-marker="vv-scorecard" aria-label="V&amp;V eng sidecar">
              <b>V&amp;V eng (lectura)</b>
              <div class="vv-status" id="vv-status">sin sidecar vv_scorecard.json</div>
              <div class="vv-meta" id="vv-rails">GO_Q partial · fusion ON · go_q_met=false</div>
              <div class="vv-meta" id="vv-metrics">field IoU/ROS/grade: — (eng_stub · no inventar)</div>
              <div class="vv-note" id="vv-note">lectura #34 · no scores de campo · no es despacho táctico</div>
            </div>
            <div class="vv-scorecard weakness-board adv" id="weakness-board" data-marker="weakness-board" aria-label="Tablero IF (lectura)">
              <b>Tablero IF (lectura)</b>
              <div class="vv-status" id="wb-summary">sin tablero WEAKNESS_BOARD.json</div>
              <div class="vv-meta" id="wb-rails">GO_Q partial · fusion ON · FREEZE · no inventar Vp/ha</div>
              <div class="vv-meta" id="wb-hellin">Hellín: —</div>
              <div class="wb-second" id="wb-second" hidden>1 ancla grade-A (Tobarra) · no inventar 2ª</div>
              <div class="wb-fires" id="wb-fires"></div>
              <div class="vv-note" id="wb-note">lectura · no POST · no promote · no es despacho</div>
            </div>
            <div class="split-conf adv" id="split-conf" data-marker="split-conf" aria-label="Confianza ML vs ROS">
              <div class="sc-banner" id="sc-banner" data-marker="split-conf-banner">Conf. ML ≠ Conf. ROS · no es despacho táctico</div>
              <div class="sc-box ml" data-marker="split-conf-ml">
                <div class="sc-k">Conf. ML / predicción</div>
                <div class="sc-v" id="sc-ml">—</div>
                <div class="sc-h">calidad de card · <b>no es ROS</b></div>
              </div>
              <div class="sc-box ros" data-marker="split-conf-ros">
                <div class="sc-k">Conf. ROS / ops</div>
                <div class="sc-v" id="sc-ros">—</div>
                <div class="sc-h">métrica ops si existe · IoU ≠ ROS · sin inventar</div>
              </div>
            </div>
            <div class="h1-rehearsal adv" id="h1-rehearsal" data-marker="h1-rehearsal" aria-label="Ensayo H1 eng">
              <b>Ensayo H1 eng (12 min)</b>
              <div class="h1-flag" id="h1-goq-flag">go_q_met=false · no es demo tercero · no es acta H1</div>
              <ol id="h1-steps"></ol>
              <div class="h1-cmd-row">
                <div class="h1-cmd" id="h1-serve-cmd">—</div>
                <button type="button" class="btn sm" id="btn-h1-copy-cmd" title="Copiar comando H1 eng">Copiar cmd</button>
              </div>
              <div class="h1-note" id="h1-note">fusion ON · eng dry-run · acta H1 es humana · no inventa GO_Q</div>
            </div>
            <div class="sr-ladder adv" id="sr-ladder" data-marker="sr-ladder" aria-label="Escala SR">
              <b>Escala SR (soporte / recomendación)</b>
              <div class="sr-levels" id="sr-levels"></div>
              <div class="sr-claims" id="sr-claims">Claims Guardian: fusion ON ≠ GO_Q complete ≠ despacho · go_q_met=false · ABSTAIN/HOLD son feature</div>
            </div>
          </div>
        </div>
      </div>
    </aside>
  </main>
</div>

<nav class="dock-nav" id="dock-nav" data-marker="dock-nav" aria-label="Navegación de sala">
  <button type="button" data-view="lectura" class="on">Lectura</button>
  <button type="button" data-view="mapa">Mapa</button>
  <button type="button" data-view="fotos">Fotos</button>
  <button type="button" data-view="mas">Más</button>
</nav>
<div class="more-sheet" id="more-sheet" data-marker="more-sheet">
  <button type="button" class="btn" data-more-tab="brief">Resumen</button>
  <button type="button" class="btn" data-more-tab="actions">Qué hacer</button>
  <button type="button" class="btn" data-more-tab="fires">Incendios</button>
  <button type="button" class="btn" data-more-tab="glossary">Términos</button>
  <button type="button" class="btn adv" data-more-tab="modelo">Modelo</button>
  <button type="button" class="btn" id="more-copy">Copiar lectura</button>
  <button type="button" class="btn" id="more-help">Ayuda</button>
  <button type="button" class="btn" id="more-print">Imprimir</button>
</div>
<div class="modal-bg" id="help-modal">
  <div class="modal" role="dialog" aria-modal="true" aria-labelledby="help-title">
    <h2 id="help-title" style="margin:0 0 10px;font-size:16px">Ayuda rápida</h2>
    <h3>WFD MANDO</h3>
    <ol>
      <li>Palabra grande = qué hacer ahora: <b>SEGUIR</b> / <b>ESPERAR</b> / <b>SE CALLA</b>. No es orden de extinción.</li>
      <li><b>Decidir</b> lee la tarjeta. <b>Estado</b> comprueba datos. <b>Acta</b> guarda la auditoría.</li>
      <li><b>Congelar</b> guarda este momento. <b>Qué cambió</b> alerta en pantalla (no SMS, no despacho).</li>
      <li><b>Copiar lectura</b> saca un parte en castellano para el puesto. Enviar comparte o imprime.</li>
      <li>Cian en el mapa = frente local. Rosa = satélite (no es perímetro oficial). Pulsa las pastillas del mapa para mostrar u ocultar capas.</li>
      <li>En el teléfono: <b>Lectura · Mapa · Fotos · Más</b> abajo. En horizontal se ve mapa y panel juntos.</li>
      <li>Fácil oculta ingeniería. Pro muestra bitácora, V&amp;V y H1. Con <code>--serve</code> el resultado sale en Último acto.</li>
      <li><b>Meter fotos</b> — abrir carpeta, soltar .tif, Procesar. Un JPG del móvil no sirve.</li>
      <li>Teclas: D Decidir · E Estado · A Acta · C Qué cambió · F Congelar · L copiar lectura · M mapa · ? ayuda.</li>
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
const splitConf = P.split_conf || {};
let decisionLog = P.decision_log || {};
const vvScorecard = P.vv_scorecard || {};
const weaknessBoard = P.weakness_board || {};
let researchStatus = P.research_status || {};
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
const intakeGuide = P.intake_guide || {};
let needKnow = P.need_to_know || {};

const WORD = { GO:'SEGUIR', HOLD:'ESPERAR', ABSTAIN:'SE CALLA', BRIEF:'SIN TARJETA' };
const SHORT = {
  GO:'El sistema propone seguir con esta lectura. No es una orden de despacho.',
  HOLD:'Espera: los datos no bastan o chocan. Revisa antes de actuar.',
  ABSTAIN:'El sistema se calla a propósito. Callarse no es un fallo.',
  BRIEF:'Sin tarjeta de este incendio. Pulsa Decidir o elige otro IF.'
};
const SRC_ES = {
  ops:'Operaciones (térmico)',
  open:'Copernicus / abierto',
  ml_live:'Predicción ML',
  reliability:'Fiabilidad del sistema'
};
let uiMode = P.ui_mode === 'advanced' ? 'advanced' : 'simple';
let activeGroup = 'Todos';
let currentRole = P.role || 'operator';
let lastAct = Object.assign({ act:null, cmd:null, ts:null, hint:null }, P.last_act || {});
let mapLayers = [];
let bounds = [];

function fusionRailOn() {
  const r = (rails && rails.field_ops_ml_live_fusion)
    || ((liveOps && liveOps.honesty_rails) || {}).field_ops_ml_live_fusion;
  const s = String(r == null ? '' : r).toUpperCase();
  return s === 'ON' || s === 'TRUE';
}
function fusionRailLabel() {
  return fusionRailOn() ? 'Fusion ON' : 'Fusion OFF';
}
function missingSourceIds(c) {
  const out = [];
  ((c && c.sources) || []).forEach(s => {
    if (s && s.available === false) out.push(String(s.id || '?'));
  });
  ((c && c.reasons) || []).forEach(r => {
    const m = String(r).match(/^missing:(.+)$/);
    if (m) out.push(m[1]);
  });
  return out;
}
function sistemaFail(c) {
  return !!(c && c.system_reliability_pass === false);
}
function sourcesThin(c) {
  const miss = missingSourceIds(c);
  return miss.indexOf('ml_clm_ensemble') >= 0
    || miss.indexOf('open_cems') >= 0
    || miss.indexOf('open_cems_perimeter') >= 0;
}

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
      : (uiMode === 'simple' && lastAct.cmd && String(lastAct.cmd).indexOf('http') === 0
        ? (lastAct.act || 'Hecho')
        : String(lastAct.cmd || '—'));
    cmdEl.textContent = body;
    const t = lastAct.ts ? new Date(lastAct.ts).toLocaleTimeString() : '—';
    const hint = (uiMode === 'simple')
      ? ((lastAct.hint || '').replace(/Live Ops · fusion ON · no shell/g, 'Hecho en pantalla')
        .replace(/sin serve — péguelo en terminal/g, 'Sin consola: el comando se ha copiado'))
      : (lastAct.hint || '');
    metaEl.textContent = (lastAct.act || 'acto') + ' · ' + t + (hint ? ' · ' + hint : '');
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
    cmdEl.textContent = 'Última lectura: ' + (outboxSnap.decision || '—') +
      (outboxSnap.quality_grade ? ' · calidad ' + outboxSnap.quality_grade : '');
    metaEl.textContent = outboxSnap.hint || 'Lo que había en la carpeta al abrir la pantalla.';
    if (pathsEl) pathsEl.hidden = true;
    if (prevEl) prevEl.hidden = true;
    if (btnsEl) btnsEl.hidden = !liveOpsOn();
  } else {
    cmdEl.textContent = '—';
    metaEl.textContent = liveOps.enabled
      ? 'Pulsa Decidir para leer este incendio. Estado comprueba datos. Acta guarda la auditoría.'
      : 'Pulsa Decidir / Estado / Acta. Sin --serve se copia el comando a la consola.';
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
  if (kind === 'snapshot') {
    return fireCmd('snapshot_cmd', 'python -m wildfire_front snapshot --work-dir "DIR" --json');
  }
  if (kind === 'compare') {
    return fireCmd('compare_cmd', 'python -m wildfire_front compare --work-dir "DIR" --json');
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
    replay_third_party: 'Replay', snapshot: 'Instantánea', compare: 'Comparar'
  };
  const label = labels[kind] || kind;
  toast(label + '…');
  try {
    const body = kind === 'replay_third_party'
      ? { bundle: 'outputs/demo_third_party' }
      : (kind === 'compare'
        ? { work_dir: wd }
        : (kind === 'snapshot'
          ? { work_dir: wd, save: true }
          : {
          work_dir: wd,
          policy_id: 'field_ops',
          event_id: (card && card.event_id) || (fireById(fireSel.value) && fireById(fireSel.value).id) || 'SPA_LIVE'
        }));
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
      recordAct(label, url, 'Live error · fusion ON', String(err).slice(0, 200));
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
        (s.latency_ms != null ? ' · ' + s.latency_ms + ' ms' : '') +
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
    } else if (kind === 'snapshot') {
      window._wfdLastSnapshot = data;
      resultLine = String(data.decision || '—') +
        ' · fuentes ' + Object.keys(data.source_board || {}).join('/') +
        (data.saved ? ' · guardada' : '') +
        ' · no despacho · GO_Q ' + ((data.rails || {}).go_q || 'partial');
      renderSourceBoard(data);
    } else if (kind === 'compare') {
      const a = data.alert || {};
      resultLine = (data.flipped ? 'FLIP ' : 'sin flip ') +
        (data.from || '—') + '→' + (data.to || '—') +
        ' · ' + (a.kind || '') +
        (data.against ? ' · ' + data.against : '') +
        (data.confidence_delta != null ? ' · Δconf ' + data.confidence_delta : '') +
        ' · alerta local (no SMS)';
      const cd = data.cited_delta || {};
      if (cd.ros_m_min != null) resultLine += ' · ΔROS ' + cd.ros_m_min;
      if (cd.area_ha != null) resultLine += ' · Δha ' + cd.area_ha;
      if (cd.delta_t_s != null) resultLine += ' · Δt ' + cd.delta_t_s + 's';
      const cmpEl = document.getElementById('snapshot-compare');
      if (cmpEl) {
        cmpEl.textContent = (a.message || resultLine) +
          ' · cifras citadas (null si falta ops) · no despacho';
      }
      paintFlipBanner(data);
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
      'Live Ops · fusion ON · no shell',
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
// Mes2 PR2-A: ACK → Live Ops /live/v1/ack-decision (shipped ack_decision) when --serve
function paintDecisionLog() {
  const dlog = decisionLog || {};
  const dlogId = document.getElementById('dlog-id');
  const dlogMeta = document.getElementById('dlog-meta');
  const st = document.getElementById('dlog-ack-state');
  const noteEl = document.getElementById('dlog-note');
  const did = dlog.decision_id || dlog.id || null;
  const mode = dlog.mode === 'sidecar_read' ? 'sidecar #31' : 'sin sidecar';
  if (dlogId) {
    dlogId.textContent = did
      ? ('id: ' + did + ' · ' + mode)
      : ('id: — (' + mode + ' · no inventa decision_id)');
  }
  if (dlogMeta) {
    const sidecarDec = dlog.mode === 'sidecar_read'
      ? String(dlog.decision || '—').toUpperCase()
      : null;
    const heroDec = String((hero && hero.decision) || (card && card.decision) || '—').toUpperCase();
    const conf = dlog.confidence_pred != null
      ? (' · conf ' + dlog.confidence_pred + ' (no es ROS)')
      : '';
    const gq = 'go_q_met=' + String(dlog.go_q_met === true);
    dlogMeta.textContent = (sidecarDec
      ? ('sidecar log ' + sidecarDec + conf + ' (ACK · no es hero orientación)')
      : ('sin sidecar (no es hero ' + heroDec + ')'))
      + ' · fusion ' + (fusionRailOn() ? 'ON' : 'OFF')
      + ' · ' + gq + ' · ' + (dlog.note || '');
  }
  if (st) {
    if (dlog.acked || (dlog.ack && dlog.ack.acked)) {
      st.textContent = 'ack: acked (sidecar)';
    } else if (dlog.mode === 'sidecar_read' && did) {
      st.textContent = liveOpsOn()
        ? 'ack: pending (pulse ACK · loopback)'
        : 'ack: pending (ACK backend requiere --serve)';
    } else {
      st.textContent = 'ack: — (sin decision_id)';
    }
  }
  if (noteEl) {
    const sidecarDec = dlog.mode === 'sidecar_read'
      ? String(dlog.decision || '').toUpperCase()
      : '';
    const heroDec = String((hero && hero.decision) || (card && card.decision) || '').toUpperCase();
    let note = (fusionRailOn() ? 'fusion ON' : 'fusion OFF')
      + ' · no GO_Q invent · ACK ≠ acta H1 · sidecar ≠ hero orientación · conf ML ≠ ROS';
    if (sidecarDec && heroDec && sidecarDec !== heroDec) {
      note += ' · hero ' + heroDec + ' ≠ sidecar ' + sidecarDec;
    }
    noteEl.textContent = note;
  }
}
async function runDlogAck() {
  const dlog = decisionLog || {};
  const did = dlog.decision_id || dlog.id || null;
  const st = document.getElementById('dlog-ack-state');
  if (!liveOpsOn()) {
    if (st) st.textContent = 'ack: no backend (sin serve · no invent success)';
    recordAct('ACK', 'decision-log', 'ACK backend requiere app --serve · no false success', 'ack_offline');
    toast('ACK backend requiere app --serve');
    return;
  }
  if (!did || dlog.mode !== 'sidecar_read') {
    if (st) st.textContent = 'ack: fail closed (sin decision_id sidecar)';
    toast('Sin decision_id de sidecar');
    return;
  }
  const url = liveUrl('ack_decision');
  if (!url) {
    toast('Endpoint ACK no configurado');
    return;
  }
  const wd = currentWorkDirRel();
  try {
    const resp = await fetch(url, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ work_dir: wd, decision_id: did }),
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok || !data.ok) {
      const err = (data && data.error) || ('http_' + resp.status);
      if (st) st.textContent = 'ack: fail · ' + err;
      recordAct('ACK fail', did, err, 'ack_fail');
      toast('ACK fail · ' + err);
      return;
    }
    decisionLog = Object.assign({}, dlog, {
      acked: true,
      ack: data.ack || { acked: true },
      ack_backend: data.ack || { acked: true },
      decision: data.decision || dlog.decision,
      confidence_pred: data.confidence_pred != null ? data.confidence_pred : dlog.confidence_pred,
    });
    paintDecisionLog();
    recordAct('ACK sidecar', did, data.note || 'acked', 'ack_ok');
    toast('ACK sidecar · decision_log.jsonl');
  } catch (e) {
    if (st) st.textContent = 'ack: error red (no invent success)';
    toast('ACK error · sin false success');
  }
}
const btnDlogAck = document.getElementById('btn-dlog-ack');
if (btnDlogAck) {
  btnDlogAck.onclick = () => { runDlogAck(); };
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
function actSnapshot() {
  if (liveOpsOn()) { runLiveAct('snapshot'); return; }
  copyText(cliCmdFor('snapshot'), 'CLI copiado', { act: 'Instantánea', hint: 'sin serve — péguelo en terminal' });
}
function actCompare() {
  if (liveOpsOn()) { runLiveAct('compare'); return; }
  copyText(cliCmdFor('compare'), 'CLI copiado', { act: 'Comparar', hint: 'sin serve — péguelo en terminal' });
}
function paintFlipBanner(data) {
  const el = document.getElementById('flip-banner');
  if (!el) return;
  if (!data) { el.hidden = true; el.textContent = ''; return; }
  const fromW = WORD[String(data.from || '').toUpperCase()] || data.from || '—';
  const toW = WORD[String(data.to || '').toUpperCase()] || data.to || '—';
  el.hidden = false;
  if (data.flipped) {
    el.className = 'flip-banner on';
    el.textContent = 'La lectura ha cambiado: ' + fromW + ' → ' + toW +
      '. Alerta en esta pantalla. No es SMS ni orden de despacho.';
  } else {
    el.className = 'flip-banner';
    el.textContent = 'Sin cambio de lectura (' + fromW + '). Las cifras citadas siguen abajo. No es despacho.';
  }
}
function lecturaText() {
  const word = String((hero && hero.decision) || (card && card.decision) || 'BRIEF').toUpperCase();
  const cited = ((window._wfdLastSnapshot || P.snapshot || {}).cited) || {};
  const have = (document.getElementById('nk-have') || {}).textContent || '—';
  const miss = (document.getElementById('nk-miss') || {}).textContent || '—';
  const act = (document.getElementById('nk-act') || {}).textContent || '—';
  const fire = (fireSel && fireSel.value) || P.selected_fire_id || '—';
  const ros = cited.ros_m_min != null ? (cited.ros_m_min + ' m/min') : 'sin dato';
  const ha = cited.area_ha != null ? (cited.area_ha + ' ha') : 'sin dato';
  return [
    'WFD MANDO · apoyo a la decisión · no es orden de despacho',
    'Incendio: ' + fire,
    'Lectura: ' + (WORD[word] || word) + (word !== 'BRIEF' ? ' (' + word + ')' : ''),
    (document.getElementById('hero-plain') || {}).textContent || '',
    'Qué hay: ' + have,
    'Qué falta: ' + miss,
    'Qué hacer ahora: ' + act,
    'Velocidad citada: ' + ros,
    'Área citada: ' + ha,
    'Calidad de fotos: ' + (cited.quality_grade || 'sin dato'),
    'GO_Q partial · fusion ON ≠ despacho · no lances medios por esta tarjeta'
  ].filter(Boolean).join('\n');
}
function copyLectura() {
  copyText(lecturaText(), 'Lectura copiada', { act: 'Copiar lectura', hint: 'parte en castellano · no es despacho' });
}
function shareLectura() {
  const t = lecturaText();
  if (navigator.share) {
    navigator.share({ title: 'WFD MANDO', text: t }).then(() => {
      toast('Enviado');
      recordAct('Enviar', 'share', 'parte compartido · no es despacho');
    }).catch(() => copyText(t, 'Lectura copiada'));
    return;
  }
  try { window.print(); toast('Imprimir lectura'); }
  catch (e) { copyText(t, 'Lectura copiada'); }
}
function renderSourceBoard(snap) {
  const el = document.getElementById('source-board');
  if (!el) return;
  const board = (snap && snap.source_board) || ((P.snapshot || {}).source_board) || {};
  const keys = ['ops', 'open', 'ml_live', 'reliability'];
  if (!keys.some((k) => board[k])) { el.textContent = ''; return; }
  el.innerHTML = '<b>Qué fuentes hay</b> · no es despacho · GO_Q partial';
  keys.forEach((k) => {
    const row = board[k] || {};
    const d = document.createElement('div');
    d.className = 'sb-row ' + (row.present ? 'ok' : 'miss');
    const label = SRC_ES[k] || k;
    d.textContent = label + ': ' + (row.present ? 'sí' : 'falta')
      + (row.status ? ' · ' + row.status : '')
      + (row.driver ? ' · ' + row.driver : '');
    el.appendChild(d);
  });
  const cited = (snap && snap.cited) || ((P.snapshot || {}).cited) || {};
  const cite = document.createElement('div');
  cite.className = 'sb-row';
  cite.setAttribute('data-marker', 'cited-instant');
  const ros = cited.ros_m_min != null ? cited.ros_m_min : 'null';
  const area = cited.area_ha != null ? cited.area_ha : 'null';
  const dt = cited.interval_s != null ? cited.interval_s : 'null';
  cite.textContent = 'citado: ROS ' + ros + ' · ha ' + area + ' · Δt ' + dt +
    ' s · frames ' + (cited.n_frames != null ? cited.n_frames : 'null') +
    ' · grade ' + (cited.quality_grade || 'null') +
    ' · no inventado · no despacho';
  el.appendChild(cite);
}

function setMode(mode, quiet) {
  uiMode = mode === 'advanced' ? 'advanced' : 'simple';
  document.body.classList.toggle('mode-simple', uiMode === 'simple');
  document.body.classList.toggle('mode-advanced', uiMode === 'advanced');
  document.getElementById('btn-mode-simple').classList.toggle('on', uiMode === 'simple');
  document.getElementById('btn-mode-advanced').classList.toggle('on', uiMode === 'advanced');
  if (uiMode === 'simple') {
    const proTab = document.querySelector(
      '#main-tabs .tab.on[data-tab="eng"], #main-tabs .tab.on[data-tab="modelo"]'
    );
    if (proTab) {
      const decTab = document.querySelector('#main-tabs .tab[data-tab="decision"]');
      if (decTab) decTab.click();
    }
  }
  renderActions(); renderIntake(); updateRoleUi(true);
  applyHero(hero);
  renderDecisionTab();
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
  const decNow = String((hero && hero.decision) || (card && card.decision) || 'BRIEF').toUpperCase();
  const reserved = decNow === 'GO' && (sistemaFail(card) || sourcesThin(card));
  const nextMando = reserved
    ? 'Hay lectura, pero faltan fuentes. No lances medios por esta tarjeta.'
    : (SHORT[decNow] || nextShort);
  const nextBody = uiMode === 'simple' ? nextMando : nextShort;
  document.getElementById('next-box').innerHTML =
    '<b>Qué hacer ahora</b>' +
    nextBody + (uiMode === 'advanced' && roleShort
      ? '<div style="margin-top:4px;font-size:10px;color:var(--faint)">' + roleShort + '</div>'
      : '');
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
addTop(fusionRailLabel(), fusionRailOn() ? 'ok' : 'warn');
addTop((P.fire_count || fires.length || 0) + ' IF', 'live');
if (liveOps && liveOps.enabled) addTop('Live Ops', 'live');
const light = hero.overall_light || brief.overall_light || '—';
addTop(light, light === 'VERDE' ? 'ok' : (light === 'ROJO' ? 'err' : 'warn'));
if (pack && pack.enabled) addTop('Pack ' + (pack.n || 0), 'live');

// Tabs — Meter fotos / Resumen / etc. must scroll into view (mando: the form is below the fold).
function revealTabWork(tabId) {
  const work = Boolean(tabId && tabId !== 'decision');
  document.body.classList.toggle('tab-work', work);
  const rail = document.querySelector('.rail');
  const stack = document.querySelector('.rail-stack');
  if (!rail || !stack) return;
  if (!work) {
    rail.scrollTop = 0;
    return;
  }
  rail.scrollTop = Math.max(0, stack.offsetTop - rail.offsetTop);
}
function openTab(tabId, quiet) {
  const btn = document.querySelector('#main-tabs .tab[data-tab="' + tabId + '"]');
  if (!btn) return;
  document.querySelectorAll('#main-tabs .tab').forEach(b => {
    const on = b === btn;
    b.classList.toggle('on', on);
    b.setAttribute('aria-selected', String(on));
    b.tabIndex = on ? 0 : -1;
  });
  document.querySelectorAll('.pane').forEach(p => {
    const on = p.id === 'tab-' + tabId;
    p.classList.toggle('on', on);
    p.hidden = !on;
  });
  const pane = document.getElementById('tab-' + tabId);
  revealTabWork(tabId);
  if (!quiet && tabId === 'newfire') setView('fotos', true);
}
const tabButtons = Array.from(document.querySelectorAll('#main-tabs .tab'));
tabButtons.forEach(btn => {
  btn.setAttribute('role', 'tab');
  btn.setAttribute('aria-controls', 'tab-' + btn.dataset.tab);
  btn.onclick = () => openTab(btn.dataset.tab);
});
document.querySelectorAll('.pane').forEach(pane => {
  pane.setAttribute('role', 'tabpanel');
  pane.setAttribute('aria-labelledby', 'tab-btn-' + pane.id.replace('tab-', ''));
});
tabButtons.forEach(btn => { btn.id = 'tab-btn-' + btn.dataset.tab; });
const initialTab = document.querySelector('#main-tabs .tab.on') || tabButtons[0];
if (initialTab) openTab(initialTab.dataset.tab, true);
document.getElementById('main-tabs').addEventListener('keydown', (event) => {
  if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
  const visible = tabButtons.filter(btn => getComputedStyle(btn).display !== 'none');
  const at = Math.max(0, visible.indexOf(document.activeElement));
  let next = at;
  if (event.key === 'ArrowLeft') next = (at - 1 + visible.length) % visible.length;
  if (event.key === 'ArrowRight') next = (at + 1) % visible.length;
  if (event.key === 'Home') next = 0;
  if (event.key === 'End') next = visible.length - 1;
  event.preventDefault();
  visible[next].focus();
  openTab(visible[next].dataset.tab);
});
try {
  const want = new URLSearchParams(location.search).get('tab');
  if (want) openTab(want, true);
} catch (e) {}

function setView(view, quiet) {
  const v = view || 'lectura';
  ['lectura', 'mapa', 'fotos', 'mas'].forEach((name) => {
    document.body.classList.toggle('view-' + name, name === v);
  });
  document.querySelectorAll('#dock-nav button').forEach((b) => {
    b.classList.toggle('on', b.dataset.view === v);
  });
  const sheet = document.getElementById('more-sheet');
  if (sheet && v !== 'mas') sheet.classList.remove('on');
  if (v === 'fotos') openTab('newfire', true);
  if (v === 'lectura') {
    openTab('decision', true);
    const rail = document.querySelector('.rail');
    if (rail) rail.scrollTop = 0;
  }
  if (v === 'mapa') {
    setTimeout(() => { try { map.invalidateSize({ animate: false }); } catch (e) {} }, 60);
  }
  if (!quiet) {
    toast(v === 'lectura' ? 'Lectura' : (v === 'mapa' ? 'Mapa' : (v === 'fotos' ? 'Meter fotos' : 'Más')));
  }
}
function toggleMapFocus() {
  const on = document.body.classList.contains('view-mapa');
  setView(on ? 'lectura' : 'mapa');
}

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
  const sysFail = sistemaFail(card);
  const thin = sourcesThin(card);
  // Card GO + sistema FAIL / missing artifacts is orientation, not product GO
  let cls = ({GO:'go',HOLD:'hold',ABSTAIN:'abstain',BRIEF:'brief'}[word] || 'brief');
  if (word === 'GO' && (sysFail || thin)) cls = 'hold';
  heroEl.className = 'decision ' + cls;
  document.getElementById('hero-word').textContent = WORD[word] || word;
  const codeEl = document.getElementById('hero-code');
  if (codeEl) codeEl.textContent = word === 'BRIEF' ? '' : word;
  document.getElementById('hero-plain').textContent = SHORT[word] || (hero.plain || '');
  const kindEl = document.getElementById('hero-kind');
  if (kindEl) {
    const dlogDec = (decisionLog && decisionLog.mode === 'sidecar_read')
      ? String(decisionLog.decision || '').toUpperCase()
      : '';
    let kind = 'orientación de card · no es GO_Q';
    if (uiMode === 'simple') {
      if (word === 'GO' && (sysFail || thin)) {
        kind = 'Faltan fuentes — trátalo como espera. No es una orden.';
      } else if (word === 'GO') {
        kind = 'Orientación de apoyo. No es una orden de despacho.';
      } else if (word === 'HOLD') {
        kind = 'Espera y revisa. No es una orden de despacho.';
      } else if (word === 'ABSTAIN') {
        kind = 'El sistema se calla. Callarse no es un fallo.';
      } else {
        kind = 'Sin tarjeta de este incendio.';
      }
    } else {
      if (word === 'GO') {
        kind = 'orientación de card (no es GO_Q · no es despacho)';
        if (sysFail || thin) kind += ' · sistema FAIL / fuentes incompletas';
      }
      if (dlogDec && dlogDec !== word) {
        kind += ' · sidecar log ' + dlogDec + ' (ACK) ≠ hero';
      }
    }
    kindEl.textContent = kind;
  }
  const bannerEl = document.getElementById('hero-banner');
  if (bannerEl) {
    bannerEl.textContent = (word === 'GO' && (sysFail || thin))
      ? 'Con reservas · apoyo a la decisión · no es orden de despacho'
      : 'Apoyo a la decisión · no es orden de despacho';
  }
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
  if (labelEl) {
    labelEl.textContent = uiMode === 'simple'
      ? 'Calidad de la lectura (no es ROS)'
      : ((ub && ub.label) || 'Conf. predicción (no es ROS)');
  }
  const noteEl = document.getElementById('unc-note');
  if (noteEl) {
    // Keep bold **no es ROS** emphasis for honesty pin (Mes2 PR1-A)
    noteEl.innerHTML = '<b>no es ROS</b> · no es la velocidad del frente'
      + '<span class="adv"> · IoU ≠ ROS · banda de calidad existente, sin inventar scores</span>';
  }
  // A5 / PR3-A split conf: prefer server split_conf (existing fields only)
  const scMl = document.getElementById('sc-ml');
  const scRos = document.getElementById('sc-ros');
  const scBan = document.getElementById('sc-banner');
  const sc = splitConf || {};
  if (scBan && sc.banner) scBan.textContent = sc.banner;
  if (scMl) {
    if (sc.ml && sc.ml.display) scMl.textContent = sc.ml.display;
    else scMl.textContent = conf != null ? (Math.round(conf * 100) + '% · ' + band) : '—';
  }
  if (scRos) {
    if (sc.ros && sc.ros.display) {
      scRos.textContent = sc.ros.display;
    } else {
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
  }
  // A4/A8/PR2-A decision-log surface (real #31 sidecar or honest empty)
  paintDecisionLog();
  paintVvScorecard();
  paintWeaknessBoard();
  renderH1Eng();
  renderSrLadder();
}

function paintVvScorecard() {
  const vv = vvScorecard || {};
  const st = document.getElementById('vv-status');
  const railsEl = document.getElementById('vv-rails');
  const metEl = document.getElementById('vv-metrics');
  const noteEl = document.getElementById('vv-note');
  const mode = vv.mode === 'sidecar_read' ? 'sidecar #34' : 'sin sidecar';
  const status = vv.status || '—';
  if (st) {
    st.textContent = vv.mode === 'sidecar_read'
      ? (mode + ' · ' + status + ' · eng_stub')
      : (mode + ' · vv_scorecard.json');
  }
  if (railsEl) {
    railsEl.textContent = 'GO_Q ' + String(vv.go_q || 'partial')
      + ' · fusion ' + String(vv.field_ops_fusion || 'OFF')
      + ' · go_q_met=' + String(vv.go_q_met === true);
  }
  if (metEl) {
    metEl.textContent = 'field IoU/ROS/grade: — (eng_stub · no inventar)';
  }
  if (noteEl) {
    noteEl.textContent = vv.note || 'lectura · no scores de campo · no es despacho';
  }
}

function _wbDash(v) {
  return (v === null || v === undefined || v === '') ? '—' : String(v);
}

function paintWeaknessBoard() {
  const wb = weaknessBoard || {};
  const sumEl = document.getElementById('wb-summary');
  const railsEl = document.getElementById('wb-rails');
  const hellinEl = document.getElementById('wb-hellin');
  const secondEl = document.getElementById('wb-second');
  const firesEl = document.getElementById('wb-fires');
  const noteEl = document.getElementById('wb-note');
  const empty = wb.empty === true || wb.mode !== 'board_read';
  if (sumEl) {
    if (empty) {
      sumEl.textContent = 'sin tablero WEAKNESS_BOARD.json · no inventar conteos';
    } else {
      sumEl.textContent = 'n_fires=' + _wbDash(wb.n_fires)
        + ' · confirmed=' + _wbDash(wb.n_confirmed)
        + ' · ml_strong=' + _wbDash(wb.n_ml_strong)
        + ' · NO_USE=' + _wbDash(wb.n_no_use)
        + ' · grade_a=' + _wbDash(wb.grade_a_ops_anchors);
    }
  }
  if (railsEl) {
    railsEl.textContent = 'GO_Q ' + String(wb.go_q || 'partial')
      + ' · fusion ' + String(wb.field_ops_ml_fusion || 'ON')
      + ' · FREEZE=' + String(wb.freeze_ml !== false)
      + ' · go_q_met=' + String(wb.go_q_met === true)
      + ' · no inventar Vp/ha';
  }
  if (hellinEl) {
    hellinEl.textContent = 'Hellín: ' + _wbDash(wb.hellin_status);
  }
  const second = wb.second_anchor || {};
  if (secondEl) {
    const showSecond = second.visible === true
      && Number(second.grade_a_ops_anchors) >= 2
      && Number(second.n_confirmed_cited) >= 2;
    secondEl.hidden = !showSecond;
    secondEl.textContent = showSecond
      ? String(second.copy || '')
      : '1 ancla grade-A (Tobarra) · no inventar 2ª';
    if (!showSecond) {
      secondEl.hidden = false;
    }
  }
  if (firesEl) {
    firesEl.innerHTML = '';
    const rows = Array.isArray(wb.fires) ? wb.fires : [];
    if (!empty && rows.length) {
      const tbl = document.createElement('table');
      const thead = document.createElement('thead');
      const hr = document.createElement('tr');
      ['fire_id', 'class', 'status', 'use', 'gap', 'Vp', 'ha'].forEach(h => {
        const th = document.createElement('th');
        th.textContent = h;
        hr.appendChild(th);
      });
      thead.appendChild(hr);
      tbl.appendChild(thead);
      const tb = document.createElement('tbody');
      rows.forEach(r => {
        const tr = document.createElement('tr');
        const cells = [
          r.fire_id,
          r.honesty_class,
          r.status,
          r.use_flag,
          r.blocking_gap,
          r.vp_m_min_cited,
          r.area_ha_cited,
        ];
        cells.forEach(c => {
          const td = document.createElement('td');
          td.textContent = _wbDash(c);
          tr.appendChild(td);
        });
        tb.appendChild(tr);
      });
      tbl.appendChild(tb);
      firesEl.appendChild(tbl);
    }
  }
  if (noteEl) {
    noteEl.textContent = wb.note || 'lectura · no POST · no promote · no es despacho';
  }
}

function renderH1Eng() {
  const flag = document.getElementById('h1-goq-flag');
  const stepsEl = document.getElementById('h1-steps');
  const cmdEl = document.getElementById('h1-serve-cmd');
  const noteEl = document.getElementById('h1-note');
  const h1 = h1Eng || {};
  if (flag) {
    flag.textContent = 'go_q_met=' + String(h1.go_q_met === true ? true : false)
      + ' · eng dry-run · no es demo tercero · no es acta H1';
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
      || 'fusion ON · go_q_met=false · acta H1 es humana · no inventa GO_Q';
  }
}
const btnH1Copy = document.getElementById('btn-h1-copy-cmd');
if (btnH1Copy) {
  btnH1Copy.onclick = () => {
    const cmd = (h1Eng && (liveOpsOn() ? h1Eng.serve_cmd : h1Eng.offline_cmd))
      || (liveOpsOn()
        ? 'python -m wildfire_front app --serve'
        : 'python -m wildfire_front app --open');
    copyText(cmd, 'H1 cmd copiado', { act: 'H1 eng', hint: 'eng dry-run · no acta tercero' });
  };
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

function researchScore(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n.toFixed(3) : '—';
}
function researchClock(value) {
  const time = new Date(value || '');
  if (!Number.isFinite(time.getTime())) return '';
  return time.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
}
function researchStat(parent, key, value, hint, accent) {
  const card = document.createElement('div');
  card.className = 'research-stat' + (accent ? ' accent' : '');
  const k = document.createElement('div'); k.className = 'k'; k.textContent = key;
  const v = document.createElement('div'); v.className = 'v'; v.textContent = value;
  const h = document.createElement('div'); h.className = 'h'; h.textContent = hint;
  card.append(k, v, h); parent.appendChild(card);
}
function researchCheck(parent, text, pass) {
  const row = document.createElement('div');
  row.className = 'research-check' + (pass ? '' : ' pending');
  const icon = document.createElement('i'); icon.textContent = pass ? '✓' : '·';
  const label = document.createElement('span'); label.textContent = text;
  row.append(icon, label); parent.appendChild(row);
}
function researchStage(parent, label, status, detail, progressValue) {
  const stage = document.createElement('div');
  stage.className = 'research-stage ' + String(status || 'pending');
  const top = document.createElement('div'); top.className = 'top';
  const dot = document.createElement('i');
  const state = document.createElement('span');
  state.textContent = status === 'done' ? 'cerrado' : (status === 'active' ? 'en curso' : 'pendiente');
  top.append(dot, state);
  const name = document.createElement('b'); name.textContent = label;
  const note = document.createElement('small'); note.textContent = detail || 'sin artefacto todavía';
  const mini = document.createElement('div'); mini.className = 'mini';
  const fill = document.createElement('span');
  fill.style.width = String(Math.max(0, Math.min(100, Number(progressValue) || 0))) + '%';
  mini.appendChild(fill); stage.append(top, name, note, mini); parent.appendChild(stage);
}
function researchRunName(value) {
  return String(value || 'sin nombre').replaceAll('_', ' ');
}
function renderValidationBoard(parent, rows, evidence) {
  if (!rows.length) return;
  const section = document.createElement('div'); section.className = 'research-section';
  const title = document.createElement('h3');
  title.textContent = 'Clasificacion VAL · ' + String(evidence.events || '—') + ' incendios';
  const board = document.createElement('div'); board.className = 'research-board';
  const maxScore = Math.max(...rows.map(row => Number(row.event_macro_iou) || 0), 0.001);
  rows.forEach((row, index) => {
    const item = document.createElement('div');
    item.className = 'research-rank' + (index === 0 ? ' leader' : '');
    const pos = document.createElement('div'); pos.className = 'pos'; pos.textContent = '#' + String(row.rank || index + 1);
    const body = document.createElement('div');
    const run = document.createElement('div'); run.className = 'run'; run.textContent = researchRunName(row.run_name);
    const ci = row.event_bootstrap_95_ci || [];
    const delta = Number(row.delta_from_leader);
    const meta = document.createElement('div'); meta.className = 'meta';
    meta.textContent = (ci.length === 2 ? ('IC95 ' + researchScore(ci[0]) + '–' + researchScore(ci[1])) : 'IC pendiente')
      + (index ? (' · Δ lider −' + researchScore(delta)) : ' · lider provisional');
    const track = document.createElement('div'); track.className = 'track';
    const fill = document.createElement('i'); fill.style.width = String(Math.max(3, 100 * Number(row.event_macro_iou || 0) / maxScore)) + '%';
    track.appendChild(fill); body.append(run, meta, track);
    const score = document.createElement('div'); score.className = 'score'; score.textContent = researchScore(row.event_macro_iou);
    item.append(pos, body, score); board.appendChild(item);
  });
  const proof = document.createElement('div'); proof.className = 'research-proof';
  const proofLeft = document.createElement('span'); proofLeft.textContent = String(evidence.candidate_count || rows.length) + ' candidatos · bootstrap ' + String(evidence.bootstrap_resamples || '—');
  const proofRight = document.createElement('span'); proofRight.textContent = evidence.test_evaluated === false ? 'TEST SELLADO' : 'TEST desconocido';
  proof.append(proofLeft, proofRight); section.append(title, board, proof); parent.appendChild(section);
}
function renderExperimentQueue(parent, jobs) {
  if (!jobs.length) return;
  const section = document.createElement('div'); section.className = 'research-section';
  const title = document.createElement('h3'); title.textContent = 'Cola nocturna de experimentos';
  const queue = document.createElement('div'); queue.className = 'research-queue';
  jobs.forEach(job => {
    const item = document.createElement('div'); item.className = 'research-job ' + String(job.status || 'submitted');
    const name = document.createElement('b'); name.textContent = researchRunName(job.run_name);
    const state = document.createElement('span'); const dot = document.createElement('i');
    const stateText = document.createElement('em'); stateText.textContent = String(job.status || 'submitted');
    state.append(dot, stateText); item.append(name, state); queue.appendChild(item);
  });
  section.append(title, queue); parent.appendChild(section);
}
function renderResearchStatus() {
  const host = document.getElementById('research-status');
  if (!host) return;
  host.innerHTML = '';
  const rs = researchStatus || {};
  const head = document.createElement('div'); head.className = 'research-head';
  const copy = document.createElement('div');
  const title = document.createElement('div'); title.className = 'research-title'; title.textContent = 'RCDA · experimento sellado';
  const sub = document.createElement('div'); sub.className = 'research-sub';
  const refreshedAt = researchClock(rs.updated_at);
  sub.textContent = (rs.phase_label || 'Sin ejecución registrada') + (refreshedAt ? (' · ' + refreshedAt) : '');
  copy.append(title, sub);
  const state = document.createElement('div');
  const stateDone = rs.phase === 'complete';
  const stateFail = rs.status === 'error';
  state.className = 'research-state' + (rs.training_live ? ' live' : (stateDone ? ' done' : (stateFail ? ' fail' : '')));
  const dot = document.createElement('i');
  const stateText = document.createElement('span');
  const liveBackend = rs.execution_backend === 'gcp_cpu_spot' ? 'GCP Spot activo' : (rs.execution_backend === 'kaggle_gpu' ? 'Kaggle T4 activo' : 'GPU activa');
  const liveEpoch = (rs.training_progress || {}).epoch;
  stateText.textContent = rs.training_live ? (liveBackend + (liveEpoch ? (' · época ' + liveEpoch) : '')) : (stateFail ? 'error' : (stateDone ? 'terminado' : (rs.status || 'pendiente')));
  state.append(dot, stateText); head.append(copy, state); host.appendChild(head);

  const progress = document.createElement('div'); progress.className = 'research-progress';
  const fill = document.createElement('span');
  const progressByPhase = {not_started:0, validation_only_tuning:20, validation_only_stage2:48, validation_only_stage2_gcp:48, validation_only_stage2_precision_gcp:52, validation_only_stage2_precision_kaggle:52, validation_only_stage2_low_lr_gcp:55, validation_only_stage2_low_lr_kaggle:55, validation_only_stage2_growth_gcp:58, validation_only_stage2_growth_kaggle:58, validation_only_stage2_growth_low_lr_kaggle:59, validation_only_stage2_event_balanced_gcp:60, validation_only_stage2_event_balanced_kaggle:60, validation_only_stage2_uniform_events_gcp:62, validation_only_stage2_uniform_events_kaggle:62, validation_only_stage2_film_gcp:64, validation_only_stage2_film_kaggle:64, recipe_frozen:66, preregistered_final_test:84, preregistered_final_test_gcp:84, preregistered_final_test_kaggle:84, complete:100};
  fill.style.width = String(progressByPhase[rs.phase] || 0) + '%'; progress.appendChild(fill); host.appendChild(progress);

  const protocol = rs.protocol || {};
  const baseline = rs.baseline || {};
  const wfigs = rs.wfigs || {};
  const winner = rs.validation_winner || {};
  const frozenTestRecipe = rs.frozen_test_recipe || {};
  const valEnsemble = rs.validation_ensemble || {};
  const valPostprocess = rs.validation_postprocess || {};
  const valReproducibility = rs.validation_reproducibility || {};
  const valReplications = rs.validation_replications || {};
  const valStrata = rs.validation_strata || {};
  const samplerAudit = rs.training_sampler_audit || {};
  const numericStability = rs.numeric_stability || {};
  const final = rs.final || {};
  const strongest = baseline.strongest_learned || {};
  const pipeline = document.createElement('div'); pipeline.className = 'research-pipeline';
  const rcdaClosed = rs.phase === 'complete' && final.model_event_macro_iou != null;
  const testDone = wfigs.external_evaluation_executed === true;
  const testActive = !testDone && String(wfigs.test_materialization_phase || '').indexOf('waiting') < 0 && Boolean(wfigs.test_materialization_phase);
  const testTotal = Number(wfigs.test_groups_total || 0);
  const testComplete = Number(wfigs.test_groups_complete || 0);
  const testProgress = testDone ? 100 : (testTotal > 0 ? 100 * testComplete / testTotal : 0);
  const hasScaleupAdaptation = Boolean(wfigs.scaleup_adaptation_phase);
  const adaptDone = hasScaleupAdaptation
    ? wfigs.scaleup_adaptation_phase === 'complete'
    : wfigs.adapted_evaluation_executed === true;
  const adaptActive = wfigs.scaleup_adaptation_active === true
    || (!adaptDone && String(wfigs.adaptation_phase || '').indexOf('training') >= 0);
  const scaleupPhase = String(wfigs.dataset_phase || '');
  const scaleupActive = Boolean(scaleupPhase) && scaleupPhase !== 'complete';
  const scaleupDone = scaleupPhase === 'complete';
  researchStage(pipeline, 'RCDA sellado', rcdaClosed ? 'done' : 'active', rcdaClosed ? (String(final.events || 0) + ' incendios · TEST cerrado') : 'receta y métricas en curso', rcdaClosed ? 100 : 50);
  researchStage(pipeline, 'WFIGS TEST', testDone ? 'done' : (testActive ? 'active' : 'pending'), testDone ? (String(wfigs.test_tensors || 0) + ' tensores evaluados') : (String(testComplete) + '/' + String(testTotal || '—') + ' grupos materializados'), testProgress);
  const adaptDetail = adaptDone
    ? (wfigs.scaleup_prospective_test_evaluated ? 'TRAIN/VAL congelado · TEST prospectivo ejecutado' : 'adaptación histórica completada')
    : (researchRunName(wfigs.scaleup_adaptation_recipe || wfigs.adaptation_phase || 'esperando TEST')
      + (hasScaleupAdaptation ? ' · TEST prospectivo cerrado' : ''));
  researchStage(pipeline, 'Adaptación', adaptDone ? 'done' : (adaptActive ? 'active' : 'pending'), adaptDetail, adaptDone ? 100 : (adaptActive ? 55 : 0));
  researchStage(pipeline, 'Escalado WFIGS', scaleupDone ? 'done' : (scaleupActive ? 'active' : 'pending'), scaleupActive ? researchRunName(scaleupPhase) : (scaleupDone ? (String(wfigs.train_tensors || 0) + ' TRAIN · ' + String(wfigs.validation_tensors || 0) + ' VAL') : 'cohorte siguiente pendiente'), scaleupDone ? 100 : (scaleupActive ? 45 : 0));
  host.appendChild(pipeline);
  const grid = document.createElement('div'); grid.className = 'research-grid';
  researchStat(grid, 'Datos sellados', String(protocol.samples || 0), String(protocol.events || 0) + ' incendios');
  researchStat(grid, strongest.event_macro_iou != null ? 'Rival aprendido TEST' : 'Baseline TEST', researchScore(strongest.event_macro_iou != null ? strongest.event_macro_iou : baseline.event_macro_iou), strongest.event_macro_iou != null ? ('IoU macro · ' + (strongest.name || 'modelo sellado')) : 'IoU macro · copia dilatada');
  if (final.model_event_macro_iou != null) {
    researchStat(grid, 'Modelo TEST', researchScore(final.model_event_macro_iou), String(final.events || protocol.splits?.test?.events || '—') + ' incendios', true);
    researchStat(grid, 'Delta pareado', (Number(final.paired_delta) >= 0 ? '+' : '') + researchScore(final.paired_delta), 'bootstrap por incendio');
    if ((final.model_event_macro_ci || []).length === 2) {
      researchStat(grid, 'IC95% modelo', researchScore(final.model_event_macro_ci[0]) + '–' + researchScore(final.model_event_macro_ci[1]), 'bootstrap por incendio');
    }
    if (final.ensemble_event_macro_iou != null) {
      const ensembleCi = final.ensemble_event_macro_ci || [];
      researchStat(grid, 'Ensemble TEST', researchScore(final.ensemble_event_macro_iou), ensembleCi.length === 2 ? ('IC95% ' + researchScore(ensembleCi[0]) + '–' + researchScore(ensembleCi[1])) : 'secundario · promedio de probabilidades', true);
    }
    if (final.ensemble_vs_strongest_delta != null) {
      const strongestCi = final.ensemble_vs_strongest_delta_ci || [];
      researchStat(grid, 'Ensemble vs rival', (Number(final.ensemble_vs_strongest_delta) >= 0 ? '+' : '') + researchScore(final.ensemble_vs_strongest_delta), strongestCi.length === 2 ? ('IC95% ' + researchScore(strongestCi[0]) + '–' + researchScore(strongestCi[1])) : 'comparación pareada');
    }
    if (final.decoder_event_macro_iou != null) {
      researchStat(grid, 'Decoder TEST', researchScore(final.decoder_event_macro_iou), 'secundario · geometría congelada en VAL');
    }
  } else if (winner.event_macro_iou != null) {
    const winnerDetail = winner.frozen ? (winner.run_name || winner.model_name || 'receta congelada') : ((winner.run_name || winner.model_name || 'receta') + ' · provisional');
    researchStat(grid, winner.frozen ? 'Mejor VAL' : 'Líder VAL', researchScore(winner.event_macro_iou), winnerDetail, true);
    researchStat(grid, 'Umbral VAL', researchScore(winner.threshold), 'época ' + (winner.best_epoch ?? '—'));
    if (winner.delta_vs_runner_up != null) {
      const deltaCi = winner.delta_vs_runner_up_95_ci || [];
      const deltaHint = deltaCi.length === 2
        ? ('IC 95% ' + researchScore(deltaCi[0]) + '–' + researchScore(deltaCi[1]))
        : 'bootstrap pareado por incendio';
      researchStat(grid, 'Delta vs 2º VAL', '+' + researchScore(winner.delta_vs_runner_up), deltaHint);
    }
    if ((winner.event_bootstrap_95_ci || []).length === 2) {
      researchStat(grid, 'IC 95% líder', researchScore(winner.event_bootstrap_95_ci[0]) + '–' + researchScore(winner.event_bootstrap_95_ci[1]), 'bootstrap por 106 incendios');
    }
    if (valReproducibility.reproducible === true) {
      const replicaEvents = String(valReproducibility.events || 0);
      const replicaHash = String(valReproducibility.checkpoint_sha256 || '').slice(0, 10);
      researchStat(grid, 'Réplica independiente', 'exacta', replicaEvents + ' incendios · pesos ' + replicaHash + '… · TEST sellado');
    }
    if (valReplications.event_macro_iou_seed_mean != null) {
      const seedStd = Number(valReplications.sample_std_across_seeds);
      const replicationCi = valReplications.event_bootstrap_95_ci || [];
      const replicationHint = String(valReplications.seed_count || (valReplications.seeds || []).length)
        + ' semillas · σ ' + (Number.isFinite(seedStd) ? researchScore(seedStd) : '—')
        + (replicationCi.length === 2 ? (' · IC 95% ' + researchScore(replicationCi[0]) + '–' + researchScore(replicationCi[1])) : '')
        + ' · TEST sellado';
      researchStat(grid, 'Réplicas fijas VAL', researchScore(valReplications.event_macro_iou_seed_mean), replicationHint, true);
    }
    if (valReplications.ensemble_event_macro_iou != null) {
      const replicationDelta = Number(valReplications.ensemble_delta_vs_best_individual);
      const replicationDeltaCi = valReplications.ensemble_delta_95_ci || [];
      const ensembleHint = (Number.isFinite(replicationDelta) ? ((replicationDelta >= 0 ? '+' : '') + researchScore(replicationDelta) + ' vs mejor semilla') : 'promedio de probabilidades')
        + (replicationDeltaCi.length === 2 ? (' · IC 95% ' + researchScore(replicationDeltaCi[0]) + '–' + researchScore(replicationDeltaCi[1])) : '')
        + ' · sólo VAL';
      researchStat(grid, 'Ensemble replicado VAL', researchScore(valReplications.ensemble_event_macro_iou), ensembleHint, true);
    }
    const growthStrata = valStrata.growth_strata || [];
    if (growthStrata.length) {
      const stratumScores = growthStrata.map(row => Number(row.event_macro_iou)).filter(Number.isFinite);
      const growthRho = Number((valStrata.growth_support_spearman || {}).rho);
      if (stratumScores.length) {
        researchStat(grid, 'Rango estratos VAL', researchScore(Math.min(...stratumScores)) + '–' + researchScore(Math.max(...stratumScores)), growthStrata.length + ' cuartiles por crecimiento · descriptivo');
      }
      if (Number.isFinite(growthRho)) {
        researchStat(grid, 'Dependencia del tamaño', researchScore(growthRho), 'Spearman en ' + String(valStrata.events || 0) + ' incendios · sólo VAL');
      }
    }
    if (valEnsemble.event_macro_iou != null) {
      const ensembleDelta = Number(valEnsemble.delta_vs_best_individual);
      const ensembleCi = valEnsemble.paired_delta_95_ci || [];
      let ensembleHint = Number.isFinite(ensembleDelta)
        ? ((ensembleDelta >= 0 ? '+' : '') + researchScore(ensembleDelta) + ' vs mejor individual' + (valEnsemble.preregistered === false ? ' · descartado' : ''))
        : 'promedio de probabilidades · sólo VAL';
      if (ensembleCi.length === 2) {
        ensembleHint += ' · IC 95% ' + researchScore(ensembleCi[0]) + '–' + researchScore(ensembleCi[1]) + ' · sólo VAL';
      }
      researchStat(grid, 'Mejor ensemble VAL', researchScore(valEnsemble.event_macro_iou), ensembleHint);
    }
    if (valPostprocess.event_macro_iou != null) {
      const postDelta = Number(valPostprocess.delta_vs_raw);
      const postHint = (Number.isFinite(postDelta) ? ((postDelta >= 0 ? '+' : '') + researchScore(postDelta) + ' vs salida cruda · ') : '')
        + 'radio ' + String(valPostprocess.dilation_radius_px ?? '—') + ' px'
        + (valPostprocess.require_t0_connection ? ' · conectado a t0' : '');
      researchStat(grid, 'Postproceso VAL', researchScore(valPostprocess.event_macro_iou), postHint);
    }
  } else {
    researchStat(grid, 'Selección', 'VAL', 'TEST aún aislado', true);
    researchStat(grid, 'Semillas finales', String((protocol.final_seeds || []).length || 3), (protocol.final_seeds || [11,29,47]).join(' · '));
  }
  if (samplerAudit.default_event_mass_cv != null && samplerAudit.uniform_event_mass_cv != null) {
    researchStat(grid, 'Masa por incendio', Number(samplerAudit.default_event_mass_cv).toFixed(3) + '→' + Number(samplerAudit.uniform_event_mass_cv).toFixed(3), 'CV TRAIN · uniforme por evento');
  }
  if (numericStability.failure_recovered) {
    researchStat(grid, 'Recuperación numérica', 'epoch ' + (numericStability.checkpoint_epoch ?? '—'), 'VAL macro ' + researchScore(numericStability.recovered_val_event_macro_iou) + ' · TEST aislado');
    researchStat(grid, 'Protección anti-NaN', 'grad ≤ ' + researchScore(numericStability.max_grad_norm), String(numericStability.train_files_scanned || 0) + ' NPY finitos');
  }
  host.appendChild(grid);

  if ((rs.artifacts || {}).validation_figure) {
    const figure = document.createElement('figure'); figure.className = 'research-figure';
    const image = document.createElement('img');
    image.src = 'validation_evidence.svg?research=' + encodeURIComponent(String(rs.updated_at || 'current'));
    image.alt = 'Ranking de candidatos en validaciÃ³n con intervalos bootstrap y comparaciÃ³n pareada; TEST permanece sellado.';
    image.loading = 'lazy';
    const caption = document.createElement('figcaption');
    caption.textContent = 'Evidencia sÃ³lo VAL Â· IC por incendio Â· TEST sellado';
    figure.append(image, caption); host.appendChild(figure);
  }

  renderValidationBoard(
    host,
    Array.isArray(rs.validation_candidates) ? rs.validation_candidates : [],
    rs.validation_evidence || {}
  );
  renderExperimentQueue(
    host,
    Array.isArray(rs.experiment_queue) ? rs.experiment_queue : []
  );

  const live = rs.training_progress || {};
  if (rs.training_live && (live.run || live.epoch != null)) {
    const liveSection = document.createElement('div'); liveSection.className = 'research-section';
    const liveTitle = document.createElement('h3'); liveTitle.textContent = 'Telemetría de entrenamiento';
    const liveGrid = document.createElement('div'); liveGrid.className = 'research-grid';
    const seedHint = live.seed != null ? ('semilla ' + live.seed) : (live.run || 'selección en VAL');
    if (live.epoch != null) {
      researchStat(liveGrid, 'Época activa', String(live.epoch), seedHint, true);
    } else {
      researchStat(liveGrid, 'Receta activa', String(live.run || '—'), String(live.remote_status || 'remota'), true);
    }
    if (live.val_event_macro_iou != null) {
      const selectionHint = 'umbral VAL ' + researchScore(live.val_selection_threshold)
        + ' · F1@0.5 ' + researchScore(live.val_f1_at_0_5);
      researchStat(liveGrid, 'IoU macro VAL', researchScore(live.val_event_macro_iou), selectionHint);
    } else if (live.epoch != null) {
      researchStat(liveGrid, 'F1 VAL @ 0.5', researchScore(live.val_f1_at_0_5), 'telemetría; la selección final usa IoU macro');
    }
    if (live.epoch != null) {
      researchStat(liveGrid, 'Pérdida TRAIN', Number.isFinite(Number(live.train_loss)) ? Number(live.train_loss).toFixed(4) : '—', 'objetivo focal-Tversky');
      researchStat(liveGrid, 'Reinicios Spot', String(live.spot_restarts || 0), 'checkpoint persistente');
    } else {
      researchStat(liveGrid, 'Mejor VAL completado', researchScore(live.best_completed_val_event_macro_iou), 'IoU macro por incendio');
      researchStat(liveGrid, 'Corridas registradas', String(live.registered_runs || 0), String(live.recovered_runs || 0) + ' recuperada(s) desde checkpoint finito');
      researchStat(liveGrid, 'TEST nuevo', live.test_evaluated === false ? 'sellado' : '—', 'sin uso para seleccionar');
    }
    liveSection.append(liveTitle, liveGrid); host.appendChild(liveSection);
  }

  const externalGrid = document.createElement('div'); externalGrid.className = 'research-grid';
  researchStat(externalGrid, 'WFIGS auditados', String(wfigs.pairs_enriched || 0), String(wfigs.pairs_hrrr_space_time_valid || 0) + ' con HRRR espacio-tiempo válido');
  const tensorDetail = wfigs.campaign_running
    ? 'campaña TRAIN/VAL en ejecución'
    : (String(wfigs.train_tensors || 0) + ' TRAIN · ' + String(wfigs.validation_tensors || 0) + ' VAL');
  researchStat(externalGrid, 'Tensores externos', String(wfigs.tensors_training_ready || 0), tensorDetail, true);
  if (wfigs.test_groups_total) {
    researchStat(externalGrid, 'Progreso WFIGS TEST', String(wfigs.test_groups_complete || 0) + '/' + String(wfigs.test_groups_total), researchRunName(wfigs.test_materialization_phase || 'pendiente'), testActive);
  }
  const external = wfigs.external_summary || {};
  const pairedExternal = external.paired_event_analysis || {};
  if (wfigs.external_evaluation_executed) {
    researchStat(externalGrid, 'WFIGS zero-shot', researchScore(external.model_event_macro_iou_mean), 'IoU macro · media de semillas', true);
    researchStat(externalGrid, 'Baseline geométrico', researchScore(external.geometry_baseline_event_macro_iou), 'radio elegido en WFIGS VAL');
    if (pairedExternal.paired_delta != null) {
      const extCi = pairedExternal.paired_delta_event_bootstrap_95_ci || [];
      researchStat(externalGrid, 'Delta externo', (Number(pairedExternal.paired_delta) >= 0 ? '+' : '') + researchScore(pairedExternal.paired_delta), extCi.length === 2 ? ('IC 95% ' + researchScore(extCi[0]) + '–' + researchScore(extCi[1])) : 'bootstrap por incendio');
    }
    if (external.ensemble_event_macro_iou != null) {
      researchStat(externalGrid, 'Ensemble WFIGS', researchScore(external.ensemble_event_macro_iou), 'umbral congelado en RCDA VAL');
    }
  }
  const adaptedExternal = wfigs.adapted_summary || {};
  if (wfigs.adapted_evaluation_executed) {
    researchStat(externalGrid, 'WFIGS adaptado', researchScore(adaptedExternal.adapted_event_macro_iou_mean), 'IoU macro · media de semillas', true);
    if (adaptedExternal.ensemble_event_macro_iou != null) {
      researchStat(externalGrid, 'Ensemble adaptado', researchScore(adaptedExternal.ensemble_event_macro_iou), 'umbral elegido sólo en WFIGS VAL');
    }
    const adaptedPaired = adaptedExternal.ensemble_paired_event_analysis || adaptedExternal.paired_event_analysis || {};
    if (adaptedPaired.paired_delta != null) {
      const adaptedCi = adaptedPaired.paired_delta_event_bootstrap_95_ci || [];
      researchStat(externalGrid, 'Delta adaptado', (Number(adaptedPaired.paired_delta) >= 0 ? '+' : '') + researchScore(adaptedPaired.paired_delta), adaptedCi.length === 2 ? ('IC 95% ' + researchScore(adaptedCi[0]) + '–' + researchScore(adaptedCi[1])) : 'bootstrap por incendio');
    }
    const zeroShotEnsemble = Number(external.ensemble_event_macro_iou);
    const adaptedEnsemble = Number(adaptedExternal.ensemble_event_macro_iou);
    if (Number.isFinite(zeroShotEnsemble) && Number.isFinite(adaptedEnsemble)) {
      const lift = adaptedEnsemble - zeroShotEnsemble;
      researchStat(externalGrid, 'Lift por adaptación', (lift >= 0 ? '+' : '') + researchScore(lift), researchScore(zeroShotEnsemble) + '→' + researchScore(adaptedEnsemble) + ' IoU macro');
    }
    researchStat(externalGrid, 'Señal externa', adaptedExternal.adapted_transfer_signal_gate === true ? 'APROBADA' : 'NO CONCLUYENTE', adaptedExternal.adapted_transfer_signal_gate === true ? 'IC pareado por encima de cero' : 'el IC pareado todavía cruza cero', adaptedExternal.adapted_transfer_signal_gate === true);
  }
  host.appendChild(externalGrid);

  const section = document.createElement('div'); section.className = 'research-section';
  const sectionTitle = document.createElement('h3'); sectionTitle.textContent = 'Integridad científica';
  const checks = document.createElement('div'); checks.className = 'research-checks';
  researchCheck(checks, 'Splits por incendio, sin compartir eventos', protocol.event_disjoint === true);
  researchCheck(checks, 'Normalización ajustada sólo con TRAIN', protocol.normalization_train_only === true);
  researchCheck(checks, 'Arquitectura y umbral elegidos sólo en VAL', protocol.test_used_for_selection === false);
  researchCheck(checks, 'Decisiones y código registrados antes del nuevo TEST', protocol.pretest_decisions_registered === true);
  researchCheck(checks, 'Ablación de muestreo motivada sólo con TRAIN', samplerAudit.test_evaluated === false && samplerAudit.validation_evaluated === false);
  researchCheck(checks, 'Geometrías TRAIN acumulativas sin pérdida de t0', samplerAudit.samples_with_any_t0_loss === 0);
  researchCheck(checks, 'Fallo numérico recuperado desde checkpoint finito, sin TEST', numericStability.failure_recovered === true && numericStability.nonfinite_train_files === 0 && numericStability.test_evaluated === false);
  researchCheck(checks, 'Corridas posteriores con clipping y parada numérica segura', numericStability.future_runs_fail_fast === true && numericStability.max_grad_norm === 5.0);
  researchCheck(checks, 'Tres semillas finales preregistradas', (protocol.final_seeds || []).length >= 3);
  researchCheck(checks, 'Dominio espacial HRRR verificado por bbox', wfigs.spatial_weather_contract === true);
  researchCheck(checks, 'Auditoría tensorial WFIGS sin incidencias', wfigs.dataset_audit_status === 'pass' && wfigs.dataset_audit_issues === 0);
  researchCheck(checks, 'WFIGS TRAIN/VAL disjuntos por incendio', wfigs.dataset_event_disjoint === true);
  researchCheck(checks, 'Normalización WFIGS recomputada sólo en TRAIN', wfigs.dataset_normalization_train_only === true);
  researchCheck(checks, 'WFIGS TEST no usado para seleccionar', wfigs.external_test_used_for_selection === false && wfigs.adapted_test_used_for_selection === false);
  if (final.gates) {
    Object.keys(final.gates).forEach(key => researchCheck(checks, key.replaceAll('_', ' '), final.gates[key] === true));
  } else {
    researchCheck(checks, 'Gates estadísticos del paper pendientes', false);
  }
  section.append(sectionTitle, checks); host.appendChild(section);

  const warning = document.createElement('div'); warning.className = 'research-warning';
  const baseWarning = wfigs.adapted_evaluation_executed && (wfigs.adapted_summary || {}).adapted_transfer_signal_gate !== true
    ? 'La adaptación mejora el resultado WFIGS, pero su intervalo pareado cruza cero: la generalización externa sigue sin demostrarse y la nueva cohorte permanece en escalado.'
    : ((rs.claims || {}).paper_ready
      ? (wfigs.external_evaluation_executed ? 'Candidato RCDA con evaluación WFIGS ejecutada; revisar el informe externo antes de formular claims.' : 'Candidato de paper en este dataset. WFIGS se está materializando, pero la generalización externa aún no ha sido evaluada.')
      : (wfigs.external_evaluation_executed ? 'Evaluación WFIGS disponible, pero no implica todavía validez operativa.' : 'Aún no es un claim de paper ni una métrica operativa. WFIGS ya tiene pipeline físico, pero su evaluación externa sigue pendiente.'));
  const postFreezeWarning = winner.post_freeze_candidate === true && frozenTestRecipe.tested === true
    ? ('Nuevo líder sólo VAL (' + researchRunName(winner.run_name) + ', ' + researchScore(winner.event_macro_iou)
      + '); no hereda las métricas TEST de la receta congelada ' + researchRunName(frozenTestRecipe.run_name) + '. ')
    : '';
  warning.textContent = postFreezeWarning + baseWarning;
  host.appendChild(warning);
  const path = document.createElement('div'); path.className = 'research-path';
  path.textContent = ((rs.artifacts || {}).scorecard || (rs.artifacts || {}).frozen_recipe || (rs.artifacts || {}).state || 'Sin artefacto');
  host.appendChild(path);
}

function renderOpsKv() {
  const okv = document.getElementById('ops-kv');
  okv.innerHTML = '';
  if (ops && Object.keys(ops).length) {
    const ros = ops.primary_ros_m_min != null ? ops.primary_ros_m_min : ops.speed_median_m_min;
    const ha = ops.area_ha_max != null ? ops.area_ha_max : ops.area_ha_last;
    const n = ops.n_frames != null ? ops.n_frames : ops.num_observations || ops.observation_count;
    metric(okv, 'Calidad', ops.quality_grade);
    metric(okv, 'Velocidad m/min', typeof ros === 'number' ? Math.round(ros * 100) / 100 : ros);
    metric(okv, 'Área ha', typeof ha === 'number' ? Math.round(ha * 10) / 10 : ha);
    metric(okv, 'Fotos', n);
    const g = (brief && brief.gates) || {};
    metric(okv, 'Producto listo', yn(g.GO_MES));
    metric(okv, 'Demo tercero', yn(g.GO_Q));
  } else okv.innerHTML = '<div class="empty" style="grid-column:1/-1">Sin métricas</div>';
}

function renderDecisionTab() {
  const dbody = document.getElementById('decision-body');
  if (card) {
    dbody.className = '';
    dbody.innerHTML = '<div class="grid2" id="dec-kv"></div><div id="src-list" style="margin-top:8px"></div>' +
      ((card.reasons || []).length ? '<ul id="dec-reasons" style="padding-left:1.1rem;margin:8px 0;color:var(--muted);font-size:11px"></ul>' : '') +
      '<div class="dlog-note" id="dec-honest" data-marker="decision-honest"></div>' +
      '<button type="button" class="btn primary block" id="btn-copy-decision" style="margin-top:8px">Copiar</button>';
    const dkv = document.getElementById('dec-kv');
    const decWord = String(card.decision || '').toUpperCase();
    metric(dkv, 'Lectura', (WORD[decWord] || decWord) + (decWord ? ' · ' + decWord : ''));
    metric(dkv, 'Calidad (no ROS)', card.confidence_pred != null ? Math.round(card.confidence_pred * 100) + '%' : '—');
    metric(dkv, 'Incendio', card.event_id || '—');
    const sys = card.system_reliability_pass === true ? 'OK'
      : (card.system_reliability_pass === false ? 'FAIL' : '—');
    const thinDec = sourcesThin(card);
    metric(dkv, 'Fuentes', (sys === 'FAIL' || thinDec) ? 'incompletas' : (sys === 'OK' ? 'completas' : '—'));
    const citedDec = ((window._wfdLastSnapshot || P.snapshot || {}).cited) || {};
    const rosDec = citedDec.ros_m_min != null ? citedDec.ros_m_min
      : (ops && (ops.primary_ros_m_min != null ? ops.primary_ros_m_min : ops.speed_median_m_min));
    const haDec = citedDec.area_ha != null ? citedDec.area_ha
      : (ops && (ops.area_ha_max != null ? ops.area_ha_max : ops.area_ha_last));
    if (rosDec != null) metric(dkv, 'Velocidad citada', (typeof rosDec === 'number' ? Math.round(rosDec * 100) / 100 : rosDec) + ' m/min');
    if (haDec != null) metric(dkv, 'Área citada', (typeof haDec === 'number' ? Math.round(haDec * 10) / 10 : haDec) + ' ha');
    (card.sources || []).slice(0, 6).forEach(s => {
      const row = document.createElement('div');
      row.className = 'src';
      const avail = s.available === false ? ' · ausente' : '';
      row.innerHTML = '<span>' + (s.id || '?') + avail + '</span><span>' + Math.round(Number(s.confidence || 0) * 100) + '%</span>';
      document.getElementById('src-list').appendChild(row);
    });
    const ur = document.getElementById('dec-reasons');
    if (ur) (card.reasons || []).slice(0, 4).forEach(r => {
      const li = document.createElement('li'); li.textContent = r; ur.appendChild(li);
    });
    const miss = missingSourceIds(card);
    const honest = document.getElementById('dec-honest');
    if (honest) {
      const isGo = String(card.decision || '').toUpperCase() === 'GO';
      if (sys === 'FAIL' || miss.length) {
        honest.textContent = (isGo ? 'Card GO = orientación de outbox ≠ GO_Q · ' : '')
          + (sys === 'FAIL' ? 'sistema FAIL (fail-closed / artefactos incompletos) · ' : '')
          + (miss.length ? ('fuentes incompletas: ' + miss.join(', ') + ' · ') : '')
          + 'no es despacho · fusion ON ≠ GO_Q complete';
      } else {
        honest.textContent = 'Card = orientación · no es GO_Q · no es despacho táctico';
      }
    }
    document.getElementById('btn-copy-decision').onclick = () => copyText([
      'Decisión: ' + (card.decision || '—') + ' (orientación de card · no es GO_Q)',
      'Confianza: ' + (card.confidence_pred != null ? Math.round(card.confidence_pred * 100) + '%' : '—'),
      'Sistema: ' + sys,
      ...(card.reasons || []).slice(0, 4).map(r => '- ' + r),
    ].join('\n'), 'Decisión', { act: 'Decisión', hint: 'Resumen Decision Card copiado' });
  } else {
    dbody.className = 'empty';
    dbody.textContent = P.work_dir ? 'Sin tarjeta en outbox.' : 'Selecciona un IF con datos.';
  }
}

const layerVis = { local: true, firms: true };
function clearMapLayers() {
  mapLayers.forEach(item => {
    const l = item && item.layer ? item.layer : item;
    try { map.removeLayer(l); } catch (e) {}
  });
  mapLayers = [];
  bounds = [];
}
function paintLayerToggles() {
  const host = document.getElementById('map-layer-toggles');
  if (!host) return;
  host.innerHTML = '';
  [['local', 'Frente local'], ['firms', 'Satélite ≠ perímetro']].forEach(([key, label]) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'chip' + (layerVis[key] ? '' : ' off');
    b.textContent = label;
    b.onclick = () => {
      layerVis[key] = !layerVis[key];
      applyLayerVis();
      paintLayerToggles();
    };
    host.appendChild(b);
  });
}
function applyLayerVis() {
  mapLayers.forEach(item => {
    if (!item || !item.layer) return;
    const show = item.firms ? layerVis.firms : layerVis.local;
    try {
      if (show) item.layer.addTo(map);
      else map.removeLayer(item.layer);
    } catch (e) {}
  });
  const n = mapLayers.filter(it => it && ((it.firms && layerVis.firms) || (!it.firms && layerVis.local))).length;
  const el = document.getElementById('map-layer-n');
  if (el) el.textContent = n + ' capas';
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
    });
    mapLayers.push({ layer: layer, firms: firms, name: Lyr.name || Lyr.id });
    touchBounds(layer);
  });
  applyLayerVis();
  paintLayerToggles();
  const conn = (P.connectivity && P.connectivity.status) || (mp.connectivity && mp.connectivity.status) || 'skipped';
  const connEl = document.getElementById('map-conn');
  if (connEl) {
    connEl.textContent =
      conn + (mp.firms && mp.firms.n_hotspots != null ? ' · ' + mp.firms.n_hotspots + ' focos' : '');
  }
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
  renderNeedKnow();
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
    const decF = String(f.decision || '').toUpperCase();
    const wordF = WORD[decF] || '';
    const clsF = ({GO:'go',HOLD:'hold',ABSTAIN:'abstain'}[decF] || '');
    el.innerHTML = '<div class="id">' + (f.label || f.id) + '</div>' +
      (wordF ? '<div class="word ' + clsF + '">' + wordF + '</div>' : '') +
      '<div class="badge">' +
      [decF && decF !== 'BRIEF' ? decF : null, f.has_geojson ? 'mapa' : null, packOn ? (inPack ? 'pack' : 'rebuild') : null].filter(Boolean).join(' · ') + '</div>';
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
document.getElementById('btn-act-snapshot').onclick = () => actSnapshot();
document.getElementById('btn-act-compare').onclick = () => actCompare();
const btnCopyLect = document.getElementById('btn-copy-lectura');
if (btnCopyLect) btnCopyLect.onclick = () => copyLectura();
const btnShareLect = document.getElementById('btn-share-lectura');
if (btnShareLect) btnShareLect.onclick = () => shareLectura();
renderSourceBoard(P.snapshot);

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
  const cite = /citada/.test(k) ? ' cite' : '';
  d.innerHTML = '<div class="k">' + k + '</div><div class="v' + cite + '">' + (v == null || v === '' ? '—' : v) + '</div>';
  parent.appendChild(d);
}
function renderKpis() {
  bkv.innerHTML = '';
  const cited = ((window._wfdLastSnapshot || P.snapshot || {}).cited) || {};
  const rosKpi = cited.ros_m_min != null ? cited.ros_m_min
    : (ops && (ops.primary_ros_m_min != null ? ops.primary_ros_m_min : ops.speed_median_m_min));
  const haKpi = cited.area_ha != null ? cited.area_ha
    : (ops && (ops.area_ha_max != null ? ops.area_ha_max : ops.area_ha_last));
  const gradeKpi = cited.quality_grade || (ops && ops.quality_grade);
  const dtKpi = cited.interval_s != null ? cited.interval_s : (ops && ops.interval_s_median);
  const rosTxt = typeof rosKpi === 'number' ? (Math.round(rosKpi * 100) / 100) + ' m/min'
    : (rosKpi != null ? String(rosKpi) : 'sin dato');
  const haTxt = typeof haKpi === 'number' ? (Math.round(haKpi * 10) / 10) + ' ha'
    : (haKpi != null ? String(haKpi) : 'sin dato');
  const dtTxt = typeof dtKpi === 'number' ? (Math.round(dtKpi) + ' s')
    : (dtKpi != null ? String(dtKpi) : 'sin dato');
  kpi(bkv, 'Velocidad citada', rosTxt);
  kpi(bkv, 'Área citada', haTxt);
  kpi(bkv, 'Calidad ops', gradeKpi || 'sin dato');
  kpi(bkv, 'Entre fotos', dtTxt);
}
renderKpis();
renderNeedKnow();
renderLastAct();
updateRoleUi(true);
wireIntake();

// Overview metrics
function metric(parent, k, v) {
  const d = document.createElement('div');
  d.className = 'metric';
  d.innerHTML = '<div class="k">' + k + '</div><div class="v">' + (v == null || v === '' ? '—' : v) + '</div>';
  parent.appendChild(d);
}
renderOpsKv();
renderResearchStatus();

async function refreshResearchStatus() {
  if (!/^https?:$/.test(window.location.protocol)) return;
  try {
    const response = await fetch('app_payload.json?research=' + Date.now(), {cache:'no-store'});
    if (!response.ok) return;
    const nextPayload = await response.json();
    if (!nextPayload || !nextPayload.research_status) return;
    researchStatus = nextPayload.research_status;
    renderResearchStatus();
  } catch (_) {
    // The exported app remains fully usable offline with its embedded snapshot.
  }
}
window.setInterval(refreshResearchStatus, 15000);
document.addEventListener('visibilitychange', () => {
  if (!document.hidden) refreshResearchStatus();
});

const railsEl = document.getElementById('rails');
const fusionOn = fusionRailOn();
[
  [fusionRailLabel(), fusionOn],
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

function renderNeedKnow(extra) {
  const data = extra || needKnow || {};
  const haveEl = document.getElementById('nk-have');
  const missEl = document.getElementById('nk-miss');
  const actEl = document.getElementById('nk-act');
  if (haveEl) haveEl.textContent = (data.have || []).join(' · ') || 'Todavía no hay cifras.';
  if (missEl) missEl.textContent = (data.missing || []).join(' · ') || '—';
  if (actEl) actEl.textContent = data.action || 'Mete las fotos y pulsa Procesar.';
}
function renderIntake() {
  const nameEl = document.getElementById('intake-fire');
  if (nameEl && !nameEl.value) {
    nameEl.value = intakeGuide.fire_id || (P.selected_fire_id || '');
  }
  paintIntakeFiles(intakeGuide);
  const el = document.getElementById('intake-steps');
  if (!el) return;
  el.innerHTML = '';
  if (!intake.length) return;
  intake.forEach(s => {
    const row = document.createElement('div');
    row.className = 'step';
    row.innerHTML = '<div class="n">' + (s.step || '·') + '</div><div><b>' + (s.title || '') +
      '</b><p>' + (s.plain || s.detail || '') + '</p>' +
      (s.cmd ? '<div class="cmd" style="font-family:var(--mono);font-size:10px;color:var(--cyan);margin-top:4px;word-break:break-all">' + s.cmd + '</div>' : '') +
      '<button type="button" class="btn sm" style="margin-top:6px">Copiar</button></div>';
    row.querySelector('button').onclick = () =>
      copyText(s.cmd || [s.title, s.plain || s.detail].filter(Boolean).join('\n'));
    el.appendChild(row);
  });
}
function paintIntakeFiles(data) {
  const el = document.getElementById('intake-files');
  const hint = document.getElementById('intake-hint');
  if (!el) return;
  const photos = (data && data.photos) || [];
  const bad = (data && data.rejected_not_tif) || [];
  let html = '';
  if (photos.length) {
    html += '<div>En la carpeta: ' + photos.map(p => (p.name || p)).join(', ') + '</div>';
  }
  if (bad.length) {
    html += '<div class="bad">No se usarán (no son .tif): ' + bad.join(', ') + '</div>';
  }
  if (!html) html = 'Carpeta vacía. Suelta fotos .tif con fecha en el nombre.';
  el.innerHTML = html;
  if (hint && data && data.hint) hint.textContent = data.hint;
}
function intakeBody() {
  const nameEl = document.getElementById('intake-fire');
  return {
    work_dir: currentWorkDirRel(),
    fire_id: (nameEl && nameEl.value) || intakeGuide.fire_id || P.selected_fire_id || 'nuevo_incendio'
  };
}
async function runIntake(kind, extra) {
  const label = kind === 'intake_open' ? 'Abrir carpeta' : (kind === 'intake_process' ? 'Procesar' : 'Subir fotos');
  if (!liveOpsOn()) {
    if (kind === 'intake_open') {
      copyText(intakeGuide.cmd_open || '', 'Ruta copiada', { act: 'Abrir carpeta', hint: 'Pégala en el Explorador de Windows' });
      toast('Copia la ruta y abre esa carpeta');
      return;
    }
    copyText('python -m wildfire_front app --serve', 'CLI copiado', { act: label, hint: 'Abre la consola con --serve para no usar terminal' });
    toast('Haz falta abrir la app con --serve');
    return;
  }
  const url = liveUrl(kind === 'intake_open' ? 'intake_open' : (kind === 'intake_process' ? 'intake_process' : 'intake_upload'));
  if (!url) { toast('Intake no disponible'); return; }
  try {
    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(Object.assign(intakeBody(), extra || {}))
    });
    const data = await resp.json().catch(() => ({}));
    paintIntakeFiles(data);
    if (data.hint) {
      const h = document.getElementById('intake-hint');
      if (h) h.textContent = data.hint;
    }
    if (kind === 'intake_process' && data.card) {
      card = data.card;
      applyHero({
        decision: String(data.decision || card.decision || 'ABSTAIN').toUpperCase(),
        confidence_pred: data.confidence_pred,
        plain: SHORT[String(data.decision || '').toUpperCase()] || ''
      });
      renderDecisionTab();
      needKnow = {
        have: ['Fotos procesadas · ' + (data.n_photos || 0) + ' archivo(s)'],
        missing: [],
        action: data.hint || 'Mira la palabra grande.'
      };
      renderNeedKnow();
    }
    recordAct(label + ' LIVE', url, data.hint || label, data.word || data.hint || '');
    toast(data.hint || (data.ok ? (label + ' OK') : (label + ' — revisa')));
  } catch (e) {
    toast(label + ' no disponible');
  }
}
function fileToB64(file) {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => {
      const s = String(r.result || '');
      const i = s.indexOf(',');
      resolve(i >= 0 ? s.slice(i + 1) : s);
    };
    r.onerror = reject;
    r.readAsDataURL(file);
  });
}
async function uploadIntakeFiles(fileList) {
  const files = Array.from(fileList || []);
  if (!files.length) return;
  const bad = files.filter(f => !/\.tiff?$/i.test(f.name));
  if (bad.length && bad.length === files.length) {
    toast('Un JPG del móvil no sirve. Hace falta .tif');
    const el = document.getElementById('intake-files');
    if (el) el.innerHTML = '<div class="bad">Un JPG o foto del móvil no sirve. Hace falta una foto térmica con mapa (.tif).</div>';
    return;
  }
  if (!liveOpsOn()) {
    toast('Abre la app con --serve para soltar fotos aquí');
    return;
  }
  const packed = [];
  for (const f of files) {
    if (!/\.tiff?$/i.test(f.name)) continue;
    packed.push({ name: f.name, content_b64: await fileToB64(f) });
  }
  await runIntake('intake_upload', { files: packed });
}
function wireIntake() {
  const openBtn = document.getElementById('btn-intake-open');
  const procBtn = document.getElementById('btn-intake-process');
  const drop = document.getElementById('intake-drop');
  const file = document.getElementById('intake-file');
  if (openBtn) openBtn.onclick = () => runIntake('intake_open');
  if (procBtn) procBtn.onclick = () => runIntake('intake_process');
  if (drop && file) {
    drop.onclick = () => file.click();
    drop.ondragover = (e) => { e.preventDefault(); drop.classList.add('on'); };
    drop.ondragleave = () => drop.classList.remove('on');
    drop.ondrop = (e) => {
      e.preventDefault();
      drop.classList.remove('on');
      uploadIntakeFiles(e.dataTransfer && e.dataTransfer.files);
    };
    file.onchange = () => uploadIntakeFiles(file.files);
  }
}

const glossEl = document.getElementById('glossary-list');
function renderGlossary(filter) {
  if (!glossEl) return;
  const q = String(filter || '').trim().toLowerCase();
  const list = glossary.filter(g => {
    if (!q) return true;
    const blob = ((g.term || '') + ' ' + (g.id || '') + ' ' + (g.plain || '')).toLowerCase();
    return blob.indexOf(q) >= 0;
  });
  glossEl.innerHTML = '';
  if (!list.length) {
    glossEl.innerHTML = '<div class="empty">' + (glossary.length ? 'Sin coincidencias.' : '—') + '</div>';
    return;
  }
  list.forEach(g => {
    const d = document.createElement('div');
    d.className = 'gitem';
    d.innerHTML = '<b>' + (g.term || g.id || '') + '</b><span>' + (g.plain || '') + '</span>';
    glossEl.appendChild(d);
  });
}
renderGlossary('');
const gSearch = document.getElementById('glossary-search');
if (gSearch) gSearch.oninput = () => renderGlossary(gSearch.value);

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
      recordAct('Bridge', url, 'Card live (same-origin proxy o bridge) — fusion ON');
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
const btnExpand = document.getElementById('btn-map-expand');
if (btnExpand) btnExpand.onclick = () => toggleMapFocus();

document.querySelectorAll('#dock-nav button').forEach((b) => {
  b.onclick = () => {
    const v = b.dataset.view;
    if (v === 'mas') {
      const sheet = document.getElementById('more-sheet');
      const open = sheet && !sheet.classList.contains('on');
      setView('mas', true);
      if (sheet) sheet.classList.toggle('on', !!open);
      return;
    }
    setView(v);
  };
});
document.querySelectorAll('#more-sheet [data-more-tab]').forEach((b) => {
  b.onclick = () => {
    const sheet = document.getElementById('more-sheet');
    if (sheet) sheet.classList.remove('on');
    setView('lectura', true);
    openTab(b.dataset.moreTab);
  };
});
const moreCopy = document.getElementById('more-copy');
if (moreCopy) moreCopy.onclick = () => copyLectura();
const moreHelp = document.getElementById('more-help');
if (moreHelp) moreHelp.onclick = () => document.getElementById('help-modal').classList.add('on');
const morePrint = document.getElementById('more-print');
if (morePrint) morePrint.onclick = () => { try { window.print(); } catch (e) { shareLectura(); } };

function paintClock() {
  const el = document.getElementById('clock');
  if (!el) return;
  const now = new Date();
  el.textContent = 'Ahora ' + now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}
function paintConnPlain() {
  const el = document.getElementById('conn-plain');
  if (!el) return;
  el.textContent = liveOpsOn()
    ? 'Con consola · los botones hacen el trabajo'
    : 'Sin consola · se copia el comando';
}
paintClock();
paintConnPlain();
setInterval(paintClock, 30000);

document.addEventListener('keydown', (e) => {
  const tag = (e.target && e.target.tagName) || '';
  if (/INPUT|TEXTAREA|SELECT/.test(tag)) return;
  const k = String(e.key || '').toLowerCase();
  if (k === '?' || (e.shiftKey && k === '/')) {
    document.getElementById('help-modal').classList.add('on');
    return;
  }
  if (k === 'd') actDecide();
  else if (k === 'e') actStatus();
  else if (k === 'a') actActa();
  else if (k === 'c') actCompare();
  else if (k === 'f') actSnapshot();
  else if (k === 'l') copyLectura();
  else if (k === 'm') toggleMapFocus();
});

setMode(uiMode, true);
const resize = () => map.invalidateSize({ animate: false });
setTimeout(resize, 50);
window.addEventListener('resize', resize);
if (window.ResizeObserver) new ResizeObserver(resize).observe(document.querySelector('.map-wrap'));
""".strip()


def render_product_app_html(payload: dict[str, Any]) -> str:
    """Self-contained industrial SPA: map-first, dense KPIs, no essay text."""
    data_js = json.dumps(payload, ensure_ascii=False)
    title = _esc(str(payload.get("title") or "WFD MANDO"))
    return (
        "<!DOCTYPE html>\n"
        '<html lang="es" class="dark">\n'
        "<head>\n"
        '<meta charset="utf-8"/>\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"/>\n'
        '<meta name="description" content="WFD MANDO — apoyo a la decisión. Not tactical dispatch."/>\n'
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
