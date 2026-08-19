# Adaptadores regionales WFIGS, CWFIS e INPE

Los tres conectores implementan el mismo recorrido:

```text
API/fixture → payload bruto inmutable → normalización GeoJSON
            → manifiesto con hashes → índice deduplicado → estado incremental
```

Entrada CLI:

```powershell
python -m wildfire_front ingest-regional --help
```

Salida predeterminada:

```text
data/open_if/regional/<source_id>/
├── snapshots/<retrieved_at>_<query_hash>/
│   ├── raw/*
│   ├── normalized.geojson
│   └── manifest.json
├── index.geojson
├── latest.geojson
├── latest.json
└── state.json
```

Cada snapshot conserva el payload recibido y su SHA-256. `index.geojson` une observaciones por
`observation_id`: repetir la misma respuesta crea un snapshot auditable, pero no duplica la
observación. `first_seen_at` se conserva y `last_seen_at` avanza.

## Contrato normalizado

Cada `Feature.properties` usa `wfd_fire_observation_v1` y contiene:

- `observation_id`, `source_id`, `upstream_item_id`, `event_id`;
- `observation_kind`, `geometry_semantics`, `role`;
- `observed_at`, `published_at`, `source_updated_at`, `retrieved_at`;
- `first_seen_at`, `last_seen_at`, `crs`;
- `licence_id`, `provisional`, `quality_flags`;
- `candidate_progression_label` y `requires_temporal_pair_audit`;
- `source_url` y `upstream_properties` no nulos.

Los tiempos no se colapsan. Cuando INPE entrega una hora local sin zona, se conserva sin `Z` y se
añade `timestamp_local_timezone_unspecified`.

## WFIGSAdapter

Fuente oficial: [WFIGS Interagency Perimeters FeatureServer](https://services3.arcgis.com/T4QMspbfLg3qTGWY/ArcGIS/rest/services/WFIGS_Interagency_Perimeters/FeatureServer/0).

Ejemplo acotado:

```powershell
python -m wildfire_front ingest-regional `
  --provider wfigs `
  --bbox=-125,32,-114,42 `
  --start 2026-08-01 `
  --end 2026-08-18 `
  --limit 2000 `
  --output-root data/open_if/regional
```

El adaptador:

- pagina como máximo 2.000 entidades por petición;
- solicita GeoJSON en EPSG:4326 y solo los campos necesarios;
- filtra acceso público, visibilidad y borrados en el servidor;
- usa `attr_UniqueFireIdentifier`/IRWIN como identidad de evento;
- conserva `poly_PolygonDateTime` como `observed_at`;
- solo marca candidato un polígono aprobado de categoría `Wildfire Daily Fire Perimeter` con hora;
- mantiene `working_data_may_change=true` y exige pares del mismo evento.

WFIGS publica el mejor perímetro disponible de cada incidente. Una observación aislada no es una
serie de progresión; la serie aparece al conservar snapshots sucesivos o al disponer de varias
geometrías fechadas del mismo evento.

## CWFISAdapter

Contrato oficial: [CWFIS/CWFIF Data Services](https://cwfis.cfs.nrcan.gc.ca/downloads/docs/en/how-tos/how-to-access-cwfis-data-services.pdf).

Capas permitidas:

| Opción CLI | Capa | Semántica WFD | Label de progresión |
|---|---|---|---|
| `activefires` | `public:cwfif_national_activefires` | localización reportada | No |
| `reportedfires` | `public:cwfif_national_reportedfires` | localización reportada | No |
| `hotspots` | `public:hotspots` | punto/píxel térmico | No |
| `fire_perimeter_estimate` | `public:m3polygons` | buffer de hotspots | No |
| `burned_area` | `public:nbac` | scar/composite final o estacional | No |

Ejemplos:

```powershell
python -m wildfire_front ingest-regional `
  --provider cwfis --cwfis-layer activefires --limit 2000

python -m wildfire_front ingest-regional `
  --provider cwfis --cwfis-layer fire_perimeter_estimate --limit 500
```

El servicio CWFIF requiere orden estable (`sortBy=id A`) cuando se usa paginación WFS 2.0. El
adaptador implementa ese dialecto y conserva `record_start`, `record_end`, `status_date` y el resto
de atributos de agencia. Los polígonos M3 quedan bloqueados como proxy: CWFIS los describe como
estimaciones derivadas de hotspots acumulados.

## INPEFireEventsAdapter

Fuente oficial: [Programa Queimadas — datos abiertos](https://www.terrabrasilis.dpi.inpe.br/queimadas/portal/pages/secao_downloads/dados-abertos/index.html).

Ejemplo:

```powershell
python -m wildfire_front ingest-regional `
  --provider inpe `
  --inpe-status both `
  --bbox=-74,-34,-34,6 `
  --limit 5000 `
  --max-bytes 67108864
```

Los KML mundiales de Brasil son grandes; el 18 de agosto de 2026 medían aproximadamente 17,8 MB
para activos y 23,3 MB para observación. Por eso cada respuesta tiene timeout, límite de bytes y
una descarga por estado, seguida de filtrado local por bbox/fecha.

El parser recorre la jerarquía evento → `Frentes`/`Focos` y distingue:

- `provisional_active_fire_front`: candidato débil sujeto a par temporal;
- `active_fire_focus_point`: evidencia térmica, nunca perímetro;
- `provisional_event_extent_estimate`: extensión del evento, no frente activo.

INPE declara el producto Eventos de Fogo en fase provisional de validación. Ninguna geometría se
promueve automáticamente a label fuerte.

## Fixtures y replay offline

`--fixture` evita la red y ejecuta exactamente la misma normalización/materialización:

```powershell
python -m wildfire_front ingest-regional `
  --provider wfigs `
  --fixture tests/fixtures/regional_adapters/wfigs.geojson `
  --output-root outputs/regional_fixture `
  --json
```

Puede repetirse para páginas o estados múltiples. En INPE, el nombre con `ativos/active` u
`observacao/observation` determina el estado del payload.

## Cadencia operativa recomendada

- WFIGS: 15–30 minutos durante incidentes vigilados, siempre por bbox/fecha.
- CWFIS active fires: 60 minutos; la fuente reportada suele actualizarse diariamente.
- CWFIS M3: según uso de contexto, nunca como label.
- INPE eventos activos/observación: cada hora, coincidiendo con la cadencia publicada.

No se recomienda descargar todo el historial en cada ciclo. Los adaptadores son idempotentes, pero
la consulta debe seguir siendo espacial y temporalmente acotada.

## Verificación

Pruebas offline:

```powershell
python -m pytest tests/test_regional_fire_adapters.py -q
python -m ruff check wildfire_front/open_if/regional wildfire_front/cli_regional.py tests/test_regional_fire_adapters.py
```

La suite cubre normalización de los tres proveedores, filtros bbox/fecha, semántica honesta,
materialización completa, hashes, índice incremental idempotente y ejecución real de la CLI.
