# Pista B — IF famoso / open data (sin LWIR Heligrafics)

## Objetivo

Validar métodos y gates con **datos públicos reproducibles**, en paralelo a CLM/Pablo.

## Packs generados

| Activación CEMS | Localización (CEMS) | max ha (CEMS) | Timeline pasos | Path |
|-----------------|---------------------|---------------|----------------|------|
| **EMSR578** | España jun-2022 (Artesa de Segre / multi-AOI) | ~2693 | 5 (FEP→DEL→MONIT→GRA) | `outputs/open_if/emsr578/` |
| **EMSR583** | España jun-2022 (misma ola CEMS) | ~1791 | 5 | `outputs/open_if/emsr583/` |

Fuente: [Copernicus EMS Rapid Mapping](https://mapping.emergency.copernicus.eu/).

## Cómo regenerar

```bash
pip install shapely pyproj
python scripts/build_open_if_pack.py --activation EMSR578
python scripts/build_open_if_pack.py --activation EMSR583
# abrir mapa
start outputs/open_if/emsr578/map.html
```

## Artefactos por pack

| Archivo | Contenido |
|---------|-----------|
| `manifest.json` | Provenance, productos, timeline, ROS proxy, papers FIRE-RES |
| `vectors/*.geojson` | Perímetros fire (`observedEventA`) por producto |
| `timeline_perimeters.geojson` | Capas multi-temporal |
| `map.html` | Leaflet + OSM |
| `operator_brief_open_if.md` | Brief 1 página |
| `scorecard_pista_b.json` | Gates O2/O1 open-data |
| `raw_cems/` | Zips CEMS originales (cache) |

## Métricas (sin LWIR)

1. **Área ha** por producto CEMS (proyección equal-area).  
2. **Crecimiento** ha/h entre productos (Δt **asumido 24 h** si no hay tiempo de adquisición en props).  
3. **ROS proxy** por radio equivalente de círculo.  
4. **Hausdorff** perímetro_t vs perímetro_t-1 (CEMS↔CEMS).  

## Gates honestos

| Gate | Estado pack |
|------|-------------|
| O2 delineación CEMS open | **GO** |
| O2 perímetro nacional/catastral oficial | **NO_GO_CEMS_PROXY** (no inventar) |
| O1 multi-fuente open (ha/timeline públicos) | **GO_PROXY** |
| Requiere Heligrafics | **No** |

## Contexto papers

- FIRE-RES D1.1, D5.3 (en `manifest.json` → `papers_and_context`)  
- Contraste: simulación EWE fire–atmósfera vs **perímetro satelital de emergencia**

## Relación con Pista A (CLM)

| Pista A | Pista B |
|---------|---------|
| Secuencias LWIR + ROS local | Perímetros CEMS multi-día |
| Ancla Pablo/INFOCAM | Datos sin NDA |
| Producto diferencial | Demo TFG / O2 proxy / brief |

## Limitaciones

- CEMS no es perímetro “nacional definitivo”.  
- Δt 24 h es **hipótesis** para ROS proxy.  
- dNBR Sentinel no se descarga aquí (API/STAC aparte); el pack ya da perímetro BA de emergencia.  
