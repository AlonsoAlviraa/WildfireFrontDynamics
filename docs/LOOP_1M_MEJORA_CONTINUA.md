# Loop de 1 mes — mejora continua — mejora continua WildfireFrontDynamics

> **Horizonte:** 4 semanas (~2026-07-16 → 2026-08-13)  
> **Método:** loop-engineering (hipótesis → un cambio → métrica honesta → go/no-go → siguiente)  
> **Cliente dual:** (A) CMA / Observatorio-INFOCAM  ·  (B) I+D ML TFG  
> **Regla de oro:** un experimento = una hipótesis = una métrica primaria. Prohibido re-tunear ruido.

---

## 0. Punto de partida (congelado)

| Activo | Estado | Límite |
|--------|--------|--------|
| Producto dual | `ndws_v21` + `clm_v28` READY | No mezclar con ROS ops |
| Ops motor | `front_dynamics_v1` multi-estimador | 5 packs IF |
| Tobarra | ROS **5.71** m/min vs Vp **7** (ratio **0.82**), grado **A** | 1 sola ancla |
| O1 / O5 | PARTIAL / NO_GO | Falta Vp/ha externos |
| O2 | PROXY ok; official **BLOCKED** | Sin perímetro vectorial |
| O3 | Multi-ventana Tobarra (2/3–3/3 según corrida) | Área no monótona |
| G0 | v21 IoU **0.226** Δ **+0.076** | Production NDWS |
| G1 | **OPEN** — features cerradas (v25/v26 NO_PROMOTE) | v27 T=2 RUNNING |
| G2 | **GO** clm_v28 IoU **0.838** Δ **+0.196** | Holdout test only |
| CMA | Informe v1.0 + correo listo | Pendiente respuesta datos |

**Kill list (todo el mes):** filter-only · pos_weight-only · EMA/focal sin señal · train-CLM como “transfer GO” · KMZ como perímetro · inventar anclas · promocionar NDWS sin G1 · promesa táctica 15/30/60 sin validación.

---

## 1. Qué cuenta como salto (mes)

### Pista O — Observatorio (prioridad #1)

| ID | Salto | Métrica de verdad | Target mes | Kill si… |
|----|-------|-------------------|------------|----------|
| **O1** | Multi-ancla | ≥2 IF confirmed + ratio ROS ∈ [0.5, 2] | **2/2** mínimo; stretch 3 | Solo Tobarra |
| **O2** | Hausdorff oficial | P50 o mean dist vs perímetro en ≥1 IF | P50 < **50 m** o abstención justificada | Fake con KMZ |
| **O3** | Estabilidad temporal | 3 ventanas Tobarra en banda | **3/3** o 2/3 + 1 abstención documentada | Media única “afortunada” |
| **O4** | Producto decisor | brief 1p + main_front + timeline + informe CMA feedback | Checklist CMA 5 min | Solo JSON técnico |
| **O5** | 2º grado A | Segundo IF con ancla + criterios A | ≥ **2** grado A | Todo en B |

### Pista M — ML (prioridad #2; no bloquea O)

| ID | Salto | Métrica | Target mes | Kill si… |
|----|-------|---------|------------|----------|
| **M1 / G1** | Superar v21 | IoU full + Δ copy (979 any_fire) | IoU ≥ **0.25** y Δ ≥ **+0.09** | < v21 full |
| **M2 / G2** | Transfer | Ya GO clm_v28 | Mantener; mejorar holdout o multi-fire | Cherry-pick train |
| **M3** | Stretch | IoU ≥ 0.28 | opcional | — |
| **M4** | Producto dual usable | CLI + docs + 1 demo reproducible | smoke CLM + NDWS en CI | Manifest roto |

### Gate de mes

```
GO_MES     = (O1 ∧ O4) ∨ (O3 ∧ O4 ∧ O1_partial)   y  Tobarra ratio ∈ [0.4, 2.5]
GO_MES+    = GO_MES ∧ O2 ∧ O5
ML_MES     = M1 resuelto (GO o NO-GO documentado) ∧ M2 no regresa
TFG_CIERRE = informe CMA v1.1 + scorecard mes + memoria técnica 8–12 pp
```

---

## 2. Arquitectura del loop (semanal)

