# Plan 1 mes — Graph Engineering **v6.1** (implementación + research)

> **Horizonte:** 2026-08-04 → **2026-09-04**  
> **Mode:** Graph Engineering **v6.1** — *evidence + third-parties + research-backed ops*  
> **STATE:** `.grok/graph_engineering/STATE.md`  
> **Machine:** `docs/PLAN_1_MES_GRAPH_V6_STATUS.json`  
> **Research bridge:** `docs/fire_intel/RESEARCH_TO_GRAPH_V6_MAP.md`  
>
> **Inputs fusionados (ampliados):**
> 1. Plan post-O1 → `docs/PLAN_1_MES_POST_O1_UNLOCK.md`
> 2. Reunión senior → `docs/REUNION_RESUMEN_Y_ANALISIS_ACCIONES.md`
> 3. Industria CA/CN/ferias/OSS → `docs/fire_intel/INDUSTRY_RESEARCH_2024_2026_CONGRESOS_FERIAS_OSS.md`
> 4. Mega SOTA mejoras → `docs/MEGA_RESEARCH_MEJORAS_SOTA_2024_2026.md`
> 5. SOTA stack adopción → `docs/fire_intel/SOTA_STACK_ADOPTION_2026.md`
> 6. Corpus ROS/fuel → `docs/fire_intel/LITERATURE_CORPUS_ROS_FUEL.md` + `data/fire_intel/literature/corpus_v1.json`
> 7. Fire intel / CEMS → `docs/fire_intel/COMPLETION_MATRIX.md` · mega-fires
> 8. Research CN / roadmaps → `research/chinese_research.md` · `research/*` (históricos; no primary)
> 9. GO_MES → `docs/GO_MES_VERDICT.md` (**true**)
>
> **No reemplaza** kill list dual-product / fusion OFF / no inventar anclas.

---

## 0. Diagnóstico unificado (planes + research)

| Fuente | Dice | Decisión graph v6.1 |
|--------|------|---------------------|
| **Plan post-O1** | GO_MES=true; M3.2 human; Hellín grade A blocked O5 | Mantener |
| **Reunión senior** | Fallo = evidencia + terceros, no CI | E1–E3 critical path |
| **Industria** | Hueco ROS LWIR; ferias; ELMFIRE/ForeFire | I* + E8; no “otro Technosylva” |
| **Mega SOTA** | B1 sector + B2 UQ + B7 envelope + A1 EFFIS; no más NDWS physics | R-B1/B2 + open; C7 G1 muerto |
| **SOTA stack 2026** | Lampman TIR→ROS método; Orion UQ→ABSTAIN; RGB-TIR ≠ ROS táctico | E2 cites; fusion OFF reinforced |
| **Corpus fuel ~93** | MED fuels + hybrid α + abstain sin viento | maintain fuel; cite in report |
| **CN research** | Multimodal/attention/instance FT | lab only; contract metadata CN UAV |
| **Gap real** | Templates sin acta; research sin empaquetar para terceros | **Research entra en E2/E9/pack, no en retrain** |

```text
GO_MES  = true   (mínimo; hold)
GO_MES+ = false
GO_Q    = partial → target mes
ml_product_go = false · field_ops fusion OFF
research_hours_retrain_ML = 0  (métrica de éxito = contención)
```

---

## 1. Objetivo del mes (una frase)

> **Stack de evidencia reproducible para terceros**, anclado en research SOTA (Lampman-class ops TIR, Orion-class UQ rails, fuel Med corpus), sin reabrir retrain ML ni Hellín param spam.

### Exit criteria (2026-09-04)

| Nivel | Criterios |
|-------|-----------|
| **Best** | M3.2 acta + M3.4 informe + demo zip + Reliability Report **con citas research** + open freshness + thermal contract + scorecard GO_Q |
| **Good** | Pack+report+replay DONE + demo o shadow commitment + informe ≥70% + ≥3 citas research en report + OSS catalog |
| **Minimum** | Pack one-cmd + Report Tobarra/Hellín + agenda demo + research map status actualizado + no claim inflation |
| **Fail** | Solo scorecards; retrain “por un paper”; fusion flip; anclas inventadas; research sin entregable |

---

## 2. Topology v6.1 (ampliada)

