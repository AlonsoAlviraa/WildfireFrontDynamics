# PLAN — Nuevos incendios y material de entrenamiento (LATAM + Australia)

> **As of:** 2026-08-13  
> **Objetivo:** mejorar **métricas ML de lab** con dominio nuevo (fuera del pool CLM/España), sin violar rails.  
> **SSOT gates:** `docs/CURRENT_STATE.md` · `docs/ML_PRODUCT_GO_STATUS.json` · `docs/PLAN_ML_LEAP_2026-08-12.md`  
> **Intake local (CLM):** `docs/ML_LEAP_REQUEST_DATA.md` · `docs/REAL_IF_INTAKE_PROTOCOL.md` · `docs/DATA_ANCHOR_SSOT.md`  
> **Producto:** `clm_ensemble_v34` lab · **no** field_ops fusion · **no** despacho táctico  

## Verdict en una línea

Para subir métricas de forma honesta hace falta **nuevo material multi-escena + máscaras/perímetros auditables** en dominios distintos a Tobarra/CLM. LATAM y Australia son **pools P1 de open-data** (CEMS/FIRMS/agencias nacionales), no un atajo a GO_Q o fusion ON. Orden: **descubrir → inventariar → rights → pack GeoTIFF ≥3 → eval LOFO/transfer → (solo entonces) lift FREEZE + retrain v35**.

---

## 1. Por qué LATAM + Australia (y por qué no “más Tobarra”)

| Hecho repo | Implicación |
|------------|-------------|
| Tobarra LOFO ~0.49; KEEP thrash = **KILL** | Más epochs en el mismo mix **no** es el plan |
| Solo **1** ancla `confirmed` (Tobarra) | Multi-IF honesto necesita **más eventos con cite** |
| U1 TEST IoU ~0.86 / selective @80 ~0.90 | Techo de sell lab; salto real = **dominio + datos**, no vanity retrain |
| FREEZE_ML_AND_REQUEST_DATA | Primero **bytes + inventario**, después modelo |

**Hipótesis de métricas (a medir, no a inventar):**

1. **Transfer out-of-Spain:** IoU / Δ-vs-copy en packs LATAM/AU (holdout por evento).  
2. **LOFO multi-continente:** fold leave-one-fire-out con ≥1 IF AU + ≥1 IF LATAM + CLM.  
3. **Calibración / selective:** ECE y risk–coverage en dominio nuevo (E1b method).  
4. **Domain gap report:** tabla “CLM test vs AU/LATAM test” sin mezclar IoU con ROS.

---

## 2. Rails (no negociables)

| Rail | Valor |
|------|--------|
| field_ops ML fusion | **OFF** |
| GO_Q | **partial** (no se cierra con open data extranjero) |
| FREEZE Tobarra KEEP reopen | **false** hasta IF nuevo + OK humano |
| Anclas | Solo `confirmed` con cite; sin inventar Vp/ha |
| O2 / catastro | CEMS/EFFIS/NASA = **proxy**, no perímetro oficial ES |
| Rights | Licencia / términos de uso documentados antes de train |
| PII / ops sensibles | No en git; raw bajo `data/` gitignored |

---

## 3. Criterio de incendio “útil para ML” (mínimo)

Un evento entra a **candidato train/eval** solo si cumple **todas**:

| # | Requisito | Por qué |
|---|-----------|---------|
| R1 | **≥3 escenas** datadas (mismo sensor o pipeline alineable) | Dinámica / no single-frame vanity |
| R2 | Geometría usable: perímetro o máscara quemada o active-fire stack | Target o weak label |
| R3 | CRS + bbox + fechas documentados | Repro |
| R4 | Licencia open o cesión escrita | Rights |
| R5 | **No** depende de un solo `k` multi-IF ni de k-fit silencioso | Honesty B4 |
| R6 | Hash + inventario en CSV (protocolo real_if) | Audit |

**Clases de uso** (como `REAL_IF_INTAKE_PROTOCOL`):

- `ml_strong` — R1–R6 + máscaras alineadas o protocolo umbral estable  
- `ml_weak` — active fire / burned area coarse (solo pretrain / weak labels)  
- `context_only` — meteo o mapa sin multi-escena  
- `discard` — basura, FOV roto, rights dudosos  