```
Lunes        Revisión gates + scorecard (priority_stack + anchors + ML)
Mar–Jue      1–2 experimentos (O o M, no ambos ambiciosos el mismo día)
Viernes      Cierre: métricas, EXPERIMENT_TRACKER, commit, mensaje CMA si aplica
Continuo     Kaggle async; no bloquear O por GPU
```

**Cadencia de scorecard:**  
`python scripts/score_infocam_anchors.py`  
`python scripts/run_multi_if_hausdorff.py`  
`python scripts/finalize_priority_stack.py`  
Actualizar `docs/EXPERIMENT_TRACKER.md` en cada cierre de kernel.

**Artefacto vivo del mes:** `docs/LOOP_1M_MEJORA_CONTINUA.md` (crear en implementación; este plan es la especificación).

---

## 3. Semana a semana

### Semana 1 (D0–D7) — Cerrar loops abiertos + datos

**Objetivo:** no dejar colgados v27 ni la comunicación CMA; endurecer baseline.

| Día | Pista | Trabajo | Salida |
|-----|-------|---------|--------|
| 1 | M | Evaluar **v27 T=2** (COMPLETE → métricas vs G1/v21) | `docs/V27_TEMPORAL_VERDICT.json` GO/NO_PROMOTE |
| 1–2 | O | Enviar correo + informe CMA si no enviado | hilo con Pablo |
| 2–3 | M | Si v27 señal: lanzar **v27b T=3**; si no: **cerrar temporal rail** para G1 | kernel o kill doc |
| 3–4 | O | Inventario 8 IF: Brazatortas, Polán, ACOM2 — packs faltantes | packs o “skip justificado” |
| 4–5 | O | QA Retuerta (área anómala ~4200 ha): root-cause máscara/FOV | issue + fix o flag “no usable” |
| 5–7 | M/O | CI smoke dual product + tests Hausdorff/product_catalog | verde en main |
| 7 | — | Scorecard S1 | GO parcial S1 |

**Hipótesis S1:**  
- **H-T2:** T=2 aporta señal temporal real vs T=1.  
- **H-RET:** Retuerta falla por pipeline de máscara, no por motor ROS.

**No hacer S1:** nuevos schemas physics*; reentrenar CLM sin holdout nuevo.

---

### Semana 2 (D8–D14) — Validación multi-IF (si hay datos) / ops robustez (si no)

**Rama A — llegan anclas o perímetro de CMA**

| Trabajo | Gate |
|---------|------|
| Rellenar `data/infocam_anchors.json` (confirmed) | — |
| Re-score O1/O5 | O1 GO si ≥2 en banda |
| `--mode official` Hausdorff 1 IF | O2 GO o REVIEW |
| Re-pack IF afectados sin retocar estimadores | O5 camino A |

**Rama B — sin datos externos (techo actual)**

| Trabajo | Gate |
|---------|------|
| H5 segmentación: **un** cambio (Otsu ROI o percentil en blob principal) en Tobarra | ratio se mantiene ∈ [0.5,2] y `area_non_monotonic` ↓ |
| O3 re-correr 3 ventanas con máscara nueva | O3 GO |
| Export operador unificado: `main_front.gpkg` + PDF/HTML 1 página | O4 |
| Documentar techo O1/O2 blocked en informe v1.1 | honest ceiling |

**ML S2 (solo si sobra GPU y S1 no cerró G1):**  
- Si T=2/3 NO_PROMOTE → **parar G1** y pivotar a **transfer multi-fire**: holdout por evento (leave-one-fire-out) en CLM patches.  
- Métrica: mean Δ copy en fires held-out ≥ 0.

**Hipótesis S2:**  
- **H1:** el motor ya basta; faltan anclas.  
- **H5:** máscara monótona mejora ROS multi-IF sin inventar anclas.

---

### Semana 3 (D15–D21) — Producto + transfer serio

| Prioridad | Trabajo | Métrica |
|-----------|---------|---------|
| 1 | Protocolo **leave-one-fire-out** CLM (Cardoso / Hellín / Estrella / Tobarra patches) | tabla IoU/Δ por fire |
| 2 | Si G1 aún vivo: un solo experimento residual (p.ej. T=2 + legacy17 ya hecho; no apilar) | G1 o kill final G1 |
| 3 | Demo reproducible 15 min: `install_dual_weights` → predict CLM test 50 → observatorio pack Tobarra | checklist |
| 4 | Integrar feedback CMA en informe v1.1 (formato ops) | O4 |
| 5 | Hardening: tests métricas ROS sintéticas + Hausdorff official con perímetro sintético | coverage |

