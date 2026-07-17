#!/usr/bin/env python3
"""Build a single clear portal: what we sell, what we built, metrics, how to run.

Output: docs/PORTAL.html  (open this — one page for demos and teaching)
Also: docs/START_HERE.md
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(p: Path):
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


def main() -> int:
    # refresh hub if possible
    try:
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_metrics_hub.py")],
            cwd=str(ROOT),
            env={**dict(__import__("os").environ), "PYTHONPATH": str(ROOT)},
            capture_output=True,
            timeout=120,
        )
    except Exception:
        pass

    hub = _load(ROOT / "docs" / "METRICS_HUB.json") or {}
    card = hub.get("decision_card") or {}
    ml = (hub.get("ml") or {}).get("metrics") or {}
    packs = (hub.get("open_cems") or {}).get("packs") or []
    gates = hub.get("gates") or {}
    compare = hub.get("commercial_compare") or {}
    plan = _load(ROOT / "docs" / "PLAN_3_MESES_STATUS.json") or {}

    dec = card.get("decision") or "—"
    conf = card.get("confidence_pred")
    conf_s = f"{conf:.2f}" if isinstance(conf, (int, float)) else "—"
    iou = ml.get("test_iou") or "—"
    delta = ml.get("improvement_vs_copy_iou") or "—"
    n_packs = len(packs)
    max_ha = max((float(p.get("max_area_ha") or 0) for p in packs), default=0)

    pack_rows = "".join(
        f"<tr><td><b>{p.get('activation') or p.get('id')}</b></td>"
        f"<td class='num'>{float(p.get('max_area_ha') or 0):.0f} ha</td>"
        f"<td class='num'>{p.get('n_timeline_steps') or '—'}</td>"
        f"<td><span class='pill ok'>{p.get('O2_cems_delineation') or '—'}</span></td>"
        f"<td><a href='../outputs/open_if/{(p.get('id') or '').lower()}/map.html'>mapa</a></td></tr>"
        for p in packs
    )
    if not pack_rows:
        pack_rows = "<tr><td colspan='5'>Sin packs — ejecuta <code>python scripts/build_open_if_pack.py --activation EMSR578</code></td></tr>"

    gate_pills = "".join(
        f"<span class='pill {'ok' if str(v).upper() in ('GO','GO_ENG','GO_PROXY','TRUE','PASS') else 'warn' if 'PARTIAL' in str(v).upper() or 'FOLLOW' in str(v).upper() else 'bad'}'>{k}: {v}</span>"
        for k, v in list(gates.items())[:12]
    )

    done_items = sum(
        1
        for v in (plan.get("items") or {}).values()
        if isinstance(v, dict) and v.get("status") == "DONE"
    )
    n_items = len(plan.get("items") or {})

    badge_color = {"GO": "#12b886", "HOLD": "#f59f00", "ABSTAIN": "#fa5252"}.get(
        str(dec), "#868e96"
    )

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>WildfireFrontDynamics — Portal</title>
<style>
:root {{
  --bg: #0b0f14;
  --card: #141b24;
  --line: #243041;
  --text: #e9eef5;
  --muted: #8b9bb0;
  --accent: #3b82f6;
  --ok: #12b886;
  --warn: #f59f00;
  --bad: #fa5252;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; font-family: "Segoe UI", system-ui, sans-serif;
  background: var(--bg); color: var(--text); line-height: 1.45;
}}
a {{ color: #74c0fc; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
.hero {{
  background: linear-gradient(135deg, #12203a 0%, #0b0f14 60%);
  border-bottom: 1px solid var(--line);
  padding: 2rem 1.25rem 1.5rem;
}}
.hero-inner {{ max-width: 1080px; margin: 0 auto; }}
.hero h1 {{ margin: 0 0 .4rem; font-size: 1.85rem; letter-spacing: -0.02em; }}
.hero .tag {{ color: var(--muted); font-size: 1.05rem; max-width: 40rem; }}
.grid {{
  max-width: 1080px; margin: 0 auto; padding: 1.25rem;
  display: grid; gap: 1rem;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
}}
.card {{
  background: var(--card); border: 1px solid var(--line);
  border-radius: 14px; padding: 1.1rem 1.2rem;
}}
.card h2 {{ margin: 0 0 .75rem; font-size: 0.95rem; color: var(--muted);
  text-transform: uppercase; letter-spacing: .06em; font-weight: 600; }}
.card.wide {{ grid-column: 1 / -1; }}
.big {{ font-size: 2rem; font-weight: 750; letter-spacing: -0.03em; }}
.sub {{ color: var(--muted); font-size: .9rem; margin-top: .25rem; }}
.badge {{
  display: inline-block; padding: .45rem .9rem; border-radius: 999px;
  background: {badge_color}; color: #fff; font-weight: 800; font-size: 1.1rem;
}}
.pills {{ display: flex; flex-wrap: wrap; gap: .4rem; }}
.pill {{
  display: inline-block; padding: .2rem .55rem; border-radius: 999px;
  font-size: .75rem; font-weight: 600; border: 1px solid var(--line);
  background: #0f1620;
}}
.pill.ok {{ border-color: #0d6b4f; color: #63e6be; }}
.pill.warn {{ border-color: #8a6a00; color: #ffd43b; }}
.pill.bad {{ border-color: #8a2b2b; color: #ffa8a8; }}
table {{ width: 100%; border-collapse: collapse; font-size: .92rem; }}
th, td {{ padding: .5rem .4rem; border-bottom: 1px solid var(--line); text-align: left; }}
th {{ color: var(--muted); font-weight: 600; font-size: .78rem; text-transform: uppercase; }}
td.num {{ font-variant-numeric: tabular-nums; text-align: right; }}
.steps {{ counter-reset: s; list-style: none; padding: 0; margin: 0; }}
.steps li {{
  counter-increment: s; padding: .65rem .75rem .65rem 2.6rem;
  position: relative; border: 1px solid var(--line); border-radius: 10px;
  margin-bottom: .5rem; background: #0f1620;
}}
.steps li::before {{
  content: counter(s); position: absolute; left: .65rem; top: .55rem;
  width: 1.4rem; height: 1.4rem; border-radius: 50%;
  background: var(--accent); color: white; font-size: .8rem; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
}}
code {{
  background: #0a1018; padding: .12rem .35rem; border-radius: 4px;
  font-size: .85rem; color: #a5d8ff;
}}
pre.cmd {{
  background: #070b10; border: 1px solid var(--line); border-radius: 10px;
  padding: .9rem 1rem; overflow-x: auto; font-size: .82rem; color: #d0ebff;
  line-height: 1.5;
}}
.two {{ display: grid; gap: 1rem; grid-template-columns: 1fr 1fr; }}
@media (max-width: 720px) {{ .two {{ grid-template-columns: 1fr; }} }}
.footer {{ max-width: 1080px; margin: 0 auto 2rem; padding: 0 1.25rem; color: var(--muted); font-size: .85rem; }}
.work {{ display: grid; gap: .5rem; }}
.work .row {{
  display: flex; justify-content: space-between; gap: 1rem; flex-wrap: wrap;
  padding: .55rem .7rem; background: #0f1620; border-radius: 8px; border: 1px solid var(--line);
}}
.ok-text {{ color: var(--ok); font-weight: 700; }}
.warn-text {{ color: var(--warn); font-weight: 700; }}
</style>
</head>
<body>
  <header class="hero">
    <div class="hero-inner">
      <h1>WildfireFrontDynamics</h1>
      <p class="tag">
        <b>Qué es:</b> apoyo a la decisión en incendios con <b>confianza explícita</b>
        (GO / HOLD / ABSTAIN), métricas visibles y rastro auditable —
        no un visor más de mapas gratis.
      </p>
      <p class="tag" style="margin-top:.75rem">
        Actualizado: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC · git <code>{_git()}</code>
      </p>
    </div>
  </header>

  <section class="grid">
    <div class="card">
      <h2>Decisión ahora</h2>
      <div class="badge">{dec}</div>
      <div class="sub">Confianza del fenómeno: <b>{conf_s}</b> · Sistema reliability: <b>{card.get('system_reliability_pass')}</b></div>
      <p class="sub" style="margin-top:.6rem">Si faltan fuentes → ABSTAIN. No inventamos acción.</p>
    </div>
    <div class="card">
      <h2>ML España (v34)</h2>
      <div class="big">{iou}</div>
      <div class="sub">IoU holdout · Δ vs copy <b>{delta}</b></div>
      <div class="sub">Producto: clm_ensemble_v34 (no es ROS de dron)</div>
    </div>
    <div class="card">
      <h2>Open CEMS (sin NDA)</h2>
      <div class="big">{n_packs}</div>
      <div class="sub">packs públicos · hasta <b>{max_ha:.0f} ha</b></div>
      <div class="sub">Perímetros multi-día descargables</div>
    </div>
    <div class="card">
      <h2>Ops térmico (CLM)</h2>
      <div class="big">A</div>
      <div class="sub">Tobarra ancla · ROS ~5.7 m/min · ratio ~0.8</div>
      <div class="sub">Producto: incident_runtime_v1</div>
    </div>
  </section>

  <section class="grid">
    <div class="card wide">
      <h2>En 30 segundos — qué vendemos</h2>
      <div class="two">
        <div>
          <p><b>1. Thermal Front</b> — cuando hay cámara LWIR: ROS, grado, brief, envelope.</p>
          <p><b>2. Open Perimeter</b> — cuando no hay dron: CEMS multi-día + ha + mapa.</p>
          <p><b>3. Decision Card</b> — fusión con GO/HOLD/ABSTAIN + hash de auditoría.</p>
        </div>
        <div>
          <p class="ok-text">Sí se paga:</p>
          <p>saber cuándo confiar, cuándo callarse, y dejar rastro.</p>
          <p class="warn-text">No se vende:</p>
          <p>mapitas CEMS “porque sí”, ni 99.9999% de acierto del fuego.</p>
        </div>
      </div>
    </div>
  </section>

  <section class="grid">
    <div class="card wide">
      <h2>Un solo comando para recrear la demo</h2>
<pre class="cmd">cd C:\\Users\\Mariano\\Documents\\ALONSOO\\WildfireFrontDynamics
$env:PYTHONPATH = "C:\\Users\\Mariano\\Documents\\ALONSOO\\WildfireFrontDynamics"
python scripts\\show_all.py</pre>
      <p class="sub">Abre este portal, el hub de métricas y los mapas. Sin memorizar 40 scripts.</p>
    </div>
  </section>

  <section class="grid">
    <div class="card wide">
      <h2>Trabajo hecho (visible)</h2>
      <div class="work">
        <div class="row"><span>ML ensemble CLM v34 (holdout honesto)</span><span class="ok-text">HECHO · IoU {iou}</span></div>
        <div class="row"><span>Incident runtime + field kit</span><span class="ok-text">HECHO</span></div>
        <div class="row"><span>FDC en cada incident update (outbox)</span><span class="ok-text">HECHO · fire_decision_card.json</span></div>
        <div class="row"><span>Open IF CEMS multi-pack</span><span class="ok-text">HECHO · {n_packs} packs</span></div>
        <div class="row"><span>Decision Card CLI + reliability gate</span><span class="ok-text">HECHO</span></div>
        <div class="row"><span>Metrics Hub unificado</span><span class="ok-text">HECHO</span></div>
        <div class="row"><span>SLA incidente sintético (&lt;10 min)</span><span class="ok-text">HECHO · ver INCIDENT_SLA_LATENCY.json</span></div>
        <div class="row"><span>Plan 3 meses + cycle runner</span><span class="ok-text">HECHO · {done_items}/{n_items or '—'} items DONE</span></div>
        <div class="row"><span>2ª ancla INFOCAM / perímetro nacional</span><span class="warn-text">BLOQUEADO externo</span></div>
        <div class="row"><span>Piloto con cliente real</span><span class="warn-text">PENDIENTE humano</span></div>
      </div>
    </div>
  </section>

  <section class="grid">
    <div class="card wide">
      <h2>Packs open (mapas)</h2>
      <table>
        <thead><tr><th>Activación</th><th>Área</th><th>Pasos</th><th>O2 CEMS</th><th>Ver</th></tr></thead>
        <tbody>{pack_rows}</tbody>
      </table>
      <p class="sub"><a href="../outputs/open_if/index.html">Índice open_if</a></p>
    </div>
  </section>

  <section class="grid">
    <div class="card wide">
      <h2>Gates (estado)</h2>
      <div class="pills">{gate_pills or '<span class="pill">sin gates cargados — corre build_metrics_hub</span>'}</div>
    </div>
  </section>

  <section class="grid">
    <div class="card wide">
      <h2>Cómo enseñarlo (3 pasos)</h2>
      <ol class="steps">
        <li><b>ABSTAIN vacío</b> — <code>python -m wildfire_front decide</code> → el sistema se calla sin datos.</li>
        <li><b>Mapa open grande</b> — abrir EMSR632 (~5k ha) sin NDA.</li>
        <li><b>Incidente → Decision Card en outbox</b> — tras <code>incident update</code> lee <code>fire_decision_card.md</code> (GO/HOLD/ABSTAIN).</li>
      </ol>
    </div>
  </section>

  <section class="grid">
    <div class="card">
      <h2>Docs cortos (solo estos)</h2>
      <ul>
        <li><a href="START_HERE.md">START_HERE.md</a> — lectura 2 min</li>
        <li><a href="ONEPAGER_COMERCIAL_ES.md">One-pager venta</a></li>
        <li><a href="SUENOS_MAXIMOS.md">Sueños máximos</a> — techo de resultados y funciones</li>
        <li><a href="GUIA_COMANDOS_RECREAR_TODO.md">Comandos completos</a></li>
        <li><a href="PLAN_3_MESES.md">Plan 3 meses</a></li>
        <li><a href="PRODUCT_REDESIGN_PAID_VALUE.md">Por qué se paga</a></li>
      </ul>
    </div>
    <div class="card">
      <h2>Números clave</h2>
      <ul>
        <li>ML IoU: <b>{iou}</b></li>
        <li>ML Δ: <b>{delta}</b></li>
        <li>Open packs: <b>{n_packs}</b></li>
        <li>Max ha open: <b>{max_ha:.0f}</b></li>
        <li>Score dual vs CLM-solo: <b>{compare.get('score_dual')}</b> / <b>{compare.get('score_clm_only')}</b></li>
        <li>Decision: <b>{dec}</b> ({conf_s})</li>
      </ul>
    </div>
  </section>

  <p class="footer">
    Portal generado por <code>python scripts/build_portal.py</code>.
    No afirma precisión 99.9999% del fuego — solo reliability de no-GO-silencioso bajo tests.
  </p>
</body>
</html>
"""
    # fix accidental space in CSS if any
    html = html.replace("border-color: #a dig  #8a6a00;", "border-color: #8a6a00;")

    out = ROOT / "docs" / "PORTAL.html"
    out.write_text(html, encoding="utf-8")

    start = f"""# Empieza aquí (2 minutos)

## Qué es esto (1 frase)

**Apoyo a la decisión en incendios** con tres piezas claras:

1. **Ops térmico** (si hay dron/LWIR) → ROS y brief  
2. **Open CEMS** (si no hay dron) → perímetros públicos multi-día  
3. **Decision Card** → GO / HOLD / **ABSTAIN** + métricas + auditoría  

No es “otro mapa de Copernicus”. Es **cuándo confiar y cuándo callarse**.

## Abre esto

```powershell
cd C:\\Users\\Mariano\\Documents\\ALONSOO\\WildfireFrontDynamics
$env:PYTHONPATH = "C:\\Users\\Mariano\\Documents\\ALONSOO\\WildfireFrontDynamics"
python scripts\\show_all.py
```

Se abre el **portal** (`docs/PORTAL.html`) con números, trabajo hecho y enlaces.

## Tres números para enseñar

| Qué | Valor |
|-----|------:|
| ML v34 IoU holdout | **{iou}** |
| Packs open CEMS | **{n_packs}** (hasta ~{max_ha:.0f} ha) |
| Decisión ejemplo | **{dec}** (conf {conf_s}) |

## Solo 5 documentos (ignora el resto al principio)

| Doc | Para qué |
|------|----------|
| `docs/PORTAL.html` | **Ver todo** |
| `docs/START_HERE.md` | Este resumen |
| `docs/ONEPAGER_COMERCIAL_ES.md` | Venta |
| `docs/GUIA_COMANDOS_RECREAR_TODO.md` | Comandos largos |
| `docs/PLAN_3_MESES.md` | Roadmap |

El resto de `docs/` es archivo técnico / scorecards — no hace falta para la primera demo.

## Qué está hecho vs bloqueado

| Hecho | Bloqueado (externo) |
|-------|---------------------|
| ML v34, ops incident, 4 packs CEMS | 2ª ancla INFOCAM |
| Decision Card + Metrics Hub | Perímetro nacional oficial |
| Portal + demo 1 comando | Piloto con cliente real |

## Comando mínimo de decisión

```powershell
cd C:\\Users\\Mariano\\Documents\\ALONSOO\\WildfireFrontDynamics
$env:PYTHONPATH = "."
python -m wildfire_front decide                    # vacío → ABSTAIN
python -m wildfire_front decide --use-ml-v34 --open-pack outputs\\open_if\\emsr578 --require-ops-for-go
```
"""
    (ROOT / "docs" / "START_HERE.md").write_text(start, encoding="utf-8")
    print(json.dumps({"ok": True, "portal": str(out), "start_here": "docs/START_HERE.md"}, indent=2))
    return 0


if __name__ == "__main__":
    from datetime import datetime, timezone
    import json

    raise SystemExit(main())
