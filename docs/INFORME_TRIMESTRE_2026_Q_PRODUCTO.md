# WildfireFrontDynamics — Informe de trimestre (producto)

| Campo | Valor |
|-------|--------|
| **Título** | WildfireFrontDynamics — informe de trimestre (producto) |
| **Ventana** | Plan 3M: 2026-07-17 → 2026-10-17 · foco mes 1 overlay post-O1 · Graph v6.1 (2026-08-04 → 2026-09-04) |
| **Fecha de corte** | 2026-08-04 |
| **Autor** | WildfireFrontDynamics project (relleno de ingeniería / memoria producto; sin firma formal de autor humano) |
| **Versión doc** | 1.0 ENG_FILLED (M3.4 eng support) |
| **Esqueleto origen** | `docs/INFORME_TRIMESTRE_ESQUELETO.md` |
| **Clasificación** | Memoria técnica / capítulo producto (TFG / GO_Q) |
| **Estado M3.4** | **ENG_FILLED** — relleno con evidencia de repo; pendiente sello/firma humana si se usa como acta formal |

**Una frase de producto:** apoyo a la decisión en incendios con Decision Card (GO / HOLD / **ABSTAIN**), audit trail y abstención honesta — no es orden táctica de despacho.

**Disclaimer:** este documento no autoriza despacho, evacuación ni asignación de medios. Las cifras citadas salen de paths de repo; no se inventan ROS, Vp ni ha.

---

## Portada — producto en una mirada

| Capa | Qué entrega | Rails |
|------|-------------|-------|
| **Ops térmico** | ROS multi-estimador, grade, ratio vs ancla INFOCAM | `front_dynamics_v1` / `incident_runtime_v1` |
| **Open multi-CCAA** | Perímetros / ha públicos (CEMS, REDIAM, RAI) | research_open; FIRMS hull ≠ quemado oficial |
| **Decision Card** | GO / HOLD / ABSTAIN + motivos + UQ band | `field_ops` fusión ML live **OFF** |
| **ML lab** | Máscaras next-day, IoU / ECE | `ml_product_go` **false**; IoU **≠** ROS |

**Evidencia one-liner:** `docs/ONEPAGER_COMERCIAL_ES.md` · `docs/PRODUCTO_DUAL.md` · `docs/START_HERE.md`

---

## 1. Resumen ejecutivo

### Qué se entrega (demostrable en repo)

1. **Decision Card** con políticas `field_ops` y `research_open`, motivos y banda de incertidumbre (Orion-style mapping, no labels EVACUATE).  
2. **Stack de evidencia para terceros:** pack offline + Reliability Report + replay de un comando (`outputs/demo_third_party/`, `docs/RELIABILITY_GATE_REPORT_THIRD_PARTY.md`, `scripts/run_third_party_replay.py`).  
3. **Producto dual documentado:** ops LWIR multi-pasada vs ML de máscaras lab (`docs/PRODUCTO_DUAL.md`, `docs/METRICS_HONESTY_IOU_NE_ROS.md`).  
4. **Dos anclas confirmed** con ratio ROS/Vp en banda [0.5, 2]: Tobarra grade **A**, Hellín grade **B** honesto.  
5. **Piloto multi-CCAA** Tobarra · Níjar · Caminomorisco con la misma card y honestidad de fuentes (`docs/PILOT_HONESTY_CARD.md`).

### Estado de gates (corte 2026-08-04)

| Gate | Veredicto | Nota honesta |
|------|-----------|--------------|
| **GO_ENG** | **true** | Ingeniería y smokes cerrados en el mínimo de plan |
| **GO_MES** | **true** | Fórmula mínima plan 1 mes: O1 ∧ O4 ∧ P1 ∧ M2 ∧ E1 — ver `docs/GO_MES_VERDICT.md` |
| **GO_MES+** | **false** | O2 nacional, O5 2º grade A, M5, D1 no cerrados como stretch |
| **GO_Q** | **partial** | Falta **M3.2** (demo tercero + acta firmada); M3.4 este informe = eng filled, no sello formal |
| **ml_product_go** | **false** | Lab only |
| **field_ops · ML live fusion** | **OFF** | Policy freeze |

