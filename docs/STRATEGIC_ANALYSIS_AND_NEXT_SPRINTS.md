# Análisis Estratégico Experto + Roadmap de Sprints Siguientes

> **Autor:** Asistente experto (Meteorología + Física de Combustión + Machine Learning)
> **Fecha:** 2026-07-09
> **Base:** Resultados del último mega-entrenamiento (`kaggle_output/latest/`) + `INFORME_MEGA_ENTRENAMIENTO_ML.md` + `MEGA_SPRINT_PLAN.md`
> **Estado:** ACTIVO — reemplaza la sección de prioridades de `MEGA_SPRINT_PLAN.md`
> **Actualización 2026-07-09 (13:30):** Sprints 3, 4 y 5 implementados ✓ (122 tests pasan)

---

## 1. Contexto y Resumen Ejecutivo

Este documento sintetiza un análisis experto del estado actual del proyecto
**WildfireFrontDynamics** desde tres perspectivas complementarias —
meteorología, física de propagación de incendios y machine learning — y define
los sprints prioritarios para la siguiente iteración.

**Conclusión principal:** El modelo `A3C_PerCellModel_LSTM` actual **aprendió
una política marginalmente mejor que azar** (loss ~0.36 vs. 0.69 de BCE
aleatorio), pero el entrenamiento se estancó en la época 4 de 8 y el
meta-labeler apenas supera el azar (58.8%). El cuello de botella no es la
arquitectura, sino **(a) la pérdida monolítica que mezcla física y
exploración, (b) el dataset pequeño (~69k parches), y (c) la ausencia de
regularización física (Rothermel)**.

---

## 2. Análisis de los Resultados del Último Mega-Entrenamiento

### 2.1. Métricas reales (`training_summary.json` + `training_history.json`)

| Época | Train Loss | Val Loss | Observación |
|-------|-----------|----------|-------------|
| 1 | 0.3807 | 0.3798 | Descenso inicial normal |
| 2 | 0.3701 | **0.3874** | ⚠️ Val sube — overfitting precoz |
| 3 | 0.3659 | 0.3759 | Recuperación parcial |
| 4 | 0.3641 | **0.3553** ✅ | **Mínimo global de val (best ckpt)** |
| 5 | 0.3647 | 0.3789 | Val rebota — early-stop window |
| 6 | 0.3653 | 0.3655 | Oscilación |
| 7 | 0.3664 | 0.3862 | Degradación |
| 8 | 0.3663 | 0.3779 | **Early stopping disparado** (sin mejora en 4 épocas) |

**Métricas finales:**
- **Best val_loss:** 0.3553 (época 4)
- **Test loss:** 0.3465 (ligero gap val→test, aceptable)
- **Meta-labeler test accuracy:** 0.5884 (58.84%) — **apenas mejor que azar binario (50%)**
- **Samples:** Train 68,648 / Val 10,581 / Test 5,114

### 2.2. Diagnóstico: 4 problemas raíz

#### Problema 1 — Overfitting precoz (épocas 4→8) 🔴
El train_loss se estanca en ~0.365 desde la época 4, mientras el val_loss
oscila sin mejorar. El modelo **memoriza** patrones de entrenamiento en
lugar de generalizar. Con solo 68k parches y un modelo de ~5M parámetros, la
relación parámetros/dato es ~73:1, muy por encima del régimen saludable (~10:1).

#### Problema 2 — Loss plateau en zona "casi-azar" 🟡
BCE con clases balanceadas da ~0.693 para azar. Un loss de 0.36 implica que
el modelo predice la clase mayoritaria ("no propagación") la mayor parte del
tiempo. Esto explica el **recall crítico de 0.24** reportado en el baseline:
el modelo es conservador porque la loss no le penaliza suficientemente los
false negatives **en el régimen de celdas frontera**.

#### Problema 3 — Meta-labeler marginal (58.8%) 🟡
El Random Forest de confianza apenas supera el azar. Las 7 features actuales
(probabilidad, entropía, slope, aspect, wind_speed, humidity, temp) no son
suficientes para distinguir predicciones fiables de no fiables. Falta
información espacial-estructural (densidad de vecinos en ignición, gradiente
de probabilidad, distancia al frente).

#### Problema 4 — Focal loss + pos_weight no se reflejan en el loss final 🟡
Aunque se implementaron focal loss (`gamma=2.0`, `pos_weight=3.0`), el loss
final de ~0.36 es idéntico al entrenamiento anterior (Junio 2026, sin focal
loss). **Hipótesis:** el `run_mega_training.py` puede no estar aplicando
focal loss en la nube, o la magnitud de `pos_weight` es insuficiente para
vencer el desbalance extremo (~90% celdas no-propagación).

