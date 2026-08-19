# LATAM + Australia — F0 Shortlist (top 6)

> **As of:** 2026-08-13  
> **Campaign plan:** [`docs/PLAN_ML_DATA_LATAM_AU_2026-08-13.md`](../PLAN_ML_DATA_LATAM_AU_2026-08-13.md)  
> **Full candidates:** [`LATAM_AU_CANDIDATES.csv`](LATAM_AU_CANDIDATES.csv)  
> **Source catalog:** [`LATAM_AU_SOURCE_CATALOG.json`](LATAM_AU_SOURCE_CATALOG.json)  
> **License matrix:** [`LATAM_AU_LICENSE_MATRIX.md`](LATAM_AU_LICENSE_MATRIX.md)  
> **URL inventory:** run `python scripts/inventory_open_if_urls.py --check`

## Scoring rails (honest 0/1; unknown = 0)

| # | Requirement |
|---|-------------|
| R1 | ≥3 dated scenes (same sensor or alignable pipeline) |
| R2 | Usable geometry: perimeter / burned mask / active-fire stack |
| R3 | CRS + bbox + dates documented |
| R4 | License open or written cession |
| R5 | Does **not** depend on single multi-IF `k` or silent k-fit |
| R6 | Hash + inventory CSV on disk (real_if protocol) |

**None of these rows claim measured model IoU, grade A, or FREEZE lift.** R6 flips to **1** only after F2 GeoTIFF + `meta.json` hashes exist. CEMS = **proxy perimeter**, not national cadastre / O2 ES. F1 rights: [`LATAM_AU_RIGHTS.md`](LATAM_AU_RIGHTS.md).

## Top 3 — Australia

| Rank | event_id | Year | Why shortlist | R1 | R2 | R3 | R4 | R5 | R6 | Sum | class |
|------|----------|------|---------------|----|----|----|----|----|----|-----|-------|
| 1 | `AU_EMSR500_PERTH` | 2021 | Compact CEMS activation (DEL+MONIT+GRA) near Perth; F2 pack materialized (3 CEMS + 3 S2 NBR GeoTIFF) | 1 | 1 | 1 | 1 | 1 | 1 | **6** | ml_weak |
| 2 | `AU_EMSR408_NSW` | 2019 | P1-A pack: EMSR408 AOI09 Bendemeer (4 CEMS + 3 S2 NBR GeoTIFF) | 1 | 1 | 1 | 1 | 1 | 1 | **6** | ml_weak |
| 3 | `AU_NAFI_NT_SEASON_2023` | 2023 | P1-A L1 pack: NAFI 2021–2023 Darwin/NT windows + 3 S2 NBR | 1 | 1 | 1 | 1 | 1 | 1 | **6** | ml_weak |

**AU runner-ups:** `AU_EMSR408_GOSPERS` (subset of #2), `AU_NSW_NPWS_HISTORY`, `AU_BLACK_SUMMER_PANGAEA` (research polys; cite DOI).

**Primary AU pack target (P0-B):** materialize `AU_EMSR500_PERTH` first (smaller product set than EMSR408).

## Top 3 — LATAM

| Rank | event_id | Year | Why shortlist | R1 | R2 | R3 | R4 | R5 | R6 | Sum | class |
|------|----------|------|---------------|----|----|----|----|----|----|-----|-------|
| 1 | `CL_EMSR647_NACIMIENTO` | 2023 | Chile mega-fires AOI01 Nacimiento; F2 pack materialized (3 CEMS + 3 S2 NBR GeoTIFF) | 1 | 1 | 1 | 1 | 1 | 1 | **6** | ml_weak |
| 2 | `CL_EMSR715_VALPARAISO` | 2024 | P1-A pack: EMSR715 AOI01 Valparaíso (FEP+DEL+GRA JSON + 3 S2 NBR) | 1 | 1 | 1 | 1 | 1 | 1 | **6** | ml_weak |
| 3 | `BR_PANTANAL_2020_MAPBIOMAS` | 2020 | P1-A L1 pack: MapBiomas annual 2018–2020 Pantanal windows + 3 S2 NBR | 1 | 1 | 1 | 1 | 1 | 1 | **6** | ml_weak |

**LATAM runner-ups:** `MX_EMSR717_2024`, `BO_EMSR765_2024`, `GT_EMSR727_2024` / `BZ_EMSR726_2024` (confirm AOI meta before pack).

**Primary LATAM pack target (P0-B):** materialize `CL_EMSR647_NACIMIENTO` AOI01 (Nacimiento) with ≥3 S2 dates.

## Selection notes (honesty)

1. **No `ml_strong` yet.** Shortlist is L2 proxy / L1 weak until multi-date EO is staged and R6 inventory exists.  
2. **R1 = 1** only where CEMS multi-MONIT products evidence multi-date geometry (not full Sentinel stacks yet). STAC pull still required for GeoTIFF training contract.  
3. **R6** is **1** only when `meta.json` + hashed GeoTIFF exist on disk (P0-B plus P1-A: EMSR408, EMSR715, MapBiomas Pantanal, NAFI NT). Other candidate rows stay **0**.  
4. **CONAF / CONAFOR agency portals** stay `context_only` / request_only until written rights (see license matrix).  
5. **Do not** promote shortlist into FREEZE lift, retrain v35, fusion ON, or GO_Q true.

## URL probe snapshot (F0)

Live probe via `scripts/inventory_open_if_urls.py --check` (2026-08-12/13 UTC): **33 reachable / 4 unreachable** of 37 catalog URLs. Full table: [`LATAM_AU_URL_INVENTORY.csv`](LATAM_AU_URL_INVENTORY.csv).

Unreachable at probe time (honest; not invent green):

| source_id | http / error |
|-----------|----------------|
| AU_ABARES_FOREST_FIRE | TimeoutError |
| MX_DATOS_INCENDIOS | HTTP 403 |
| AR_SMN | HTTP 403 |
| CO_IDEAM | URLError timeout |

Shortlist primary URLs (CEMS EMSR500/408/647/715, NAFI, MapBiomas, FIRMS) were **reachable**.

## Next engineering steps

```bash
# Probe catalog reachability (writes inventory CSV)
python scripts/inventory_open_if_urls.py --check \
  --catalog docs/data_campaigns/LATAM_AU_SOURCE_CATALOG.json \
  --output docs/data_campaigns/LATAM_AU_URL_INVENTORY.csv \
  --json-out docs/data_campaigns/LATAM_AU_URL_INVENTORY.json

# F2 packs (rasters gitignored; meta.json + README tracked)
python scripts/materialize_latam_au_emsr_packs.py
python scripts/eval_latam_au_domain_gap.py
# data/open_if/latam_au/au/AU_EMSR500_PERTH/
# data/open_if/latam_au/cl/CL_EMSR647_NACIMIENTO/
```

## Owners

| Role | Action |
|------|--------|
| Alonso | Confirm shortlist priority; rights OK for CEMS+MapBiomas lab use |
| Data Steward | F1 license sheet complete; inventory honesty |
| eng B | F2 pack meta.json + STAC helper (out of this F0 PR if not shipped) |
