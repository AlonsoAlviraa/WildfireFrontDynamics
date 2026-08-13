# Open ROS / progression packs (Agent B)

> **As of:** 2026-08-13T10:00:00Z  
> **Rails:** FREEZE_ML_AND_REQUEST_DATA · GO_Q partial · fusion SSOT ON (brief said OFF; stamp not flipped) · no invented Vp/ha/IoU/ROS · Hellín `pending_external` · CEMS/EFFIS/PT-FireSprd/GOFER = proxy / open research ≠ official ES cadastre · decision support ≠ tactical dispatch

Bytes live under `data/external/<pack>/` (rasters/zips gitignored). Tracked: this note + `README.md` + `inventory.json` hashes.

## PT-FireSprd (Zenodo 7495506)

| Field | Value |
|-------|--------|
| Title | Portuguese Large Wildfire Spread Database |
| License | CC-BY-4.0 |
| Version | 0.08 |
| DOI | 10.5281/zenodo.7495506 |
| URL | https://zenodo.org/records/7495506 |
| Zip | `PT-FireSprd_v0.08.zip` |
| Bytes | 32981758 |
| md5 | `4d248b3f5c006c41dbaeae9e512493f6` (matches Zenodo) |
| sha256 | `8599c824181e1e7f8e13bce850402a2c3cf0e3b1ae7cf38c579c353b8da8e60b` |
| L1 shapefiles inventoried | 78 |
| R1-capable fires (≥3 dated scenes) | 73 |
| Used fire | `SaoJoaoPesqueira_10072020` — 8 aligned GeoTIFF scenes EPSG:32629; geotiff ingest 8/8 accepted; decide **HOLD** (latest latency_ms=5.598) |

Author L2/L3 `ros_*` fields are dataset attributes only. Not product ROS.

## GOFER (Zenodo concept 8327264 → record 14642378)

| Field | Value |
|-------|--------|
| Title | GOES-Observed Fire Event Representation |
| License | CC-BY-4.0 |
| Version | 0.2 |
| Requested DOI | 10.5281/zenodo.8327264 |
| Resolved DOI | 10.5281/zenodo.14642378 |
| URL | https://zenodo.org/records/14642378 |
| Zip | `GOFER.zip` |
| Bytes | 75711678 |
| md5 | `8d495af1e4a0ed77df35b5a15d5ebb04` (matches Zenodo) |
| sha256 | `96eca2e18529eb274ca94af9a730bcf1c9c6da597fb04a9b5cf9167aada451c2` |
| Catalog fires | 28 (`fireData.csv`) |
| Combined fireProg records | 20301 hourly polygons |
| Fires with ≥3 hourly tUTC | 28 |
| GeoTIFF contract | **skipped** — native rasters absent; hourly WGS84 polygons, not ≥3 aligned GeoTIFF scenes |

`acres_official` in `fireData.csv` is author/catalog, not product ha.

## CFSDS (OSF f48ry / Barber 2024 Scientific Data)

| Field | Value |
|-------|--------|
| Title | Canadian Fire Spread Dataset |
| License | CC-BY-4.0 (research proxy; paper 10.1038/s41597-024-03436-4) |
| OSF DOI | 10.17605/OSF.IO/F48RY |
| URL | https://osf.io/f48ry/ |
| Staged | 26 files / 62,726,634 B (version note + R example + 2020 points zip + 23 daily-summary zips) |
| Used | 2023 groups CSV: **21717** rows · **621** fire IDs · **593** IDs with ≥3 daily rows |
| GeoTIFF contract | **skipped** — yearly DOY rasters + daily group tables, not ≥3 aligned incident GeoTIFF scenes |
| Author fields unused | `sprdistm`, `pctgrowth`, `prevgrow`, `firearea` — not product ROS/ha |

23 yearly fire-DOY raster zips were listed on OSF and not downloaded this pass.

## NIROPS (Mendeley 95rj5d379g)

Not downloaded. `data.mendeley.com/public-api/datasets/95rj5d379g/files` → HTTP 400; `/1/files` → 404; `api.mendeley.com` → 401 (no auth header). No unauthenticated file URL.

## Non-claims

- Not GO_Q complete, not FREEZE lift, not Hellín promote, not Tobarra KEEP reopen.
- Not official ES cadastre / O2.
- Not tactical dispatch.
