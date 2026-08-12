# Plan 1 mes — activo post-parallel (2026-08-04)

> **Base plan (histórico):** `docs/PLAN_1_MES_MEJORA_GLOBAL.md` (horizonte 2026-07-17 → 2026-08-17)  
> **Este documento es el plan activo** para los días restantes (~2026-08-04 → **2026-08-17**).  
> **Machine snapshot:** `docs/PLAN_1_MES_STATUS_20260804.json`  
> **Graph:** `.grok/graph_engineering/STATE.md` **v6.1** (human demo + eng evidence + research-backed R\*)  
> **Mes completo implement:** `docs/PLAN_1_MES_GRAPH_V6_IMPLEMENT.md` (horizonte → 2026-09-04)  
> **Research → IDs:** `docs/fire_intel/RESEARCH_TO_GRAPH_V6_MAP.md`  
> **Does not replace** kill list / dual-product honesty of the base plan.

---

## 0. Snapshot post-parallel (2026-08-04)

| Item | Estado |
|------|--------|
| **O1 multi-ancla** | **PASS** (Tobarra Vp 7 + Hellín Vp 50 confirmed) |
| **Fuel stack PR-α/β** | **DONE** on main + AEMET Tobarra + envelope v3 (peso 0 táctico) |
| **Track A eng** | **BLOCKED** — Hellín best pack grade **B**, ROS ~27.9, ratio ~0.56 in-band; no grade A + in-band |
| **Track B templates** | **DONE** — acta / guion 30 min / informe esqueleto (shells) |
| **Track C honesty** | **DONE** — Estrella/Cardoso `pending_external`; `DATA_PROXY_HONESTY.md` |
| **1h loop Hellín** | **DONE** — best retained; extra param chase regressed → restored |
| **GO_MES** | **GO_MES=true** (plan mínimo 2026-08-04) — `docs/GO_MES_VERDICT.md` |
| **Fusion field_ops** | **OFF** · `ml_product_go=false` |

Evidence: `docs/O1_GOMES_RECOMPUTE_20260803.json`, `docs/P1_HELLIN_ENG_STATUS.md`, `docs/HELLIN_TRACK_A_SCORECARD.md`, `data/infocam_anchors.json`, `docs/DATA_PROXY_HONESTY.md`, `docs/SCORECARD_MES_1.md`.

---

## 1. GO_MES formula (unchanged) — current fill

```
GO_MES = O1 ∧ O4 ∧ P1 ∧ M2 ∧ E1
```

| Component | Met? | Note |
|-----------|------|------|
| O1 | **yes** | Tobarra 7 + Hellín 50; ratios in-band (best pack) |
| O4 | **yes** | field kit / brief eng |
| P1 | **yes** | smoke incident 2 IF reales (Tobarra+Hellín) sin crash — **not** grade A |
| M2 | **yes** | v34 catalog hold |
| E1 | **yes** | eng CI |

**Verdict now:** **GO_MES = true** (plan mínimo).  
**GO_MES+** still needs O2 national / **O5** 2º grade A / demo stretch.  
**Hellín grade A** remains eng-blocked for O5 — see `docs/P1_HELLIN_ENG_STATUS.md`.

---

## 2. What is DONE (do not re-litigate)

### Engineering / data

| ID | Deliverable | Evidence |
|----|-------------|----------|
| O1 | Multi-ancla PASS | `docs/O1_GOMES_RECOMPUTE_20260803.json` |
| Fuel PR-α/β | AEMET + envelope v3 on main | `docs/design/PR_PLAN_FUEL_AEMET_ENVELOPE.md` |
| Track A pack | Hellín front_dynamics vs Vp 50 | `outputs/observatorio/hellin_2024/` |
| Track A BLOCKED | Grade A + in-band unreachable under current rules+data | `docs/P1_HELLIN_ENG_STATUS.md` |
| 1h loop | Multi-config; best B/0.559 restored | `outputs/plan_1h_loop/` · scorecard |
| Track C anchors | Hellín confirmed; Estrella/Cardoso proxy only | `data/infocam_anchors.json` · `docs/DATA_PROXY_HONESTY.md` |
| Track D maintain | Fuel tests / honesty rails | scorecards fuel-AEMET |

### Product templates (Track B shells)

| ID | Deliverable | Path |
|----|-------------|------|
| B-template acta | Acta demo 1 p. | `docs/ACTA_DEMO_TERCERO_TEMPLATE.md` |
| B-template guion | Guion 30 min post-O1 | `docs/GUION_DEMO_30MIN_POST_O1.md` |
| B-template informe | Esqueleto 8–12 pp | `docs/INFORME_TRIMESTRE_ESQUELETO.md` |

---

## 3. What remains (~2026-08-04 → 2026-08-17)

### P0 — Human / product (primary)

| # | Task | Deliverable | Gate | Owner |
|---|------|-------------|------|-------|
| **H1** | **Demo real 30 min con tercero** | Acta **rellenada + firmada** | **M3.2** | Human |
| **H2** | Informe trimestre **relleno** 8–12 pp | MD/DOCX desde esqueleto | **M3.4** / GO_Q | Human |
| H3 | Optional: thank-you / no Cardoso spam | email hygiene | outreach | Human |

### P1 — Engineering optional (not GO_MES main engine)

| # | Task | Deliverable | Gate | Note |
|---|------|-------------|------|------|
| E1 | Optional Hellín grade A | only if **policy/data** change (new frames, rule review) | P1 / O5 | Do **not** tune params hoping for magic |
| E2 | Status sync after any gate change | SCORECARD + recompute JSON | hygiene | |
| E3 | O2 national Hausdorff | SHP/GPKG EGIF or stay BLOCKED | O2 | External |
| E4 | CyL wait | silence / calendar ~2026-08-17 | D1 | No re-spam |

