# V14 Resultados y Analisis — Loop Engineering Edition

**Fecha:** 2026-07-10
**Kernel:** https://www.kaggle.com/code/alonsoalviraaaa/wildfire-front-training-v14
**GPU:** T4 x2
**Tiempo de entrenamiento:** 4.4 minutos (18 epochs + early stopping)

## Resumen Ejecutivo

El experimento v14 logro un **salto cuantico** respecto a todas las versiones anteriores (v10-v12), multiplicando el IoU por **125x** y superando los criterios de aceptacion en IoU y Recall.

## Configuracion

| Parametro | Valor |
|-----------|-------|
| Modelo | WildfireUNetSmall (3 niveles, bottleneck 8x8) |
| Parametros | 1,076,385 |
| Loss | Composite (BCE w=5 + Dice 0.3 + Tversky 0.3) |
| Optimizer | AdamW (lr=1e-3, wd=1e-4) |
| Scheduler | LinearWarmup(3) + CosineAnnealing |
| EMA | decay=0.999 |
| Batch size | 32 |
| Patch size | 64x64 (full grid) |
| Train/Val/Test | 7900 / 1303 / 619 muestras |

## Resultados en Test

### Mejor threshold (0.3 — maximiza recall)

| Metrica | v12 (anterior) | **v14** | Mejora |
|---------|---------------|---------|--------|
| IoU (micro) | 0.002 | **0.229** | **125x** |
| Dice (micro) | 0.004 | **0.372** | **93x** |
| Precision (micro) | 0.161 | **0.266** | 1.7x |
| Recall (micro) | 0.002 | **0.618** | **309x** |

### Threshold 0.5 (balance precision/recall)

| Metrica | v12 | **v14** |
|---------|-----|---------|
| IoU (micro) | 0.002 | **0.239** |
| Dice (micro) | 0.004 | **0.385** |
| Precision | 0.161 | **0.293** |
| Recall | 0.002 | **0.564** |

### Threshold 0.6 (maximiza precision)

| Metrica | v12 | **v14** |
|---------|-----|---------|
| IoU (micro) | 0.002 | **0.242** |
| Precision | 0.161 | **0.308** |
| Recall | 0.002 | **0.533** |

## Evolucion del entrenamiento

```
Epoch 01: IoU@0.5=0.030  Recall=0.720  (warmup, lr subiendo)
Epoch 03: IoU@0.5=0.177  Recall=0.627  (lr pico, gran salto)
Epoch 05: IoU@0.5=0.240  Recall=0.595  (convergiendo rapido)
Epoch 08: IoU@0.5=0.255  Recall=0.596  (BEST val_loss=0.1124)
Epoch 18: Early stopping (IoU@0.5=0.266, val loss estabilizada)
```

**Observacion clave:** El modelo converge muy rapido (epoch 3 ya tiene IoU 0.177) gracias al warmup + cosine schedule.

## Criterios de Aceptacion

| Criterio | Objetivo | **v14** | Estado |
|----------|----------|---------|--------|
| IoU | >0.15 | **0.239** | SUPERADO |
| Recall | >0.30 | **0.564** | SUPERADO |
| Precision | >0.30 | 0.293 | CASI (0.308 @ thresh=0.6) |
| Dice | >0.25 | **0.385** | SUPERADO |
| best_epoch | >10 | **8** | NO (converge muy rapido) |

## Analisis de que funciono

1. **64x64 patches (no 30x30):** El bottleneck ahora es 8x8 en lugar de 1x1, preservando informacion espacial.
2. **Composite loss:** BCE sola no era suficiente. Dice + Tversky forzan al modelo a aprender limites del fuego.
3. **3 niveles U-Net (no 4):** Reduce sobre-parametrizacion y mejora gradient flow.
4. **Warmup + Cosine:** El warmup de 3 epochs evita inestabilidad inicial.
5. **EMA:** Estabiliza las predicciones en validacion.

## Siguientes pasos del loop

- **v15:** U-Net Small + SE Attention (probar si la atencion mejora precision)
- **v16:** U-Net Full (4.3M params) — mas capacidad para mejor precision
- **v17:** Focal loss (gamma=3) — mejor manejo de ejemplos dificiles
- **v18:** Pos weight tuning (probar pos_weight=10 o 15)