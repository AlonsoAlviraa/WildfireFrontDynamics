# Informe de trimestre / memoria producto — esqueleto (8–12 pp)

> **Propósito:** armazón para **M3.4** (memoria trimestre / capítulos TFG producto) y cierre **GO_Q**.  
> **Regla:** rellenar solo con evidencia existente; **no inventar métricas**.  
> **Congelado dual-product:** ops Tobarra A + Hellín B/in-band; ML **lab only**; fusión `field_ops` **OFF**; `ml_product_go` **false**.  
> **No es el informe relleno:** solo secciones + bullets de paths de evidencia.  
> **Relleno eng (M3.4 / H2):** `docs/INFORME_TRIMESTRE_2026_Q_PRODUCTO.md` (ENG_FILLED; GO_MES true al corte 2026-08-04).  
> **Demo externa:** `docs/GUION_DEMO_30MIN_POST_O1.md` + `docs/ACTA_DEMO_TERCERO_TEMPLATE.md` (M3.2).

**Metadatos al rellenar**

| Campo | Valor |
|-------|--------|
| Título | WildfireFrontDynamics — informe de trimestre (producto) |
| Ventana | 2026-07-17 → 2026-10-17 (plan 3M) · foco mes 1 overlay post-O1 |
| Autor | |
| Versión doc | 0.1 esqueleto |
| Commit / tag | |

**Extensión objetivo:** 8–12 páginas (sin anexos) · anexos ilimitados por path.

---

## Portada (p. 1)

- [ ] Título, autor, afiliación, fecha  
- [ ] Una frase de producto (decision support + abstención)  
- [ ] Disclaimer: no es orden táctica de despacho  
- [ ] Clasificación: memoria técnica / TFG capítulo producto  

**Evidencia:** `docs/ONEPAGER_COMERCIAL_ES.md` · `docs/PRODUCTO_DUAL.md`

---

## 1. Resumen ejecutivo (½–1 pp)

Bullets a completar (sin cifras inventadas):

- [ ] Qué se entrega: Decision Card + audit + dual ops/open + ML lab documentado  
- [ ] Estado gates mes: **GO_ENG**; **NO_GO_MES** (P1 parcial); O1 **PASS**  
- [ ] Hallazgo humano pendiente: 1 demo tercero + acta (M3.2)  
- [ ] Hallazgo técnico: 2 anclas confirmed (Tobarra, Hellín); Hellín grade **B**  
- [ ] No-claims en una línea (fusión OFF, sin ROS inventado, sin ml_product_go)

**Evidencia:**

- `docs/SCORECARD_MES_1.md`
- `docs/O1_GOMES_RECOMPUTE_20260803.json`
- `docs/PLAN_3_MESES.md` (§ GO_Q)
- `docs/PLAN_1_MES_POST_O1_UNLOCK.md`
- `docs/PROJECT_STATUS.md` (si se usa como canónico de estado)

---

## 2. Problema y propuesta de valor (1 pp)

- [ ] Gap: mapas open gratis vs **decisión auditada** con abstención  
- [ ] Usuario: sala / CMA / research — políticas distintas  
- [ ] Qué se vende vs qué no (`ONEPAGER`)

**Evidencia:**

- `docs/ONEPAGER_COMERCIAL_ES.md`
- `docs/PRODUCT_REDESIGN_PAID_VALUE.md`
- `docs/design/DECISION_POLICY.md`
- `docs/funding/02_ONEPAGER_EU_EN.md` (si audiencia UE)

---

## 3. Arquitectura de producto dual (1–1.5 pp)

### 3.1 Ops (frente térmico)

- [ ] `front_dynamics_v1` / `incident_runtime_v1`  
- [ ] ROS multi-estimador, grades, ratio vs ancla  
- [ ] Field kit / brief  

### 3.2 ML lab

- [ ] Productos: `clm_ensemble_v34`, `clm_v28`, `ndws_v21` (G1 KILL features)  
- [ ] U1 honest vs catalog holdout = provenance only  
- [ ] `ml_product_go=false`  

### 3.3 Decision Card y políticas

- [ ] GO / HOLD / ABSTAIN  
- [ ] `field_ops` vs `research_open`  
- [ ] Fusión ML live en field_ops **OFF**  
- [ ] API mínima / replay / acta forense (eng, no confundir con acta demo)

**Evidencia:**

