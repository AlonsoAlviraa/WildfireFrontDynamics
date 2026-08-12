# Mes 2 — PR3 para Agentes A y B (humanos)

**Quién:** compañeros humanos A/B — **no** bots Grok.  
**Tras:** PR2-A [#35](https://github.com/AlonsoAlviraa/WildfireFrontDynamics/pull/35) decision-log UI + ACK · PR2-B [#34](https://github.com/AlonsoAlviraa/WildfireFrontDynamics/pull/34) V&V sidecar eng.  
**SSOT:** `docs/PLAN_MES2_PR2_AGENTES_A_B.md` · `docs/PLAN_30D_AGENTES_A_B_2026-08-12.md` · `docs/CURRENT_STATE.md`

## Rails

fusion **OFF** · GO_Q **partial** · FREEZE_ML · máx 1 PR/agente · paths disjuntos · squash + CI verde · A merge 09–13 · B 14–18 Madrid

---

## Baseline (no rehacer)

| Item | PR |
|------|-----|
| SPA + 501 | #19 |
| Operator + B3 | #18 / #22 |
| H1 panel / SR ladder | #29 |
| Uncertainty bar | #32 |
| Decision-log + ACK library | #31 |
| Decision-log UI + ACK live | #35 |
| V&V sidecar eng stub | #34 (`vv_sidecar.py` · `scripts/run_vv_sidecar.py`) |

---

## PR3-A — Agente A

**Título:** `feat(spa): H1 dry-run polish + split-conf residual (mes2 PR3-A)`  
**Branch:** `feat/mes2-a-pr3-h1-polish`

### Scope (solo A)
- `wildfire_front/product/app_spa.py` / `app_spa_html.py` / `spa_honesty_ui.py` / `operator_ux.py` (si aplica)
- `docs/APP.md` y/o `docs/CHEATSHEET*` (checklist dry-run, máx 1–2 párrafos + bullets)
- Tests: `tests/test_spa_*.py`, `tests/test_spa_honesty_ui.py`, `tests/test_product_app.py` según markers

### Acceptance
1. Split-conf residual: labels ML/prediction vs ROS/ops consistentes en superficies Estado/Decidir (copy **no es ROS** · IoU ≠ ROS · conf ML ≠ ROS).
2. H1 dry-run checklist UX: panel/rehearsal usable en loopback; siempre `go_q_met=false` / no inventar GO_Q.
3. Decision-log UI (#35) no se rompe: lectura sidecar + ACK fail-closed / sin stub con IDs inventados.
4. Rails markers en pack SPA: fusion OFF · `go_q_invent_forbidden`.
5. `make test-spa` (o pack SPA) verde.

### Non-goals
- Cambiar `decision_log.py` / `vv_sidecar.py` / `decide_service.py` (B)
- Sector ROS physics · V&V field claims · GO_Q true · fusion ON
- Marketing copy / one-pagers

### Done-when
Squash-merge CI verde; operador hace Estado→Decidir→log→ACK→checklist H1 eng en loopback sin claims de campo.

---

## PR3-B — Agente B

**Título:** `feat(ros): sector ROS default (physics eng) + tests (mes2 PR3-B)`  
**Branch:** `feat/mes2-b-pr3-sector-ros`

### Scope (solo B)
- Módulo physics/sector ROS bajo ownership B (p.ej. `wildfire_front/product/` o path ROS ya existente — **no** SPA)
- Tests: `tests/test_*sector*ros*.py` o pack conf/decide según markers reales
- Eng status paragraph en `docs/CURRENT_STATE.md` (**sin** flip gates)
- Wire `cli.py` solo si hace falta un subcomando eng documentado — **no** `cli_app` / SPA

### Acceptance
1. Default sector ROS **physics/eng** documentado; explícito ≠ field GO / ≠ tactical speed sell.
2. Tests verdes del path sector ROS; fail-closed si inputs incompletos (sin inventar métricas).
3. Snapshot/docs: fusion OFF · GO_Q partial · FREEZE_ML; no retrain.
4. `check_release_flags` PASS; no promover Hellín / no claims O2.

### Non-goals
- SPA UI (A)
- Retrain / fusion ON / GO_Q invent
- V&V field-validated scorecard (sigue stub eng #34)

### Done-when
Squash-merge; A puede enlazar label/read-only en polish residual si hace falta (PR aparte, no este).

---

## Orden anti-choque

```
AM  → A abre PR3-A (paths SPA/docs A)
PM  → B abre PR3-B en paralelo (cero solape)
A merge ventana mañana; B tarde
```

## Tras ambos PR3 (preview W3 / mes2 next)

- **A-W3 residual:** E2E eng doc contra decision-log + V&V reales; a11y/touch residual
- **B-W3:** FREEZE_ML data-request pack (O1/B4/B5) · forensics allowlist harden · CURRENT_STATE mid refresh
- **Humano Alonso:** agenda H1 tercero + acta (único flip GO_Q)

## Qué NO hacer este PR3

- Delegar a bots Grok como “Agente A/B”
- Ampliar a CI gate full + data FOI fills en el mismo PR
- Marketing / outreach sin Claims clear
