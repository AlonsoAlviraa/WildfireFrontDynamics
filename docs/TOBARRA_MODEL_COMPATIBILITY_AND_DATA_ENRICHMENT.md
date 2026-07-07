# TOBARRA: compatibilidad del modelo y enriquecimiento externo

Fecha: 2026-07-07

## Estado actual

TOBARRA ya no es solo un ZIP descargado: ahora tenemos una ruta tecnica reproducible para preparar sus GeoTIFF reales antes de llamar al modelo.

El modelo actual hace bien en rechazar TOBARRA tal cual:

- Los GeoTIFF originales estan en `EPSG:4326`.
- El estimador de velocidades exige coordenadas metricas proyectadas.
- Los TIFF son RGBA visuales, no termicos radiometricos calibrados.
- No hay mascaras independientes de frente activo.
- Mezclar HD-EO y LWIR causa timestamps duplicados.
- Las resoluciones originales son variables.

Este rechazo evita calcular velocidades en grados o sobre mascaras sin significado fisico.

## Mejoras implementadas

Se ha ampliado el pipeline sin rebajar las garantias cientificas:

- `wildfire_front.ingestion.geotiff.infer_timestamp` conserva milisegundos de nombres reales tipo `2024-08-02_16-08-21-553_LWIR.tif`.
- `segment_band_threshold` y `segment_band_mad` aceptan mascara de validez.
- `ingest_geotiff_sequence(..., respect_alpha=True)` ignora pixeles transparentes en GeoTIFF RGBA.
- `ingest_geotiff_sequence(..., min_component_pixels=N)` aplica `rasterio.features.sieve` antes de vectorizar para eliminar ruido pequeño.
- CLI: `wildfire-front ingest-geotiff --respect-alpha --min-component-pixels N`.
- Nuevo script: `scripts/prepare_real_if_geotiffs.py`, que filtra y reproyecta GeoTIFFs reales a CRS metrico.

Comando usado para preparar LWIR:

```powershell
.\.venv\Scripts\python.exe scripts\prepare_real_if_geotiffs.py `
  --source data\real_if\extracted\TOBARRA-AB-20240802\fotos `
  --output outputs\tobarra_model_probe\lwir_utm_05m `
  --pattern "*_LWIR.tif" `
  --dst-crs EPSG:32630 `
  --resolution-m 0.5 `
  --overwrite
```

## Pruebas ejecutadas

### TOBARRA original

Entrada: `data/real_if/extracted/TOBARRA-AB-20240802/fotos`.

Resultado:

- Registros: 67.
- Observaciones aceptadas: 0.
- Estado: `review=67`.
- Motivo: `crs_not_projected_metric=67`.

Interpretacion: correcto. No se deben estimar velocidades sobre `EPSG:4326`.

### TOBARRA LWIR reproyectado, subset 8 frames

Entrada: `outputs/tobarra_model_probe/lwir_utm_05m_8`.

Configuracion: banda 1, threshold 220, `respect_alpha=True`.

| min_component_pixels | aceptadas | rechazadas | max componentes | decreases de area |
|---:|---:|---:|---:|---:|
| 500 | 8/8 | 0 | 165 | 3 |
| 2,000 | 8/8 | 0 | 130 | 3 |
| 10,000 | 8/8 | 0 | 107 | 3 |
| 50,000 | 6/8 | 2 empty_mask | 47 | 1 |

Interpretacion: el pipeline puede ingerir datos reales preparados, pero las mascaras por threshold siguen siendo ruidosas y no monotonicamente crecientes. Eso indica que no son perimetros acumulados ni frente validado.

### Velocidad sobre subset preparado

Configuracion: banda 1, threshold 220, alfa, `min_component_pixels=50000`, estimador geometry-speed con muestreo coarse.

