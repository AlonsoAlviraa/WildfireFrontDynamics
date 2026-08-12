# Auditoría de cuellos B1–B10 × prácticas de industria (2023–2026)

> **As of:** 2026-08-10  
> **Método:** `/deep-research` (grok-workflows) — multi-source + verificación adversarial  
> **Claims verificados:** **89** · **dropped:** **10** (todos `refuted`) · **0** duplicates · **0** verifierFailed  
> **Nota de síntesis:** el agente de síntesis del harness falló (`spawn ENAMETOOLONG`); este documento es la **síntesis WFD-mapeada** sobre claims verificados.  
> **Raw:** `outputs/research/deep_research_b1_b10_raw.json` · claims legibles: `outputs/research/claims_readable.txt`  
> **Estado canónico WFD:** `docs/CURRENT_STATE.md` · venta: `docs/MEGA_AUDIT_SELL_20260805.md` · ML closeout: `docs/GOAL_ML_CLOSEOUT.md`

---

## 0. Veredicto en una página

| Lente | Conclusión |
|-------|------------|
| **¿El eng es el cuello principal?** | **No.** El cuello **crítico** (B1/H1) y varios de alto impacto (B5, B10, parte de B4/B6) son **humano / datos / agencias**. |
| **¿Qué dice la industria?** | Productos de apoyo a decisión en incendios se venden y se despliegan con **HITL**, validación **multi-incendio**, dual-track **open vs ops**, y **freeze + más datos** cuando LOFO se estanca — no con más thrash de arquitectura. |
| **Alineación WFD** | WFD ya hace lo “difícil de industria” en lab (LOFO sellado, kill list, fusion OFF, Decision Card ABSTAIN). Falta lo que **no se codifica**: demo con tercero, 2º grade A, perímetro nacional, máscaras/chain honest. |
| **Prioridad EV (industria + WFD)** | **B1** (calendario) → **B2/B3** (higiene ½–2 días) → **B4/B7** (datos multi-IF + labels) → **B6** solo con nueva clase de dato → **B8** como SKU field_ops (ya hay superficie; skill ≠ IoU) → **B5/B10** pipeline de waits → **B9** continuo. |

```
[ENG CONTROLA]                    [NO CONTROLA / CALENDARIO]
B2 docs/flags SSOT       ──┐
B3 repo noise            ──┼── velocidad / credibilidad interna
B9 scripts hygiene       ──┘
B8 multihorizon product  ── skill surface (no mean IoU)
B4 partial (packs, scores) ── necesita 2º IF grade A (datos)
B6 partial (protocol)    ── LOFO hard fire = techo sin nuevos IF
B7 partial (label QA)    ── máscaras / chain_honest
B1 H1 demo+acta          ── humano 30 min + tercero
B5 O2 nacional           ── EGIF/CCAA / FOI / partner
B10 CyL/GAL/OAuth        ── transparencia + login gates
```

---

## 1. Tabla maestra B1–B10

