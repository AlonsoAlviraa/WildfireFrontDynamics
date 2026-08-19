# LATAM + AU campaign — license matrix (F0/F1)

> **As of:** 2026-08-13  
> **Scope:** Lab-internal training/eval only. Not a legal opinion.  
> **SSOT plan:** [`docs/PLAN_ML_DATA_LATAM_AU_2026-08-13.md`](../PLAN_ML_DATA_LATAM_AU_2026-08-13.md)  
> **F1 rights sheet (EMSR500/647 T&C + download URLs):** [`LATAM_AU_RIGHTS.md`](LATAM_AU_RIGHTS.md)  
> **Catalog:** [`LATAM_AU_SOURCE_CATALOG.json`](LATAM_AU_SOURCE_CATALOG.json)

## How to read `lab_ok`

| Value | Meaning |
|-------|---------|
| **yes (provisional)** | Public open terms documented at source; OK for lab experiments **if** attribution/citation kept; re-check before product ship |
| **mixed** | Some products open, some restricted; per-product check required |
| **no / request** | Do not train until written cession / FOI / formal request completes |
| **unknown** | Not assessed — treat as **no** for train |

**Never** treat open remote sensing as Spanish national O2 cadastre or grade A INFOCAM.

## Matrix

| source_id | Source | License / terms (summary) | lab_ok? | Notes |
|-----------|--------|---------------------------|---------|-------|
| AU_DEA_HOTSPOTS | DEA Hotspots | GA/DEA CC-BY style open | yes (provisional) | Weak labels; cite DEA |
| AU_NAFI | NAFI fire scars | Open research/management; confirm redistribution | yes (provisional) | Check firenorth terms before public redistrib |
| AU_NT_FIRE_HISTORY | NT Fire History | CC-BY (portal) | yes (provisional) | Attribution required |
| AU_NSW_NPWS_FIRE_HISTORY | NSW NPWS Fire History SEED | NSW open data | yes (provisional) | Confirm SEED license tag on download |
| AU_ABARES_FOREST_FIRE | ABARES forest fire | Australian Gov open | yes (provisional) | Tables; limited geometry |
| AU_NIAFED_BLACK_SUMMER | National indicative fire extent | AU gov open geospatial | yes (provisional) | Indicative only |
| AU_PANGAEA_BLACK_SUMMER | PANGAEA 939064 | PANGAEA dataset license + cite paper | yes (provisional) | Research polys |
| CEMS_EMSR* / GLOBAL_CEMS_* | Copernicus EMS Rapid Mapping | Copernicus open access; EU attribution | yes (provisional) | **Proxy** perimeter; not national cadastre |
| BR_INPE_BDQUEIMADAS | INPE BDQueimadas | Public INPE fire foci | yes (provisional) | Cite INPE Queimadas |
| BR_TERRABRASILIS | TerraBrasilis | INPE open dissemination | yes (provisional) | Per-product cite |
| BR_MAPBIOMAS_FOGO* | MapBiomas Fogo | **CC-BY** public free | yes (provisional) | Annual/monthly scars; cite MapBiomas |
| CL_CONAF | CONAF Chile | Agency mixed / often request | **no / request** | P2-A formal request for SHP+dates |
| MX_CONAFOR | CONAFOR gob.mx | Mixed agency | mixed | Prefer datos.gob.mx open tables |
| MX_DATOS_INCENDIOS | CONAFOR incendios (datos.gob.mx) | MX open data libre uso | yes (provisional) | Often CSV not multi-scene EO; inventory probe HTTP 403 from some nets — recheck |
| AR_SMN | SMN Argentina | Mixed met service | mixed | Meteo context; not fire poly primary; probe may 403 |
| CO_IDEAM | IDEAM Colombia | Mixed | mixed | Prefer FIRMS + published layers; probe timeout observed |
| GLOBAL_FIRMS | NASA FIRMS | NASA open data policy | yes (provisional) | Some bulk needs free Earthdata login |
| GLOBAL_GWIS* | GWIS / JRC downloads | JRC public research downloads | yes (provisional) | Coarse MCD64/GlobFire |
| GLOBAL_ELEMENT84_STAC | Element84 Earth Search | Sentinel-2 Copernicus open; free STAC API | yes (provisional) | Inputs only |
| GLOBAL_GFW_FIRES | Global Forest Watch | Aggregator mixed | mixed | Prefer original FIRMS provenance |

## Lab use policy (this campaign)

1. **Train/eval allowed (provisional):** CEMS vector products, MapBiomas CC-BY scars, INPE hotspots, NASA FIRMS, DEA/NAFI/NSW/NT open layers, STAC Sentinel-2.  
2. **Blocked until human rights note:** CONAF operational perimeters, unpublished provincial SHP, any “request_only” row.  
3. **Redistribution:** Open license ≠ free to rehost multi-GB without attribution/terms; keep raw under `data/` gitignored.  
4. **Honesty:** Using CEMS/MapBiomas does **not** flip GO_Q, fusion, Hellín confirmed, or grade A.

## Human-only remaining

| Item | Owner |
|------|-------|
| Written OK for commercial product use of CEMS-derived packs | Alonso / legal light |
| CONAF formal perimeter request (if open CEMS insufficient) | Alonso |
| MapBiomas attribution text in pack README | eng on F2 |
| Earthdata login for bulk FIRMS (if needed) | eng ops |

## Update procedure

When a source license is re-verified:

1. Update `LATAM_AU_SOURCE_CATALOG.json` (`license_class`, `lab_ok_provisional`, `license_note`).  
2. Update this matrix row.  
3. Re-run `python scripts/inventory_open_if_urls.py --check` (reachability only; does not prove license).  
4. Do **not** invent “lab_ok=yes” for request_only portals.
