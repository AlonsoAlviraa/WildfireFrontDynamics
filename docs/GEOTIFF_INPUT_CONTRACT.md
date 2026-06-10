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
Sin máscaras se utiliza `--band` con `--threshold` o `--mad-z`.

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

## Segmentación robusta MAD

`--mad-z` crea un baseline adaptativo con:

```text
threshold = median + mad_z * 1.4826 * median_absolute_deviation
mask = selected_band > threshold
```

No sustituye una segmentación validada para el sensor, pero evita fijar un
umbral absoluto cuando el nivel base cambia entre escenas.

## QA

`ingest_manifest.csv` registra:

- ruta y SHA-256;
- timestamp;
- estado `accepted`, `review` o `rejected`;
- razón;
- CRS y tipo de coordenadas;
- resolución métrica cuando aplica;
- método y número de componentes.

Se rechazan entradas ilegibles, duplicadas, sin georreferenciación, sin máscara
emparejada, con dimensiones o georreferenciación incompatibles y con máscara
vacía. También se auditan timestamps duplicados, cambios de CRS o resolución y
máscaras casi completas. Un timestamp ausente queda en revisión y no genera
observación.

## Salidas y limitaciones

`fronts.geojson` es una exportación interna. Puede contener coordenadas
proyectadas y por tanto no es conforme con RFC 7946; cada feature declara su CRS.

La velocidad local se estima únicamente en CRS proyectado, con timestamps
crecientes y componentes emparejables. El método por normales aplica gates de
observabilidad, curvatura, intersección y correspondencia; las muestras que no
los superan se abstienen. Sigue siendo una estimación sobre geometrías
observadas, no una velocidad de llama validada contra ground truth independiente.