| ID | Cuello | Sev. WFD | Control eng | ETA priorizado | Estado WFD (2026-08-10) | Cómo lo mejora la industria | Acción WFD recomendada |
|----|--------|----------|-------------|----------------|-------------------------|-----------------------------|------------------------|
| **B1** | H1 humano (demo+acta tercero) | **crítica** | **no** | 1 call 30 min | GO_Q **partial**; demo eng listo | Alpha→beta con stakeholders; HITL; TRL 6–7; métricas operativas (no solo IoU) | **Agendar 1 tercero** + cheatsheet 12 min + acta; no más retrain como sustituto |
| **B2** | Docs/flags desalineados | alta | **sí** | ½ día | CURRENT_STATE vs stale JSON residual | SSOT + GitOps + model registry + flags = release plane | Un solo `CURRENT_STATE` + CI check de flags (`ml_product_go` ≠ fusion); matar docs stale |
| **B3** | Repo noise (`_*`, untracked) | alta | **sí** | 1–2 h | Limpieza 2026-08-10 hecha; residual untracked data/ | `.gitignore` AI-era + artefactos en workspace versionado + worktrees | Completar ignore data/large; no reintroducir `_FINAL_*` en raíz |
| **B4** | Solo 1 grade A ops | alta | **parcial** | semanas | Tobarra **A**; Hellín **B**; GO_MES+ false | Multi-incident (Cardil 1853; ELMFIRE 214; Filippi 80) + ± error bands | Buscar 2º ancla + scorecard grade; no redefinir grade A por un showcase |
| **B5** | O2 nacional BLOCKED | media-alta | **no** | externo | Nacional BLOCKED; Tobarra ops PARTIAL; CEMS proxy | Dual-track NIFC open vs IRWIN auth; EFFIS WFS; EGIF FOI/XML | Mantener proxy CEMS/ops; FOI/partner para catastro; no vender “cadastre oficial” |
| **B6** | ML Tobarra LOFO ~0.48 | alta *si se vende ML* | solo datos/features | mes+ | KEEP **KILL** (K1 −0.012); FREEZE+REQUEST_DATA | LOFO/GroupKFold estándar; reject/uncertainty; train≠eval labels | **No thrash KEEP**; pitch lab sealed 0.79; campo = ABSTAIN fusion OFF |
| **B7** | Máscaras incompletas | media | parcial | días–semanas | Corpus pequeño; chain_honest backlog | CEOS LPV unmapped; noisy-label models; weak supervision | Label QA + unmapped mask; priorizar chain multi-día FOV-alineado |
| **B8** | Multi-horizon táctico | media (roadmap) | **sí, caro** | trimestre | API 1/3/5/12/24 h **sí**; skill física; **no** lift IoU | NICC 7d / USGS / NextDay / SpreadTS / hybrid physics+AI | Vender envelope honest; validar multipass; no reclamar IoU |
| **B9** | Scripts > código producto | media | **sí** | continuo | ~177 scripts vs ~114 package py | Rules of ML: infra first; scripts reutilizables; CI | Promover paths estables a `wildfire_front/`; archivar lab one-shots |
| **B10** | External waits CyL/GAL/OAuth | baja-media | **no** | calendario | CyL 4082 / GAL / logins en waits | Open data regional + FOI + dual auth/public | Tracker de waits + open fallbacks; no bloquear H1 |

---

## 2. Análisis por cuello (industria → WFD)

### B1 — H1 humano (crítico, no eng)

**WFD hoy:** Operator UX, Decision Card, pack third-party y Reliability Report están listos. Falta **demo + acta con tercero** → GO_Q partial. Mega-auditoría de venta: evidencia externa ~25/100.

**Industria (claims verificados):**

- Pilotos gubernamentales de sensores ML usan **alpha → beta OT&E con la comunidad de bomberos**, no demos solo de lab (DHS S&T; métricas tipo head-start vs 911, control de falsos positivos).
- **HITL** es gate operativo (cámaras AI HI/CA; verificación humana antes de alerta).
- USFS: la **decisión final** queda en managers humanos; WFDSS es system-of-record — el ML comercial **se integra**, no reemplaza la pila de política.
- OGC / SAPEA / NIST AI RMF: HITL, intervalos de confianza, fit-for-purpose, Govern–Map–Measure–Manage.
- TRL: pilotos humanos suelen ser **TRL 6–7** (demo en entorno relevante) antes de GTM producción.
- GAO: eng acelera asimilación y flag de errores; **no** resuelve datos raros, liability ni adopción.

**Qué controla eng / no:**

| Sí | No |
|----|-----|
| UI demo, cheatsheet, kill list verbal, packs replay, métricas TEVV | Calendario del tercero, cultura de adopción, procurement, decisión de vida/seguridad |

**Mejora industria-style para WFD:**

1. Tratar H1 como **OT&E gate**, no como “falta feature”.
2. Métricas de demo: tiempo a Decision Card, ABSTAIN honesto, ROS multipass vs Vp — **no** IoU de lab.
3. Un solo call 30 min + acta (`docs/ACTA_DEMO_TERCERO_TEMPLATE.md`) desbloquea más valor comercial que otro Kaggle run.

---

### B2 — Docs / flags desalineados (alta, eng sí)

**WFD hoy:** `CURRENT_STATE.md` es autoridad; aún hay JSON/docs stale históricos (p.ej. readiness viejos). Riesgo clásico: `ml_product_go` vs `field_ops fusion OFF` mal leídos por un pitch.

