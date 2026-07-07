# Auditoria data science: TOBARRA-AB-20240802

Fecha de auditoria: 2026-07-07

## Veredicto ejecutivo

TOBARRA es un candidato real muy bueno para el siguiente salto del proyecto, pero no debe entrar todavia como dataset de entrenamiento/evaluacion final.

Tiene una secuencia temporal densa, sensores EO/LWIR, GeoTIFFs y KML/KMZ georreferenciados. Sirve ya para construir un primer pipeline real de ingestion, alineacion temporal, lectura geoespacial y generacion de candidatos de mascara. No sirve aun para reportar precision cientifica del frente porque faltan una referencia independiente de validacion, meteorologia sincronizada, perimetros oficiales y metadatos operativos.

Prioridad recomendada: usar TOBARRA como primer caso real de desarrollo del pipeline, no como benchmark definitivo.

## Procedencia y trazabilidad

- Fuente: Dropbox Transfer `https://www.dropbox.com/t/5CFtPw4KTkAHXysh`.
- Transfer resuelto: 5 ZIPs disponibles.
- Archivo auditado: `TOBARRA-AB-20240802.zip`.
- Tamano descargado: 145,580,509 bytes.
- SHA-256: `9934C0F425075AEC3B3AB5721A2D43E81F7851E5BDE64F4F2884989883E6E69B`.
- Ruta local bruta: `data/real_if/raw_dropbox/20260707_transfer_01/TOBARRA-AB-20240802.zip`.
- Ruta local extraida: `data/real_if/extracted/TOBARRA-AB-20240802`.

Los datos brutos y extraidos estan excluidos de Git con `.gitignore`.

## Inventario bruto

El ZIP contiene 376 archivos, todos con timestamp en nombre.

| Tipo | Conteo |
|---|---:|
| `.jpg` | 140 |
| `.tif` | 67 |
| `.kml` | 67 |
| `.kmz` | 67 |
| `.png` | 35 |

Estructura:

| Carpeta | Conteo |
|---|---:|
| `fotos/` | 242 |
| `kmz/` | 134 |

Por modalidad:

| Modalidad | Archivos |
|---|---:|
| HD-EO jpg normal | 35 |
| HD-EO jpg raw | 35 |
| HD-EO GeoTIFF | 32 |
| HD-EO KML | 32 |
| HD-EO KMZ | 32 |
| LWIR jpg normal | 35 |
| LWIR jpg raw | 35 |
| LWIR GeoTIFF | 35 |
| LWIR KML | 35 |
| LWIR KMZ | 35 |
| Window PNG | 35 |

## Cobertura temporal

- Inicio: `2024-08-02T16:08:21.553Z`.
- Fin: `2024-08-02T18:11:11.534Z`.
- Duracion observable: 122.83 minutos.
- Instantes unicos: 35.
- Intervalo minimo: 2.955 s.
- Intervalo mediano: 167.40 s.
- Intervalo medio: 216.76 s.
- Intervalo maximo: 1177.214 s.

Gaps mayores de 5 minutos:

| Desde | Hasta | Gap |
|---|---|---:|
| 16:09:52.717 | 16:15:07.320 | 314.603 s |
| 16:28:28.532 | 16:34:00.090 | 331.558 s |
| 16:34:00.090 | 16:39:29.464 | 329.374 s |
| 16:45:46.730 | 17:01:04.340 | 917.610 s |
| 17:02:48.735 | 17:12:20.738 | 572.003 s |
| 17:16:24.981 | 17:29:23.730 | 778.749 s |
| 17:29:23.730 | 17:49:00.944 | 1177.214 s |

Conclusion temporal: hay serie temporal suficiente para estudiar evolucion visual y geoespacial del frente, pero no es uniforme. Cualquier velocidad debe calcularse por pares con `delta_t` real, nunca asumiendo cadencia constante.

## Completitud por timestamp

Los 35 instantes tienen EO, LWIR y Window en imagen. Tres instantes no tienen georreferenciacion HD-EO:

- `2024-08-02T16:08:21.553Z`: faltan `HD-EO.tif`, `HD-EO.kml`, `HD-EO.kmz`.
- `2024-08-02T16:08:28.630Z`: faltan `HD-EO.tif`, `HD-EO.kml`, `HD-EO.kmz`.
- `2024-08-02T16:18:39.480Z`: faltan `HD-EO.tif`, `HD-EO.kml`, `HD-EO.kmz`.

LWIR esta completo en los 35 instantes con JPG, Raw JPG, GeoTIFF, KML y KMZ.

Conclusion practica: LWIR debe ser la modalidad principal para el primer pipeline. HD-EO puede usarse como apoyo visual/contextual, con 32 frames georreferenciados.

## Calidad espacial

Todos los GeoTIFF inspeccionados son `EPSG:4326`, 4 bandas `uint8,uint8,uint8,uint8`.

Bounding box global de overlays KML:

- lon min: `-1.88800391`
- lat min: `38.61015211`
- lon max: `-1.64297540`
- lat max: `38.69321239`

Bounding box LWIR:

- lon min: `-1.71968104`
- lat min: `38.62303435`
- lon max: `-1.69170765`
- lat max: `38.64971131`

