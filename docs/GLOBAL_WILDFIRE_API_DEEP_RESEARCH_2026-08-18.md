# Deep research de APIs globales para WildfireFrontDynamics

Fecha de corte: 2026-08-18  
Registro máquina-legible: `research/global_wildfire_api_registry_2026.json`  
Sonda reproducible: `scripts/probe_global_wildfire_apis.py`

## Resultado ejecutivo

Se han catalogado 37 servicios programáticos de alcance global o regional estratégico:

- 11 P0: integrar o endurecer ahora.
- 18 P1: alto valor, detrás de los P0.
- 7 P2: covariables, impacto o cobertura complementaria.
- 1 P3: útil para producto/impacto, no para el núcleo de propagación.

La oportunidad no está en acumular más hotspots. El mayor salto para WFD es combinar:

1. descubrimiento mundial de incidentes;
2. perímetros fechados o delineaciones sucesivas;
3. imagen EO adquirida antes de cada horizonte;
4. meteorología de la corrida que habría estado disponible en ese momento;
5. combustible, humedad y terreno versionados;
6. trazabilidad completa de observación, publicación y descarga.

La primera prueba acotada ejecutó 29 fuentes P0/P1, de forma secuencial y con un máximo de 256 KiB por respuesta. La primera pasada obtuvo 23 `PASS`, 3 `FAIL` y 3 `SKIP`. Tras corregir el enlace antiguo, LANDFIRE respondió `200`, quedando 24 servicios verificados directamente. El índice DWD ICON está activo, pero el Python local no pudo construir su cadena TLS; no se desactivó la verificación. El endpoint auxiliar de países de FIRMS devolvió `400`, aunque la documentación oficial sigue publicando ese contrato. Los tres `SKIP` son deliberados: falta de clave o ausencia de una consulta inocua declarada.

## Decisión principal: recolección dirigida por eventos

No conviene hacer un volcado mundial recurrente. NASA advierte que una consulta VIIRS de todo el mundo puede producir entre 30.000 y más de 100.000 filas por día. FIRMS además usa una clave gratuita y cuotas por ventana temporal. La estrategia recomendada es:

```text
FIRMS / EONET / INPE / DEA / AFIS
              │
              ▼
       cola global de incidentes
              │
       bbox + tiempo + región
              │
      ┌───────┼────────┬───────────┐
      ▼       ▼        ▼           ▼
 perímetros   EO   meteo/run   fuel/terrain
      └───────┴────────┴───────────┘
              │
              ▼
   snapshot inmutable + auditoría
```

Frecuencia propuesta:

- Descubrimiento global: cada 10–15 minutos donde la licencia y la cuota lo permitan.
- Enriquecimiento: solo para incidentes nuevos o actualizados.
- Perímetros: sondeo regional condicionado por actividad y `last_updated`.
- EO: búsquedas STAC por `bbox`, intervalo, nube y colección; descargar solo assets/bandas necesarios.
- Meteo: capturar identificador de modelo, `run_at`, `valid_at` y hora real de disponibilidad.
- Covariables estáticas: cachearlas por tesela y versión, no por incidente.

La documentación oficial de [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/content/academy/data_api/firms_api_use.html) respalda las cuotas, la clave y el volumen mundial. Sus puntos térmicos sirven para descubrimiento/evidencia, no representan una línea de fuego ni un perímetro.

## Qué usaríamos ya