> **Corrección al esqueleto:** el esqueleto (`docs/INFORME_TRIMESTRE_ESQUELETO.md`) mencionaba **NO_GO_MES** por una lectura antigua que equacionaba P1 con “2× grade A”. El plan mínimo y el veredicto canónico declaran **GO_MES = true** (`docs/GO_MES_VERDICT.md`, `docs/GO_MES_VERDICT.json`, `docs/SCORECARD_MES_1.md` §GO_MES actualizado, `docs/O1_GOMES_RECOMPUTE_20260803.json`). P1 = smoke de `incident_runtime` en **2 IF reales sin crash**, no grade A del segundo IF (eso es **O5 / GO_MES+**).

### Hallazgos clave

- **Humano pendiente (bloquea GO_Q completo):** 1 demo con tercero + acta firmada (M3.2) usando `docs/GUION_DEMO_30MIN_POST_O1.md` y `docs/ACTA_DEMO_TERCERO_TEMPLATE.md`.  
- **Técnico:** 2 anclas confirmed (Tobarra, Hellín). Hellín best-of-run grade **B**, ratio ~0.56 in-band; grade A eng-blocked opcional (`docs/P1_HELLIN_ENG_STATUS.md`).  
- **No-claims (una línea):** fusión field_ops OFF; sin ROS inventado; sin k conjunto Tobarra↔Hellín; IoU ≠ ROS; sin `ml_product_go`; sin reclamar GO_Q sin acta.

**Evidencia:** `docs/SCORECARD_MES_1.md` · `docs/O1_GOMES_RECOMPUTE_20260803.json` · `docs/GO_MES_VERDICT.md` · `docs/PLAN_1_MES_GRAPH_V6_STATUS.json` · `docs/PLAN_3_MESES_STATUS.json`

---

## 2. Problema y propuesta de valor

### Gap

Los mapas open (CEMS, portales CCAA, FIRMS) son **gratis** y útiles para monitorización de ha/perímetros. Lo que no resuelven de forma auditada es:

- **cuándo confiar** en una estimación de frente (ROS) frente a un boletín Vp;  
- **cuándo callarse** (ABSTAIN) si faltan fuentes, el grade es débil o solo hay ML de máscaras;  
- un **trail** reproducible (inputs, política, versión, UTC) para sala / CMA / investigación.

### Usuario y políticas

| Usuario | Política típica | Comportamiento |
|---------|-----------------|----------------|
| Sala / ops de campo | `field_ops` | Exige ops multi-frame creíble; ML live fusion **OFF**; fail-closed a ABSTAIN |
| Research / demo open | `research_open` | Más permisiva con open + ML experimental; no es despacho |
| CMA / partner datos | entrega Tobarra + field kit | Brief ≤5 min; no inventar anclas |

### Qué se vende vs qué no

**Sí:** Decision Card, audit trail, Metrics Hub, reliability gate (no silent GO bajo suite), dual field (LWIR + open), honesty cards multi-sitio.

**No:** “otro mapa Copernicus”, IoU como si fuera extinción, ROS inventado con Δt falso, 99.9999% de acierto del fuego (confusión con residual silent-GO contractual).

**Evidencia:** `docs/ONEPAGER_COMERCIAL_ES.md` · `docs/PRODUCT_REDESIGN_PAID_VALUE.md` · `docs/design/DECISION_POLICY.md` · `docs/funding/02_ONEPAGER_EU_EN.md`

---

## 3. Arquitectura de producto dual

### 3.1 Ops (frente térmico)

- **IDs:** `front_dynamics_v1` (estimación ROS multi-estimador sobre secuencias LWIR) y `incident_runtime_v1` (inbox → outbox, brief, card).  
- **Salidas:** ROS primaria, grades estructurales, ratio vs ancla Vp, sector ROS cuando existe export.  
- **Field kit / O4:** `docs/FIELD_KIT_INCIDENT.md`, `docs/INCIDENT_RUNTIME_V1.md`, smokes en 2 IF reales.  
- **Método (cita, no SLA):** alineado con medición geométrica multi-pasada TIR/UAS (Lampman et al. 2026) — ver §9 y Reliability Report; **no** se importa el MAE del pastizal prescrito como SLA de Tobarra/Hellín.

