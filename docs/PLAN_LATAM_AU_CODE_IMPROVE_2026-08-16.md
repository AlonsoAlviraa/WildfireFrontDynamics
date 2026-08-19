# Plan de mejora — código de packs LATAM / AU / otros países

**As of:** 2026-08-16  
**Alcance:** solo pipeline de datos abiertos fuera de CLM (`wildfire_front/open_if/latam_au.py`, `scripts/*latam_au*`, packs bajo `data/open_if/latam_au/`).  
**No entra:** H1, GO_Q, GEACAM, VisionSetil, retrain v35, FREEZE lift.  
**SSOT previo:** `docs/PLAN_ML_DATA_LATAM_AU_2026-08-13.md` · status `docs/data_campaigns/LATAM_AU_P0_P2_STATUS.md`

**Shipped (eng, 2026-08-16):** PR-A–H implemented. Warp is idempotent and GCs `*_to_cems_to_cems*`. Domain-gap reads `WARP_PROVENANCE.json`. `complete_proxy` mean excludes Δt<12h and label-mask IoU>0.98. Specs `BO_EMSR765` + `MX_EMSR717` added (R6=0 until hashed meta). Annual next-mask → `blocked_annual_not_event`. CONAF ingest stub does not flip `lab_ok_conaf` product rail. No transfer IoU invented.

---

## 0. Dónde está el código hoy

Hay **6 packs materializados**, todos `ml_weak`. El modelo `clm_ensemble_v34` **no se puede evaluar en el scorecard oficial** (`blocked_incompatible_schema`) salvo un camino *proxy* aparte.

| Pack | País | Tipo | Labels | S2 | Covariates | Warp S2→label | complete_proxy IoU |
|------|------|------|--------|----|------------|---------------|--------------------|
| `AU_EMSR500_PERTH` | AU | CEMS L2 | 3 | 3 | sí | 0.60 (sucio) | **0.916** (32 tiles) |
| `CL_EMSR647_NACIMIENTO` | CL | CEMS L2 | 3 | 3 | sí | **0.086** | **0.788** (32 tiles) |
| `AU_EMSR408_NSW` | AU | CEMS L2 | 4 | 3 | sí | 0.184 | no medido |
| `CL_EMSR715_VALPARAISO` | CL | CEMS JSON L2 | 3 | 3 | sí | 0.466 | no medido |
| `BR_PANTANAL_2020_MAPBIOMAS` | BR | anual L1 | 3 años | 3 | **no** | no aplica igual | no (no hay next-mask) |
| `AU_NAFI_NT_SEASON_2023` | AU | anual L1 250 m | 3 años | 3 | **no** | no | no |

**Descubiertos y no codificados** (CSV `LATAM_AU_CANDIDATES.csv`, R6=0):

- CEMS: `MX_EMSR717`, `BO_EMSR765`, `GT_EMSR727`, `BZ_EMSR726`, `AU_EMSR408_GOSPERS`
- Agencia/open: `AU_NT_FIRE_HISTORY`, `AU_NSW_NPWS_HISTORY`, `AU_BLACK_SUMMER_PANGAEA`, `BR_CERRADO_MAPBIOMAS_SAMPLE`
- En disco, otro contrato: FireBench Caldor, PT-FireSprd, GOFER (`data/external/`) — **no** pasan por `latam_au.py`

### Qué ya funciona (no rehacer)

- Specs + materialize CEMS zip/JSON + STAC S2 + hash `meta.json`
- Download MapBiomas / NAFI + window anual
- ERA5 Open-Meteo por pack (punto, no raster nativo)
- Fill covariates (meteo/DEM/veg) en 4 EMSR
- Adapt NPZ `legacy17` en modos `partial_fill` y `real_proxy`
- Eval experimental vs complete_proxy **etiquetados** (no sellados)
- LOFO fold JSON honesto (`model_iou=null`)
- Rights / license matrix / tests de campaña

---

## 1. Diagnóstico de código (por qué no mejora el modelo)

El tapón no es “faltan países”. Es que **los bytes que hay no entran limpios al contrato NDWS**, y las métricas que sí salen **miden casi copiar la máscara anterior**.

### D1 — Warp no es idempotente (bug)

`scripts/warp_latam_au_s2_to_cems.py` escribe `eo_aligned/{stem}_to_cems.tif` y **no excluye** destinos previos. Re-ejecutar produce:

```
*_to_cems.tif
*_to_cems_to_cems.tif
*_to_cems_to_cems_to_cems.tif
```

Perth y Nacimiento reportan `n_warped=9` con solo **3** S2 reales. El scorecard de domain-gap sigue diciendo `blocked_crs_mismatch` porque **no lee** `eo_aligned/`.

### D2 — IoU 0.85 no es transferencia

`complete_proxy_model_iou` ~0.852 en **2 packs, 32 tiles, primer par de labels**:

| Pack | Par de labels | Δt real | Mask IoU label→label | Lectura |
|------|---------------|---------|----------------------|---------|
| Perth | 05-feb → 11-feb | ~6 d | **0.99** (casi idénticos) | Predecir “next” es copiar. 0.92 es fácil. |
| Nacimiento | 13-feb 23:56 → 14-feb 02:15 | **~2,3 h** | 0.86 | No es next-day. Dinámica casi nula. |

EMSR408 (4 monit, Δt de días) y EMSR715 **no se midieron**. Ahí es donde habría señal.

### D3 — NBR vs CEMS es un umbral ciego

`threshold_nbr_mask(nbr < -0.1)` fijo. Nacimiento da proxy IoU **0.086**: o el S2 no es post-fuego útil, o el umbral no vale en eucalipto/pino chileno, o se emparejó mid/pre. Perth mid/post son **el mismo día civil**, tiles distintos.

### D4 — Meteo/DEM son constantes

`fill_latam_au_ndws_covariates.py` pinta un **campo constante** (media del periodo Open-Meteo) en todo el raster. DEM puede ser `fallback_constant` si `--skip-dem-fetch`. El UNet ve 17 canales, pero viento/T/HR **no varían en el espacio**. Eso no es NDWS.

### D5 — Adaptador solo habla CEMS

`adapt_latam_au_to_ndws_patches.py` itera `EMSR_PACK_SPECS`. MapBiomas y NAFI (anuales, CRS 4326, NAFI 250 m) **no tienen camino a NPZ**. `build_latam_au_lofo_folds.py` hold-out NSW sigue `compatible_with_clm_ensemble_v34=false`.

### D6 — Países encontrados, specs vacíos

México / Bolivia / Guatemala / Belice están en el catálogo con URL CEMS y R1=1, pero **cero** entradas en `EMSR_PACK_SPECS`. El materialize no puede crearlos.

### D7 — CONAF no tiene ingest

Hay request + folio `AR003T0011849` (vence 10-sep). No hay `ingest_conaf_shp.py` ni schema de pack `CL_CONAF_*`. Si llega el SHP, el código no sabe convertirlo.

### D8 — External (PT, US, FireBench) huérfano

`data/external/pt_firesprd`, `firebench/caldor_2021`, GOFER no comparten contrato `wfd_open_if_pack_meta_v1`. No se pueden mezclar en el mismo eval sin un bridge.

---

## 2. Norte de la mejora

**Objetivo:** que los packs extranjeros sean **inputs reproducibles y honestos** para eval zero-shot (y, más adelante, un sealed harness). No subir FREEZE. No vender 0.85.

Done-when del plan (código):

1. Warp idempotente: 3 S2 → 3 aligned; `n_warped` = nº de escenas fuente.  
2. Domain-gap scorecard lee `eo_aligned` y deja de mentir `blocked_crs_mismatch` cuando el warp existe.  
3. `complete_proxy` se reporta **por par de labels con Δt ≥ 12 h** (mejor ≥ 1 d); pares <12 h se marcan `too_short_delta` y no entran en la media.  
4. Se mide EMSR408 + EMSR715 (los pares útiles).  
5. Specs + materialize de **≥2** CEMS nuevos (prioridad `BO_EMSR765`, `MX_EMSR717`).  
6. MapBiomas/NAFI: protocolo **anual** explícito (no next-mask); covariates opcionales; `model_iou` sigue null.  
7. Stub de ingest CONAF (SHP → pack `ml_weak` / `pending_cession`) **sin** `lab_ok`.  
8. Tests que fallen si reaparece `_to_cems_to_cems` o un par <12 h en la media.

---

## 3. Rails

| Rail | Valor |
|------|--------|
| FREEZE / v35 | no |
| `model_iou` sellado / transfer | null hasta harness + owner |
| `complete_proxy_*` | etiqueta obligatoria; ≠ U1 TEST ≠ ROS |
| CEMS / MapBiomas / NAFI | proxy / L1–L2, no O2, no CONAF |
| `lab_ok_conaf` | false hasta cesión escrita |
| fusion / GO_Q | no se tocan |