```text
                         ┌─ H-PRIMARY ─ human: demo M3.2 + acta ──► GO_Q
                         ├─ H-WRITE ─── informe M3.4 (citar research)
                         │
                         ├─ E-P0 ────── demo-with-third-parties pack
                         ├─ E-P0 ────── Reliability Gate Report (+ Lampman/Orion/fuel)
                         ├─ E-P0 ────── replay forense one-command
                         │
                         ├─ E-P1 ────── thermal contract multi-provider (CN UAV ready)
                         ├─ E-P1 ────── open freshness + checksum (+ EFFIS/CEMS hygiene)
                         ├─ E-P1 ────── Decision Card reasons + u_data band (Orion rails)
                         ├─ E-P1 ────── metrics honesty one-pager (IoU≠ROS)
                         │
                         ├─ R-P1 ────── research: sector ROS export note/partial (B1)
                         ├─ R-P1 ────── research: OSS+datasets catalog (ELMFIRE, TS-SatFire…)
                         ├─ R-P2 ────── research: ELMFIRE/ForeFire spike Tobarra
                         ├─ R-P2 ────── research: FIRMS direction overlay one pack
                         ├─ R-P2 ────── research: EO/LWIR pair inventory (no net train)
                         ├─ R-LAB ───── frozen: WFTS/Swin/CN-CA/RF-ROS promote
                         │
                         ├─ I-CAL ───── OWTRD · Red Sky · ICFFR · INTERSCHUTZ
                         ├─ X-WAIT ──── O2 · CyL · 3ª ancla formal
                         │
                         ├─ 2–3×/week ► wfd-external-unblock
Sense / research hygiene ┼─ weekly ───► wfd-status-sync
                         ├─ weekly ───► wfd-autonomous-cycle
                         ├─ season ───► wfd-fire-intel-scrape
                         ├─ on lit ───► wfd-literature-ingest → update RESEARCH_TO_GRAPH map
                         ├─ after open ► wfd-open-pack-audit
                         └─ on code ─► wfd-pilot-regression
```

**v6 → v6.1:** se añade track **R-*** explícito (research-backed eng) y se **fusionan** mega-SOTA / SOTA_STACK / corpus / CN en el DAG. Primary product **no** cambia.

---

## 3. Tracks

### Track H — Human / product (PRIMARY capacity)

| ID | Task | Done when | Gate | Research use |
|----|------|-----------|------|--------------|
| **H1** | Demo 30 min tercero | Acta firmada `docs/actas/` | **M3.2** | Guion: Lampman método + Orion ABSTAIN |
| **H2** | Informe trimestre | 8–12 pp filled | **M3.4** | **ENG_FILLED** `docs/INFORME_TRIMESTRE_2026_Q_PRODUCTO.md` (human stamp optional) |
| **H3** | Dry-run pack | 1 run zip offline | — | **ENG READY** `make dry-run-demo-third-party` → `DRY_RUN_REPORT.md`; **human operator still TODO** |
| **H4** | Shadow outreach 1 org | Commitment escrito | adoption | No pitch IoU |
| **H5** | CyL silence ~17 ago | Nota CONTACTOS | D1 | **DONE** `docs/fire_intel/CYL_SILENCE_RULE_NOTE.md` (wait ~2026-08-17) |

### Track E — Engineering evidence (critical path)

| ID | Task | Done when | P | Research ancla |
|----|------|-----------|---|----------------|
| **E1** | demo-with-third-parties pack | zip + README + field_ops card | **P0** | **DONE** `scripts/build_demo_third_party_pack.py` |
| **E2** | Reliability Gate Report 1–3 pp | MD third-party + **§ research** | **P0** | **DONE** `docs/RELIABILITY_GATE_REPORT_THIRD_PARTY.md` |
| **E3** | Replay one-command | exit 0 = replay_ok | **P0** | **DONE** `scripts/run_third_party_replay.py` |
| **E4** | Thermal contract harden | metadata platform/res/provider | **P1** | **DONE** contract + `validate_geotiff_contract.py` |
| **E5** | Open freshness + checksum | ≥1 pack manifest fields | **P1** | **DONE** `audit_open_pack_freshness.py` |
| **E6** | Card reasons + uncertainty visible | export legible + u band | **P1** | **DONE** `render_decision_card_md` |
| **E7** | Hub abstention slice | JSON/fields abstain_rate | **P2** | **DONE** `build_metrics_hub.py` → `hub.abstention` |
| **E9** | Honesty one-pager IoU≠ROS | `docs/` 1 p. | **P1** | **DONE** `docs/METRICS_HONESTY_IOU_NE_ROS.md` |
| **E10** | Portal/START_HERE sync | after gates | hygiene | **DONE** START_HERE pointers |

### Track R — Research-backed eng (NEW explicit)

