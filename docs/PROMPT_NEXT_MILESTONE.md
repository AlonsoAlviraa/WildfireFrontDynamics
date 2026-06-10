# Prompt para el siguiente hito: primer adaptador geoespacial real

**Estado:** completado y auditado el 2026-06-10.
**Evidencia:** `docs/COMPLETION_AUDIT_GEOTIFF.md`.

Usa el siguiente prompt en una nueva sesión de Codex dentro de este workspace.

---

## Prompt

Trabaja en `C:\Users\alonso.alvira\WildfireFrontDynamics` hasta implementar y
verificar el siguiente hito completo:

> Sustituir el generador sintético por un adaptador reproducible de GeoTIFF y
> máscara georreferenciada, capaz de producir `FrontObservation`, ejecutar la
> reconstrucción existente y generar el dashboard sin depender de verdad
> sintética.

Antes de editar:

1. ejecuta `pwd`, `git status --short --branch` y lista los archivos;
2. lee `README.md`, `docs/MVP_ARCHITECTURE.md`, `docs/PROVENANCE.md`,
   `ESTUDIO_FIRE_FRONT_TRACKER.md` y `AUDITORIA_DATASETS_MVP.md`;
3. ejecuta `scripts\run_mvp.cmd` para establecer el baseline;
4. inspecciona los módulos externos indicados abajo antes de reutilizar ideas.

### Módulos descargados que debes aprovechar

Usa estas fuentes como referencias y adapta únicamente las piezas necesarias:

- `external/DetectorDeIncendios/src/data_prep/ingesta_pipeline.py`
  - reutilizar los patrones de SHA-256, timestamps, estados
    `accepted/review/rejected` y manifiestos;
- `external/DetectorDeIncendios/src/data_prep/sample_identity.py`
  - conservar identidad estable y trazable;
- `external/nasa-ams/AMS_dataset_processing.py`
  - estudiar `get_geotransform`, interpolación, CRS y escritura geoespacial;
- `external/nasa-ams/dataset_utils.py`
  - estudiar lectura multibanda y procesado de máscaras;
- `external/nasa-ams/combined_algorithm.py`
  - conservar conceptualmente la separación clasificador/segmentador, sin
    incorporarla aún como dependencia;
- `external/activefire/src/utils/cnn/generator.py`
  - adaptar la lectura de imagen y máscara con `rasterio`.

No importes módulos desde `external/` en tiempo de ejecución. Están ignorados por
Git y algunos usan TensorFlow/Keras antiguos. Toda adaptación debe vivir dentro
de `wildfire_front/`, tener pruebas propias y quedar documentada en
`docs/PROVENANCE.md`.

### Alcance obligatorio

1. **Dependencias geoespaciales**
   - añade únicamente dependencias justificadas, preferentemente `rasterio`;
   - no añadas TensorFlow, GDAL directo ni modelos entrenados en este hito;
   - conserva el MVP sintético funcionando.

2. **Refactor de contratos**
   - permite crear `FrontObservation` real sin `truth_points`;
   - representa explícitamente CRS, URI de origen, SHA-256, resolución y error;
   - diferencia observación real, verdad sintética y ground truth opcional;
   - evita valores ficticios cuando un metadato no exista.

3. **Ingesta GeoTIFF**
   - crea `wildfire_front/ingestion/geotiff.py`;
   - valida que imagen y máscara sean legibles, tengan dimensiones compatibles,
     transformación y CRS;
   - conserva TIFF sin convertirlo a JPEG;
   - calcula SHA-256;
   - produce un manifiesto de aceptados, revisión y rechazados con razones
     auditables;
   - rechaza o marca para revisión rasters sin georreferenciación.

4. **Baseline de segmentación**
   - crea un baseline determinista basado en umbral sobre una banda elegida;
   - soporta también una máscara binaria suministrada;
   - separa lectura, segmentación y extracción de geometría;
   - no llames “frente activo” a cualquier zona caliente: etiqueta el método y
     sus limitaciones.

5. **Extracción y proyección del frente**
   - extrae el contorno exterior de la máscara;
   - transforma coordenadas píxel a coordenadas del raster usando su affine
     transform;
   - conserva `LineString` o múltiples componentes cuando proceda;
   - no presupongas que todos los frentes son radiales o están centrados en
     `(0, 0)`;
   - si la reconstrucción actual no soporta una geometría, abstente con una
     razón explícita en vez de producir una velocidad falsa.

6. **CLI**
   - conserva `python -m wildfire_front demo`;
   - añade un comando similar a:

     ```powershell
     python -m wildfire_front ingest-geotiff `
       --images data\sample\images `
       --masks data\sample\masks `
       --output outputs\geotiff-demo `
       --sensor-id thermal_demo `
       --estimated-error-m 2.0
     ```

   - los errores de entrada deben terminar con mensajes claros y código distinto
     de cero.

7. **Fixture reproducible**
   - genera mediante tests un pequeño GeoTIFF multibanda y máscaras
     georreferenciadas; no dependas de internet ni de datos pesados;
   - incluye al menos dos timestamps para probar orden temporal;
   - incluye casos inválidos: sin CRS, dimensiones incompatibles y máscara vacía.

8. **Salidas visuales**
   - integra el nuevo flujo con los artefactos existentes;
   - el dashboard debe indicar fuente, CRS, resolución, método, error declarado,
     número de componentes y abstenciones;
   - no muestres métricas contra verdad cuando no exista ground truth.

9. **Documentación**
   - actualiza `README.md`, `docs/MVP_ARCHITECTURE.md` y
     `docs/PROVENANCE.md`;
   - crea `docs/GEOTIFF_INPUT_CONTRACT.md` con estructura de carpetas, esquema de
     nombres/timestamps, bandas, máscara, CRS y limitaciones;
   - explica qué se reutilizó de cada repositorio externo y qué se descartó.

### Restricciones científicas

- No presentes una máscara caliente como frente validado.
- No calcules `m/min` si falta timestamp, CRS métrico o movimiento observable.
- No uses GeoJSON con coordenadas proyectadas sin declarar claramente que es una
  exportación interna no conforme con RFC 7946; usa preferentemente GeoPackage,
  GeoParquet o documenta la limitación actual.
- No conviertas datos radiométricos a 8 bits.
- Mantén `observed`, `inferred` y `ground_truth` separados.

### Criterios de aceptación

El hito solo está completo cuando exista evidencia de todos estos puntos:

1. `scripts\run_mvp.cmd` sigue pasando.
2. Todos los tests nuevos pasan con `python -m unittest discover -s tests -v`.
3. El adaptador acepta un GeoTIFF georreferenciado válido y genera una
   observación con coordenadas métricas correctas.
4. El adaptador rechaza o pone en revisión entradas sin CRS, con tamaños
   incompatibles o máscaras vacías.
5. La CLI genera manifiesto, geometrías, resumen y dashboard desde el fixture.
6. El pipeline se abstiene de calcular velocidad cuando falten condiciones.
7. No existen imports en `wildfire_front/` que apunten a `external/`.
8. `git diff --check` no informa errores.
9. La procedencia y las limitaciones están documentadas.

Antes de finalizar, realiza una auditoría requisito por requisito y comunica:

- archivos creados/modificados;
- comandos de verificación ejecutados;
- resultados y métricas;
- limitaciones restantes;
- siguiente dato real recomendado.

---

## Resultado esperado

Tras completar este prompt, el proyecto habrá pasado de demostrar únicamente la
matemática sintética a aceptar un contrato geoespacial real y auditable. El hito
posterior será conectar una secuencia real de FLAME 3, NASA AMS o una quema
controlada que cumpla dicho contrato.