- `docs/PRODUCTO_DUAL.md`
- `docs/PILOT_HONESTY_CARD.md`
- `docs/FIRE_DECISION_CARD.json` / outbox examples
- `docs/FIELD_KIT_INCIDENT.md`
- `docs/INCIDENT_RUNTIME_V1.md`
- `docs/design/MINIMAL_DECIDE_API.md`
- `docs/DECIDE_API_LATENCY.json`
- `config/decision_policies.json` (si se cita)
- `docs/ML_PRODUCT_SCORECARD.json` · `docs/ML_LOOP_RAILS.md`
- Commander: `docs/commander/index.html` · `docs/commander/README.md`

---

## 4. Datos e ingesta (1 pp)

- [ ] Inventario IF / máscaras / QA  
- [ ] Anclas INFOCAM: protocolo confirmed vs proxy  
- [ ] Open multi-CCAA: REDIAM, RAI, CEMS  
- [ ] Outreach / contactos (sin spam narrative)

**Evidencia:**

- `docs/DATA_INTAKE_STATUS.md`
- `data/infocam_anchors.json`
- `docs/DATA_PROXY_HONESTY.md` — confirmed vs proxy (Estrella/Cardoso no son anclas GO)
- `docs/REAL_IF_INTAKE_PROTOCOL.md`
- `docs/REAL_IF_AUDIT_TOBARRA_20240802.md`
- `docs/CONTACTOS_EMERGENCIAS_DATOS.md`
- `docs/CONTACTOS_OUTREACH.csv`
- `docs/open_if_intake/` (REDIAM, RAI, La Mierla notes)
- `docs/OPEN_RESOURCES_CATALOG.md`

---

## 5. Resultados operativos multi-ancla (1.5–2 pp)

### 5.1 Tobarra (grade A)

- [ ] Ancla Vp 7 / ha 39  
- [ ] ROS / ratio / grade  
- [ ] Limitaciones FOV / partner  

### 5.2 Hellín (2ª ancla, grade B)

- [ ] Ancla Vp 50 / ha 100\*  
- [ ] ROS ~27.9, ratio ~0.56 in-band  
- [ ] Por qué no grade A / P1 abierto  
- [ ] Honestidad: no k conjunto Tobarra↔Hellín  

### 5.3 O1 / GO_MES

- [ ] Fórmula GO_MES = O1 ∧ O4 ∧ P1 ∧ M2 ∧ E1  
- [ ] Tabla componentes actual  
- [ ] Veredicto **NO_GO_MES** con fecha  

**Evidencia:**

- `docs/HELLIN_TRACK_A_SCORECARD.md` · `docs/HELLIN_TRACK_A_SCORECARD.json`
- `docs/P1_HELLIN_ENG_STATUS.md` — eng BLOCKED P1/O5; **no** implica GO_MES
- `docs/O1_GOMES_RECOMPUTE_20260803.json`
- `docs/SCORECARD_MES_1.md`
- `outputs/observatorio/hellin_2024/`
- `outputs/observatorio/anchor_scorecard.json` (si existe)
- `docs/entrega_cma/` (figs + informe técnico v1.0)
- `docs/O2_HAUSDORFF_BLOCKED.md`
- `docs/O3_TEMPORAL_WINDOWS_SNAPSHOT.json`

---

## 6. Open multi-CCAA y piloto de honestidad (1–1.5 pp)

- [ ] Tobarra · Níjar · Caminomorisco — misma Decision Card  
- [ ] Tabla research_open vs field_ops  
- [ ] Demo portal reproducible  
- [ ] Industrial E2E AND/EXT (actas 10/10 capas)  

**Evidencia:**

- `docs/PILOT_HONESTY_CARD.md`
- `outputs/pilot_honesty_card/`
- `docs/design/DEMO_MULTI_CCAA_TOBARRA_NIJAR_CAMINOMORISCO.md`
- `docs/design/DEMO_FRONT_SALES_HANDOFF.md`
- `outputs/demo_multi_ccaa/`
- `docs/AND_INDUSTRIAL_E2E_VERIFICATION.md` · `.json`
- `docs/EXT_INDUSTRIAL_E2E_VERIFICATION.md` · `.json`
- `docs/GOLD_IF_E2E_VERIFICATION.md` · `.json`
- `docs/COMPARE_CLM_VS_OPEN.md` · scorecard JSON

---

## 7. ML laboratorio (1 pp)

- [ ] Champion v34: métricas U1 honest + catalog provenance  
- [ ] Rails / no leakage Cardoso en claim de promote  
- [ ] Gates G0/G1/G2/G2e  
- [ ] Qué **no** se afirma en campo  

**Evidencia:**

