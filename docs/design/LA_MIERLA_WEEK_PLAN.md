# Plan semanal — IF La Mierla (Guadalajara)

**event_id:** `guadalajara_la_mierla_20260717`  
**Ventana datos:** 2026-07-16 → 2026-07-21 (primera semana del incendio)  
**Dominio:** Castilla-La Mancha · Sierra Norte de Guadalajara  
**Centroide open (FIRMS multi):** ~41.113°N, 3.062°W  
**Track actual:** `open_firms_only` · Decision cards: **HOLD**  
**Última consolidación:** 2026-07-21  

> **Honestidad O1/O2:** nada de lo open se usa como perímetro oficial, ROS táctico ni ancla confirmed. ha ~29k = estimación INFOCAM/prensa, no EGIF.

---

## 1. Objetivo del plan

Convertir **toda la evidencia de la primera semana** en:

1. **Memoria operativa open** (timeline + capas + enlaces).  
2. **Backlog WFD priorizado** (qué generar ya / qué pedir / qué no hacer).  
3. **Plan de ejecución en 4 sprints** (D0–D7, D8–D14, post-fuego, cierre ancla).  

---

## 2. Snapshot de la semana (hechos consolidados)

### 2.1 Situación civil / INFOCAM (open)

| Campo | Valor | Fuente primaria | Confianza |
|-------|--------|-----------------|-----------|
| Detección | **2026-07-16 ~13:55** | COR/INFOCAM vía prensa | alta |
| Nivel | **2** (Nivel 3 = cambio dirección, no más medios) | @Plan_INFOCAM 21 jul | alta |
| ha estimada | **~26k (20 jul) → ~29k (21 jul)** | INFOCAM X + prensa | media-alta (no EGIF) |
| Perímetro press | **~120 km** (20 jul) | El País | media |
| Personas | **>1.200** afectadas | INFOCAM | alta |
| Evacuados | **34** municipios | INFOCAM 08:33Z 21 jul | alta |
| Confinados | **14** municipios | INFOCAM | alta |
| Medios 21 jul AM | **72** terrestres / **394** efectivos | INFOCAM | alta |
| Medios noche 20 | 74 terrestres / 424 efectivos; fuego técnico + maquinaria | INFOCAM | alta |
| PMA | Tamajón / Guadalajara | prensa + INFOCAM | alta |
| Flanco Soria | Freno; Barcones + residencia Retortillo evacuados | prensa 21 jul | media |
| CEMS | **EMSR896 = Orés (Aragón)**, no La Mierla | Copernicus news | alta (negativo) |

### 2.2 Satélite FIRMS — timeline VIIRS N20 7d (bbox Sierra Norte)

| Día | Hotspots N20 (conteo) | Lectura cualitativa |
|-----|----------------------:|---------------------|
| **16 jul** | **5** | Ignición / primeras detecciones satélite |
| **17 jul** | **133** | Escape / crecimiento explosivo |
| **18 jul** | **274** | Expansión fuerte |
| **19 jul** | **316** | Meseta alta |
| **20 jul** | **397** | Pico actividad térmica en ventana 7d |
| **21 jul** | **198** | Parcial (día en curso al scrape) |

**Total N20 7d:** **1.323** hotspots · hull ~**47.935 ha** (proxy, no quemado).

### 2.3 Multi-sensor (scrape 21 jul, 24h salvo 7d)

| Sensor | n | FRP max (MW) | Hull ~ha | Uso |
|--------|--:|-------------:|---------:|-----|
| VIIRS N20 24h | 595 | 429 | 39.980 | base pack |
| VIIRS N21 24h | 816 | 377 | 39.872 | confirma núcleo |
| VIIRS SNPP 24h | 740 | 367 | 39.927 | redundancia órbita |
| MODIS 24h | 197 | **1.572** | 36.546 | FRP 1 km (no comparar área con VIIRS) |
| Unión multi (solapes) | ~3.671 | — | ~49.600 | mapa satélite |