**Industria:**

- Config como **código versionado** + GitOps self-heal (GKE Config Sync, Terraform).
- Feature flags = **control plane de release** (dark ship, canary, kill switch) separado del deploy.
- Feature registry SSOT offline/online; CI valida **código + schema + modelo**.
- Model registry enlaza versión ↔ data lineage ↔ env; model cards + policy-as-code.
- OGC wildland fire: MLOps + provenance como gobernanza de misión.

**Acción eng (½ día):**

1. Un script/CI: `fusion_off && (ml_product_go implies lab_only_banner)`.
2. Lista de “docs autoridad” en `START_HERE` / `REPO_MAP`; marcar stale en cabecera.
3. Un JSON de release flags único leído por CLI `ml doctor` / `operator`.

---

### B3 — Repo noise (alta, eng sí)

**WFD hoy:** Limpieza 2026-08-10 (~480 artefactos agent); `REPO_MAP` + `.gitignore` endurecido. Siguen untracked grandes en `data/` (esperado) y ruido potencial de agentes.

**Industria:**

- Ignore en **3 capas**: build, secrets, **AI context** (`.cursorignore` / agent exclude) — git-ignore ≠ agent-invisible.
- Artefactos de agent: naming, carpetas draft/final/archive, retención, audit de qué agente creó qué.
- Worktrees aislados; PRs atómicos revertibles (checklist CTO AI coding 2026).
- SE-ML / Google Rules of ML: versionar data/model/config; quitar features muertas; CI + static analysis.
- Wildfire ML review: solo ~7.7% papers con código abierto — **higiene = ventaja competitiva ops-grade**.

**Acción eng (1–2 h residual):**

1. No recrear `_FINAL_*` / `_OUT_*` en raíz.
2. Outputs de research/agent → `outputs/research/` o `docs/archive/`.
3. Mantener data grandes gitignored; documentar en REPO_MAP.

---

### B4 — Solo 1 grade A ops (alta, parcial)

**WFD hoy:** Tobarra grade **A** (ROS multipass ~6.14 vs Vp 7). Hellín grade **B**. GO_MES+ false por 2º grade A / O2 / demo.

**Industria (estándar multi-incendio, no showcase):**

- Cruz & Alexander: banda de adecuación ROS **±35%**; error medio alto y sesgo de subpredicción frecuente — un solo “grade A” no prueba flota.
- Cardil et al. 2023: **1 853** incendios CA; MAPE ~47% aún “usable” con modos de ajuste en línea.
- ELMFIRE: ASTM E1355 + **214** forecasts retrospectivos con rúbrica Poor→Excellent.
- Filippi et al.: **80** fuegos, simulaciones **ciegas sin tuneo**; ranking por distribución de scores.
- Duff: ADI + F1 entre índices preferidos; no hay un único índice universal.
- USDA PCL: multi-temporada, >80% / 90% contención success/fail.

**Acción WFD:**

1. Definir **board multi-IF** (ya LOFO lab; falta ops grade board público) con distribución, no media de un caso.
2. Pipeline de intake para 2º ancla (Hellín upgrade o nuevo IF) con mismos criterios Tobarra.
3. Pitch honesto: “1 A + 1 B + open packs” = GO_MES mínimo, **no** flota nacional.

---

### B5 — O2 nacional BLOCKED (media-alta, no eng)

**WFD hoy:** Nacional/catastral **BLOCKED**. Tobarra ops KMZ **PARTIAL_GO**. CEMS **GO_PROXY**. No vender catastro oficial.

**Industria (gobernanza dual):**

- EE.UU.: IRWIN/EGP **auth** (grupo ArcGIS + token) vs **NIFC Open Data** público post-GeoMAC.
- Europa: **EFFIS** WMS/WFS open; historic vía **data request form**.
- España: EGIF consolidado CCAA con **lag ~2 años** histórico; Civio vía FOI; MITECO XML/buscador (tabular, no FeatureServer NRT).
- CyL: informativos open (CSV/JSON) en datos.gob.es — path regional cuando nacional no expone perímetro vivo.
- FIRMS: open + Earthdata login ligero; FEDS OGC API perimeters NRT.

**Acción WFD:**

