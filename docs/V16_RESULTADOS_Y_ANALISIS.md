# V16 Resultados y Analisis Comparativo

**Fecha:** 2026-07-10
**Version:** v16 (WildfireUNet Full + SE Attention)
**GPU:** Tesla P100-PCIE-16GB
**Tiempo:** 6.1 min (366s)

## 1. Configuracion v16

| Parametro | v14 | v16 |
|-----------|-----|-----|
| Arquitectura | WildfireUNetSmall | **WildfireUNet (Full)** |
| Parametros | 1,076,385 | **4,334,913 (4x mas)** |
| SE Attention | No | **Si** |
| Norm | GroupNorm | GroupNorm |
| Loss | Composite | Composite |
| Epochs | 50 (early stop @8) | 50 (early stop @6) |
| Batch size | 32 | 32 |
| LR peak | 1e-3 | 1e-3 |

## 2. Resultados Comparativos (Test Set, 619 muestras)

### Metricas principales @threshold=0.5

| Metrica | v14 (Small) | v16 (Full+SE) | Cambio | Copy Baseline |
|---------|-------------|---------------|--------|---------------|
| **IoU** | 0.2387 | 0.2367 | -0.002 | **~0.79** |
| **Dice** | 0.3854 | 0.3828 | -0.003 | ~0.86 |
| **Recall** | 0.5636 | **0.5886** | +0.025 | ~0.88 |
| **Precision** | 0.2928 | 0.2836 | -0.009 | ~0.90 |

### Metricas @threshold=0.3 (maximo recall)

| Metrica | v14 | v16 | Cambio |
|---------|-----|-----|--------|
| IoU | 0.2288 | 0.2218 | -0.007 |
| Recall | 0.6184 | **0.6531** | +0.035 |
| Precision | 0.2664 | 0.2514 | -0.015 |

### Metricas @threshold=0.6 (maxima precision)

| Metrica | v14 | v16 | Cambio |
|---------|-----|-----|--------|
| IoU | 0.2424 | **0.2398** | -0.003 |
| Precision | 0.3077 | 0.2980 | -0.010 |
| Recall | 0.5333 | 0.5510 | +0.018 |

## 3. Analisis Critico

### Hallazgo principal: Cuadruplicar parametros NO ayudo

El modelo v16 con 4.3M parametros (4x mas que v14) obtuvo resultados **practicamente identicos**:
- IoU: 0.237 vs 0.239 (-0.8%)
- Recall mejoro ligeramente: +4.5% en recall@0.3
- Precision empeoro: -3.4%

**Conclusion:** El cuello de botella NO es la capacidad del modelo. Es el **dataset/architectura**.

### Confirmacion del Copy Baseline Problem

El copy baseline (IoU ~0.79) sigue superando al modelo por **3.3x**. Esto confirma que:

1. **El modelo NO esta aprendiendo a copiar el input** (sino IoU seria ~0.79)
2. **El modelo TAMPOCO esta aprendiendo propagacion real** (sino IoU seria >0.79)
3. El modelo esta en un **limite inferior** prediciendo ruido estructurado

### Fire pixel ratio

- **Mean fire pixel ratio:** 1.03% (solo 1% de pixels son fuego)
- Esto confirma el fuerte desbalanceo de clases

## 4. Evolucion de Versiones

| Version | Modelo | Params | IoU@0.5 | Recall@0.3 | Tiempo |
|---------|--------|--------|---------|------------|--------|
| v10 | SimpleUNet | ~500K | 0.003 | 0.006 | 3 min |
| v11 | SimpleUNet | ~500K | 0.002 | 0.004 | 3 min |
| v12 | SimpleUNet | ~500K | 0.002 | 0.002 | 3 min |
| v14 | UNetSmall | 1.1M | **0.239** | 0.618 | 4.4 min |
| v16 | UNet Full+SE | 4.3M | 0.237 | **0.653** | 6.1 min |

El salto de v12 a v14 fue gracias al loop engineering (64x64 patches, composite loss, 3-level UNet).
De v14 a v16 **no hay salto** porque el problema no es de capacidad.

## 5. Cuellos de Botella Identificados

### Botella #1: Copy Baseline (CRITICO)
- **Problema:** PrevFireMask correlaciona r=0.87 con FireMask
- **Solucion:** Arquitectura residual (predict delta) o cambiar target

### Botella #2: Desbalanceo extremo
- **Problema:** Solo 1% de pixels son fuego
- **Solucion:** pos_weight=15-20, o focal loss con gamma=3

### Botella #3: Canales no informativos
- **Problema:** 14 de 17 canales tienen correlacion < 0.02 con target
- **Solucion:** Feature engineering (wind x slope, temp x humidity)

### Botella #4: Dataset mayormente estable
- **Problema:** 46% de muestras son "stable" (cambio < 10%)
- **Solucion:** Filtrar o augmentar con fire growth sintetico

## 6. Recomendaciones para v17/v18

### v17: Arquitectura Residual Real
```python
# NO usar logit(probs) que es inestable numericamente
# En su lugar, el modelo predice logits absolutos
# pero se anade el current_fire como bias:
prediction_logits = model(x) + current_fire * scale_factor
```

### v18: Sin PrevFireMask
- Eliminar PrevFireMask del input
- Forzar al modelo a usar solo features meteorologicos/topograficos
- Evaluar si puede predecir fuego solo con fisica

### v19: Target = Fire Spread
- Cambiar target a `spread = target_fire XOR current_fire`
- Solo predecir donde el fuego CRECE o RETROCEDE
- Mucho mas balanceado (aunque mas dificil)

## 7. Siguientes pasos inmediatos

1. **Lanzar v17** con arquitectura residual correcta (sin logit inestable)
2. **Lanzar leakage analysis kernel** con datos reales NDWS
3. **Probar sin PrevFireMask** para medir cuanto aporta la fisica vs persistencia