# Auditoría inicial de datasets para el MVP

**Fecha:** 2026-06-10  
**Objetivo:** elegir una secuencia que permita evaluar frente, tiempo de llegada y velocidad en unidades métricas.

## Criterios

- `Sí`: disponibilidad confirmada por documentación o inspección.
- `Parcial`: existe, pero no cubre todo el dataset o no basta para el MVP.
- `No`: el recurso no ofrece ese elemento.
- `?`: debe verificarse accediendo a los datos completos.

## Matriz inicial

| Recurso | Radiométrico | RGB sincronizado | Secuencia | Timestamps | Pose/calibración | CRS/escala métrica | Etiqueta de frente | Ground truth de velocidad | Acceso actual | Veredicto |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| FLAME 3 | Sí | Sí | Sí | ? | ? | ? | Parcial | ? | Una quema en Kaggle; seis bajo solicitud | Primer candidato a auditar |
| NASA AMS | Parcial | Multiespectral | Parcial | Parcial | ? | ? | Máscara de fuego activo | No | Bloqueado por cuota Git LFS | Baseline de segmentación |
| ActiveFire | No | No | No | No útil | No | Parches Landsat | Máscara de fuego activo | No | Repositorio descargado; datos externos | Solo firmas espectrales |
| TS-SatFire | No | No | Diario | Sí | No aplica | Sí | Fuego activo/área quemada | No táctica | Paper y dataset publicado | Línea estratégica |
| Next Day Wildfire Spread | No | No | Diario | Sí | No aplica | Raster | Área quemada/progresión | No táctica | Público | Baseline estratégico |
| WildFireVQA | Sí | Sí | Parcial | ? | ? | ? | Tareas derivadas | No confirmado | Público | Auxiliar, no MVP |
| WIT-UAS-ROS | Sí, LWIR | ? | Sí | Sí | Probable en ROS bags | ? | No, etiquetas de activos | No | Público | Auditar metadatos |

## Resultado

Ningún recurso está todavía confirmado como suficiente para el MVP completo.

El orden de investigación recomendado es:

1. solicitar acceso al conjunto completo de FLAME 3 y pedir explícitamente pose, calibración, timestamps y productos georreferenciados;
2. inspeccionar los ROS bags de WIT-UAS para confirmar pose y sincronización;
3. buscar una colaboración para capturar o anotar una quema controlada si ninguno aporta ground truth métrico;
4. usar NASA AMS y ActiveFire únicamente para desarrollar baselines de segmentación mientras se resuelve el dato temporal.

## Preguntas de acceso para FLAME 3

1. ¿Se incluyen timestamps originales para cada frame RGB y térmico?
2. ¿Se incluye telemetría de vuelo o pose de cámara por frame?
3. ¿Se publican calibraciones intrínsecas y extrínsecas?
4. ¿Las imágenes nadir están ortorrectificadas?
5. ¿Existe una transformación a coordenadas de terreno?
6. ¿Se incluyen anotaciones temporales del frente o perímetro?
7. ¿Qué licencia aplica al conjunto completo?

## Condición de selección

Una secuencia se acepta para el MVP solo si permite calcular y auditar:

```text
pixel -> coordenada métrica -> frente(t) -> desplazamiento normal -> velocidad
```

Si falla la transformación a coordenadas métricas, la secuencia puede utilizarse para segmentación, pero no para validar dinámica del frente.
