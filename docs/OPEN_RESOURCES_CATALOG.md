# Catálogo de recursos abiertos (repos, datos, APIs)

Recursos **a mano** para mejorar precisión y producto de emergencia.  
Prioridad: integrables sin contrato / con acceso público.

---

## 1. Datos satélite de fuego (perímetro / hotspots)

| Recurso | Qué da | Acceso | Uso en WFD |
|---------|--------|--------|------------|
| **NASA FIRMS** | Hotspots MODIS/VIIRS (puntos ~375 m) | CSV país/año sin key; API con MAP_KEY gratis | `scripts/fetch_firms_hotspots.py` → overlay dirección |
| **EFFIS / CEMS** | Burnt areas >30 ha, active fires, FWI | [Viewer](https://forest-fire.emergency.copernicus.eu/) · [Data & services](https://forest-fire.emergency.copernicus.eu/applications/data-and-services) · form para históricos | O2 perímetro cuando haya BA en fecha/IF |
| **Copernicus EMS Rapid Mapping** | Delineation/grading shapefiles | [API](https://mapping.emergency.copernicus.eu/api/redoc/) · [Portal](https://mapping.emergency.copernicus.eu/) | Perímetros oficiales de activaciones |
| **GWIS** | Global wildfire info | Copernicus/JRC | Contexto multi-país |

**FIRMS Europe 24h (NRT):**  
https://firms.modaps.eosdis.nasa.gov/data/active_fire/noaa-20-viirs-c2/csv/J1_VIIRS_C2_Europe_24h.csv  

**FIRMS España 2024 VIIRS (archivo):**  
https://firms.modaps.eosdis.nasa.gov/data/country/viirs-snpp/2024/viirs-snpp_2024_Spain.csv  

---

## 2. España / CLM (anclas y contexto)

| Recurso | Qué da | Link |
|---------|--------|------|
| **EGIF (MITECO)** | Partes nacionales, ha, fechas (XML/Excel) | https://servicio.mapa.gob.es/incendios/Search/Publico |
| **INFOCAM portal** | Mapa/riesgo CLM (no API abierta completa) | https://infocam.castillalamancha.es/ |
| **EGIF stats MITECO** | Estadística general | https://www.miteco.gob.es/es/biodiversidad/temas/incendios-forestales/estadisticas-datos.html |
| **Heligrafics / CMA** | LWIR + KMZ (ya en Dropbox del proyecto) | Contacto Pablo |

---

## 3. Repositorios de simulación / ROS (física)

| Repo | Qué es | Link | Cómo nos ayuda |
|------|--------|------|----------------|
| **ForeFire** | Motor C++ ROS + NetCDF, JOSS | https://github.com/forefireAPI/forefire | Comparar ROS física vs observada |
| **ELMFIRE** | Level-set operativo (US) | https://github.com/lautenberger/elmfire · https://elmfire.io | Referencia de forecasting real |
| **Rothermel / Behave** | Clásicos USFS | Literature + implementaciones varias | Calibrar head ROS con wind/slope |
| **Wang Zhengfei 王正非 (CN)** | ROS empírico viento×pendiente×combustible | **In-repo** `wildfire_front/cn_wang_zhengfei.py` · mega: `docs/MEGA_ANALISIS_CHINA_LINHUO.md` | Prior / anisotropía envelope |
| **xllyll/fire-spread** | Java polar 360° + DEM (CN) | https://github.com/xllyll/fire-spread | Patrón rayos; vendored `_vendor_cn/` |
| **CesiumFire** | Vue+Cesium linhuo | https://github.com/winrelde/CesiumFire | Ideas UI 3D |
| **YongfengX WildfireSpreadTS** | Mejoras ML next-day (FNO) | https://github.com/YongfengX/wildfire-spread-prediction | Research only (G1 KILL) |

```bash
python scripts/run_cn_physics_prior.py --obs-ros 5.71 --ca
```

---

## 4. Repositorios ML / datasets

| Repo / dataset | Link | Nota |
|----------------|------|------|
| **Next Day Wildfire Spread (Huot)** | https://www.kaggle.com/datasets/fantineh/next-day-wildfire-spread | Nuestro `ndws_v21` |
| **WildfireSpreadTS** | Multi-día multi-modal | Mejor que Huot para temporal serio |
| **TS-SatFire** | https://github.com/zhaoyutim/TS-SatFire | Ciclo de vida satelital |
| **Orion WildFireSpread** | https://github.com/Orion-AI-Lab/WildFireSpread | Burned area final |
| **TEI WildfireSpread** | https://github.com/dwgb93/TEI_WildfireSpread | NDWS notebooks |
| **Mesogeos / fire datasets survey** | varios en GitHub “Fire-datasets” | Inventario tareas |

---

## 5. Meteo / combustible

| Recurso | Link / vía |
|---------|------------|
| **AEMET** open data | open data AEMET (API key) |
| **ERA5-Land** | CDS Copernicus |
| **EFFIS FWI forecasts** | Data & services EFFIS |
| **LFMC / fuel moisture** | papers USFS + productos ML satelitales |

---

## 6. Foros / comunidades

| Comunidad | Para qué |
|-----------|----------|
| **r/wildfire**, **r/gis**, **r/MachineLearning** | Dudas ops/GIS/ML |
| **GIS Stack Exchange** | CRS, WFS, QGIS |
| **EFFIS / Copernicus forums** | Acceso a capas |
| **JOSS / ForeFire issues** | Simulación open source |
| **X / LinkedIn INFOCAM–CLM** | Contexto operativo (no datos crudos) |

---

## 7. Integración en este repo (hecho / siguiente)

| Script / módulo | Estado |
|-----------------|--------|
| `scripts/fetch_firms_hotspots.py` | **Implementado** — hotspots VIIRS/MODIS España |
| `wildfire_front/sector_ros_local.py` | **Implementado** — sectores desde `local_speeds.csv` |
| `scripts/export_pack_geojson_wgs84.py` | Mapa Leaflet WGS84 |
| EFFIS WFS automatic | Parcial (viewer + form; descarga BA a demanda) |
| EGIF parser | Siguiente (XML → anchors) |

### Comandos

```bash
python scripts/fetch_firms_hotspots.py --fire tobarra_20240802 --date 2024-08-02
python scripts/enrich_emergency_ops.py --packs tobarra_20240802,cardoso_2025
python scripts/emergency_briefing.py --fires tobarra_20240802,cardoso_2025
python scripts/export_pack_geojson_wgs84.py --fires tobarra_20240802
```