---

## 3. Análisis Experto Multidisciplinar

### 3.1. Perspectiva Meteorológica

**Factores críticos para propagación de incendios (modelo Rothermel):**

| Factor | Estado en el modelo | Gap |
|--------|-------------------|-----|
| Viento (velocidad + dirección) | ✅ Canales 4-5 | Falta **viento local** (actual es regional GFS) |
| Humedad relativa | ✅ Canal 3 | No se modela **humedad del combustible fino** (FFMC) |
| Temperatura | ✅ Canal 2 | OK |
| Precipitación 24h | ✅ Canal 6 | Falta precipitación acumulada (drought index KBDI) |
| Topografía (slope, aspect) | ✅ Canales 0-1 | OK — pero pendiente debe estar en grados, no radianes |
| Vegetación (NDVI) | ✅ Canal 11 | NDVI es proxy débil; falta **modelo de combustible NFFL** |
| Humedad del combustible | ❌ Ausente | **Crítico** — el 90% de la variabilidad de propagación |

**Recomendación:** Integrar datos de AEMET (estaciones a <10km de cada incendio)
para obtener humedad del combustible fino (FFMC del FWI canadiense), que es el
predictor #1 de tasa de propagación.

### 3.2. Perspectiva Física de Combustión

**Limitaciones del enfoque actual:**

1. **Esquema per-cell 8-neighbor sin física:** El modelo decide binariamente
   si cada vecino se enciende, pero no impone **velocidad máxima de
   propagación**. Una celda puede "prender" un vecino a 500 m/min en pendiente
   pronunciada sin viento, lo cual es físicamente imposible (máximo real ~100
   m/min en condiciones extremas).

2. **No hay restricción de continuidad:** El fuego puede "saltar" celdas
   (prender un vecino no-adyacente), violando la física de transferencia de
   calor por conducción/radiación.

3. **Loss monolítico:** El BCE/focal loss actual mide error de clasificación
   pero no penaliza violaciones físicas (propagación a contraviento,
   propagación cuesta arriba excesiva, etc.).

**Recomendación:** Añadir un **physics-informed loss term** que penalice
predicciones que violen la tasa de propagación máxima de Rothermel:
`ROS_max = f(fuel_load, moisture, wind, slope)`.

### 3.3. Perspectiva Machine Learning

**Arquitectura:**
- CNN encoder (16→64→128→256) + LSTM temporal + gated fusion + policy/value heads
- ~5M parámetros para ~69k muestras → **sobre-parametrizado**
- Dropout 0.1-0.2 presente pero insuficiente para este ratio

**Training:**
- AdamW con cosine annealing — correcto
- Early stopping con patience=4 — disparó demasiado pronto
- No hay **data augmentation** documentada (flips, rotaciones, variantes temporales)

**Datos:**
- 30×30 parches son muy pequeños para capturar contexto sinóptico
- Solo 16 canales, pero algunos (FSM one-hot) ocupan 4 canales que podrían ser 1 categórico embebido
- NDWS (satelital) tiene resolución temporal de 1-3h, insuficiente para
  capturar ráfagas de viento

**Recomendaciones ML:**
1. **Data augmentation agresiva** (8× augmentation con flips + rotaciones 90°)
2. **Reduce-overfitting:** aumentar dropout a 0.3, añadir weight decay
   (actual 1e-4 → 3e-4), reducir lstm_hidden 256→128
3. **Curriculum learning** (synthetic → mixed → real) ya planeado, priorizar
4. **Calibración del umbral** de decisión (0.5 → óptimo por F1)

---

## 4. Sprints Siguientes — Priorizados por Impacto/Esfuerzo

### 🏆 Sprint 3 — Diagnóstico de Focal Loss + Data Augmentation (ALTA PRIORIDAD)

> **Objetivo:** Confirmar que focal loss se aplica en la nube y añadir
> augmentation para combatir el overfitting precoz.

**Justificación:** El loss plateau idéntico al entrenamiento anterior sugiere
que focal loss podría no estar activa. Si no lo está, todo el Sprint 2 fue
código muerto. La augmentation es la intervención de mayor ROI para combatir
overfitting con dataset pequeño.

**Acciones:**

