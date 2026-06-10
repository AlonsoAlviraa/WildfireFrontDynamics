# Auditoría de la iteración científica

**Fecha:** 2026-06-10

## Resultado

La iteración mejora datos, modelos y robustez sin cambios de frontend.

| Área | Evidencia |
|---|---|
| Datos | SHA-256 duplicado, timestamps duplicados, coherencia de CRS/resolución, fracción positiva y baseline MAD |
| Modelo | Velocidad no radial mediante normales exteriores y asociación uno a uno de componentes |
| Abstención | Gates por incertidumbre, curvatura, consistencia geométrica y cobertura |
| Evaluación | Distancias media, P95 y Hausdorff; MAE sólo cuando existe ground truth |
| Robustez | Validación de observaciones y 26 tests automatizados |

## Demo reproducible

`scripts/run_mvp.cmd` genera demos sintética y GeoTIFF y ejecuta la suite.

Resultado de la demo GeoTIFF:

- 3 de 3 entradas aceptadas;
- 2 pares de componentes emparejados;
- 230 muestras locales, 54 observables;
- velocidad mediana: 10.0 m/min;
- velocidad P95: 10.54 m/min;
- abstenciones locales registradas por motivo.

Estos valores verifican el flujo, no la exactitud sobre incendios reales.

Resultado sintético:

- distancia media de frente: 0.362 m;
- distancia P95: 0.913 m;
- Hausdorff: 1.473 m;
- MAE de velocidad radial observable: 0.574 m/min.

## Pruebas cubiertas

- expansión rectangular no radial;
- movimiento bajo incertidumbre;
- nuevas igniciones y asociación uno a uno;
- CRS no métrico;
- estabilidad frente a remuestreo y orientación;
- métricas de distancia y detección de reducción de área;
- QA de duplicados, timestamps y resolución;
- segmentación robusta MAD.

## Riesgo residual

El estimador aún no está validado con ground truth independiente de incendios
reales. No debe utilizarse como herramienta operacional ni interpretar el borde
de una máscara como frente de llama confirmado.
