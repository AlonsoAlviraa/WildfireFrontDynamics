# Procedencia y reutilización

## DetectorDeIncendios

Repositorio auditado:
https://github.com/AlonsoAlviraa/DetectorDeIncendios

Commit inspeccionado:
`5cc86819d76da95ac3485a8026a7f0b5999baab0`

Adaptaciones incorporadas:

- `wildfire_front/identity.py`: identidad estable y hash SHA-256 por bloques,
  adaptados de `src/data_prep/sample_identity.py` y
  `src/data_prep/ingesta_pipeline.py`.
- `wildfire_front/ingestion/geotiff.py`: estados `accepted`, `review`,
  `rejected`, razones auditables, inferencia conservadora de timestamps y
  escritura de manifiesto.

No se reutilizaron normalización a JPEG, control de calidad RGB ni tracking por
bounding boxes. Convertir TIFF radiométrico a JPEG destruiría información y una
caja no representa un frente.

## NASA AMS

Fuentes inspeccionadas:

- `external/nasa-ams/AMS_dataset_processing.py`
- `external/nasa-ams/dataset_utils.py`
- `external/nasa-ams/combined_algorithm.py`

Ideas adaptadas:

- conservar transformación y CRS del raster;
- separar lectura multibanda, segmentación y extracción;
- mantener conceptualmente separadas clasificación y segmentación.

No se incorporaron TensorFlow, modelos, pesos, GDAL directo, HDF ni su
interpolador. La descarga de datos NASA AMS continúa limitada por la cuota Git
LFS del repositorio externo.

## ActiveFire

Fuente inspeccionada:

- `external/activefire/src/utils/cnn/generator.py`

Idea adaptada:

- lectura de bandas y máscaras mediante `rasterio`, conservando dtype nativo.

No se incorporaron generadores Keras, normalización fija a 16 bits, modelos ni
entrenamientos antiguos.

## Independencia de ejecución

No existen imports desde `wildfire_front/` hacia `external/`. Todo el código
adaptado vive en el paquete principal, tiene pruebas propias y puede ejecutarse
sin los repositorios descargados.