- `docs/PRODUCTO_DUAL.md`
- `docs/ML_BASELINE_METRICS.json` · `.md`
- `docs/ML_PRODUCT_SCORECARD.json`
- `docs/ML_U1_PROMOTE_RECORD.json`
- `docs/ML_LIVE_ABSTAIN_ECE_NOTE.md`
- `docs/ML_FEATURE_METHODOLOGY.md`
- `docs/ML_TRANSFER_PROTOCOL.md`
- `models/clm_ensemble/manifest.json` · `models/catalog.json`
- `docs/METRICS_HUB.md` · `docs/METRICS_HUB.json`

---

## 8. Fuel, meteorología y envelope (½–1 pp)

- [ ] PR-α/β AEMET + envelope v3  
- [ ] Scorecard Tobarra pipeline  
- [ ] Envelope **peso 0** en Decision Card (política)  
- [ ] No claim táctico  

**Evidencia:**

- `docs/design/PR_PLAN_FUEL_AEMET_ENVELOPE.md`
- `docs/DESIGN_ENVELOPE_V3_HYBRID.md`
- scripts/scorecards fuel-AEMET (citar path real al rellenar)
- `docs/SCORECARD_MES_1.md` (fila Fuel / AEMET)

---

## 9. Ingeniería, fiabilidad y reproducibilidad (1 pp)

- [ ] CI / E1 / smokes  
- [ ] Reliability gate / residual silent-GO (definición contractual vs predicción fuego)  
- [ ] Decide API latency  
- [ ] Incident SLA  
- [ ] Rituales `run_plan_cycle` / graph  

**Evidencia:**

- `docs/INDUSTRIAL_PRODUCTION_GATES.md`
- `docs/INDUSTRIAL_READINESS_STATUS.json`
- `docs/RELIABILITY_GATE_REPORT.json`
- `docs/OPS_ML_SMOKE_SNAPSHOT.json`
- `docs/INCIDENT_SLA_LATENCY.json`
- `docs/DECIDE_API_LATENCY.json`
- `docs/PRODUCCION_INDUSTRIAL_ESTADO.md`
- `docs/LOOP_ENGINEERING_PLAN.md`
- `docs/graph_evolution/` (cycles post-O1)
- `.grok/graph_engineering/STATE.md` (si se documenta proceso)

---

## 10. Demo con tercero y validación humana (½–1 pp)

- [ ] Guion 30 min ejecutado  
- [ ] Acta firmada (fecha, asistentes, kill list)  
- [ ] Feedback y follow-ups  
- [ ] Estado M3.2  

**Evidencia:**

- `docs/GUION_DEMO_30MIN_POST_O1.md`
- `docs/ACTA_DEMO_TERCERO_TEMPLATE.md` → copia rellenada `docs/actas/…`
- `docs/funding/04_GUION_DEMO_10MIN.md` (variante corta)
- `docs/PLAN_3_MESES_STATUS.json` (M3.2)

---

## 11. Estado de gates y veredictos (1 pp · tabla)

Rellenar desde scorecards; **no inventar**:

| Gate / fórmula | Criterio (resumen) | Estado | Path evidencia |
|----------------|--------------------|--------|----------------|
| O1 multi-ancla | ≥2 confirmed + ratio banda | | O1_GOMES… |
| O4 brief | field kit | | FIELD_KIT… |
| P1 2 IF | grade A usable ×2 | | HELLIN… · SCORECARD |
| M2 v34 | no regresión catalog | | manifest / SCORECARD |
| E1 CI | smokes/tests | | INDUSTRIAL… |
| **GO_MES** | O1∧O4∧P1∧M2∧E1 | **NO_GO_MES** (hasta P1) | SCORECARD |
| O2 Hausdorff | oficial | BLOCKED / proxy | O2_… |
| O5 2º grade A | | OPEN | HELLIN… |
| GO_Q | fórmula PLAN_3_MESES | | PLAN_3_MESES_STATUS |
| M3.2 demo | acta tercero | | acta rellenada |
| M3.4 informe | este documento relleno | | este path |

**Evidencia master:**

- `docs/PLAN_3_MESES.md` · `docs/PLAN_3_MESES_STATUS.json`
- `docs/PLAN_1_MES_MEJORA_GLOBAL.md`
- `docs/PLAN_1_MES_POST_O1_UNLOCK.md`
- `docs/SCORECARD_MES_1.md`
- `docs/LOOP_1M_SCORECARD_SNAPSHOT.json`

---

## 12. Limitaciones, riesgos y kill list (½–1 pp)

Copiar y contextualizar (no suavizar):

- [ ] Fusión field_ops OFF; no silent GO  
- [ ] Sin inventar ROS/Vp/ha  
- [ ] Sin k conjunto Tobarra–Hellín  
- [ ] Cardoso/Estrella no confirmed  
- [ ] FIRMS hull ≠ quemado oficial  
- [ ] GO_MES no se declara solo con O1  
- [ ] Dependencia datos externos (Pablo/CMA, Juntas, CyL calendario)

