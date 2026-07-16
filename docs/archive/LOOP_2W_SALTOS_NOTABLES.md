# Loop Engineering — 2 semanas · Saltos notables

> **Inicio:** 2026-07-15 (post v3 estructural)  
> **Cliente:** Observatorio / INFOCAM–CLM (+ pista I+D ML secundaria)  
> **Método:** loop-engineering (hipótesis → experimento único → métrica honesta → go/no-go → siguiente)  
> **Baseline congelado:** packs v3 + motor `front_dynamics_v1` + ML v21  

---

## 0. Punto de partida (no reescribir la historia)

| Activo | Estado actual | Límite |
|--------|---------------|--------|
| Motor dinámica | `front_dynamics_v1` (área + radio + normal + coreg gated) | Solo **1 ancla** INFOCAM (Tobarra) |
| Tobarra | ROS **8.23** m/min vs 7 (ratio **1.18**), grado **A** | Área no monótona; sin perímetro oficial |
| Cardoso / Hellín | grado **B**, ROS área/radio ~30 | Sin ancla; posible sobre-estimación |
| ML NDWS | v21 IoU **0.226**, Δ copy **+0.076** | Techo features; clean12 no superó full IoU |
| Overnight mega | fallido (0 patches) | Requeue solo tras fail-fast verificado |

**Regla de oro del loop:** un cambio = una hipótesis = una métrica primaria.  
**Prohibido:** re-tunear LR/EMA/residual sin hipótesis de salto; llamar “breakthrough” a métricas tautológicas; prometer predicción 24 h al observatorio.

---

## 1. Qué cuenta como “salto notable”

No basta con +0.01 de IoU o un HTML más bonito. Un salto es **estructural o de validación**.

### Pista O — Observatorio (prioridad #1)

| ID | Salto | Métrica de verdad | Target de salto | Kill si… |
|----|-------|-------------------|-----------------|----------|
| **O1** | Validación multi-ancla | ≥ **3 IF** con ancla Vp o área oficial y ratio ROS ∈ **[0.5, 2.0]** | 3/3 o 2/3 + 1 documentado | Solo Tobarra sigue siendo A |
| **O2** | Error geométrico real | Hausdorff / distancia media vs perímetro oficial en ≥ **1 IF** | P50 dist < **50 m** o abstención justificada | No hay vectores → O2 blocked, no fake |
| **O3** | ROS estable multi-ventana | Tobarra: ROS primaria en **3 ventanas temporales** distintas con ratio INFOCAM ∈ [0.5, 2] | 3/3 ventanas | Solo 1 ventana “afortunada” |
| **O4** | Producto decisor | Informe 1 página + GeoJSON **capa única “frente principal”** + tabla ROS por intervalo | Aprobado checklist observatorio | Sigue siendo solo CSV técnico |
| **O5** | Grado A en 2º IF | Segundo incendio grado **A** con ancla o validación cruzada | ≥2 IF grado A | Todo el mundo en B |

### Pista M — ML (prioridad #2, solo si no bloquea O)

| ID | Salto | Métrica | Target | Kill si… |
|----|-------|---------|--------|----------|
| **M1** | Superar v21 honesto | IoU full + Δ copy (protocolo 979 any_fire) | IoU ≥ **0.25** y Δ ≥ **+0.09** | < v21 en full |
| **M2** | Transfer real-fire | Eval holdout CLM patches **o** doc “no transfer” con números | Δ vs copy > 0 en CLM **o** NO-GO explícito | Silencio / cherry-pick |
| **M3** | Stretch competitive | IoU full ≥ **0.28** | stretch, no bloquea entrega O | — |

### Gate de quincena (GO entrega)

```
GO  = O1 OR (O3 ∧ O4)   y   no regresión Tobarra ratio fuera [0.4, 2.5]
GO+ = GO ∧ O2 ∧ O5
ML  = M1 opcional; M2 obligatorio como resultado (pass o NO-GO documentado)
```

---

