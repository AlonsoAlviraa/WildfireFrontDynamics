# Pablo GEACAM / CMA — respuesta 2026-07-30 (Tobarra)

**Hilo:** `Re: Petición de información TFG`  
**De:** `pablo.arroyobretano@geacam.com`  
**Fecha:** 2026-07-30 16:19 (+ follow-up 16:21 “enviado sin querer”)  
**Gmail message IDs:** `19fb36562e96e3e0`, `19fb366e1ac158f6`  
**Descarga local:** este directorio (2026-07-30)

---

## Inventario de archivos (9 adjuntos — todos descargados)

| Archivo | Tipo | Tamaño | Contenido útil |
|---------|------|-------:|----------------|
| `2024020124_TOBARRA_20240802_1830.kmz` | KMZ perímetro | 3.6 KB | **Perímetro activo** · Sup_ha **21,489832** · 34 vértices |
| `2024020124_TOBARRA_20240802_2143.kmz` | KMZ perímetro | 3.9 KB | **Perímetro activo** · Sup_ha **37,075054** · 50 vértices |
| `2024020124_TOBARRA_20240802_1830.kml` | KML extraído | — | misma geometría (trabajo local) |
| `2024020124_TOBARRA_20240802_2143.kml` | KML extraído | — | misma geometría |
| `photo_2024-08-03_11-00-08.jpg` | Mapa INFOCAM | 345 KB | Pre Análisis · 02/08/2024 **17:11** · meteo · foto humo |
| `photo_2024-08-03_11-00-42.jpg` | Mapa INFOCAM | 333 KB | cartografía operativa (serie) |
| `photo_2024-08-03_11-00-50.jpg` | Mapa INFOCAM | 251 KB | cartografía operativa (serie) |
| `photo_2024-08-03_11-02-07.jpg` | Mapa INFOCAM | 259 KB | cartografía operativa (serie) |
| `photo_2024-08-03_11-02-13.jpg` | Mapa INFOCAM | 350 KB | cartografía operativa (serie) |
| `photo_2024-08-03_11-03-35.jpg` | Mapa ARGOS | 422 KB | Análisis y ARGOS · **21:33** · medios + flanco · 5 km/h |
| `photo_2024-08-03_11-03-41.jpg` | Mapa INFOCAM | 329 KB | cartografía operativa (serie) |

**CRS mapas:** UTM HUSO 30 / ETRS89 (INFOCAM).  
**KMZ:** WGS84 (lon ~−1.709, lat ~38.633 — Tobarra AB).

---

## Lectura del correo (puntos clave)

1. **Demora** por emergencias (La Mierla / campaña) — tono cooperativo.  
2. **Informe WFD:** le parece claro pero **muy técnico** para CMA; lo reenvió a compañeros (al menos uno puede valorarlo).  
3. **Cardoso:** **no hay más material** del que ya pasó en Dropbox.  
4. **Perímetros multi-IF:** **SÍ puede pasarlos** (varios por incendio + final de superficie) — pide **tiempo** para buscarlos.  
5. **“Cartografía operativa” (UNAP):** la actualizan por incendio; cree que sirve al modelo predictivo; **tú tienes que extraer** la info de esos productos.  
6. **Adjuntos = material Tobarra** de muestra: “échale un ojo y me dices si te vale, y si es así te busco lo que necesites.”  
7. Segundo mail (16:21): solo aclara envío accidental parcial / “ya me cuentas”.

### Lo que **no** trae este mail

- Tablita **Vp m/min** por IF (Cardoso / Hellín / Estrella)  
- Perímetros de **otros** incendios (solo Tobarra de muestra)  
- LWIR nuevo  
- Confirmación numérica de Vp 7 m/min en texto (sí hay ha en KMZ)

---

## Valor técnico para WFD

| Gap Tobarra / O2 | Estado con este drop |
|------------------|----------------------|
| Perímetro oficial-ish multi-temporal | **PARCIAL GO** — 2 instantes 18:30 (21.5 ha) y 21:43 (37.1 ha) |
| ha de parte | **~37 ha** a las 21:43 en KMZ (ancla histórica era 39 ha) |
| Cartografía operativa UNAP/ARGOS | **Muestra visual** (PNG/JPG mapas) — no SHP aún |
| O1 2ª ancla Cardoso | **Sigue bloqueada** — Pablo dice no hay más en Cardoso |
| Vp multi-IF | **Sigue pendiente** — no en adjuntos |

### Crecimiento área Tobarra (de los 2 KMZ)

| Hora (filename) | Sup_ha (atributo KMZ) | Δ ha |
|-----------------|----------------------:|-----:|
| 2024-08-02 **18:30** | **21,49** | — |
| 2024-08-02 **21:43** | **37,08** | **+15,59** en ~3 h 13 min |

→ Δt ≈ 193 min → crecimiento medio ~**4,8 ha/h** (proxy de expansión de polígono, **no** es Vp de frente lineal).

### Mapas (ejemplos leídos)

- **Pre Análisis 17:11:** detección 16:42; meteo Aemet T 35 °C, HR 10 %, viento W 21 km/h rachas 40; previsión NW.  
- **Análisis y ARGOS 21:33:** SITAC favorable; SE1 flanco izquierdo; SE2 salto zona crítica; flecha **5 km/h**; medios R/B/A etiquetados.

---

## Respuesta recomendada a Pablo (siguiente)

1. **Agradecer** y confirmar que Tobarra **sí vale** como muestra.  
2. Pedir **prioridad:**  
   - perímetros multi-temporal (como estos KMZ) de **Cardoso + Hellín + La Estrella** (y final si hay),  
   - si puede, **export vectorial** (SHP/GPKG) o más KMZ con `Sup_ha` relleno.  
3. Preguntar **formato de cartografía operativa UNAP** exportable (no solo PNG): capa / servicio / PDF con atributos.  
4. Mantener petición **suave** de Vp/ha de parte si salen al sacar perímetros finales.  
5. Ofrecer **1 página no técnica** del informe para el compañero CMA (menos jerga ML).

---

## Uso en el repo (integrado 2026-07-30)

```bash
# Parser: wildfire_front.ops_perimeter
# Eval + GeoJSON + report:
python scripts/eval_tobarra_pablo_perimeters.py
```

| Artefacto | Ruta |
|-----------|------|
| GeoJSON (derivados) | `outputs/tobarra_pablo_perimeters/*.geojson` (no se reescriben en este drop por defecto) |
| Report JSON | `outputs/tobarra_pablo_perimeters/eval_report.json` |
| Docs O2 | `docs/O2_HAUSDORFF_BLOCKED.md` (Tobarra ops PARTIAL; nacional BLOCKED) |

Opt-in: `python scripts/eval_tobarra_pablo_perimeters.py --export-geojson-to-drop` escribe GeoJSON aquí.

---

## Provenance

```
source: pablo.arroyobretano@geacam.com
org: GEACAM / CMA
thread: Petición de información TFG
downloaded_at: 2026-07-30
path: data/real_if/pablo_geacam_20260730_tobarra/
use: validation / O2 proxy Tobarra — not Cardoso anchor
never: invent Vp; treat KMZ as official national cadastre without caveat
```
