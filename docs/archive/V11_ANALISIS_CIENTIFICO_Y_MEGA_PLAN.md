# 🔬 V11 — Análisis Científico Profundo y Mega Plan de Sprints

> **Fecha:** 2026-07-10
> **Kernel v11:** `alonsoalvira/wildfire-front-training-v11` — COMPLETE
> **Commit:** `263932d` — LR 5e-5, warmup 5, patience 12, meta-labeler 12 features
> **Gráficas:** `docs/analysis_plots/` (5 PNG generados)

---

## ✅ Resumen Ejecutivo

v11 trajo **tres mejoras claras** y **una revelación crítica**:

| Métrica | v10 | v11 | Cambio | Veredicto |
|---|---|---|---|---|
| `best_val_loss` | 0.2849 | **0.2712** | **−4.8%** | ✅ Mejor |
| `test_loss` | 0.2771 | **0.2726** | **−1.6%** | ✅ Mejor |
| `meta_labeler_test_acc` | 68.9% | **90.1%** | **+21.2pp** | ✅ ✅ Excelente |
| `best_pretrain_epoch` | 3 | **1** | **−2** | 🔴 **PROBLEMA RAÍZ CONFIRMADO** |
| `micro_recall` | N/A | **0.042** | — | 🔴 **CATASTRÓFICO** |
| `micro_iou` | N/A | **0.035** | — | 🔴 El modelo apenas predice fuego |

---

## 📊 Análisis Comparativo v10 vs v11

### Gráficas generadas (en `docs/analysis_plots/`)

1. `01_loss_curves_v10_vs_v11.png` — Curvas superpuestas
2. `02_gap_analysis.png` — Gap train→val
3. `03_lr_schedule.png` — Schedule de LR
4. `04_segmentation_metrics_v11.png` — IoU/Dice/Precision/Recall
5. `05_summary_comparison.png` — Barras comparativas

### Curva v11 (epoch a epoch)

| Epoch | Train Loss | Val Loss | Gap | LR (aprox) | Estado |
|---|---|---|---|---|---|
| **1** | **0.5903** | **0.2712** | **−0.319** | 0.5e-5 | **★ BEST** |
| 2 | 0.2729 | 0.2853 | +0.012 | 1.0e-5 | |
| 3 | 0.2725 | 0.2893 | +0.017 | 1.5e-5 | |
| 4 | 0.2753 | 0.2877 | +0.012 | 2.0e-5 | |
| 5 | 0.2786 | 0.2872 | +0.009 | 2.5e-5 | Fin warmup |
| 6 | 0.2776 | 0.2874 | +0.010 | 5.0e-5 | Peak LR |
| 7 | 0.2779 | 0.2872 | +0.009 | 4.9e-5 | |
| 8 | 0.2784 | 0.3157 | +0.037 | 4.8e-5 | 🔴 Salto |
| 9 | 0.2826 | 0.3118 | +0.029 | 4.7e-5 | |
| 10 | 0.2836 | 0.3182 | +0.035 | 4.6e-5 | |
| 11 | 0.2866 | 0.3218 | +0.035 | 4.4e-5 | |
| 12 | 0.2858 | 0.3584 | +0.073 | 4.3e-5 | 🔴 |
| 13 | 0.2831 | 0.3215 | +0.038 | 4.1e-5 | Early stop |

### Pregunta clave del usuario: ¿El LR reducido extendió el entrenamiento más allá de epoch 3?

**NO.** El best epoch retrocedió de epoch 3 (v10) a **epoch 1** (v11). El problema NO es el learning rate.

---

## 🔬 Descubrimiento Crítico: El problema es arquitectural, no de hiperparámetros

### Evidencia #1: El mejor momento es ANTES de aprender

En v11, la **primera epoch** tiene `train_loss=0.59` (alta, el modelo no ha aprendido) pero `val_loss=0.27` (la más baja de todo el run). Esto significa:

> **Los pesos pre-entrenados de v3.pt (`load_pretrained_weights`) son MEJORES que cualquier cosa que el entrenamiento produce.**

El modelo empieza desde `models/v3.pt` (entrenado previamente por alguien más en NDWS) y nuestro fine-tuning **destruye** ese conocimiento en lugar de mejorarlo.

### Evidencia #2: Recall = 4.2% (catastrófico)

```
micro_recall:    0.042  → solo detecta 4 de cada 100 fuegos reales
micro_precision: 0.183  → cuando predice fuego, acierta 18% de las veces
micro_iou:       0.035  → solapamiento casi nulo
accuracy:        0.965  → ALTA porque 96.5% del mapa es "no fuego"
```

