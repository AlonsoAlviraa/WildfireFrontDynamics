# LATAM + AU dual-analyst report — EMSR500 Perth and EMSR647 Nacimiento

> **As of (UTC):** 2026-08-13T09:22:46Z  
> **Roles:** senior ML data analyst · decision-product analyst  
> **Campaign plan:** [`docs/PLAN_ML_DATA_LATAM_AU_2026-08-13.md`](../PLAN_ML_DATA_LATAM_AU_2026-08-13.md)  
> **F1 rights:** [`LATAM_AU_RIGHTS.md`](LATAM_AU_RIGHTS.md)  
> **Domain-gap scorecard:** [`LATAM_AU_DOMAIN_GAP_SCORECARD.json`](LATAM_AU_DOMAIN_GAP_SCORECARD.json)  
> **Product E2E:** `outputs/open_if/latam_au_e2e/product_e2e_report.json`  
> **Product:** `clm_ensemble_v34` (lab) · **GO_Q remains `partial`** · **model IoU on these packs remains `null`**

This note is a measured inventory and decide-path review of the two P0-B packs. It does **not** invent transfer IoU, ROS/Vp, GO_Q complete, FREEZE lift, O2 España, CONAF official, or `ml_strong`.

---

## 1. Executive summary

Both campaign packs exist on disk, pass the open-data product bridge, and produce a **valid `HOLD`** on the decide path. They are **not** ready to train or zero-shot `clm_ensemble_v34`.

| Question | Measured answer |
|----------|-----------------|
| Are the two packs materialized (R1–R6 for these IDs)? | **Yes.** 3 CEMS label GeoTIFFs + 3 S2 NBR windows each; hashes in `meta.json` and `inventories/file_inventory.csv`. |
| Product decide outcome? | **HOLD / MEDIUM** for both. Open CEMS source available; ops and CLM ensemble missing. `require_ops_for_go=true`. |
| Transfer / zero-shot model IoU? | **`null`.** Eval status `blocked_incompatible_schema`. Zero-shot `not_run` (not attempted). |
| GO_Q? | **`partial`** (stamp + `check_release_flags` PASS). Not complete. |
| Train `clm_ensemble_v34` from this export? | **No.** 135 + 144 CEMS mask patches, contract `cems_label_mask_patches_v1`, `compatible_with_clm_ensemble_v34=false`, `train_ready_status=inventory_only`. |
| Lift FREEZE / retrain v35? | **No.** F5 criteria not met (no `ml_strong`, no measured zero-shot gap). |
| Field dispatch / ops ROS? | **No.** CEMS proxy only. V&V sidecars are `eng_stub`. `system_reliability_pass=false`. |

**One-line verdict (ML):** useful **out-of-Spain L2 proxy inventory**; schema-blocked for the sealed UNet.

**One-line verdict (product):** open-if monitoring path works; both events stay **HOLD** and must not be sold as field GO.

**Scale contrast (CEMS rasterized observedEvent, not official cadastre):** Perth max **10,678.61 ha** over ~7.2 days with almost no product growth after first monitoring; Nacimiento max **99,976.67 ha** over ~45.5 hours with large successive product growth. Nacimiento is ~9.4× Perth by max CEMS area.

---

## 2. Measurement provenance (this session)

Re-ran after the 00:29Z bridge so numbers in this note match the live artifacts.

| Step | Command / source | Result | UTC |
|------|------------------|--------|-----|
| Rails | `python scripts/check_release_flags.py` | `status=PASS` · GO_Q `partial` · fusion ON · Tobarra KEEP reopen false | this session |
| Product E2E | `python scripts/run_latam_au_product_e2e.py --update-domain-gap` | `ok=true`, 2/2 packs, both `HOLD` | `2026-08-13T09:22:41.610706Z` |
| Domain-gap | `python scripts/eval_latam_au_domain_gap.py` | AU/LATAM `blocked_incompatible_schema`; `model_iou=null`; zero-shot `not_run` | `2026-08-13T09:22:46.787892Z` |
| Patch stats | Manifests under `artifacts/latam_au_ml_export/*/ml/manifest.json` | 135 + 144 patches; pos_frac tables below | export `2026-08-13T00:23:05Z` |
| Rights | [`LATAM_AU_RIGHTS.md`](LATAM_AU_RIGHTS.md) | CEMS + S2 lab_ok **provisional**; CONAF **blocked**; commercial-product OK **open** | 2026-08-13 |