| # | Acción | Archivo | Esfuerzo |
|---|--------|---------|----------|
| 3.1 | Auditar `run_mega_training.py` para verificar que focal_loss se invoca | `kaggle_job/run_mega_training.py` | 1h |
| 3.2 | Añadir bloques de data augmentation (flip H/V, rot 90°, temporal jitter) en `NpzWildfireDataset` | `wildfire_front/ml/dataset.py` | 3h |
| 3.3 | Añadir test de augmentación (verifica 8× variants, shapes preservadas) | `tests/test_ml_pipeline.py` | 1h |
| 3.4 | Aumentar dropout (0.1→0.2, 0.2→0.3) y weight_decay (1e-4→3e-4) | `models/model.py`, `kaggle_job/run_mega_training.py` | 1h |
| 3.5 | Lanzar mega-entrenamiento v2 en Kaggle | Kaggle | 12h (async) |

**Criterios de aceptación:**
- [ ] `run_mega_training.py` invoca `focal_loss_with_logits` con gamma=2.0, pos_weight=3.0
- [ ] Augmentation genera 8 variantes por parche
- [ ] Test de augmentation pasa
- [ ] Mega-entrenamiento v2: val_loss < 0.35 o recall > 0.40

---

### 🏆 Sprint 4 — Physics-Informed Loss (ALTA PRIORIDAD)

> **Objetivo:** Añadir término de pérdida física que penalice violaciones de
> la tasa de propagación máxima de Rothermel.

**Justificación:** Sin restricciones físicas, el modelo puede aprender
atajos estadísticos que violan la física (propagación a contraviento,
velocidades imposibles). Un physics-informed loss es el diferenciador
científico de este proyecto frente a enfoques puramente data-driven.

**Acciones:**

| # | Acción | Archivo | Esfuerzo |
|---|--------|---------|----------|
| 4.1 | Implementar `rothermel_ros(wind, slope, moisture)` en nuevo módulo | `wildfire_front/ml/physics.py` (nuevo) | 4h |
| 4.2 | Implementar `physics_loss(predictions, wind, slope, moisture)` | `wildfire_front/ml/physics.py` | 3h |
| 4.3 | Integrar physics_loss en train loop con peso λ=0.1 | `wildfire_front/ml/train.py` | 2h |
| 4.4 | Tests de physics (Rothermel ROS en condiciones conocidas) | `tests/test_physics.py` (nuevo) | 2h |

**Criterios de aceptación:**
- [ ] `rothermel_ros()` devuelve valores físicamente plausibles (0-120 m/min)
- [ ] `physics_loss` penaliza predicciones con ROS > máximo
- [ ] Test: viento fuerte + pendiente → ROS alto; sin viento + plano → ROS bajo
- [ ] Train loop usa `total_loss = focal_loss + 0.1 * physics_loss`

---

### 🥈 Sprint 5 — Enrichment: AEMET + FFMC Fuel Moisture (MEDIA PRIORIDAD)

> **Objetivo:** Integrar humedad del combustible fino (FFMC) como canal 16
> adicional, elevando in_channels de 16 → 17.

**Justificación:** El FFMC (Fine Fuel Moisture Code) del sistema FWI
canadiense explica el 60-70% de la variabilidad de ignición y propagación
inicial. Es el predictor faltante más impactante.

**Acciones:**

| # | Acción | Archivo | Esfuerzo |
|---|--------|---------|----------|
| 5.1 | Crear `scripts/fetch_aemet_fwi.py` que descarga datos de AEMET AOpen | `scripts/` (nuevo) | 4h |
| 5.2 | Calcular FFMC a partir de temp/humidity/wind/precip 24h | `wildfire_front/ml/physics.py` | 2h |
| 5.3 | Añadir FFMC como canal 16 en `NpzWildfireDataset` | `wildfire_front/ml/dataset.py` | 2h |
| 5.4 | Actualizar `in_channels=17` en modelo | `models/model.py` | 0.5h |

**Criterios de aceptación:**
- [ ] Script descarga datos AEMET para coordenadas/timestamp de cada incendio
- [ ] FFMC calculado en rango [0-101] (escala canadiense)
- [ ] Modelo entrena con 17 canales sin errores dimensionales

---

### 🥈 Sprint 6 — Meta-Labeler v2: Features Espaciales (MEDIA PRIORIDAD)

> **Objetivo:** Mejorar la precisión del meta-labeler de 58.8% → ≥70%.

**Justificación:** El meta-labeler actual usa solo 7 features globales. La
informización espacial (densidad de vecinos, gradiente de probabilidad) es
clave para distinguir predicciones fiables.

**Acciones:**