### 3.2 ML lab

| Producto | Rol | Métrica (repo) | Claim de campo |
|----------|-----|----------------|----------------|
| `clm_ensemble_v34` | Champion lab | U1 TEST honest IoU ~0.86 · ECE ~0.15; catalog holdout **0.8963** provenance | **No** `ml_product_go` |
| `clm_v28` | Fallback specialist | IoU 0.838 | Lab / research |
| `ndws_v21` | Global next-day | IoU 0.226; G1 **KILL** features | Research only |

**Regla:** ROS de dron ≠ predicción de máscara NDWS/CLM. Catalog IoU es **proveniencia de protocolo limpio**, no certeza live del incendio de hoy (`docs/METRICS_HONESTY_IOU_NE_ROS.md`).

### 3.3 Decision Card y políticas

- Decisiones: **GO** | **HOLD** | **ABSTAIN** con `reasons` y banda UQ en markdown de card (E6).  
- `field_ops.allow_ml_live_in_fusion` = **false** (congelado).  
- API mínima / replay / acta forense de decisión (eng) ≠ acta de **demo tercero** (humano M3.2).  
- Commander HUD: `docs/commander/index.html`.  
- Latencias: `docs/DECIDE_API_LATENCY.json` · `docs/INCIDENT_SLA_LATENCY.json`.

**Evidencia:** `docs/PRODUCTO_DUAL.md` · `docs/PILOT_HONESTY_CARD.md` · `docs/FIRE_DECISION_CARD.json` · `docs/ML_PRODUCT_SCORECARD.json` · `docs/ML_LOOP_RAILS.md` · `docs/design/MINIMAL_DECIDE_API.md` · `config/decision_policies.json` (si se inspecciona en código)

---

## 4. Datos e ingesta

### Inventario y protocolos

- Protocolo real-IF: `docs/REAL_IF_INTAKE_PROTOCOL.md`.  
- Estado de ingesta y outreach: `docs/DATA_INTAKE_STATUS.md`.  
- Honestidad confirmed vs proxy: `docs/DATA_PROXY_HONESTY.md` — **Estrella / Cardoso no son anclas GO** hasta Vp formal.  
- Anclas machine: `data/infocam_anchors.json` · scorecard `outputs/observatorio/anchor_scorecard.json`.  
- Auditoría Tobarra partner: `docs/REAL_IF_AUDIT_TOBARRA_20240802.md`.  
- Entrega CMA Tobarra (figs + informe técnico v1.0): `docs/entrega_cma/`.

### Anclas confirmed (O1)

| IF | Vp (m/min) | ha | Fuente |
|----|-----------:|---:|--------|
| Tobarra 2024-08-02 | 7 | 39 | INFOCAM parte |
| Hellín 2024-07-19 | 50 | 100* | Boletín UNAP 20/07/2024 (*estimada no oficial) |

### Open multi-CCAA (sin inventar perímetros)

- REDIAM Andalucía, RAI Extremadura, CEMS EMSR, packs open — ver `docs/open_if_intake/`, `docs/OPEN_RESOURCES_CATALOG.md`, `docs/AND_INDUSTRIAL_E2E_VERIFICATION.md`, `docs/EXT_INDUSTRIAL_E2E_VERIFICATION.md`.  
- n_open_packs reportado en hub/status ≈ 11 (`docs/PLAN_3_MESES_STATUS.json` live).  
- **CyL:** trámite transparencia / silencio documentado (D1) — `docs/SOLICITUD_TRANSPARENCIA_CYL.md`, `docs/fire_intel/CYL_SILENCE_RULE_NOTE.md`; **no** hay perímetro fino CyL inventado en este informe.  
- Contactos: `docs/CONTACTOS_EMERGENCIAS_DATOS.md` · `docs/CONTACTOS_OUTREACH.csv`.

---

## 5. Resultados operativos multi-ancla

### 5.1 Tobarra (grade A)

