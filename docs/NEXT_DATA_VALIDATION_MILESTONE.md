# Siguiente hito: paquete de datos para validación científica

**Objetivo:** nutrir el MVP con una secuencia real o semirreal auditable que
permita ejecutar el pipeline completo y medir si la reconstrucción del frente es
defendible. El frontend queda fuera de este hito.

## Decisión principal

El siguiente trabajo no es mejorar la interfaz ni añadir predicción. Es crear un
paquete mínimo de datos que convierta el MVP en una evaluación científica:

```text
secuencia georreferenciada -> máscaras/anotaciones -> FrontObservation
-> llegada inferida -> velocidad local -> métricas contra referencia independiente
```

El repositorio ya demuestra el flujo con datos sintéticos y un fixture GeoTIFF.
Lo que todavía falta es una secuencia con suficiente trazabilidad para validar
el método fuera del caso generado por nosotros.

## Alcance del hito

### Entrada mínima aceptable

Una secuencia candidata debe incluir:

- 3 a 10 timestamps del mismo evento;
- imágenes térmicas, RGB ortorrectificadas o máscaras ya georreferenciadas;
- CRS proyectado, transform affine y resolución espacial conocida;
- timestamp UTC inferible o manifiesto explícito;
- una máscara observada por timestamp;
- una anotación independiente del frente para al menos 2 timestamps;
- separación clara entre datos usados para calibrar umbrales y datos usados para
  evaluar.

Si no hay CRS proyectado o resolución métrica, la secuencia puede servir para
segmentación, pero no para validar velocidad en `m/min`.

### Salidas obligatorias

El hito debe producir:

- `data/candidates/<dataset_id>/README.md` con procedencia, licencia, sensor,
  resolución, CRS, timestamps y limitaciones;
- `data/candidates/<dataset_id>/images/` y `masks/` o un script reproducible
  que los genere;
- `data/candidates/<dataset_id>/annotations/` con referencia independiente del
  frente cuando exista;
- `outputs/<dataset_id>/ingest_manifest.csv`;
- `outputs/<dataset_id>/observations_manifest.csv`;
- `outputs/<dataset_id>/fronts.geojson`;
- `outputs/<dataset_id>/arrival_time.csv`;
- `outputs/<dataset_id>/local_speeds.csv`;
- `outputs/<dataset_id>/summary.json`;
- una breve auditoría en `docs/REAL_SEQUENCE_AUDIT_<dataset_id>.md`.

## Candidatos de datos

| Prioridad | Fuente | Uso esperado | Decisión pendiente |
|---:|---|---|---|
| 1 | FLAME 3 completo | Validación principal si incluye pose, timestamps y escala métrica | Solicitar/acceder y auditar metadatos |
| 2 | Quema controlada ortorrectificada propia o colaborativa | Mejor opción si se puede anotar frente independiente | Definir protocolo de captura/anotación |
| 3 | WIT-UAS-ROS | Posible secuencia con telemetría en ROS bags | Auditar sincronización, pose y escala |
| 4 | NASA AMS | Baseline de segmentación multiespectral | No asumir velocidad táctica ni ground truth |
| 5 | `semireal_controlled_001` | Ensayo local del flujo con anotaciones independientes generadas | Ejecutado; ver `docs/REAL_SEQUENCE_AUDIT_semireal_controlled_001.md` |
| 6 | Fixture GeoTIFF actual | Test de plumbing y regresión | Mantener, pero no usar como validación real |

## Trabajo técnico

1. Crear un evaluador de dataset candidato.
   - Comprueba CRS, transform, resolución, timestamps, número de frames,
     tamaño de máscaras y fracción positiva.
   - Clasifica el dataset como `ready_for_dynamics`, `segmentation_only` o
     `rejected`.
   - Primera implementación: `scripts/audit_dataset_candidate.py`.