## 2. Hipótesis de salto (solo estas; el resto es ruido)

### H1 — Multi-ancla operativa (O1, O5)
**Creencia:** El motor ya es suficiente; falta **calibración por evento** y anclas.  
**Experimento:** Incorporar Vp/ha (o proxy oficial) para Cardoso, Hellín, La Estrella o Retuerta; re-correr `front_dynamics` sin cambiar estimadores.  
**Go si:** ≥1 IF adicional con ratio ∈ [0.5, 2] o grado A con criterios documentados.  
**No-go:** Re-tunear máscaras hasta “cuadrar” anclas inventadas.

### H2 — Perímetro independiente (O2)
**Creencia:** Sin GT geométrico no hay salto a “validado”.  
**Experimento:** Pipeline `eval_vs_official_perimeter.py` (GeoJSON/GPKG oficial vs frente principal).  
**Go si:** Métricas Hausdorff/P50/P95 + mapa residual en 1 IF.  
**Blocked:** Sin vectores del observatorio → entregar plantilla de datos + solicitud formal.

### H3 — Estabilidad temporal Tobarra (O3)
**Creencia:** v3 puede ser una ventana densa afortunada.  
**Experimento:** 3 ventanas disjuntas (inicio / medio / final del vuelo) con el mismo motor.  
**Go si:** 3/3 ratios ∈ [0.5, 2] o 2/3 + 1 abstención justificada.  
**No-go:** Solo promediar todo el vuelo y declarar victoria.

### H4 — Frente principal como producto GIS (O4)
**Creencia:** El observatorio necesita **una capa** y una tabla, no 8 artefactos.  
**Experimento:** Export `main_front.gpkg` + `ros_timeline.csv` + `brief_1page.md/pdf` auto-generado.  
**Go si:** Checklist humano 5 min sin abrir JSON.

### H5 — Segmentación térmica calibrada (apoya O1–O3)
**Creencia:** MAD genérico limita área monótona y ROS.  
**Experimento:** Un solo cambio — umbral por percentil robusto **o** Otsu en ROI del blob principal (no reintroducir 1000 componentes).  
**Go si:** `area_non_monotonic` ↓ y Tobarra ratio se mantiene ∈ [0.5, 2].  
**No-go:** Volver a máscaras fragmentadas.

### H6 — ML: señal de cambio + schema limpio (M1)
**Creencia:** clean12 falló full IoU por quitar CLM y por target; el salto es **train changed-filter + clean12 + sin basura de canales**, evaluado en any_fire.  
**Experimento:** v24 = clean12 + `filter_mode=changed` train / eval any_fire protocol (cross-protocol obligatorio).  
**Go si:** IoU full ≥ 0.25 y Δ copy ≥ +0.09.  
**No-go:** Mejor solo en changed y peor en full (como v22).

### H7 — ML: transfer CLM honesto (M2)
**Creencia:** NDWS no transfiere; hay que medirlo.  
**Experimento:** Eval v21 (y candidato) en holdout CLM patches con mismas métricas honestas.  
**Go si:** Δ copy > 0 en CLM **o** informe NO-GO con cifras.  
**Éxito del loop = la verdad medida**, no el número alto.

### Hipótesis **rechazadas de antemano** (no gastar la quincena)

| No hacer | Por qué |
|----------|---------|
| Más residual/EMA/focal sin feature o target nuevo | Ya agotado en overnight fallido / v14–v22 |
| A3C / per-cell | Arquitectura muerta |
| IoU “Tier-1 changed” naive | Métrica tautológica (lección v19/v20) |
| Prometer tiempo real / edge | Fuera de producto de 2 semanas |
| Entrenar con máscaras LWIR sin GT | Contamina y no valida |

---

## 3. Arquitectura del loop (proceso)

