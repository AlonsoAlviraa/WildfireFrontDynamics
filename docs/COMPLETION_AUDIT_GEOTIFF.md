# Auditoría de finalización del adaptador GeoTIFF

> Auditoría histórica del primer adaptador. La abstención global descrita aquí
> fue sustituida por el estimador no radial conservador documentado en
> `SCIENTIFIC_ITERATION_AUDIT.md`.

**Fecha:** 2026-06-10
**Prompt auditado:** `docs/PROMPT_NEXT_MILESTONE.md`

## Evidencia por criterio de aceptación

| Criterio | Estado | Evidencia |
|---|---|---|
| `scripts/run_mvp.cmd` sigue pasando | Cumplido | Ejecuta 12 tests, demo sintética y demo GeoTIFF |
| Todos los tests nuevos pasan | Cumplido | `python -m unittest discover -s tests -v`: 12 tests OK |
| GeoTIFF válido produce coordenadas métricas | Cumplido | `test_valid_projected_sequence_produces_metric_observations` comprueba EPSG:32630, 10 m y coordenadas affine |
| Entradas inválidas se auditan | Cumplido | `test_invalid_inputs_are_audited` cubre falta de CRS, dimensiones incompatibles y máscara vacía |
| CLI genera manifiesto, geometrías, resumen y dashboard | Cumplido | `test_cli_flow_generates_complete_real_artifacts_and_abstains` y `outputs/geotiff-demo/` |
| Pipeline se abstiene cuando no debe calcular velocidad | Cumplido | `speed_status=abstained` y razón `non_radial_real_geometry_speed_estimator_not_implemented` |
| No existen imports hacia `external/` | Cumplido | búsqueda `rg` devuelve `NO_EXTERNAL_IMPORTS` |
| `git diff --check` limpio | Cumplido | ejecución sin errores |
| Procedencia y limitaciones documentadas | Cumplido | `docs/PROVENANCE.md` y `docs/GEOTIFF_INPUT_CONTRACT.md` |

## Alcance obligatorio

| Requisito | Implementación |
|---|---|
| Dependencia geoespacial mínima | `rasterio>=1.4` en `pyproject.toml`; sin TensorFlow ni GDAL directo |
| Ground truth opcional | `FrontObservation.truth_components` opcional |
| Metadatos reales | CRS, URI, SHA-256, resolución, error, método y limitaciones |
| Ingesta y QA | `wildfire_front/ingestion/geotiff.py` |
| Máscara suministrada y umbral | `read_binary_mask` y `segment_band_threshold` |
| Contornos y affine transform | `extract_mask_components` |
| Múltiples componentes | `FrontObservation.components` y `MultiLineString` interno |
| Reconstrucción no radial | `reconstruct_arrival_from_components` |
| Velocidad no defendible | Abstención explícita, sin valores `m/min` reales |
| CLI | Comandos `demo` e `ingest-geotiff` |
| Fixture reproducible | Tests y `scripts/generate_geotiff_fixture.py` |
| Dashboard real | `outputs/geotiff-demo/report.html` |

## Resultados de la demo GeoTIFF

- observaciones aceptadas: 3;
- componentes: 3;
- resolución: 5 m;
- CRS: EPSG:32630;
- celdas con llegada reconstruida: 157;
- velocidad: abstención explícita;
- entradas revisadas o rechazadas en la demo válida: 0.

## Restricciones científicas verificadas

- Las geometrías se etiquetan como bordes de máscara, no como frentes de llama validados.
- Los TIFF multibanda se leen en dtype nativo.
- `fronts.geojson` declara que la exportación proyectada no es conforme con RFC 7946.
- `arrival_time.csv` marca su procedencia como `inferred_from_observed_geometries`.
- Ground truth solo aparece en la demo sintética.
- No se calcula velocidad real con el estimador radial sintético.

## Limitación restante y siguiente dato

El sistema acepta el contrato geoespacial real, pero todavía no estima velocidad
entre geometrías reales. El siguiente dato recomendado es una secuencia FLAME 3
o una quema controlada ortorrectificada con timestamps, CRS proyectado,
resolución conocida y anotaciones independientes del frente.