**Evidencia:**

- `docs/PLAN_1_MES_POST_O1_UNLOCK.md` §5 Kill list  
- `docs/PILOT_HONESTY_CARD.md` §4  
- `docs/design/PILOT_PACK_REAL_HONESTY_CARD.md`  
- `docs/GUION_DEMO_30MIN_POST_O1.md` §1  

---

## 13. Trabajo futuro / Q2 backlog (½ pp)

Solo si GO_Q o como backlog condicional (M3.5):

- [ ] Cerrar P1 (Hellín grade A o BLOCKED eng escrito)  
- [ ] O2 nacional o abstención formal  
- [ ] 3ª ancla confirmed si llega  
- [ ] Carta interés / presupuesto piloto  
- [ ] Tag release producto (`v1.1-decision-card` u otro acordado)  
- [ ] **No** reentreno GPU sin datos nuevos no-Cardoso  

**Evidencia:**

- `docs/PLAN_3_MESES.md` Mes 3  
- `docs/SUENOS_MAXIMOS.md` (filtrar sueños vs plan)  
- `docs/EMERGENCY_PRODUCT_STATUS.md`

---

## 14. Conclusiones (½ pp)

- [ ] Tres bullets de logros demostrables  
- [ ] Un bullet de bloqueo honesto  
- [ ] Un bullet de valor de pago (audit/abstención)  
- [ ] Veredicto dual: GO_ENG / estado GO_MES / estado GO_Q  

---

## Anexos (no cuentan en 8–12 pp)

| Anexo | Contenido | Path |
|-------|-----------|------|
| A | Scorecard mes 1 | `docs/SCORECARD_MES_1.md` |
| B | Hellín Track A | `docs/HELLIN_TRACK_A_SCORECARD.md` |
| C | O1 recompute JSON | `docs/O1_GOMES_RECOMPUTE_20260803.json` |
| D | Pilot honesty | `docs/PILOT_HONESTY_CARD.md` |
| E | Acta demo tercero | plantilla + relleno |
| F | Guion 30 min | `docs/GUION_DEMO_30MIN_POST_O1.md` |
| G | Metrics hub snapshot | `docs/METRICS_HUB.json` |
| H | Plan 3M status | `docs/PLAN_3_MESES_STATUS.json` |
| I | Entrega CMA Tobarra | `docs/entrega_cma/` |
| J | Demo multi-CCAA manifest | `outputs/demo_multi_ccaa/demo_manifest.json` |

---

## Cómo rellenar (checklist autor)

1. Congelar commit/tag y fecha de corte.  
2. Copiar tablas de SCORECARD / O1 / HELLIN **sin redondeos creativos**.  
3. Pegar 1 captura portal + 1 Decision Card (anexo).  
4. Si M3.2 hecho: anexar acta firmada; si no: marcar PENDING y no reclamar GO_Q completo.  
5. Revisar kill list §12 línea a línea antes de PDF.  
6. No tocar `ml_product_go` ni fusion field_ops en código “para el informe”.

---

## Mapa rápido evidencia → sección

| Path | Secciones |
|------|-----------|
| `docs/PRODUCTO_DUAL.md` | 1, 3, 7 |
| `docs/SCORECARD_MES_1.md` | 1, 5, 11 |
| `docs/HELLIN_TRACK_A_SCORECARD.md` | 5, 11 |
| `docs/P1_HELLIN_ENG_STATUS.md` | 5, 11, 12 |
| `docs/DATA_PROXY_HONESTY.md` | 4, 5, 12 |
| `docs/O1_GOMES_RECOMPUTE_20260803.json` | 1, 5, 11 |
| `docs/PILOT_HONESTY_CARD.md` | 3, 6, 12 |
| `docs/DATA_INTAKE_STATUS.md` | 4 |
| `docs/ONEPAGER_COMERCIAL_ES.md` | 2, portada |
| `docs/PLAN_3_MESES.md` | 1, 11, 13 |
| `docs/GUION_DEMO_30MIN_POST_O1.md` | 10 |
| `docs/ACTA_DEMO_TERCERO_TEMPLATE.md` | 10, M3.2 |
| `docs/METRICS_HUB.md` | 7, 9 |
| `docs/design/PR_PLAN_FUEL_AEMET_ENVELOPE.md` | 8 |
| `outputs/demo_multi_ccaa/` | 6, 10 |
| `outputs/observatorio/hellin_2024/` | 5 |