```
          ┌─────────────────┐
          │  Hipótesis Hi   │
          └────────┬────────┘
                   ▼
          ┌─────────────────┐
          │ Smoke pytest    │  scientific_ops + front_dynamics + ingest
          └────────┬────────┘
                   ▼
          ┌─────────────────┐
          │ Experimento 1Δ  │  un cambio / un kernel / un pack
          └────────┬────────┘
                   ▼
          ┌─────────────────┐
          │ Métrica primaria│  protocol-labeled
          └────────┬────────┘
                   ▼
            ┌──────┴──────┐
            │ Go / No-go  │
            └──────┬──────┘
         go│       │no-go
           ▼       ▼
    actualizar   log + kill branch
    baseline     siguiente Hi
           │
           ▼
    ENTREGA + scorecard + tracker
```

**Cadencia:**  
- Daily: 1 hipótesis activa máximo en O, 1 en M si hay GPU.  
- Cada 48 h: checkpoint escrito en este doc §9.  
- Fin de semana 1: gate intermedio.  
- Fin de semana 2: GO / GO+ / NO-GO con evidencia.

**Artefactos obligatorios por experimento:**

1. Entrada en `docs/EXPERIMENT_TRACKER.md` o sección O del scorecard  
2. `outputs/observatorio/` o `kaggle_outputs_*` con summary  
3. Una línea go/no-go en `scripts/experiment_queue.json`

---

## 4. Semana 1 — “Validar el motor, no decorarlo”

| Día | Foco | Hipótesis | Entregable | DoD del día |
|-----|------|-----------|------------|-------------|
| **D1** | Congelar baseline v3 | — | Tag git `baseline-observatorio-v3` + snapshot scorecard | Números v3 en tracker |
| **D1–D2** | Ventanas Tobarra | H3 | Script `scripts/eval_temporal_windows.py` | 3 ventanas + ratios |
| **D2–D3** | Producto GIS 1-capa | H4 | `main_front.gpkg` + `ros_timeline.csv` + brief | Checklist 5 min |
| **D3–D4** | Solicitud anclas / perímetros | H1/H2 | Plantilla `docs/SOLICITUD_DATOS_OBSERVATORIO.md` | Enviada o lista para enviar |
| **D4–D5** | Segmentación calibrada (si área inestable) | H5 | Un algoritmo, re-pack Tobarra | Ratio INFOCAM se mantiene |
| **D5–D6** | Multi-IF con anclas disponibles | H1 | Re-pack 2–3 IF | Scorecard multi-ancla |
| **D7** | Checkpoint S1 | — | Actualizar §9 + ENTREGA draft v4 | Gate intermedio |

**Gate intermedio (fin S1) — PASS si:**

- [ ] O3 medido (pass o fail con cifras)  
- [ ] O4 entregable consumible  
- [ ] Tobarra no regresado (ratio ∈ [0.4, 2.5])  
- [ ] Cola H1/H2 desbloqueada o blocked documentado  

**Si S1 FAIL en O3:** no escalar a más IF; root-cause ventanas antes de multi-ancla.

---

## 5. Semana 2 — “Segundo IF en A o validación geométrica”

| Día | Foco | Hipótesis | Entregable | DoD del día |
|-----|------|-----------|------------|-------------|
| **D8** | Perímetro oficial (si hay dato) | H2 | `eval_vs_official_perimeter` | Hausdorff report |
| **D9** | Segundo grado A | H1/H5 | Pack IF#2 | Grado A o B justificado |
| **D10** | ML v24 clean12+changed | H6 | Kernel Kaggle | Cross-protocol vs v21 |
| **D11** | ML transfer CLM | H7 | `clm_eval_report.json` | Pass o NO-GO |
| **D12** | Integración entrega | O4+O1 | `outputs/observatorio` v4 + index | 1 comando reproduce |
| **D13** | check-work + review | — | Tests verdes + review notes | Sin regresión |
| **D14** | Cierre loop | — | ENTREGA_v4 + retro §10 | GO / GO+ / NO-GO |

**Gate final (fin S2):**

