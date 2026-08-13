# Open ROS / progression packs (Agent B)

> **As of:** 2026-08-13T09:46:29Z  
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
| Used fire | `SaoJoaoPesqueira_10072020` — 8 aligned GeoTIFF scenes EPSG:32629; geotiff ingest 8/8 accepted; decide **HOLD** (latency_ms=26.266) |

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

## CFSDS / NIROPS

Not downloaded this pass (PT-FireSprd + GOFER already staged).

## Non-claims

- Not GO_Q complete, not FREEZE lift, not Hellín promote, not Tobarra KEEP reopen.
- Not official ES cadastre / O2.
- Not tactical dispatch.