| Campo | Valor | Path |
|-------|-------|------|
| Ancla Vp / ha | 7 m/min · 39 ha | `data/infocam_anchors.json` |
| ROS primaria (pack) | ~**5.71** m/min | `outputs/observatorio/tobarra_20240802/` · `docs/GO_MES_VERDICT.json` |
| Ratio ROS/Vp | ~**0.82** ∈ [0.5, 2] | grade estructural **A** |
| Sector ROS (orientativo) | head ~5.99 · flank ~5.71 · rear ~2.78 | `docs/fire_intel/SECTOR_ROS_TOBARRA_NOTE.md` |
| Limitaciones | FOV / partner / no despacho táctico | Reliability Report §2 |

Entrega partner / figs: `docs/entrega_cma/`.

### 5.2 Hellín (2ª ancla, grade B honest)

| Campo | Valor | Path |
|-------|-------|------|
| Ancla Vp / ha | 50 m/min · 100* ha | Boletín UNAP |
| ROS best-of-run | **27.934** m/min | `docs/HELLIN_TRACK_A_SCORECARD.md` |
| Ratio | **0.559** in-band | yes |
| Grade estructural | **B** | Grade A eligible: **NO** |
| O5 / GO_MES+ | OPEN / false | no param-chase primary |

**Por qué no grade A:** eligibility exige structural A **y** ratio en banda; best keep es B + 0.56. No se reescala ROS a Vp en silencio. **No** k conjunto Tobarra(7)↔Hellín(50). Área de máscara en pack (~44 ha max en series) vs boletín 100 ha* sugiere FOV incompleto (`docs/HELLIN_TRACK_A_SCORECARD.md` honesty).

> Nota: `docs/HELLIN_TRACK_A_SCORECARD.md` aún etiqueta localmente `GO_MES | NO_GO_MES` en su tabla de result (visión “grade A path”). El **veredicto de plan mínimo** es canónico en `docs/GO_MES_VERDICT.md` (**GO_MES = true**). Este informe sigue el veredicto canónico y deja Hellín como **B** honesto para O5.

### 5.3 O1 y GO_MES (mínimo plan)

```
GO_MES = O1 ∧ O4 ∧ P1 ∧ M2 ∧ E1
```

| Componente | Met? | Evidencia |
|------------|------|-----------|
| **O1** multi-ancla | **sí** | ≥2 confirmed + ratios in-band Tobarra 0.82 + Hellín 0.56 |
| **O4** brief ≤5 min | **sí** | Field kit + incident briefing |
| **P1** 2 IF reales | **sí** | `smoke_incident_runtime.py --p1-two-real --skip-synthetic` → Tobarra+Hellín `updated` |
| **M2** v34 | **sí** | catalog holdout IoU ≥ 0.890 (~0.8963 provenance) |
| **E1** CI/smokes | **sí** | pytest + smokes |

**Veredicto (2026-08-04): GO_MES = true** · **GO_ENG = true** · **GO_MES+ = false**.

**Evidencia:** `docs/GO_MES_VERDICT.md` · `docs/GO_MES_VERDICT.json` · `docs/O1_GOMES_RECOMPUTE_20260803.json` · `docs/SCORECARD_MES_1.md` · `docs/P1_HELLIN_ENG_STATUS.md` · `docs/O2_HAUSDORFF_BLOCKED.md` · `docs/O3_TEMPORAL_WINDOWS_SNAPSHOT.json`

---

## 6. Open multi-CCAA y piloto de honestidad

### Mismos rails, tres pistas

| Sitio | Pista | Cifra clave (piloto) | field_ops (piloto) |
|-------|-------|----------------------|--------------------|
| Tobarra | OPS | ROS ~6.75 m/min (snapshot piloto; pack O1 usa ~5.71) | ABSTAIN (fail-closed sin inventar R1–R4 en piloto) |
| Níjar | OPEN_AND | ha REDIAM ~2169 | HOLD |
| Caminomorisco | OPEN_EXT | ha RAI ~2679 | HOLD |

Fuente tabla: `docs/PILOT_HONESTY_CARD.md` (generado research_open vs field_ops). Demo vendible: `outputs/demo_multi_ccaa/` · diseño `docs/design/DEMO_MULTI_CCAA_TOBARRA_NIJAR_CAMINOMORISCO.md` · handoff `docs/design/DEMO_FRONT_SALES_HANDOFF.md`.