El modelo ha aprendido a **predecir "no fuego" en casi todas partes** porque esa es la estrategia óptima para minimizar focal BCE cuando el 90%+ de las células son negativas.

### Evidencia #3: El gap nunca indica overfitting

El gap `val_loss - train_loss` está siempre entre +0.01 y +0.04 (salvo epoch 1). No hay overfitting. El modelo simplemente **no tiene capacidad de aprender patrones útiles** con este setup.

---

## 🎯 Diagnóstico de las 3 causas raíz

### Causa #1: `batch_size=1` genera gradientes inútiles (CRÍTICO)

El modelo `A3C_PerCellModel_LSTM` itera célula por célula dentro del forward pass. Esto fuerza `batch_size=1`, lo que significa:

- Cada gradiente viene de **un único patch 30×30** con ~5-10 células ardientes
- Con `GRAD_ACCUM=4`, el batch efectivo es 4 patches → ~20-40 células
- El ruido estocástico es **mayor que la señal**
- Resultado: el modelo oscila alrededor del mínimo sin converger

**Solución:** Vectorizar el forward pass para procesar todas las células en paralelo (batch de celdas, no de patches). Esto permitiría `batch_size=8-16` real.

### Causa #2: Desequilibrio extremo de clases (CRÍTICO)

```
TEST meta features: 860,853 positivos / 83,043 negativos (91.2% pos)
```

Aunque usamos `pos_weight=3.0` y focal loss con `gamma=2.0`, la función de loss sigue premiando "predecir no-fuego" porque:

- El 90%+ de vecinos de células ardientes **no se incendian** al día siguiente
- Focal loss reduce pero no elimina el sesgo hacia la clase mayoritaria
- Con `batch_size=1`, el modelo ve secuencias casi todas negativas

**Solución:** Oversampling agresivo de patches con alta actividad de fuego, o `pos_weight=10.0`.

### Causa #3: Los pesos v3.pt son demasiado buenos (PARADOJA)

Los pesos pre-entrenados `v3.pt` ya fueron entrenados en NDWS por un tercero. Cuando los cargamos y empezamos a entrenar, destruimos ese conocimiento porque:

- Nuestro preprocessing de patches 30×30 difiere del original
- El warmup no protege los pesos: aún con LR bajo (5e-6 en epoch 1), el primer gradiente ya daña los features
- No hay freezing de capas convolucionales durante warmup

**Solución:** Freeze de capas conv durante las primeras 5 epochs (solo entrenar policy head), luego unfreeze progresivo.

---

## 📈 Estimación del Techo del Modelo Actual

Basado en el patrón observado:

| Escenario | val_loss alcanzable | ¿Cómo? |
|---|---|---|
| **Actual (v11)** | 0.2712 | Pesos v3 sin tocar |
| **Techo con ajustes menores** | ~0.260 | pos_weight=10, freeze conv 5 epochs |
| **Techo con batch vectorization** | ~0.200 | Refactor arquitectural mayor |
| **Literatura (NDWS papers)** | 0.10–0.15 | Modelos UNet/DeepLab con full supervision |

**Conclusión:** El modelo actual tiene un techo de loss ≈ 0.25–0.27 con la arquitectura per-cell. Para bajarlo significativamente necesitamos **batch vectorization** o **cambiar a arquitectura fully-convolutional**.

---

## 🗺️ MEGA PLAN DE SPRINTS (Re-estructurado)

### Sprint 1: Estabilizar el entrenamiento — NO tocar el modelo (1 día)

**Objetivo:** Lograr que el modelo mejore a partir de epoch 1 en lugar de empeorar.

| # | Acción | Archivo | Riesgo |
|---|---|---|---|
| 1.1 | **Freeze conv1/conv2/conv3 durante 5 epochs** (solo entrenar LSTM + policy head) | `run_mega_training.py` | Bajo |
| 1.2 | **Subir pos_weight de 3.0 a 8.0** (forzar al modelo a predecir más fuego) | `wildfire_front/ml/train.py` | Medio |
| 1.3 | **LR warmup start más bajo:** `start_factor=0.01` (en lugar de 0.1) | `run_mega_training.py` | Bajo |
| 1.4 | **Gradient clipping más agresivo:** `max_norm=0.3` (en lugar de 0.5) | `run_mega_training.py` | Bajo |
| 1.5 | Re-entrenar v12 en Kaggle | — | — |

**Criterio de éxito:** Best epoch > 5 (el modelo aprende durante el entrenamiento, no solo usa v3.pt).

### Sprint 2: Análisis SHAP + Feature Importance (1 día)

**Objetivo:** Entender qué features explican los errores del meta-labeler.

