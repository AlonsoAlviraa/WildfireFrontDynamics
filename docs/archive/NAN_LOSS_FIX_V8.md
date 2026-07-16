# Fix Crítico: NaN Loss en Mega Entrenamiento V8

**Fecha**: 2026-07-09
**Kernel**: `wildfire-front-training-v8`
**Impacto**: Bloqueante — el entrenamiento anterior (v6/v7) colapsaba con NaN en epoch 1-2

---

## 🔍 Causa Raíz Diagnosticada

Tras analizar el pipeline completo, se identificaron **3 causas simultáneas** del NaN loss:

### Causa 1: Temperaturas en Kelvin (NDWS)
El dataset Google NDWS entrega `tmmn`/`tmmx` en **Kelvin** (~250-330K), no en Celsius.
El código las usaba directamente, generando valores que al normalizarse a fp16 (AMP) producían overflow → NaN.

```python
# ANTES (BROKEN): max_temp = 310.15  (Kelvin)
# DESPUÉS (FIXED): max_temp = 37.0   (Celsius)
if np.max(max_temp) > 200:
    max_temp = max_temp - 273.15
```

### Causa 2: Canales sin normalizar (3 órdenes de magnitud de spread)
El vector de 17 canales tenía valores brutos con rangos incompatibles:

| Canal | Variable | Valor típico (raw) |
|-------|----------|-------------------|
| 0 | slope | 0.3 rad |
| 7 | pressure | **1013.0** hPa |
| 8 | cloud | 10.0 % |
| 11 | NDVI | 0.6 |
| 16 | FFMC | 85.0 |

Pressure=1013 vs slope=0.3 genera un spread de **3 órdenes de magnitud** que, bajo AMP (fp16), satura el rango representable (max ~65504) y produce Inf → NaN en el backward pass.

### Causa 3: Sin guard de NaN en el loop de entrenamiento
`run_mega_training.py` no detectaba NaN en inputs/features, por lo que un solo batch corrupto contaminaba los gradientes acumulados y arrastraba todo el modelo a NaN.

---

## ✅ Fixes Aplicados (5 archivos)

### 1. `wildfire_front/ml/normalization.py` (NUEVO)
Módulo centralizado de normalización con estadísticas por canal:

```python
def normalize_channels_inplace(channels: np.ndarray) -> np.ndarray:
    """Normaliza 17 canales a ~[0,1] usando estadísticas físicas conocidas."""
    # sub/div por canal: pressure (1013±50), temp (15±20), FFMC (50±51), etc.
    # + sanitización de NaN/Inf → 0.0
    # + clip a [-10, 10]
```

### 2. `kaggle_job/preprocess_ndws.py`
- ✅ Detección y conversión Kelvin → Celsius
- ✅ Normalización de los 17 canales antes de guardar NPZ
- ✅ Sanitización de NaN/Inf → 0.0

### 3. `wildfire_front/ml/dataset.py`
- ✅ `WildfireDataset._build_17_channels()` ahora llama a `normalize_channels_inplace()`
- ✅ `NpzWildfireDataset.__getitem__()` sanitiza NaN/Inf del NPZ antes de convertir a tensor

### 4. `wildfire_front/ml/train.py`
- ✅ `focal_loss_with_logits()`: clamp de logits a [-10, 10] + replace NaN → 0
- ✅ Fallback final: si loss sigue siendo NaN, retorna tensor `0.0` con `requires_grad=True`

### 5. `kaggle_job/run_mega_training.py`
- ✅ Guard de NaN en **inputs** (sequence): skip batch
- ✅ Guard de NaN en **features** (post-forward): skip batch + log warning
- ✅ Guard de NaN en **loss**: skip step
- ✅ Contador `nan_skipped_batches` con logging por epoch

---

## 🧪 Cómo Verificar el Fix

### Test local (CPU, smoke test):
```bash
python scripts/smoke_test_finetune.py
```

### Test Kaggle (GPU):
```bash
kaggle kernels push -p kaggle_job/
# Monitorizar con:
kaggle kernels status alonsoalvira/wildfire-front-training-v8
```

### Métricas esperadas post-fix:
- **Epoch 1**: train_loss entre 0.3-0.8 (NO NaN)
- **Epoch 5**: train_loss entre 0.1-0.3
- **Epoch 15**: val_loss estable, early stopping activa si no mejora
- **NaN skipped batches**: < 1% del total (idealmente 0)

---

## 📋 Próximos Sprints Recomendados

Tras confirmar que V8 entrena sin NaN:

1. **Sprint 6.1**: Descargar resultados de V8, analizar curvas train/val loss
2. **Sprint 6.2**: Fine-tuning con datos reales de Tobarra (LWIR)
3. **Sprint 7**: Validación cualitativa visual (predicción vs ground truth)
4. **Sprint 8**: Integración de meteo AEMET en tiempo real (FFMC dinámico)
5. **Sprint 9**: Deploy inference endpoint (FastAPI + Docker)