Resolucion aproximada por pixel:

| Modalidad | X min | X mediana | X max | Y min | Y mediana | Y max |
|---|---:|---:|---:|---:|---:|---:|
| LWIR | 0.208 m | 0.411 m | 0.714 m | 0.264 m | 0.523 m | 0.907 m |
| HD-EO | 0.235 m | 1.134 m | 7.756 m | 0.299 m | 1.441 m | 9.860 m |

Riesgo espacial importante: los KML usan `gx:LatLonQuad`, es decir, overlays con cuatro esquinas potencialmente rotadas/perspectivas. Los GeoTIFFs tienen transform affine en EPSG:4326. Antes de calcular areas, velocidades o distancias, hay que verificar si el TIFF conserva correctamente la geometria del quad o si es una aproximacion rectangular.

## Calidad de imagen

Dimensiones:

| Modalidad | Dimensiones |
|---|---|
| HD-EO JPG normal | 1920 x 1080, 35 frames |
| HD-EO JPG raw | 1920 x 1080, 35 frames |
| LWIR JPG normal | 1920 x 1080, 35 frames |
| LWIR JPG raw | 720 x 576, 35 frames |
| Window PNG | 1920 x 991, 35 frames |
| LWIR GeoTIFF | dimensiones variables, 35 tamanos unicos |
| HD-EO GeoTIFF | dimensiones variables, 32 tamanos unicos |

Los TIFF no parecen raster termico fisico calibrado; son RGBA `uint8`. Esto apunta a producto visual georreferenciado, no a temperatura radiometrica directa. Para segmentacion inicial vale, pero para modelar intensidad termica fisica harian falta unidades, calibracion o metadatos del sensor.

Fraccion de alfa positiva:

| Modalidad | Min | Mediana | Max |
|---|---:|---:|---:|
| LWIR | 0.4991 | 0.5695 | 0.8273 |
| HD-EO | 0.3521 | 0.5145 | 0.6825 |

Esto confirma que hay grandes zonas transparentes/no validas en los overlays. El pipeline debe respetar alfa y no tratar el rectangulo completo como observacion valida.

## Variables presentes y ausentes

Presentes:

- Tiempo exacto por frame, con milisegundos.
- Imagen EO.
- Imagen LWIR.
- Imagen raw por modalidad.
- Window PNG.
- GeoTIFF georreferenciado.
- KML/KMZ con camara, centro, HFOV/VFOV y `LatLonQuad`.
- Localizacion espacial suficiente para mapear overlays.

Ausentes o no localizadas en este ZIP:

- Meteorologia sincronizada: viento, direccion, rachas, temperatura, humedad, precipitacion.
- Perimetros oficiales o referencia independiente de validacion.
- Mascaras de frente/fuego ya etiquetadas.
- Linea de tiempo operativa: inicio, estabilizacion, control, medios, actuaciones.
- Topografia/fuel/coberturas de combustible.
- Metadatos radiometricos: calibracion, unidades termicas, emisividad.

## Decision para el programa

No hay que "nutrir con datos" sin mas. El siguiente paso correcto es crear el adaptador real para TOBARRA y una capa de calidad/validacion antes de entrenar.

Orden recomendado:

1. Implementar `RealIFSequence` para leer una carpeta real extraida y producir frames ordenados por timestamp.
2. Parsear KML/KMZ y GeoTIFF respetando `LatLonQuad`, CRS y alfa.
3. Crear una tabla `frame_manifest` con una fila por timestamp y columnas para EO, LWIR, Window, KML, KMZ, TIFF, bbox, resolucion y gaps.
4. Generar mascaras candidatas LWIR por thresholding/control visual, siempre marcadas como `candidate`, no como ground truth.
5. Elegir 5-10 frames representativos para etiquetado manual del frente o area activa.
6. Pedir a los proveedores perimetros oficiales, meteo sincronizada y contexto operativo.
7. Solo despues, ejecutar comparacion del modelo contra referencia independiente.

## Riesgos cientificos

- Usar LWIR como verdad terreno seria incorrecto: es observacion, no validacion independiente.
- Calcular velocidad sobre EPSG:4326 directamente seria incorrecto; hay que reproyectar a CRS metrico local.
- Ignorar alfa inflaria areas y contaminaria mascaras.
- Entrenar y validar con la misma imagen/mascara daria metricas optimistas.
- La serie tiene gaps grandes; no debe interpolarse movimiento sin marcar incertidumbre.
- Los TIFF son RGBA visuales; no debe asumirse temperatura fisica.

## Acciones inmediatas

- Crear script `build_real_if_frame_manifest.py`.
- Crear tests con TOBARRA en mini-fixture sintetico, no subiendo datos reales.
- Incorporar validaciones: timestamps monotonicos, modalidad completa, CRS presente, alfa presente, bbox plausible, resolucion metrica estimada.
- Crear notebook o script de QA visual para 6 frames LWIR: inicio, mitad, final y frames alrededor de gaps.
- Preparar respuesta al equipo pidiendo meteo, perimetros oficiales, planificacion y significado de productos EO/LWIR/Window/Raw.

