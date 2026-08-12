# Schema Bridge 14↔17 (V2)

**Status:** lab implementation · `work_class=schema_bridge_projected`  
**Code:** `wildfire_front/ml/schema_bridge.py` · **Tests:** `tests/test_schema_bridge.py`  
**Rails:** not geotiff spatial_v1 · not sealed T1 comparable · `ml_product_go=false` · fusion OFF

## Why

multi_if residual-small is trained on **legacy17** (17 feat + prev_fire → 18 in).  
spatial_v1 / physics14 is **14 feat + prev_fire → 15 in**.  
Without a bridge, spatial trains from scratch and collapses to copy (KILL ~0.39).

## legacy17 channel semantics (build order)

| idx | name | physics14 fate |
|----:|------|----------------|
| 0 | slope | → slope |
| 1 | aspect+π | → aspect_sin/cos (derive) |
| 2 | temperature | → tmin **and** tmax (temp_split_proxy) |
| 3 | humidity | → humidity |
| 4 | wind_speed | → wind_speed |
| 5 | wind_dir | → wind_sin/cos (derive) |
| 6 | precipitation | → precipitation |
| 7–10 | pressure/cloud/vis/dew **const** | **DROP** |
| 11 | vegetation | → vegetation |
| 12 | erc | → erc |
| 13 | 1−erc | DROP redundant |
| 14–15 | pads | DROP |
| 16 | ffmc | → drought_or_ffmc |
| — | elevation | **GAP** in sealed NPZ (not stored) |

## physics14 / spatial_v1 names

`elevation, slope, aspect_sin, aspect_cos, tmin, tmax, humidity, wind_speed, wind_sin, wind_cos, precipitation, vegetation, erc, drought_or_ffmc`

## First-conv partial init map (T=1)

Spatial in_ch 15 ← legacy in_ch 18:

| spatial_i | name | legacy_i |
|----------:|------|---------:|
| 0 | elevation | — GAP |
| 1 | slope | 0 |
| 2–3 | aspect_sin/cos | — no 1:1 weight |
| 4–5 | tmin/tmax | 2 (shared proxy) |
| 6 | humidity | 3 |
| 7 | wind_speed | 4 |
| 8–9 | wind_sin/cos | — derive |
| 10 | precip | 6 |
| 11 | vegetation | 11 |
| 12 | erc | 12 |
| 13 | ffmc | 16 |
| 14 | prev_fire | 17 |

## Done gates (from engineering graph)

1. Spec + tests (this doc + CI).  
2. A/B board: partial init mean − scratch mean ≥ 0.02 on projected pack.  
3. Spatial geotiff transfer: ≥2 folds `improvement_vs_copy ≥ 0.05`.  
4. Never flip product rails.

## Comparability

| Board | Comparable to champion 17ch T1? |
|-------|--------------------------------|
| sealed legacy17 LOFO | **yes** |
| projected physics14 from legacy | **no** (schema_bridge) |
| geotiff spatial_v1 | **no** (feature_spatial_v1) |