### Industrial E2E

- Andalucía: `docs/AND_INDUSTRIAL_E2E_VERIFICATION.md` (+ JSON).  
- Extremadura: `docs/EXT_INDUSTRIAL_E2E_VERIFICATION.md` (+ JSON).  
- Gold IF: `docs/GOLD_IF_E2E_VERIFICATION.md`.  
- Compare CLM vs open: `docs/COMPARE_CLM_VS_OPEN.md` · scorecard JSON.

**No-claim:** multi-CCAA demostrable en tres sitios **no** significa “funciona en toda España”. FIRMS hull ≠ área quemada oficial.

---

## 7. ML laboratorio

### Champion y rails

- Promote record / scorecard: `docs/ML_U1_PROMOTE_RECORD.json` · `docs/ML_PRODUCT_SCORECARD.json` · `docs/ML_BASELINE_METRICS.json`.  
- Gates G0/G1/G2/G2e: ver `docs/PRODUCTO_DUAL.md` (G1 KILL en features/temporal NDWS; G2e ensemble GO lab).  
- No leakage Cardoso en claim de promote: `docs/ML_LOOP_RAILS.md` · `docs/ML_TRANSFER_PROTOCOL.md`.  
- Abstención / ECE live demo note: `docs/ML_LIVE_ABSTAIN_ECE_NOTE.md`.  
- Hub: `docs/METRICS_HUB.md` · `docs/METRICS_HUB.json` (slice abstention E7).  
- Manifests: `models/clm_ensemble/manifest.json` · `models/catalog.json`.

### Qué **no** se afirma en campo

- IoU holdout **no** es ROS táctico ni perímetro O2.  
- `ml_product_go` permanece **false**.  
- Fusión ML live en `field_ops` permanece **OFF**.  
- CN / WFTS / Swin retrain **no** son primary del mes (R-CN1 lab-only, R-C frozen).

---

## 8. Fuel, meteorología y envelope

- Plan PR fuel/AEMET/envelope: `docs/design/PR_PLAN_FUEL_AEMET_ENVELOPE.md`.  
- Diseño envelope v3 hybrid: `docs/DESIGN_ENVELOPE_V3_HYBRID.md`.  
- Scorecard mes: fila Fuel/AEMET **PASS** eng en `docs/SCORECARD_MES_1.md` (pipeline Tobarra).  
- **Política:** envelope / hybrid α / Rothermel-lite = **priors de escenario**, **peso 0** en fusión field_ops de la Decision Card (`docs/RELIABILITY_GATE_REPORT_THIRD_PARTY.md` §5).  
- Corpus fuel Med: `docs/fire_intel/LITERATURE_CORPUS_ROS_FUEL.md` (~93 estudios citados en report).  
- **No claim táctico:** sin viento medido o sin ops TIR no se vende prior de fuel como ROS de frente validado.

---

## 9. Ingeniería, fiabilidad y reproducibilidad

### CI, smokes, industrial

- Gates: `docs/INDUSTRIAL_PRODUCTION_GATES.md` · `docs/INDUSTRIAL_READINESS_STATUS.json` · `docs/PRODUCCION_INDUSTRIAL_ESTADO.md`.  
- Ops/ML smoke snapshot: `docs/OPS_ML_SMOKE_SNAPSHOT.json`.  
- Loop eng: `docs/LOOP_ENGINEERING_PLAN.md`.  
- Graph cycles: `docs/graph_evolution/` · estado vivo `.grok/graph_engineering/STATE.md`.

### Reliability para terceros (E2) + research cites

Documento canónico: **`docs/RELIABILITY_GATE_REPORT_THIRD_PARTY.md`**.

1. **R-STACK-L (Lampman):** método multi-pasada TIR → ROS; cita IJWF WF25133; **no** MAE del paper como SLA mediterráneo.  
2. **R-UQ1 (Orion):** incertidumbre epistémica/aleatoria → GO/HOLD/ABSTAIN rails; **nunca** renombrar a EVACUATE/SAFE de producto.  
3. Tobarra acierto / Hellín abstención de grade A / no-claims table (§6 del report).  
4. Suite machine: `docs/RELIABILITY_GATE_REPORT.json` (suite-only; no field unlock).

