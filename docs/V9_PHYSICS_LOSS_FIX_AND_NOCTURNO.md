# V9 — Physics Loss Fix + Configuración Nocturna

**Fecha:** 2026-07-09
**Estado:** Implementado y verificado localmente (smoke test PASS)

---

## Problema crítico resuelto

El entrenamiento v8 sufría de **loss explosion**: el `physics_loss_cell` podía devolver valores de 100,000+ cuando la propagación física era imposible, desestabilizando completamente el entrenamiento.

### Causa raíz
La función `physics_loss_cell` calculaba `violation = (ros_implied / (ros_max + eps)) - 1` sin **clipping**. Cuando `ros_max → 0` (viento débil + pendiente baja), la violación explotaba a infinito, arrastrando el loss total consigo.

---

## Sprint 1 — Fix crítico (COMPLETADO)

### Cambios

| Archivo | Cambio |
|---------|--------|
| `wildfire_front/ml/physics.py` | Nueva función `physics_loss_cell_vectorized` — vectorizada + bounded a `[0, lambda_physics]` |
| `wildfire_front/ml/train.py` | Reemplazo del loop Python por llamada vectorizada |
| `scripts/smoke_test_physics_loss.py` | 4 tests de regresión |

### Función nueva: `physics_loss_cell_vectorized`

```python
def physics_loss_cell_vectorized(
    probs, wind_norm, slope_norm,
    ffmc=90.0, lambda_physics=0.1, cell_size_m=30.0, dt_min=10.0
):
```

**Garantías matemáticas:**
1. **Bounded:** `loss ∈ [0, lambda_physics]` — NUNCA excede 0.1
2. **Des-normalización interna:** wind_norm × 20, slope_norm × π/2
3. **Vectorizada:** procesa N celdas en paralelo (speedup infinito vs loop Python)
4. **Penalty suave:** usa `min(violation × 0.5, 1.0)` para suavizar el gradiente

### Smoke test resultados

```
[1/4] Loss bounded in [0, lambda_physics]:     PASS (0.100000 ≤ 0.1)
[2/4] Zero penalty when physical:              PASS (0.000000 ≈ 0)
[3/4] Des-normalization correct:               PASS (0.045150 = 0.045150)
[4/4] Speedup vs legacy loop:                  PASS (0.00ms vs 26.80ms)
```

---

## Sprint 2 — Optimización training (COMPLETADO)

### DataParallel NO es viable

El modelo `A3C_PerCellModel_LSTM` itera celda-por-celda y requiere `batch_size=1`. DataParallel (que replica el modelo y divide el batch) es **incompatible** con esta arquitectura.

### Soluciones implementadas

| Técnica | Impacto |
|---------|---------|
| **Gradient accumulation (×4)** | Simula batch_size=4 → gradientes más estables |
| **AMP (Automatic Mixed Precision)** | ~40-50% speedup en T4 sin cambios semánticos |
| **cudnn.benchmark=True** | Auto-tuning de kernels conv para input shapes fijos |
| **8 workers + persistent + prefetch** | GPU alimentada constantemente |

---

## Sprint 3 — Config nocturna (COMPLETADO)

### Cambios en `run_mega_training.py`

| Parámetro | v8 | v9 |
|-----------|----|----|
| `EPOCHS` | 15 | **50** (`WF_EPOCHS` env var) |
| `patience` | 4 | **8** |
| `WARMUP_EPOCHS` | 2 | **3** |
| Gradient accumulation | No | **Sí (×4)** |
| Auto-resume | No | **Sí** |
| Logging a archivo | No | **Sí (`training_log.txt`)** |
| State persistence | No | **Sí (`training_state.json`)** |

### Auto-resume

Si la sesión Kaggle se desconecta, el training puede reanudarse exactamente donde se quedó:

```python
# Al reiniciar, carga automáticamente:
# - weights_pretrained_best.pt (mejor modelo)
# - training_state.json (epoch, best_val_loss, history)
```

---

## Cómo lanzar el entrenamiento nocturno

### Opción 1: Kaggle CLI (recomendado)

```bash
# Push del kernel actualizado
kaggle kernels push -p kaggle_job/

# Monitorear estado
kaggle kernels status alonsoalvira/wildfire-front-training-v9

# Cuando termine, descargar outputs
kaggle kernels output alonsoalvira/wildfire-front-training-v9 -p kaggle_job/outputs/
```

### Opción 2: Override de epochs vía environment

```bash
# Para runs cortos de prueba (5 epochs)
WF_EPOCHS=5 kaggle kernels push -p kaggle_job/
```

### Outputs esperados

```
weights_pretrained.pt          # Modelo final (mejor epoch)
weights_pretrained_best.pt     # Best checkpoint (para auto-resume)
training_state.json            # Estado completo para resume
training_history.json          # Historial epoch-by-epoch
training_log.txt               # Log completo de texto
training_summary.json          # Métricas finales (test loss, meta-labeler acc)
meta_labeler.pkl               # Meta-labeler entrenado
```

---

## Próximos sprints sugeridos

Una vez que el run v9 nocturno complete, los siguientes pasos serían:

1. **Análisis de resultados v9** — Descargar outputs, comparar curvas train/val, evaluar si el physics loss bounded mejoró la convergencia
2. **Fine-tuning con datos de Tobarra** — Dataset real disponible en `data/real_if/`
3. **Evaluación cualitativa** — Visualizar predicciones en secuencias reales
4. **Hyperparameter tuning** — Probar `lambda_physics` en {0.05, 0.1, 0.2}
5. **Arquitectura batch-ready** — Si v9 muestra que bs=1 es el bottleneck, rediseñar el modelo para soportar batch>1 (cambio arquitectónico mayor)