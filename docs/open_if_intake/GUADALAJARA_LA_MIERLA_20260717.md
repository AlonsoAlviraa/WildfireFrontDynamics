# Open intake — IF La Mierla (Guadalajara) 2026-07

**Prioridad WFD:** máxima entre los tres grandes de julio-2026 (CLM + activo + satélite denso + prensa + INFOCAM).  
**event_id propuesto:** `guadalajara_la_mierla_20260717`  
**Recolectado (UTC scrape):** 2026-07-22 (web + X + FIRMS)  
**Update detallado:** [LA_MIERLA_UPDATE_20260722.md](LA_MIERLA_UPDATE_20260722.md)  
**Loop-engineering pack:** `outputs/open_if/la_mierla_20260717/`  
**Plan semanal (16–21 jul + sprints):** [LA_MIERLA_WEEK_PLAN.md](../design/LA_MIERLA_WEEK_PLAN.md)  
**Solicitud datos (borrador, no enviado):** [SOLICITUD_LA_MIERLA_INFOCAM.md](SOLICITUD_LA_MIERLA_INFOCAM.md)

### CLI (cadence + legado)

```bash
# Recomendado: un solo comando de día open (timeline + CEMS WATCH + decide HOLD + week_package)
set PYTHONPATH=.
python scripts/run_la_mierla_open_day.py

# Offline (sin re-fetch FIRMS/STAC)
python scripts/run_la_mierla_open_day.py --skip-network

# Intentar dNBR (honesto: BLOCKED si no hay post clear)
python scripts/run_la_mierla_open_day.py --try-dnbr

# Pack / enrich por separado
python scripts/build_la_mierla_open_pack.py
python scripts/enrich_la_mierla_satellite.py

# Decide manual
PYTHONPATH=. python -m wildfire_front.cli decide --event-id guadalajara_la_mierla_20260717 --open-pack outputs/open_if/la_mierla_20260717 --policy field_ops --output outputs/open_if/la_mierla_20260717/fire_decision_card_field_ops.json
```

**Estado de ancla:** `pending_external` — **no** confirmed (falta Vp/ha oficial EGIF; **30–32k ha** = estimación INFOCAM/prensa 21–22 jul, no ancla O1). Fase open: **estabilización**. Guard: `wildfire_front.open_if.anchor_guard`.

---

## Por qué este IF (más información usable)

| Criterio | La Mierla | Orés (Zaragoza) | Los Gallardos (Almería) |
|----------|-----------|-----------------|-------------------------|
| Dominio CLM (pipeline real_if) | **Sí** | No (Aragón) | No (Andalucía) |
| FIRMS NRT 24h (2026-07-22) | **~273 hotspots** (baja vs 658 el 21) | ~0 en bbox | ~0 |
| Cobertura prensa 20–22 jul | Muy alta (récord + visita Sánchez) | Alta | Media |
| Perfil X oficiales | INFOCAM, GC, SER GU | 112 Aragón, GC | INFOCA |
| ha reportadas (open) | **30–32k** est.; fase **estabilización** | ~15–15.8k | ~6.6–7k + víctimas |

---

## Hechos consolidados (fuentes abiertas)

