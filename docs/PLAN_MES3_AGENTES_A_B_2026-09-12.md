# Plan Mes 3 — Agentes A y B (2026-09-12 → 2026-10-11)

**Repo:** AlonsoAlviraa/WildfireFrontDynamics  
**Quién:** compañeros humanos **A** (Product Surface) y **B** (Platform & Data Honesty) — **no** bots Grok.  
**SSOT previa:** `docs/PLAN_30D_AGENTES_A_B_2026-08-12.md` · `docs/PLAN_MES2_PR3_AGENTES_A_B.md` · `docs/CURRENT_STATE.md`  
**Handoff:** `docs/HANDOFF_MES3_HUMANOS_2026-09-12.md`

## Contexto (honest)

El plan 30d (13 ago–11 sep) y los slices “Mes2 PR1–PR3” se **adelantaron** en eng (ago). Mes 3 **no** relanza SPA/decision-log/V&V stub: asume tip `main` post-#38 (PR3-A) y post-**#39** (PR3-B sector ROS) cuando mergee.

## Baseline en main (no rehacer)

| Item | PR |
|------|-----|
| SPA Live Ops + 501 CLI fallback | **#19 shipped** |
| Decision-log + ACK library | **#31 shipped** |
| Uncertainty bar + no-ROS | **#32 shipped** |
| V&V eng scorecard sidecar | **#34 shipped** |
| SPA decision-log UI + loopback ACK | **#35 shipped** |
| H1 eng polish + split-conf ML≠ROS | **#38 shipped** |
| Mes2 PR3 docs + CURRENT_STATE refresh | **#37 shipped** |
| Sector ROS eng default + tests | **#39 in flight** (B cierra antes de W1-B si sigue abierto) |

**Objetivo del mes:** stack **demo-tercero listo** + camino honest hacia GO_MES+ **sin inventar gates**.  
GO_Q sigue **partial** hasta acta firmada de Alonso. Marketing embargado hasta Claims clear.

## Rails (no negociables)

- `field_ops` ML fusion **OFF**
- `GO_Q` **partial** (nunca inventar `true` / complete)
- `FREEZE_ML_AND_REQUEST_DATA` (no retrain Tobarra)
- No métricas de campo inventadas · no publish externo sin Alonso
- No revive `#10` / `fix/b2-b3-flags-noise*`
- Máx. **1 PR abierto por agente** · paths disjuntos · rebase diario · squash + CI verde
- Merge windows Madrid: **A 09–13** · **B 14–18**

## Ownership (igual que 30d)

| Owner | Paths |
|-------|--------|
| **A** | `app_spa*`, `spa_honesty_ui`, `live_ops` UI, `cli_app`, `operator_ux`, `plain_language`, `map_status`, tests `test_spa_*` / `test_product_app*`, docs APP / CHEATSHEET / LIVE_OPS |
| **B** | `decide_service`, `decision_log`, `vv_sidecar`, `forensics`, `confidence`, `emergency_products`, `cli_operator`, `data/**` honesty, `CURRENT_STATE`, `check_release_flags*`, V&V/CI scripts |
| **Wire** | `cli.py` / `Makefile` — un solo owner/semana (ver cada PR) |
| **Humano Alonso** | H1 agenda+acta · Hellín promote · Claims/marketing · tokens · flip GO_Q |

---

## Prerrequisito (antes o día 0 Mes 3)

| Item | Estado esperado |
|------|-----------------|
| Mes2 PR3-A H1/split-conf | **Shipped** #38 |
| Mes2 PR3-B sector ROS eng | **#39** merge CI verde (si aún abierto al start: B cierra antes de W1-B) |
| Gates | GO_MES true · GO_Q partial · fusion OFF · GO_MES+ false · Hellín pending_external |

---

## W1 (12–18 sep) — Residual 30d / “demo eng plumbing”

### PR-W1-A — Agente A
**Título:** `feat(spa): read V&V eng sidecar + E2E eng notes (mes3 W1)`  
**Branch:** `feat/mes3-a-w1-vv-ui`