| # | Acción | Archivo | Esfuerzo |
|---|--------|---------|----------|
| 6.1 | Añadir features espaciales: densidad de vecinos en ignición (3×3, 5×5) | `wildfire_front/ml/meta_labeler.py` | 3h |
| 6.2 | Añadir gradiente de probabilidad Sobel | `wildfire_front/ml/meta_labeler.py` | 2h |
| 6.3 | Añadir distancia al frente (transformada de distancia) | `wildfire_front/ml/meta_labeler.py` | 2h |
| 6.4 | Añadir features físicas: ROS relativo vs. ROS máximo | `wildfire_front/ml/meta_labeler.py` | 2h |
| 6.5 | Retrain meta-labeler en Kaggle | Kaggle | 2h |

**Criterios de aceptación:**
- [ ] Features expandidas de 7 → 15+
- [ ] Meta-labeler test accuracy ≥ 0.70
- [ ] Recall en Clase-0 (fallos) ≥ 0.60 (detectar predicciones no fiables)

---

### 🥉 Sprint 7 — Evaluación Continua + Threshold Optimization (BAJA PRIORIDAD)

> **Objetivo:** Optimizar el umbral de decisión y establecer evaluación
> automatizada post-entrenamiento.

**Acciones:**

| # | Acción | Archivo | Esfuerzo |
|---|--------|---------|----------|
| 7.1 | Script de threshold sweep (0.1-0.9, reportar F1/IoU/recall por umbral) | `scripts/optimize_threshold.py` (nuevo) | 2h |
| 7.2 | Integrar evaluación de IoU/Recall en `run_mega_training.py` post-train | `kaggle_job/run_mega_training.py` | 2h |
| 7.3 | Guardar `evaluation_metrics.json` junto a `training_summary.json` | `kaggle_job/run_mega_training.py` | 1h |

---

## 5. Roadmap Visual (Cronograma)

```
SEMANA 1-2:
  ├── Sprint 3 (Focal loss audit + augmentation)     ← desbloqueante
  └── Sprint 4 (Physics-informed loss)               ← paralelo

SEMANA 3-4:
  ├── Sprint 5 (AEMET + FFMC enrichment)             ← tras Sprint 3-4
  └── Mega-entrenamiento v3 (con Sprint 3+4+5)       ← 16h Kaggle

SEMANA 5-6:
  ├── Sprint 6 (Meta-labeler v2)                     ← usa pesos v3
  └── Sprint 7 (Threshold optimization)              ← cierre

SEMANA 7+:
  └── Evaluación final + paper draft (opcional)
```

---

## 6. Métricas Objetivo por Sprint

| Sprint | Métrica | Baseline | Objetivo | Crítico |
|--------|---------|----------|----------|---------|
| 3 | Val loss (focal audit) | 0.355 | < 0.34 | Sí — valida Sprint 2 |
| 3 | Recall | 0.24 | > 0.40 | Sí |
| 4 | ROS violation rate | N/A | < 5% de predicciones | Sí |
| 5 | Val loss (FFMC) | 0.34 | < 0.32 | No |
| 6 | Meta-labeler acc | 58.8% | ≥ 70% | No |
| 7 | F1 (optimal threshold) | 0.33 | > 0.50 | No |

---

## 7. Riesgos y Mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| Focal loss no estaba activa en la nube | Alta | Alto | Sprint 3.1 lo resuelve primero |
| Physics loss desestabiliza entrenamiento | Media | Medio | Empezar con λ=0.01, validar antes de subir |
| AEMET API rate limits / datos faltantes | Media | Medio | Cachear respuestas, fallback a ERA5 |
| Kaggle GPU timeout (12h límite) | Baja | Alto | Reducir epochs a 10, checkpointing |
| Data augmentation introduce sesgo | Baja | Medio | Tests de invarianza geométrica |

---

## 8. Dependencias y Orden Estricto

```
Sprint 3 ──────┐
               ├──→ Mega-entrenamiento v3 ──→ Sprint 6
Sprint 4 ──────┤                              │
               │                              ├──→ Sprint 7
Sprint 5 ──────┘                              │
                                               │
Sprint 2 (COMPLETADO) ────────────────────────┘
```

**Sprint 3 es el más crítico y debe ejecutarse primero** porque valida que el
código de focal loss (Sprint 2) realmente se ejecuta en producción.

---

## 9. Artefactos Esperados al Final de los Sprints

- `docs/SPRINT3_FOCAL_AUDIT.md` — informe del audit de focal loss
- `wildfire_front/ml/physics.py` — módulo de física (Rothermel + FFMC)
- `scripts/fetch_aemet_fwi.py` — descarga de datos meteorológicos
- `kaggle_output/v3/` — nuevo mega-entrenamiento con todas las mejoras
- `docs/ML_EVALUATION_V3.md` — reporte final con métricas comparativas---