**Hipótesis S3:**  
- **H-LOFO:** clm_v28 generaliza a fires no vistos en fine-tune (o no: documentar fallo).  
- **H-PROD:** dual product + ops se demuestran sin notebook.

**No hacer S3:** mega-architecture LSTM/A3C; datasets satélite nuevos sin contrato de ingesta.

---

### Semana 4 (D22–D28) — Cierre de mes y entrega

| Trabajo | Entregable |
|---------|------------|
| Scorecard final O1–O5 + M1–M4 | `outputs/observatorio/loop_1m_scorecard.json` |
| Memoria técnica 8–12 pp (método, números, límites) | `docs/MEMORIA_LOOP_1M.md` o DOCX |
| Informe CMA v1.1 (si hay datos nuevos) o “sin cambios de ancla” | `docs/entrega_cma/` |
| Decisiones de promote: NDWS / CLM / ops tags | manifests actualizados solo si GO |
| Roadmap post-mes (TFG defense / ops pilot) | 1 página |
| Limpieza repo: no basura kaggle, node_modules ignorado | main limpio |

**Criterio de éxito del mes (honesto):**

| Nivel | Condición |
|-------|-----------|
| **Mínimo** | M1 cerrado (GO o NO-GO) + O4 sólido + scorecard + CMA al día |
| **Objetivo** | Mínimo + O1 (≥2 anclas) o O3 3/3 + LOFO transfer documentado |
| **Excelente** | Objetivo + O2 + O5 (2× grado A) |

---

## 4. Cola de experimentos ML (orden estricto)

```
v27 T=2  ──complete──►  (GO G1?) ──yes──► promote candidate / freeze G1
                │
                no
                ▼
         v27b T=3 (solo si T=2 ≥ v21 en Δ o IoU)
                │
                no / T=2 peor
                ▼
         KILL G1 temporal+features
                ▼
         Transfer LOFO CLM (M2+)
                ▼
         (opcional) physics15 solo como features de ops transfer, no NDWS promote
```

**Presupuesto Kaggle:** ≤ **4** kernels GPU/mes tras v27 (T=3, LOFO×2, 1 comodín).  
Cada kernel: `single_change` en metadata + fila en `experiment_queue_features.json`.

---

## 5. Dependencias externas (críticas)

| Necesidad | Desbloquea | Owner | Fallback si no llega |
|-----------|------------|-------|----------------------|
| Vp/ha 2–3 IF (Cardoso, Hellín, Estrella) | O1, O5 | CMA / INFOCAM | O1 PARTIAL permanente; memoria con techo |
| 1 perímetro vectorial | O2 | CMA / centro operativo | O2 BLOCKED; solo proxy temporal |
| Feedback formato informe | O4 | Pablo / Cma | mantener DOCX v1.0 |
| Cardoso 10 días completo | multi-fase ROS | Pablo | trabajar parcial |

**No pedir de nuevo:** acceso Drive/BD (ya rechazado).  
**Canal:** correo ya redactado (`docs/correo_pablo_cma_avances.md` + informe).

---

## 6. Trabajo de ingeniería (código) por sprint

### PR / commits orientativos (DAG)

```
PR1  [S1] v27 verdict + tracker + kill/queue T=3
PR2  [S1] packs IF pendientes + Retuerta QA flag
PR3  [S2] anchors ingest path (CSV→infocam_anchors) + re-score CLI
PR4  [S2] official Hausdorff demo + synthetic GT test
PR5  [S2] segmentation single-change experiment (H5) behind flag
PR6  [S3] leave-one-fire-out CLM protocol + report
PR7  [S3] operator export gpkg + 1-page brief polish
PR8  [S4] loop_1m_scorecard + MEMORIA + product freeze
```

**Módulos tocados (esperados):**

- `scripts/score_infocam_anchors.py`, `eval_perimeter_hausdorff.py`, `build_observatory_pack.py`
- `wildfire_front/` front dynamics / mask (solo S2 H5)
- `kaggle_job/run_unet_training_v27*.py`, `kaggle_common.py`
- `wildfire_front/ml/` holdout LOFO
- `docs/entrega_cma/`, `docs/EXPERIMENT_TRACKER.md`, `models/catalog.json` (solo promote)

---

## 7. Métricas y dashboards (sin vanity)