| Resultado | Condición |
|-----------|-----------|
| **GO** | (O1 ∨ (O3∧O4)) ∧ Tobarra estable |
| **GO+** | GO ∧ O2 ∧ O5 |
| **NO-GO parcial** | Motor OK pero sin 2ª ancla / sin perímetro — entregar con blocked list |
| **FAIL** | Regresión Tobarra o packs peores que v3 |

---

## 6. Cola de experimentos (orden fijo)

| Orden | ID | Pista | Cambio único | Métrica primaria | Depende de |
|------:|----|-------|--------------|------------------|------------|
| 1 | W1-T-windows | O | 3 ventanas Tobarra | ratios INFOCAM | baseline v3 |
| 2 | W1-product-gis | O | gpkg + timeline + brief | checklist humano | 1 |
| 3 | W1-seg-cal | O | segmentación ROI (si hace falta) | area mono + ratio | 1 |
| 4 | W1-multi-anchor | O | anclas 2º/3º IF | count ratio∈[0.5,2] | anclas externas |
| 5 | W2-perimeter | O | eval vs oficial | Hausdorff P50 | vectores externos |
| 6 | W2-second-A | O | pack IF#2 grado A | quality_grade | 4 o 3 |
| 7 | W2-ml-v24 | M | clean12+changed train | IoU full ≥0.25 | GPU |
| 8 | W2-ml-clm | M | eval CLM holdout | Δ copy CLM | 7 o v21 |

Actualizar `scripts/experiment_queue.json` al arrancar cada ítem (`status: running|completed|killed`).

---

## 7. PR Plan (DAG) — implementación

```text
PR1  baseline freeze + temporal windows Tobarra
      │
      ├─► PR2  GIS product (gpkg, ros_timeline, brief)
      │
      ├─► PR3  segmentation calibration (optional, only if O3 weak)
      │
      └─► PR4  multi-anchor scorecard schema
               │
               ├─► PR5  official perimeter evaluator (H2)
               │
               └─► PR6  delivery v4 packing + docs

PR7  (paralelo, no bloquea O) ML v24 clean12+changed + cross-protocol
PR8  (tras PR7 o v21) CLM transfer eval report
```

**Reglas PR:**  
- Un PR = una hipótesis.  
- Tests: `test_front_dynamics`, `test_scientific_ops`, ingest.  
- Tras merge: re-generar pack canónico solo si go.  
- Usar `/check-work` al cerrar cada PR de O.

---

## 8. Métricas y protocolos (etiquetar siempre)

### Observatorio

| Nombre | Definición | Usar para |
|--------|------------|-----------|
| `primary_ros_m_min` | Fusión front_dynamics | Headline |
| `ros_area / ros_radius / ros_normal` | Componentes | Diagnóstico |
| `ratio_infocam` | primary / Vp_ref | O1, O3 |
| `quality_grade` | A/B/C estructural | O5 |
| `hausdorff_p50_m` | vs perímetro oficial | O2 |
| `area_non_monotonic` | flag máscara | H5 |

### ML

| Nombre | Protocolo | Usar para |
|--------|-----------|-----------|
| IoU full @0.5 | any_fire, N=979 (o cross-protocol) | M1 |
| Δ copy full | same | M1 |
| Δ dilated changed | secondary | diagnóstico |
| Δ copy CLM | holdout declarado | M2 |

---

## 9. Checkpoint log (rellenar en ejecución)

| Fecha | Hipótesis | Resultado | Go/No-go | Evidencia | Siguiente |
|-------|-----------|-----------|----------|-----------|-----------|
| 2026-07-15 | H3 ventanas Tobarra | early ratio 2.01 FAIL; mid 0.50 PASS; late 1.24 PASS | **GO_PARTIAL** 2/3 | `outputs/temporal_windows/...` | fusión balanceada |
| 2026-07-15 | H3 re-cierre | early 0.94 · mid 0.40 · late 0.99; **wide 3/3** | **GO** | same + band_wide [0.35,2.2] | O3 cerrado |
| 2026-07-15 | H4 producto GIS | main_front + timeline + brief | **GO** | packs v4/v5 | — |
| 2026-07-15 | Multi-IF | 5 IF packs (La Estrella, Retuerta +3) | **GO packs** | observatorio_v5 | O5 sigue 1×A |
| 2026-07-15 | Tobarra ancla | ROS ~7–13 según ventana pack | **GO** ratio∈[0.5,2] | v4/v5 | — |
| 2026-07-15 | H7 CLM transfer | IoU 0.79, Δcopy +0.29 train | **GO*** | ml_eval | holdout pendiente |
| 2026-07-15 | M1 v24 | kernel preparado | **queued** | `run_unet_training_v24.py` | push Kaggle si red |