---

## 4. Trabajo por PRs (orden de dependencia)

### PR-A — Higiene warp (1 día, bloquea el resto)

**Archivos:** `scripts/warp_latam_au_s2_to_cems.py` · `tests/test_latam_au_residual_backlog.py`

- Fuente S2 **solo** `pack/eo/*.tif` (nunca `eo_aligned/`, nunca stem que ya termine en `_to_cems`).
- Destino fijo `eo_aligned/{original_stem}_to_cems.tif`; si existe y CRS/shape coinciden con el label ref → skip.
- Borrar (o `--gc`) los `*_to_cems_to_cems*.tif`.
- Test: re-run 2× → mismo `n_warped` = n S2 fuente.

**Done-when:** Perth/Nacimiento `n_warped=3`. Summary no cuenta dobles.

### PR-B — Scorecard usa el warp (½ día, tras A)

**Archivos:** `scripts/eval_latam_au_domain_gap.py` · `wildfire_front/open_if/latam_au.py` (helper `aligned_s2_paths`) · scorecard JSON

- Si hay `WARP_PROVENANCE.json` + aligned, `stac_proxy.status=measured` con el IoU ya calculado.
- Si no hay warp: seguir `blocked_crs_mismatch` (honesto).
- Extra: no reportar `blocked` cuando el pack ya está warpeado.

**Done-when:** scorecard AU/CL `stac_proxy.value` numérico o `null` con razón actual, nunca “no audited warp” si el fichero existe.

### PR-C — Pares temporales honestos + medir 408/715 (1–2 días)

**Archivos:** `scripts/run_latam_au_complete_model_iou.py` · `run_latam_au_experimental_model_iou.py`

- Extraer `delivery_utc` del `meta.json`; Δt entre par t→t+1.
- Excluir de la media pares con Δt < 12 h (`too_short_delta`).
- No usar como par “next” dos productos con mask IoU > 0.98 (Perth DEL→MONIT) — reportar aparte como `static_label_copy`.
- Correr 408 (4 monit, Δt de días) y 715.
- Reportar por pack: `n_pairs_used`, `delta_hours`, `label_mask_iou`, `complete_proxy_model_iou`.
- Sampling: no solo los primeros 32 tiles en scanline; estratificar borde / interior / baja densidad.

**Done-when:** JSON nuevo con 408+715; Perth static separado; Nacimiento 2,3 h **fuera** de la media.

### PR-D — NBR umbral por pack (1 día, tras A)

**Archivos:** `warp_latam_au_s2_to_cems.py`

- Emparejar S2 **post** (datetime > último label) si existe; si no, nearest after first label.
- Barrido de umbral documentado `{-0.2,-0.15,-0.1,-0.05,0}` → elegir por IoU en **un** split de labels y **congelar**; no k-fit silencioso en el mismo par que se reporta (dejar 1 label out).
- Perth: dejar de llamar mid/post al mismo día civil si son tiles, no fases.

**Done-when:** Nacimiento proxy IoU o bien sube con umbral/fecha auditados, o queda bajo con razón (`s2_not_post` / `cloud` / `threshold_unusable`) — no 0.086 opaco.

### PR-E — Covariates no constantes (2 días)

**Archivos:** `fill_latam_au_ndws_covariates.py`

- Meteo: raster **por escena** (hora del label), no media de toda la ventana. Sigue siendo 1 valor espacial si Open-Meteo es punto — **documentar** `spatial_constant=true`. Opcional: grid Open-Meteo 0.1° si la API lo da.
- DEM: prohibir `fallback_constant` en `--all` salvo flag explícito; fallar el pack.
- Extender fill a MapBiomas/NAFI **solo** si hay label grid (anual).

**Done-when:** `PROVENANCE.json` declara `meteo_spatial=constant_point|gridded` y `dem_status!=fallback_constant` en los 4 EMSR.

### PR-F — Dos CEMS nuevos: BO + MX (2–3 días)

**Archivos:** `latam_au.py` (`EMSR_PACK_SPECS`) · `materialize_latam_au_emsr_packs.py` · candidates CSV R6

Prioridad (URL ya en catálogo, Rapid Mapping 2024):

1. `BO_EMSR765` (Bolivia 2024)  
2. `MX_EMSR717` (México 2024)