**No es candidato retrain** si solo hay: 1 frame, KMZ sin tiempo, o paper abstract sin bytes.

---

## 4. Mapa de fuentes (búsqueda)

### 4.1 Australia (prioridad alta — open y denso)

| Fuente | Qué da | Uso ML | Acceso | Notas honesty |
|--------|--------|--------|--------|----------------|
| **Digital Earth Australia / DEA Hotspots** | Hotspots, historia | weak / timeline | open | ≠ perímetro final |
| **NAFI (N. Territory / north AU)** | Fire scars, seasonality | burned-area labels | open/reg | Bueno multi-escena estacional |
| **Geoscience Australia / Sentinel hub AU** | EO stacks | inputs GeoTIFF | open | Alinear GSD al contrato geotiff |
| **NSW RFS / Vic CFA open data** (donde exista) | perímetros incidentes | validation | open/mixed | Rights por estado |
| **AFAC / national situation** | catálogo eventos | discovery | web | Solo índice → bajar bytes open |
| **FIRMS / VIIRS / MODIS** | NRT hotspots global | weak | NASA open | Proxy; no “campo validado” |
| **CEMS EMSR (si hay AU)** | delineation | proxy perimeter | Copernicus | Proxy ≠ catastro |

**Target AU (ejemplos de búsqueda, no lista cerrada):**

1. Incendios con **≥1 delineation CEMS o scar DEA** + **≥3 fechas Sentinel-2/Landsat** en ventana.  
2. Season north AU (NAFI) con scar maps multi-week (weak → strong si hay high-res).  
3. Evitar mega-fires solo “news clip” sin stack EO.

### 4.2 Latinoamérica (prioridad alta — diversidad de combustible/clima)

| Región | Fuente | Qué da | Notas |
|--------|--------|--------|-------|
| **Chile** | CONAF / CIREN / datos abiertos GORE | perímetros, stats | Pedir SHP+fecha; rights |
| **Brasil** | INPE BDQueimadas, MapBiomas Fogo | focos, scars anuales | Excelente volume; weak→annual scar |
| **Argentina** | SMN / provincias / SNMF (si open) | focos, reportes | Heterogéneo por provincia |
| **México** | CONAFOR / datos abiertos | focos, polígonos | Validar año y CRS |
| **Colombia / Perú / Bolivia** | IDEAM / SERFOR / ABT + FIRMS | focos | Más weak-label |
| **Regional** | CEMS EMSR LatAm, EFFIS (parcial), GWIS | perímetros crisis | Proxy |
| **Global** | FIRMS, GFW fires, MODIS MCD64 | burned area | Coarse; pretrain only |

**Target LATAM (ejemplos de búsqueda):**

1. **Brasil MapBiomas Fogo + INPE:** 2–3 eventos con scar anual + stack Sentinel en pico.  
2. **Chile temporada** con perímetro oficial o CEMS + multi-S2.  
3. **México** polígono CONAFOR + 3+ fechas EO.  
4. Evitar solo CSV de focos sin geometría de área quemada.

### 4.3 Fuentes transversales (siempre en el radar)

| Fuente | Rol |
|--------|-----|
| **Copernicus EMS Rapid Mapping** | Perímetros de activación (proxy) |
| **Sentinel-2 / Landsat STAC** (Element84, Planetary, CDSE) | Stacks input |
| **ERA5-Land / GSOD** | Meteo alineable (canal opcional; no inventar ROS) |
| **Papers + Zenodo/Figshare** | Datasets publicados (FLAME, Corsican, etc.) — **no** sustituyen multi-IF ops, pero sí pretrain |

---

## 5. Pipeline de trabajo (fases)

```
F0 Discover  →  F1 Rights+Inventory  →  F2 Pack bytes  →  F3 Weak/strong labels
     →  F4 Eval zero-shot / LOFO  →  F5 Decision FREEZE lift  →  F6 Train v35 (optional)
```

### F0 — Discover (1–2 semanas eng + humano)

