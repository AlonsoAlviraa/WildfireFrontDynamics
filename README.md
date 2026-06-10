# Wildfire Front Dynamics

MVP reproducible para reconstruir la dinámica observada de un frente de incendio.
Genera una quema sintética con verdad conocida, simula observaciones con error,
reconstruye tiempos de llegada, estima velocidades locales y produce un informe
visual auditable.

También acepta secuencias GeoTIFF georreferenciadas y máscaras binarias para
generar geometrías observadas, campos de llegada y un dashboard sin inventar
ground truth ni velocidades no soportadas.

## Inicio rápido

```powershell
python -m wildfire_front demo --output outputs/demo
python -m unittest discover -s tests -v
```

Abrir después `outputs/demo/report.html`.

Para ejecutar pruebas y demo en un único paso:

```powershell
.\scripts\run_mvp.cmd
```

Este comando genera tanto `outputs/demo/report.html` como
`outputs/geotiff-demo/report.html`.

## Ingesta GeoTIFF

```powershell
python -m wildfire_front ingest-geotiff `
  --images data\sample\images `
  --masks data\sample\masks `
  --output outputs\geotiff-demo `
  --event-id burn_001 `
  --sensor-id thermal_demo `
  --estimated-error-m 2.0
```

Sin máscaras suministradas puede utilizarse el baseline determinista de umbral:

```powershell
python -m wildfire_front ingest-geotiff `
  --images data\sample\images `
  --threshold 350 `
  --band 1 `
  --output outputs\threshold-demo `
  --sensor-id thermal_demo `
  --estimated-error-m 2.0
```

La frontera de una máscara caliente se etiqueta como geometría candidata, no
como frente de llama validado. El estimador de velocidad real se abstiene hasta
disponer de un método no radial validado.

## Salidas del MVP

- `fronts.geojson`: frentes verdaderos y observados.
- `observations_manifest.csv`: trazabilidad de observaciones y error declarado.
- `ingest_manifest.csv`: aceptados, revisiones, rechazos y sus razones.
- `arrival_time.csv`: campo rasterizado de tiempo de llegada.
- `local_speeds.csv`: velocidad local, incertidumbre y abstenciones.
- `summary.json`: métricas y configuración reproducible.
- `fronts.svg`: visualización vectorial.
- `report.html`: dashboard autocontenido.

## Alcance

Este MVP valida el núcleo geométrico con datos sintéticos y acepta el contrato
GeoTIFF real. No es una herramienta operacional ni predice incendios reales.
El siguiente hito es conectar una secuencia térmica real que cumpla el contrato.

Consulta [ESTUDIO_FIRE_FRONT_TRACKER.md](ESTUDIO_FIRE_FRONT_TRACKER.md),
[AUDITORIA_DATASETS_MVP.md](AUDITORIA_DATASETS_MVP.md) y
[docs/PROVENANCE.md](docs/PROVENANCE.md). La arquitectura está resumida en
[docs/MVP_ARCHITECTURE.md](docs/MVP_ARCHITECTURE.md).

El contrato de entrada está en
[docs/GEOTIFF_INPUT_CONTRACT.md](docs/GEOTIFF_INPUT_CONTRACT.md).

El prompt ejecutable para el siguiente hito está en
[docs/PROMPT_NEXT_MILESTONE.md](docs/PROMPT_NEXT_MILESTONE.md).
