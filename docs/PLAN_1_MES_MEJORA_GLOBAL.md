# Plan 1 mes — mejora global WildfireFrontDynamics

> **Horizonte:** 4 semanas (≈ 2026-07-17 → 2026-08-17)  
> **Método:** loop-engineering — hipótesis → un cambio → métrica honesta → GO/NO_GO → siguiente  
> **Clientes:** (A) ops / CMA-INFOCAM  ·  (B) ML transfer CLM / TFG  
> **Regla de oro:** ops y ML no se mezclan en claims; un experimento = una métrica primaria  
>  
> **⚠ Plan activo (2026-08-04 post-parallel):** ver **`docs/PLAN_1_MES_POST_O1_UNLOCK.md`** y graph **v5**  
> (`.grok/graph_engineering/STATE.md`). Snapshot: `docs/PLAN_1_MES_STATUS_20260804.json`.  
> O1 multi-ancla **PASS** (Tobarra+Hellín). Track A Hellín eng **BLOCKED** (grade B/in-band; no P1 close).  
> **Next primary = human demo M3.2** (templates ready). GO_MES sigue **false** hasta P1/O5 policy satisfied — eng BLOCKED ≠ GO_MES.

---

## 0. Punto de partida (congelado 2026-07-17)

| Activo | Estado actual | Límite / nota |
|--------|---------------|---------------|
| **ML champion** | `clm_ensemble_v34` IoU **0.8963** Δ **+0.2545** growth **0.9071** | Plateau bucle 3-way (30 rondas); temps VAL |
| **ML single** | `clm_v28` IoU **0.838** Δ **+0.196** | Fallback emergencia |
| **ML research** | `ndws_v21` IoU **0.226** Δ **+0.076** | G1 KILL features/temporal |
| **Ops** | `front_dynamics_v1` + `incident_runtime_v1` | ROS multi-estimador + watch inbox |
| **CLI** | `wildfire_front` incident + predict_spread + smokes | Profesional; mejorar UX field |
| **Datos CLM** | Holdout v1 + LOFO (Cardoso/LA/Tobarra) | Pocas fuentes; techo ML |
| **Ingesta real** | Tobarra, Cardoso, LA ACOM1/2, Hellín, Retuerta, Brazatortas… | QA desigual; Retuerta flagged |
| **Outreach** | Solicitud transparencia CyL Llamas de Cabrera | Pendiente respuesta usuario |
| **Git** | main limpio post close-out v34 | Ahead of origin (push opcional) |

### Kill list (todo el mes)

- Mezclar ROS dron con IoU ML en el mismo claim de “precisión táctica”
- Tune de mix/temps en LOFO-CARDOSO/test (= holdout test)
- Añadir miembros LOFO que entrenaron con Cardoso al ensemble “GO holdout”
- G1 NDWS “revivir” sin protocolo nuevo y datos nuevos
- KMZ/KML como perímetro oficial Hausdorff
- Promesas 15/30/60 min sin validación multi-ancla
- Inventar anclas INFOCAM / Vp
- Entrenar en test o re-seleccionar checkpoint mirando test

---

## 1. Objetivos del mes (qué significa “éxito”)

### GO_MES (mínimo)

```
GO_MES =
  (O1 multi-ancla ≥2 IF con ratio ROS ∈ [0.5, 2]) AND
  (O4 brief operativo usable en ≤5 min por un no-autor) AND
  (P1 incident_runtime smoke en 2 IF reales sin crash) AND
  (M2 v34 no regresa: holdout test IoU ≥ 0.890) AND
  (E1 CI verde + smokes ops/ML en CI o script one-shot)
```

### GO_MES+ (stretch)

```
GO_MES+ = GO_MES AND
  (O2 Hausdorff oficial en ≥1 IF o abstención documentada) AND
  (O5 segundo grado A) AND
  (M5 más datos no-Cardoso → multi_if mejor o v35 honesto) AND
  (D1 CyL datos o seguimiento formal registrado)
```

### TFG / entrega

- Scorecard mes + informe 8–12 pp  
- Demo reproducible: ops pack + ML v34 en 1 comando  
- Catálogo de productos alineado (IDs v34 en docs/CLI)

---

## 2. Cinco pistas en paralelo