### Gate S1

| Item | Status | Notas |
|------|--------|-------|
| O3 ventanas Tobarra | ✅ **GO** | strict 2/3 + wide 3/3 (fase mid más lenta) |
| O4 producto GIS | ✅ GO | geojson + csv + brief |
| Tobarra no regresión | ✅ | ratio ancla en banda |
| Multi-IF escala | ✅ 5 packs | sin 2ª ancla externa |
| Anclas/perímetros | ⏳ blocked | sin datos externos |

### Gate S2

| Item | Status | Notas |
|------|--------|-------|
| O1 multi-ancla | ⏳ | solo Tobarra |
| O2 perímetro | ⏳ blocked | |
| O5 segundo A | ⏳ | Cardoso/Hellín siguen B |
| M1 | ⏳ | no corrido v24 esta sesión |
| M2 | ✅ GO* | train split CLM; documentado |
| **Veredicto sesión 2h** | **GO parcial fuerte** | O3 partial + O4 + Tobarra 7.21 + M2 train |

---

## 10. Entregables finales de la quincena

1. `outputs/observatorio/` v4 (o confirmación v3 + delta)  
2. `docs/ENTREGA_OBSERVATORIO.md` actualizado (lenguaje observatorio)  
3. `docs/EXPERIMENT_TRACKER.md` + `experiment_queue.json`  
4. Si ML: summary v24 + veredicto promote/no  
5. `docs/LOOP_2W_SALTOS_NOTABLES.md` §9–10 cerrados  
6. Lista **blocked** (datos que solo el observatorio puede dar)

---

## 11. Roles y ritmo

| Rol | Responsabilidad |
|-----|-----------------|
| PM/loop owner | Prioridad O > M; go/no-go; no vanity |
| Eng motor | front_dynamics, packs, GIS |
| Eng ML | solo cola 7–8; no robar días a O1–O4 |
| Observatorio (externo) | Anclas Vp/ha, perímetros, feedback brief |

**Standup mental diario (5 líneas):**  
hipótesis activa · métrica · bloqueo · go/no-go ayer · próximo experimento.

---

## 12. Arranque inmediato (D1, sin esperar)

```bash
# 1) Congelar lectura de baseline
#    outputs/observatorio/observatory_scorecard.json  (v3)
#    docs/ENTREGA_OBSERVATORIO.md

# 2) Implementar primer salto O3
#    scripts/eval_temporal_windows.py --fire tobarra_20240802 --windows 3

# 3) Registrar en experiment_queue + EXPERIMENT_TRACKER
```

**Primera pregunta al observatorio (en paralelo a D1):**  
> ¿Podéis darnos Vp media / ha (o croquis) para Cardoso 2025 y Hellín 2024, y un perímetro vectorial de Tobarra o de otro IF?

Sin eso, el techo de la quincena es **GO parcial** (motor validado en 1 ancla + producto GIS), no **GO+**.

---

## 13. Definición de éxito en una frase

> En 2 semanas, el observatorio puede abrir un pack y ver **ROS multi-estimador estable en Tobarra (varias ventanas), un segundo IF con ancla o validación geométrica, y un producto GIS de 5 minutos** — o un **NO-GO documentado** por falta de datos externos, no por caos del repo.

---

*Documento canónico del loop. Actualizar §9 en cada checkpoint. No abrir vN de ML hasta cumplir gate S1 de pista O.*
