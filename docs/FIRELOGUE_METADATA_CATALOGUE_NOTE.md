# Firelogue / Zenodo — Wildfire Risk Management Metadata Catalogue

> Fuente: [https://zenodo.org/records/18410949](https://zenodo.org/records/18410949)  
> Archivo: `DataRegister_Firelogue_v1.xlsx` (~34 kB)  
> Autores: incl. **Claudia Berchtold (née Bach)** et al. (Firelogue + partners)  
> Fecha revisión WFD: 2026-07-17  

## Qué es (y qué no es)

| | Realidad |
|--|----------|
| **Es** | Catálogo de **metadatos** (registro Excel) de datasets de los proyectos Green Deal **LC-GD-1-1-2020** (FIRE-RES, SILVANUS, TREEADS…) + **FirEUrisk** |
| **No es** | Un zip con rasters/perímetros/anclas listas para entrenar o validar Tobarra/Cardoso |
| Tamaño | 21 filas de datasets en hoja `Overview` |
| Proyectos en registro | FirEUrisk 8 · SILVANUS 8 · FIRE-RES 4 · TREEADS 1 |

Cada fila describe: proyecto, headline, aim, tipo de dato, región, fuente, y a menudo un **DOI/URL** de paper o deliverable (no siempre el raw data).

## Utilidad para WildfireFrontDynamics

### Alta (literatura / contexto / links)

| Tema en catálogo | Ejemplo | Uso WFD |
|------------------|---------|---------|
| Fuel moisture Spain | FirEUrisk LFMC semi-mechanistic | Contexto combustible (no es nuestro label LWIR) |
| Fire regimes Europe | GlobFire 2001–2018 | Contexto multi-país |
| Fuel types Iberian Peninsula | FirEUrisk mapping | Capa combustible si se abre simulación |
| Mediterranean critical events 2021 | JRC report | Casos EWE |
| FIRE-RES climate/seasonal | D1.5 en catálogo | Early warning / clima |
| Fuel treatments WUI Greece | FIRE-RES MTT simulations | Simulación landscape |

### Baja / no desbloquea gaps

| Gap WFD | ¿Catálogo lo resuelve? |
|---------|------------------------|
| O1 2ª ancla Vp/ha CLM | **No** |
| O2 perímetro oficial Tobarra/Cardoso | **No** |
| Datos Heligrafics / INFOCAM | **No** |
| Pesos / parches CLM | **No** |

## Respuesta a la pregunta de Claudia

> *“Would you be looking for operational staff that can validate the model?”*

**Sí, en parte** — pero hay que especificar **dos productos distintos**:

1. **Ops** (`incident_runtime` / frente LWIR): validación con **personal operativo** (INFOCAM/GEACAM/CMA) que aporte **Vp, ha, parte de comportamiento**, y opcionalmente perímetro oficial.  
2. **ML** (`clm_ensemble_v34`): validación **técnica** holdout ya hecha; el feedback operativo sería sobre **utilidad del producto** (brief, mapas, disclaimers), no re-tunear IoU.

Redirección útil: contactos **España / CLM** con mandos o técnicos de observación aérea / INFOCAM, o living labs Firelogue con experiencia **durante evento**, no solo riesgo estático.

## Acción recomendada

1. Agradecer catálogo; ya descargado en revisión local.  
2. Contestar especificando request (borrador abajo).  
3. Opcional: scrapear URLs del Excel a `OPEN_RESOURCES` (solo links abiertos).  
4. No gastar sprints ML en re-leer las 21 filas: el valor es **mapa de papers + redirección a ops**.

## DOI

- Record: https://doi.org/10.5281/zenodo.18410949 (si asignado en página; URL canónica del record: zenodo.org/records/18410949)