| Campo | Valor | Fuentes (open) | Confianza |
|-------|--------|----------------|-----------|
| Nombre | IF La Mierla / Sierra Norte de Guadalajara | El País, Euronews, EP, INFOCAM | alta |
| Detección | **Jueves 16 jul 2026 ~13:55** (COR/Infocam) | Infobae / COR CLM vía prensa | alta |
| Municipio inicio | **La Mierla** (Sierra Norte) | El País | alta |
| ha 20 jul | **~26.000 ha**; perímetro **~120 km** | [El País 20 jul](https://elpais.com/espana/2026-07-20/las-llamas-no-dan-tregua-en-la-mierla-32-pueblos-evacuados-y-26000-hectareas-afectadas.html), Euronews | media-alta (provisional) |
| ha 21 jul AM | **~29.000 ha estimadas** | @Plan_INFOCAM AM + EP | media-alta |
| ha 21 jul PM | **+30.000** · **fase estabilización** | @Plan_INFOCAM 2079631495405203691 | media-alta |
| ha 21–22 jul | **30–32.000** (rango) | Fernández EFE; EP/EFE 22 jul | media |
| Fase | **Estabilización** (no controlado) | INFOCAM + Fernández | alta |
| Récord | Mayor de la historia CLM (supera Riba de Saelices 2005 ~13k ha) | El País, Euronews | media-alta |
| Evacuados | **>1.200** personas; **34 municipios** evacuados; **14** confinados | INFOCAM X 21 jul 08:33Z | alta |
| Nivel | **Nivel 2** (INFOCAM: Nivel 3 = cambio dirección, no más medios) | INFOCAM 10:23Z Almodóvar PMA | alta |
| PMA | **Tamajón** / Guadalajara | El País / INFOCAM | alta |
| Cabeza / avance | Defensa núcleos + ataque cabeza; frena flanco **Soria** (Barcones–Retortillo evacuados) | INFOCAM + prensa 21 jul | media |
| Medios (21 jul AM) | **72** terrestres / **394** efectivos; noche anterior fuego técnico + maquinaria | INFOCAM X 08:33Z | alta |
| Medios (20 jul) | ~400 efectivos, ~30 aéreos; UME + Madrid + CyL; coste ~**50 M€** (Page) | El País | media |
| Origen (investigación) | Parcela de cereal / cosechadora; investigación GC (prensa cita alcalde Robledillo de Mohernando — **presunción de inocencia**, no usar en producto) | Euronews | baja para producto |
| Meteorología | Ola de calor; rachas ~50 km/h; Aemet propagación extrema | El País / Euronews | media |

### Evacuaciones / localidades citadas (no exhaustivo)

Primeras / mencionadas en prensa: Arroyo de Fraguas, Zarzuela de Jadraque, La Mierla, Muriel, Umbralejo, Semillas, Bustares, Villares de Jadraque, Veguillas, Prádena de Atienza, Robledo de Corpes, Aldeanueva de Guadalajara, Naharros…  

Nuevas citadas GC 21 jul: **Miedes de Atienza, Hijes, Bañuelos, Romanillos de Atienza, Casillas, Bochones**.  

Acogida: polideportivo **Humanes** (Cruz Roja), IES Brianda de Mendoza / Residencia Los Guzmán (Guadalajara).

### Mapa prensa

- Datawrapper citado por El País: `https://datawrapper.dwcdn.net/OwoD2/full.png` (ubicación; no vector WFD).

---

## Datos abiertos ya bajados al repo

| Archivo | Contenido |
|---------|-----------|
| `outputs/firms/guadalajara_la_mierla_20260717/firms_hotspots_wgs84.geojson` | **595** puntos VIIRS NRT 24h (WGS84) |
| `.../firms_viirs_nrt_24h_filtered.csv` | Mismo filtro CSV |
| `.../firms_summary.json` | Stats: extent lat 40.98–41.23, lon −3.19–−2.91; FRP mean 22.5 MW, max 429, sum ~13400 |
| `docs/open_if_intake/guadalajara_la_mierla_20260717_inventory.json` | Inventario máquina |

**Fuente FIRMS:**  
`https://firms.modaps.eosdis.nasa.gov/data/active_fire/noaa-20-viirs-c2/csv/J1_VIIRS_C2_Europe_24h.csv`  
**Bbox filtro:** lat [40.7, 41.4], lon [−3.4, −2.7].

### Comando re-fetch

```bash
# Re-descarga manual (o re-ejecutar el pipeline que generó outputs/firms/...)
python scripts/fetch_firms_hotspots.py --help
```

---

## Fuentes web scrapeadas / leídas (2026-07-21, refresh loop)

| Fuente | URL / handle | Uso |
|--------|--------------|-----|
| El País 20 jul | elpais.com/...la-mierla...26000-hectareas... | ha, perímetro, PMA, medios, Soria |
| Euronews 20 jul | es.euronews.com/...26000-hectareas... | ha, origen, política, despliegue |
| Europa Press 21 jul | europapress.es/...29000-hectareas... | ha 29k, campamento niños |
| **@Plan_INFOCAM** | post **2079484888751710377** 08:33Z | **PRIMARY:** 29k ha, 34+14, 72/394, Nivel 2 |
| **@Plan_INFOCAM** | post **2079512599058592198** 10:23Z | Nivel 2 vs 3; PMA Guadalajara |
| @AT_Brif | post 2079513423402893431 10:26Z | reconocimiento aéreo BRIF Tabuyo |
| @europapress | post 2079516083950612662 10:37Z | 29k ha; campamento 100 niños |
| @ElDecanodeGuad1 | 10:21Z | Barcones + residencia Retortillo (Soria) |
| Objetivo CLM / La Razón CLM | X 21 jul | Page ofensiva ~600 operarios; freno Soria |

**Artefacto scrape pack:** `outputs/open_if/la_mierla_20260717/scrape_latest.json`  
**X:** `from:Plan_INFOCAM (Mierla OR Guadalajara)` + `#IFLaMierla` — INFOCAM es la única fuente operativa primaria; resto prensa/opinión.

---

## Encaje en WFD (honesto)

| Pista | ¿Listo? | Acción |
|-------|---------|--------|
| **Open overlay FIRMS** | **Sí** | GeoJSON en `outputs/firms/...` |
| **Open IF dNBR/STAC** | Parcial | Cuando despeje nubes: `build_open_if_*` / STAC S2 sobre bbox FIRMS |
| **CEMS EMSR** | Pendiente | Vigilar [mapping.emergency.copernicus.eu](https://mapping.emergency.copernicus.eu/) por activación Sierra Norte |
| **Ops ROS / incident LWIR** | **No** | Falta material térmico INFOCAM/dron |
| **Ancla O1 confirmed** | **No** | Solicitar Vp + ha oficiales; hasta entonces `pending_external` |
| **ML fine-tune** | **No** | Sin parches legacy17 de este IF |

### Stub ancla (JSON conceptual — no mezclar con confirmed)

```json
{
  "fire_id": "guadalajara_la_mierla_20260717",
  "status": "pending_external",
  "name": "La Mierla / Sierra Norte de Guadalajara",
  "ccaa": "Castilla-La Mancha",
  "province": "Guadalajara",
  "start_date_local": "2026-07-16",
  "ha_press_max_reported": 29000,
  "ha_source": "prensa (EP/El País); provisional",
  "vp_m_min": null,
  "firms_nrt_hotspots_24h": 595,
  "notes": "FIRMS only open layer until LWIR/anchor. Do not use press ha as official."
}
```

---

## Comparativa rápida Orés (2º en info, menos satélite hoy)

| | Orés (Cinco Villas) |
|--|---------------------|
| Inicio | ~mié 15 jul 2026 |
| ha | ~15.000–15.800; perímetro ~60–78 km |
| Evacuados | 6 pueblos (Orés, Asín, Luesia, Malpica de Arba, Uncastillo, …); realojo 20–21 jul; **nivel 1** 21 jul (GC) |
| FIRMS 24h (21 jul) | ~0 en bbox (baja actividad residual) |
| WFD | Mejor para **post-fuego open** (dNBR) que live |

---

## Enriquecimiento satélite (2026-07-21)

**Script:** `python scripts/enrich_la_mierla_satellite.py`  
**Mapa satélite (local):** [map_satellite.html](../../outputs/open_if/la_mierla_20260717/map_satellite.html)  
**Brief:** [SATELLITE_BRIEF.md](../../outputs/open_if/la_mierla_20260717/satellite_enrichment/SATELLITE_BRIEF.md)

| Sensor | n hotspots | FRP max | Notas |
|--------|------------|---------|-------|
| VIIRS N20 24h | 595 | 429 MW | base pack |
| VIIRS N21 24h | 816 | (ver report) | recuperado tras timeout |
| VIIRS SNPP 24h | 740 | 367 MW | confirma núcleo |
| MODIS 24h | 197 | **1572 MW** | píxeles 1 km, FRP alto |
| VIIRS N20 **7d** | 1323 | 429 MW | timeline 16→21 jul |

**Timeline N20 (conteos):** 16:5 → 17:133 → 18:274 → 19:316 → 20:397 → 21:198 (parcial día).

**Sentinel-2 STAC (tile 30TVL):** pre-fuego 14 escenas; durante 5 (p.ej. 16 jul cloud ~1.4–1.8%; 19 jul ~40%). Listas en `satellite_enrichment/sentinel2_stac_search.json`.

**Google Maps:** solo deep-links al centroide (~41.113, −3.062) — **no** scrape de tiles (ToS). Basemap local = Esri World Imagery.

### Viewers externos
- Google Maps sat: centro pack (ver `viewer_deep_links` en enrichment_report.json)
- NASA Worldview / FIRMS / EO Browser / Esri — mismos links en el mapa satélite

---

## Pack open generado (loop-engineering)

| Artefacto | Path |
|-----------|------|
| Manifest | `outputs/open_if/la_mierla_20260717/manifest.json` |
| Hotspots | `.../firms_hotspots.geojson` (595) |
| Hull proxy | `.../firms_footprint_proxy.geojson` (~39 980 ha hull ≠ quemado) |
| Scorecard | `.../scorecard_pista_b.json` |
| Map | `.../map.html` |
| Brief | `.../operator_brief_open_if.md` |
| Scrape | `.../scrape_latest.json` |
| Decide field_ops | `.../fire_decision_card_field_ops.json` → **HOLD** |
| Decide research | `.../fire_decision_card_research.json` → **HOLD** |
| Anchor stub | `data/infocam_anchors.json` → `pending_external` |

## Próximos pasos recomendados

1. **Cadence 12–24 h:** `python scripts/run_la_mierla_open_day.py` (timeline + CEMS + decide + week_package).  
2. **Humano:** enviar [SOLICITUD_LA_MIERLA_INFOCAM.md](SOLICITUD_LA_MIERLA_INFOCAM.md) a INFOCAM/CMA (LWIR/KMZ + Vp/ha EGIF).  
3. **STAC S2** post-nubes → `python scripts/run_la_mierla_open_day.py --try-dnbr` cuando `dnbr_queue.json` diga `ready`.  
4. **No** promover field_ops a GO con solo open/FIRMS (hard rule en day runner).  
5. **No** promover ancla a `confirmed` con solo ha de prensa (anchor_guard).

### Artefactos cadence (Sprint B+)

| Artefacto | Path |
|-----------|------|
| Timeline diaria | `outputs/open_if/la_mierla_20260717/timeline_daily.json` |
| Scrape history | `.../scrape_history.json` |
| CEMS WATCH | `.../cems_watch.json` |
| dNBR queue / status | `.../dnbr_queue.json`, `.../dnbr_status.json` |
| Week package | `.../week_package/manifest.json` |
| Forensic week-1 | `.../forensic_week1_brief.md` |