| Entrega | Dueño | Artefacto |
|---------|-------|-----------|
| Lista **≥20** eventos candidatos (10 AU + 10 LATAM) | Data Steward | `docs/data_campaigns/LATAM_AU_CANDIDATES.csv` |
| Score R1–R6 por evento (0/1) | eng | misma CSV |
| Top **6** shortlist (3+3) | Alonso + Steward | `docs/data_campaigns/LATAM_AU_SHORTLIST.md` |

**Columnas CSV mínimas:**  
`event_id, country, year, lat, lon, source_index, n_eo_scenes_est, perimeter_source, license, class(ml_strong|ml_weak|context|discard), url, notes`

### F1 — Rights + inventory (antes de bajar terabytes)

| Entrega | Dueño |
|----------|-------|
| Ficha license por fuente (URL T&C + “lab internal OK?”) | Alonso / legal light |
| `inventory_real_if`-style CSV de URLs + hashes al materializar | eng |
| Rechazar cualquier dump sin provenance | todos |

### F2 — Pack bytes (gitignored raw)

Árbol propuesto (no commitear rasters grandes):

```
data/open_if/latam_au/<region>/<event_id>/
  README.md          # source, license, dates, bbox
  eo/                # GeoTIFF multi-date
  labels/            # mask / perimeter / hotspots
  meta.json          # CRS, GSD, sensor, license_id
```

Contrato: alinear a `docs/GEOTIFF_INPUT_CONTRACT.md` (si existe) / pipeline `geotiff_to_training_patches`.

**Done-when pack listo para eval:** ≥3 GeoTIFF datados + 1 label layer + `meta.json` + README rights.

### F3 — Labels

| Nivel | Método | Métrica que desbloquea |
|-------|--------|------------------------|
| L0 hotspots | FIRMS densify | solo discovery |
| L1 burned coarse | MCD64 / MapBiomas annual | weak pretrain |
| L2 perimeter | CEMS / agency SHP | transfer eval semi-strong |
| L3 multi-mask aligned | manual/semi + same GSD | **train/eval fuerte** |

Priorizar **2 eventos L2+** y **4 L1** antes de pedir L3 caro.

### F4 — Eval (sin retrain primero)

Orden honesto (FREEZE intacto):

1. `check_release_flags` PASS  
2. Smoke ML actual en CLM test (baseline sellada)  
3. **Zero-shot** `clm_ensemble_v34` (o pesos actuales) en packs LATAM/AU → scorecard nuevo  
4. Tabla gap: `IoU_CLM_test` vs `IoU_AU` vs `IoU_LATAM` (n, conf intervals si n≥)  
5. Selective/FNR method note si hay confidences (`ML_LEAP_SELECTIVE_FNR.md`)

**No-go vanity:** reportar solo el mejor tile; promediar fires con 1 escena; mezclar IoU con ROS.

### F5 — Decisión de lift FREEZE (humano)

Lift **parcial** solo si:

- ≥1 pack `ml_strong` nuevo **o** ≥3 `ml_weak` con eval reproducible, **y**  
- zero-shot gap documentado, **y**  
- Alonso escribe OK en PR/acta (promote data, no fusion).

Lift **no** implica fusion ON ni GO_Q true.

### F6 — Train v35 (solo post-F5)

| Paso | Guardrail |
|------|-----------|
| Rebuild patches | manifest seed + event IDs en holdout |
| Train | **train** split only; select **val**; report **test** + LOFO |
| Gate | Δ vs copy en test > 0 **o** NO-GO con números (`ML_TRANSFER_PROTOCOL`) |
| Product | scorecard + stamp refresh; fusion sigue OFF |

---

## 6. Priorización P0 / P1 / P2 (esta campaña)

### P0 — desbloquea métricas multi-dominio (4–6 semanas)

| ID | Acción | Done-when |
|----|--------|-----------|
| P0-A | Shortlist 3 AU + 3 LATAM con URLs open | CSV + shortlist MD |
| P0-B | Materializar **2** packs (1 AU + 1 LATAM) R1–R4 | carpetas + meta.json |
| P0-C | Zero-shot eval + scorecard gap vs CLM | JSON en `outputs/ml_eval/` (no inventar) |
| P0-D | Rights sheet (license matrix) | 1 página en campaign doc |

