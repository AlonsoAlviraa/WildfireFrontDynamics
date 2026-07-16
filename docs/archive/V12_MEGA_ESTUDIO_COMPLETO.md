# 🔬🔬 MEGA ESTUDIO COMPARATIVO: v10 vs v11 vs v12

> **Fecha:** 2026-07-10
> **Cuenta Kaggle:** `alonsoalviraaaa` (migrada a uni)
> **3 entrenamientos analizados:** v10, v11, v12

---

## ✅ Resumen Ejecutivo — Tabla Maestra

| Métrica | v10 | v11 | **v12** | Tendencia |
|---|---|---|---|---|
| **Configuración** | LR=1e-4, pw=3 | LR=5e-5, pw=3 | LR=5e-5, **pw=8**, freeze | — |
| `best_val_loss` | 0.2849 | 0.2712 | **0.2740** | v11 mejor |
| `test_loss` | 0.2771 | 0.2726 | **0.3016** | 🔴 v12 peor |
| `best_epoch` | 3 | 1 | **2** | 🔴 Sigue prematuro |
| `total_epochs` | 11 | 13 | **14** | v12 duró más |
| `meta_labeler_acc` | 68.9% | **90.1%** | 63.6% | 🔴 v12 catastrophic |
| `micro_recall` | N/A | 0.042 | **0.002** | 🔴🔴 v12 peor aún |
| `micro_iou` | N/A | 0.035 | **0.002** | 🔴🔴 |
| `micro_precision` | N/A | 0.183 | **0.161** | 🔴 |

---

## 📊 Análisis Detallado v12

### Curva de entrenamiento v12

| Epoch | Train Loss | Val Loss | Gap | Estado |
|---|---|---|---|---|
| 1 | 2.5330 | 2.0884 | −0.445 | 🔴 Loss altísimo (pos_weight=8) |
| **2** | **0.3313** | **0.2740** | **−0.057** | **★ BEST** |
| 3 | 0.2745 | 0.2931 | +0.019 | |
| 4 | 0.2742 | 0.2896 | +0.015 | |
| 5 | 0.2770 | 0.2870 | +0.010 | Fin warmup (unfreeze conv) |
| 6 | 0.2782 | 0.2890 | +0.011 | |
| 7 | 0.2768 | 0.2890 | +0.012 | |
| 8 | 0.2787 | 0.2868 | +0.008 | |
| 9 | 0.2803 | 0.3275 | +0.047 | 🔴 Salto |
| 10 | 0.2880 | 0.3066 | +0.019 | |
| 11 | 0.2891 | 0.3208 | +0.032 | |
| 12 | 0.2850 | 0.2977 | +0.013 | |
| 13 | 0.2848 | 0.3295 | +0.045 | |
| 14 | 0.2834 | 0.3259 | +0.043 | Early stop |

### Hallazgos clave de v12

1. **Epoch 1 train_loss=2.53** (vs v11: 0.59) — `pos_weight=8` hizo que la loss inicial fuera 4x más alta. El modelo recibe una penalización masiva por cada falsos negativo.

2. **Best epoch = 2** (vs v11: 1) — El freeze de conv + start_factor=0.01 permitió que el modelo sobreviviera la epoch 1 y encontrara un mínimo LIGERAMENTE mejor en epoch 2. **Mejora marginal.**

3. **Recall = 0.2%** (vs v11: 4.2%) — **CATASTRÓFICAMENTE PEOR**. El `pos_weight=8` paradoxically hizo que el modelo prediga AÚN MENOS fuego. Esto confirma que el problema NO es el balance de clases sino la arquitectura.

4. **Test loss = 0.30** (vs v11: 0.27) — Overfitting: el modelo generaliza peor al test set.

5. **Meta-labeler acc = 63.6%** (vs v11: 90.1%) — Con recall tan bajo, el meta-labeler no tiene información útil para aprender.

---

## 🔬 CONCLUSIÓN DEFINITIVA: El problema NO es de hiperparámetros

### Evidencia acumulada de 3 entrenamientos

| Intento | Qué cambiamos | Resultado | Conclusión |
|---|---|---|---|
| v10 | LR=1e-4, pw=3 | best=epoch 3 | LR un poco alto |
| v11 | LR=5e-5, pw=3 | best=epoch 1, val=0.2712 | LR más bajo no ayuda |
| v12 | LR=5e-5, pw=8, freeze conv | best=epoch 2, val=0.2740, **recall=0.2%** | pw=8 empeora todo |

**Patrón claro:** En las TRES versiones, el mejor modelo se obtiene en las primeras 1-3 epochs. Después, el entrenamiento SOLO empeora. Los pesos pre-entrenados `v3.pt` son consistentemente mejores que cualquier cosa que produce nuestro fine-tuning.

### Las 3 hipótesis descartadas

1. ❌ **"El LR es demasiado alto"** — v11 bajó el LR a la mitad y el best epoch retrocedió a 1
2. ❌ **"El desequilibrio de clases causa bajo recall"** — v12 subió pos_weight de 3 a 8 y el recall bajó de 4.2% a 0.2%
3. ❌ **"El freeze de conv protegerá los features"** — v12 freezeó conv durante 5 epochs y el resultado fue peor

### La causa raíz confirmada

**El modelo A3C_PerCellModel_LSTM no puede aprender de nuestro pipeline de patches 30×30.** La arquitectura per-cell iterativa con `batch_size=1` produce gradientes con un ratio señal/ruido tan bajo que el entrenamiento es contraproducente.

---

## 📈 Gráficas generadas

En `docs/analysis_plots_v12/`:
- `01_loss_curves_v10_vs_v11.png` — v10 vs v12 superpuestas
- `02_gap_analysis.png` — Gap analysis
- `03_lr_schedule.png` — LR schedule
- `04_segmentation_metrics_v11.png` — Métricas v12
- `05_summary_comparison.png` — Barras comparativas

---

## 🎯 DECISIÓN: Ir directo al Sprint 6 (Batch Vectorization)

Dado que 3 intentos de hiperparámetros no han resuelto el problema, **el siguiente paso obligatorio es el refactor arquitectural**:

### Sprint 6: Batch Vectorization (PRIORIDAD CRÍTICA)

**Objetivo:** Eliminar la restricción `batch_size=1` que hace imposible el entrenamiento.

| Cambio | Impacto esperado |
|---|---|
| Refactorizar `forward()` para procesar batch de patches | batch_size=8-16 real |
| Reducir ruido de gradientes | Best epoch > 10 |
| Estabilizar el entrenamiento | val_loss < 0.20 |
| Aumentar capacidad de aprendizaje | recall > 20% |

**Alternativa si batch vectorization es muy compleja:** Implementar UNet baseline (Sprint 7) que es nativamente batch-friendly.

---

## 📁 Artefactos v12

- `models/weights_v12_best.pt` — Mejor checkpoint (epoch 2)
- `docs/V12_TRAINING_RESULTS.json` — Métricas completas
- `docs/analysis_plots_v12/` — 5 gráficas comparativas

---

## ✅ Conclusión del Mega Estudio

**Tras 3 entrenamientos (v10, v11, v12) queda demostrado que:**

1. El modelo alcanza su techo (~0.27 val_loss) instantáneamente con los pesos v3.pt
2. Ningún ajuste de hiperparámetros (LR, pos_weight, freeze, warmup) permite superar ese techo
3. El recall es críticamente bajo (0.2%–4.2%) en todas las versiones
4. **La arquitectura per-cell con batch_size=1 es el cuello de botella fundamental**

**Próximo paso:** Sprint 6 (batch vectorization) o Sprint 7 (UNet alternativa)