| ID | Task | Done when | P | Source docs |
|----|------|-----------|---|-------------|
| **R-UQ1** | Map aleatoria/epistémica → GO/HOLD/ABSTAIN in report+card notes | Written mapping + no EVAC labels | **P0** (with E2) | **DONE** E2 §3 + card UQ band |
| **R-STACK-L** | Lampman paragraph in E2 (method not SLA) | In report | **P0** | **DONE** E2 §1 |
| **R-DATA1** | Catalog OSS/datasets (ELMFIRE, ForeFire, TS-SatFire, BCWildfire, Orion UQ repo, RoboFireFuseNet) | Update OPEN_RESOURCES or fire_intel note | **P1** | **DONE** `OSS_DATASETS_CATALOG_2026.md` |
| **R-B1** | Sector ROS head/flank/rear: export or gap note on Tobarra | Scorecard section or deferred | **P1** | **DONE** `SECTOR_ROS_TOBARRA_NOTE.md` |
| **R-SIM1** | ELMFIRE **or** ForeFire vs Tobarra ROS (compare only) | 1 p. note numbers | **P2** | **DONE** `ELMFIRE_FOREFIRE_SPIKE_NOTE.md` |
| **R-A1** | EFFIS/CEMS perimeter attempt 1 IF (Hausdorff lite) | script or pack note | **P1–P2** | **DONE** `summarize_open_perimeter_attempt.py` |
| **R-A3** | FIRMS direction overlay one open pack | optional artifact | **P2** | **DONE** `firms_direction_overlay_note.py` |
| **R-B4** | Inventory EO+LWIR pairs (yes/no paths) | 1 p. inventory | **P2** | **DONE** `EO_LWIR_PAIR_INVENTORY.md` |
| **R-OSS1** | Pyronear / FEDS / FlamMap / ELMFIRE short inventory | table in fire_intel | **P2** | **DONE** OSS catalog § R-OSS1 |
| **R-CN1** | Instance FT / attention: **lab-only flag** in plan | written never-promote | hygiene | **DONE** `CN_RESEARCH_LAB_ONLY.md` |
| **R-LIT1** | corpus_v1.json row hygiene if scrape | map update | maintain | LITERATURE_CORPUS |
| **R-C\*** | WFTS/Swin/pretrain | **frozen this month** | P3 | Mega C |

### Track I — Industry calendar

| ID | Task | Done when | P |
|----|------|-----------|---|
| **I1** | OWTRD 2024+2025 notes | `docs/fire_intel/OWTRD_NOTES.md` | **DONE** (skeleton; PDF UNREAD) |
| **I2** | ICFFR abstract draft | 1 p. multi-ancla+ABSTAIN | **DONE** draft |
| **I3** | Red Sky decision | apply/wait/skip + pack ready | **DONE** calendar table |
| **I4** | INTERSCHUTZ flag | visit/skip budget | **DONE** calendar table |
| **I5** | = R-DATA1 OSS catalog | shared | **DONE** |

### Track X — External wait

| ID | Status | Action |
|----|--------|--------|
| O2 national | BLOCKED | wait SHP; CEMS proxy only |
| O5 grade A | OPEN | new data only |
| 3ª ancla | pending_external | formal Vp only |
| CyL/GAL | calendar | silence rules |

### Track K — Kill list (research-reinforced)

| # | Forbidden | Research why |
|---|-----------|--------------|
| K1 | Hellín param spam primary | eng BLOCKED; papers no dan grade A |
| K2 | field_ops ML fusion ON | RGB-TIR ≠ tactical ROS; Orion reject |
| K3 | Invent Vp/ha; SITAC/Δha confirmed | DATA_PROXY_HONESTY |
| K4 | Joint k 7↔50 | Cardil bias / multi-fuel |
| K5 | GO_Q without acta | reunión |
| K6 | IoU catalog as ROS | mega + stack |
| K7 | Sat = ops ROS 5–15 min | layer confusion |
| K8 | Honesty cycles as demo | reunión |
| K9 | Retrain ensemble / WFTS this month as primary | capacity; GO_Q first |
| K10 | RF/ANN ROS promote without copy baseline | Lampman/SOTA_STACK |
| K11 | Rename card to EVACUATE/SAFE CRC marketing | conformal paper ≠ ops ES |
| K12 | CA-CNN CN as field product | chinese_research lab |
| K13 | Generative 3D fire product claim | mega anti |
| K14 | Lampman MAE as Tobarra SLA | domain mismatch grassland |

---

## 4. Semanas (calendario)

### S1 — 2026-08-04 → 08-10 · Pack + research spine

| Focus | IDs | Done if |
|-------|-----|---------|
| Eng | **E3 → E1 → E2 draft** | zip runs; report outline |
| Research in E2 | **R-UQ1, R-STACK-L** | paragraphs drafted |
| Human | **H1 schedule** | date proposed |
| Catalog | **R-DATA1** start | links table begun |
| Kill | no ML retrain | |

