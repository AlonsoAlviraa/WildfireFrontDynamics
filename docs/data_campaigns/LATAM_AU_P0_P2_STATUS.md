# LATAM + AU campaign — status by ID

> **As of:** 2026-08-16  
> **Plan:** [`PLAN_ML_DATA_LATAM_AU_2026-08-13.md`](../PLAN_ML_DATA_LATAM_AU_2026-08-13.md) · improve [`PLAN_LATAM_AU_CODE_IMPROVE_2026-08-16.md`](../PLAN_LATAM_AU_CODE_IMPROVE_2026-08-16.md)  
> **Rails:** GO_Q **partial** · field_ops fusion **ON** (human, unchanged) · FREEZE Tobarra KEEP reopen **false** · **no** transfer IoU invented · `lab_ok_conaf=false`

Inventory of what shipped before this P1–P2 pass, then P0–P2 IDs.

## Already done (pre-P1)

| Item | Evidence |
|------|----------|
| Shortlist 3 AU + 3 LATAM | [`LATAM_AU_SHORTLIST.md`](LATAM_AU_SHORTLIST.md) |
| Candidates ≥20 | [`LATAM_AU_CANDIDATES.csv`](LATAM_AU_CANDIDATES.csv) |
| Rights + license matrix | [`LATAM_AU_RIGHTS.md`](LATAM_AU_RIGHTS.md) · [`LATAM_AU_LICENSE_MATRIX.md`](LATAM_AU_LICENSE_MATRIX.md) |
| 2 EMSR packs (P0-B) | `data/open_if/latam_au/au/AU_EMSR500_PERTH/` · `.../cl/CL_EMSR647_NACIMIENTO/` |
| Domain-gap scorecard | [`LATAM_AU_DOMAIN_GAP_SCORECARD.json`](LATAM_AU_DOMAIN_GAP_SCORECARD.json) — AU/LATAM `model_iou=null`, zero-shot `not_run` |
| Product E2E | `outputs/open_if/latam_au_e2e/` — decide **HOLD** on bridged packs |
| Dual-analyst note | [`LATAM_AU_DUAL_ANALYST_REPORT.md`](LATAM_AU_DUAL_ANALYST_REPORT.md) |

## P0

| ID | Acción | Status | Artefacto / nota |
|----|--------|--------|------------------|
| **P0-A** | Shortlist 3 AU + 3 LATAM + URLs | **done** | CSV + shortlist MD |
| **P0-B** | Materializar 2 packs (1 AU + 1 LATAM) | **done** | EMSR500 Perth · EMSR647 Nacimiento; R6=1 |
| **P0-C** | Zero-shot + gap vs CLM | **done (honest)** | Scorecard `wfd_ml_domain_gap_v1` + P1 `extra_packs` geometry. **No** model IoU on foreign packs (schema block). CLM TEST IoU cited from sealed scorecard only. |
| **P0-D** | Rights sheet | **done** | `LATAM_AU_RIGHTS.md` (lab_ok provisional CEMS+S2; CONAF blocked) |

## P1

| ID | Acción | Status | Artefacto / nota |
|----|--------|--------|------------------|
| **P1-A** | +4 packs (total 6) ≥3 escenas | **done (this machine)** | `AU_EMSR408_NSW` (4 CEMS + 3 S2), `CL_EMSR715_VALPARAISO` (3 CEMS JSON + 3 S2), `BR_PANTANAL_2020_MAPBIOMAS` (3 annual + 3 distinct S2: 2020-07-15 / 08-07 / 08-31), `AU_NAFI_NT_SEASON_2023` (3 annual + 3 S2). Still `ml_weak`. `WEAK_MATERIALIZE_REPORT.json` lists both L1 packs. |
| **P1-B** | Weak-label MapBiomas/NAFI scripted download | **done** | Inventories under `data/open_if/latam_au/inventories/mapbiomas_inventory.csv` and `nafi_inventory.csv` (3/3 downloaded each). |
| **P1-C** | LOFO fold including 1 non-CLM fire | **done** | `outputs/ml_eval/latam_au_lofo/lofo_non_clm_v1.json` held-out `AU_EMSR408_NSW`. `eval_status=blocked_incompatible_schema`, `model_iou=null`. |
| **P1-D** | Align meteo ERA5 opcional | **done** | Open-Meteo ERA5 archive fetch **ok** for 6 packs (`era5_align_report.json`). Not CDS-native. **Not ROS.** |

## P2

| ID | Acción | Status | Artefacto / nota |
|----|--------|--------|------------------|
| **P2-A** | CONAF formal request | **done (template)** | [`CONAF_DATA_REQUEST_TEMPLATE.md`](CONAF_DATA_REQUEST_TEMPLATE.md). Envío = humano. |
| **P2-B** | Paper datasets pretrain ablated | **done (note)** | [`LATAM_AU_PAPER_DATASETS.md`](LATAM_AU_PAPER_DATASETS.md) |
| **P2-C** | Active learning ranking on new domain | **done** | `outputs/ml_eval/latam_au_active_learning/ranking.json` (80 tiles, unique `y/x` tile_id). `model_iou=null`. |

## Commands

```bash
python scripts/check_release_flags.py
# expect: status=PASS · GO_Q partial · fusion ON · KEEP reopen false

python scripts/materialize_latam_au_emsr_packs.py --only AU_EMSR408_NSW --only CL_EMSR715_VALPARAISO
python scripts/download_mapbiomas_fogo.py
python scripts/download_nafi_scars.py
python scripts/materialize_latam_au_weak_packs.py
python scripts/build_latam_au_lofo_folds.py --held-out AU_EMSR408_NSW
python scripts/align_latam_au_era5.py
python scripts/rank_latam_au_active_learning.py
python scripts/eval_latam_au_domain_gap.py
```