1. Mantener **dual-track** (ya: open CEMS/AND/EXT vs ops LWIR).
2. FOI / partner CCAA para perímetro cuando exista; no bloquear producto en O2 nacional.
3. Documentar en pitch: “O2 proxy ≠ catastro EGIF”.

---

### B6 — ML Tobarra LOFO ~0.48 (alta si se vende ML)

**WFD hoy:** Fresh LOFO IoU **0.4776**; K1 lift **−0.012** → **KILL**. Sealed core3 mean **0.7878**. Closeout: **FREEZE_ML_AND_REQUEST_DATA**. Fusion field **OFF**.

**Industria:**

- LOFO / GroupKFold by `fire_id` / LOCO = protocolo de **transfer real** (burn severity 2025; Portugal burned-area; CROWNFIRE-AI).
- Separar **labels de train ruidosos** (FIRMS/NIFC) de **eval QA manual** (TS-SatFire).
- Uncertainty + **reject** (ECE, discard tests) para go/no-go — alinea con Decision Card ABSTAIN.
- Label noise heteroscedástico en EO; weak supervision desde tags imagen cuando no hay máscara perfecta.
- GAO / Caron: adopción bloqueada por datos, métricas y coste — no por “un U-Net más grande”.

**Acción WFD (alineada closeout):**

1. **No reabrir Tobarra KEEP** sin nueva clase de señal (features/data/protocol).
2. Vender: lab sealed multi-IF + reject; **no** “IoU 0.48 resuelto”.
3. Único EV residual: **chain_honest multi-día** + más fuegos (REQUEST_DATA).

---

### B7 — Máscaras incompletas (media, parcial)

**WFD hoy:** Corpus pequeño; máscaras/parches heterogéneos; backlog chain_honest.

**Industria:**

- CEOS LPV: referencia con **burned / unburned / unmapped** (nubes/sombra) — product-to-product no basta.
- Train ruidoso vs test limpio (TS-SatFire).
- Weak supervision / uncertainty-aware BA mapping sin máscara pixel-perfect.

**Acción WFD:**

1. Schema de máscara: explícito `unmapped` + provenance.
2. Priorizar **calidad de 3–5 IF chain** sobre cantidad FIRMS-only.
3. No mezclar IoU de máscara incompleta con ROS ops.

---

### B8 — Multi-horizon táctico ausente / incompleto (media, eng caro)

**WFD hoy:** Superficie field_ops 1/3/5/12/24 h **entregada** (iso + aniso + hybrid envelope); **sin** lift lab IoU. Validación multipass PARTIAL en Tobarra (span IR corto).

**Industria — roadmap multi-capa estándar:**

| Horizonte | Práctica ops/ML |
|-----------|-----------------|
| Sub-hora / hora | GOES ~5 min; NOAA hourly wildfire potential experimental; front reconstruction |
| 12–24 h | Next Day Wildfire Spread; WildfireSpreadTS (NeurIPS 2023); hybrid AI+physics (UB 2026) |
| 1–7 días | NICC 7-Day Significant Fire Potential; USGS WFPI/WLFP/WFSP |
| Mensual–estacional | NICC monthly outlooks |
| Binding constraints | Freshness de **fuel** (ECMWF/NCAR), label noise, asimilación multi-sensor — **antes** que arquitectura |

**Acción WFD:**

1. Pitch: multihorizon = **envelope geométrico honest** + ROS medido; **≠** NextDay ML.
2. PR plan skill: validar envelopes en multipass cuando haya cadena IR.
3. No reabrir U-Net scale como atajo a multihorizon.

---

### B9 — Scripts > código producto (media, higiene continua)

**WFD hoy (aprox.):** `scripts/` ~**177** py vs `wildfire_front/` ~**114** py (+ kaggle_job). Normal en lab ML; riesgo: paths de demo que solo viven en scripts one-shot.

**Industria:**

- Google Rules of ML: **infra end-to-end limpia** antes de modelo complejo.
- SE-ML: notebooks → scripts testeables en pipeline; CI + regression.
- Archivar features no usadas; versionar training scripts con data IDs.

**Acción WFD:**

