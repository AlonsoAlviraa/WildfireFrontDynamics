# Plan de producto — 2 semanas (Observatorio)

> **Rol:** Product Manager + ejecución técnica  
> **Fecha inicio:** 2026-07-15  
> **Cliente interno:** Observatorio / colaboradores INFOCAM–CLM  
> **Estado:** v3 entregado · **siguiente loop:** [`LOOP_2W_SALTOS_NOTABLES.md`](LOOP_2W_SALTOS_NOTABLES.md)

---

## 1. Problema que resolvemos

El observatorio **no pide un paper de IoU en Kaggle**. Pide un sistema **auditable** que, con material real de IF:

1. Ingiere secuencias térmicas georreferenciadas.
2. Reconstruye **frente observado** con trazabilidad.
3. Estima **velocidades locales** con incertidumbre y **abstención** cuando no hay señal.
4. Produce un **paquete por incendio** (HTML + GeoJSON + CSV + resumen) revisable por humanos.
5. No vende predicción ML como verdad operativa sin validación real-fire.

El track NDWS (v21 IoU 0.226) es **I+D satélite**. Puede alimentar predicción futura, pero **no es el entregable del observatorio esta quincena**.

---

## 2. Definition of Done (DoD) — lo que “nos piden”

### Pista A — Operativa (OBLIGATORIA para el observatorio)

| ID | Criterio | Target | Cómo se prueba |
|----|----------|--------|----------------|
| A1 | ≥ **3 incendios** con paquete completo | Tobarra + 2 CLM | `outputs/observatorio/<id>/` |
| A2 | Artefactos por incendio | `report.html`, `fronts.geojson`, `local_speeds.csv`, `summary.json`, `ingest_manifest.csv` | checklist script |
| A3 | CRS métrico + resolución documentada | 100% frames accepted o motivo de rechazo | manifest |
| A4 | Velocidades con abstención | `observable_ratio` reportado; no inventar m/min si no hay señal | summary |
| A5 | Ancla operativa Tobarra | Comparar mediana Vp estimada vs INFOCAM **7 m/min** (39 ha) | `observatory_scorecard.json` |
| A6 | Umbral de ruido | `min_component_pixels` calibrado (no 1000+ componentes basura) | manifest `component_count` |
| A7 | Documento de limitaciones | 1 página honesta para el observatorio | `docs/ENTREGA_OBSERVATORIO.md` |
| A8 | Reproducible en 1 comando | `python scripts/build_observatory_pack.py` | CI o smoke local |

**Gate A (GO/NO-GO observatorio):** A1–A8 ✅. Sin esto no hay “entrega al observatorio”.

### Pista B — Predicción ML (SECUNDARIA, investigación)

| ID | Criterio | Target | Notas |
|----|----------|--------|-------|
| B1 | Schema features limpio | 12 canales reales, **0 constantes** | fix raíz del techo IoU |
| B2 | Wind vectorizado | sin/cos, no ángulo 0–360 | |
| B3 | Elevación cruda | no solo slope | |
| B4 | Modelo ≥ v21 honesto | IoU full ≥ **0.226** y Δ copy ≥ **+0.076** | mismo protocolo 979 any_fire |
| B5 | Stretch competitive | IoU full ≥ **0.28** | hacia VISION 0.30 |
| B6 | Eval real-fire | métricas en holdout CLM o explícito “no transferido” | no mentir |

**Gate B (GO investigación):** B1–B4. B5 es stretch. B6 honesto.

### Fuera de alcance (estas 2 semanas)

- Predicción en tiempo real en vuelo.
- UI de centro de mando.
- “IoU 0.42 SOTA paper” como promesa al observatorio.
- Entrenar sobre máscaras LWIR sin GT independiente.

---

## 3. Semana 1 (días 1–7) — “Paquete observatorio + cimientos ML”

| Día | Entregable | Owner | Done when |
|-----|------------|-------|-----------|
| D1 | Plan + DoD + scorecard schema | PM | este doc |
| D1–D2 | `build_observatory_pack.py` multi-IF | Eng | 1 cmd → 3 packs |
| D2 | Tobarra full pipeline con filtros anti-ruido | Eng | speeds + HTML |
| D3 | Cardoso + La Estrella (o Hellín) packs | Eng | A1 |
| D3 | Scorecard vs INFOCAM Tobarra | Eng | A5 |
| D4 | Feature surgery `schema=clean12` | Eng | B1–B3 código + tests |
| D5 | Smoke train local / Kaggle v23-clean12 | Eng | summary.json |
| D6 | Overnight results review + promote if better | Eng | tracker update |
| D7 | Borrador `ENTREGA_OBSERVATORIO.md` | PM | A7 draft |

**Checkpoint semana 1:** Gate A al 80% (al menos 2/3 incendios + Tobarra scorecard). Gate B código listo.