| sample_spacing_m | observable_ratio | velocidad mediana | p95 |
|---:|---:|---:|---:|
| 10 | 0.051 | 174.24 m/min | 440.64 m/min |
| 25 | 0.075 | 117.16 m/min | 320.61 m/min |
| 50 | 0.070 | 44.61 m/min | 245.55 m/min |
| 100 | 0.082 | 33.23 m/min | 185.51 m/min |

INFOCAM publica para TOBARRA una velocidad media de propagacion de aproximadamente 7 m/min. Por tanto, estas velocidades del modelo no son defendibles: estan midiendo cambios en regiones thresholded de una imagen visual, no avance del frente.

### TOBARRA LWIR reproyectado, 35 frames

Configuracion: banda 1, threshold 220, alfa.

| min_component_pixels | aceptadas | rechazadas | motivo principal | area decreases |
|---:|---:|---:|---|---:|
| 50,000 | 12/35 | 23/35 | empty_mask | 6 |
| 100,000 | 5/35 | 30/35 | empty_mask | 2 |
| 250,000 | 1/35 | 34/35 | empty_mask | 0 |

Interpretacion: al limpiar ruido, muchas mascaras desaparecen. Esto confirma que necesitamos segmentacion/etiquetado especifico de frente, no solo threshold de RGB.

## Datos externos localizados

Fuentes publicas utiles para enriquecer TOBARRA:

- INFOCAM/FIDIAS via prensa: incendio declarado/detectado el `2024-08-02 16:42`, forestal-matorral, superficie lenosa no arbolada, 22 medios y 83 personas al inicio.
- INFOCAM 2024: TOBARRA `(AB)`, `2024-08-02`, `39 ha`, intensidad `Media-Alta`, motor `Contraviento`, `Vp media = 7 m/min`, `Sp media = 13.4 ha/h`.
- Extincion/control via FIDIAS/prensa: controlado `2024-08-03 13:56`, extinguido `2024-08-04 20:50`.
- Meteo Tobarra AEMET 7103Y via historico publico: temperatura alrededor de 37.4-38.5 C, HR 14-16%, precipitacion 0.0 mm entre 16:00-19:00.
- Viento: Tobarra publico no trae viento horario completo; usar Albacete/Los Llanos o Open-Meteo como proxy/contexto, no como verdad local exacta.
- EFFIS/Copernicus podria tener perimetro porque el incendio fue de 39 ha, pero hay que comprobar disponibilidad y geometria.
- NASA FIRMS sirve para hotspots, no para perimetro ni frente continuo.
- MITECO/EGIF sirve como contraste estadistico oficial, no como geometria operativa inmediata.

## Que pasaria si usamos esto ya en el modelo

Sin preparacion:

- No se generan observaciones.
- No hay velocidades.
- El manifiesto queda en `review` por CRS geografico.

Con reproyeccion y threshold:

- Se generan observaciones candidatas.
- La reconstruccion de llegada puede producir una malla, pero representa threshold visual, no llegada real del frente.
- La velocidad local puede devolver numeros, pero son inestables y demasiado altos frente a INFOCAM.
- Los decreases de area invalidan tratar la mascara como perimetro acumulado.

Conclusion: el codigo ya evita el peor error; con las mejoras nuevas puede probar datos reales preparados, pero todavia debe abstenerse de conclusiones cientificas hasta tener mascaras/perimetros validos.

## Siguiente paso tecnico

1. Construir `frame_manifest` real para TOBARRA con una fila por timestamp.
2. Separar secuencias por sensor: primero LWIR.
3. Reproyectar a `EPSG:32630` con resolucion comun.
4. Generar QA visual de 8-12 frames representativos.
5. Crear un modulo de segmentacion candidato especifico para LWIR visual, con alfa y limpieza morfologica.
6. Etiquetar manualmente 5-10 frames o conseguir perimetros oficiales.
7. Usar INFOCAM `Vp media = 7 m/min` y `39 ha` como control agregado, no como validacion pixel a pixel.