| Prioridad | Fuente | Aporte real a WFD | Decisión |
|---|---|---|---|
| P0 | NASA FIRMS | Descubrimiento mundial, hora de adquisición, sensor, confianza y FRP | Mantener/robustecer el adaptador; consultas por bbox y 1–5 días; nunca crear perímetros con convex hull |
| P0 | Copernicus EMS Rapid Mapping | Delineaciones y monitorizaciones sucesivas de incendios distribuidos globalmente | Es la mejor palanca abierta para ampliar pares temporales fuera de EE. UU.; conservar sensor, product type y observation/delivery time |
| P0 | WFIGS | Perímetros interagencia de EE. UU. vía ArcGIS REST | Construir adaptador de snapshots fechados; aporta labels de progresión de gran valor, sujetos a auditoría temporal |
| P0 | CWFIS | Active fires, hotspots, danger, weather y capas canadienses por OGC | Construir adaptador WFS/WMS y descubrir qué capas conservan historia apta para pares |
| P0 | INPE Queimadas | Hotspots cada ~10 min y eventos/fronts/área/duración en Brasil | Integrar `eventos de fogo`, no solo focos; puede abrir una fuente regional de progresión |
| P0 | CDSE STAC + Earth Search | Sentinel-2, Landsat y colecciones EO consultables por espacio/tiempo | Unificar detrás de una interfaz STAC y elegir proveedor por colección, latencia y coste |
| P0 | ECMWF Open Data | IFS/AIFS operacionales globales | Fuente primaria de forecast operacional; preservar corrida y validez |
| P0 | Open-Meteo Historical Forecast | Acceso simple a corridas históricas de modelos | Excelente broker de prototipado y replay; fijar explícitamente el modelo, no usar un blend silencioso |
| P0 | ERA5/CDS | Reanálisis coherente para experimentos históricos | Solo covariable retrospectiva; no llamarlo forecast operacional |
| P0 | AEMET OpenData | Observación convencional, radar, rayos, NDVI y mapas de riesgo en España | Integrar para el piloto español; clave obligatoria en llamadas de datos |
| P1 | NOAA GOES + EUMETSAT | Alta frecuencia geoestacionaria en Américas/Europa/África | Usar para evidencia de timing/nube/señal térmica; no como polígono ground truth |
| P1 | CLMS / DEA FMC / LANDFIRE | Humedad, vegetación y combustibles | Cachear por versión; muy valioso para dominio regional y ablaciones |
| P1 | OSM Overpass | Carreteras, poblaciones e infraestructura | Contexto operativo y de exposición, nunca etiqueta de propagación |

Contratos oficiales relevantes:

- [FIRMS Area API](https://firms.modaps.eosdis.nasa.gov/api/area/)
- [Copernicus EMS Mapping](https://mapping.emergency.copernicus.eu/)
- [WFIGS ArcGIS FeatureServer](https://services3.arcgis.com/T4QMspbfLg3qTGWY/ArcGIS/rest/services/WFIGS_Interagency_Perimeters/FeatureServer)
- [CWFIS Data Services](https://cwfis.cfs.nrcan.gc.ca/downloads/CWFIS_DataServices_HowtoAccessDailyMaps%26DataLayers.pdf)
- [INPE Queimadas: datos abiertos](https://www.terrabrasilis.dpi.inpe.br/queimadas/portal/pages/secao_downloads/dados-abertos/index.html)
- [Copernicus Data Space STAC](https://documentation.dataspace.copernicus.eu/APIs/STAC.html)
- [Earth Search](https://github.com/Element84/earth-search/blob/main/README.md)
- [ECMWF Open Data](https://github.com/ecmwf/ecmwf-opendata)
- [CDS API](https://cds.climate.copernicus.eu/how-to-api)
- [Open-Meteo Historical Forecast](https://open-meteo.com/en/docs/historical-forecast-api)
- [AEMET OpenData](https://opendata.aemet.es/dist/index.html)

## Cobertura mundial por función

### Descubrimiento y fuego activo

- Global: FIRMS, EONET y GWIS.
- Brasil/LatAm: INPE y MapBiomas; FIRMS cubre el resto mientras se incorporan agencias nacionales.
- Norteamérica: WFIGS, CWFIS y GOES.
- Australia: DEA Hotspots y NAFI.
- África: AFIS y Digital Earth Africa.
- Europa/África: EUMETSAT y GWIS; AEMET aporta profundidad en España.

[EONET v3](https://eonet.gsfc.nasa.gov/docs/v3) es útil para metadatos y referencias cruzadas, no para ground truth. [DEA Hotspots](https://knowledge.dea.ga.gov.au/data/product/dea-hotspots/?tab=access) publica WFS/WMS/GeoJSON/KML, actualización frecuente y limitaciones explícitas de precisión/uso. [AFIS](https://www.afis.co.za/afisapi/) añade una ruta programática regional africana.

### Etiquetas de progresión

Las fuentes más prometedoras son CEMS, WFIGS, CWFIS, INPE, NAFI y MapBiomas. Aun así, la etiqueta `progression_label` en el registro significa “candidata a auditoría”, no aprobación automática. Antes de entrenar debe verificarse:

- que existan dos observaciones del mismo incidente;
- que `observed_at` sea real y no se sustituya por `published_at`;
- que el perímetro posterior no sea simplemente el scar final;
- que la geometría represente extensión/edge y no hotspot, área administrativa o bounding box;
- que licencia y redistribución permitan el uso propuesto;
- que el split sea por evento, no por tesela.

### Observación de la Tierra

- [CDSE STAC](https://documentation.dataspace.copernicus.eu/APIs/STAC.html): ruta principal para Copernicus.
- [Earth Search](https://element84.com/earth-search/examples/): alternativa STAC abierta y directa sobre colecciones en AWS.
- [NASA CMR STAC](https://cmr.earthdata.nasa.gov/search/site/docs/search/stac): acceso normalizado al catálogo NASA.
- [Planetary Computer STAC](https://planetarycomputer.microsoft.com/docs/quickstarts/reading-stac/): catálogo amplio; algunos assets requieren firmar URLs.
- [Digital Earth Africa STAC](https://docs.digitalearthafrica.org/en/latest/sandbox/notebooks/Frequently_used_code/Downloading_data_with_STAC.html): acceso regional listo para análisis.
- [NOAA GOES Open Data](https://registry.opendata.aws/noaa-goes/) y [EUMETSAT Data Store](https://user.eumetsat.int/resources/user-guides/data-store-detailed-guide): alta frecuencia geoestacionaria.

Recomendación técnica: un solo `STACBroker` con adaptadores de autenticación/firma, selección de assets, control de CRS y caché por `collection/item/asset/etag`.

### Meteorología

Tres clases deben permanecer separadas:

1. Forecast operacional: ECMWF Open Data, GFS/NOMADS, DWD ICON, AEMET/ECCC regionales.
2. Archivo de forecast: Open-Meteo Historical Forecast o archivos nativos de cada centro.
3. Reanálisis: ERA5; útil para retrospectiva, inválido como prueba de disponibilidad operacional pasada.

Fuentes oficiales: [NOAA NOMADS GFS](https://nomads.ncep.noaa.gov/pub/data/nccf/com/gfs/prod/), [DWD ICON](https://opendata.dwd.de/weather/nwp/icon/grib/), [ECCC GeoMet](https://eccc-msc.github.io/open-data/msc-geomet/ogc_api_en/) y [NASA POWER](https://power.larc.nasa.gov/docs/services/api/). POWER es cómodo y global, pero su escala es demasiado gruesa para sustituir a un forecast de viento local.

### Combustible, humedad y terreno

- [Copernicus Land Monitoring Service](https://land.copernicus.eu/en/how-to-guides) y sus productos de [soil moisture](https://land.copernicus.eu/en/products/soil-moisture).
- [SoilGrids REST](https://rest.isric.org/soilgrids/v2.0/docs), sujeto a una cuota pública conservadora.
- [OpenTopography](https://opentopography.org/developers), con clave para APIs de DEM global.
- [LANDFIRE](https://www.landfire.gov/help), que ofrece combustible, vegetación, régimen histórico y topografía en EE. UU. mediante LFPS.
- DEA Fuel Moisture para Australia y MapBiomas para uso/cobertura/fuego en Latinoamérica.

El terreno se cachea prácticamente una vez. Combustible/humedad exige `version`, fecha de validez y una política explícita para datos faltantes.

### Impacto y contexto

[CAMS GFAS](https://ads.atmosphere.copernicus.eu/datasets/cams-global-fire-emissions-gfas) aporta emisiones de fuego; [OpenAQ v3](https://docs.openaq.org/api) observaciones de calidad de aire; [Global Forest Watch Tiles API](https://tiles.globalforestwatch.org/) contexto forestal; y [Overpass API](https://wiki.openstreetmap.org/wiki/Overpass_API) infraestructura y asentamientos. Son entradas de impacto/exposición, no ground truth de propagación.

## Contrato mínimo de cada observación

Todo adaptador debe emitir, como mínimo:

```json
{
  "source_id": "...",
  "upstream_item_id": "...",
  "event_id": "...",
  "observation_kind": "hotspot|perimeter|eo|weather|fuel|terrain|impact",
  "observed_at": "...",
  "published_at": "...",
  "retrieved_at": "...",
  "forecast_run_at": null,
  "valid_at": null,
  "bbox": [0, 0, 0, 0],
  "crs": "EPSG:4326",
  "nominal_resolution_m": null,
  "geometry_semantics": "point|pixel|edge|extent|scar|administrative",
  "role": "event_discovery|progression_label|eo_input|weather_input|fuel_input|terrain_input|impact_context",
  "quality_flags": [],
  "licence_snapshot": "...",
  "source_url": "...",
  "sha256": "..."
}
```

Reglas duras:

- `observed_at`, `published_at`, `retrieved_at`, `forecast_run_at` y `valid_at` nunca se colapsan en un único timestamp.
- Un hotspot conserva semántica de punto/píxel; no se convierte en label de perímetro.
- Un scar final no produce por sí solo una secuencia temporal.
- Toda descarga es inmutable, con hash y metadatos de licencia.
- Los reintentos usan backoff, `ETag`/`Last-Modified` cuando existan y límites por proveedor.
- Los fallos de cobertura se expresan como `MISSING/HOLD`, no como ceros físicos inventados.

## Sprint recomendado

### 1. Más labels, no más catálogos

Construir `WFIGSAdapter`, `CWFISAdapter` e `INPEFireEventsAdapter`. El objetivo de aceptación no es “descarga funciona”, sino número de incidentes con dos o más perímetros auditables, distribución de `Δt`, derechos y separación por evento.

Estado 2026-08-18: implementados end-to-end mediante `wildfire-front ingest-regional`, con payload bruto, contrato normalizado, hashes, snapshots, índice incremental, fixtures y pruebas. CWFIS se mantiene deliberadamente como descubrimiento/proxy y no produce labels de progresión; WFIGS e INPE solo producen candidatos que requieren auditoría temporal.

### 2. Broker meteorológico con replay honesto

Crear un contrato común para ECMWF, GFS, ICON y Open-Meteo. Cada tensor debe poder demostrar qué corrida se usó y si estaba disponible antes de `t0`.

### 3. Broker STAC

Consolidar CDSE, Earth Search, CMR, Planetary Computer y DE Africa. Evitar lógica de proveedor dentro del dataset/modelo.

### 4. Covariables regionales

- España: AEMET + CLMS.
- EE. UU.: WFIGS + LANDFIRE + GOES.
- Canadá: CWFIS + ECCC.
- Brasil: INPE + MapBiomas.
- Australia: DEA/NAFI + fuel moisture.
- África: AFIS + DE Africa + EUMETSAT.

### 5. Observabilidad de ingesta

Medir por fuente: frescura, latencia, tasa de error, cuota restante, bytes, número de eventos nuevos/actualizados, duplicados y porcentaje de registros con derechos resueltos.

## Qué no haría

- No descargaría cada asset mundial de FIRMS, Sentinel, GOES o MTG.
- No entrenaría con hotspots rasterizados como si fueran perímetros.
- No mezclaría ERA5 con forecasts operacionales bajo el mismo nombre de canal.
- No usaría imágenes adquiridas después de `t0` para predecir el frente de `t1`.
- No publicaría ni redistribuiría datos con derechos desconocidos.
- No declararía cobertura mundial solo porque una API acepte `bbox=world`; cobertura, latencia y calidad son propiedades distintas.

## Evidencia de ejecución

La sonda realiza solo `GET` permitidos por el registro, secuencialmente, con timeout y límite de bytes. No guarda secretos ni descarga productos masivos. Los resultados crudos quedan en:

- `docs/GLOBAL_WILDFIRE_API_PROBE_2026-08-18.json`
- `docs/GLOBAL_WILDFIRE_API_PROBE_RETRY_2026-08-18.json`

El registro completo contiene por fuente: geografía, roles, señales, interfaz, autenticación, licencia, cadencia, resolución, prioridad, score, uso recomendado, bloqueos, documentación y probe seguro.
