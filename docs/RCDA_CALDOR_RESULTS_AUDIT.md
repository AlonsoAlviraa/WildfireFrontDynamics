# Auditoría de resultados RCDA y readiness Caldor

Fecha: 2026-08-16  
Artefacto machine-readable: `docs/RCDA_CALDOR_RESULTS_AUDIT.json`

## Veredicto ejecutivo

El IoU RCDA de 0,3083 es débil para localizar crecimiento diario, aunque aporta
señal real frente a una dilatación geométrica: en el mismo TEST upstream, la
mejor dilatación diagnóstica alcanza solo IoU 0,1111. El modelo funciona cerca
del frente y se degrada con crecimiento lejano, saltos y cambios de escala.

La cifra publicada no es una estimación independiente: checkpoint, threshold y
dos extremos de normalización usan TEST; además, `UID_FIRE_656` cruza
TRAIN/TEST. Hace falta reentrenar sobre el split sellado antes de juzgar la
arquitectura RCDA.

Caldor no tiene un score pobre: todavía no existe un checkpoint compatible ni
un tensor clean17 evaluable. Los 171 GeoTIFF pasan la auditoría espacial, pero
el paquete falla disponibilidad temporal y no debe usarse para model IoU.

## RCDA: qué está ocurriendo

### Desbalance y dispersión

- Solo el 1,0214 % de los 106.823.680 píxeles TEST corresponde a crecimiento.
- Un predictor siempre negativo obtiene accuracy 0,989786; RCDA obtiene
  0,989476. Accuracy no sirve como KPI para esta tarea.
- 154/1.630 escenas tienen IoU cero y 423/1.630 quedan por debajo de 0,1.
- A nivel incendio, 6/184 tienen IoU cero y 21/184 quedan por debajo de 0,1.
- IoU mediano por escena: 0,2472. IoU mediano por incendio: 0,2818.
- El año 2017 es el peor dominio: IoU 0,2682, frente a 0,3428 en 2015.

### El fallo principal es la distancia al frente

| Distancia desde el perímetro `t0` | IoU | Recall |
|---|---:|---:|
| 0–1,5 px | 0,5828 | 0,8219 |
| 1,5–3,5 px | 0,4722 | 0,7594 |
| 3,5–5,5 px | 0,3798 | 0,6547 |
| 5,5–10,5 px | 0,2973 | 0,5092 |
| >10,5 px | 0,1154 | 0,1527 |

RCDA aprende una expansión local del frente, pero casi no captura propagación
lejana/spotting. Para crecimientos de 1–99 píxeles produce recall 0,6165 pero
precisión 0,1361; para crecimientos ≥2.000 píxeles la precisión sube a 0,6812
y el recall cae a 0,4091. Es regresión hacia una escala de crecimiento media.

### Probabilidades casi binarias

- 98,9873 % de los píxeles reciben probabilidad ≤0,01.
- 0,9324 % reciben probabilidad ≥0,99.
- Solo 0,0154 % cae entre 0,2 y 0,6.
- Cambiar threshold de 0,2 a 0,6 altera F1 en solo 0,000095.
- Brier RCDA: 0,010457; Brier del predictor siempre cero: 0,010214.

El ECE global de 0,01045 parece bajo porque está dominado por negativos fáciles;
no demuestra buena calibración del crecimiento. Hace falta calibración dentro
del frente candidato, AP/PR y error selectivo, no solo ECE global.

### Defectos de protocolo upstream

1. `train.py` usa TEST en cada época y guarda el checkpoint con mejor F1 TEST.
2. `eval.py` vuelve a elegir threshold sobre TEST.
3. `UID_FIRE_656` aporta 21 días TRAIN y siete días TEST adyacentes.
4. Los máximos normalizadores de viento y precipitación coinciden con TEST y no
   con TRAIN original: 13,046875 vs 12,9921875 y 0,00128398 vs 0,000680989.
5. No se declara seed, modo determinista, época del checkpoint, optimizer state
   ni log suficiente para reproducir el entrenamiento exacto.
6. El comando documentado usa DiceLoss sobre un target extremadamente escaso;
   no optimiza frontera, distancia, spotting ni calibración.

## Caldor: auditoría corregida