### S2 — 2026-08-11 → 08-17 · Human close + report final

| Focus | IDs | Done if |
|-------|-----|---------|
| Human | **H1, H2≥50%, H3, H5** | M3.2 or reschedule |
| Eng | **E2 final, E9, E10** | report merged with research § |
| Graph | status-sync | post-O1 subwindow honest exit |

### S3 — 2026-08-18 → 08-24 · Industrialize + research eng

| Focus | IDs | Done if |
|-------|-----|---------|
| Eng | **E4, E5, E6** | contract + freshness + reasons |
| Research | **R-B1, R-A1** attempt | sector note or export; perimeter attempt |
| Industry | **I1, I5** | OWTRD + OSS catalog |
| Optional | **R-SIM1** start | |

### S4 — 2026-08-25 → 09-04 · GO_Q + stretch research

| Focus | IDs | Done if |
|-------|-----|---------|
| Human | **H2 complete, H4** | M3.4; shadow |
| Stretch | **E7, R-SIM1, R-A3, R-B4, R-OSS1, I2–I4** | notes not claims |
| Graph | GO_Q checklist · STATE exit | Best/Good/Minimum declared |
| Research map | all DONE/DEFER marked | RESEARCH_TO_GRAPH_V6_MAP.md |

---

## 5. Capacity split (v6.1)

| Slice | % | Work |
|-------|---|------|
| Human demo + informe + outreach | **30%** | H* |
| Eng evidence stack E1–E3, E9–E10 | **25%** | pack/report/replay |
| Eng diversify E4–E6 | **12%** | thermal/open/reasons |
| **Research-backed R\*** | **15%** | UQ text, catalog, sector, EFFIS, sim spike |
| Industry calendar I* | **8%** | OWTRD, ferias |
| Hygiene / wait / CI | **10%** | workflows, CyL, O2 |

---

## 6. Definition of Done (eng + research)

### E1 pack

```text
dist/demo_third_party_<date>.zip
  README.md  (cómo validar; qué research no reclamamos)
  fire_decision_card.json/.md
  replay_manifest.json
  run_replay.(ps1|sh)
  sample_data/
  optional: RESEARCH_CITATIONS.md  (3 bullets Lampman/Orion/fuel)
gate: field_ops · replay_ok · no ML-live claim
```

### E2 Reliability Report (research-mandatory sections)

```text
docs/RELIABILITY_GATE_REPORT_THIRD_PARTY.md
  1. Qué medimos (ops TIR multi-pasada) — Lampman method cite
  2. Dónde acierta (Tobarra)
  3. Dónde se abstiene — Orion UQ mapping
  4. Hellín B honest
  5. Fuel/hybrid Med (corpus) — no tactical dispatch
  6. Qué no somos (Technosylva-class sim; IoU≠ROS)
  7. Cómo reejecutar (E3)
```

### R-DATA1 catalog

```text
docs/fire_intel/OSS_DATASETS_CATALOG_2026.md  (or section in OPEN_RESOURCES)
  ELMFIRE | ForeFire | TS-SatFire | BCWildfire | Orion UQ | RoboFireFuseNet
  | WildfireSpreadTS | NDWS (legacy) | EFFIS/CEMS | FIRMS
  columns: url, role in WFD, promote? (never/lab/ops-prior)
```

### R-B1 sector ROS

```text
Either:
  - export head/flank/rear in Tobarra pack scorecard, OR
  - docs note "GAP: sector export deferred; hybrid sectors exist in fuel/"
Never: invent sectors without code path
```

---

## 7. DAG de dependencias (ampliado)

```text
R-UQ1 + R-STACK-L ──┐
E3 replay ──────────┼──► E2 report ──┐
fuel corpus (done) ─┘                │
E9 honesty 1p ───────────────────────┤
                                     ├──► E1 pack (README cites) ──► H3 ──► H1 ──► M3.2
                                     │                                    │
R-DATA1 ──► I5 ──────────────────────┤                                    ├──► H2 informe
I1 OWTRD ────────────────────────────┘                                    │
                                                                          ▼
E4 contract ──┐                                                    GO_Q checklist
E5 freshness ─┼──► E10 portal
E6 reasons ───┘
R-B1 / R-A1 / R-SIM1 ── parallel stretch (no block H1)
R-C* frozen ──────────── no edge into critical path
```

**Critical path:** E3 → E1 → E2(+R-UQ1,R-STACK-L) → H3 → H1 → H2 → GO_Q.  
**Research on critical path:** only citations + UQ mapping (not models).

---

## 8. Workflow registry v6.1

