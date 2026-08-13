# Plan 30 días — Agentes A y B (2026-08-13 → 2026-09-11)

**Repo:** AlonsoAlviraa/WildfireFrontDynamics  
> **Historical 30d brief** (filed 2026-08-12). Living gates: `docs/CURRENT_STATE.md` — field_ops ML fusion **ON** (human 2026-08-13; cap 0.20 / abstain 0.45) ≠ GO_Q complete ≠ despacho. Rails below were the constraint **at filing**.
**Rails (at filing, 2026-08-12):** `field_ops` ML fusion **OFF** · `GO_Q` **partial** (nunca inventar `true`) · `FREEZE_ML_AND_REQUEST_DATA` · no métricas inventadas · no publish externo sin Alonso · no merge de ramas con secretos (`fix/b2-b3-flags-noise*`, tip #10).

**Objetivo del mes:** SPA Live Ops usable en `main` + honesty/V&V/data path + eng H1 listo. Demo+acta tercero = **humano Alonso** (fuera del stack A/B).

---

## Roles

### Agente A — Product Surface
SPA / Live Ops UI, `cli_app` + `--serve`, operator UX copy, demo H1 eng pack UI/cheatsheet, uncertainty + decision-log **UI**, docs APP / LIVE_OPS / CHEATSHEET.

### Agente B — Platform & Data Honesty
`decide` / forensics / confidence / api_server, V&V sidecar, DATA_INTAKE / Hellín SSOT, sector ROS default, CI + `check_release_flags`, FREEZE_ML data-request docs only (**no retrain**), hooks de Claims/scorecard.

### Humano Alonso (fuera de A/B)
H1 agenda + acta firmada · rotar tokens fuera de git · promote Hellín · Claims clear marketing · reconnect GitHub en Cursor · merge GO_Q solo con evidencia.

---

## Ownership de ficheros (anti-colisión PR)

| Owner | Paths |
|-------|--------|
| **A only** | `wildfire_front/product/app_spa.py`, `app_spa_html.py`, `live_ops.py`, `operator_ux.py`, `plain_language.py`, `teach_path.py`, `fire_catalog.py`, `wildfire_front/map_status/**`, `wildfire_front/cli_app.py`, `tests/test_spa_*.py`, `tests/test_product_app.py`, `tests/test_plain_language_app.py`, `tests/test_app_spa_security.py`, `docs/APP.md`, `docs/design/LIVE_OPS*`, `docs/CHEATSHEET*` |
| **B only** | `wildfire_front/product/decide_service.py`, `forensics.py`, `confidence.py`, `api_server.py`, `policy.py`, `wildfire_front/cli_operator.py`, `cli_report.py`, `data/**` honesty manifests (no PII dumps), `docs/DATA_*`, `docs/CURRENT_STATE.md` (B editor; A review), `scripts/check_release_flags*`, V&V scripts/tests, sector ROS modules/tests owned today by backend |
| **Wire (solo 1 PR, 1 owner/semana)** | `wildfire_front/cli.py`, `Makefile` — ver regla de coordinación |

### Reglas de coordinación
1. **Máx. 1 PR abierto por agente.** El otro rebasea `main` y espera.
2. **Nunca los dos tocan el mismo fichero la misma semana.**
3. Si hace falta wire en `cli.py` / `Makefile`: el owner de esa semana abre un PR *wire* **después** de que el otro haya mergeado su base, o se asigna un solo owner esa semana.
4. Alternancia merge Europe/Madrid: **A mañana (09–13)** · **B tarde (14–18)** si ambos verdes el mismo día.
5. Rebase diario sobre `main`. Squash-merge preferido. CI verde obligatorio.
6. Prohibido: cherry-pick desde bases con secretos; ampliar scope a rasters/FOI/Gmail.

---

## Semana 1 (13–19 ago) — Cerrar superficie + honesty base

### A-W1 (orden)
1. **A1** — Merge/stabilize SPA land (`#19` o follow-up): `make test-spa` verde; `liveUnavailableFallback` presente.  
   *Done-when:* SPA pack pytest PASS en CI; sin paths PII.  
   *Non-goals:* multihorizon, fusion UI, tip `decide_service`.
2. **A2** — Demo dry-run eng: cheatsheet 12 min + script path `app --serve` documentado en `docs/CHEATSHEET*` / APP.  
   *Done-when:* un operador puede hacer Estado→Decidir→Acta offline con copy-CLI.
3. **A3** — Uncertainty bar (UI only): mostrar bandas ya existentes; no inventar scores.  
   *Done-when:* test UI marker + copy “no es ROS”.

### B-W1 (orden)
1. **B1** — CURRENT_STATE + release flags alineados post-SPA (si #19 mergeó).  
   *Done-when:* `check_release_flags` PASS; GO_Q sigue partial.
2. **B2** — DATA_INTAKE / Hellín: mantener `pending_external`; checklist cite→promote (docs only).  
   *Done-when:* `docs/DATA_ANCHOR_SSOT.md` + test honesty sin promover.
3. **B3** — CLI/operator regression guard (#18): tests exit 2 + operator hub smoke.  
   *Done-when:* no regresión vs main tip.

**Wire W1:** A posee `cli.py` solo si queda residual SPA; B no toca `cli.py` esta semana.

---

## Semana 2 (20–26 ago) — V&V + decisión trazable

### A-W2
1. **A4** — Decision-log UI + ACK surface (mostrar log; no inventar ACK backend si B aún no shippea).  
   *Done-when:* Último acto / panel muestra id de decisión stub o real si B4 merged.
2. **A5** — Split conf UI: ML conf ≠ ROS conf labels.  
   *Done-when:* copy + test markers; fusion OFF assert.

### B-W2
1. **B4** — Decision-log + ACK **backend** (sidecar JSON en work_dir allowlist).  
   *Done-when:* pytest escribe/lee log; loopback only.
2. **B5** — V&V sidecar mínimo (schema + run script + test).  
   *Done-when:* un comando documentado produce scorecard stub sin claims de campo.
3. **B6** — Sector ROS default (physics path; no ML retrain).  
   *Done-when:* tests sector ROS verdes; docs “default eng” sin vender GO_Q.

**Wire W2:** B posee `cli.py` si registra subcomandos V&V; A no toca `cli.py`.

---

## Semana 3 (27 ago–2 sep) — H1 eng pack + data requests

### A-W3
1. **A6** — H1 eng session pack UI polish (third-party rehearsal, no GO_Q true).  
   *Done-when:* Demo Engineer puede correr 12 min en loopback; `go_q_met` false.
2. **A7** — SR ladder UI (escala de soporte/recomendación) con non-claims.  
   *Done-when:* markers + tests; Claims Guardian checklist adjunto en PR body.

### B-W3
1. **B7** — FREEZE_ML data-request pack: qué pedir (O1/B4/B5) sin reentrenar.  
   *Done-when:* doc + manifest templates; ML Lab freeze respectado.
2. **B8** — Forensics replay hardening + work_dir allowlist tests.  
   *Done-when:* pytest forensics PASS; no path traversal.
3. **B9** — Update CURRENT_STATE mid-month (honest stamps only).

**Wire W3:** ninguno, salvo hotfix CI (owner del fail).

---

## Semana 4 (3–11 sep) — Integración + freeze pre-demo

### A-W4
1. **A8** — Integración UI contra decision-log/V&V reales de B (solo lectura APIs/files).  
   *Done-when:* dry-run E2E eng documentado; grabación opcional.
2. **A9** — Bugfix / a11y / touch targets residual SPA.  
   *Done-when:* SPA pack + smoke manual checklist.

### B-W4
1. **B10** — CI gate: SPA pack + release flags + V&V smoke en Makefile/CI.  
   *Done-when:* CI en main verde con targets nuevos.
2. **B11** — Pre-demo freeze doc: lista de non-goals + claim board sync (con Claims Guardian).  
   *Done-when:* `docs/CURRENT_STATE.md` + claim board paths actualizados; GO_Q partial explícito.
3. **B12** — Buffer: solo fixes de CI/regresión.

**Humano (cualquier semana):** H1 acta → solo Alonso marca GO_Q; A/B **nunca** ponen `GO_Q=true`.

---

## Cadencia diaria (ambos)

```
09:00 A rebase + CI
09–13 A merge window si verde
14:00 B rebase + CI
14–18 B merge window si verde
EOD: cada uno deja 3 líneas: merged / blocked / next PR tip
```

Conflictos: el que **no** es owner del fichero abandona el hunk y pide wire PR al owner.

---

## Definition of Done (30 días)

- [ ] SPA Live Ops en `main` (sin base secreta)
- [ ] Operator + `app --serve` + copy-CLI 501 path
- [ ] Decision-log + ACK (backend B + UI A)
- [ ] V&V sidecar mínimo
- [ ] Sector ROS default (eng)
- [ ] CURRENT_STATE / flags PASS
- [ ] H1 eng rehearsal listo; GO_Q sigue partial hasta acta humana
- [ ] Cero PRs con PII/secret paths
- [ ] Marketing sigue embargado hasta Claims clear (humano)

## Explicit kill list

- Retrain / fusion ON / GO_Q inventado  
- Merge #10 / b2-b3  
- Outbound marketing sin Claims  
- Ampliar a rasters bulk / FOI fills en git  