### Lo que sí está bien

- 15 pares y 17 canales físicos materializados.
- 171 GeoTIFF únicos con hash, CRS EPSG:32610, 30 m, dimensiones y nodata
  verificados.
- Los ciclos HRRR fueron inicializados al menos una hora antes de `t0`.
- LANDFIRE LF2020 es pre-Caldor y no se usan MTBS/RAVG como inputs.

### Bloqueantes

| Severidad | Hallazgo | Consecuencia |
|---|---|---|
| Crítica | Los 15 ERC seleccionados para el día `t0` declaran cierre a las 07 UTC del día siguiente | El valor no estaba disponible en `t0` |
| Alta | 0/15 resúmenes HRRR coinciden exactamente con `[t0,t1]` | Mezclan una media de 4,60 h anteriores a `t0` y dejan sin cubrir 4,94 h del target en promedio, hasta 9,5 h |
| Alta | Solo hay un incendio y 15 pares correlacionados | Sirve para validación externa, no para entrenar ni estimar generalización |
| Alta | No existe ningún tensor NPZ clean17 apilado | Falta orden, normalización, imputación y adapter final |
| Media | Canopy tiene 11,19 % nodata | Falta política de imputación y máscara de missingness |
| Media | Aspecto y viento se conservan como ángulos escalares | Hay discontinuidad artificial en 0/360 o −π/π; deben codificarse sin/cos |
| Media | Horizonte real 18,75–28,38 h no entra como variable | El modelo no puede ajustar la escala temporal de la propagación |
| Crítica | `legacy17` fue entrenado con slots constantes | No es compatible con `clean17_physical_v1` |

## Qué mejorar y en qué orden

### P0 — Validez antes que arquitectura

1. Reparar Caldor: elegir el último ERC realmente disponible en `t0` y agregar
   HRRR por valid time dentro de `[t0,t1]`, descargando leads >24 h cuando haga
   falta. Gate: 15/15 ERC disponibles y 15/15 ventanas exactas.
2. Reentrenar RCDA desde cero con TRAIN 5.552 / VAL 928 / TEST 1.651, todos
   disjuntos por incendio. Normalización solo TRAIN; checkpoint y threshold solo
   VAL; TEST una vez; mínimo tres seeds.
3. Evaluar copy, dilated-copy, U-Net y RCDA sobre exactamente el mismo TEST.
   Reportar micro y macro por incendio, AP, boundary F1, recall por distancia,
   calibración y casos sin crecimiento.

### P1 — Target, muestreo y loss

1. Comparar Dice con focal-Tversky + boundary/signed-distance loss.
2. Tratar explícitamente targets vacíos y balancear incendios/tamaños de
   crecimiento, no solo días aleatorios.
3. Predecir conjuntamente crecimiento, distancia/arrival time y probabilidad de
   spotting; no reducir todo a una máscara binaria.

### P1 — Información que falta al modelo

1. Incluir varios perímetros previos o un mapa de arrival time para estimar
   velocidad y aceleración.
2. Añadir horizonte exacto y secuencia meteorológica por valid time.
3. Codificar dirección del viento y aspecto con seno/coseno.
4. Añadir distancia al frente y features alineadas con normal/tangente del frente.
5. Conservar resolución efectiva de HRRR y no presentar una interpolación a
   30 m como información meteorológica de 30 m.

### P2 — Generalización y operación

1. Entrenar clean17 con múltiples incendios; mantener Caldor como holdout externo.
2. Usar ensemble de seeds, calibración en VAL y abstención OOD.
3. Exigir mejora sobre dilated-copy en event-macro IoU y en recall >10,5 px, no
   solo mejora de full-mask IoU.

## Gate recomendado para el siguiente resultado

No aceptar una nueva cifra si no cumple simultáneamente:

- separación por incendio demostrada y hashes de manifests;
- cero selección o normalización con TEST;
- mejora sobre U-Net y dilated-copy en el mismo split;
- event-macro growth IoU, AP y boundary F1 reportados;
- recall por distancia, especialmente >10,5 px;
- tres seeds con intervalo de confianza;
- auditoría temporal Caldor en PASS antes de cualquier model IoU Caldor.