### Stack demo terceros (E1 + E3)

| Asset | Path |
|-------|------|
| Pack folder | `outputs/demo_third_party/` |
| Zip | `dist/demo_third_party_YYYYMMDD.zip` |
| Builder | `scripts/build_demo_third_party_pack.py` |
| Replay one-cmd | `scripts/run_third_party_replay.py` (exit 0 ⇔ `replay_ok`) |
| Entry point | `docs/START_HERE.md` § pack demo terceros |
| IoU ≠ ROS | `docs/METRICS_HONESTY_IOU_NE_ROS.md` |
| Thermal contract | `docs/GEOTIFF_INPUT_CONTRACT.md` |
| Open freshness | `scripts/audit_open_pack_freshness.py` |

### Research map (anexo conceptual)

Bridge research → IDs Graph v6.1: `docs/fire_intel/RESEARCH_TO_GRAPH_V6_MAP.md`.  
SOTA stack / industry / OSS: `docs/fire_intel/SOTA_STACK_ADOPTION_2026.md`, `docs/fire_intel/OSS_DATASETS_CATALOG_2026.md`, `docs/MEGA_RESEARCH_MEJORAS_SOTA_2024_2026.md`.

---

## 10. Demo con tercero y validación humana (M3.2)

| Elemento | Estado | Path |
|----------|--------|------|
| Guion 30 min | **Listo eng** (no ejecutado/firmado aquí) | `docs/GUION_DEMO_30MIN_POST_O1.md` |
| Variante 10 min | Listo | `docs/funding/04_GUION_DEMO_10MIN.md` |
| Plantilla acta | Listo | `docs/ACTA_DEMO_TERCERO_TEMPLATE.md` |
| Acta firmada | **PENDING** | `docs/actas/…` (aún no) |
| Dry-run pack (H3) | ENG_READY_HUMAN_TODO | `scripts/dry_run_demo_third_party.py` / `make dry-run-demo-third-party` |
| Pack + replay | **DONE eng** | ver §9 |

**Estado M3.2:** PENDING (humano).  
**Estado GO_Q:** **partial** — no se reclama completo sin acta firmada + (idealmente) sello formal de este informe.

---

## 11. Estado de gates y veredictos

| Gate / fórmula | Criterio (resumen) | Estado | Path evidencia |
|----------------|--------------------|--------|----------------|
| O1 multi-ancla | ≥2 confirmed + ratio banda | **PASS** | `docs/O1_GOMES_RECOMPUTE_20260803.json` |
| O4 brief | field kit ≤5 min | **PASS** | `docs/FIELD_KIT_INCIDENT.md` |
| P1 2 IF | smoke 2 IF reales sin crash | **PASS** | `docs/GO_MES_VERDICT.json` · smoke script |
| M2 v34 | IoU catalog ≥ 0.890 | **PASS** | manifest · `docs/SCORECARD_MES_1.md` |
| E1 CI | smokes/tests | **PASS** | industrial gates |
| **GO_MES** | O1∧O4∧P1∧M2∧E1 | **true** | `docs/GO_MES_VERDICT.md` |
| O2 Hausdorff | perímetro oficial nacional | **BLOCKED** | `docs/O2_HAUSDORFF_BLOCKED.md` |
| O2 open proxy | CEMS/REDIAM/RAI | **GO_PROXY** | open packs / industrial E2E |
| O5 2º grade A | 2º IF structural A | **OPEN** | Hellín **B** · `docs/HELLIN_TRACK_A_SCORECARD.md` |
| D1 CyL | datos o follow-up | **FOLLOW_UP / wait** | silencio ~2026-08-17 |
| GO_MES+ | O2 + O5 + … | **false** | veredicto stretch |
| **GO_Q** | plan 3M | **partial** | `docs/PLAN_3_MESES_STATUS.json` |
| M3.2 demo | acta tercero | **PENDING** | plantilla lista |
| M3.4 informe | este documento | **ENG_FILLED** | este path |
| ml_product_go | product ML field | **false** | dual / rails |
| field_ops fusion | ML live | **OFF** | policy freeze |

