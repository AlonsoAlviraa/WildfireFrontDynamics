# LATAM + AU — F1 rights sheet (lab internal)

> **As of:** 2026-08-13  
> **Scope:** Lab-internal train/eval only. **Not** a legal opinion.  
> **Plan:** [`docs/PLAN_ML_DATA_LATAM_AU_2026-08-13.md`](../PLAN_ML_DATA_LATAM_AU_2026-08-13.md)  
> **License matrix (F0):** [`LATAM_AU_LICENSE_MATRIX.md`](LATAM_AU_LICENSE_MATRIX.md)  
> **Catalog:** [`LATAM_AU_SOURCE_CATALOG.json`](LATAM_AU_SOURCE_CATALOG.json)

This sheet is the F1 gate for the six campaign packs (2 P0-B CEMS + 2 P1-A CEMS + 2 L1 MapBiomas/NAFI). Bytes stay under `data/open_if/latam_au/` (rasters gitignored). Open CEMS/S2 does **not** flip GO_Q, fusion, Hellín `confirmed`, FREEZE, or Spanish O2 / grade A.

## Decision (this campaign)

| Pack | Source | T&C / licence | lab_ok (internal) | Redistribute | Train/eval class |
|------|--------|---------------|-------------------|--------------|------------------|
| `AU_EMSR500_PERTH` | Copernicus EMS Rapid Mapping EMSR500 | [CEMS On-Demand T&C](https://mapping.emergency.copernicus.eu/terms-and-conditions/) · Reg. (EU) 2021/696 free, full, open | **yes (provisional)** | Cite source; do not rehost multi-GB in git | `ml_weak` L2 proxy |
| `CL_EMSR647_NACIMIENTO` | Copernicus EMS Rapid Mapping EMSR647 AOI01 | same T&C | **yes (provisional)** | same | `ml_weak` L2 proxy |
| `AU_EMSR408_NSW` | Copernicus EMS Rapid Mapping EMSR408 AOI09 Bendemeer | same T&C | **yes (provisional)** | same | `ml_weak` L2 proxy |
| `CL_EMSR715_VALPARAISO` | Copernicus EMS Rapid Mapping EMSR715 AOI01 (Rapid Mapping API + viewer JSON) | same T&C | **yes (provisional)** | same | `ml_weak` L2 proxy |
| `BR_PANTANAL_2020_MAPBIOMAS` | MapBiomas Fogo Collection 5 annual burned | **CC-BY** MapBiomas | **yes (provisional)** | Cite MapBiomas; L1 annual | `ml_weak` L1 |
| `AU_NAFI_NT_SEASON_2023` | NAFI 250 m fire scars | open research/management; confirm redistribution | **yes (provisional)** | Cite NAFI / firenorth | `ml_weak` L1 |
| Sentinel-2 L2A windows (optional EO) | Copernicus S2 via Element84 Earth Search | Copernicus open; STAC API free | **yes (provisional)** | Cite Copernicus + access date | inputs only |
| CONAF operational SHP | CONAF Chile | mixed / request | **no** | [`CONAF_DATA_REQUEST_TEMPLATE.md`](CONAF_DATA_REQUEST_TEMPLATE.md) | blocked until written cession |

**Human remaining:** written OK for *commercial product* use of CEMS-derived packs (Alonso / legal light). Lab experiments may proceed with attribution.

**Commercial rehost gate:** [`cems_commercial_rehost_gate.json`](cems_commercial_rehost_gate.json) · checklist [`CEMS_COMMERCIAL_REHOST_CHECKLIST.md`](CEMS_COMMERCIAL_REHOST_CHECKLIST.md) · `commercial_rehost_ok=false` until human signs. Packaging path: `python scripts/check_cems_commercial_rehost.py --require-commercial-rehost` fails closed while false.

## Copernicus EMS terms (what we rely on)

Fetched 2026-08-13 from [mapping.emergency.copernicus.eu/terms-and-conditions](https://mapping.emergency.copernicus.eu/terms-and-conditions/) (last modified 07/06/2023):

- Access/use of Copernicus Service Information is regulated by **Regulation (EU) 2021/696**.
- Users have **free, full and open access** without express or implied warranty (quality / suitability).
- Subject to T&C, users may: **reproduce, distribute, communicate to the public, adapt/modify/combine**.
- Some products are **restricted** under Art. 53 of Reg. 2021/696 (registration). EMSR500 / EMSR647 public vector zips used here are the **public** Rapid Mapping packages (no login).
- Public communication / distribution **must inform recipients of the source**. Official citation page linked from T&C (`/about/citations-guidelines/`) returned 404 on 2026-08-13; use the attribution block below until the portal page is restored.
- Data are **“as is”**; no IP transfer to the user; EU ownership of the source data remains.
- Third-party layers linked from the portal may have **different** terms (not used as train labels here).

### Required attribution (lab + any public figure)

```
Contains modified Copernicus Emergency Management Service information (2019, 2021, 2023, 2024).
Activations: EMSR408 NSW (AOI09 Bendemeer); EMSR500 Western Australia (AOI01 Perth);
EMSR647 Forest Fires in Chile (AOI01 Nacimiento); EMSR715 Valparaíso (AOI01).
Source: https://mapping.emergency.copernicus.eu/
© European Union, Copernicus EMS — information provided as-is, no warranty.
Proxy perimeter ≠ national cadastre / O2 España / CONAF official.

MapBiomas Fogo Collection 5 annual burned maps (CC-BY). Cite Projeto MapBiomas.
NAFI fire scars: North Australia Fire Information (firenorth.org.au). L1 weak only.
```

If Sentinel-2 windows are staged:

```
Contains modified Copernicus Sentinel-2 data ([year of acquisition]).
Accessed via Element84 Earth Search STAC (https://earth-search.aws.element84.com/v1).
```

## Researched download URLs (F1 inventory, public S3)

Portal index (HTML product list; reachable F0 probe):

| Activation | Portal |
|------------|--------|
| EMSR500 | https://mapping.emergency.copernicus.eu/activations/EMSR500/ |
| EMSR647 | https://mapping.emergency.copernicus.eu/activations/EMSR647/ |
| EMSR408 | https://mapping.emergency.copernicus.eu/activations/EMSR408/ |
| EMSR715 | https://mapping.emergency.copernicus.eu/activations/EMSR715/ · Rapid Mapping API `?code=EMSR715` |

Public vector packages (pattern confirmed on the activation pages, 2026-08-13). Host: `cems-mapping-website.s3.eu-west-1.amazonaws.com`.

### EMSR500 — Wildfire Western Australia (AOI01 Perth)

Activation 2021-02-05 · 1 AOI · 3 products. Centroid on portal map ≈ **116.17767, −31.77966**.

| Product | Delivery (portal) | Vector ZIP |
|---------|-------------------|------------|
| Delineation | 2021-02-05 20:32:25 | `https://cems-mapping-website.s3.eu-west-1.amazonaws.com/static/activations/EMSR500/EMSR500_AOI01_DEL_PRODUCT_r1_RTP01_v1_vector.zip` |
| Delineation Monit01 | 2021-02-11 17:03:24 | `https://cems-mapping-website.s3.eu-west-1.amazonaws.com/static/activations/EMSR500/EMSR500_AOI01_DEL_MONIT01_r1_RTP01_v1_vector.zip` |
| Grading | 2021-02-13 02:23:04 | `https://cems-mapping-website.s3.eu-west-1.amazonaws.com/static/activations/EMSR500/EMSR500_AOI01_GRA_PRODUCT_r1_RTP01_v1_vector.zip` |

PDF maps exist at the same stem with `.pdf`. **No public `_raster.zip` / native GeoTIFF package is listed on the EMSR500 page.** Pack GeoTIFFs are **materialized** (rasterized `observedEvent` polygons and/or windowed Sentinel-2 COGs). That is documented in each `meta.json` (`geotiff_origin`).

### EMSR647 — Forest Fires Chile (AOI01 Nacimiento)

Activation 2023-02-05 · 7 AOIs · 38 products. Pack uses **AOI01 Nacimiento only**.

| Product | Delivery (portal) | Vector ZIP |
|---------|-------------------|------------|
| First Estimate | 2023-02-13 23:56:12 | `https://cems-mapping-website.s3.eu-west-1.amazonaws.com/static/activations/EMSR647/EMSR647_AOI01_FEP_PRODUCT_r1_RTP01_v2_vector.zip` |
| Delineation | 2023-02-13 23:56:34 | `https://cems-mapping-website.s3.eu-west-1.amazonaws.com/static/activations/EMSR647/EMSR647_AOI01_DEL_PRODUCT_r1_RTP01_v2_vector.zip` |
| Delineation Monit01 | 2023-02-13 23:56:55 | `https://cems-mapping-website.s3.eu-west-1.amazonaws.com/static/activations/EMSR647/EMSR647_AOI01_DEL_MONIT01_r1_RTP01_v2_vector.zip` |
| Delineation Monit05 | 2023-02-14 02:15:43 | `https://cems-mapping-website.s3.eu-west-1.amazonaws.com/static/activations/EMSR647/EMSR647_AOI01_DEL_MONIT05_r1_RTP01_v1_vector.zip` |
| Delineation Monit06 | 2023-02-15 21:24:10 | `https://cems-mapping-website.s3.eu-west-1.amazonaws.com/static/activations/EMSR647/EMSR647_AOI01_DEL_MONIT06_r1_RTP01_v1_vector.zip` |

P0-B materializes **≥3** dated AOI01 products (DEL + two MONIT). Other AOIs (Rafael, Cuca, …) stay out of this pack.

### EMSR408 — Wildfires New South Wales (AOI09 Bendemeer)

Activation 2019-11-13 · 14 AOIs. Pack uses **AOI09 Bendemeer** (compact 4-product stack; Gospers AOI11 is DEL-only).

| Product | Delivery (portal) | Vector ZIP |
|---------|-------------------|------------|
| Delineation | 2019-11-14 21:15:50 | `https://cems-mapping-website.s3.eu-west-1.amazonaws.com/static/activations/EMSR408/EMSR408_AOI09_DEL_PRODUCT_r1_RTP01_v1_vector.zip` |
| Delineation Monit01 | 2019-11-16 18:10:46 | `https://cems-mapping-website.s3.eu-west-1.amazonaws.com/static/activations/EMSR408/EMSR408_AOI09_DEL_MONIT01_r1_RTP01_v1_vector.zip` |
| Delineation Monit02 | 2019-11-18 21:53:33 | `https://cems-mapping-website.s3.eu-west-1.amazonaws.com/static/activations/EMSR408/EMSR408_AOI09_DEL_MONIT02_r1_RTP01_v1_vector.zip` |
| Delineation Monit03 | 2019-11-21 21:20:42 | `https://cems-mapping-website.s3.eu-west-1.amazonaws.com/static/activations/EMSR408/EMSR408_AOI09_DEL_MONIT03_r1_RTP01_v1_vector.zip` |

### EMSR715 — Wildfire Valparaíso (AOI01)

Activation 2024-02-04. Public product HTML is JS-only; **vector geometry** from Rapid Mapping API + viewer JSON (same T&C). ObservedEvent JSON (primary) + product zip backup:

| Product | Delivery (API) | ObservedEvent JSON |
|---------|----------------|--------------------|
| First Estimate | 2024-02-04T20:02:40 | `https://rapidmapping-viewer.s3.eu-west-1.amazonaws.com/EMSR715/AOI01/FEP_PRODUCT/EMSR715_AOI01_FEP_PRODUCT_observedEventA_v1.json` |
| Delineation | 2024-02-06T16:52:36 | `https://rapidmapping-viewer.s3.eu-west-1.amazonaws.com/EMSR715/AOI01/DEL_PRODUCT/EMSR715_AOI01_DEL_PRODUCT_observedEventA_v2.json` |
| Grading | 2024-02-09T14:01:39 | `https://rapidmapping-viewer.s3.eu-west-1.amazonaws.com/EMSR715/AOI01/GRA_PRODUCT/EMSR715_AOI01_GRA_PRODUCT_observedEventA_v3.json` |

Zip mirrors: `https://rapidmapping.emergency.copernicus.eu/backend/EMSR715/AOI01/...`.

### MapBiomas Fogo / NAFI (L1 weak)

Annual GeoTIFF URLs and NAFI year zips are inventoried by `scripts/download_mapbiomas_fogo.py` and `scripts/download_nafi_scars.py`. Windowed lab packs only; not official cadastre.

JRC catalogue cross-ref (discovery, not a second licence): [Forest Fires in Chile (2023-02-05)](https://data.jrc.ec.europa.eu/dataset/8d3e2cf9-6b84-487c-9945-1d3f3de33d60).

## What these products are / are not

| Are | Are not |
|-----|---------|
| L2 **proxy** burned-area / damage delineation | Spanish national O2 cadastre |
| Open Rapid Mapping vectors | CONAF / INFOCAM grade A ops perimeters |
| Usable for lab transfer / weak labels after rasterize | Tactical ROS / Vp |
| Dated multi-product stacks (R1 evidence) | `ml_strong` until aligned multi-date EO + R6 inventory |

## Blocked until extra rights

- CONAF / unpublished provincial SHP (`lab_ok_provisional=false` in catalog).
- Restricted CEMS Art. 53 products (none used here).
- Rehosting full activation dumps on a public CDN without attribution.
- **Commercial product rehost / paid CDN** of CEMS-derived packs while `commercial_rehost_ok=false` (see commercial gate + Reg. (EU) 2021/696 obligations in the checklist).

## F1 checklist (this sheet)

- [x] T&C URL recorded and fetched
- [x] Public download URLs researched from official activation pages
- [x] lab_ok provisional = yes for CEMS500/647 + S2
- [x] Attribution text fixed
- [x] Explicit non-claims (O2 / GO_Q / fusion / FREEZE / ROS)
- [ ] Commercial-product OK (human) — gate `commercial_rehost_ok` still **false**

## Owners

| Role | Action |
|------|--------|
| Alonso / legal light | Commercial-use OK; CONAF request if CEMS insufficient |
| Data Steward | Keep this sheet in sync with pack `meta.json` `license_id` |
| eng B | Materialize packs only from URLs listed here |

## CONAF cession gate

<!-- CONAF_LAB_OK_AUTO -->
- **lab_ok_conaf:** `false` (auto from `scripts/record_conaf_cession.py`, 2026-08-18T22:46:13Z)
