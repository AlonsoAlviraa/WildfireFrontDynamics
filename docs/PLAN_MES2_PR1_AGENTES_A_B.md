# Mes 2 — PR1 para Agentes A y B (humanos)

**Ventana:** 2026-09-12 → 2026-10-11 (después del plan 30d #20)  
> **Historical Mes2 brief.** Living gates: `docs/CURRENT_STATE.md` — fusion **ON** (human 2026-08-13; cap 0.20 / abstain 0.45) ≠ GO_Q complete ≠ despacho.
**Repo:** AlonsoAlviraa/WildfireFrontDynamics · tip `main` post-#19 SPA + #22 operator  
**Quién:** compañeros humanos **A** (Product Surface) y **B** (Platform & Data Honesty) — **no** bots Grok.  
**SSOT previa:** `docs/PLAN_30D_AGENTES_A_B_2026-08-12.md` · `docs/CURRENT_STATE.md`

## Rails (iguales)

- `field_ops` ML fusion **OFF**
- `GO_Q` **partial** (nunca inventar `true`)
- `FREEZE_ML_AND_REQUEST_DATA` (no retrain)
- No métricas inventadas · no publish externo sin Alonso
- No revive `#10` / `fix/b2-b3-flags-noise*`
- Máx. **1 PR abierto por agente** · paths disjuntos · rebase diario · squash + CI verde
- Merge windows Madrid: **A 09–13** · **B 14–18**

---

## Baseline (ya en main — no rehacer)

| Item | PR |
|------|-----|
| SPA Live Ops + 501 CLI fallback | #19 |
| Operator hub + B3 smoke | #18 / #22 |
| CURRENT_STATE + 30d plan docs | #13 / #20 |
| Honesty / Hellín pending (si mergeó W1 B) | ver `docs/CURRENT_STATE.md` tip |

---

## PR1-A — Agente A (abrir primero, mañana)

**Título sugerido:** `feat(spa): uncertainty bar + no-ROS copy (mes2 PR1)`  
**Branch:** `feat/mes2-a-pr1-uncertainty-bar`

### Scope (solo paths A)
- `wildfire_front/product/app_spa_html.py` (+ `app_spa.py` si payload)
- `tests/test_spa_layout.py` / `tests/test_product_app.py` según markers
- Opcional docs: `docs/APP.md` o `docs/CHEATSHEET_DEMO_12MIN.md` (1 párrafo)

### Acceptance
1. UI muestra banda/uncertainty ya existente en payload (no inventar scores nuevos).
2. Copy visible: **no es ROS** / no velocidad táctica.
3. Assert rails en HTML/JSON: `field_ops_ml_live_fusion` OFF · `go_q_invent_forbidden`.
4. `make test-spa` (o pack SPA pytest) verde en CI.

### Non-goals
- Decision-log ACK backend (eso es B)
- Multihorizon / fusion UI / GO_Q true
- Tocar `decide_service.py`, `forensics.py`, `cli_operator.py`

### Done-when
PR squash-merged a `main` con CI verde + checklist en body.

---

## PR1-B — Agente B (abrir después del merge A-PR1 **o** en paralelo si cero solape de ficheros)

**Título sugerido:** `feat(decide): decision-log + ACK sidecar (mes2 PR1)`  
**Branch:** `feat/mes2-b-pr1-decision-log-ack`

### Scope (solo paths B)
- `wildfire_front/product/decide_service.py` y/o módulo nuevo bajo `wildfire_front/product/` (p.ej. `decision_log.py`)
- `wildfire_front/product/forensics.py` solo si el log vive en bundle (mínimo)
- Tests nuevos: `tests/test_decision_log.py` (nombre libre)
- Docs: párrafo en `docs/CURRENT_STATE.md` (Eng status) — **sin** flip de gates

### Acceptance
1. Cada decide escribe sidecar JSON bajo `work_dir` **allowlist** (path traversal fail-closed).
2. ACK endpoint o CLI hook loopback-only; test lee/escribe log.
3. `go_q_met` sigue false; fusion OFF en snapshot.
4. pytest del pack B + `check_release_flags` PASS.

### Non-goals
- UI SPA / `app_spa*` / `cli_app` (A)
- Retrain / sector ROS completo (B mes2 PR2+)
- Promover Hellín / inventar GO_Q

### Done-when
PR squash-merged; A puede leer el log en mes2 PR2 (UI).

### Wire
Si hace falta registrar subcomando en `cli.py`: **solo B** esta semana, PR aparte `chore(cli): wire decision-log` **después** de PR1-B, o un solo commit al final de PR1-B sin tocar `cli_app`.

---

## Orden recomendado (anti-choque)

```
Día 1 AM  → A abre PR1-A
Día 1–2   → A CI verde → squash merge
Día 1 PM  → B puede abrir PR1-B en paralelo (ficheros disjuntos)
Día 2–3   → B CI verde → squash merge (ventana tarde)
EOD       → cada uno: merged / blocked / next tip (3 líneas a Alonso)
```

---

## Qué NO hacer este PR1

- Delegar a bots Grok como “Agente A/B”
- Ampliar a V&V completo + sector ROS + SR ladder en el mismo PR
- Marketing / outreach / FOI fills en git

## Siguiente tras ambos PR1 (mes2 PR2 — preview)

- **A-PR2:** Decision-log UI + ACK surface leyendo sidecar de B  
- **B-PR2:** V&V sidecar mínimo (schema + script + test)