2. Añadir soporte para anotaciones independientes.
   - Leer referencia de frente desde GeoJSON interno o máscara separada.
   - Mantenerla como `ground_truth` o referencia de evaluación, no como
     observación.
   - Calcular distancia media, P95 y Hausdorff contra la referencia.
   - Primera implementación: `scripts/audit_dataset_candidate.py --annotations`
     acepta máscaras GeoTIFF independientes emparejadas por nombre y calcula
     métricas de distancia cuando los timestamps coinciden.

3. Ejecutar el pipeline sobre el candidato.
   - Usar `python -m wildfire_front ingest-geotiff`.
   - Revisar abstenciones de velocidad y razones.
   - No reportar exactitud si la referencia independiente no existe.

4. Escribir auditoría de resultado.
   - Qué se aceptó, revisó o rechazó.
   - Qué métricas son defendibles.
   - Qué incertidumbre domina.
   - Qué datos faltan para pasar a una validación fuerte.
   - `scripts/audit_dataset_candidate.py --markdown-output` genera un informe
     Markdown reproducible a partir de `candidate_audit.json`.
   - `scripts/verify_data_validation_milestone.py` verifica que el candidato,
     outputs, auditoría y políticas científicas mínimas están presentes.

## Criterios de aceptación

El hito se considera completo cuando:

1. Existe al menos un paquete de datos candidato documentado.
2. El paquete pasa la ingesta GeoTIFF o queda clasificado con una razón
   auditable.
3. Si hay referencia independiente, se calculan métricas de distancia de frente.
4. Si no hay referencia independiente, el informe lo declara explícitamente y no
   reporta exactitud.
5. La velocidad sólo se reporta cuando hay CRS proyectado, timestamps crecientes
   y movimiento observable por encima de la incertidumbre.
6. Se conserva la separación `observed`, `inferred` y `ground_truth`.
7. El fixture sintético sigue pasando como regresión.
8. La auditoría final recomienda el siguiente dato o mejora técnica concreta.

## Lo que no toca todavía

- Frontend o dashboard avanzado.
- Predicción de propagación futura.
- Modelo físico de viento, pendiente y combustible.
- Entrenamiento de segmentadores complejos.
- Uso operacional.

## Próxima acción recomendada

Empezar por una de estas dos rutas:

1. **Ruta FLAME 3:** solicitar o localizar el paquete completo, verificar si trae
   timestamps, pose, calibración y escala métrica, y convertir una secuencia
   mínima al contrato GeoTIFF.
2. **Ruta semirreal controlada:** construir una secuencia pequeña con GeoTIFFs
   ortorrectificados y anotaciones manuales independientes para validar el
   evaluador antes de depender de un dataset externo.

La ruta semirreal es la más rápida para desbloquear código y métricas. La ruta
FLAME 3 es la más importante para defender el proyecto científicamente.

## Comando de auditoría inicial

```powershell
python scripts\audit_dataset_candidate.py `
  --images data\candidates\<dataset_id>\images `
  --masks data\candidates\<dataset_id>\masks `
  --annotations data\candidates\<dataset_id>\annotations `
  --output outputs\<dataset_id>-audit `
  --markdown-output docs\REAL_SEQUENCE_AUDIT_<dataset_id>.md `
  --event-id <dataset_id> `
  --sensor-id thermal_or_rgb `
  --estimated-error-m 2.0
```

Si no existen anotaciones independientes, omitir `--annotations`. En ese caso el
auditor puede clasificar el candidato, pero no debe reportar exactitud de
frente.

## Comando de verificación del hito

```powershell
python scripts\verify_data_validation_milestone.py `
  --dataset-dir data\candidates\<dataset_id> `
  --audit-dir outputs\<dataset_id>-audit `
  --pipeline-dir outputs\<dataset_id> `
  --audit-doc docs\REAL_SEQUENCE_AUDIT_<dataset_id>.md `
  --json-output outputs\<dataset_id>-audit\milestone_verification.json
```

## Sprint reproducible local

Para repetir el ensayo completo con `semireal_controlled_001`:

```powershell
python scripts\run_data_validation_sprint.py
```

Este comando regenera el candidato, crea auditoría JSON y Markdown, ejecuta el
pipeline GeoTIFF, verifica el hito y lanza la suite de tests.
