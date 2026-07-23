# REDIAM Andalucía — perímetros e histórico (respuesta 2026-07)

> **Estado:** **RESPONDIDO_GO** (buzón REDIAM)  
> **Fecha registro:** 2026-07-22  
> **Origen:** respuesta a outreach Alonso → `rediam.atiende.csma@juntadeandalucia.es`  
> **Tracking:** `docs/CONTACTOS_OUTREACH.csv` · `docs/open_if_intake/OUTREACH_AND_GAL_EXT_20260722.md`

---

## Texto de la respuesta (esencia)

REDIAM indica dos productos descargables en el portal de Descargas REDIAM (share Nextcloud `mxHMWXyHfrCxyNK`):

1. **Perímetros de incendios forestales en Andalucía 2008–2025**  
   Carpeta: `…/01_INCENDIOS/00_INCENDIOS/Historico_Incendios_COR`  
   [Enlace directo](https://portalrediam.cica.es/descargas/index.php/s/mxHMWXyHfrCxyNK?dir=/06_RIESGOS_NATURALES_TECNOLOG/03_ACCIDENTES_DESASTRES/01_INCENDIOS/00_INCENDIOS/Historico_Incendios_COR)

2. **Áreas recorridas por el fuego en Andalucía (1975–actualidad)**  
   Carpeta: `…/AreasRecorrFuego`  
   [Enlace directo](https://portalrediam.cica.es/descargas/index.php/s/mxHMWXyHfrCxyNK?dir=/06_RIESGOS_NATURALES_TECNOLOG%2F03_ACCIDENTES_DESASTRES%2F01_INCENDIOS%2F00_INCENDIOS%2FAreasRecorrFuego)

Además: **contactar con la Agencia de Emergencias de Andalucía** (responsable de la gestión de incendios en la Comunidad).

---

## Canales técnicos verificados (2026-07-22)

| Canal | URL / capa | Estado |
|-------|------------|--------|
| **WFS perímetros** (preferido para pipeline) | `https://www.juntadeandalucia.es/medioambiente/mapwms/REDIAM_perimetros_incendios_forestales?` | **OK** GetCapabilities + GetFeature GeoJSON |
| Capas WFS | `ms:perim_incendios_2008` … `ms:perim_incendios_2025` | Anual |
| **WMS perímetros** | misma base `…REDIAM_perimetros_incendios_forestales?` | OK |
| **WMS áreas recorridas** | `https://www.juntadeandalucia.es/medioambiente/mapwms/REDIAM_historico_areas_recorridas_fuego?` | OK (capas `areas_afectadas_YYYY`, `historico_incendios`) |
| Descargas Nextcloud | share token `mxHMWXyHfrCxyNK` | UI web OK; **WebDAV automatizado devuelve 401** desde este entorno → descargar en navegador o usar WFS |
| Ficha portal OGC | [WMS/WFS 2008–2025](https://www.juntadeandalucia.es/medioambiente/portal/landing-page-servicio-ogc/-/asset_publisher/1qlWV3LW9vV6/content/rediam.-wms-per-c3-admetros-de-incendios-forestales-en-andaluc-c3-ada.-2008-2016/20151) | |
| Portal ARF | [Áreas recorridas por el fuego](https://www.juntadeandalucia.es/medioambiente/portal/acceso-rediam/observacion-caracterizacion-territorio/observacion/accidentes-desastres-naturales/areas-recorridas-fuego) | Metodología satélite 1975–hoy |

### Condiciones de uso (WFS)

- **Fees:** Gratuito  
- **AccessConstraints:** uso libre y gratuito **siempre que se mencione a los autores y propietarios** (REDIAM / Junta de Andalucía)  
- **Contenido:** incendios forestales **mayores de 10 ha** en Andalucía, 2008–2025  
- **Keywords WFS:** Incendios Forestales, Infoca, IDEAndalucia  

### Esquema muestreado (GeoJSON 2024)

| Campo | Ejemplo | Notas |
|-------|---------|--------|
| `Municipio` | TURRE | |
| `Provincia` | Almería | |
| `CODIGO` | 2024040011 / IIFF2025230035 | Formato varía por año |
| `FECHA_INC` | 20240207 | YYYYMMDD |
| `SUP_ARBOLA` / `SUP_MATORR` / `SUP_PASTIZ` | ha | Superficies por tipología |
| `X_INIC` / `Y_INIC` | coords | Presente en 2024 sample; no en sample 2025 (schema parcial) |
| CRS | **EPSG:3042** | ETRS89 / UTM zone 30N (IBERPIX-like) |
| Geometría | Polygon | Anillos densos (cientos de vértices) |

**Smoke 2024 (3 features, ~173 KB GeoJSON):** OK  
**Smoke 2025 (5 features):** OK (Montizón, Úbeda, Tarifa, Villaviciosa de Córdoba, Andújar…)

```bash
curl.exe -sL --get "https://www.juntadeandalucia.es/medioambiente/mapwms/REDIAM_perimetros_incendios_forestales" ^
  --data-urlencode "SERVICE=WFS" --data-urlencode "VERSION=2.0.0" ^
  --data-urlencode "REQUEST=GetFeature" --data-urlencode "TYPENAMES=ms:perim_incendios_2024" ^
  --data-urlencode "COUNT=3" --data-urlencode "OUTPUTFORMAT=geojson" ^
  -o outputs/open_if/rediam_and/perim_2024_sample.geojson
```

---

## Qué implica para WFD (honesto)

| Gate / objetivo | ¿Desbloquea? | Por qué |
|-----------------|--------------|---------|
| **O2 Tobarra / Cardoso / CLM** | **NO** | Perímetros son **solo Andalucía**, no CLM |
| **O2 metodología Hausdorff** | **SÍ (proxy multi-IF AND)** | Vectores oficiales con fecha + ha → validar pipeline geométrico sin inventar |
| **Pista B open_if** | **SÍ** | Nuevo pack CCAA con BA/perímetro institucional |
| **Anclas Vp / ROS táctico** | **NO** en estos shapefiles | No hay Vp; hay fecha + superficies. Ops → **Agencia de Emergencias** |
| **Multi-CCAA narrative / TFG** | **SÍ** | Primera respuesta institucional con datos descargables |

---

## Plan industrial E2E (Tobarra-grade, Pista B+)

**Plan completo:** [`docs/design/ANDALUCIA_REDIAM_INDUSTRIAL_E2E_PLAN.md`](../design/ANDALUCIA_REDIAM_INDUSTRIAL_E2E_PLAN.md)

Objetivo: `GO_AND_INDUSTRIAL_E2E` — intake WFS → catálogo → gold IF → pack open + O2 REDIAM → métricas Hausdorff/área → scorecard → verify script → tests. Sin inventar Vp; ASEMA en paralelo para anclas.

---

## Acciones recomendadas

### Ya (humano, 15–30 min)

1. Abrir en navegador los dos enlaces de Descargas y bajar zips (SHP/GPKG si vienen empaquetados).  
2. Guardar en `data/open_if/rediam_andalucia/` (o `outputs/open_if/rediam_and/`) **sin commitear** binarios grandes si superan política del repo.  
3. Atribuir: *Fuente: REDIAM — Junta de Andalucía*.

### Pipeline (repo)

1. Script `scripts/fetch_rediam_perimeters.py` (WFS → GeoJSON/GPKG por año, CRS a 4326/25830).  
2. Inventario: nº polígonos/año, ha total, provincias.  
3. Pack open_if Andalucía en el estilo de `outputs/open_if/emsr*`.  
4. Tests: descarga smoke + CRS + schema mínimo.

### Outreach follow-up

1. **Agradecer** a REDIAM (1 línea + confirmación de descarga).  
2. **Agencia de Emergencias de Andalucía** (gestión IIFF):  
   - Vía ya abierta: `gerencia.asema@juntadeandalucia.es` (Alejandro García Hernández)  
   - Pedir reenvío a cartografía ops / partes: **Vp media, ha de parte, 1–2 perímetros con secuencia temporal si existen**  
   - No confundir con 112  
3. Mantener **sin** mencionar CLM/Pablo en hilos Andalucía (regla outreach multi-CCAA).

### Plantilla corta — gracias REDIAM + puente Agencia

```
Para: rediam.atiende.csma@juntadeandalucia.es
Asunto: Re: consulta datos espaciales — recibido y descargando

Buenos días,

Muchas gracias por la respuesta y por los enlaces a:
- Perímetros de incendios forestales en Andalucía 2008-2025
- Áreas recorridas por el fuego (1975-actualidad)

Ya estoy consultando el WFS
(mapwms/REDIAM_perimetros_incendios_forestales) y las carpetas
de Descargas REDIAM. Citaré a REDIAM / Junta de Andalucía como
fuente.

Si pueden, les agradecería el buzón o canal recomendado en la
Agencia de Emergencias de Andalucía para consultas de datos
operativos (partes / validación), sin interferir en el 112.

Saludos,
Alonso Alvira
alonso.alvbal@gmail.com
```

---

## Run status industrial E2E (2026-07-22)

| Paso | Resultado |
|------|-----------|
| WFS fetch 2022–2025 | **OK** · n=58/40/38/53 (189 IF) → `data/open_if/rediam_andalucia/wfs_cache/` |
| Inventory + gold | **OK** · gold `2024040053` Níjar/Almería 2024-06-06 ~2144 ha · silver Obejo + Lubrín |
| Pack gold | `outputs/open_if/and_2024040053_20240606` · **GO_OPEN_AND_O2** · FIRMS 85 · dNBR GO · Hausdorff PASS |
| Pack silver ×2 | PARTIAL (O2 OK; FIRMS 0 / dNBR SKIP) |
| Tests | `tests/test_rediam_and_intake.py` + `tests/test_and_if_pack.py` |
| Acta | `docs/AND_INDUSTRIAL_E2E_VERIFICATION.{md,json}` |

**Comandos:**

```powershell
$env:PYTHONPATH = "."
python scripts/fetch_rediam_perimeters.py --years 2022,2023,2024,2025
python scripts/inventory_rediam_and.py --no-firms
python scripts/build_and_if_pack.py --selection data/open_if/rediam_andalucia/inventory/selection_gold.json
python scripts/build_open_if_dnbr.py --pack outputs/open_if/and_2024040053_20240606 --event-date 2024-06-06
python scripts/verify_and_industrial_e2e.py
```

> Nota: capa 2023 WFS ~81 MB (anillos densos). No commitear geojson anuales grandes.

---

## Provenance

| Campo | Valor |
|-------|-------|
| Solicitante | Alonso Alvira (`alonso.alvbal@gmail.com`) |
| Buzón REDIAM | `rediam.atiende.csma@juntadeandalucia.es` (no usar `…csmaea@`) |
| Message id envío | `19f88abfb1aba151` (ronda 2 buzón correcto) |
| Verificación WFS | 2026-07-22, GetCapabilities + GetFeature COUNT=3/5 · full years 2022–2025 industrial |
| Contacto servicio (capabilities) | `rediam.atiende.csma@juntadeandalucia.es` · +34 955 003 400 |