**Masters de plan:** `docs/PLAN_3_MESES.md` · `docs/PLAN_3_MESES_STATUS.json` · `docs/PLAN_1_MES_MEJORA_GLOBAL.md` · `docs/PLAN_1_MES_POST_O1_UNLOCK.md` · `docs/PLAN_1_MES_GRAPH_V6_IMPLEMENT.md` · `docs/PLAN_1_MES_GRAPH_V6_STATUS.json` · `docs/LOOP_1M_SCORECARD_SNAPSHOT.json`

---

## 12. Limitaciones, riesgos y kill list

Copiado y contextualizado (sin suavizar):

1. **Fusión field_ops OFF** — no silent GO por ML de máscaras.  
2. **Sin inventar ROS / Vp / ha** — press y Δha no son anclas confirmed.  
3. **Sin k conjunto Tobarra–Hellín** (7 vs 50).  
4. **Cardoso / Estrella** no confirmed para GO.  
5. **FIRMS hull ≠ quemado oficial**.  
6. **GO_MES no se declara solo con O1** — requiere O4∧P1∧M2∧E1 (cumplidos al corte).  
7. **GO_Q no se declara sin M3.2** (acta).  
8. **IoU ≠ ROS** (`docs/METRICS_HONESTY_IOU_NE_ROS.md`).  
9. **Lampman MAE ≠ SLA Tobarra**; **Orion UQ ≠ labels EVACUATE**.  
10. **Dependencia externa:** partner CMA/Pablo, Juntas, CyL calendario silencio (~17 ago), O2 nacional.  
11. **Hellín grade A** no es primary del mes (kill param spam).  
12. **ML retrain** no es primary del mes sin datos nuevos no-Cardoso.

**Evidencia kill list plan:** `docs/PLAN_1_MES_GRAPH_V6_STATUS.json` `kill_list` · `docs/PLAN_1_MES_POST_O1_UNLOCK.md` §5 · `docs/PILOT_HONESTY_CARD.md` §4 · `docs/GUION_DEMO_30MIN_POST_O1.md` §1 · `docs/design/PILOT_PACK_REAL_HONESTY_CARD.md`

---

## 13. Trabajo futuro / backlog condicional (post-corte)

Solo como backlog; **no** implica GO_Q cerrado:

| ID | Acción | Owner |
|----|--------|-------|
| M3.2 | Ejecutar demo tercero + firmar acta | Humano |
| M3.4 | Sello/firma humana de este informe si se archiva formal | Humano |
| H3 | Walkthrough dry-run del pack | Humano (eng ready) |
| O5 | 2º grade A (Hellín o otro IF) **sin** param spam | Opcional eng / datos |
| O2 | Perímetro nacional o abstención formal | Externo |
| D1 | Post silencio CyL: un follow-up o cierre | Humano calendario |
| 3ª ancla | Cardoso/Estrella si llega Vp formal | Externo |
| Release tag | p.ej. `v1.1-decision-card` cuando GO_Q | Humano+eng |
| ML | **No** reentreno GPU sin datos nuevos no-Cardoso | Kill primary |

**Evidencia:** `docs/PLAN_3_MESES.md` Mes 3 · `docs/SUENOS_MAXIMOS.md` (filtrar sueños vs plan) · `docs/EMERGENCY_PRODUCT_STATUS.md`

---

## 14. Conclusiones

1. **Logro:** producto dual ops+ML documentado con rails de abstención; Decision Card y field kit operativos en ingeniería.  
2. **Logro:** **GO_MES = true** (mínimo plan) con O1 multi-ancla (Tobarra **A**, Hellín **B** honest) + smoke P1 en 2 IF reales + M2/E1.  
3. **Logro:** stack de evidencia terceros (pack + Reliability Report con citas Lampman/Orion + replay) y piloto multi-CCAA de honestidad.  
4. **Bloqueo honesto:** **GO_Q partial** — falta demo con tercero y acta (M3.2); este informe es **ENG_FILLED**, no sello formal humano.  
5. **Valor de pago:** audit + ABSTAIN + no silent GO, no “otro mapa gratis”.  
6. **Veredicto dual al corte:** **GO_ENG true** · **GO_MES true** · **GO_Q partial** · fusión OFF · `ml_product_go` false · IoU ≠ ROS.