| Scorecard | Comando / path |
|-----------|----------------|
| Anclas O1/O5 | `scripts/score_infocam_anchors.py` → `outputs/observatorio/anchor_scorecard.json` |
| Hausdorff O2 | `scripts/run_multi_if_hausdorff.py` + official cuando haya GT |
| Priority stack | `scripts/finalize_priority_stack.py` |
| ML | `docs/EXPERIMENT_TRACKER.md` + `V2x_*_VERDICT.json` |
| Mes | `outputs/observatorio/loop_1m_scorecard.json` (crear S4) |

**Tobarra no se toca como “mejorar el número”:** se re-evalúa; si ratio sale de [0.4, 2.5] → regresión blocker.

---

## 8. Riesgos y mitigaciones

| Riesgo | Prob. | Impacto | Mitigación |
|--------|-------|---------|------------|
| CMA no responde en 4 sem | alta | O1/O2/O5 techo | Rama B S2–S4; TFG con límites explícitos |
| v27/T=3 fallan G1 | alta | sin salto NDWS | Kill G1; valor en CLM transfer + ops |
| Overfitting CLM holdout v1 | media | G2 frágil | LOFO S3 |
| Scope creep “predicción táctica” | media | credibilidad CMA | Mantener mensaje informe: dinámica observada |
| Kaggle cuotas / fallos preprocess | media | retrasos M | Fail-fast ya en kaggle_common; smoke local |

---

## 9. Roles de tiempo (capacidad realista)

| Bloque | % mes | Notas |
|--------|-------|-------|
| Observatorio / datos / CMA | **45%** | Prioridad |
| ML G1 + transfer | **30%** | Async Kaggle |
| Producto / docs / tests / TFG | **20%** | |
| Buffer / imprevistos | **5%** | |

---

## 10. Definition of Done del mes

- [ ] G1 resuelto por escrito (promote o kill features+temporal)
- [ ] G2 no regresado; LOFO report existe aunque sea NO-GO
- [ ] Dual product smoke en CI o script de regresión
- [ ] Scorecard O1–O5 actualizado; techos honestos
- [ ] Informe CMA v1.0 enviado; v1.1 si hay datos
- [ ] `docs/LOOP_1M_MEJORA_CONTINUA.md` + scorecard final
- [ ] main limpio; experiment tracker al día
- [ ] 1 demo 15 min documentada (ops Tobarra + predict CLM)

---

## 11. Enfoque de implementación (cuando se apruebe el plan)

1. **Crear** `docs/LOOP_1M_MEJORA_CONTINUA.md` copiando este plan (versión repo).  
2. **S1 inmediata:** bajar v27, veredicto, actualizar queue.  
3. **No implementar H5 ni LOFO hasta** cerrar S1 (evitar paralelismo confuso).  
4. **Cada PR** con métrica en descripción y fila en tracker.  
5. **Viernes** scorecard + commit; no acumular 2 semanas de JSON sin commit.

### Alternativas consideradas

| Enfoque | Pros | Contras | Decisión |
|---------|------|---------|----------|
| Solo ML 1 mes G1 | GPU foco | Ignora valor CMA/TFG ops | Rechazado |
| Solo observatorio | O1–O5 | Pierde rail ML ya en vuelo | Rechazado |
| **Dual: O primario + M async** | realista, datos-aware | más gestión | **Elegido** |
| Big-bang modelo nuevo | “innovación” | alto riesgo, 0 entrega | Rechazado |

---

## 12. Pregunta abierta (no bloquea el plan)

Si CMA responde con anclas **a mitad de S2**, se cancela H5 no empezada y se prioriza O1/O2.  
Si responde en S4, se documenta para post-mes sin forzar GO_MES+ artificial.

---

**Estado del plan:** listo para aprobación.  
**Siguiente paso tras approve:** implementar S1 (v27 verdict + doc loop 1M + scorecard scaffold) sin tocar estimadores ROS.


---

## Progress log (vivo)

| Fecha | Semana | Evento | Resultado |
|-------|--------|--------|-----------|
| 2026-07-16 | S1 D0 | Plan aprobado; doc repo + scorecard scaffold | en curso |
| 2026-07-16 | S1 D0 | v27 T=2 | RUNNING (pendiente verdict) |

## Scorecard mes (actualizar con scripts/finalize_loop_1m_scorecard.py)

Ver outputs/observatorio/loop_1m_scorecard.json (local) y resumen en EXPERIMENT_TRACKER.

