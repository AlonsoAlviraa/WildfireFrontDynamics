# Arquitectura del MVP

```mermaid
flowchart LR
    A[Generador sintético] --> O[FrontObservation]
    B[GeoTIFF multibanda] --> C[Lectura nativa rasterio]
    D[Máscara binaria] --> E[Segmentación]
    C --> E
    E --> F[Contornos + affine transform]
    F --> O
    O --> G[Reconstrucción genérica de llegada]
    O --> H[Velocidad por normales]
    H --> I[Estimación o abstención local]
    O --> Q[QA científico]
    O --> J[Manifiestos + geometrías]
    G --> K[Dashboard]
    I --> K
    Q --> K
    J --> K
```

## Responsabilidades

| Módulo | Responsabilidad |
|---|---|
| `models.py` | Contratos inmutables con ground truth opcional y metadatos reales |
| `identity.py` | Identidad estable y SHA-256 adaptados de `DetectorDeIncendios` |
| `synthetic.py` | Observaciones sintéticas con verdad conocida |
| `ingestion/geotiff.py` | Lectura, QA, segmentación y extracción geoespacial |
| `reconstruction.py` | Llegada genérica y velocidad radial sintética |
| `geometry_speed.py` | Correspondencia de componentes y velocidad no radial con gates |
| `quality.py` | Resúmenes de QA de ingesta y secuencias observadas |
| `evaluation.py` | Distancias simétricas de frente contra referencias |
| `outputs.py` | Manifiestos, geometrías, tablas y dashboard |
| `cli.py` | Comandos `demo` e `ingest-geotiff` |

## Separación científica

- `observed`: geometría extraída de una observación o máscara.
- `ground_truth`: disponible únicamente en el escenario sintético.
- `inferred`: campo de llegada rasterizado entre observaciones.
- `forecast`: no implementado.

La reconstrucción de llegada acepta geometrías no radiales y múltiples
componentes. La velocidad sintética conserva el estimador radial original. Para
geometrías observadas se emparejan componentes y se mide desplazamiento sobre
normales exteriores. Cada muestra puede abstenerse por incertidumbre,
curvatura, intersección inconsistente o mala correspondencia.

## Sustitución por datos reales

El adaptador GeoTIFF produce `FrontObservation` sin depender del origen del
dataset. Para integrar FLAME 3, NASA AMS o una quema controlada se debe construir
un empaquetado que cumpla `GEOTIFF_INPUT_CONTRACT.md`; reconstrucción, salidas y
auditoría permanecen desacopladas del proveedor.

El modelo no convierte una máscara térmica en ground truth. Su validación
externa requiere anotaciones independientes; véase `SCIENTIFIC_CORE.md`.