Mismo contrato que EMSR715 (JSON Rapid) o zip S3 si existe. ≥3 productos o ≥3 S2. Luego warp + covariates + (si hay ≥2 labels con Δt≥12 h) complete_proxy.

Runner-up: `GT_EMSR727`, `BZ_EMSR726` (mismo cluster; solo si BO/MX salen baratos).  
**No** Gospers hasta verificar bbox del zip (nota ya en CSV).

**Done-when:** 2 directorios `data/open_if/latam_au/{bo,mx}/…` con `meta.json` hasheado + test `source_pack_ready`.

### PR-G — L1 anual: no fingir next-mask (1 día)

**Archivos:** `adapt_latam_au_to_ndws_patches.py` · `build_latam_au_lofo_folds.py`

- Aceptar `WEAK_PACK_SPECS` en modo `annual_scar_only`.
- `eval_status=blocked_annual_not_event` si alguien pide next-mask IoU.
- LOFO hold-out anual documenta la misma razón (no “incompatible_schema” genérico).

**Done-when:** un NPZ de Pantanal/NAFI se puede **generar**; eval next-mask se niega con código estable.

### PR-H — Ingest CONAF stub (½–1 día)

**Archivos nuevos:** `scripts/ingest_conaf_perimeters.py` · test

- Input: SHP/GPKG + `--cession-evidence` opcional.
- Output: pack `CL_CONAF_<event>` `class=ml_weak`, `lab_ok_conaf=false` salvo evidence que pase `record_conaf_cession`.
- Sin evidence: pack usable para geometría, **no** para train list.

**Done-when:** fixture sintético round-trip; no toca flags.

### PR-I — Bridge `data/external` (opcional, 1–2 días)

PT-FireSprd / FireBench → el mismo `meta.json` v1 bajo `data/open_if/external_bridge/`, `region=pt|us`. Eval separado. No mezclar en media LATAM.

---

## 5. Semanas (si se ejecuta seguido)

| Semana | PRs | Salida |
|--------|-----|--------|
| **S1** | A + B + C | Warp limpio; scorecard coherente; IoU proxy **honesto** en 408/715; Perth/Nacimiento recortados |
| **S2** | D + E | NBR auditado; covariates sin DEM falso; meteo por timestamp |
| **S3** | F | Bolivia + México en disco, mismo pipeline |
| **S4** | G + H (+ I si sobra) | Anuales no mienten; CONAF listo para cuando llegue el SHP (10-sep) |

---

## 6. Qué no hacer

- Promediar Perth 0.92 + Nacimiento 0.79 y llamarlo “transfer 0.85”.  
- Meter MapBiomas anual como fold LOFO de dinámica.  
- Añadir 10 CEMS más antes de arreglar warp + Δt.  
- `lab_ok_conaf=true` al primer GeoJSON.  
- Retrain v35 / lift FREEZE desde estos packs.  
- Usar FireBench/FLAME para reclamar dominio LATAM.

---

## 7. Verificación

```powershell
pytest tests/test_latam_au_campaign.py tests/test_latam_au_p1_p2.py tests/test_latam_au_product_e2e.py tests/test_latam_au_residual_backlog.py tests/test_inventory_open_if_urls.py -q

python scripts/warp_latam_au_s2_to_cems.py --all
# n_warped == n S2 fuente; cero archivos *_to_cems_to_cems*

python scripts/eval_latam_au_domain_gap.py
python scripts/run_latam_au_complete_model_iou.py --all
# media solo pares Δt>=12h y label_mask_iou<0.98
```

---

## 8. Mapa rápido de ficheros

| Pieza | Ruta |
|-------|------|
| Contrato packs | `wildfire_front/open_if/latam_au.py` |
| Materialize CEMS | `scripts/materialize_latam_au_emsr_packs.py` |
| Weak BR/AU | `scripts/download_mapbiomas_fogo.py` · `download_nafi_scars.py` · `materialize_latam_au_weak_packs.py` |
| Warp | `scripts/warp_latam_au_s2_to_cems.py` |
| Covariates | `scripts/fill_latam_au_ndws_covariates.py` |
| NPZ | `scripts/adapt_latam_au_to_ndws_patches.py` |
| Eval | `scripts/run_latam_au_complete_model_iou.py` · `eval_latam_au_domain_gap.py` |
| Bytes | `data/open_if/latam_au/{au,br,cl}/` |
| Candidatos | `docs/data_campaigns/LATAM_AU_CANDIDATES.csv` |