### P1 — volumen y LOFO

| ID | Acción |
|----|--------|
| P1-A | +4 packs (total 6) con ≥3 escenas |
| P1-B | Weak-label MapBiomas/NAFI batch (scripted download) |
| P1-C | LOFO fold including 1 non-CLM fire |
| P1-D | Align meteo ERA5 opcional (no vender ROS) |

### P2 — nice / research

| ID | Acción |
|----|--------|
| P2-A | Chile/CONAF formal data request (si open insuficiente) |
| P2-B | Paper datasets (FLAME etc.) solo pretrain ablated |
| P2-C | Active learning: ranking tiles por uncertainty en dominio nuevo |

---

## 7. Scripts / eng (checklist de implementación)

No bloquear el plan en código inexistente; orden sugerido:

| # | Trabajo | Repo touch |
|---|---------|------------|
| 1 | Plantilla `docs/data_campaigns/LATAM_AU_CANDIDATES.csv` + shortlist | docs |
| 2 | `scripts/inventory_open_if_urls.py` (hash + type + dates from names) | scripts |
| 3 | STAC pull helper (S2 bbox/time → GeoTIFF) reutilizando ingest existente | scripts / open_if |
| 4 | FIRMS/MapBiomas download notes (manual first, script later) | docs |
| 5 | `eval_*` path que acepte pack foráneo sin tocar cal under FREEZE | ml eval |
| 6 | Scorecard schema `wfd_ml_domain_gap_v1` (CLM vs AU vs LATAM) | docs + json |

**Tests:** no inventar IoU; tests de inventario (CSV schema, path allowlist, no gate flip).

---

## 8. Relación con D0 España / B4 / B6

| Track | Rol |
|-------|-----|
| **D0 CLM** (`ML_LEAP_REQUEST_DATA`) | Sigue **P0 local**: Hellín cite + 2º IF ES |
| **Esta campaña LATAM/AU** | **P0 dominio**: reduce gap Tobarra/CLM-only |
| **B4 grade A ops** | Sigue siendo ops ES; open LATAM/AU **no** inventa grade A INFOCAM |
| **B6 FREEZE** | Se respeta hasta F5; open data no es excusa para KEEP thrash |
| **B5 O2 nacional ES** | No se cierra con AU/LATAM |

Ambos tracks en paralelo: **local anclas** + **global open packs**.

---

## 9. KPIs de éxito (medibles)

| KPI | Target honesto | Anti-target |
|-----|----------------|-------------|
| Eventos shortlist R1–R4 | ≥6 | 50 URLs sin bytes |
| Packs materializados | ≥2 en 30 días | “en Dropbox de alguien” |
| Zero-shot scorecard | 1 JSON reproducible | screenshot notebook |
| Domain gap table | CLM vs ≥1 non-CLM | un solo número “IoU subió” |
| FREEZE | intacto hasta F5 | retrain silencioso |
| Gates | GO_Q partial, fusion OFF | flip por euforia datos |

---

## 10. Calendario propuesto (humano + eng)

| Semana | Foco | Owner |
|--------|------|-------|
| **W0** | Este plan mergeado; CSV candidatos vacío → seed 10+10 | eng docs |
| **W1** | Shortlist 3+3; rights matrix | Steward + Alonso |
| **W2** | Pack #1 AU bytes + inventory | eng |
| **W3** | Pack #2 LATAM bytes + inventory | eng |
| **W4** | Zero-shot dual-pack eval + gap report | ML Lab |
| **W5–6** | +2 packs; decidir F5 lift | Alonso |
| **W7+** | Solo si F5: patches + v35 protocol | ML Lab |

---

## 11. PR shippable (cuando se ejecute)

| PR | Título | Scope |
|----|--------|-------|
| **PR-DA0** | `docs(data): LATAM+AU fire hunt plan + candidate CSV template` | este doc + CSV vacío/esquema |
| **PR-DA1** | `docs(data): shortlist 3 AU + 3 LATAM + rights matrix` | shortlist |
| **PR-DA2** | `data/scripts: open_if inventory + first AU/LATAM pack meta` | sin rasters pesados en git |
| **PR-DA3** | `eval(ml): domain-gap scorecard zero-shot` | números medidos |

