# Research → Graph v6 map (corpus completo → IDs implementables)

> **As of:** 2026-08-04  
> **Authority:** alimenta `docs/PLAN_1_MES_GRAPH_V6_IMPLEMENT.md` y `.grok/graph_engineering/STATE.md` **v6.1**  
> **Regla:** research no es gate de GO_Q; **sí** es backlog priorizado y anti-hype.

---

## 0. Inventario de research (repo)

| ID | Documento | Tipo | n / foco | Estado de adopción en código |
|----|-----------|------|----------|------------------------------|
| **R-SOTA** | `docs/MEGA_RESEARCH_MEJORAS_SOTA_2024_2026.md` | SOTA papers → mejoras A–E | NDWS, WFTS, PINN, UAV, DT, EFFIS | Parcial (fuel, ensemble, envelope) |
| **R-STACK** | `docs/fire_intel/SOTA_STACK_ADOPTION_2026.md` | Adopción 2025–26 | Lampman TIR-ROS, RGB-TIR, Orion UQ, OSS | **Doctrina lista**; código parcial |
| **R-DEEP-202608** | `docs/fire_intel/DEEP_RESEARCH_STRATEGIES_2024_2026.md` | Expanded 2024–26 strategies post Tobarra KILL | SDC/CP reject, LOFO dual, arrival-time ROS, EFFIS/MedEU, GFM LoRA | **Shortlist S1–S4**; 75 claims verified |
| **R-IND** | `docs/fire_intel/INDUSTRY_RESEARCH_2024_2026_CONGRESOS_FERIAS_OSS.md` | Ferias CA/CN + startups + OSS | Red Sky, INTERSCHUTZ, ELMFIRE… | Calendario + mapa capas |
| **R-LIT** | `docs/fire_intel/LITERATURE_CORPUS_ROS_FUEL.md` + `data/fire_intel/literature/corpus_v1.json` | Corpus ~93 estudios Med/ES/hybrid | Fuel MED, hybrid α, ABSTAIN wind | **En código** fuel/rothermel/hybrid |
| **R-FI** | `docs/fire_intel/MEGA_FIRES_2026_ES_FR.md` + COMPLETION_MATRIX | Intel mega-IF open | CEMS packs, press ha | Open packs GO_PROXY |
| **R-CN** | `research/chinese_research.md` | CN ML/CA/UAV | FY-4A, attention, instance calib | Ideas lab only |
| **R-RD** | `research/implementation_roadmap.md` · models · datasets · expert_consensus | Roadmap histórico ML | U-Net/ConvLSTM | **Superseded** por dual-product honesty; no reabrir como primary |
| **R-REU** | `docs/REUNION_RESUMEN_Y_ANALISIS_ACCIONES.md` | Decisión senior | Evidence + terceros | Primary product v6 |
| **R-DSG** | `docs/design/PR_PLAN_FUEL_AEMET_ENVELOPE.md` etc. | Design shipped/partial | Fuel+AEMET | PR-α/β DONE |

**Mensaje unificado de todos los researchs:**

```text
Ops TIR medido (Lampman-class)  +  open perimeter (CEMS/EFFIS)
  +  fuel/hybrid Med (corpus)  +  Decision Card UQ (Orion-class rails)
  +  ABSTAIN / no ML-live field
  ≠  otra U-Net NDWS / CA-CNN CN como producto de sala
```

---

## 1. Mega-research A–E → IDs graph v6

### A — Validación y datos (SOTA + industria)

| Mega ID | Research source | Graph ID | Priority mes | Status |
|---------|-----------------|----------|--------------|--------|
| A1 EFFIS/CEMS perimeter fetch | R-SOTA, R-FI, R-IND | **R-A1** / open E5 | P1 | **DONE eng** summary+Hausdorff-lite on existing pack (`summarize_open_perimeter_attempt.py`); O2 national still BLOCKED |
| A2 multi-IF Vp anchors | R-SOTA, R-REU | **X-anchor** | external | 2 confirmed; 3ª wait |
| A3 FIRMS direction overlay | R-SOTA | **R-A3** | P2 | **DONE** `firms_direction_overlay_note.py` + overlay path doc |
| A4 AEMET/ERA5 in-scene | R-SOTA, R-DSG | **fuel done** | maintain | Tobarra AEMET live |
| A5 LFMC product | R-SOTA, R-LIT | **R-A5** | P2 | catalog/hybrid only |
| A6 Cardoso multi-day | R-SOTA, R-FI | **R-A6** | P2 proxy | timeline ha only |

### B — Ops ROS / frente (diferencial + Lampman)

