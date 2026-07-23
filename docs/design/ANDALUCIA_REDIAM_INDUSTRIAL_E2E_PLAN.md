# Plan industrial E2E — Andalucía REDIAM (estilo Tobarra, Pista B+O2)

**Status:** IMPLEMENTED — `GO_AND_INDUSTRIAL_E2E` (2026-07-22)  
**Fecha:** 2026-07-22  
**Trigger:** Respuesta REDIAM con perímetros 2008–2025 + áreas recorridas 1975–hoy  
**Analogía Tobarra:** mismo rigor de **gates, scorecard, provenance, no overclaim** — distinto stack de datos  
**Acta:** `docs/AND_INDUSTRIAL_E2E_VERIFICATION.md` · gold pack `outputs/open_if/and_2024040053_20240606`  

| | **Tobarra (Pista A · OPS gold)** | **Andalucía REDIAM (Pista B+ · OPEN industrial)** |
|--|----------------------------------|-----------------------------------------------------|
| Termografía LWIR multi-frame | Sí (Heligrafics) | **No** (salvo ASEMA/ops futuro) |
| Ancla Vp/ha confirmed | Sí (~7 m/min, ~39 ha) | **No en capa** → pedir a **Agencia de Emergencias** |
| Perímetro “oficial” | KMZ/ops (no catastro O2) | **Sí: REDIAM / Junta** (IF >10 ha, 2008–2025) |
| Multi-temporal delineación | Frames LWIR | FIRMS + dNBR S2 + (opcional) ARF histórico |
| Producto | ROS multi-estimador + card | O2 Hausdorff + open pack + scorecard industrial |
| Veredicto posible | `GO_OPS_GOLD` | `GO_OPEN_AND_O2` / `PARTIAL` / `NO_GO` |

> **Honestidad:** esto **no sustituye** Tobarra como gold OPS.  
> **Sí** demuestra, a escala industrial, que el stack **open + perímetro institucional** funciona de punta a punta en otra CCAA.

---

## 0. Objetivo industrial (definición de “funciona”)

Un run se declara **`GO_AND_INDUSTRIAL_E2E`** solo si pasan **todas** las capas del contrato:

| # | Capa | Criterio PASS |
|---|------|----------------|
| C1 | **Intake** | Inventario + hashes + CRS + schema; atribución REDIAM |
| C2 | **Selección IF** | ≥3 IF candidatas documentadas; ≥1 **gold AND** elegida |
| C3 | **O2 oficial** | Perímetro REDIAM del IF en pack (GeoJSON 4326 + CRS original) |
| C4 | **Open sat** | FIRMS (VIIRS/MODIS) ventana evento ±2 d; hull **etiquetado proxy** |
| C5 | **dNBR / STAC** | Pre/post S2 o `dnbr_status=SKIP` documentado (nubes/out of season) |
| C6 | **Métricas O2** | Hausdorff / IoU / área vs REDIAM (FIRMS hull vs perímetro **no** se vende como quemado) |
| C7 | **Scorecard** | `scorecard_and_industrial.json` con GO/PARTIAL/NO_GO por gate |
| C8 | **Decide / brief** | Decision card open-only (HOLD si no hay ops); operator brief 1 p |
| C9 | **Tests** | pytest smoke intake + geometry + pack build |
| C10 | **Repro** | Un comando Makefile/script regenera el pack desde cero |

**Fuera de alcance de este E2E (no bloquear el GO open):**

- LWIR Heligrafics en Andalucía  
- ROS táctico para sala INFOCA  
- Sustituir Tobarra en `verify_gold_if_e2e.py` como ops champion (solo **añadir** champion open AND)

---

## 1. Fuentes y provenance (congelar al día 0)

### 1.1 Datos espaciales (ya concedidos)