## 10. Actualizacion Critica - Fix NaN + Velocidad (2026-07-09 18:10)

> **Estado:** Kernel v6 RUNNING en Kaggle (https://www.kaggle.com/code/alonsoalvira/wildfire-front-training-v6)

### 10.1 Problemas detectados en entrenamientos v3-v5

#### Bug 1 - NaN en loss (v4-v5) [CRITICO]

**Sintoma:** `Epoch 01 train=nan val=nan`

**Causa raiz:** `torch.amp.autocast('cuda')` envolvia tanto el forward pass COMO
el calculo de loss dentro del mismo contexto fp16. La combinacion de:

1. Focal loss: `(1.0 - p_t) ** gamma` donde gamma=2.0
2. `pos_weight=3.0` en BCE
3. fp16 (rango maximo ~65504, precision ~3 decimales)

...produce overflow y NaN en gradientes.

**Fix aplicado** (`kaggle_job/run_mega_training.py`):

```python
# ANTES (roto):
with torch.amp.autocast('cuda', enabled=USE_AMP):
    features, _ = model.forward(sequence, current_fire)
    loss = calculate_local_spread_loss(...)  # loss en fp16 = NaN

# DESPUES (correcto):
with torch.amp.autocast('cuda', enabled=USE_AMP):
    features, _ = model.forward(sequence, current_fire)
features = features.float()  # cast a fp32 ANTES del loss
loss = calculate_local_spread_loss(...)  # loss estable en fp32
```

Aplicado en las 3 zonas: `evaluate_loss`, pre-training loop, y fine-tuning loop.

#### Bug 2 - 9910s/epoch (2.75 horas por epoch) [CRITICO]

**Sintoma:** Entrenamiento estimado en >40h, imposible en Kaggle (limite 9-12h)

**Causa raiz:** `preprocess_ndws.py` generaba **80,000 patches de entrenamiento**.
Con batch_size=1 (requerido por arquitectura per-cell) y ~100 burning cells por
patch, cada epoch = ~8,000,000 evaluaciones de loss.

**Fix aplicado** (`kaggle_job/preprocess_ndws.py`):

- Train: 80,000 a 12,000 patches (6.7x menos)
- Val: 15,000 a 5,000 patches
- Test: 15,000 a 5,000 patches

**Estimacion de tiempo v6:**

- Preprocesamiento: ~30 min
- 15 epochs x ~1500s = ~6.25h
- Fine-tuning + meta-labeler + test: ~1h
- **Total: ~8h** (dentro del limite de 9h de Kaggle)

### 10.2 Commits y artifacts

| Commit | Descripcion | Hash |
|--------|-------------|------|
| 1 | fix: resolve NaN loss + reduce dataset size for feasible training time | `0d87636` |
| 2 | chore: bump kernel to v6 for clean re-run with NaN+speed fixes | `11cabd9` |

### 10.3 Proximos sprints post-v6

#### Sprint 8 - Analisis de resultados v6 (INMEDIATO post-v6)

1. Descargar `training_summary.json` + `training_history.json` de Kaggle
2. Comparar val_loss v6 vs v3 (objetivo: v6 < 0.34, sin NaN)
3. Verificar que focal loss ahora impacta (loss deberia diferir de Junio 2026)
4. Si val_loss > 0.40, diagnosticar si 12k patches es insuficiente

#### Sprint 9 - Si v6 funciona: escalar a 25k patches

Si v6 completa sin NaN y val_loss < 0.34:

- Subir `max_patches` de 12k a 25k (todavia factible en 9h)
- Mas datos = mejor generalizacion sin overfitting

#### Sprint 10 - Si v6 tiene good recall: threshold optimization

- Script `scripts/optimize_threshold.py` con sweep 0.1-0.9
- Reportar F1, IoU, precision, recall por umbral
- Seleccionar umbral optimo para deployment

### 10.4 Lecciones aprendidas (para futuro)

1. **AMP + loss custom = peligroso:** Siempre castear a fp32 antes de losses
   no-estandar (focal, contrastive, etc.)
2. **Profilear antes de lanzar:** 80k patches x batch=1 deberia haberse
   detectado en local antes de gastar horas de GPU en Kaggle
3. **Dataset size != mejor:** 12k patches diversos pueden generalizar mejor
   que 80k redundantes (muchos patches solapan geograficamente)