**Scope:** SPA solo lectura de `vv_scorecard` (#34); empty/sin-sidecar honest; párrafo E2E eng en APP/CHEATSHEET.  
**Done-when:** markers + tests; no inventar field scores; `go_q_met=false`; `make test-spa` CI verde.  
**Non-goals:** cambiar `vv_sidecar.py` · GO_Q true · fusion ON.

### PR-W1-B — Agente B
**Título:** `docs+ci: FREEZE data-request pack + forensics allowlist + CI smokes (mes3 W1)`  
**Branch:** `feat/mes3-b-w1-freeze-ci`  
*(si el pack supera 1 PR limpio: partir en W1-B data-request y W1-B2 CI — máx 1 abierto a la vez)*

**Scope:**  
1. FREEZE_ML data-request pack (qué pedir O1/B4/B5) — docs/templates, **no retrain**  
2. Forensics `work_dir` allowlist harden + tests fail-closed  
3. CI/Makefile: SPA pack + `check_release_flags` + V&V smoke  

**Done-when:** pytest forensics + flags PASS; CI targets documentados/verdes; CURRENT_STATE eng note **sin** flip gates.  
**Non-goals:** SPA · Hellín promote · invent O2 flags.

**Wire W1:** B posee `Makefile`/`cli.py` si registra smokes.

---

## W2 (19–25 sep) — H1 eng freeze

### PR-W2-A — Agente A
**Título:** `feat(spa): H1 12min rehearsal freeze copy (mes3 W2)`  
**Branch:** `feat/mes3-a-w2-h1-freeze`

**Scope:** polish rehearsal + cheatsheet “**no es acta H1**” · copy-CLI serve/offline · rails visibles.  
**Done-when:** operador repite Estado→Decidir→log→ACK→checklist en loopback; tests markers; CI verde.  
**Non-goals:** `record_h1_demo_complete` / GO_Q true.

### PR-W2-B — Agente B
**Título:** `docs: pre-demo freeze + claim board sync (mes3 W2)`  
**Branch:** `docs/mes3-b-w2-predemo-freeze`

**Scope:** pre-demo freeze doc + sync claim board paths (Claims Guardian checklist en PR body); CURRENT_STATE mid-month honesty.  
**Done-when:** GO_Q partial explícito; non-claims list; flags PASS.  
**Non-goals:** marketing outbound · flip GO_MES+.

---

## W3 (26 sep–2 oct) — Datos process (sin humo)

### PR-W3-A — Agente A
**Título:** `fix(spa): a11y/touch + honest empty states (mes3 W3)`  
**Branch:** `feat/mes3-a-w3-a11y`

**Scope:** touch targets / a11y residual + empty states sin IDs inventados.  
**Done-when:** SPA pack verde + smoke checklist.  
**Non-goals:** backend · nuevos claims.

### PR-W3-B — Agente B
**Título:** `docs(data): Hellín cite→promote checklist + O2/FOI honesty path (mes3 W3)`  
**Branch:** `docs/mes3-b-w3-data-path`

**Scope:** Hellín permanece `pending_external` hasta cite+Alonso; checklist promote; FOI/O2 path docs **sin** inventar flags/scorecards.  
**Done-when:** DATA_ANCHOR / intake docs alineados; honesty tests PASS; no promote en git.  
**Non-goals:** rasters bulk · retrain · fusion ON.

---

## W4 (3–11 oct) — Integración + buffer

### PR-W4-A — Agente A
**Título:** `docs(demo): E2E eng dry-run record notes (mes3 W4)`  
**Branch:** `docs/mes3-a-w4-e2e`

**Scope:** doc dry-run E2E (grabación opcional); enlaza V&V UI + decision-log + H1 freeze.  
**Done-when:** path documentado; sin GO_Q invent.  
**Non-goals:** features nuevas grandes.

### PR-W4-B — Agente B
**Título:** `chore(ci): regression buffer + CURRENT_STATE month-end (mes3 W4)`  
**Branch:** `chore/mes3-b-w4-buffer`

**Scope:** solo fixes CI/regresión + CURRENT_STATE month-end (**gates honestos**).  
**Done-when:** main CI verde; GO_Q partial / GO_MES+ false salvo evidencia humana real.  
**Non-goals:** scope creep features.

---

## Humano Alonso (cualquier semana)

| Acción | Efecto |
|--------|--------|
| Agenda H1 tercero + acta firmada | Único path a GO_Q complete |
| Cite + promote Hellín | 2nd grade A / B4 |
| Claims clear | Levanta embargo marketing |
| Rotar tokens / reconnect GitHub Cursor | Ops |

A/B **nunca** ponen `GO_Q=true` ni fusion ON.

---

## Definition of Done (Mes 3)

- [ ] #39 (PR3-B) en main si no lo estaba
- [ ] V&V UI lectura + E2E eng doc
- [ ] FREEZE data-request pack + forensics harden + CI smokes
- [ ] H1 rehearsal freeze repetible; `go_q_met=false` hasta acta
- [ ] Pre-demo freeze + claim board sync
- [ ] Hellín/O2 path docs honest (sin promote inventado)
- [ ] Month-end CURRENT_STATE alineado; marketing embargado
- [ ] GO_MES+ solo con evidencia — si no, **false**

## Explicit kill list

- Retrain / fusion ON / GO_Q inventado  
- Merge #10 / b2-b3  
- Outbound marketing sin Claims  
- Ampliar a rasters bulk / FOI fills en git  
- Delegar Mes 3 eng a bots Grok como “Agente A/B"