---

## Anexos (paths; no cuentan en extensión narrativa)

| Anexo | Contenido | Path |
|-------|-----------|------|
| A | Scorecard mes 1 | `docs/SCORECARD_MES_1.md` |
| B | Hellín Track A | `docs/HELLIN_TRACK_A_SCORECARD.md` · `.json` |
| C | O1 recompute JSON | `docs/O1_GOMES_RECOMPUTE_20260803.json` |
| D | GO_MES veredicto | `docs/GO_MES_VERDICT.md` · `.json` |
| E | Pilot honesty | `docs/PILOT_HONESTY_CARD.md` |
| F | Reliability terceros | `docs/RELIABILITY_GATE_REPORT_THIRD_PARTY.md` |
| G | IoU ≠ ROS | `docs/METRICS_HONESTY_IOU_NE_ROS.md` |
| H | Acta demo (plantilla) | `docs/ACTA_DEMO_TERCERO_TEMPLATE.md` |
| I | Guion 30 min | `docs/GUION_DEMO_30MIN_POST_O1.md` |
| J | Metrics hub | `docs/METRICS_HUB.json` |
| K | Plan 3M / Graph v6 status | `docs/PLAN_3_MESES_STATUS.json` · `docs/PLAN_1_MES_GRAPH_V6_STATUS.json` |
| L | Entrega CMA Tobarra | `docs/entrega_cma/` |
| M | Demo multi-CCAA | `outputs/demo_multi_ccaa/` |
| N | Demo third-party pack | `outputs/demo_third_party/` · `docs/START_HERE.md` |
| O | Research → graph map | `docs/fire_intel/RESEARCH_TO_GRAPH_V6_MAP.md` |
| P | CyL silencio D1 | `docs/fire_intel/CYL_SILENCE_RULE_NOTE.md` · `docs/SOLICITUD_TRANSPARENCIA_CYL.md` |

---

## Mapa evidencia → sección (relleno)

| Path | Secciones |
|------|-----------|
| `docs/PRODUCTO_DUAL.md` | 1, 3, 7 |
| `docs/SCORECARD_MES_1.md` | 1, 5, 11 |
| `docs/GO_MES_VERDICT.md` | 1, 5, 11, 14 |
| `docs/HELLIN_TRACK_A_SCORECARD.md` | 5, 11 |
| `docs/P1_HELLIN_ENG_STATUS.md` | 5, 11, 12 |
| `docs/DATA_PROXY_HONESTY.md` | 4, 5, 12 |
| `docs/O1_GOMES_RECOMPUTE_20260803.json` | 1, 5, 11 |
| `docs/PILOT_HONESTY_CARD.md` | 3, 6, 12 |
| `docs/DATA_INTAKE_STATUS.md` | 4 |
| `docs/ONEPAGER_COMERCIAL_ES.md` | 2, portada |
| `docs/PLAN_3_MESES.md` / status | 1, 11, 13 |
| `docs/PLAN_1_MES_GRAPH_V6_*` | 1, 9, 11 |
| `docs/GUION_DEMO_30MIN_POST_O1.md` | 10 |
| `docs/ACTA_DEMO_TERCERO_TEMPLATE.md` | 10 |
| `docs/RELIABILITY_GATE_REPORT_THIRD_PARTY.md` | 1, 5, 9, 12 |
| `docs/METRICS_HONESTY_IOU_NE_ROS.md` | 1, 3, 7, 12 |
| `docs/START_HERE.md` | 1, 9, 10 |
| `docs/METRICS_HUB.md` | 7, 9 |
| `docs/design/PR_PLAN_FUEL_AEMET_ENVELOPE.md` | 8 |
| `outputs/demo_multi_ccaa/` | 6, 10 |
| `outputs/observatorio/hellin_2024/` · `tobarra_20240802/` | 5 |
| `docs/fire_intel/*` research | 9, anexos |

---

*Fin del informe ENG_FILLED. No modificar rails de producto “para mejorar el informe”. No reclamar M3.2 ni GO_Q completo.*