1. Paths de demo/operator/ml freeze ya en paquete — mantener.
2. Lab loops v34 / one-shots: prefijo claro o `scripts/lab/` + no importados por producto.
3. Cada script “de venta” debe tener test o smoke en CI.

---

### B10 — External waits CyL / GAL / OAuth (baja-media, no eng)

**WFD hoy:** Transparencia CyL, Galicia Extinción, logins OAuth/agency en calendario. No deben bloquear H1 ni GO_MES mínimo.

**Industria:**

- Siempre hay **fallback open** (NIFC open, EFFIS, datos regionales CyL CSV) cuando ops feed es auth-only.
- FOI + open portal cuando API NRT no existe (EGIF España).
- Token/group membership (IRWIN) = patrón normal — planear onboarding de credenciales como workstream, no como bug de código.

**Acción WFD:**

1. Board de waits con owner + next touch date.
2. Usar open proxies ya integrados para demos.
3. No mezclar “esperando CyL” con “producto no demoable”.

---

## 3. Priorización EV (industria × controlable)

Orden recomendado (impacto / esfuerzo / control):

| Rank | ID | Por qué ahora |
|------|-----|----------------|
| 1 | **B1** | Único gate crítico de credibilidad B2G; 30 min humano; eng ya plateau |
| 2 | **B2** | ½ día; evita pitch mentirosa por flag drift |
| 3 | **B3** residual | 1–2 h; protege onboarding y agentes |
| 4 | **B4 + B7** | Desbloquean GO_MES+ y ML data path; semanas; partner/data |
| 5 | **B6** | Solo vía REQUEST_DATA; freeze recipe |
| 6 | **B8** | Producto ya existe; invertir en validación skill, no en IoU |
| 7 | **B5 + B10** | Tracker + FOI; no bloquean venta de piloto decisión |
| 8 | **B9** | Continuo; no sprint único |

**Anti-patrones (industria + rails WFD):**

- Sustituir H1 por otro ciclo autónomo de honesty/ML.
- Reabrir Tobarra KEEP / ECE same-holdout / larger U-Net.
- Vender multihorizon o sealed IoU como “despacho táctico”.
- Esperar O2 nacional antes de demo.

---

## 4. Matriz “industria vs WFD ya hecho”

| Práctica industria | ¿WFD ya? | Gap |
|--------------------|----------|-----|
| HITL / ABSTAIN / no autonomía total | **Sí** (Decision Card, fusion OFF) | Falta **acta externa** (B1) |
| LOFO / group by fire | **Sí** (sealed + Tobarra KEEP protocol) | Hard-fire techo; más IF (B6/B7) |
| Dual open vs ops data | **Sí** (CEMS/AND/EXT + LWIR) | Nacional auth (B5) |
| Multi-incident validation | **Parcial** (2 anclas, 1 grade A) | N≥ varios grade A/B board (B4) |
| Model freeze + kill list | **Sí** (FREEZE_ML_AND_REQUEST_DATA) | Disciplina de no thrash |
| Multi-horizon product layers | **Parcial** (field_ops API) | Validación skill + fuel freshness (B8) |
| SSOT config/docs | **Parcial** | CI flags + stale purge (B2) |
| Agent/repo hygiene | **Parcial** (cleanup 08-10) | Mantener (B3/B9) |
| External data governance | **Parcial** | Waits tracker (B10) |

---

## 5. Fuentes (muestra; 89 claims en raw)