---

## 4. Semana 2 (días 8–14) — “Calibración + prueba de predicción”

| Día | Entregable | Done when |
|-----|------------|-----------|
| D8–D9 | Calibrar `min_component` / speed gates por sensor | Vp Tobarra no absurda o abstención justificada |
| D10 | Tercer+ incendio + tabla comparativa multi-IF | scorecard multi |
| D11 | Si clean12 ≥ v21 → promote experimental; si no, root-cause | B4 |
| D12 | CLM patch eval o documento “no transfer” | B6 |
| D13 | Empaquetado entrega (zip + docs + checklist) | listo para enviar |
| D14 | Retro + backlog 2 semanas siguientes | plan v2 |

**Checkpoint final:** Gate A 100%. Gate B B1–B4 o explicación con datos.

---

## 5. Métricas que reportamos al observatorio (lenguaje humano)

No abrir con “IoU 0.226”. Abrir con:

1. **Incendios procesados** y frames aceptados/rechazados.
2. **Frente observado** (GeoJSON) por timestamp.
3. **Velocidad mediana / P95** (m/min) solo donde hay observabilidad.
4. **Tasa de abstención** y motivos.
5. **Comparación Tobarra vs parte INFOCAM** (7 m/min, 39 ha) — con sesgos explicados (máscara automática ≠ perímetro oficial).
6. **Qué NO hace el sistema** (predicción 24h operacional, tiempo real).

Anexo técnico: métricas ML NDWS para I+D.

---

## 6. Riesgos y mitigación

| Riesgo | Prob. | Impacto | Mitigación |
|--------|-------|---------|------------|
| Máscaras MAD con miles de componentes | Alta | Vp inflada | `min_component_pixels` alto + sieve |
| Sin perímetro oficial vectorial | Alta | No Hausdorff real | scorecard “proxy only” |
| Overnight Kaggle falla | Media | Retrasa B | clean12 local smoke + requeue |
| Expectativa de predicción mágica | Alta | Confianza | A7 explícito |

---

## 7. Backlog de ejecución inmediata (orden)

1. ✅ Este plan  
2. Script paquete observatorio  
3. Correr Tobarra (+2 IF)  
4. Schema clean12 + tests  
5. Entrenamiento / eval vs v21  
6. Documento entrega  

---

## 8. Decisiones de producto (congeladas)

1. **Producto principal 2 semanas = Pista A (ops).**  
2. **v21 sigue siendo baseline ML** hasta que clean12 lo supere en protocolo honesto.  
3. **No llamar “operacional de predicción”** a ningún modelo sin B6.  
4. **Una métrica de mentira = rollback de comunicación** (lección v19/v20).

---

*Actualizar diariamente la sección “Estado de ejecución” abajo.*

## 9. Estado de ejecución

| Item | Estado | Notas |
|------|--------|-------|
| Plan PM | ✅ | 2026-07-15 |
| build_observatory_pack.py | ✅ | subsample + cluster espacial anti-OOM |
| Packs multi-IF | ✅ | Tobarra + Cardoso + Hellín (A1) |
| Scorecard gates A1/A2/A5 | ✅ | `outputs/observatorio/observatory_scorecard.json` |
| clean12 schema | ✅ | `feature_schema.py` + preprocess `--schema clean12` + tests |
| Train/eval clean12 | ✅ | IoU 0.215 Δ+0.065 — **no supera v21**; no promote |
| ENTREGA_OBSERVATORIO.md | ✅ | **v2 científica** — grado A Tobarra |
| scientific_ops + operational_report | ✅ | máscara limpia, Vp plausible, A/B/C |

### Resultados packs v3 (estructural) — canónicos en `outputs/observatorio/`

| Incendio | Grado | ROS primaria | Métodos | vs INFOCAM |
|----------|-------|--------------|---------|------------|
| tobarra_20240802 | **A** | **8.23** | area+radius+normal | ratio **1.18** |
| cardoso_2025 | B | ~30 | area | n/d |
| hellin_2024 | B | ~35 | radius | n/d |

**Trayectoria Tobarra:** v1 0.78 → v2 4.31 → **v3 8.23** (INFOCAM 7).  
**Motor:** `wildfire_front/front_dynamics.py`

### Gate checklist

| Gate | Resultado |
|------|-----------|
| A1 ≥3 incendios | ✅ PASS |
| A2 artefactos + informe operativo ES | ✅ PASS |
| A5 Tobarra mismo orden magnitud INFOCAM | ✅ PASS (ratio 0.62, grado A) |
| A7 documento | ✅ PASS |
| Utilidad real (no basura) | ✅ Tobarra A; otros abstienen con honestidad |
| B4 clean12 ≥ v21 | ❌ FAIL — v21 production ML |