**Extent unión observado:** lat 40.93–41.24 · lon −3.25–−2.91.

### 2.4 Sentinel-2 STAC (tile 30TVL, Element84)

| Ventana | n escenas | Notas |
|---------|----------:|-------|
| Pre-fuego 01–15 jul | 14 | base dNBR (p.ej. 13 jul cloud ~0.2%) |
| Durante 14–21 jul | 5 | **16 jul** muy claro (~1.4–1.8%); **19 jul** ~40% nubes |
| Strict clear durante | 4 | útil pre-frente / ignición, no quemado final |

### 2.5 Estado producto WFD (hoy)

| Producto | Estado |
|----------|--------|
| Open pack FIRMS | **READY** |
| Mapa embebido + mapa satélite Esri | **READY** |
| Scorecard pista B open | **READY** (open-only) |
| Decide field_ops / research_open | **HOLD** |
| Ancla `infocam_anchors` | **pending_external** |
| LWIR / ROS incident | **BLOCKED** |
| O2 perímetro oficial / CEMS La Mierla | **BLOCKED / WATCH** |
| dNBR open post-fuego | **PENDING** (esperar S2/HLS claro) |
| ML fine-tune este IF | **NO-GO** (sin parches LWIR) |

---

## 3. Timeline día a día (semana 1) — narrativa + datos

```
16 JUL  Ignición ~13:55 · primeras evacuaciones · N20: 5 hotspots · S2 claro pre/ignición
17 JUL  Crecimiento brutal · N20: 133 · multi-evacuaciones · UME/medios externos
18 JUL  Expansión · N20: 274 · amenaza núcleos / Parque Natural (prensa)
19 JUL  Meseta · N20: 316 · S2 parcialmente nublado (~40%) · más confinamientos
20 JUL  Pico térmico N20: 397 · prensa ~26k ha · ~120 km perímetro · 33 mun · Nivel 2
21 JUL  INFOCAM ~29k ha · 34+14 · 72/394 · freno Soria · N20 24h parcial 198 · HOLD decide
```

### Diagrama de crecimiento térmico (N20 7d)

```
hotspots
  400 |                    ████ 397
  300 |              ████  ██
  200 |        ████  ██    ██    ░░ 198 (parcial)
  100 |   ████ ██    ██    ██    ░░
    0 | █
        16   17   18   19   20   21
```

---

## 4. Inventario de artefactos (clicables en repo)

### Pack open
| Artefacto | Ruta |
|-----------|------|
| Mapa FIRMS embebido | [map.html](../../outputs/open_if/la_mierla_20260717/map.html) |
| Mapa satélite multi-sensor | [map_satellite.html](../../outputs/open_if/la_mierla_20260717/map_satellite.html) |
| Brief operador | [operator_brief_open_if.md](../../outputs/open_if/la_mierla_20260717/operator_brief_open_if.md) |
| Scorecard | [scorecard_pista_b.json](../../outputs/open_if/la_mierla_20260717/scorecard_pista_b.json) |
| Scrape | [scrape_latest.json](../../outputs/open_if/la_mierla_20260717/scrape_latest.json) |
| Manifest | [manifest.json](../../outputs/open_if/la_mierla_20260717/manifest.json) |
| Decide field_ops | [fire_decision_card_field_ops.json](../../outputs/open_if/la_mierla_20260717/fire_decision_card_field_ops.json) |
| Decide research | [fire_decision_card_research.json](../../outputs/open_if/la_mierla_20260717/fire_decision_card_research.json) |
| Hotspots 24h | [firms_hotspots.geojson](../../outputs/open_if/la_mierla_20260717/firms_hotspots.geojson) |
| Hotspots 7d | [firms_hotspots_7d.geojson](../../outputs/open_if/la_mierla_20260717/firms_hotspots_7d.geojson) |
| Enrichment report | [enrichment_report.json](../../outputs/open_if/la_mierla_20260717/satellite_enrichment/enrichment_report.json) |
| STAC S2 | [sentinel2_stac_search.json](../../outputs/open_if/la_mierla_20260717/satellite_enrichment/sentinel2_stac_search.json) |
| Brief satélite | [SATELLITE_BRIEF.md](../../outputs/open_if/la_mierla_20260717/satellite_enrichment/SATELLITE_BRIEF.md) |