| Mega ID | Research source | Graph ID | Priority | Status |
|---------|-----------------|----------|----------|--------|
| B1 ROS sector head/flank/rear | R-SOTA, R-STACK Lampman | **R-B1** | **P1 eng** | **DONE** export Tobarra + note `SECTOR_ROS_TOBARRA_NOTE.md` |
| B2 uncertainty band brief | R-SOTA, R-STACK Orion | **R-B2** / E6 | **P0–P1** | Partial P25–P75 |
| B3 optical flow LWIR | R-SOTA | **R-B3** | P2 | not primary |
| B4 RGB+LWIR | R-STACK Fire-YOLO / RoboFire | **R-B4** | P2 lab | **DONE inventory** 0 co-located pairs (`EO_LWIR_PAIR_INVENTORY.md`) |
| B5 soft physics cal (Rothermel) | R-LIT, PiNN | fuel hybrid | maintain | hybrid α DONE weight 0 tactical |
| B6 FOV adaptive seg | R-SOTA | maintain | — | shipped rails |
| B7 DT-light envelope 15–60 | R-SOTA NASA DT | envelope v3 | maintain | shipped; card weight 0 |
| B+ FI/FRP from TIR | R-STACK Lampman | **R-B8** | P2 | gap ops |
| B+ copy baseline before RF-ROS | R-STACK | kill list | — | doctrine |

### C — ML NDWS / G1

| Mega ID | Graph | Priority | Status |
|---------|-------|----------|--------|
| C1 WFTS multi-day | **R-C1** | P3 lab | not mes primary |
| C2 ImageNet pretrain | **R-C2** | P3 | — |
| C4 AP/growth IoU metrics | **R-C4** | P2 lab | optional |
| C7 G1 KILL | **done** | — | ndws_v21 G1 KILL |

### D — ML CLM transfer

| Mega ID | Graph | Priority | Status |
|---------|-------|----------|--------|
| D2 ensemble LOFO | **done** v34 | maintain | clm_ensemble_v34 |
| D5 growth mask | **R-D5** | P3 | lab only |
| — no promote without rails | kill | — | ml_product_go false |

### E — Producto industrial (NASA DT light + reunión)

| Mega ID | Graph | Priority | Status |
|---------|-------|----------|--------|
| E1 API tablet-like | serve-decide | maintain | exists |
| E2 QGIS/timeline brief | packs | maintain | partial |
| E3 uncertainty HTML | **R-B2** | P1 | — |
| E4 public CLM aerial bench | **R-E4** | P3 | privacy |
| Orion UQ → card rails | **R-UQ1** | **P0 copy + P1 fields** | doctrine in SOTA_STACK |
| CRC three-way SAFE/MONITOR/EVAC | **R-UQ2** | P2 map to GO/HOLD/ABSTAIN only — **never rename to EVAC** | |

### Industria / OSS

| Item | Graph ID | Priority |
|------|----------|----------|
| ELMFIRE / ForeFire spike vs Tobarra | **E8** / **R-SIM1** | **DONE** spike note |
| TS-SatFire / BCWildfire catalog | **I5** / **R-DATA1** | **DONE** |
| Technosylva/CAL FIRE language study | **I1** OWTRD | **DONE** notes skeleton |
| Red Sky / INTERSCHUTZ / ICFFR | **I2–I4** | **DONE** draft + decision table |
| CN vendor thermal contract | **E4** | **DONE** |
| Pyronear / FEDS / FlamMap inventory | **R-OSS1** | **DONE** catalog § |

### China research (ideas, not product)

| Idea CN | Graph | Rule |
|---------|-------|------|
| Multimodal fuel+DEM as channels | already fuel stack | maintain |
| Attention / Swin | **R-C3** lab | not field |
| Instance-level fine-tune first 3 obs | **R-CN1** | **DONE flag** `CN_RESEARCH_LAB_ONLY.md` — never field_ops |
| FY-4A 15 min thermal fronts | open/sat layer | not ops LWIR ROS |

---

## 2. Priorización research para **este mes** (v6.1)

### Debe entrar en entregables del mes (research-backed)

