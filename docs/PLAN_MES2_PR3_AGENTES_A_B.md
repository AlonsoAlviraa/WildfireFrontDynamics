# Mes 2 — PR3 para Agentes A y B (humanos)

**Quién:** compañeros humanos A/B — **no** bots Grok.  
> **Historical Mes2 brief.** Living gates: `docs/CURRENT_STATE.md` — fusion **ON** (human 2026-08-13; cap 0.20 / abstain 0.45) ≠ GO_Q complete ≠ despacho. Rails below were **at filing**.
**Tras:** PR2-A [#35](https://github.com/AlonsoAlviraa/WildfireFrontDynamics/pull/35) decision-log UI+ACK · PR2-B [#34](https://github.com/AlonsoAlviraa/WildfireFrontDynamics/pull/34) V&V sidecar.  
**SSOT:** `docs/PLAN_MES2_PR2_AGENTES_A_B.md` · `docs/PLAN_30D_AGENTES_A_B_2026-08-12.md` (A5/A6 · B6) · `docs/CURRENT_STATE.md` · `docs/HANDOFF_MES2_PR3_HUMANOS_2026-08-12.md`

## Rails (no negociables)

- `field_ops` ML fusion **OFF**
- `GO_Q` **partial** (nunca inventar `true` / complete)
- `FREEZE_ML_AND_REQUEST_DATA` (no retrain)
- No métricas de campo inventadas · no publish externo sin Alonso
- No revive `#10` / `fix/b2-b3-flags-noise*`
- Máx. **1 PR abierto por agente** · paths disjuntos · rebase diario · squash + CI verde
- Merge windows Madrid: **A 09–13** · **B 14–18**

---

## Baseline en main (no rehacer)

| Item | PR |
|------|-----|
| SPA Live Ops + 501 | #19 |
| Operator hub + B3 smoke | #18 / #22 |
| H1 eng pack / SR ladder | #29 |
| Uncertainty bar + no-ROS copy | #32 (PR1-A) |
| Decision-log + ACK backend | #31 (PR1-B) |
| Decision-log UI + ACK wire | #35 (PR2-A) |
| V&V scorecard stub | #34 (PR2-B) |
| Mes2 PR1/PR2 briefs | #30 / #33 |

---

## Ownership (anti-colisión)

| Owner | Paths (PR3) |
|-------|-------------|
| **PR3-A only** | `wildfire_front/product/app_spa.py`, `app_spa_html.py`, `spa_honesty_ui.py`, `operator_ux.py`, `plain_language.py`, `teach_path.py`, `live_ops.py` (UI only), `tests/test_spa_*.py`, `tests/test_spa_honesty_ui.py`, `tests/test_product_app.py`, `tests/test_plain_language_app.py`, docs `APP.md` / `CHEATSHEET*` / `LIVE_OPS*` (copy only) |
| **PR3-B only** | `wildfire_front/emergency_products.py` (sector ROS), envelope / physics helpers already owned by backend, `tests/test_*sector*` / `tests/test_emergency_products.py` (extend), optional `docs/design/*envelope*` or eng note in `CURRENT_STATE.md`, **no** SPA files |
| **Wire** | Ninguno en PR3 salvo hotfix CI del owner del fail. No tocar `cli.py` si no hace falta smoke sector. |

---

## PR3-A — Agente A (H1 / split-conf polish)

**Título:** `feat(spa): H1 eng polish + split-conf ML≠ROS (mes2 PR3-A)`  
**Branch:** `feat/mes2-a-pr3-h1-split-conf`  
**Alineado a:** plan 30d **A5** (split conf UI) + residual **A6** (H1 eng rehearsal polish)

### Scope
1. **Split conf UI** — labels/copy que separan **ML conf** ≠ **ROS conf** (o banda de incertidumbre); assert fusion OFF en markers/tests.
2. **H1 eng polish** — dry-run 12 min usable en loopback (`app --serve` / cheatsheet path); `go_q_met` sigue false; no acta inventada.
3. Tests SPA markers + copy “no es ROS” / “no es despacho táctico”.

### Done-when
- [ ] `make test-spa` (o pack SPA pytest) verde en CI
- [ ] UI markers: split conf visible + fusion OFF
- [ ] H1 rehearsal eng documentado / ejercitable sin poner `GO_Q=true`
- [ ] Squash-merge CI verde

### Non-goals
- Backend decide / decision_log / vv_sidecar / sector ROS (B)
- GO_Q true · fusion ON · marketing outbound

---

## PR3-B — Agente B (sector ROS eng + tests)

**Título:** `feat(ops): sector ROS eng default + tests (mes2 PR3-B)`  
**Branch:** `feat/mes2-b-pr3-sector-ros`  
**Alineado a:** plan 30d **B6** (sector ROS default, physics path; no ML retrain)

### Scope
1. **Sector ROS default eng** — path physics existente (`compute_sector_ros` / emergency products); default eng documentado sin vender GO_Q o field grade.
2. **Tests** — pytest verdes sobre head/flank/rear split, fail-closed sin primary ROS, no claims de campo en snapshot/docs.
3. **Honesty** — un párrafo en `CURRENT_STATE` o design note: “default eng · no es ROS táctico validado”.

### Done-when
- [ ] pytest sector / emergency products verdes
- [ ] Docs eng: default sin GO_Q / fusion ON
- [ ] FREEZE_ML respetado (no retrain Tobarra)
- [ ] Squash-merge CI verde

### Non-goals
- SPA UI (A)
- V&V scorecard redesign (#34 ya shipped)
- Hellín promote · invent metrics · fusion ON

---

## Orden anti-choque

```
AM  → A abre PR3-A (paths SPA only)
PM  → B abre PR3-B en paralelo (emergency_products / tests only)
A merge 09–13; B 14–18 (si ambos verdes el mismo día)
```

## Tras PR3 (preview)

- **A:** integración UI lectura V&V real (solo lectura) si B4/B5 ya en main  
- **B:** FREEZE_ML data-request pack (B7) / forensics allowlist (B8)  
- **Humano:** H1 acta tercero → único path a GO_Q