### Docs / código
| Artefacto | Ruta |
|-----------|------|
| Intake | [GUADALAJARA_LA_MIERLA_20260717.md](../open_if_intake/GUADALAJARA_LA_MIERLA_20260717.md) |
| Design open loop | [LA_MIERLA_OPEN_LOOP.md](LA_MIERLA_OPEN_LOOP.md) |
| **Este plan** | [LA_MIERLA_WEEK_PLAN.md](LA_MIERLA_WEEK_PLAN.md) |
| Anclas | [infocam_anchors.json](../../data/infocam_anchors.json) |
| Build pack | [build_la_mierla_open_pack.py](../../scripts/build_la_mierla_open_pack.py) |
| Enrich satélite | [enrich_la_mierla_satellite.py](../../scripts/enrich_la_mierla_satellite.py) |

### Viewers externos (centroide)
- [Google Maps satélite](https://www.google.com/maps/@41.11320,-3.06231,11z/data=!3m1!1e3)
- [Google Earth](https://earth.google.com/web/search/41.11320,-3.06231/@41.11320,-3.06231,2500a,12000d,35y,0h,0t,0r)
- [NASA Worldview](https://worldview.earthdata.nasa.gov/?v=-3.61,40.76,-2.51,41.46&l=VIIRS_NOAA20_Thermal_Anomalies_375m_Day,VIIRS_NOAA20_Thermal_Anomalies_375m_Night,MODIS_Aqua_Thermal_Anomalies_All,VIIRS_SNPP_CorrectedReflectance_TrueColor&t=2026-07-20)
- [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/map/#d:24hrs;@-3.0623,41.1132,11z)
- [EO Browser S2](https://apps.sentinel-hub.com/eo-browser/?lat=41.11320&lng=-3.06231&zoom=11&datasetId=S2L2A&fromTime=2026-07-14T00:00:00.000Z&toTime=2026-07-21T23:59:59.999Z)

---

## 5. Gaps y bloqueos (honestos)

| Gap | Impacto WFD | Cómo desbloquear |
|-----|-------------|------------------|
| Sin LWIR / KMZ INFOCAM | No ROS, no field GO | Solicitud formal CMA/INFOCAM |
| Sin ha/Vp EGIF confirmed | Ancla O1 no promociona | Parte oficial / Observatorio |
| Sin CEMS EMSR La Mierla | O2 open débil | Vigilar mapping.emergency.copernicus.eu |
| S2 durante nublado post-16 | dNBR final incompleto | Esperar post-fuego clear o HLS |
| Google tiles no scrapables | Sin orto Google en pack | Esri + Worldview + deep-links (OK) |
| Sin parches training | No ML retrain | Solo si llega LWIR alineado |

---

## 6. Plan de ejecución (4 sprints)

### Sprint A — Ahora (D0, ya hecho / mantener)

**Meta:** pack open vivo y regenerable.

| # | Tarea | Estado | Comando / artefacto |
|---|-------|--------|---------------------|
| A1 | Pack FIRMS + scorecard + brief + maps | **DONE** | `python scripts/build_la_mierla_open_pack.py` |
| A2 | Multi-sensor + STAC + viewers | **DONE** | `python scripts/enrich_la_mierla_satellite.py` |
| A3 | Decide HOLD field_ops + research | **DONE** | `python -m wildfire_front.cli decide ...` |
| A4 | Anchor stub pending_external | **DONE** | `data/infocam_anchors.json` |
| A5 | Re-fetch FIRMS cada 12–24 h mientras activo | **CADENCE** | `run_la_mierla_open_day.py` o scripts A1+A2 |

**Criterio de salida A:** maps abren con fuego; decide no inventa GO; docs enlazan pack.

### Sprint B — Semana 2 del IF (D8–D14 o hasta estabilización)

**Meta:** densificar timeline y no perder el hilo operativo open.

| # | Tarea | Estado | Prioridad | Notas |
|---|-------|--------|-----------|-------|
| B1 | Cadence FIRMS 12–24 h + append timeline JSON | **IMPLEMENTED** | P0 | `timeline_daily.json` via `run_la_mierla_open_day.py` |
| B2 | Scrape INFOCAM X + 1 pieza prensa/día | **PARTIAL** (slot merge) | P0 | `scrape_history.json` merge; **human** updates press/X content |
| B3 | CEMS WATCH diario | **IMPLEMENTED** | P1 | `cems_watch.json` (EMSR896 ≠ La Mierla); optional news fetch |
| B4 | S2 STAC re-search cada 48 h (cloud &lt; 30%) | **IMPLEMENTED** (queue) | P1 | `dnbr_queue.json` ready vs blocked_clouds; enrich refreshes STAC |
| B5 | Export “week package” | **IMPLEMENTED** | P1 | `week_package/manifest.json` + copy key artifacts |
| B6 | **No** field_ops GO | **IMPLEMENTED** (hard rule) | hard | day runner coerces/asserts HOLD on open-only |

**Criterio de salida B:** serie temporal ≥ 10–14 días o hasta “controlado/estabilizado” en partes oficiales.  
**Código listo; cobertura multi-día sigue dependiendo de cadence operativa / red.**

### Sprint C — Post-frente (cuando nubes lo permitan)

**Meta:** open pack de severidad / perímetro proxy de calidad.

| # | Tarea | Estado | Prioridad | Dependencia |
|---|-------|--------|-----------|-------------|
| C1 | dNBR open con S2 pre vs post clear | **WIRED / BLOCKED nubes** | P0 | `--try-dnbr` → `build_open_if_dnbr.py`; honest `dnbr_status.json` |
| C2 | Comparar hull FIRMS vs dNBR footprint | **IMPLEMENTED** (deferred sin dNBR GO) | P0 | `hull_vs_dnbr_comparison.json` + not_official labels |
| C3 | Scorecard pista B con capa dNBR | **IMPLEMENTED** (campo status) | P1 | `dnbr_status` / `dnbr_queue_status` en scorecard |
| C4 | Si CEMS se activa: merge EMSR + FIRMS | **WATCH / EXTERNAL** | P0 | activation code La Mierla (no EMSR896) |
| C5 | Brief post-fuego (no táctico) | **PARTIAL** | P1 | `forensic_week1_brief.md` open; post-fuego cuando dNBR GO |

**Criterio de salida C:** `dnbr_status` ≠ blocked por nubes; mapa con pre/post.  
**Bloqueo actual: sin escena S2 post clear (expected).**

### Sprint D — Ancla y cierre científico (externo)

**Meta:** promoción O1 solo con datos reales.

| # | Tarea | Estado | Prioridad | Owner |
|---|-------|--------|-----------|-------|
| D1 | Solicitud INFOCAM/CMA: LWIR+KMZ, Vp media, ha EGIF | **DRAFT READY** | P0 | humano envía: `docs/open_if_intake/SOLICITUD_LA_MIERLA_INFOCAM.md` |
| D2 | Si llega material → `real_if` intake protocol | **EXTERNAL BLOCKED** | P0 | pipeline existente |
| D3 | Confirmar ancla o dejar `pending_external` | **GUARD + pending** | P0 | `wildfire_front/open_if/anchor_guard.py` refuse press-only |
| D4 | Decidir si este IF entra holdout CLM futuro | **EXTERNAL** | P2 | solo con LWIR/parches |
| D5 | Acta forense open (semana 1) opcional | **IMPLEMENTED** | P2 | pack `forensic_week1_brief.md` |

**Criterio de salida D:** ancla `confirmed` **o** documentado “no disponible” sin contaminación de GO.

---

## 7. Plan de datos de la semana → productos

```
                    ┌─────────────────────┐
  INFOCAM X/prensa  │ scrape_latest.json  │──► brief / scorecard ha est.
                    └─────────────────────┘
  FIRMS N20 7d      │ timeline counts     │──► curva crecimiento (esta semana)
  multi-sensor 24h  │ union geojson       │──► map_satellite.html
  hull proxy        │ footprint geojson   │──► AOI / STAC bbox
  STAC S2           │ pre + during items  │──► Sprint C dNBR
  decide open       │ HOLD cards          │──► no despacho
         │
         ▼
  [ BLOQUEADO hasta externo ]  LWIR · EGIF · CEMS La Mierla · Vp
```

### Productos que SÍ se publican esta semana (open)

1. Timeline térmica diaria (N20).  
2. Capas multi-sensor + mapa satélite.  
3. Scorecard open + decision HOLD.  
4. Deep-links Maps/Worldview/EO Browser.  
5. Este plan + intake.

### Productos que NO se publican

1. ROS m/min “medido”.  
2. Perímetro oficial.  
3. GO field_ops.  
4. Ancla confirmed con solo prensa.  
5. Tiles Google descargados.

---

## 8. Cadence operativa recomendada (mientras activo)

| Hora / trigger | Acción |
|----------------|--------|
| Cada 12–24 h | `build_la_mierla_open_pack.py` + `enrich_la_mierla_satellite.py` |
| Tras parte INFOCAM X | actualizar scrape + scorecard ha/medios |
| Tras escena S2 cloud &lt; 30% | STAC → cola dNBR |
| Si CEMS activa | intake EMSR + pack open_if |
| Si llega LWIR | **stop open-only** → real_if protocol |
| Diario | re-decide field_ops (esperado HOLD sin ops) |

---

## 9. Métricas de éxito del plan (no confiar con GO)

| Métrica | Target semana 1 | Actual (21 jul) |
|---------|-----------------|-----------------|
| Días con FIRMS en pack | ≥ 6 | **6** (16–21) |
| Sensores activos | ≥ 3 | **4** (N20/N21/SNPP/MODIS) |
| Decide sin silent GO | 100% | **HOLD** ✓ |
| Ancla sin inventar | pending o confirmed real | **pending** ✓ |
| Mapa local con fuego visible | sí | **sí** (embebido) |
| STAC pre-fuego catalogado | ≥ 1 escena clara | **sí** (13–14, 16) |
| Solicitud datos formal | enviada | **pendiente humano** |

---

## 10. PR Plan (implementación repo)

Orden sugerido si se industrializa el flujo “IF open week”:

| PR | Título | Scope | Dependencias |
|----|--------|-------|--------------|
| PR1 | `feat(open-if): La Mierla pack builder + maps` | `build_la_mierla_open_pack.py`, docs design | — |
| PR2 | `feat(open-if): multi-sensor FIRMS + STAC enrich` | `enrich_la_mierla_satellite.py` | PR1 |
| PR3 | `docs: week plan + intake La Mierla` | este doc + intake | PR1–2 |
| PR4 | `feat(open-if): daily timeline append job` | **DONE** `run_la_mierla_open_day.py` + `timeline_daily.json` | PR2 |
| PR5 | `feat(open-if): dNBR when S2 clear` | **WIRED** `--try-dnbr` + queue/status honest | PR2 + S2 post (external) |
| PR6 | `chore: anchor promote only with EGIF/LWIR` | **DONE** `anchor_guard.py` + tests | PR3 |

**No-PR:** no mezclar weights; no reclamar five-nines en cards open.

---

## 11. Riesgos

| Riesgo | Mitigación |
|--------|------------|
| Confundir hull ~40–50k ha con quemado 29k | Labels en map/brief; scorecard notes |
| Confundir Orés/EMSR896 con La Mierla | CEMS WATCH explícito en scrape |
| Escalada mediática → presión a GO | Policy field_ops + HOLD + disclaimers |
| Timeout FIRMS N21 | retry ya en pipeline; no bloquear pack |
| Nubes en S2 post | HLS / esperar; no forzar dNBR basura |

---

## 12. Decisiones abiertas (para el humano)

1. ¿Commit + push de scripts/docs/anchors al `main`?  
2. ¿Enviar ya solicitud formal INFOCAM/CMA (plantilla en `docs/SOLICITUD_*` / entrega_cma)?  
3. ¿Priorizar dNBR automático en cuanto haya post-clear, o esperar estabilización?  
4. ¿Incluir La Mierla en portal/commander como “open monitoring IF”?  

---

## 13. Resumen ejecutivo (1 párrafo)

En la **primera semana** (16–21 jul 2026) el IF La Mierla pasó de ignición satélite mínima (5 hotspots N20) a pico térmico el **20 jul (397)** con parte INFOCAM de **~29.000 ha estimadas**, **34+14** municipios y **Nivel 2**. WFD tiene pack open multi-sensor (**~3.7k** puntos unión, maps embebidos), STAC S2 pre/durante catalogado, y decision cards en **HOLD**. El plan de sprints es: **mantener cadence open (B) → dNBR post-nubes (C) → ancla solo con LWIR/EGIF (D)**, sin inventar ROS ni perímetro oficial.

---

## 14. Comandos rápidos

```bash
# Cadence diaria (pack + enrich + timeline + CEMS WATCH + decide HOLD + week_package)
set PYTHONPATH=.
python scripts/run_la_mierla_open_day.py

# Offline (usa artefactos ya en pack; sin re-fetch red)
python scripts/run_la_mierla_open_day.py --skip-network --skip-decide

# Intentar dNBR (search-only STAC; sin fake GO si no hay post clear)
python scripts/run_la_mierla_open_day.py --skip-build --skip-enrich --try-dnbr

# Regenerar pack + scrape embebido (manual)
python scripts/build_la_mierla_open_pack.py

# Multi-sensor + STAC + map_satellite (manual)
python scripts/enrich_la_mierla_satellite.py

# Decision cards
set PYTHONPATH=.
python -m wildfire_front.cli decide --event-id guadalajara_la_mierla_20260717 --open-pack outputs/open_if/la_mierla_20260717 --policy field_ops --output outputs/open_if/la_mierla_20260717/fire_decision_card_field_ops.json
python -m wildfire_front.cli decide --event-id guadalajara_la_mierla_20260717 --open-pack outputs/open_if/la_mierla_20260717 --policy research_open --output outputs/open_if/la_mierla_20260717/fire_decision_card_research.json
```

### Artefactos cadence (Sprint B+)

| Artefacto | Ruta |
|-----------|------|
| Timeline diaria | [timeline_daily.json](../../outputs/open_if/la_mierla_20260717/timeline_daily.json) |
| Scrape history | [scrape_history.json](../../outputs/open_if/la_mierla_20260717/scrape_history.json) |
| CEMS WATCH | [cems_watch.json](../../outputs/open_if/la_mierla_20260717/cems_watch.json) |
| dNBR queue | [dnbr_queue.json](../../outputs/open_if/la_mierla_20260717/dnbr_queue.json) |
| dNBR status | [dnbr_status.json](../../outputs/open_if/la_mierla_20260717/dnbr_status.json) |
| Week package | [week_package/manifest.json](../../outputs/open_if/la_mierla_20260717/week_package/manifest.json) |
| Solicitud INFOCAM (draft) | [SOLICITUD_LA_MIERLA_INFOCAM.md](../open_if_intake/SOLICITUD_LA_MIERLA_INFOCAM.md) |
| Day runner | [run_la_mierla_open_day.py](../../scripts/run_la_mierla_open_day.py) |