Pilots / GTM: [DHS S&T wildfire tech](https://www.dhs.gov/science-and-technology/technology-reduce-impacts-wildfires) · [GAO-25-108589](https://www.gao.gov/assets/880/879886.pdf) · [USFS AI wildfire](https://research.fs.usda.gov/sites/default/files/2026-05/ai-fire-project-final-ver2.pdf) · [WFDSS](https://research.fs.usda.gov/firelab/products/dataandtools/wildland-fire-decision-support-system-wfdss) · [OGC GenAI wildland fire ER](https://www.ogc.org/wp-content/uploads/2025/07/24-071_OGC_CLIMATE_AND_DISASTER_RESILIENCE_PILOT_IV_D-123_GENERATIVE_AI_IN_WILDLAND_FIRE_MANAGEMENT_ENGINEERING_REPORT.pdf) · [SAPEA crisis AI 2025](https://scientificadvice.eu/scientific-outputs/artificial-intelligence-in-emergency-and-crisis-management-rapid-evidence-review-report/) · [NIST AI RMF](https://www.nist.gov/itl/ai-risk-management-framework)

MLOps / hygiene: [Google MLOps](https://docs.cloud.google.com/architecture/mlops-continuous-delivery-and-automation-pipelines-in-machine-learning) · [ml-ops.org principles](https://ml-ops.org/content/mlops-principles) · [SE-ML practices](https://se-ml.github.io/practices/) · [Rules of ML](https://developers.google.com/machine-learning/guides/rules-of-ml) · [Cursor agent practices](https://cursor.com/blog/agent-best-practices)

Ops validation: [Cruz & Alexander Treesearch](https://research.fs.usda.gov/treesearch/49457) · [Cardil / Technosylva](https://technosylva.com/a-first-time-validation-of-fire-spread-modeling-on-the-fire-line/) · [ELMFIRE validation](https://elmfire.io/validation.html) · [Filippi et al. NHESS](https://nhess.copernicus.org/articles/14/3077/2014/)

Data governance: [USGS perimeter FAQ](https://www.usgs.gov/faqs/where-can-i-find-wildfire-perimeter-data) · [EFFIS data](https://forest-fire.emergency.copernicus.eu/applications/data-and-services) · [Civio EGIF methodology](https://civio.es/en/environment/spain-in-flames-methodology/) · [MITECO EGIF](https://www.miteco.gob.es/es/biodiversidad/temas/incendios-forestales/estadisticas-datos.html) · [CyL open data](https://datos.gob.es/en/catalogo/a07002862-incendios-forestales1)

LOFO / labels: [Van et al. Remote Sensing 2025](https://www.mdpi.com/2072-4292/17/22/3756) · [TS-SatFire](https://github.com/zhaoyutim/TS-SatFire) · [CEOS LPV BA protocol](https://lpvs.gsfc.nasa.gov/PDF/BurnedAreaValidationProtocol.pdf) · [Kondylatos arXiv noisy labels](https://arxiv.org/html/2504.03478)

Multi-horizon: [NICC outlooks](https://www.nifc.gov/nicc/predictive-services/outlooks) · [USGS Fire Danger](https://www.usgs.gov/fire-danger-forecast) · [WildfireSpreadTS NeurIPS](https://proceedings.neurips.cc/paper_files/paper/2023/hash/ebd545176bdaa9cd5d45954947bd74b7-Abstract-Datasets_and_Benchmarks.html) · [Next Day Wildfire Spread](https://research.google/pubs/next-day-wildfire-spread-a-machine-learning-dataset-to-predict-wildfire-spreading-from-remote-sensing-data/) · [ECMWF fuel BG 2024](https://bg.copernicus.org/articles/21/279/2024/)

---

## 6. Stats de verificación del harness

| Métrica | Valor |
|---------|------:|
| Sub-queries | 7 |
| Claims que sobrevivieron | **89** |
| Dropped | **10** |
| Dropped breakdown | refuted **10** · duplicates 0 · verifierFailed 0 |
| Síntesis automática harness | **fallida** (ENAMETOOLONG) → este doc es la síntesis humana/WFD |

---

## 7. Next steps operativos (checklist)

- [ ] **B1:** Fecha en calendario con tercero + dry-run `operator` + acta
- [ ] **B2:** CI/doctor check flags + banner lab≠field; stale docs header
- [ ] **B3:** Confirmar raíz limpia; no reintroducir agent dumps
- [ ] **B4:** Plan 2º grade A (datos + scorecard)
- [ ] **B5/B10:** Tracker waits; seguir open proxies
- [ ] **B6/B7:** REQUEST_DATA chain_honest; freeze recipe
- [ ] **B8:** Validación multipass envelopes (no IoU thrash)
- [ ] **B9:** Promover/archivar scripts en siguiente hygiene pass

**Frase de cierre (industria = WFD):**

> Los productos de decisión en incendios maduran por **confianza operativa multi-incendio + datos + HITL**, no por subir 0.01 de IoU en un holdout. WFD ya tiene rails de industria; el ROI inmediato es **B1 humano** y **datos**, no otro retrain.