Cada PR: `check_release_flags` PASS · no Hellín confirmed · no fusion ON.

---

## 12. Explicit non-claims

- No “tenemos dataset mundial listo para field GO”.  
- No perímetro AU/LATAM = O2 nacional España.  
- No IoU en scar MapBiomas = ROS táctico.  
- No retrain v35 bajo FREEZE sin F5.  
- No inventar Vp/ha de noticias.  
- No commitear multi-GB sin LFS/policy; raw gitignored.

---

## 13. Primera acción concreta (hoy)

1. Crear carpeta `docs/data_campaigns/`.  
2. Seed CSV con columnas §5 F0 (filas vacías o 5 ejemplos de **fuentes**, no de métricas inventadas).  
3. En paralelo mantener D0 ES (Hellín/Cardoso).  
4. No abrir retrain.

### Comandos de sanidad (siempre)

```bash
python scripts/check_release_flags.py
# expect: status=PASS · GO_Q partial · fusion OFF

# Cuando exista inventario:
# python scripts/inventory_real_if_material.py --source data/open_if/latam_au --output data/open_if/latam_au/inventories/file_inventory.csv
```

---

## 14. Owners

| Rol | Responsabilidad |
|-----|-----------------|
| **Alonso** | Rights, promote, lift FREEZE, priorización shortlist |
| **Data Steward** | Discover F0, licenses, inventory honesty |
| **ML Lab** | Zero-shot / LOFO / scorecards; train solo post-F5 |
| **eng B** | Scripts inventory/STAC/eval path; rails tests |
| **eng A** | Solo si UI muestra domain-gap (no en este plan) |

---

**Fin del plan.**

### F0 artifacts (shipped)

| Artefacto | Path |
|-----------|------|
| Candidates CSV (≥20) | [`docs/data_campaigns/LATAM_AU_CANDIDATES.csv`](data_campaigns/LATAM_AU_CANDIDATES.csv) |
| Shortlist 3 AU + 3 LATAM | [`docs/data_campaigns/LATAM_AU_SHORTLIST.md`](data_campaigns/LATAM_AU_SHORTLIST.md) |
| License matrix | [`docs/data_campaigns/LATAM_AU_LICENSE_MATRIX.md`](data_campaigns/LATAM_AU_LICENSE_MATRIX.md) |
| Agency/source catalog | [`docs/data_campaigns/LATAM_AU_SOURCE_CATALOG.json`](data_campaigns/LATAM_AU_SOURCE_CATALOG.json) |
| URL inventory script | `python scripts/inventory_open_if_urls.py --check` |
| URL inventory output | `docs/data_campaigns/LATAM_AU_URL_INVENTORY.csv` (generated) |
| F1 rights sheet | [`docs/data_campaigns/LATAM_AU_RIGHTS.md`](data_campaigns/LATAM_AU_RIGHTS.md) |
| F2 materialize | `python scripts/materialize_latam_au_emsr_packs.py` |
| F4 domain-gap | `python scripts/eval_latam_au_domain_gap.py` · schema `wfd_ml_domain_gap_v1` |
| P1–P2 status | [`docs/data_campaigns/LATAM_AU_CAMPAIGN_STATUS.md`](data_campaigns/LATAM_AU_CAMPAIGN_STATUS.md) |
| P1-B MapBiomas/NAFI | `scripts/download_mapbiomas_fogo.py` · `scripts/download_nafi_scars.py` |
| P1-C LOFO non-CLM | `scripts/build_latam_au_lofo_folds.py` |
| P1-D ERA5 optional | `scripts/align_latam_au_era5.py` |
| P2-A CONAF | [`docs/data_campaigns/CONAF_DATA_REQUEST_TEMPLATE.md`](data_campaigns/CONAF_DATA_REQUEST_TEMPLATE.md) |
| P2-B paper sets | [`docs/data_campaigns/LATAM_AU_PAPER_DATASETS.md`](data_campaigns/LATAM_AU_PAPER_DATASETS.md) |
| P2-C active learning | `scripts/rank_latam_au_active_learning.py` |
