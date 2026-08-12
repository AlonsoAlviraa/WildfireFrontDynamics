# Contrato de entrada GeoTIFF

**Graph v6.1 E4** — contrato multi-provider (CN UAV / Heligrafics / genérico).  
Invalid metadata → ingest **reject/review** y, en el producto de decisión, suele mapear a **ABSTAIN** (sin ROS de campo confiable).

Smoke de metadatos (opcional):

```powershell
$env:PYTHONPATH = "."
python scripts/validate_geotiff_contract.py path/to/scene.tif
python scripts/validate_geotiff_contract.py path/to/images_dir --json
```

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
- **CRS** y affine transform explícitos.
- **Timestamp UTC** inferible del nombre (o metadata sidecar).
- Para resultados métricos (ROS m/min), **CRS proyectado** (métrico).
- **Resolución** reportable (`resolution_m` cuando CRS proyectado).
- **provider_id** / **platform** recomendados (sidecar o convención de path) para multi-vendor.

Formatos de timestamp aceptados:

- `YYYYMMDD_HHMMSS`;
- `YYYY-MM-DDTHH-MM-SS`;
- Unix timestamp de diez dígitos separado por `_`.

No se inventa timestamp cuando falta.

## Metadatos multi-provider (E4 harden)

| Campo | Obligatorio para ops ROS | Dónde | Si falta / inválido |
|-------|--------------------------|-------|---------------------|
| **platform** | recomendado | sidecar JSON / path (`dji_m3t`, `helicopter_lwir`, `cn_uav`, …) | review; no bloquea máscara sola |
| **resolution_m** | sí para ROS métrico | derivado de transform si CRS proyectado | **reject** métricas de velocidad; ABSTAIN ops |
| **provider_id** | recomendado | sidecar / `sensor_id` CLI | review; trazabilidad débil |
| **timestamp** (UTC) | **sí** | nombre de archivo o metadata | **review/reject** — sin observación ordenable |
| **CRS** | **sí** | GeoTIFF tags | **reject** sin georref; sin ROS |
| **affine / georef** | **sí** | GeoTIFF | **reject** si identity sin CRS |

Sidecar opcional (mismo stem que el `.tif`):

```json
{
  "platform": "helicopter_lwir",
  "provider_id": "heligrafics",
  "sensor_id": "lwir_band",
  "timestamp_utc": "2024-08-02T16:15:07Z",
  "notes": "optional free text"
}
```

### Visibilidad ABSTAIN / reject

| Fallo de contrato | Ingest (`ingest_manifest`) | Producto decisión |
|-------------------|----------------------------|-------------------|
| Sin CRS / sin georref | `rejected` · reason `no_georeferencing` / similar | ops unavailable → field_ops **ABSTAIN** o open-only HOLD |
| Sin timestamp | `review` (no se inventa) | frame no entra en serie → puede bajar n_frames / ABSTAIN |
| CRS geográfico solo | `review` (`crs_not_projected_metric_ros_abstain` in validate helper; ingest may accept with caveat) | ROS métrica **abstiene** (necesita proyectado) |
| Máscara vacía / mismatch dims | `rejected` | sin obs → ABSTAIN |
| provider/platform ausente | accepted + reason review opcional | no ABSTAIN por sí solo; audit más débil |

Razones tipicas en manifest: ver columna `reason` de `ingest_manifest.csv`.  
Decision Card reasons legibles: `docs/RELIABILITY_GATE_REPORT_THIRD_PARTY.md` §3 (Orion UQ → ABSTAIN).

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