| Graph ID | Entregable | Research ancla | Owner | Status (2026-08-04 eng) |
|----------|------------|----------------|-------|-------------------------|
| **E1–E3** | demo pack + report + replay | R-REU, R-IND, NASA DT light | Eng | **DONE** scripts + `outputs/demo_third_party/` |
| **R-UQ1** | § Reliability Report: aleatoria/epistémica + ABSTAIN map (Orion copy-paste) | R-STACK §3 | Eng | **DONE** in E2 + card MD UQ band |
| **R-STACK-L** | § Reliability Report: Lampman metodológico (no SLA) | R-STACK §1 | Eng | **DONE** in E2 §1 |
| **E4** | thermal contract multi-provider (+ CN UAV metadata) | R-IND, R-CN, R-STACK | Eng | **DONE** contract + validate helper |
| **E5 / R-A1** | open freshness + CEMS/EFFIS hygiene | R-SOTA A1, R-FI | Eng | **E5 DONE**; **R-A1 DONE** perimeter summary + Hausdorff-lite (no O2 unlock) |
| **E6 / R-B2** | card reasons + uncertainty band visible | R-SOTA B2, Orion | Eng | **DONE** `render_decision_card_md` |
| **E7** | Hub abstention slice | Orion reject | Eng | **DONE** `hub.abstention` |
| **E9** | IoU≠ROS one-pager | R-REU, R-STACK kill | Eng | **DONE** `docs/METRICS_HONESTY_IOU_NE_ROS.md` |
| **I5 / R-DATA1** | catalog TS-SatFire, ELMFIRE, ForeFire, Orion UQ repo | R-IND, R-STACK | Eng | **DONE** `docs/fire_intel/OSS_DATASETS_CATALOG_2026.md` |
| **I1** | OWTRD notes 1 p. | R-IND | Eng+Human | **DONE** skeleton; PDF UNREAD human |
| **H1–H2** | demo + informe citando research (Lampman + Orion rails) | all | Human | TODO |
| **H3** | dry-run pack | — | Eng+Human | **ENG READY** (`dry_run_demo_third_party.py`); human operator TODO |

### Stretch S3–S4 (closed eng this run)

| Graph ID | Entregable | Research | Status |
|----------|------------|----------|--------|
| **R-B1** | ROS sector head/flank/rear export in gold pack | Mega B1, Lampman | **DONE** prior |
| **R-SIM1** | ELMFIRE or ForeFire vs Tobarra note | R-IND | **DONE** |
| **R-A3** | FIRMS direction on one open pack | Mega A3 | **DONE** |
| **R-OSS1** | short OSS inventory Pyronear/FEDS/FlamMap | R-STACK | **DONE** |
| **R-B4** | note: EO/LWIR pairs available? (no implement net) | FireCast / RoboFire | **DONE** (0 pairs) |
| **R-CN1** | lab-only flag CA-CNN / instance FT | R-CN | **DONE** |
| **I2–I4** | ICFFR draft + Red Sky / INTERSCHUTZ flags | R-IND | **DONE** |

### Explicitamente **fuera** del mes (research dice “después / never product”)

| Item | Why killed as primary |
|------|------------------------|
| WFTS SwinUnet retrain | C1/C2 trimestre; no GO_Q |
| CA-CNN China production | R-CN lab only |
| RF/ANN ROS model promote | R-STACK: copy baseline first; N small |
| Conformal EVACUATE labels | never rename Decision Card to evacuation |
| Generative 3D fire | Mega anti-rec |
| Hellín grade A param spam | P1 eng blocked; research no lo desbloquea |
| G1 NDWS revive | C7 KILL |

---

## 3. Texto research obligatorio en Reliability Report (E2)

El report E2 **debe** incluir (cortos, citados):

1. **Lampman 2026** — repeat-pass TIR→ROS es método SOTA; cifras MAE **no** son SLA WFD Med.  
2. **Orion UQ** — epistémica + aleatoria → GO/HOLD/ABSTAIN; fusión ML field OFF.  
3. **Corpus fuel Med** — hybrid α / MED fuels / no tactical dispatch.  
4. **Technosylva-class** — ellos simulan spread statewide; nosotros medimos frente cuando hay LWIR.  
5. **Hellín B honest** — no esconder grade/ratio.

---

## 4. Workflow research (graph)

| Workflow | Research role v6.1 |
|----------|-------------------|
| `wfd-literature-ingest` | Maintain corpus; tag new → RESEARCH_TO_GRAPH map |
| `wfd-fire-intel-scrape` | Mega-IF; never Vp invent |
| `wfd-open-pack-audit` | After R-A1/E5 |
| `wfd-autonomous-cycle` | Honesty; not research substitute |

**New ritual:** after any literature scrape, update **one row** in this map if actionable; do not spawn new primary tracks without STATE edit.

---

## 5. Score research coverage (mes)

| Axis | Start | Target 2026-09-04 |
|------|-------|-------------------|
| Research cited in third-party report | 0 | ≥3 (Lampman, Orion, fuel corpus) |
| Open OSS catalog updated | partial | ELMFIRE+ForeFire+TS-SatFire+Orion UQ |
| Sector ROS export | partial | documented in pack or deferred note |
| ML retrain from research | 0 hours | **0 hours** (success = restraint) |
| Industry calendar decisions | 0 | OWTRD notes + Red Sky flag |

---

*Mapa vivo: al cerrar un ID, marcar Status=DONE aquí y en PLAN_1_MES_GRAPH_V6_STATUS.json.*
