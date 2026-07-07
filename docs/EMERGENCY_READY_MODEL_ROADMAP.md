# Roadmap para un modelo fiable en emergencias

Fecha: 2026-07-07

## Resumen ejecutivo

El proyecto ya tiene una base tecnica seria: ingest GeoTIFF auditable, control de CRS, reconstruccion de llegada, estimacion geometrica conservadora de velocidades, QA de datasets y pruebas automatizadas. Tambien hemos incorporado el primer caso real, TOBARRA-AB-20240802, y comprobado que contiene una secuencia LWIR/EO georreferenciada con 35 timestamps.

La conclusion importante es esta: **TOBARRA es muy valioso para construir el pipeline real, pero todavia no es ground truth para un modelo operativo de emergencias**.

El modelo actual hace bien en bloquear el uso directo de esos datos porque:

- Los GeoTIFF originales estan en `EPSG:4326`, no en coordenadas metricas.
- Las imagenes son RGBA visuales, no temperatura radiometrica calibrada.
- No tenemos mascaras verificadas del frente activo.
- No tenemos perimetros oficiales independientes en formato geometrico.
- La segmentacion por threshold produce areas no monotonicamente crecientes.
- Las velocidades estimadas sobre threshold visual salen muy por encima del valor operativo INFOCAM.

Por tanto, el objetivo no debe ser "meter mas datos" sin control. El objetivo es crear una cadena fiable: **ingesta real -> QA -> normalizacion geoespacial -> segmentacion candidata -> validacion humana/oficial -> modelo -> abstencion si no hay confianza**.

## Estado actual del proyecto

## Estado del repositorio

Revision realizada: 2026-07-07.

### GitHub remoto

- Repositorio: `https://github.com/AlonsoAlviraa/WildfireFrontDynamics.git`.
- Rama remota principal: `origin/main`.
- Ultimo commit remoto observado: `a422a77`.
- Mensaje del ultimo commit remoto: `docs(ml): add detailed report for mega pre-training and meta-labeling results`.
- El remoto tiene trabajo nuevo posterior al commit local `4066eda`.
- Tras `git fetch origin`, el local queda **13 commits por detras** de `origin/main`.

Commits remotos recientes observados:

- `a422a77` - `docs(ml): add detailed report for mega pre-training and meta-labeling results`
- `e4daba3` - `chore(ml): prepare 16-hour mega pre-training pipeline with split preprocessing and cosine scheduler`
- `885864c` - `fix(ml): update feature mapping candidates in preprocess_ndws.py`
- `f1d0fa9` - `fix(ml): implement dynamic schema mapping and default fallback in preprocess_ndws.py`
- `9c59fe1` - `fix(ml): auto-detect TFRecord compression in preprocess_ndws.py`

### Local

- Carpeta de trabajo activa: `C:\Users\alons\Desktop\WildfireFrontDynamics_push`.
- Rama local: `main`.
- Commit local actual: `4066eda392e01b8d34aeebc42035325a09436e0b`.
- Mensaje del commit local: `Add data validation sprint`.
- Relacion con remoto tras fetch: `main...origin/main [behind 13]`.
- Diferencia de commits: local `0` por delante, `13` por detras.

Cambios locales pendientes, no subidos:

- Modificados:
  - `.gitignore`
  - `tests/test_geotiff_ingestion.py`
  - `wildfire_front/cli.py`
  - `wildfire_front/ingestion/geotiff.py`

- Nuevos archivos:
  - `docs/EMERGENCY_READY_MODEL_ROADMAP.md`
  - `docs/REAL_IF_AUDIT_TOBARRA_20240802.md`
  - `docs/REAL_IF_INTAKE_PROTOCOL.md`
  - `docs/TOBARRA_MODEL_COMPATIBILITY_AND_DATA_ENRICHMENT.md`
  - `ideas_monitorizacion_incendios_activos.md`
  - `scripts/inventory_real_if_material.py`
  - `scripts/prepare_real_if_geotiffs.py`
  - `tests/test_inventory_real_if_material.py`
  - `tests/test_prepare_real_if_geotiffs.py`

Datos y salidas locales ignorados por Git:

- `.venv/`
- `data/real_if/`
- `outputs/`
- `__pycache__/`
- `wildfire_front_dynamics.egg-info/`

### Riesgo actual de sincronizacion

