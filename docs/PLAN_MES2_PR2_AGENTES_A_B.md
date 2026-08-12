# Mes 2 — PR2 para Agentes A y B (humanos)

**Quién:** compañeros humanos A/B — **no** bots Grok.  
**Tras:** PR1-A [#32](https://github.com/AlonsoAlviraa/WildfireFrontDynamics/pull/32) uncertainty bar · PR1-B [#31](https://github.com/AlonsoAlviraa/WildfireFrontDynamics/pull/31) `decision_log.py` sidecar.  
**SSOT:** `docs/PLAN_MES2_PR1_AGENTES_A_B.md` · `docs/PLAN_30D_AGENTES_A_B_2026-08-12.md` · `docs/CURRENT_STATE.md`

## Rails

fusion **OFF** · GO_Q **partial** · FREEZE_ML · máx 1 PR/agente · paths disjuntos · squash + CI verde · A merge 09–13 · B 14–18 Madrid

---

## Baseline (no rehacer)

| Item | PR |
|------|-----|
| SPA + 501 | #19 |
| Operator + B3 | #18 / #22 |
| H1 panel / SR ladder / stub decision-log UI | #29 (y afines) |
| Uncertainty bar | #32 |
| Decision-log + ACK library | #31 (`wildfire_front/product/decision_log.py`) |

---

## PR2-A — Agente A

**Título:** `feat(spa): wire decision-log UI to real sidecar + ACK (#31)`  
**Branch:** `feat/mes2-a-pr2-decision-log-ui`

### Scope (solo A)
- `wildfire_front/product/app_spa.py` / `app_spa_html.py` / `spa_honesty_ui.py` (si existe)
- Tests: `tests/test_spa_*.py`, `tests/test_spa_honesty_ui.py`, `tests/test_product_app.py` según markers
- Docs opcionales: 1 párrafo en `docs/APP.md`

### Acceptance
1. SPA lee `decision_log.jsonl` vía API/`decision_log` de #31 (allowlisted `work_dir`) — **no** stub si el sidecar existe.
2. UI lista entradas (`decision_id`, decision, confidence_pred) + superficie ACK que llama `ack_decision` (loopback / same-origin serve only).
3. Si no hay log: copy honest “sin sidecar” (no inventar IDs).
4. Rails markers: fusion OFF · `go_q_met` false · no es ROS.
5. `make test-spa` verde.

### Non-goals
- Cambiar `decision_log.py` / `decide_service.py` (B)
- V&V / sector ROS / GO_Q true

### Done-when
Squash-merge CI verde; demo Estado→Decidir→ver log→ACK en loopback.

---

## PR2-B — Agente B

**Título:** `feat(vv): minimal V&V sidecar schema + script + test`  
**Branch:** `feat/mes2-b-pr2-vv-sidecar`

### Scope (solo B)
- Nuevo: p.ej. `wildfire_front/product/vv_sidecar.py` y/o `scripts/run_vv_sidecar.py`
- Schema JSON (campos mínimos: run_id, inputs_hash, checks[], status pass/fail/skip, rails snapshot)
- `tests/test_vv_sidecar.py`
- Eng status paragraph en `docs/CURRENT_STATE.md` (**sin** flip gates)
- Wire `cli.py` solo si hace falta un subcomando `vv-run` — **no** tocar `cli_app` / SPA

### Acceptance
1. Un comando documentado produce sidecar bajo work_dir allowlist (fail-closed path).
2. No claims de campo / no GO_Q / fusion OFF en snapshot embebido.
3. pytest + `check_release_flags` PASS.
4. Scorecard stub explícitamente **lab/eng** ≠ field GO.

### Non-goals
- SPA UI (A)
- Sector ROS default completo (→ PR3-B)
- Retrain / Hellín promote

### Done-when
Squash-merge; A puede enlazar lectura opcional en PR3 si aplica.

---

## Orden anti-choque

```
AM  → A abre PR2-A (depende de #31 ya en main)
PM  → B abre PR2-B en paralelo (cero solape de ficheros)
A merge ventana mañana; B tarde
```

## Tras ambos PR2 (preview PR3)

- **A-PR3:** split-conf polish / H1 dry-run checklist UX residual  
- **B-PR3:** sector ROS default (physics) + tests