| Producto | Acceso | Uso en pipeline |
|----------|--------|-----------------|
| **Perímetros IF AND 2008–2025** | [Descargas Historico_Incendios_COR](https://portalrediam.cica.es/descargas/index.php/s/mxHMWXyHfrCxyNK?dir=/06_RIESGOS_NATURALES_TECNOLOG/03_ACCIDENTES_DESASTRES/01_INCENDIOS/00_INCENDIOS/Historico_Incendios_COR) · **WFS** `REDIAM_perimetros_incendios_forestales` capas `ms:perim_incendios_YYYY` | **O2 vector** por IF |
| **Áreas recorridas por el fuego 1975–hoy** | [Descargas AreasRecorrFuego](https://portalrediam.cica.es/descargas/index.php/s/mxHMWXyHfrCxyNK?dir=/06_RIESGOS_NATURALES_TECNOLOG%2F03_ACCIDENTES_DESASTRES%2F01_INCENDIOS%2F00_INCENDIOS%2FAreasRecorrFuego) · WMS ARF | Contexto histórico / severidad satélite multi-década |
| FIRMS NASA | API / CSV | Hotspots durante evento |
| Sentinel-2 STAC | Element84 / CDSE | dNBR pre–post |

**Atribución obligatoria en todo artefacto:**  
*Fuente: REDIAM — Junta de Andalucía. Uso libre con mención de autores y propietarios.*

**WFS (preferido para automatizar):**  
`https://www.juntadeandalucia.es/medioambiente/mapwms/REDIAM_perimetros_incendios_forestales`  
CRS nativo típico: **EPSG:3042** · IF **>10 ha** · campos: `CODIGO`, `FECHA_INC`, `Municipio`, `Provincia`, `SUP_*`, geometría.

Detalle técnico ya verificado: `docs/open_if_intake/REDIAM_ANDALUCIA_PERIMETROS_20260722.md`.

### 1.2 Ops (puente ASEMA — paralelo, no bloquea open E2E)

| Canal | Pedir | Gate que desbloquea |
|-------|--------|---------------------|
| `gerencia.asema@juntadeandalucia.es` | Reenvío cartografía/partes | Contacto |
| ASEMA / DG Gestión IIFF | **1–2 IF** con Vp o ha de parte + fecha control | **O1 AND** (ancla) |
| No 112 | — | — |

Si ASEMA da Vp/ha → el IF pasa a **`AND_OPS_PARTIAL`** (sigue sin LWIR salvo material nuevo).

---

## 2. Layout de datos (industrial)

```
data/open_if/rediam_andalucia/          # raw (gitignore si pesado)
  downloads/                            # zips Nextcloud (humano)
  wfs_cache/YYYY/perim_incendios_YYYY.geojson
  inventory/
    file_inventory.csv
    event_catalog.parquet|csv           # 1 fila por CODIGO/IF
    selection_gold.json                 # IF elegidos + razones

outputs/open_if/and_<codigo>_<fecha>/   # pack por IF (estilo emsr*)
  manifest.json
  vectors/perimeter_rediam.geojson
  vectors/firms_hotspots.geojson
  timeline_*.geojson                    # si multi-fuente temporal
  map.html
  map_satellite.html                    # opcional
  metrics_o2.json                       # Hausdorff, IoU, areas
  scorecard_and_industrial.json
  operator_brief_open_if.md
  dnbr_status.json | dnbr_summary.json
  provenance.json

outputs/open_if/and_index.html          # índice multi-IF AND
docs/AND_INDUSTRIAL_E2E_VERIFICATION.md # acta final (como GOLD_IF)
docs/AND_INDUSTRIAL_E2E_VERIFICATION.json
```

**Regla:** no commitear rasters/zips grandes; sí manifests, geojson ligeros de muestra, scorecards, tests.

---

## 3. Selección de incendios (como elegimos Tobarra)

### 3.1 Filtros duros (catálogo)

1. `FECHA_INC` parseable (YYYYMMDD).  
2. Geometría válida, área > 10 ha (capa ya filtrada).  
3. Bbox dentro de Andalucía (sanity CRS).  
4. Año ∈ {2022, 2023, 2024, 2025} preferente (FIRMS + S2 densos).

### 3.2 Score de candidatura (0–100)

| Criterio | Puntos |
|----------|--------|
| Superficie (SUP total o geom área) ≥ 100 / 500 / 1000 ha | +10 / +20 / +30 |
| Año ≥ 2023 | +15 |
| FIRMS ≥ 20 hotspots en ±2 d del evento (probe) | +25 |
| S2 pre y post con nubes < 30% | +20 |
| Municipio/provincia claros en atributos | +5 |
| Coincidencia posible CEMS EMSR (si hay) | +5 bonus |

### 3.3 Cupo industrial

| Tier | n | Uso |
|------|---|-----|
| **Gold AND** | **1** | E2E completo + acta + demo |
| **Silver** | **2** | Pack + scorecard (sin dNBR si falla) |
| **Bronze catalog** | resto | Solo en `event_catalog` (no pack completo) |

**Salida:** `data/open_if/rediam_andalucia/inventory/selection_gold.json`

---

## 4. Pipeline end-to-end (fases = Tobarra industrial)

```
[A] FETCH → [B] INVENTORY → [C] SELECT → [D] PACK → [E] METRICS → [F] SCORECARD
    → [G] DECIDE/BRIEF → [H] VERIFY SCRIPT → [I] CI TESTS → [J] ASEMA (paralelo)
```

### Fase A — Fetch (D0)

| ID | Tarea | Done when |
|----|--------|-----------|
| A1 | Script `scripts/fetch_rediam_perimeters.py` | WFS por año → `wfs_cache/YYYY/` |
| A2 | Descarga manual zips Nextcloud (si hace falta full SHP) | En `downloads/` + README hashes |
| A3 | Probe WMS/ARF opcional | Doc en provenance |
| A4 | Atribución en `PROVENANCE.md` sección AND | Link + fecha |

**Comando objetivo:**

```powershell
$env:PYTHONPATH = "."
python scripts/fetch_rediam_perimeters.py --years 2022,2023,2024,2025 --out data/open_if/rediam_andalucia/wfs_cache
```

### Fase B — Inventory (D0–D1)

| ID | Tarea | Done when |
|----|--------|-----------|
| B1 | `scripts/inventory_rediam_and.py` | `event_catalog.csv` con n, ha, bbox, fecha |
| B2 | Stats por provincia/año | Tabla en MD |
| B3 | QA geometrías (vacías, multipolygon, área 0) | Flag `qa_geometry` |

### Fase C — Select gold (D1)

| ID | Tarea | Done when |
|----|--------|-----------|
| C1 | Scoring FIRMS dry-run por top 20 ha | CSV scores |
| C2 | Elegir gold + 2 silver | `selection_gold.json` |
| C3 | Registrar hipótesis (por qué este IF) | 5 líneas en plan update |

### Fase D — Pack open_if por IF (D1–D3) · **núcleo tipo Tobarra pack**

Reutilizar patrones de `build_open_if_pack.py` / La Mierla open loop:

| ID | Producto | Script (nuevo o extendido) |
|----|----------|----------------------------|
| D1 | Perímetro REDIAM → 4326 + equal-area ha | `build_and_if_pack.py --codigo …` |
| D2 | FIRMS bbox±buffer, multi-sensor si aplica | mismo |
| D3 | Timeline open (si hay multi-día FIRMS) | hull diario **proxy** |
| D4 | dNBR STAC pre/post | `build_open_if_dnbr.py` adaptado a pack AND |
| D5 | `map.html` Leaflet con capas: REDIAM / FIRMS / dNBR | embed o fetch |
| D6 | `manifest.json` + `operator_brief_open_if.md` | plantilla Pista B |

**Prohibido en pack:**

- Reportar hull FIRMS como “ha quemadas oficiales”.  
- Inventar Vp.  
- Decision `GO` field_ops sin ancla ASEMA.

### Fase E — Métricas O2 (D2–D3) · **equivalente audit Tobarra**

| Métrica | Definición | Gate |
|---------|------------|------|
| `area_rediam_ha` | área equal-area del polígono oficial | sanity |
| `area_firms_hull_ha` | convex hull hotspots | **proxy only** |
| `ratio_hull_vs_rediam` | hull/official | documentar; típico >1 |
| `iou_firms_vs_rediam` | raster o polygonize buffer hotspots vs perímetro | info |
| `hausdorff_m` | contorno buffer FIRMS vs REDIAM (si hay ≥N pts) | O2 method GO |
| `dnbr_burn_mask_iou` | si dNBR GO | severidad proxy |

Salida: `metrics_o2.json` por IF.

### Fase F — Scorecard industrial (D3)

`scorecard_and_industrial.json` (espejo `scorecard_pista_b` + gates AND):

| Gate | PASS si |
|------|---------|
| `O2_REDIAM` | perímetro en pack + atribución |
| `O2_METHOD_HAUSDORFF` | métrica calculada o SKIP justificado (pocos pts) |
| `OPEN_FIRMS` | ≥1 hotspot o SKIP documentado |
| `OPEN_DNBR` | GO o SKIP nubes |
| `NO_FALSE_DISPATCH` | decide HOLD o open_demo only |
| `REPRO` | script one-shot OK |
| `PROVENANCE` | REDIAM citado |

Veredicto pack:

- **GO_OPEN_AND_O2** — todos PASS o SKIP justificado  
- **PARTIAL** — falta FIRMS o dNBR pero O2 OK  
- **NO_GO** — sin perímetro / crash / sin atribución  

### Fase G — Decide + brief (D3–D4)

| ID | Tarea |
|----|--------|
| G1 | Decision card: sources = open_rediam + firms + dnbr; **sin** ops_thermal |
| G2 | `confidence` baja/media; system_reliability_pass solo si scorecard GO |
| G3 | Brief 1 página ES/EN para demo TFG / ASEMA |
| G4 | Actualizar `docs/COMPARE_CLM_VS_OPEN.md` con fila AND gold |

### Fase H — Verificación E2E (D4) · **como `verify_gold_if_e2e.py`**

Nuevo: `scripts/verify_and_industrial_e2e.py`

```
python scripts/verify_and_industrial_e2e.py
# escribe docs/AND_INDUSTRIAL_E2E_VERIFICATION.{json,md}
```

Capas a chequear (AND open champion + Tobarra ops sigue en gold dual):

| Capa AND | Pass |
|----------|------|
| rediam_perimeter_present | |
| inventory_catalog | |
| gold_selection | |
| pack_manifest | |
| metrics_o2 | |
| scorecard_go_or_partial | |
| map_html | |
| pytest_and_smoke | |

Opcional: integrar **open champion AND** en `verify_gold_if_e2e.py` como tercera pata:

- OPS: Tobarra  
- OPEN CEMS: EMSR578  
- **OPEN O2 oficial CCAA: AND gold**  

### Fase I — Tests CI (D4)

| Test | Contenido |
|------|-----------|
| `tests/test_rediam_and_intake.py` | schema mínimo, CRS transform, área > 0 |
| `tests/test_and_if_pack.py` | pack fixtures sintéticos (no red en CI) |
| Extender `test_open_if_pack.py` | gates no inventan ha oficiales |

Red en CI: **mock** WFS o fixture GeoJSON pequeño (3 polígonos).  
Live WFS: flag `--live` solo local.

### Fase J — ASEMA en paralelo (D1–D7, no bloquea)

| Día | Acción |
|-----|--------|
| D1 | Email gracias REDIAM (plantilla ya en intake MD) |
| D1 | Email ASEMA: pedir ancla 1–2 IF = gold/silver del catálogo |
| D5+ | Si llega Vp/ha → `data/infocam_anchors.json` estilo `and_<codigo>` status `confirmed` o `pending` |
| D7 | Si no llega → O1_AND = BLOCKED documentado (como O1 multi-IF CLM) |

---

## 5. Criterios de aceptación “tipo Tobarra industrial”

### 5.1 Debe verse igual de “profesional” que Tobarra

| Artefacto Tobarra | Equivalente AND |
|-------------------|-----------------|
| Pack observatorio / incident | `outputs/open_if/and_*` |
| Ingest manifest | `manifest.json` + inventory |
| Grade A metrics | `metrics_o2.json` + scorecard |
| Demo mapa | `map.html` clickable |
| Acta E2E | `docs/AND_INDUSTRIAL_E2E_VERIFICATION.md` |
| Ancla ops | ASEMA o BLOCKED honesto |

### 5.2 Checklist go/no-go final

- [ ] Catálogo ≥ 1 año WFS completo o multi-año gold window  
- [ ] 1 gold pack regenerable en **< 15 min** en máquina dev  
- [ ] Scorecard sin campos inventados  
- [ ] pytest verde  
- [ ] Comparativa CLM vs OPEN actualizada  
- [ ] Atribución REDIAM en brief y maps  
- [ ] Sin mención despacho táctico  

---

## 6. Plan de sprints (calendario realista)

### Sprint 0 — Día 0 (2–4 h)

1. Gracias REDIAM (email).  
2. `fetch` WFS 2024–2025 + sample inventory.  
3. Elegir **top 5** por ha y anotar.

### Sprint 1 — Días 1–2 (ingeniería)

1. `fetch_rediam_perimeters.py` + `inventory_rediam_and.py`.  
2. `build_and_if_pack.py` MVP (perímetro + map + manifest).  
3. Tests schema con fixture.

### Sprint 2 — Días 2–4 (industrial)

1. FIRMS + métricas O2 + scorecard.  
2. dNBR en gold IF.  
3. `verify_and_industrial_e2e.py`.  
4. 2 silver packs automáticos.

### Sprint 3 — Días 4–7 (cierre demo)

1. Índice multi-IF + portal fila AND.  
2. Brief ES para ASEMA.  
3. (Opcional) ARF capa histórica en mapa.  
4. Acta `GO_AND_INDUSTRIAL_E2E` o `PARTIAL` con razones.

---

## 7. Riesgos y mitigaciones

| Riesgo | Mitigación |
|--------|------------|
| Nextcloud 401 automatizado | WFS primero; zip manual |
| Perímetro final sin multi-día | FIRMS diario = proxy timeline; no fingir CEMS |
| CRS 3042 errores área | equal-area (3035/9377) para ha |
| IF sin FIRMS (nubes, pequeño, nocturno) | Silver con O2 only; gold elige el que tenga FIRMS |
| Overclaim “oficial ROS” | Scorecard prohíbe Vp sin ASEMA |
| CI sin red | fixtures |

---

## 8. Entregables finales (definición de done del plan)

| # | Entregable | Path |
|---|-------------|------|
| 1 | Este plan | `docs/design/ANDALUCIA_REDIAM_INDUSTRIAL_E2E_PLAN.md` |
| 2 | Scripts fetch/inventory/pack/verify | `scripts/*rediam*` / `*and_if*` |
| 3 | Catálogo eventos | `data/open_if/rediam_andalucia/inventory/` |
| 4 | Pack gold + 2 silver | `outputs/open_if/and_*` |
| 5 | Acta E2E | `docs/AND_INDUSTRIAL_E2E_VERIFICATION.{md,json}` |
| 6 | Tests | `tests/test_rediam_and_*.py` |
| 7 | Outreach ASEMA | log en `CONTACTOS_OUTREACH.csv` |

---

## 9. Relación con gold stack actual

```
                    ┌─────────────────────────┐
                    │  Decision / Demo dual   │
                    └───────────┬─────────────┘
           ┌────────────────────┼────────────────────┐
           ▼                    ▼                    ▼
    OPS GOLD              OPEN CEMS             OPEN O2 CCAA
    Tobarra               EMSR578               AND REDIAM gold
    LWIR+Vp               multi-day             perímetro Junta
    Pista A               Pista B               Pista B+ (nuevo)
```

**Mensaje comercial/TFG honesto:**  
“Validamos frente térmico en CLM (Tobarra) y **perímetros oficiales multi-año en Andalucía (REDIAM)** con el mismo stack de gates y abstención.”

---

## 10. Primer comando cuando digas “implementa”

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "."
# 1) fetch + inventory
python scripts/fetch_rediam_perimeters.py --years 2024,2025 --out data/open_if/rediam_andalucia/wfs_cache
python scripts/inventory_rediam_and.py --cache data/open_if/rediam_andalucia/wfs_cache --out data/open_if/rediam_andalucia/inventory
# 2) pack gold (código tras selection)
python scripts/build_and_if_pack.py --selection data/open_if/rediam_andalucia/inventory/selection_gold.json
# 3) verify
python scripts/verify_and_industrial_e2e.py
```

*(Scripts se crean en la fase de implementación de este plan.)*

---

## 11. Resumen ejecutivo

| Pregunta | Respuesta |
|----------|-----------|
| ¿Es Tobarra 2.0? | **Misma disciplina industrial**, **otra pista de datos** (open O2 AND) |
| ¿Qué prueba? | Intake → perímetro oficial → satélite → métricas → scorecard → repro → tests |
| ¿Qué no prueba? | LWIR ni ROS táctico sin ASEMA |
| ¿Éxito? | Acta `GO_AND_INDUSTRIAL_E2E` + pack regenerable + O2 REDIAM en mapa |

**Siguiente paso humano:** confirmar “implementa Sprint 0–1” o priorizar primero email ASEMA + download manual zips.
