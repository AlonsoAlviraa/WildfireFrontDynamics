# LATAM + AU campaign — status by ID

> **As of:** 2026-08-13  
> **Plan:** [`PLAN_ML_DATA_LATAM_AU_2026-08-13.md`](../PLAN_ML_DATA_LATAM_AU_2026-08-13.md)  
> **Rails:** GO_Q **partial** · field_ops fusion **ON** (human, unchanged) · FREEZE Tobarra KEEP reopen **false** · **no** transfer IoU invented

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
| **P2-A** | CONAF formal request | **done (template + send package)** | [`CONAF_DATA_REQUEST_TEMPLATE.md`](CONAF_DATA_REQUEST_TEMPLATE.md) · [`conaf_send/`](conaf_send/) status **`ready_to_send`** (not sent). Envío = humano. |
| **P2-B** | Paper datasets pretrain ablated | **done (note)** | [`LATAM_AU_PAPER_DATASETS.md`](LATAM_AU_PAPER_DATASETS.md) |
| **P2-C** | Active learning ranking on new domain | **done** | `outputs/ml_eval/latam_au_active_learning/ranking.json` (80 tiles, unique `y/x` tile_id). `model_iou=null`. |

## Residual backlog (eng 2026-08-13)

| # | Track | Eng | Humano |
|---|-------|-----|--------|
| 1 | CONAF envío OIRS | **`sent_gmail`** via `dispatch_conaf_oirs.py` → `consulta.oirs@conaf.cl` | Esperar respuesta OIRS / folio |
| 1b | Cesión → `lab_ok_conaf` | `record_conaf_cession.py` (exige evidencia escrita) · **lab_ok_conaf=false** | Cesión escrita CONAF |
| 2 | CEMS commercial rehost | gate + checklist + fail-closed script | legal si rehost producto |
| 3 | NDWS real (meteo/DEM/veg) | `fill_latam_au_ndws_covariates.py` + `--mode real_proxy` + `run_latam_au_complete_model_iou.py` · mean **complete_proxy** now excludes Δt<12h and static label copies (Perth out; Nacimiento 2.3 h out). See `outputs/ml_eval/latam_au_complete_iou/complete_proxy_model_iou.json`. **Not** transfer IoU | No transfer IoU sellado |
| 4 | Warp S2→CEMS | `warp_latam_au_s2_to_cems.py` · measured proxy after warp | review thr |

Detail: [`LATAM_AU_P0_P2_STATUS.md`](LATAM_AU_P0_P2_STATUS.md).

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

# residual backlog eng
python scripts/prepare_conaf_send_package.py
python scripts/check_cems_commercial_rehost.py
python scripts/check_cems_commercial_rehost.py --require-commercial-rehost  # expect exit 1
python scripts/adapt_latam_au_to_ndws_patches.py --event-id AU_EMSR500_PERTH --zero-shot-eval
python scripts/warp_latam_au_s2_to_cems.py --event-id AU_EMSR500_PERTH --event-id CL_EMSR647_NACIMIENTO
```

## Honesty

- CEMS / MapBiomas / NAFI = **proxy / L1–L2 weak**. Not O2 ES, not CONAF official, not `ml_strong`.  
- Successive CEMS / annual-window mask IoU ≠ transfer IoU. Domain-gap `extra_packs` also have `model_iou=null`.  
- L1 packs: STAC proxy is `blocked_no_audited_threshold` (same geographic CRS is **not** an audited NBR IoU). CEMS packs without warp stay `blocked_crs_mismatch`. If `WARP_PROVENANCE.json` + aligned TIFFs exist, `stac_proxy` is `measured` with the stored NBR proxy IoU (not model/transfer IoU).  
- S2 `pre`/`mid`/`post` tags are assigned by acquisition **civil day**. Same-day extras are `eo_s2_nbr_same_day_tile` (Perth 2021-02-20 is two tiles, not mid vs post).  
- Open-Meteo archive ≠ CDS ERA5-Land native.  
- No FREEZE lift, no v35, no GO_Q complete from this campaign.

## Verify (this pass)

`python scripts/check_release_flags.py` → **PASS** (GO_Q partial · fusion ON · KEEP reopen false).  
Campaign pytest: `tests/test_latam_au_campaign.py` · `test_latam_au_p1_p2.py` · `test_latam_au_product_e2e.py` · `test_inventory_open_if_urls.py` · `test_check_release_flags.py` (59 passed).
