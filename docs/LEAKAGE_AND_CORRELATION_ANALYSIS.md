# Leakage + Correlation + Bottleneck Analysis

**Fecha:** LEAKAGE_AND_CORRELATION_ANALYSIS.md
**Proposito:** Verificar que no hay data leakage y encontrar cuellos de botella

## 1. Data Leakage

| Check | Resultado |
|-------|-----------|
| Filename overlap (train<->val) | 20 |
| Filename overlap (train<->test) | 20 |
| Filename overlap (val<->test) | 20 |
| Content overlap (train<->val) | 0 |
| Content overlap (train<->test) | 0 |
| Content overlap (val<->test) | 0 |
| **LEAK DETECTADO** | **NO** |

**Conclusion:** Splits son disjuntos, no hay fuga de datos.

## 2. Copy Baseline (PrevFireMask como prediccion)

Esta es la prueba mas critica. Si el modelo solo copia el input, su IoU seria:

| Metrica | Copy Baseline | v14 Model | Diferencia |
|---------|--------------|-----------|------------|
| IoU | 0.7881 | 0.239 | -0.5491 |
| Dice | 0.8609 | 0.385 | -0.4759 |
| Recall | 0.8838 | 0.564 | -0.3198 |
| Precision | 0.9043 | 0.293 | -0.6113 |

**Correlacion espacial (PrevFireMask vs FireMask):** r = 0.8666

### [CRITICO] El modelo apenas supera el copy baseline

El modelo v14 (IoU=0.239) apenas mejora sobre copiar el input (IoU=0.7881).
**El modelo esta aprendiendo "copia el fuego anterior" en lugar de predecir propagacion.**

**Que hacer:**
1. Usar `--pos-weight` mas alto (10-15) para forzar al modelo a predecir fuego nuevo
2. Eliminar `PrevFireMask` del input temporalmente para forzar aprendizaje meteorologico
3. Cambiar el target a `fire_spread = target_fire - current_fire` (solo predecir el cambio)
4. Anadir loss term que penalice predicciones identicas al input

## 3. Importancia de Canales (Correlacion con target)

| Rank | Canal | Correlacion | |
|------|-------|------------|-|
| 1 | temperature | 0.1466 | ############## |
| 2 | padding_0 | 0.0138 | # |
| 3 | wind_dir | 0.0127 | # |
| 4 | slope | 0.0126 | # |
| 5 | precipitation | 0.0126 | # |
| 6 | 1-ERC_norm | 0.0123 | # |
| 7 | wind_speed | 0.0123 | # |
| 8 | dewpoint_const | 0.0123 | # |
| 9 | pressure_const | 0.0122 | # |
| 10 | ERC_norm | 0.0117 | # |
| 11 | visibility_const | 0.0115 | # |
| 12 | aspect | 0.0111 | # |
| 13 | FFMC | 0.0110 | # |
| 14 | padding_1 | 0.0110 | # |
| 15 | vegetation_NDVI | 0.0108 | # |
| 16 | cloud_const | 0.0108 | # |
| 17 | humidity | 0.0108 | # |

**Interpretacion:** Los canales con mayor |r| son los que mas informacion aportan
sobre donde estara el fuego manana. Si los canales meteorologicos (viento, temperatura)
tienen baja correlacion, el modelo puede estar ignorandolos.

## 4. Dinamica del Fuego

| Categoria | Count | % |
|-----------|-------|---|
| growth | 17 | 34.0% |
| shrink | 10 | 20.0% |
| stable | 23 | 46.0% |
| no_fire | 0 | 0.0% |

**Crecimiento medio:** 63.6%

**Conclusion:** Si la mayoria de muestras son "stable" o "no_fire", el dataset
esta desbalanceado hacia no-cambio, lo que explica por que el modelo tiende a copiar.

## 5. Recomendaciones

1. **Si copy baseline > 0.20:** Cambiar target a `fire_spread = target - current`
2. **Si canales meteorologicos bajos:** Probar feature engineering (wind × slope)
3. **Si muchas muestras stable:** Data augmentation con fire growth sintetico
4. **Para v16/v17:** Probar sin PrevFireMask como input (forzar aprendizaje meteorologico)
