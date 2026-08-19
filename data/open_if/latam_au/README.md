# LATAM + AU open-IF packs (gitignored rasters)

Lab packs for the 2026-08-13 campaign. **Raw GeoTIFF / CEMS zip stay gitignored.**

| Event | Path | Rights |
|-------|------|--------|
| `AU_EMSR500_PERTH` | `au/AU_EMSR500_PERTH/` | [`docs/data_campaigns/LATAM_AU_RIGHTS.md`](../../../docs/data_campaigns/LATAM_AU_RIGHTS.md) |
| `CL_EMSR647_NACIMIENTO` | `cl/CL_EMSR647_NACIMIENTO/` | same |
| `AU_EMSR408_NSW` | `au/AU_EMSR408_NSW/` | same (AOI09 Bendemeer) |
| `CL_EMSR715_VALPARAISO` | `cl/CL_EMSR715_VALPARAISO/` | same (Rapid Mapping JSON) |
| `BR_PANTANAL_2020_MAPBIOMAS` | `br/BR_PANTANAL_2020_MAPBIOMAS/` | MapBiomas CC-BY L1 |
| `AU_NAFI_NT_SEASON_2023` | `au/AU_NAFI_NT_SEASON_2023/` | NAFI L1 |

```bash
python scripts/materialize_latam_au_emsr_packs.py
python scripts/download_mapbiomas_fogo.py
python scripts/download_nafi_scars.py
python scripts/materialize_latam_au_weak_packs.py
python scripts/inventory_real_if_material.py --source data/open_if/latam_au --output data/open_if/latam_au/inventories/file_inventory.csv
python scripts/eval_latam_au_domain_gap.py
python scripts/build_latam_au_lofo_folds.py
python scripts/align_latam_au_era5.py
python scripts/rank_latam_au_active_learning.py
```

CEMS = proxy perimeter. Not O2 / grade A / ROS. Not a FREEZE lift.