### Explicit non-work

- Endless Hellín param grids for structural A + in-band under current rules  
- Invented 3ª ancla from Estrella SITAC / Cardoso Δha  
- Joint k Tobarra(7)+Hellín(50)  
- `field_ops` fusion ON or `ml_product_go=true`  
- Claiming GO_MES true from O1 alone or from eng BLOCKED doc alone  

---

## 4. New priority order (post-parallel)

1. **Human demo M3.2** (third-party + acta signed) → primary product unlock  
2. **Informe fill M3.4** (evidence paths only; no fake metrics)  
3. **Status / scorecard hygiene** after human gates  
4. **Optional eng** only if new Hellín data or explicit P1 policy change  
5. **External wait** O2 SHP / CyL calendar  
6. **Autonomous honesty** weekly (not main GO_MES engine)  
7. Fire intel / literature maintain (season)

**Graph primary shift:** eng Hellín chase → **human demo first**; eng optional.

---

## 5. Capacity split (remaining ~2 weeks)

| Slice | % | Work |
|-------|---|------|
| **Human demo / write** | **50%** | M3.2 acta · M3.4 informe · guion rehearsal |
| DATA honesty / outreach hygiene | **15%** | no invented Vp; CyL wait |
| ENG optional / hygiene | **20%** | sync, CI, optional Hellín only if unblocked |
| OPS maintain | **15%** | packs smoke; fuel regression if touched |

---

## 6. Kill list (updated)

| # | Forbidden |
|---|-----------|
| K1 | Claim **GO_MES true** with only O1 PASS |
| K2 | Claim **GO_MES true** because Hellín eng is **BLOCKED** documented — BLOCKED ≠ P1 closed |
| K3 | Invent ROS / Vp / ha without source |
| K4 | Use Cardoso ha/h or Estrella SITAC Vp as **confirmed** INFOCAM anchors |
| K5 | Calibrate single physics **k** on Tobarra(7) + Hellín(50) without fire-class split |
| K6 | Silent rescale ROS → Vp |
| K7 | Flip `field_ops` ML live fusion **ON** or `ml_product_go=true` |
| K8 | Present FIRMS hull as official burned area |
| K9 | Re-open O1 as “missing 2ª ancla” (already PASS) |
| K10 | Endless param tuning as substitute for policy/data on Hellín P1 |

---

## 7. Exit criteria by 2026-08-17

| Outcome | Criteria |
|---------|----------|
| **Best** | Demo acta signed (M3.2) + informe filled (M3.4) + honest scorecard; GO_MES only if P1 truly closes under policy |
| **Good** | M3.2 demo done; M3.4 draft advanced; P1 remains eng BLOCKED written; **NO_GO_MES** explicit |
| **Minimum** | Templates used for at least one scheduled demo or written reschedule; scorecard honest; no claim inflation; **GO_MES=false** |

**Rails at exit (always):** no invented Vp · **GO_MES false** unless formula fully met · fusion **OFF**.

---

## 8. Rituals

| When | Action |
|------|--------|
| Before demo | Rehearse `docs/GUION_DEMO_30MIN_POST_O1.md`; open P0 material |
| After demo same day | Fill `docs/ACTA_DEMO_TERCERO_TEMPLATE.md` → `docs/actas/…` |
| After M3.2 / M3.4 land | `wfd-status-sync` + SCORECARD + this plan checkboxes |
| 2–3×/week | `wfd-external-unblock` (**demo / O2**, not Cardoso O1) |
| Weekly | `wfd-autonomous-cycle` + honesty |
| Daily season | `wfd-fire-intel-scrape` only if mega-fire news |

**Authority chain:** live anchors JSON → O1 recompute → `P1_HELLIN_ENG_STATUS` → SCORECARD_MES_1 → **this plan** → graph STATE v5 → `PLAN_1_MES_STATUS_20260804.json`.

---

## 9. Key paths (one table)

| Asset | Path |
|-------|------|
| This plan (active) | `docs/PLAN_1_MES_POST_O1_UNLOCK.md` |
| Status JSON | `docs/PLAN_1_MES_STATUS_20260804.json` |
| Base plan | `docs/PLAN_1_MES_MEJORA_GLOBAL.md` |
| Graph STATE | `.grok/graph_engineering/STATE.md` |
| O1 recompute | `docs/O1_GOMES_RECOMPUTE_20260803.json` |
| P1 eng BLOCKED | `docs/P1_HELLIN_ENG_STATUS.md` |
| Proxy honesty | `docs/DATA_PROXY_HONESTY.md` |
| Hellín scorecard | `docs/HELLIN_TRACK_A_SCORECARD.md` |
| Guion / acta / informe | `docs/GUION_DEMO_30MIN_POST_O1.md` · `ACTA_DEMO_TERCERO_TEMPLATE.md` · `INFORME_TRIMESTRE_ESQUELETO.md` |
| Graph evolution | `docs/graph_evolution/graph_evolution.md` |

---

## 10. Track status rollup

| Track | Status 2026-08-04 | Next |
|-------|-------------------|------|
| **A eng Hellín** | **BLOCKED** (evidence written) | Optional only if new data/policy |
| **B human product** | Templates **DONE**; demo/informe **PENDING** | **H1 demo · H2 fill** |
| **C data honesty** | **DONE** rails | Maintain; no false anchors |
| **D fuel** | **DONE** maintain | Regression if code touch |

---

*Documento vivo. Actualizar tras M3.2 / cualquier cambio de P1. Graph pointer: **v5**.*
