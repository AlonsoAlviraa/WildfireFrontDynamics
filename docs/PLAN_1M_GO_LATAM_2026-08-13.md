# Plan 1 mes — continuación de la línea actual (2026-08-13 → 2026-09-12)

**Repo:** WildfireFrontDynamics  
**Alcance:** lo que ya se está haciendo en esta línea de trabajo (GO total honesto, LATAM+AU, rails, datos externos) — no un relanzamiento de Mes2 SPA.  
**SSOT de gates:** `docs/CURRENT_STATE.md` · `docs/ML_PRODUCT_GO_STATUS.json` · `docs/GO_TOTAL_STATUS.json`  
**Companion:** `docs/data_campaigns/LATAM_AU_P0_P2_STATUS.md` · `docs/H1_GO_Q_RUNBOOK.md` · `docs/BOTTLENECKS_B1_B6_STATUS.md`

---

## 0. Norte del mes

### Objetivo principal
**GO_TOTAL honesto** = `GO_MES=true` **y** `GO_Q=complete` con acta H1 real (tercero externo + `record_h1_demo_complete` exit 0 + stamp/`CURRENT_STATE` alineados + `check_release_flags` PASS).

### Objetivos secundarios (no bloquean GO_TOTAL)
1. **LATAM+AU lab data** usable: packs open + real_proxy NDWS documentado; CONAF respuesta/cesión si llega; sin inventar transfer IoU.  
2. **B4/B5 prep** (2ª ancla / O2): calendarios + requests + probes; **sin** inventar grade A ni GO_MES+.  
3. **Producto demo-ready estable**: fusion ON, FREEZE intact, operator 7/7, no despacho táctico.

### No-goals (explícitos)
- Inventar GO_Q / tercero / acta PENDING  
- FREEZE lift / retrain Tobarra / v35  
- Vender complete_proxy_model_iou (~0.85) como transfer IoU sellado  
- GO_MES+ true sin 2ª grade A + path O2 honesto  
- Despacho táctico / “apagamos incendios con IA”  
- Relanzar SPA/decision-log/V&V stub (ya shipped)

---

## 1. Baseline al día 0 (2026-08-13) — no rehacer