## Honesty

- CEMS / MapBiomas / NAFI = **proxy / L1–L2 weak**. Not O2 ES, not CONAF official, not `ml_strong`.  
- Successive CEMS / annual-window mask IoU ≠ transfer IoU. Domain-gap `extra_packs` also have `model_iou=null`.  
- L1 packs: STAC proxy is `blocked_no_audited_threshold` (same geographic CRS is **not** an audited NBR IoU). CEMS packs without warp stay `blocked_crs_mismatch`. If `WARP_PROVENANCE.json` + aligned TIFFs exist, `stac_proxy` is `measured` with the stored NBR proxy IoU (not model/transfer IoU).  
- S2 `pre`/`mid`/`post` tags are assigned by acquisition **civil day**. Same-day extras are `eo_s2_nbr_same_day_tile` (Perth 2021-02-20 is two tiles, not mid vs post).  
- Open-Meteo archive ≠ CDS ERA5-Land native.  
- No FREEZE lift, no v35, no GO_Q complete from this campaign.

## Residual backlog (eng ship 2026-08-13)

| # | Item | Eng status | Artefacto | Humano residual |
|---|------|------------|-----------|-----------------|
| **1** | Solicitud formal CONAF (P2-A) | Plantilla pública preparada; correspondencia externa excluida del repositorio | [`CONAF_DATA_REQUEST_TEMPLATE.md`](CONAF_DATA_REQUEST_TEMPLATE.md) | Esperar autorización escrita antes de usar o redistribuir datos |
| **1b** | Cesión escrita CONAF → `lab_ok_conaf` | **tooling shipped**; `lab_ok_conaf=false` | `scripts/record_conaf_cession.py` | CONAF debe emitir cesión escrita; no se inventa |
| **2** | OK comercial CEMS si rehost producto | ver gate firmado / checklist | [`CEMS_COMMERCIAL_REHOST_CHECKLIST.md`](CEMS_COMMERCIAL_REHOST_CHECKLIST.md) · `scripts/check_cems_commercial_rehost.py` | Legal si se rehostea en producto |
| **3** | Canales NDWS reales (meteo/DEM/veg) + IoU completo | **real_proxy_fill** · **n_ready=4**. Usable-pair mean **~0.737** (Nac 0.673 + NSW 0.802). FEP/GRA ≠ growth (EMSR715 `n_pairs_used=0`; old 0.088 not in mean). Pre-fire NBR veg. Model Δ vs copy is **negative**. **Not** transfer | `scripts/fill_latam_au_ndws_covariates.py --all` · `inventories/ndws_covariates_report.json` · `scripts/run_latam_au_complete_model_iou.py` | No es transfer IoU sellado ni GO_Q complete; `--all` refuses silent DEM fallback unless `--allow-dem-fallback` |
| **4** | Warp S2→CRS CEMS (proxy NBR auditado) | **measured** on 4 EMSR packs (proxy IoU only) | `scripts/warp_latam_au_s2_to_cems.py` · `outputs/ml_eval/latam_au_warp/` | None eng; review thr if needed; **not** model/transfer IoU |

## Code-improve pass (2026-08-16, PR-A–H)

| PR | Status | Honest note |
|----|--------|-------------|
| **A** Warp hygiene | shipped | S2 sources only `pack/eo/*.tif`; dest `{stem}_to_cems.tif`; GC `*_to_cems_to_cems*`; re-run is idempotent |
| **B** Domain-gap warp | shipped | If `WARP_PROVENANCE.json` + aligned exist → `stac_proxy.status=measured` with stored IoU. Else `blocked_crs_mismatch`. Not model IoU |
| **C** Temporal pairs | shipped | Mean excludes `too_short_delta` (<12 h) and `static_label_copy` (label IoU>0.98). Nacimiento 2.3 h out. Perth near-copy out. EMSR408/715 in default runner when packs+weights exist. `complete_proxy_*` only |
| **D** NBR post/threshold | shipped | Post = S2 datetime > last label; held-out sweep `{-0.2…0}` then freeze. Same civil-day tiles are not mid/post. Low IoU gets `s2_not_post` / `cloud` / `threshold_unusable` |
| **E** Covariates | shipped | Meteo sampled at label timestamp; `meteo_spatial=constant_point`. `--all` refuses silent `fallback_constant` unless `--allow-dem-fallback` |
| **F** BO + MX specs | shipped | Packs materialized: `data/open_if/latam_au/bo/BO_EMSR765/` and `.../mx/MX_EMSR717/` with hashed `meta.json` (3 Rapid JSON labels each). Candidates CSV rows stay `*_2024` with R6=0 (id ≠ pack event_id). Still `ml_weak` L2 proxy |
| **G** Annual L1 | shipped | Weak packs adapt as `annual_scar_only`. Next-mask eval → `blocked_annual_not_event`. LOFO annual uses the same code |
| **H** CONAF ingest stub | shipped | `scripts/ingest_conaf_perimeters.py`. Pack `CL_CONAF_*` `ml_weak`, `lab_ok_conaf=false` unless evidence file passes `record_conaf_cession` rules. Does **not** flip product `send_status.json` |

Not claimed: transfer IoU, sealed U1 TEST, GO_Q complete, `lab_ok_conaf` product rail, FREEZE lift.

## Verify (this pass)

`python scripts/check_release_flags.py` → **PASS** (GO_Q partial · fusion ON · KEEP reopen false).  
Campaign pytest: `tests/test_latam_au_campaign.py` · `test_latam_au_p1_p2.py` · `test_latam_au_product_e2e.py` · `test_inventory_open_if_urls.py` · `test_check_release_flags.py` · `test_latam_au_residual_backlog.py`.