| # | Acción | Script |
|---|---|---|
| 2.1 | Crear `scripts/analyze_meta_labeler_shap.py` | Nuevo |
| 2.2 | SHAP TreeExplainer sobre `meta_labeler_v11.pkl` | — |
| 2.3 | Matriz de correlación de las 12 features | — |
| 2.4 | Feature importance del RandomForest | — |
| 2.5 | Guardar gráficas en `docs/analysis_plots/` | — |

### Sprint 3: Análisis de errores del modelo neuronal (1 día)

**Objetivo:** Visualizar dónde y cómo falla el modelo.

| # | Acción | Script |
|---|---|---|
| 3.1 | Crear `scripts/analyze_model_errors.py` | Nuevo |
| 3.2 | Clasificar errores: FP vs FN por tipo de terreno | — |
| 3.3 | Mapa de calor espacial de errores | — |
| 3.4 | Distribución de probabilidades predichas | — |
| 3.5 | Análisis por rango de slope/vegetation | — |

### Sprint 4: Oversampling + Class Balance (1 día)

**Objetivo:** Subir el recall de 4% a >30%.

| # | Acción | Archivo |
|---|---|---|
| 4.1 | WeightedRandomSampler con pesos inversos | `run_mega_training.py` |
| 4.2 | Filtrar patches con baja actividad de fuego | `preprocess_ndws.py` |
| 4.3 | Aumentar cap de patches con alta actividad | `preprocess_ndws.py` |

### Sprint 5: Datos de Castilla-La Mancha — Fine-Tuning Táctico (2 días)

**Objetivo:** Adaptar el modelo base al dominio métrico local con los 362 frames reales.

| # | Acción | Script/Archivo |
|---|---|---|
| 5.1 | Empaquetar 8 incendios como Kaggle dataset | `scripts/package_real_data_for_kaggle.py` |
| 5.2 | Pipeline GeoTIFF→patches | `scripts/geotiff_to_training_patches.py` |
| 5.3 | Integrar fine-tuning con CLM en `run_mega_training.py` | `kaggle_job/` |
| 5.4 | Evaluación comparativa: base vs fine-tuned en Tobarra | `scripts/compare_base_vs_finetuned.py` |

### Sprint 6: Batch Vectorization — Refactor Arquitectural (3 días)

**Objetivo:** Eliminar la restricción `batch_size=1`.

| # | Acción | Archivo |
|---|---|---|
| 6.1 | Refactorizar `forward()` para procesar todas las células en paralelo | `models/model.py` |
| 6.2 | Vectorizar `calculate_local_spread_loss_vectorized` | `wildfire_front/ml/train.py` |
| 6.3 | Habilitar `batch_size=8-16` real | `run_mega_training.py` |
| 6.4 | Tests de no-regresión | `tests/test_ml_pipeline.py` |

### Sprint 7: Arquitectura Fully-Convolutional Alternativa (5 días, opcional)

**Objetivo:** Si el techo per-cell es demasiado bajo, evaluar UNet/DeepLab.

| # | Acción |
|---|---|
| 7.1 | Implementar UNet baseline para segmentación de fuego |
| 7.2 | Comparar A3C-LSTM vs UNet en mismo dataset |
| 7.3 | Decidir arquitectura final |

---

## 📁 Artefactos Generados

### Pesos v11 (en `models/`)
- `weights_v11_best.pt` — Mejor checkpoint (epoch 1)
- `weights_v11_finetuned.pt` — Fine-tuned en dataset local
- `meta_labeler_v11.pkl` — RF con 12 features (90.1% accuracy)

### Gráficas (en `docs/analysis_plots/`)
- `01_loss_curves_v10_vs_v11.png`
- `02_gap_analysis.png`
- `03_lr_schedule.png`
- `04_segmentation_metrics_v11.png`
- `05_summary_comparison.png`

### Datos (en `docs/`)
- `V11_TRAINING_RESULTS.json` — Métricas completas

---

## ✅ Conclusión

**El fix de hiperparámetros (v11) mejoró las métricas pero confirmó que el problema es arquitectural:**

1. ✅ **Meta-labeler funciona excelente** (90.1% con 12 features)
2. ✅ **Loss se redujo** (0.2849 → 0.2712)
3. 🔴 **El modelo no aprende nada nuevo** (best=epoch 1, los pesos v3.pt son mejores)
4. 🔴 **Recall catastrófico** (4.2%) — el modelo predice "no fuego" casi siempre
5. 🔴 **El techo es arquitectural** — batch_size=1 genera gradientes inútiles

**Próximo paso inmediato:** Sprint 1 (freeze conv + pos_weight=8) para validar si el modelo puede aprender. Si no, ir directo a Sprint 6 (batch vectorization).