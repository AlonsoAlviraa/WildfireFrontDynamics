# Plan de acción industrial — Extremadura RAI (3 perímetros 2025)

**Status:** IMPLEMENTED (técnico) — `GO_EXT_INDUSTRIAL_E2E` · packs PARTIAL (FIRMS 2025 archive 404)  
**Pendiente humano:** enviar Word a `rai@juntaex.es`  
**Fecha:** 2026-07-23  
**Fuente:** Registro de Áreas Incendiadas (RAI) · `rai@juntaex.es` · Servicio de Prevención y Extinción de Incendios Forestales (INFOEX)  
**Analogía:** mismo rigor que Tobarra (gates) y AND REDIAM (O2 oficial) — **perímetros SHP oficiales con fechas det/ext**

---

## 0. Qué tenemos (inventario)

| IF (nombre archivo) | Id_incen | fecha_det | fecha_ext | ha (attr) | CRS | Gold? |
|---------------------|----------|-----------|-----------|-----------|-----|-------|
| **Caminomorisco** | 2025100393 | 2025-07-29 | 2025-08-29 | **~2680** | EPSG:25829 | **GOLD** (mayor ha + ventana 31 d) |
| **Alburquerque** | 2025060450 | 2025-08-14 | 2025-08-29 | **~2356** | EPSG:25829 | Silver |
| **Burguillos del Cerro** | 2025060453 | 2025-08-14 | 2025-08-24 | **~561** | EPSG:25829 | Silver |

**Campos shape:** `OBJECTID`, `Id_incen`, `Hectareas`, `MEDICION`, `fecha_det`, `fecha_ext`, `SHAPE_Leng`, `SHAPE_Area`.

**Raw:** `data/open_if/extremadura_rai_2025/raw/{Alburquerque,Caminomorisco,Burguillos_del_Cerro}/`  
**Formulario:** `Peticion_de_Datos_RELLENADA_Alonso_Alvira.docx` → **debe enviarse a `rai@juntaex.es`** (registro).

**Ventaja vs REDIAM:** fechas de **detección y extinción** → ventana FIRMS/dNBR más limpia.

---

## 1. Objetivo industrial

Veredicto **`GO_EXT_INDUSTRIAL_E2E`** si:

| Capa | Criterio |
|------|----------|
| C1 Intake | 3 SHP inventariados + CRS + ha |
| C2 Selection | 1 gold + 2 silver documentados |
| C3 O2 oficial | perímetro RAI en pack 4326 + nativo 25829 |
| C4 FIRMS | hotspots en [det−1d, ext+1d] o SKIP documentado |
| C5 dNBR | pre/post S2 o SKIP |
| C6 Métricas | área equal-area, ratio hull, Hausdorff si hay pts |
| C7 Scorecard | GO/PARTIAL/NO_GO; sin Vp inventado |
| C8 Brief + map | 1 p + Leaflet |
| C9 Tests | fixtures offline |
| C10 Formulario | Word devuelto a RAI (humano) |

**No inventar:** Vp táctico · hull = quemado oficial · despacho field_ops.

---

## 2. Plan de acción (días)

### Hoy (D0) — **GO técnico**

1. ✅ Descargar zips RAI + unzip  
2. ✅ Inventariar CRS/ha/fechas  
3. ✅ Word rellenado  
4. **Implementar** `inventory_ext_rai.py` + `build_ext_if_pack.py`  
5. **Generar 3 packs** `outputs/open_if/ext_*`  
6. **FIRMS** en ventana det–ext (Caminomorisco gold primero)  
7. **dNBR** gold (si STAC responde)  
8. **verify_ext_industrial_e2e.py** + acta  
9. **Tests** offline  
10. **Tú:** enviar Word a `rai@juntaex.es` (obligatorio formal)

### D1 — Cierre y demo

1. Índice multi-IF EXT + fila en COMPARE  
2. Demo triple: Tobarra + Níjar (AND) + Caminomorisco (EXT)  
3. Gracias RAI (confirmación uso no comercial)

### D2–D7 — Paralelo multi-CCAA

| Track | Acción |
|-------|--------|
| AND | Mail ASEMA ancla Níjar |
| CyL | Trámite transparencia 1 IF |
| GAL | Esperar Extinción |
| EXT | Si RAI manda más IF → mismo pack pipeline |

---

## 3. Layout

```
data/open_if/extremadura_rai_2025/
  raw/...
  inventory/event_catalog.csv
  inventory/selection_gold.json
  geojson_4326/*.geojson

outputs/open_if/ext_<id>_<fecha>/
  manifest.json
  vectors/perimeter_rai.geojson
  vectors/perimeter_rai_native_epsg25829.geojson
  vectors/firms_*.geojson
  metrics_o2.json
  scorecard_ext_industrial.json
  map.html
  operator_brief_open_if.md
  provenance.json
  dnbr_status.json

docs/EXT_INDUSTRIAL_E2E_VERIFICATION.{md,json}
docs/open_if_intake/EXTREMADURA_RAI_2025.md
```

**Atribución:** *Fuente: Registro de Áreas Incendiadas (RAI) — Junta de Extremadura / INFOEX. Uso no comercial de validación; no redistribuir crudos sin acuerdo.*

---

## 4. Gold selection rationale

**Caminomorisco** = gold porque:

- Mayor ha (~2680)  
- Ventana temporal larga (29 jul–29 ago 2025) → más probabilidad FIRMS/dNBR  
- Nombre municipal claro  

Alburquerque y Burguillos = silver (misma fecha det 14 ago; Burguillos más pequeño).

---

## 5. Comandos objetivo

```powershell
$env:PYTHONPATH = "."
python scripts/inventory_ext_rai.py
python scripts/build_ext_if_pack.py --tier all
python scripts/build_open_if_dnbr.py --pack outputs/open_if/ext_<gold> --event-date 2025-07-29
python scripts/verify_ext_industrial_e2e.py
```

---

## 6. Riesgos

| Riesgo | Mitigación |
|--------|------------|
| FIRMS 2025 archive incompleto | SKIP honesto + PARTIAL |
| Formulario no enviado | Bloqueo formal de relación RAI |
| MEDICION=5 significado opaco | Guardar en props; no interpretar como Vp |
| No commitear zips grandes | gitignore raw si hace falta |

---

## 7. Relación stack dual → multi-CCAA

```
OPS gold:     Tobarra (LWIR+Vp)
OPEN O2 AND:  Níjar REDIAM
OPEN O2 EXT:  Caminomorisco RAI  ← este plan
```

**Mensaje demo:** tres CCAA, mismos gates, honestidad HOLD sin ancla ops.