| Área | Estado |
|------|--------|
| GO_MES | **true** |
| GO_Q | **partial** (eng listo; humano abierto) |
| field_ops fusion | **ON** (human 2026-08-13) |
| GO_MES+ | **false** |
| FREEZE Tobarra KEEP | **false** (KILL) |
| H1 eng prep | **7/7** · `eng_session_ready=true` · `go_q_met=false` |
| record_h1 + flags | Wiring SSOT listo: complete **solo** con `h1_acta` real |
| LATAM+AU | 6 packs `ml_weak`; CONAF **sent_gmail**; complete_proxy usable-pair mean ~0.737 (FEP/GRA excluded; EMSR715 no growth pair; **not** transfer; **not** dressed ~0.85) |
| CONAF `lab_ok_conaf` | **false** hasta cesión escrita |
| SPA / Mes2 PR1–PR3-A | Shipped (#19/#31/#32/#34/#35/#38) |
| Sector ROS eng | #39 si sigue abierto: cerrar CI, sin claim de campo |

---

## 2. Rails no negociables (todo el mes)

| Rail | Valor |
|------|--------|
| GO_Q | partial → complete **solo** vía acta real |
| GO_MES+ | false hasta criterios |
| field_ops fusion | **ON** (≠ despacho) |
| FREEZE | no retrain Tobarra / no KEEP reopen |
| IoU ≠ ROS / Vp | siempre |
| Claims | no marketing externo sin Alonso; claim board limpio |
| Secrets | no revive bases con secretos |

Verificación diaria (B o CI):
```bash
python scripts/check_release_flags.py   # PASS
python -m wildfire_front operator checklist   # eng 7/7; go_q_met false hasta H1
```

---

## 3. Roles

| Rol | Responsabilidad |
|-----|-----------------|
| **Eng / Agent B** | Flags, H1 plumbing, LATAM+AU scripts, data honesty, CURRENT_STATE, probes B4/B5, CI smokes |
| **Eng / Agent A** | Operator/SPA polish menor si hace falta para demo; cheatsheet; no flip gates |
| **Humano Alonso** | Agenda tercero H1 + demo + acta; promote Hellín/2ª ancla; legal CEMS comercial; cesión CONAF si llega; GO_MES+ decide |
| **Externo** | Tercero demo · CONAF OIRS · FOI/partner O2 · datos 2º IF |

---

## 4. Semanas (4 × ~7 días)

### Semana 1 (13–19 ago) — Cerrar el camino al GO_TOTAL (lado eng + agenda)

**Tema:** todo lo eng-closable del GO_Q ya está; el mes empieza por **calendario humano** y higiene de demo.

| ID | Owner | Acción | Done-when |
|----|-------|--------|-----------|
| **W1-H1** | Alonso | Agendar **1 tercero** (emergencias / uni / partner) con `docs/H1_CALENDAR_INVITE.md` | Fecha+nombre en calendario; slot 12–30 min |
| **W1-H2** | Alonso + eng | Ensayo dry-run operator (actos 1–4) **sin** reclamar GO_Q | Checklist 7/7; kill list verbal ensayada |
| **W1-E1** | Eng | Re-run `prepare_h1_demo_session.py`; verificar pack `outputs/demo_third_party` + reliability pointer | Session JSON fresco; `go_q_met=false` |
| **W1-E2** | Eng | SSOT: `GO_TOTAL_STATUS.json` + CURRENT_STATE eng note “H1 slot booked / not booked” | Sin flip GO_Q |
| **W1-E3** | Eng | Si #39 abierto: merge sector ROS eng o documentar hold; no field ROS | CI verde o hold explícito |
| **W1-D1** | Eng | LATAM+AU: re-run residual tests; log CONAF `sent_gmail` + folio si hay respuesta | Tests residual PASS |

**Salida S1:** fecha de demo H1 en el calendario **o** bloqueo documentado (sin tercero = GO_TOTAL sigue false).

---

### Semana 2 (20–26 ago) — Demo H1 + acta **o** intensificar datos externos

**Rama A (preferida si hay tercero):**

| ID | Owner | Acción | Done-when |
|----|-------|--------|-----------|
| **W2-H1** | Alonso | Demo 12 min (`CHEATSHEET` + operator) | Demo hecha; kill list dicha |
| **W2-H2** | Alonso | Acta real `docs/actas/ACTA_DEMO_YYYYMMDD_<org>.md` | Fecha + Presentador + Tercero reales |
| **W2-H3** | Alonso/eng | `record_h1_demo_complete.py --acta …` | Exit **0**; stamp GO_Q complete; `h1_acta` OK |
| **W2-E1** | Eng | `check_release_flags` PASS con complete + h1 evidence; actualizar GO_TOTAL_STATUS `met=true` | GO_TOTAL true |

**Rama B (si no hay tercero aún — no inventar):**

| ID | Owner | Acción | Done-when |
|----|-------|--------|-----------|
| **W2-D1** | Eng | CONAF: si hay folio OIRS → `--confirm-oirs-paste`; si hay cesión → `record_conaf_cession` | `lab_ok_conaf` solo con evidencia |
| **W2-D2** | Eng | Expand real_proxy covariates a packs restantes (EMSR408, EMSR715, weak) | Report `n_ready` ↑; schema honest |
| **W2-D3** | Eng | Warp S2→CEMS en packs con EO; registrar proxy IoU (no model IoU) | Warp reports en `outputs/ml_eval/latam_au_warp/` |
| **W2-B4** | Eng+Alonso | B4: follow-up Hellín / Cardoso scorecard path; `b4_b5_status_probe` | Status JSON actualizado; grade null si falta |

**Salida S2:** **GO_TOTAL true** **o** `GO_TOTAL_STATUS` con blocker humano + progreso datos.

---

### Semana 3 (27 ago–2 sep) — Post-H1 (si cerró) o max pressure datos + GO_MES+ prep

**Si GO_Q complete (S2 Rama A):**

| ID | Owner | Acción | Done-when |
|----|-------|--------|-----------|
| **W3-P1** | A/Eng | Congelar copy demo: “GO_Q complete con acta X; fusion ON ≠ despacho” | CHEATSHEET + APP notes |
| **W3-P2** | Eng | Claim board sync; no marketing sin Alonso | Claim board limpio |
| **W3-M1** | Alonso/Eng | Arrancar GO_MES+ **prep only**: 2ª ancla + O2 FOI checklist | B4/B5 calendar items con due dates |
| **W3-D4** | Eng | LATAM+AU: LOFO non-CLM sigue `model_iou=null` honest; opcional sealed harness doc | No inventar transfer IoU |

**Si GO_Q sigue partial:**

| ID | Owner | Acción | Done-when |
|----|-------|--------|-----------|
| **W3-H1** | Alonso | 2º intento de agenda (otra org / uni) | Nuevo slot o escalado escrito |
| **W3-D5** | Eng | Materializar +1 pack open si hay URL auditada; inventory rights | Pack o gap documentado |
| **W3-E2** | Eng | Endurecer tests residual CONAF/NDWS/flags (regresión anti-invent) | pytest verde |

**Salida S3:** o producto “post-GO_Q” estable, o datos/outreach maximizados con GO_Q still partial honest.

---

### Semana 4 (3–12 sep) — Cierre del mes + handoff a Mes3

| ID | Owner | Acción | Done-when |
|----|-------|--------|-----------|
| **W4-S1** | Eng | Snapshot mes: `CURRENT_STATE` + `GO_TOTAL_STATUS` + LATAM campaign status + B1–B6 | SSOT alineado; flags PASS |
| **W4-S2** | Eng | Scorecard 30d: qué se midió (proxy IoU, packs, envíos) vs qué no (transfer, GO_MES+) | Doc corto en `docs/` o actualización status |
| **W4-H1** | Alonso | Si aún no H1: decisión go/no-go de fecha límite Mes3; **no** forzar GO_Q | Decisión escrita en handoff |
| **W4-M2** | Eng | Handoff a `PLAN_MES3` (12 sep): fusion **ON** (corregir plan Mes3 si aún dice OFF), GO_Q real state, LATAM residual | `HANDOFF` o nota en Mes3 plan |
| **W4-D6** | Eng | CONAF/CEMS: estado legal/comercial sin inventar `lab_ok` / rehost | Gates honestos |

**Salida S4 (definición de “mes cumplido”):**
- **Éxito fuerte:** GO_TOTAL true + flags PASS + LATAM residual documentado.  
- **Éxito honesto (mínimo):** GO_Q partial con eng 7/7 + demo pack + 2+ outreach H1 intentados + LATAM P0–P2 residual cerrado o en espera externa + handoff Mes3 limpio.  
- **Fallo:** inventar GO_Q / transfer IoU / cesión / GO_MES+.

---

## 5. Tracks paralelos (todo el mes)

### Track G — GO_Q / GO_TOTAL (crítico)
```
Agenda tercero → Demo 12min → Acta firmada → record_h1 exit 0 → check_release_flags PASS
```
Artefactos: `H1_GO_Q_RUNBOOK.md`, `record_h1_demo_complete.py`, `GO_TOTAL_STATUS.json`.

### Track L — LATAM+AU (lab data)
| Item | Estado inicio | Acción mes |
|------|---------------|------------|
| CONAF OIRS | sent_gmail | Folio / paste confirm / cesión → `lab_ok_conaf` |
| Cesión tooling | shipped | Solo flip con evidencia |
| real_proxy NDWS | Perth+Nacimiento | Expand packs; IoU proxy etiquetado |
| CEMS commercial | gate firmado o no | Legal si rehost producto |
| Transfer IoU | null / blocked | Mantener null hasta sealed harness + owner |

### Track B4/B5 — GO_MES+ prep (stretch)
- Hellín `pending_external` hasta cite + promote Alonso  
- O2 FOI/partner calendar; **no** flag invention  
- Probe: `python scripts/b4_b5_status_probe.py`

### Track P — Product honesty
- fusion ON visible en narrative  
- FREEZE + REQUEST_DATA  
- complete_proxy ≠ experimental_partial_fill ≠ sealed transfer  
- Operator rails AMARILLO hasta H1

---

## 6. Cadencia operativa

| Ritmo | Qué |
|-------|-----|
| **Diario** | `check_release_flags` PASS; no PRs que inventen gates |
| **2×/semana** | Actualizar `GO_TOTAL_STATUS.json` (met + blockers) |
| **Semanal** | 15 min: ¿hay fecha H1? ¿respuesta CONAF? ¿B4 scorecard? |
| **Fin de mes** | Snapshot + handoff Mes3 (12 sep) |

PR hygiene (si hay PRs eng):
- Máx. 1 PR grande abierto por track  
- Paths disjuntos (A surface / B honesty)  
- CI verde; squash preferido  

---

## 7. Criterios de aceptación del mes

### Debe ser verdad al 12-sep
1. `check_release_flags` **PASS**  
2. FREEZE intact (`tobarra_keep_reopen=false`)  
3. GO_MES+ **false** salvo criterios reales cumplidos (improbable en 30d)  
4. `GO_TOTAL_STATUS.json` actualizado y coherente con stamp  
5. Ningún claim de transfer IoU / despacho táctico en docs de producto  

### Ideal (GO_TOTAL)
6. `GO_Q=complete` con `stamp.h1_acta` real  
7. `H1_DEMO_SESSION_READY.go_q_met=true`  
8. Operator semáforo coherente con complete (si se actualiza copy)

### LATAM (best effort)
9. CONAF: respuesta o follow-up documentado  
10. ≥2 packs con covariates real_proxy ready  
11. Tests residual + campaign **PASS**

---

## 8. Riesgos y mitigación

| Riesgo | Mitigación |
|--------|------------|
| Sin tercero H1 todo el mes | Éxito honesto mínimo; 2º canal outreach; no inventar acta |
| CONAF no responde | Mantener outbox + reenvío; `lab_ok_conaf=false` |
| Confusión proxy IoU vs transfer | Etiquetas `complete_proxy` / `not_claims` en todo artefacto |
| Mes3 plan desfasado (fusion OFF) | Handoff W4 corrige a fusion **ON** |
| Presión a “GO total” por autoridad | Solo `record_h1` con acta real cierra el gate |

---

## 9. Comandos canónicos del mes

```bash
# Rails
python scripts/check_release_flags.py

# H1 eng
python scripts/prepare_h1_demo_session.py
python -m wildfire_front operator checklist
# Tras demo real:
python scripts/record_h1_demo_complete.py --acta docs/actas/ACTA_DEMO_YYYYMMDD_<org>.md

# CONAF
python scripts/dispatch_conaf_oirs.py --confirm-oirs-paste --ticket <folio> --by Alonso
python scripts/record_conaf_cession.py --evidence <path> --signer "CONAF …" --by Alonso

# LATAM NDWS
python scripts/fill_latam_au_ndws_covariates.py --all
python scripts/adapt_latam_au_to_ndws_patches.py --mode real_proxy --zero-shot-eval
python scripts/run_latam_au_complete_model_iou.py

# B4/B5
python scripts/b4_b5_status_probe.py
```

---

## 10. Entregables a escribir/actualizar (cuando se ejecute el plan)

| Artefacto | Cuándo |
|-----------|--------|
| `docs/PLAN_1M_GO_LATAM_2026-08-13.md` (este plan en repo) | Día 0 |
| `docs/GO_TOTAL_STATUS.json` | 2×/semana |
| `docs/CURRENT_STATE.md` eng notes | Tras H1 o fin de semana |
| `docs/data_campaigns/LATAM_AU_*_STATUS.md` | Tras cada sprint datos |
| Handoff Mes3 (fusion ON, GO_Q state) | W4 |

---

## 11. Resumen en una frase

**Este mes no “fabricamos” el GO: dejamos el producto listo, conseguimos (si hay humano) el acta H1 que cierra GO_TOTAL, y seguimos la campaña LATAM+AU / B4–B5 con honestidad de datos — FREEZE y no-despacho intactos.**