| Workflow | Cadence | Note |
|----------|---------|------|
| `wfd-external-unblock` | 2–3×/week | demo / pack / O2 |
| `wfd-status-sync` | weekly / after H1 H2 E1 E2 | GO_MES true; GO_Q partial |
| `wfd-autonomous-cycle` | weekly | not main |
| `wfd-pilot-regression` | after E1 E3 E4 E6 | |
| `wfd-open-pack-audit` | after E5 R-A1 | freshness + claims |
| `wfd-fire-intel-scrape` | season | no invent Vp |
| `wfd-literature-ingest` | on research | **→ update RESEARCH_TO_GRAPH_V6_MAP.md** |

---

## 9. Métricas de progreso

| Métrica | Start | Target 09-04 |
|---------|-------|--------------|
| GO_MES | true | true hold |
| M3.2 / M3.4 | M3.2 PENDING · M3.4 **ENG_FILLED** | DONE or honest partial |
| demo zip + replay_ok | no | yes |
| Reliability Report + research § | no | ≥3 citations |
| R-DATA1 catalog | partial | yes |
| Thermal contract multi-provider | basic | hardened |
| Open freshness | no | ≥1 pack |
| Sector ROS R-B1 | partial | export or DEFER note |
| ML retrain hours | — | **0** |
| field_ops fusion | OFF | OFF |

---

## 10. Rituales

| When | Action |
|------|--------|
| Lun | ≤3 IDs critical path; 1 research row if needed |
| Mar–Jue | Implement E/R code+docs |
| Vie | `run_plan_cycle --execute-m1` + STATUS json + map checkboxes |
| After literature scrape | 1 row in RESEARCH_TO_GRAPH map |
| After H1 | acta same day; status-sync |
| Never | “paper says retrain → retrain this week” |

---

## 11. Authority chain

```text
anchors JSON → GO_MES_VERDICT → P1_HELLIN_ENG_STATUS (O5)
  → SCORECARD_MES_1
  → PLAN_1_MES_POST_O1_UNLOCK (sub-ventana)
  → **PLAN_1_MES_GRAPH_V6_IMPLEMENT.md** (this)
  → RESEARCH_TO_GRAPH_V6_MAP.md (research backlog)
  → STATE.md v6.1
  → PLAN_1_MES_GRAPH_V6_STATUS.json
  → research sources (SOTA, STACK, INDUSTRY, LIT, CN) as inputs not gates
```

---

## 12. Key paths

| Asset | Path |
|-------|------|
| **This plan** | `docs/PLAN_1_MES_GRAPH_V6_IMPLEMENT.md` |
| Research map | `docs/fire_intel/RESEARCH_TO_GRAPH_V6_MAP.md` |
| Status JSON | `docs/PLAN_1_MES_GRAPH_V6_STATUS.json` |
| STATE | `.grok/graph_engineering/STATE.md` |
| Mega SOTA | `docs/MEGA_RESEARCH_MEJORAS_SOTA_2024_2026.md` |
| SOTA stack | `docs/fire_intel/SOTA_STACK_ADOPTION_2026.md` |
| Industry | `docs/fire_intel/INDUSTRY_RESEARCH_2024_2026_CONGRESOS_FERIAS_OSS.md` |
| Corpus fuel | `docs/fire_intel/LITERATURE_CORPUS_ROS_FUEL.md` |
| Reunión | `docs/REUNION_RESUMEN_Y_ANALISIS_ACCIONES.md` |
| Cycle | `docs/graph_evolution/cycle_c5_graph_v6_implement.md` |

---

## 13. Primeras 72 h

1. **E3** — replay one-command wrapper  
2. **E1** — demo zip scaffold  
3. **E2 + R-UQ1 + R-STACK-L** — report draft with research paragraphs  
4. **R-DATA1** — start OSS catalog table  
5. **H3 / H1** — dry-run + schedule demo  

---

## 14. Research histórico `research/*` — política

| File | Policy v6.1 |
|------|-------------|
| `implementation_roadmap.md` (U-Net+ConvLSTM historical) | **Archive doctrine** — superseded by dual-product; do not re-primary |
| `models.md` / `training_strategy.md` / `pretrained_models.md` | Lab reference only |
| `datasets.md` | Merge useful links into R-DATA1 |
| `expert_consensus.md` | Cite if aligns with SOTA_STACK; no new primary |
| `chinese_research.md` | Metadata + lab ideas; R-CN1 never-promote |
| `cloud_training_setup.md` | Only if future lab GPU cycle post-GO_Q |

---

*Graph Engineering v6.1 — plans + full research corpus fused. Update checkboxes on ID close.*