No conviene hacer `git pull` o `git push` sin revisar antes, porque:

- GitHub tiene 13 commits nuevos que el local aun no incorpora.
- El local tiene refactorizaciones y documentos nuevos sin commitear.
- Puede haber conflictos en codigo o docs si los commits remotos tocaron areas cercanas.
- Los datos reales estan correctamente ignorados y no deben subirse.

Secuencia recomendada para sincronizar:

1. Guardar los cambios locales en un commit o rama temporal.
2. Revisar los 13 commits remotos.
3. Integrar `origin/main` mediante rebase o merge controlado.
4. Resolver conflictos.
5. Ejecutar la suite completa.
6. Solo entonces subir los cambios.

### Ya implementado

- Pipeline sintetico de demostracion.
- Ingesta GeoTIFF auditable.
- Rechazo/revision de entradas sin CRS, sin timestamp, CRS no metrico o resolucion inconsistente.
- Extraccion de componentes desde mascaras binarias.
- Reconstruccion de arrival time desde componentes observados.
- Estimacion geometrica de velocidad local por intersecciones normales.
- Abstenciones por baja observabilidad, mala geometria, CRS no metrico o pares inconsistentes.
- Auditoria de candidatos de dataset.
- Sprint semirreal con dataset controlado.
- Inventario de material real.
- Descarga y auditoria de TOBARRA.
- Preparador inicial para reproyectar GeoTIFFs reales a `EPSG:32630`.
- Soporte para timestamps con milisegundos.
- Soporte para respetar canal alfa.
- Limpieza de componentes pequenos por `min_component_pixels`.
- Exclusión de datos reales privados en `.gitignore`.

### Datos reales disponibles ahora

TOBARRA-AB-20240802:

- 376 archivos.
- 35 timestamps entre `2024-08-02T16:08:21.553Z` y `2024-08-02T18:11:11.534Z`.
- 35 LWIR con GeoTIFF/KML/KMZ.
- 32 HD-EO con GeoTIFF/KML/KMZ.
- 35 Window PNG.
- GeoTIFFs en `EPSG:4326`, RGBA `uint8`.
- KML con `gx:LatLonQuad`, camara, HFOV/VFOV y centro.

Datos externos localizados:

- INFOCAM/FIDIAS: deteccion `2024-08-02 16:42`.
- INFOCAM 2024: `39 ha`, intensidad `Media-Alta`, motor `Contraviento`, `Vp media = 7 m/min`, `Sp media = 13.4 ha/h`.
- Controlado `2024-08-03 13:56`.
- Extinguido `2024-08-04 20:50`.
- Meteo publica aproximable con AEMET/Tutiempo, Meteostat y Open-Meteo.
- EFFIS/FIRMS pueden aportar contexto, hotspots o perimetro satelital si existe.

## Que pasaria si usamos el modelo actual en emergencias

### Caso 1: entrada original TOBARRA

Resultado: no genera observaciones.

Motivo: `crs_not_projected_metric`.

Esto es correcto. En emergencias es mejor abstenerse que calcular velocidades sobre grados lat/lon como si fueran metros.

### Caso 2: TOBARRA reproyectado + threshold visual

Resultado: el modelo puede ingerir algunos frames y generar velocidades, pero no son fiables.

Problemas detectados:

- Las mascaras por threshold no representan necesariamente frente activo.
- Hay decreases de area entre timestamps.
- Hay muchos componentes fragmentados.
- La velocidad mediana estimada en pruebas oscilo entre `33` y `174 m/min`, mientras INFOCAM reporta `7 m/min`.
- La salida depende demasiado de threshold, banda, alfa y filtrado de componentes.

Conclusion: el pipeline ya puede procesar datos reales preparados, pero todavia debe etiquetar esas salidas como **candidatas/no validadas**.

## Principios para un sistema utilizable en emergencias

1. **Abstencion antes que falsa precision.**
   Si no hay CRS metrico, timestamp fiable, georreferenciacion o validacion suficiente, el sistema debe decir "no se puede estimar".

2. **Trazabilidad total.**
   Cada observacion debe conservar archivo fuente, hash, sensor, timestamp, CRS, metodo, version del pipeline y limitaciones.

3. **Separar observacion, mascara candidata y ground truth.**
   Una imagen LWIR no es automaticamente verdad terreno. Una mascara por threshold no es perimetro oficial.