| ID | Pista | Prioridad | Owner mental |
|----|-------|-----------|--------------|
| **P-OPS** | Incident runtime + front dynamics + brief | **#1** | Valor campo |
| **P-DATA** | Ingesta, QA, anclas, CyL/open data | **#1** empatado | Desbloquea O y M |
| **P-ML** | Mejorar v34 sin leakage; GPU si hace falta | **#2** | Techo actual ~0.90 |
| **P-OBS** | Observatorio packs, CMA, mapas | **#2** | Entrega externa |
| **P-ENG** | CI, tests, docs, release hygiene | **#3** | Sostenibilidad |

---

## 3. Backlog por semana

### Semana 1 — Cimientos y honestidad de producto (días 1–7)

**Meta:** repo alineado con v34, ops demostrable, datos inventariados.

| # | Tarea | Pista | Entregable | Métrica GO |
|---|-------|-------|------------|------------|
| 1.1 | Push main (si se acuerda) + tag `product-v34` | ENG | tag git | remoto = local |
| 1.2 | Alinear docs/CLI: catalog ID vs `clm_ensemble_v34`, PRODUCTO_DUAL, README | ENG | docs sin v33 como “best” | `predict_spread --list-products` muestra v34 |
| 1.3 | Smoke industrial: `smoke_ops_ml.py` + `smoke_incident_runtime` en 1 IF | OPS | log verde | exit 0 |
| 1.4 | Inventario IF actualizado (máscaras, reproy, QA flags) | DATA | tabla en DATA_INTAKE_STATUS | 100% IF con estado |
| 1.5 | Completar/QA Hellín, Retuerta, Brazatortas, Polán (máscaras o flag) | DATA | artifacts/* | sin multi-kha basura |
| 1.6 | Protocolo anclas: plantilla + Tobarra + 1 candidato 2º IF | OBS | `infocam_anchors` v2 | ≥1 ancla extra documentada o BLOCKED |
| 1.7 | CyL: seguimiento solicitud Llamas de Cabrera | DATA | nota en CONTACTOS | fecha seguimiento |
| 1.8 | Tests: temperatures ensemble + no demote champion | ENG | pytest | verde |

**Kill semana 1:** no abrir nuevo bucle ML infinito sin hipótesis.

---

### Semana 2 — Ops de campo y multi-ancla (días 8–14)

**Meta:** incident_runtime usable “de verdad”; O1 avanzado.

| # | Tarea | Pista | Entregable | Métrica GO |
|---|-------|-------|------------|------------|
| 2.1 | Field kit: `run_incident.cmd` + README 1 página español | OPS | doc + cmd | operador externo sigue pasos |
| 2.2 | Doctor mejorado: CRS, timestamps monótonos, huecos, masks vs frames | OPS | códigos error claros | ≥5 fallos sintéticos detectados |
| 2.3 | Watch: resumen humano periódico + outbox GeoJSON WGS84 | OPS | HTML/GeoJSON | Leaflet abre sin error |
| 2.4 | Pack observatorio ≥5 IF sin crash (v5 o unificado) | OBS | packs | 5/5 build |
| 2.5 | Multi-ancla: segundo IF con Vp o ha oficial (O1) | OBS | scorecard anclas | ratio ∈ [0.5,2] o abstención |
| 2.6 | Brief 1 página auto (ROS, sectores, disclaimer, no ML confuso) | OPS | PDF/MD | checklist 5 min |
| 2.7 | Sector envelope: stress test multi-IF + unit tests | OPS | tests | no regresión Tobarra ratio |
| 2.8 | Hausdorff: preparar pipeline; si no hay perímetro → BLOCKED O2 | OBS | script + nota | no fake KMZ |

**Salida semana 2:** demo ops en 2 incendios + brief.

---

### Semana 3 — Datos nuevos → ML y validación (días 15–21)

**Meta:** romper techo v34 con **datos honestos**, no con re-tune.

| # | Tarea | Pista | Entregable | Métrica GO |
|---|-------|-------|------------|------------|
| 3.1 | Incorporar ≥1 fuego no-Cardoso nuevo a parches LOFO (si hay LWIR+máscara) | DATA/ML | lofo splits v2 | n_train multi_if ↑ |
| 3.2 | Reentrenar multi_if (GPU Kaggle preferible) desde v28/v34 freeze | ML | weights + meta | holdout Δ ≥ freeze o NO_PROMOTE |
| 3.3 | Solo si 3.2 mejora: recalibrar mix+temps en **VAL** → candidato v35 | ML | scorecard | IoU > 0.8963 + 1e-4 |
| 3.4 | Evaluación multi-fuente: tabla por IF (ops ROS + ML si hay parches) | ML/OBS | CSV | sin leakage claims |
| 3.5 | Open data: FIRMS/AEMET/CyL open como **contexto**, no label | DATA | catálogo + fetch | no sustituye ancla |
| 3.6 | Physics / CA / priors: solo si mejora Δ en VAL; si no → archive | ML | verdict JSON | kill si flat |
| 3.7 | Robustez: seeds multi_if ×3 en CPU/GPU, promedio honesto | ML | tabla | varianza documentada |

**Regla:** si no hay fuego nuevo usable, **no** forzar v35; pivot a ops/obs.

---

### Semana 4 — Cierre industrial y entrega (días 22–30)

**Meta:** GO_MES o explicación escrita de BLOCKED.

| # | Tarea | Pista | Entregable | Métrica GO |
|---|-------|-------|------------|------------|
| 4.1 | Scorecard mes (JSON + MD): O1–O5, M2/M5, P1, E1 | ENG | `docs/SCORECARD_MES_1.md` | checkboxes |
| 4.2 | Actualizar INDUSTRIAL_READINESS_STATUS.json | ENG | JSON | veredicto GO_MES / NO |
| 4.3 | Informe técnico 8–12 pp (ops + ML dual, límites, ética) | OBS | DOCX/MD | reutilizable CMA |
| 4.4 | One-command demo: install weights + smoke ops + smoke ML | ENG | script | < 10 min máquina limpia |
| 4.5 | CI: pytest core + catalog + incident unit + optional smokes | ENG | GitHub Actions o local make | verde |
| 4.6 | Limpieza: archivar outputs experimentales enormes; documentar gitignore | ENG | tree limpio | README actualizado |
| 4.7 | Plan mes 2 (solo si GO_MES): multi-cámara, streaming, más CCAA | — | 1 página | — |
| 4.8 | Tag release `v1.0-dual-product` si GO_MES | ENG | tag | — |

---

## 4. Detalle por pista (qué mejorar “en todas las partes”)

### P-OPS — Incident + front dynamics

| Área | Ahora | En 1 mes |
|------|-------|----------|
| Runtime | watch/doctor/update existe | Field kit + errores accionables |
| ROS | multi-estimador Tobarra A | ≥2 IF con ancla o abstención clara |
| Envelope | 15/30/60 | Validación honest o disclaimer fuerte |
| Productos | GeoJSON/HTML | Brief 1p + outbox estable |
| QA | Retuerta flag | Flags automáticos área/FOV |

### P-DATA — Ingesta y gobernanza

| Área | Ahora | En 1 mes |
|------|-------|----------|
| Inventario | parcialmente desactualizado | tabla viva por IF |
| Máscaras | muchas listas | 100% con QA pass/fail |
| Anclas | Tobarra dominante | 2ª ancla o BLOCKED O1 |
| Externos | CyL solicitud, FIRMS script | seguimiento + 1 ingest open data |
| Provenance | docs | PROVENANCE por pack generado |

### P-ML — Ensemble y honestidad

| Área | Ahora | En 1 mes |
|------|-------|----------|
| Champion | v34 0.8963 | Mantener; v35 solo con datos/GPU |
| Loop 3-way | cerrado plateau | Usar on-demand, no ∞ |
| Leakage guards | en código | tests de regresión |
| NDWS G1 | KILL | Queda KILL salvo plan nuevo |
| Inferencia | temps en manifest | CLI expone temps; eval one-shot |

### P-OBS — Observatorio / CMA

| Área | Ahora | En 1 mes |
|------|-------|----------|
| Packs | v1–v5 | Un pipeline canónico |
| Informe CMA | v1.0 | v1.1 + feedback loop |
| Mapas | Leaflet WGS84 | Multi-IF index |
| Outreach | contactos CSV | 2 follow-ups registrados |

### P-ENG — Ingeniería

| Área | Ahora | En 1 mes |
|------|-------|----------|
| Tests | 32 py tests | +incident +temps +leakage |
| CI | limitado | make test + smokes documentados |
| IDs producto | catalog `clm_ensemble_v30` vs manifest v34 | unificar naming |
| Release | commits locales | tag + opcional push |

---

## 5. Calendario tipo (ritmo semanal)

| Día | Ritual |
|-----|--------|
| Lun | Priorizar 3 tareas de la semana; 1 hipótesis ML máximo |
| Mar–Jue | Implementar + métrica |
| Vie | Scorecard parcial, commit, actualizar PLAN checkboxes |
| Dom | Revisión kill list y riesgos datos |

**Capacidad sugerida (1 persona full-stack):**

- 40% OPS+DATA  
- 25% OBS/entrega  
- 20% ML (solo si datos)  
- 15% ENG/docs  

---

## 6. Métricas y gates (recordatorio)

| Gate | Definición | Estado inicio mes |
|------|------------|-------------------|
| G0 NDWS | v21 baseline locked | GO |
| G1 NDWS | IoU≥0.25 Δ≥0.09 | **KILL** features/temporal |
| G2 CLM single | holdout Δ>0 | GO v28 |
| G2e ensemble | holdout + honest mix/temps | **GO v34** |
| O1 multi-ancla | ≥2 IF | **PASS** (Tobarra+Hellín; 2026-08-03) |
| O2 Hausdorff oficial | perímetro real | BLOCKED |
| O3 temporal | ventanas estables | PARTIAL Tobarra |
| O4 producto decisor | brief 5 min | PARTIAL → eng yes (field kit) |
| O5 2º grado A | segundo IF | OPEN (Hellín grade B; eng BLOCKED) |
| P1 incident | 2 IF smoke / 2º grade A | PARTIAL / eng BLOCKED — **no** GO_MES |

---

## 7. Riesgos y mitigaciones

| Riesgo | Impacto | Mitigación |
|--------|---------|------------|
| Sin 2ª ancla oficial | No GO_MES O1 | Documentar BLOCKED + solicitud datos |
| CPU-only ML | No v35 | Kaggle GPU 1–2 jobs/semana |
| Plateau ML | Tiempo perdido | Tope 2 días ML/semana sin datos nuevos |
| Scope creep docs | Menos código | PLAN es la cola; no nuevos mega-docs |
| Leakage sutil | Claims falsos | tests + review de members ensemble |

---

## 8. Definición de “mes terminado”

Checklist cierre (2026-08-17):

- [ ] Scorecard mes relleno  
- [ ] v34 (o v35) en catalog + CLI  
- [ ] Incident demo 2 IF  
- [ ] O1 GO o BLOCKED escrito  
- [ ] Informe 8–12 pp  
- [ ] Tests verdes  
- [ ] Tag release o decisión explícita de no taggear  
- [ ] Plan mes 2 de 1 página  

---

## 9. Primeras 72 horas (acción inmediata)

1. ~~Unificar naming producto **v34** en catalog/docs/CLI.~~ **HECHO**  
2. ~~Correr smokes / demo dual.~~ **Scripts listos** (`demo_dual_product.py`)  
3. ~~Actualizar inventario IF + flags QA.~~ **HECHO** (`DATA_INTAKE_STATUS.md`)  
4. ~~Registrar follow-up CyL.~~ **HECHO** (CONTACTOS)  
5. ~~Elegir IF candidato 2ª ancla.~~ **Cardoso** — falta Vp/ha externo  

## 10. Progreso loop-engineering (2026-07-17)

Ver `docs/SCORECARD_MES_1.md`. Ingeniería automatizable adelantada (semanas 1–2 eng + cierre parcial).  
**GO_MES bloqueado por P1/O5** (2º IF grade A usable; Hellín eng BLOCKED documentado — no es GO_MES). O1 ya **PASS**. O2 nacional sigue BLOCKED. Ver plan activo `PLAN_1_MES_POST_O1_UNLOCK.md`.

---

*Documento vivo. Actualizar checkboxes cada viernes. No sustituye EXPERIMENT_TRACKER (ML) ni scorecards de gates; los orquesta.*