Sealed CLM TEST IoU cited below is **not** recomputed here. It is copied from `docs/ML_PRODUCT_SCORECARD.json` via the domain-gap script (`clm_holdout_test_seed42_v1`, n=200).

---

## 3. Rails (unchanged by this campaign)

| Rail | Value | Evidence |
|------|-------|----------|
| GO_Q | `partial` | stamp + flags + E2E rails |
| field_ops ML fusion | **ON** (existing human promote; not flipped by CEMS) | `docs/ML_PRODUCT_GO_STATUS.json` |
| FREEZE / Tobarra KEEP reopen | intact / `false` | stamp `tobarra_keep_reopen=false` |
| IoU ≠ ROS | true | domain-gap rails |
| Retrain from these packs | **not done** | `no_retrain=true`; train inventory `would_feed_train=false` |
| O2 national ES / CONAF / grade A | **not claimed** | pack `not_*` flags + scorecards |

Open CEMS/S2 does **not** close GO_Q, does **not** lift FREEZE, and does **not** make CEMS a national cadastre.

---

## 4. Data inventory

### 4.1 Pack identity

| Field | `AU_EMSR500_PERTH` | `CL_EMSR647_NACIMIENTO` |
|-------|--------------------|-------------------------|
| Activation / AOI | EMSR500 AOI01 Perth | EMSR647 AOI01 Nacimiento |
| Year / country | 2021 / AU | 2023 / CL |
| Source pack | `data/open_if/latam_au/au/AU_EMSR500_PERTH` | `data/open_if/latam_au/cl/CL_EMSR647_NACIMIENTO` |
| Open-if pack | `outputs/open_if/emsr500_perth` | `outputs/open_if/emsr647_nacimiento` |
| Class / label | `ml_weak` / `L2_proxy` | `ml_weak` / `L2_proxy` |
| Licence | `copernicus_ems_reg_2021_696_open` | same |
| lab_ok | yes (provisional) | yes (provisional) |
| Pack CRS (meta) | EPSG:32750 | EPSG:32718 |
| Pack GSD (meta) | 30.0 m | 30.0 m (label rasters record **37.763671875 m**) |
| `geotiff_origin` | `rasterized_cems_vector+stac_s2_nbr` | same |
| Native CEMS GeoTIFF listed on portal | **false** | **false** |
| bbox WGS84 | 116.026, −31.793 → 116.333, −31.700 | −73.126, −37.751 → −72.588, −37.071 |
| Built (pack `meta.json`) | 2026-08-12T23:59:59Z | 2026-08-13T00:00:24Z |
| Bridge built | 2026-08-13T00:29:55Z | 2026-08-13T00:29:56Z |
| R1–R6 (shortlist) | 6/6 | 6/6 |
| Portal | [EMSR500](https://mapping.emergency.copernicus.eu/activations/EMSR500/) | [EMSR647](https://mapping.emergency.copernicus.eu/activations/EMSR647/) |

EMSR647 activation has 7 AOIs / 38 products; **this pack is AOI01 only**. Other Chile AOIs are out of scope.

### 4.2 On-disk file inventory

Source: `data/open_if/latam_au/inventories/file_inventory.csv` (29 rows).

| Pack | Files | Bytes | MiB |
|------|------:|------:|----:|
| AU Perth | 14 | 98,880,798 | 94.30 |
| CL Nacimiento | 14 | 32,089,359 | 30.60 |
| Root (`MATERIALIZE_REPORT.json`) | 1 | 590 | 0.00 |
| **Total inventoried** | **29** | **130,970,747** | **124.90** |

Most of the AU byte count is the grading vector ZIP (73,388,503 B). Rasters themselves are small (CEMS labels ~7.5–40 KB; S2 NBR windows 55–242 KB).

Per pack layout (same shape):

| Slot | AU | CL |
|------|----|----|
| Label GeoTIFF | 3 | 3 |
| Label GeoJSON | 3 | 3 |
| S2 NBR GeoTIFF | 3 | 3 |
| Raw CEMS ZIP | 3 | 3 |
| `meta.json` + README | 2 | 2 |

### 4.3 CEMS products used (not the full activation)

| Pack | Product | Kind | Delivery UTC | Source ZIP | Label SHA-256 (12) |
|------|---------|------|--------------|------------|--------------------|
| Perth | DEL_PRODUCT | delineation | 2021-02-05T20:32:25Z | `EMSR500_AOI01_DEL_PRODUCT_r1_RTP01_v1_vector.zip` | `08fe9d0fc903` |
| Perth | DEL_MONIT01 | delineation_monitoring | 2021-02-11T17:03:24Z | `EMSR500_AOI01_DEL_MONIT01_r1_RTP01_v1_vector.zip` | `46474f5ca872` |
| Perth | GRA_PRODUCT | grading | 2021-02-13T02:23:04Z | `EMSR500_AOI01_GRA_PRODUCT_r1_RTP01_v1_vector.zip` | `46474f5ca872` |
| Nacimiento | DEL_PRODUCT | delineation | 2023-02-13T23:56:34Z | `EMSR647_AOI01_DEL_PRODUCT_r1_RTP01_v2_vector.zip` | `a1a07d5ad5c4` |
| Nacimiento | DEL_MONIT05 | delineation_monitoring | 2023-02-14T02:15:43Z | `EMSR647_AOI01_DEL_MONIT05_r1_RTP01_v1_vector.zip` | `8b14b5afd8d1` |
| Nacimiento | DEL_MONIT06 | delineation_monitoring | 2023-02-15T21:24:10Z | `EMSR647_AOI01_DEL_MONIT06_r1_RTP01_v1_vector.zip` | `f5f8547d6efa` |

**Data-quality finding (Perth):** GRA_PRODUCT and DEL_MONIT01 share the **same** label raster SHA-256, byte size (7,582), width/height, positive pixel count, and area. Successive CEMS mask IoU 1→2 is therefore **1.0**. That is **label identity**, not model performance, and it means the third timeline step does **not** add a new burned-area geometry.

### 4.4 Sentinel-2 NBR windows (inputs only)

CRS for all six windows: **EPSG:4326** (not the CEMS UTM). Domain-gap therefore records `stac_proxy.status=blocked_crs_mismatch` and `nbr_vs_cems_iou=null`.

| Pack | Role in meta | STAC item | Datetime UTC | Cloud cover | Bytes | Hours vs first CEMS | Hours vs last CEMS |
|------|--------------|-----------|--------------|------------:|------:|--------------------:|-------------------:|
| Perth | `eo_s2_nbr_pre` | `S2B_50HMK_20210121_1_L2A` | 2021-01-21T02:26:36Z | 0.000042 | 241,149 | −378.1 | −551.9 |
| Perth | `eo_s2_nbr_mid` | `S2B_50HMK_20210220_1_L2A` | 2021-02-20T02:26:34Z | 0.000003 | 241,976 | +341.9 | +168.1 |
| Perth | `eo_s2_nbr_post` | `S2B_50JML_20210220_1_L2A` | 2021-02-20T02:26:20Z | 0.002074 | 55,187 | +341.9 | +168.1 |
| Nacimiento | `eo_s2_nbr_pre` | `S2A_18HYD_20230128_0_L2A` | 2023-01-28T14:53:19Z | 0.000119 | 73,122 | −393.1 | −438.5 |
| Nacimiento | `eo_s2_nbr_mid` | `S2B_18HYD_20230304_0_L2A` | 2023-03-04T14:53:23Z | 0.000292 | 74,211 | +446.9 | +401.5 |
| Nacimiento | `eo_s2_nbr_post` | `S2B_18HYD_20230222_0_L2A` | 2023-02-22T14:53:21Z | 0.000431 | 74,267 | +206.9 | +161.5 |

**Pack-hygiene findings:**

1. **Nacimiento role labels are temporally inverted.** `eo_s2_nbr_post` (22 Feb) is **before** `eo_s2_nbr_mid` (4 Mar). Treat roles as tags, not chronology.
2. **Perth mid/post are the same day, different tiles** (`50HMK` vs `50JML`). Post is a smaller window (55 KB vs 242 KB). Neither is contemporaneous with CEMS (last CEMS 13 Feb; S2 20 Feb).
3. **No S2 scene falls inside the CEMS delivery window** on either pack. These are pre/post context, not aligned multi-date labels.

---

## 5. Areas and timelines

Areas are **rasterized CEMS `observedEvent` polygons** stored in pack `meta.json` / domain-gap `area_ha_by_product`. They are **proxy hectares**, not O2 / CONAF / INFOCAM. Successive differences are **product-to-product area deltas**, **not** ROS and **not** Vp.

### 5.1 Perth — EMSR500 AOI01

Label grid: 1012 × 378, GSD 30.0 m, EPSG:32750.

| Step | Product | Delivery UTC | Area (ha) | Positive pixels | Δt (h) | Δ area (ha) | Δ area (%) |
|------|---------|--------------|----------:|----------------:|-------:|------------:|-----------:|
| 0 | DEL_PRODUCT | 2021-02-05T20:32:25Z | 10,565.960281211275 | 119,954 | — | — | — |
| 1 | DEL_MONIT01 | 2021-02-11T17:03:24Z | 10,678.61432716903 | 121,180 | 140.516 | +112.654 | +1.066 |
| 2 | GRA_PRODUCT | 2021-02-13T02:23:04Z | 10,678.61432716903 | 121,180 | 33.328 | 0.000 | 0.000 |

| Summary | Value |
|---------|-------|
| Min / max area | 10,565.96 / **10,678.61 ha** |
| Span (first→last CEMS) | 173.844 h (~7.24 d) |
| Net product growth | +112.65 ha |
| Successive CEMS **mask** IoU (label vs label) | 0.989882818947021 then **1.0** |
| Mean successive mask IoU | 0.9949414094735105 |

Interpretation: the Perth stack is a **near-static scar**. Almost all geometry is already in the first delineation. Step 2 is a duplicate raster of step 1. Useful as a compact AU transfer **target**, weak as a dynamics / growth sequence.

### 5.2 Nacimiento — EMSR647 AOI01

Label grid: 1261 × 2048, GSD **37.763671875 m**, EPSG:32718. Pack-level `gsd_m=30.0` does **not** match the written rasters.

| Step | Product | Delivery UTC | Area (ha) | Positive pixels | Δt (h) | Δ area (ha) | Δ area (%) |
|------|---------|--------------|----------:|----------------:|-------:|------------:|-----------:|
| 0 | DEL_PRODUCT | 2023-02-13T23:56:34Z | 80,902.07010329801 | 579,391 | — | — | — |
| 1 | DEL_MONIT05 | 2023-02-14T02:15:43Z | 94,568.5775717084 | 674,344 | 2.319 | +13,666.51 | +16.893 |
| 2 | DEL_MONIT06 | 2023-02-15T21:24:10Z | 99,976.67025107979 | 711,406 | 43.141 | +5,408.09 | +5.719 |

| Summary | Value |
|---------|-------|
| Min / max area | 80,902.07 / **99,976.67 ha** |
| Span (first→last CEMS) | 45.46 h (~1.89 d) |
| Net product growth | +19,074.60 ha |
| Successive CEMS **mask** IoU (label vs label) | 0.8591920444164995 then 0.9478757857568567 |
| Mean successive mask IoU | 0.9035339150866781 |

Interpretation: Nacimiento is a **growing multi-product delineation** at campaign scale (~100 kha). The +16.9% jump in **2.3 hours** between DEL and MONIT05 is a **mapping-product update**, not a measured front speed. Do not convert these deltas into ROS.

### 5.3 Side-by-side

| Metric | Perth | Nacimiento |
|--------|------:|-----------:|
| Max CEMS area (ha) | 10,678.61 | 99,976.67 |
| Area ratio vs Perth | 1.00 | 9.36 |
| Timeline steps | 3 | 3 |
| Distinct label rasters (by SHA-256) | **2** (GRA = MONIT01) | **3** |
| CEMS span | 173.8 h | 45.5 h |
| Mean label-vs-label mask IoU | 0.9949 | 0.9035 |
| Dynamics utility | low (static scar) | higher (growing stack) |
| Model IoU | **null** | **null** |

**Do not** put successive mask IoU in a transfer-performance table. Domain-gap `gap_table` is explicit:

| Split | Model IoU | n | Status |
|-------|-----------|--:|--------|
| CLM sealed TEST | 0.8568865373678947 | 200 | sealed (`docs/ML_PRODUCT_SCORECARD.json`) |
| AU Perth | **null** | 0 | `blocked_incompatible_schema` |
| LATAM Nacimiento | **null** | 0 | `blocked_incompatible_schema` |

CLM selective IoU @80 = 0.903428533834858; ECE patch conf = 0.15280955026564416. Those are **CLM holdout** numbers only.

---

## 6. ML readiness

### 6.1 Contract mismatch (why zero-shot was refused)

| Side | Contract |
|------|----------|
| `clm_ensemble_v34` | NDWS **17-channel** sequences, legacy17 / `holdout_v1` NPZ, typically `(1, 17, 64, 64)` |
| These packs | 1-band rasterized CEMS burned mask ± windowed S2 **NBR** (EPSG:4326) |
| Export | `cems_label_mask_patches_v1` — uint8 binary mask tiles |

Running the UNet on these rasters would **invent** IoU. Domain-gap therefore set `zero_shot.attempted=false`, `zero_shot.status=not_run`, `model_iou=null`.

S2 NBR vs CEMS proxy IoU is also **null**: `blocked_crs_mismatch` (no audited warp/resample in this F4 pass).

### 6.2 Export inventory (present, not train-ready)

Path: `artifacts/latam_au_ml_export/`. Summary `2026-08-13T00:23:05.539560Z`. `would_feed_train=false`.

| Pack | n_label_tif | n_patches | patch size | Train-ready | Compatible v34 |
|------|------------:|----------:|------------|-------------|----------------|
| Perth | 3 | **135** | 64 | `inventory_only` | **false** |
| Nacimiento | 3 | **144** | 64 | `inventory_only` | **false** |
| **Total** | 6 | **279** | 64 | inventory only | **false** |

Per-source counts: Perth 45 + 45 + 45; Nacimiento 48 + 48 + 48. Perth’s last two sources share geometry (see §4.3), so many MONIT01/GRA tiles are duplicates.

### 6.3 Patch positive-fraction stats (label occupancy, not IoU)

Computed from export manifests (`pos_frac` per 64×64 tile). These describe **how burned the tile is**, not model skill.

| Stat | Perth (n=135) | Nacimiento (n=144) |
|------|--------------:|-------------------:|
| min | 0.012451171875 | 0.03076171875 |
| p25 | 0.326416015625 | 0.437255859375 |
| median | 0.639404296875 | 0.801025390625 |
| mean | 0.6182092737268519 | 0.6854434543185763 |
| p75 | 0.95703125 | 1.0 |
| max | 1.0 | 1.0 |
| n with pos_frac ≥ 0.999 | 21 | 46 |
| n with pos_frac < 0.05 | 7 | 6 |
| n in [0.05, 0.95) | 92 | 81 |

Per label source (mean pos_frac):

| Source | n | mean pos_frac |
|--------|--:|--------------:|
| Perth DEL 20210205 | 45 | 0.613775 |
| Perth MONIT01 20210211 | 45 | 0.620426 |
| Perth GRA 20210213 | 45 | 0.620426 |
| Nacimiento DEL 20230213 | 48 | 0.692312 |
| Nacimiento MONIT05 20230214 | 48 | 0.689163 |
| Nacimiento MONIT06 20230215 | 48 | 0.674856 |

Nacimiento tiles are more fully burned (median 0.80, 46 saturated). Perth is more mixed-edge (median 0.64, 92 edge tiles). Both exports are **mask-only** — no 17-ch covariates, no aligned S2 stack, no temporal sequence tensor.

### 6.4 What this is / is not for ML

| Ready for | Verdict |
|-----------|---------|
| Weak-label inventory / hash audit | **Yes** |
| Geometry / area / successive-mask diagnostics | **Yes** (measured above) |
| Pretrain after an audited warp + multi-band rebuild | Possible later; not this export |
| Zero-shot `clm_ensemble_v34` | **Blocked** |
| LOFO multi-continent fold | **Not yet** (need NDWS-compatible tensors or a new input head) |
| Promote to `ml_strong` | **No** (no aligned multi-date EO at label GSD/CRS) |
| FREEZE lift / v35 | **No** |

---

## 7. Decision-product analysis

### 7.1 Measured decide path

Protocol `latam_au_product_e2e_v1`, `use_ml_v34=false`, `require_ops_for_go=true`. Both packs `ok=true`.

| Field | Perth | Nacimiento |
|-------|-------|------------|
| Decision | **HOLD** | **HOLD** |
| `confidence_pred` | 0.7200000000000001 | 0.7200000000000001 |
| Label | MEDIUM | MEDIUM |
| Decide latency (ms) | 10.728 | 3.534 |
| Wall (ms) | 19.25 | 10.312 |
| Policy | `default` | `default` |
| `open_source_available` | true | true |
| `system_reliability_pass` | **false** | **false** |
| `vp_invented` | false | false |
| Timeline steps seen by product | 3 | 3 |
| Max area into decide (ha) | 10,678.61 | 99,976.67 |

Reasons (identical on both cards):

- `missing:ml_clm_ensemble`
- `missing:ops`
- `open_cems_perimeter:conf=0.720:w=0.35`
- `policy:default`
- `open_only_monitoring`

The 0.72 figure is the **open CEMS perimeter source weight**, not a model posterior and not a field-validated confidence.

Open scorecards (`scorecard_pista_b.json`):

| Gate | Perth | Nacimiento |
|------|-------|------------|
| `status` | `GO_OPEN_DATA_PACK` | `GO_OPEN_DATA_PACK` |
| `decision_open` | HOLD | HOLD |
| `O2_cems_delineation` | GO | GO |
| `O2_national_official` | `NO_GO_CEMS_PROXY` | `NO_GO_CEMS_PROXY` |
| LWIR / heligraphics | false | false |

`GO_OPEN_DATA_PACK` means **the bridge is ready**, not field GO and not GO_Q complete.

### 7.2 Sidecars

| Sidecar | Status |
|---------|--------|
| `decision_log.jsonl` | Present; latest entries HOLD, rails `GO_Q=partial` |
| `vv_scorecard.json` | Schema `wfd_vv_scorecard_stub_v1`, `eng_stub=true` |
| Stub field_iou / field_ros / field_grade | **null** (intentional) |

V&V is an engineering stub. It must not be quoted as a field scorecard.

### 7.3 Product decision (analyst)

| Option | Perth | Nacimiento |
|--------|-------|------------|
| GO / dispatch | **Reject.** Missing ops + ML; reliability fail; CEMS proxy. | Same. |
| ABSTAIN | Allowed by product, but not what decide emitted. | Same. |
| **HOLD** | **Accept.** Correct for open-only monitoring. | **Accept.** Same, at ~100 kha campaign scale. |
| Promote to field_ops fusion input | **No.** Fusion ON is a **stamp rail**, not permission to feed CEMS-AU/CL as ops. | Same. |
| Show as “validated burned area” in UI | **No.** Label as CEMS Rapid Mapping proxy. | Same; also not CONAF. |

**Product outcome:** keep both events in the **open monitoring / research** lane. HOLD is a successful E2E result, not a failed fire call.

Confidence 0.72 / MEDIUM is **not** evidence that either fire is 72% contained, 72% mapped, or 72% model-certain.

---

## 8. Residual gaps

| ID | Gap | Why it matters | Blocks |
|----|-----|----------------|--------|
| G1 | Input schema: 1-band CEMS mask vs NDWS 17-ch | Cannot evaluate or train v34 without inventing IoU | P0-C zero-shot, F4 model gap table, F5 |
| G2 | S2 NBR in EPSG:4326 vs CEMS UTM | No honest dNBR / NBR-vs-mask IoU | STAC proxy metric |
| G3 | No S2 window inside CEMS delivery dates | EO is context, not contemporaneous label pair | `ml_strong` |
| G4 | Perth GRA raster == MONIT01 | Timeline step 3 is not new geometry | Dynamics / 3-scene claim for that pair |
| G5 | Nacimiento `mid`/`post` role tags reversed in time | Easy to mis-order a dNBR | **Fixed 2026-08-13:** `assign_s2_roles_by_datetime` remaps tags by acquisition time (filenames/hashes unchanged). Treat remaining same-day Perth pair as two tiles, not mid vs post. |
| G6 | Nacimiento raster GSD 37.76 m vs pack meta 30.0 m | Contract / area audit risk if someone uses pack GSD | GeoTIFF contract alignment |
| G7 | Export has no covariates (only mask tiles) | Cannot rebuild NDWS sequences from this zip | Train inventory |
| G8 | V&V sidecar is stub; reliability fail | No field metric to quote | GO_Q, dispatch |
| G9 | Commercial-product CEMS OK still human-open | Lab provisional ≠ product ship | Paid redistribution |
| G10 | CONAF / agency SHP blocked | No official CL perimeter to score CEMS against | Grade-A LATAM label |
| G11 | Only 2 materialized packs; shortlist others R6=0 | Cannot LOFO a continent fold yet | **Superseded P1-A:** 6 packs on disk (`AU_EMSR408_NSW`, `CL_EMSR715_VALPARAISO`, `BR_PANTANAL_2020_MAPBIOMAS`, `AU_NAFI_NT_SEASON_2023` + P0). LOFO fold exists; eval still `blocked_incompatible_schema`. |
| G12 | EMSR647 other AOIs not packed | Nacimiento ≠ full Chile 2023 complex | Completeness of CL event |

---

## 9. Next actions

Ordered. Do **not** retrain.

| Priority | Action | Owner | Done-when |
|----------|--------|-------|-----------|
| **Now** | Treat this report + refreshed scorecard as the F4 **honesty** deliverable. Leave `iou_au` / `iou_latam` **null**. | ML Lab / Steward | This file + `LATAM_AU_DOMAIN_GAP_SCORECARD.json` |
| **P0** | Audited **warp/resample**: S2 NBR → each pack’s CEMS CRS/GSD. Then re-run domain-gap STAC proxy. Still **no** UNet IoU until tensors match. | eng B | `stac_proxy.status` ≠ `blocked_crs_mismatch`; metric still named `nbr_vs_cems_iou` |
| **P0** | Fix Nacimiento EO role chronology (swap mid/post tags or rename by datetime). Fix pack-level `gsd_m` to 37.763671875 **or** re-raster at 30 m and re-hash. | eng B | **Roles:** remapped by datetime. Residual: pack-level `gsd_m` vs raster GSD. |
| **P0** | Document Perth GRA=MONIT01 in pack README (already measured). Do not advertise 3 distinct scars. | Data Steward | README note |
| **P1** | If a transfer number is required: build NDWS-compatible sequences (or a new eval head) **then** zero-shot. Refuse any notebook that feeds 1-band masks to v34. | ML Lab | `zero_shot.status` in {`run`,`blocked`} with `model_iou` measured **or** still null with a new honest reason |
| **P1** | Materialize next shortlist packs (`AU_EMSR408_NSW`, `CL_EMSR715_VALPARAISO`) to grow R6=1 beyond these two. | eng B | **Done P1-A** (+ MapBiomas/NAFI L1). Still `ml_weak`. |
| **P1** | Alonso / legal light: commercial-use OK on CEMS-derived packs (checkbox still open on the rights sheet). | Alonso | F1 checklist commercial box |
| **P2** | CONAF written cession only if CEMS is not enough for a CL official comparison. | Alonso | `lab_ok` on CONAF row |
| **Never from this pack** | Flip GO_Q, lift FREEZE, reopen Tobarra KEEP, invent ROS from Δha/Δt, or quote successive mask IoU as transfer IoU. | all | rails stay as stamped |

Suggested commands (already used this session):

```powershell
$env:PYTHONPATH = "."
python scripts/check_release_flags.py
python scripts/run_latam_au_product_e2e.py --update-domain-gap
python scripts/eval_latam_au_domain_gap.py
```

---

## 10. Explicit non-claims

- **Not** model IoU on AU or LATAM (`null`, n=0).
- **Not** GO_Q complete (remains `partial`).
- **Not** FREEZE lift and **not** v35 retrain.
- **Not** ROS / Vp; CEMS Δha/Δt is not a rate of spread.
- **Not** Spanish O2 cadastre, **not** CONAF official, **not** grade A INFOCAM.
- **Not** `ml_strong`.
- **Not** field dispatch or tactical recommendation.
- **Not** field-validated V&V (`eng_stub`; `field_iou`/`field_ros`/`field_grade` are null).
- Successive CEMS mask IoU is **label-vs-label**, not transfer performance.
- `GO_OPEN_DATA_PACK` is **bridge readiness**, not operational GO.
- Decide confidence 0.72 is the **open CEMS source weight**, not a model score.

---

## 11. Attribution

```
Contains modified Copernicus Emergency Management Service information (2021, 2023).
Activations: EMSR500 Wildfire in Western Australia (AOI01 Perth);
EMSR647 Forest Fires in Chile (AOI01 Nacimiento).
Source: https://mapping.emergency.copernicus.eu/
© European Union, Copernicus EMS — information provided as-is, no warranty.
Proxy perimeter ≠ national cadastre / O2 España / CONAF official.
```

```
Contains modified Copernicus Sentinel-2 data (2021, 2023).
Accessed via Element84 Earth Search STAC (https://earth-search.aws.element84.com/v1).
```

---

## 12. Artifact index

| Artifact | Path |
|----------|------|
| This report | `docs/data_campaigns/LATAM_AU_DUAL_ANALYST_REPORT.md` |
| Rights | `docs/data_campaigns/LATAM_AU_RIGHTS.md` |
| Domain-gap (docs + eval copy) | `docs/data_campaigns/LATAM_AU_DOMAIN_GAP_SCORECARD.json` · `outputs/ml_eval/scorecards/wfd_ml_domain_gap_v1.json` |
| Product E2E | `outputs/open_if/latam_au_e2e/product_e2e_report.json` |
| Open packs | `outputs/open_if/emsr500_perth/` · `outputs/open_if/emsr647_nacimiento/` |
| Source packs | `data/open_if/latam_au/au/AU_EMSR500_PERTH/` · `data/open_if/latam_au/cl/CL_EMSR647_NACIMIENTO/` |
| File inventory | `data/open_if/latam_au/inventories/file_inventory.csv` |
| ML export | `artifacts/latam_au_ml_export/` |
| GO stamp | `docs/ML_PRODUCT_GO_STATUS.json` |