4. **Validacion independiente.**
   No se debe entrenar y evaluar contra la misma mascara generada por el modelo.

5. **Unidades metricas obligatorias para dinamica.**
   Velocidades, areas y distancias solo tras reproyeccion y comprobacion de resolucion.

6. **Incertidumbre visible.**
   El output operativo debe mostrar confianza, abstenciones, gaps temporales y motivos de fallo.

7. **Producto operativo, no solo modelo.**
   En emergencias importa el flujo: ingestion rapida, QA, mapa, alertas, explicabilidad, exportacion GIS y logs.

## Refactorizaciones necesarias

### 1. Modelo de datos real

Crear entidades explicitas:

- `RealFireEvent`
- `SensorFrame`
- `FrameManifest`
- `GeoReference`
- `CandidateMask`
- `ReferenceMask`
- `OperationalReport`
- `WeatherObservation`
- `ModelRun`
- `QualityGateResult`

Objetivo: dejar de pasar carpetas sueltas y empezar a trabajar con manifiestos reproducibles.

### 2. Frame manifest

Crear `scripts/build_real_if_frame_manifest.py`.

Debe producir una tabla con:

- `event_id`
- `timestamp_utc`
- `sensor`
- `modality`
- `image_path`
- `geotiff_path`
- `kml_path`
- `kmz_path`
- `window_path`
- `crs`
- `coordinate_system`
- `bbox`
- `latlon_quad`
- `width`
- `height`
- `alpha_valid_fraction`
- `resolution_estimate_m`
- `source_sha256`
- `qa_status`
- `qa_reasons`

### 3. Preparacion geoespacial robusta

Refactorizar `prepare_real_if_geotiffs.py` hacia modulo importable:

- Filtrar por sensor/modalidad.
- Reproyectar a CRS metrico local.
- Normalizar resolucion.
- Respetar canal alfa.
- Guardar manifest de preparacion.
- Verificar bounds plausibles.
- Detectar cambios bruscos de footprint.
- Conservar relacion con KML `LatLonQuad`.

Pendiente importante: decidir si los GeoTIFF rectangulares preservan bien el `LatLonQuad` o si hay que warpear explicitamente desde las cuatro esquinas KML.

### 4. Segmentacion candidata real

Sustituir threshold simple por un modulo de segmentacion experimental:

- Threshold por bandas RGB/LWIR visual.
- Segmentacion HSV/colormap si LWIR esta colorizado.
- Uso del canal alfa.
- Limpieza morfologica.
- Union/filtro de componentes.
- Tracking temporal de componentes.
- Reglas de plausibilidad: area, continuidad, movimiento maximo, gaps.
- Salida marcada siempre como `candidate_mask`.

Esto no debe llamarse ground truth.

### 5. Etiquetado y validacion

Crear flujo de validacion:

- Elegir 5-10 frames representativos de TOBARRA.
- Generar previews PNG con overlay.
- Etiquetar manualmente frente/area activa.
- Guardar `annotations/` separadas.
- Comparar candidato vs anotacion.
- Medir IoU, distancia Hausdorff/percentil, area error y estabilidad temporal.

Sin esto, no hay precision reportable.

### 6. Integracion meteo

Crear `weather_manifest`:

- Fuente: AEMET/Tutiempo/Meteostat/Open-Meteo.
- Timestamp.
- Temperatura.
- Humedad relativa.
- Viento velocidad/direccion/racha.
- Precipitacion.
- Distancia de estacion al incendio.
- Tipo de dato: estacion real, aeropuerto, reanalisis/modelo.
- Calidad/confianza.

Uso inicial: contexto y features auxiliares, no prediccion fisica completa.

### 7. Referencias oficiales y externas

Crear conectores o importadores para:

- INFOCAM/FIDIAS: tiempos, superficie, comportamiento, recursos.
- EFFIS/Copernicus: perimetros si existen.
- NASA FIRMS: hotspots VIIRS/MODIS.
- MITECO/EGIF: contraste estadistico.

Cada fuente debe etiquetarse por precision:

- `operational_timeline`
- `aggregate_validation`
- `coarse_hotspot`
- `independent_geometry`
- `context_only`

### 8. Quality gates operativos

Antes de ejecutar dinamica:

- Minimo 3 timestamps utiles.
- Timestamps estrictamente crecientes.
- CRS proyectado metrico.
- Resolucion comun o reamostrada.
- Alfa/footprint valido.
- No duplicados de timestamp por sensor.
- Mascara no vacia.
- Mascara no casi completa.
- Area no decrece salvo justificacion.
- Componentes no excesivamente fragmentados.
- Gaps temporales marcados.
- Referencia independiente disponible si se reporta precision.

### 9. Abstencion y explicabilidad

El output debe incluir:

- `can_estimate_speed: true/false`
- `can_report_accuracy: true/false`
- `can_use_for_training: true/false`
- `reasons`
- `required_next_data`
- `confidence_level`
- `operational_warning`

Esto es esencial para emergencias.

### 10. Arquitectura del modelo futuro

Fase 1: modelo geometrico validado.

- Usa mascaras/perimetros fiables.
- Calcula velocidad local y arrival time.
- Reporta incertidumbre.

Fase 2: modelo de segmentacion.

- Aprende de LWIR/EO etiquetado.
- Produce mascaras candidatas con confianza.
- Nunca sustituye validacion si hay consecuencias operativas.

Fase 3: modelo predictivo.

- Integra meteo, pendiente, combustible y operaciones.
- Predice corto plazo.
- Necesita dataset mucho mayor y validacion externa.

Fase 4: decision support.

- Dashboard operativo.
- Export GIS.
- Alertas.
- Registro de decisiones.
- Modo degradado/offline.

## Plan de trabajo recomendado

### Sprint 1: manifiesto real y QA visual

- Crear `build_real_if_frame_manifest.py`.
- Generar manifest TOBARRA.
- Crear previews QA para LWIR.
- Documentar frames buenos/malos.
- Verificar KML vs GeoTIFF.

Salida esperada: sabemos exactamente que frames son usables.

### Sprint 2: preparacion metrica estable

- Convertir `prepare_real_if_geotiffs.py` en modulo robusto.
- Reproyectar LWIR.
- Guardar manifest de reproyeccion.
- Probar varias resoluciones.
- Garantizar que el ingest no se cuelga con datos reales.

Salida esperada: carpeta lista para modelo, reproducible.

### Sprint 3: segmentacion candidata

- Crear segmentador LWIR visual.
- Comparar thresholds, HSV, alfa, limpieza.
- Medir fragmentacion, area, estabilidad.
- Generar reporte de mascaras candidatas.

Salida esperada: mejor mascara candidata, aun no ground truth.

### Sprint 4: validacion manual/minima

- Etiquetar 5-10 frames.
- Crear tests con mini-fixtures anonimos.
- Medir error geometrico.
- Ajustar segmentacion.

Salida esperada: primer benchmark real defendible.

### Sprint 5: meteo y fuentes externas

- Crear `weather_manifest`.
- Incorporar INFOCAM `39 ha`, `Vp 7 m/min`.
- Buscar/descargar EFFIS si existe.
- Consultar FIRMS si hay API key.

Salida esperada: contexto operativo y validacion agregada.

### Sprint 6: modelo emergencia-ready v0

- Quality gates completos.
- Abstencion explicita.
- Reporte HTML operativo.
- Export GeoJSON/GPKG.
- Resumen para decisores.

Salida esperada: prototipo que puede ser evaluado con usuarios operativos, todavia no desplegado como sistema critico.

## Criterios minimos antes de uso en emergencias

No usar operacionalmente hasta cumplir:

- Al menos 3 incendios reales auditados.
- Al menos 1 incendio con perimetros independientes.
- Al menos 20-50 frames etiquetados manualmente.
- Error geometrico reportado con referencia independiente.
- Pruebas de abstencion ante datos malos.
- Validacion de meteo/fuentes.
- Reproducibilidad completa por manifest.
- Revision por experto de incendios.
- Interfaz que muestre incertidumbre y limitaciones.

## Decision actual

Siguiente accion: **no entrenar todavia**.

Primero hay que convertir TOBARRA en un caso real bien estructurado:

1. `frame_manifest`.
2. Reproyeccion metrica verificada.
3. QA visual.
4. Segmentacion candidata.
5. Etiquetado/validacion.
6. Comparacion con INFOCAM/meteo/perimetros externos.

Solo despues merece la pena hablar de entrenamiento o prediccion.
