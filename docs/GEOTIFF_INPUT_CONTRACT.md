# Contrato de entrada GeoTIFF

## Estructura

Con máscaras suministradas:

```text
data/sample/
  images/
    burn_20260610_120000.tif
    burn_20260610_120100.tif
  masks/
    burn_20260610_120000.tif
    burn_20260610_120100.tif
```

Imagen y máscara se emparejan primero por nombre completo y después por stem.
Sin máscaras se utiliza `--band` y `--threshold`.

## Requisitos de imagen

- GeoTIFF legible.
- Una o más bandas, conservadas en dtype nativo.
- CRS y affine transform explícitos.
- Timestamp UTC inferible del nombre.
- Para resultados métricos, CRS proyectado.

Formatos de timestamp aceptados:

- `YYYYMMDD_HHMMSS`;
- `YYYY-MM-DDTHH-MM-SS`;
- Unix timestamp de diez dígitos separado por `_`.

No se inventa timestamp cuando falta.

## Requisitos de máscara

- GeoTIFF de una banda.
- Valores mayores que cero se interpretan como región candidata.
- Misma anchura, altura, CRS y affine transform que la imagen.
- Al menos un píxel positivo.

La máscara puede representar una región caliente o fuego activo según su origen.
Su borde se exporta como geometría observada candidata; no se declara
automáticamente frente de llama validado.

## Segmentación por umbral

Cuando no se proporciona `--masks`, el baseline aplica:

```text
mask = selected_band > threshold
```

El umbral es determinista y no convierte el raster a 8 bits. Debe justificarse
según las unidades y calibración del sensor.

## QA

`ingest_manifest.csv` registra:

- ruta y SHA-256;
- timestamp;
- estado `accepted`, `review` o `rejected`;
- razón;
- CRS y tipo de coordenadas;
- resolución métrica cuando aplica;
- método y número de componentes.

Se rechazan entradas ilegibles, sin georreferenciación, sin máscara emparejada,
con dimensiones o georreferenciación incompatibles y con máscara vacía. Un
timestamp ausente queda en revisión y no genera observación.

## Salidas y limitaciones

`fronts.geojson` es una exportación interna. Puede contener coordenadas
proyectadas y por tanto no es conforme con RFC 7946; cada feature declara su CRS.

No se calcula velocidad real porque el estimador actualmente validado es radial
y sintético. El sistema genera una abstención explícita hasta implementar y
validar correspondencia normal entre geometrías reales.

