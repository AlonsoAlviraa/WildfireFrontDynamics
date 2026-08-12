# Design — Features & multi-fire data truth path (2026-08-06)

| Campo | Valor |
|-------|--------|
| **Status** | IMPLEMENTED (harness + unit tests); full geotiff re-emit / Kaggle LOFO optional offline |
| **Date** | 2026-08-06 |
| **Product rail** | `lab_ml` only |
| **Schema id (E2-P2)** | `spatial_v1` (alias `physics14_spatial`) |
| **Mix policy (Priority B)** | `estrella_floor_v1` |
| **Related** | `DESIGN_ML_METRICS_LIFT_20260806.md`, sealed recipe T1 (recover_v2 / force_train / grid) |

---

## 0. Rails (immutable)

```
No Tobarra KEEP reopen / thrash
No ECE same-TEST thrash
No larger U-Net default
Field fusion OFF · IoU ≠ ROS
Recipe KEEP (recover_v2 / force_train / grid) = sealed T1 — not feature work
```

---

## 1. Recipe vs data clarity (Priority C)

### 1.1 Sealed recipe T1 is not feature work

| Item | Classification | Note |
|------|----------------|------|
| `recover_v2` LOFO residual path | **Recipe T1 on sealed legacy17** | Improves training recipe on sealed NPZ; does **not** add real spatial features |
| `force_train` / grid KEEP | **Recipe T1 on sealed** | Hyperparam / schedule exploration only |
| E2-P1 `clean12_subset` projector | **Low EV / cosmetic** | Drops dead legacy indices; elevation/aspect_cos/wind_cos zero-filled; **not** full re-emit |
| E2-P2 `spatial_v1` re-emit | **Feature work** | DEM → slope/aspect; weather rasters; fuel maps; FFMC from grids |
| `estrella_floor_v1` mix | **Data design** | Caps external share; sibling oversample; Tobarra stress-only |

Stamp any board JSON:

```json
{
  "work_class": "recipe_t1_sealed | feature_spatial_v1 | data_mix_estrella_floor_v1",
  "feature_schema": "legacy17 | clean12_subset | spatial_v1",
  "schema_path_id": "E2-P1 | E2-P2 | null"
}
```

### 1.2 G2 path options (weak-fold floor) — not more dead patches

1. **Real features (Priority A)** — re-emit `spatial_v1` from DEM + weather/fuel rasters; never-channel gate on train.
2. **Hard-fold curriculum on sealed** — growth / change weighting when ACOM2 held out; **no Hellín** required; still legacy17 honesty.
3. **VAL ensemble of KEEP folds** — recipe refresh only after a KEEP member; VAL-only mix/temps.
4. **Explicit non-path:** more Hellín/Braz/Retuerta concat **without** re-emit + reweight; larger U-Net for missing data; fake physics14 on legacy17.

### 1.3 Explicit low-EV list

| Low-EV item | Why |
|-------------|-----|
| `clean12_subset` full train as “feature upgrade” | Cosmetic projector; missing elevation; not physics14 |
| Fake physics14 on sealed legacy17 | No true tmin/tmax/FFMC spatial build |
| More Hellín / Braz / Retuerta naive concat | Dominates train without cap; weak transfer |
| Larger U-Net for missing data | Capacity ≠ signal; scale kill criteria already closed |
| Scalar-per-fire weather sold as spatial channels | std~0 / frac_const≈1 → never channels |

---

## 2. Priority A — Features with real variance (`spatial_v1`)

### 2.1 Schema

Registered in `wildfire_front/ml/feature_schema.py`:

- **id:** `spatial_v1` (alias `physics14_spatial`)
- **path id:** `E2-P2`
- **n_channels:** 14 (+ `prev_fire` → 15 in trainer)
- **names:** same order as physics14  
  `elevation, slope, aspect_sin, aspect_cos, tmin, tmax, humidity, wind_speed, wind_sin, wind_cos, precipitation, vegetation, erc, drought_or_ffmc`
- **honesty:** re-emit only; not clean12_subset; not physics14-on-legacy17

Terrain: `_terrain_from_elevation` (DEM required).  
Weather: rasterized to patch grid when AEMET/reanalysis geotiffs exist under `--weather-dir`; else **GAP** + `missing_mask` / non-spatial stamp.  
Fuel: spatial texture when maps exist.  
FFMC: `compute_ffmc` on weather grids — not constant fill sold as variance.

### 2.2 Re-emit

```powershell
$env:PYTHONPATH = "."
# Dry-run / GAP inventory (no invented rasters)
python scripts/reemit_spatial_v1_patches.py --dry-run --manifest-out outputs/ml_eval/spatial_v1_reemit_dry_run.json

# Full emit when DEM + images/masks present
python scripts/reemit_spatial_v1_patches.py `
  --images-dir path/to/lwir --masks-dir path/to/masks `
  --dem-path data/dem/<fire>/glo30_window.tif `
  --weather-dir path/to/weather_rasters `
  --ndvi-path path/to/ndvi.tif `
  --source-id LA_ESTRELLA_ACOM1 `
  --output-dir artifacts/clm_ndws_patches/spatial_v1/LA_ESTRELLA_ACOM1

# Optional wrapper
python scripts/geotiff_to_training_patches.py ... --schema spatial_v1 --dem-path ... --dry-run
```

**GAPs (honest):**

| GAP id | Meaning |
|--------|---------|
| `dem_missing` | No DEM → blocked (no synthetic flat DEM as spatial_v1) |
| `weather_rasters_missing` | No tmin/tmax/humidity/wind/precip geotiffs — scalar broadcast only if allowed; flagged non-spatial |
| `weather_partial_rasters` | Subset of weather geotiffs spatial; bulk `weather_is_spatial=False` |
| `fuel_or_ndvi_missing` | Vegetation channel missing spatial texture |
| `images_dir_missing` / `masks_dir_missing` | Cannot emit patches |

### 2.2b Multi-fire weather + fuel paths (post-KILL engineering)

Canonical layout (auto-discovered by `run_spatial_v1_full_reemit.py`):

| Asset | Path |
|-------|------|
| DEM | `data/dem/<dem_key>/glo30_window.tif` |
| Weather rasters | `data/weather/<weather_key>/{tmin,tmax,humidity\|rh,wind_speed,wind_dir,precip}.tif` |
| Fuel / WorldCover | `data/fuel_map/<fuel_key>/worldcover_window.tif` |
| NDVI (optional) | `data/fuel_map/<fuel_key>/ndvi.tif` or `data/ndvi/<key>/ndvi.tif` |

```powershell
$env:PYTHONPATH = "."

# A) Inventory weather+fuel presence (exit 1 = honest GAPs remain; exit 2 with --require-*)
python scripts/build_spatial_v1_weather_rasters.py --inventory-only `
  --manifest-out outputs/ml_eval/spatial_v1_weather_fuel_inventory.json

# B) Stage operator-provided gridded geotiffs (refuses constant std≈0 grids)
python scripts/build_spatial_v1_weather_rasters.py --fire tobarra_20240802 `
  --stage-tmin path/tmin.tif --stage-tmax path/tmax.tif `
  --stage-humidity path/rh.tif --stage-wind-speed path/ws.tif `
  --stage-wind-dir path/wd.tif --stage-precip path/pr.tif

# C) Multi-fire fuel / WorldCover (download opt-in OFF by default)
python scripts/build_fuel_map.py --fire hellin_2024 --resolve-only
python scripts/build_fuel_map.py --fire CARDOSO --allow-download

# D) Full re-emit with auto-discovery of weather_dir + fuel
python scripts/run_spatial_v1_full_reemit.py --inventory-only
python scripts/run_spatial_v1_full_reemit.py
```

**Honesty:** AEMET station JSON (`build_aemet_weather_scenario.py`) is **scalar** — not spatial weather.
`--allow-download` on the weather builder does **not** invent gridded reanalysis; stage real geotiffs.
Never sell constant geotiffs as spatial variance (`ConstantRasterRefused`).

**CLI exit codes:**

| Code | Meaning |
|------|---------|
| 0 | No weather/fuel GAPs on selected fires |
| 1 | Inventory/re-emit ok; honest GAPs remain (expected offline) |
| 2 | Blocked when a `--require-*` flag fails (see per-CLI flags below) |
| 3 | Hard error (unknown fire, stage wrote nothing, missing align/DEM on full emit) |

| CLI | `--require-*` flags | `--fire` aliases |
|-----|---------------------|------------------|
| `build_spatial_v1_weather_rasters.py` | `--require-weather-spatial`, `--require-full-weather-core`, `--require-fuel-spatial` | source_id / dem_key / weather_key / fuel_key |
| `run_spatial_v1_full_reemit.py` | `--require-weather-spatial`, `--require-full-weather-core`, `--require-fuel-spatial` | source_id / dem_key / weather_key / fuel_key |
| `build_fuel_map.py --resolve-only` | n/a (exit 0 present / 2 missing) | source_id / dem_key / fuel_key / `tobarra` |

### 2.3 Signal analysis + never-channel gate

```powershell
python scripts/analyze_feature_signal.py `
  --data-dir artifacts/clm_ndws_patches/spatial_v1/.../train `
  --schema spatial_v1 --gate-train `
  --output outputs/ml_eval/feature_signal_spatial_v1.json
```

Labels: `always` | `maybe` | `never` (legacy report `must` → `always`).  
Train harness (`run_clm_lofo_all_folds.py`) **refuses** `never` channels by default unless `--allow-never-channels` + honesty stamp / allowlist.

### 2.4 LOFO residual-small one-shot (E2-P2)

```powershell
# Smoke (CI) — no KEEP
python scripts/run_clm_lofo_all_folds.py --smoke `
  --feature-schema spatial_v1 --schema-path-id E2-P2 --in-channels 15

# Full train (GPU / Kaggle offline) after re-emit + mix packs exist
python scripts/run_clm_lofo_all_folds.py `
  --lofo-root artifacts/clm_ndws_patches/lofo_spatial_v1 `
  --out-root outputs/ml_eval/lofo_spatial_v1 `
  --feature-schema spatial_v1 --schema-path-id E2-P2 `
  --in-channels 15
```

Full multi-hour Kaggle retrain is **optional offline** — harness + smoke ship in CI.

### 2.4b Kaggle T4 one-shot (spatial_v1 + estrella mix)

Local machine has **no CUDA**. Use Kaggle T4 via the operator (short `C:\temp\...` staging for Windows CLI path bugs):

```powershell
$env:PYTHONPATH = "."
# End-to-end: stage → reuse/version dataset → push kernel → poll → download → E2 kill score
python scripts/run_kaggle_spatial_v1_estrella.py

# Variants
python scripts/run_kaggle_spatial_v1_estrella.py --dry-run          # stage only
python scripts/run_kaggle_spatial_v1_estrella.py --no-watch         # push, no poll
python scripts/run_kaggle_spatial_v1_estrella.py --skip-dataset     # remote pack ready
python scripts/run_kaggle_spatial_v1_estrella.py --download-only    # pull + score
python scripts/run_kaggle_spatial_v1_estrella.py --score-only       # board already local

# Watcher (legacy)
python scripts/watch_kaggle_spatial_v1_estrella.py
```

| Asset | Slug / path |
|-------|-------------|
| Dataset | `alonsoalviraaaa/wfd-lofo-spatial-estrella-v1` |
| Kernel | `alonsoalviraaaa/wfd-spatial-v1-estrella-lofo` |
| Script | `kaggle_job/run_spatial_v1_lofo_estrella.py` |
| Pack | `artifacts/clm_ndws_patches/lofo_mix_spatial_estrella_v1` |
| Board out | `outputs/kaggle_spatial_v1_estrella/spatial_v1_estrella_lofo_board.json` |
| Kill JSON | `outputs/ml_eval/lab_loop/metrics_lift_E2_P2_spatial_v1_estrella_kill.json` |

Recipe: **residual-small**, no multi_if/legacy17 init, `feature_schema=spatial_v1`, `work_class=feature_spatial_v1+data_mix_estrella_floor_v1`. Never invent KEEP; scorer decides. WorldCover multi-fire on Kaggle = GAP unless offline fuel rasters staged.

---

## 3. Priority B — Multi-fire mix design (`estrella_floor_v1`)

Replaces naive Hellín concat (`build_holdout_v1_plus_w3` → unweighted LOFO).

| Rule | Default |
|------|---------|
| External source cap | ≤ **0.28** of each fold train |
| Sibling oversample | When held=ACOM1 → 2× ACOM2 (and vice versa) |
| Tobarra | **Excluded** from core train (stress fold only) |
| Reweight | Optional `1/n_source` stamp → `train_sample_weights.json` |
| Leak | Held source never in train; run `audit_lofo_pack_leak.py` (0 leak) |

```powershell
python scripts/build_lofo_mix_v1.py --dry-run
python scripts/build_lofo_mix_v1.py `
  --src-root artifacts/clm_ndws_patches/holdout_v1_plus_w3 `
  --out-root artifacts/clm_ndws_patches/lofo_mix_estrella_v1 `
  --mix-policy estrella_floor_v1

# Or via splits script
python scripts/build_clm_lofo_splits.py `
  --src-root artifacts/clm_ndws_patches/holdout_v1_plus_w3 `
  --out-root artifacts/clm_ndws_patches/lofo_mix_estrella_v1 `
  --mix-policy estrella_floor_v1
```

### Board metrics law

- **Core-3** mean / min (CARDOSO, ACOM1, ACOM2) for G1/G2 comparability  
- **Hellín fold** only if D3 applicable (`n_test≥50`)  
- **ACOM2** reported separately as floor  
- Tobarra stress-only — not success criterion  

---

## 4. File map

| Path | Role |
|------|------|
| `wildfire_front/ml/feature_schema.py` | `spatial_v1`, terrain, FFMC, never-gate |
| `wildfire_front/fuel/spatial_v1_sources.py` | Multi-fire catalog, weather/fuel resolve + inventory |
| `scripts/reemit_spatial_v1_patches.py` | E2-P2 re-emit + dry-run GAP |
| `scripts/build_spatial_v1_weather_rasters.py` | Multi-fire weather inventory + stage geotiffs |
| `scripts/build_fuel_map.py` | Multi-fire fuel/WorldCover (`--fire`, `--resolve-only`) |
| `scripts/run_spatial_v1_full_reemit.py` | Full multi-fire re-emit + auto weather/fuel discover |
| `scripts/geotiff_to_training_patches.py` | `--schema spatial_v1` delegates |
| `scripts/analyze_feature_signal.py` | always/maybe/never + `--gate-train` |
| `scripts/run_clm_lofo_all_folds.py` | residual LOFO + never gate + spatial_v1 smoke |
| `scripts/build_lofo_mix_v1.py` | `estrella_floor_v1` mix designer |
| `scripts/build_clm_lofo_splits.py` | `--mix-policy` delegate |
| `tests/test_spatial_v1_features.py` | terrain, schema, never gate |
| `tests/test_spatial_v1_weather_fuel_sources.py` | inventory gaps, fuel resolve, CLI exit codes |
| `tests/test_lofo_mix_v1.py` | caps, Tobarra exclude, sibling OS |

---

## 5. Acceptance checklist

- [x] New schema registered with channel names + honesty  
- [x] Re-emit script with dry-run/GAP (no invented rasters)  
- [x] `analyze_feature_signal` never labels + train refuse by default  
- [x] Mix designer with caps / sibling / no Tobarra core train  
- [x] Unit tests (terrain, never gate, schema count, mix policy)  
- [x] This design doc (projector clean12 = low EV / cosmetic)  
- [ ] Full geotiff re-emit for all CLM fires — **blocked on external DEM/weather presence per fire**  
- [ ] Multi-hour Kaggle LOFO — offline optional  

---

## 6. One-shot operator sequence

```powershell
$env:PYTHONPATH = "."

# A) inventory / re-emit (per fire when rasters exist)
python scripts/reemit_spatial_v1_patches.py --dry-run

# B) mix LOFO packs (sealed or plus_w3 src)
python scripts/build_lofo_mix_v1.py `
  --src-root artifacts/clm_ndws_patches/holdout_v1 `
  --out-root artifacts/clm_ndws_patches/lofo_mix_estrella_v1 `
  --mix-policy estrella_floor_v1

# C) leak audit
python scripts/audit_lofo_pack_leak.py --lofo-root artifacts/clm_ndws_patches/lofo_mix_estrella_v1

# D) signal + gate
python scripts/analyze_feature_signal.py --data-dir .../train --schema spatial_v1 --gate-train

# E) LOFO residual smoke / train
python scripts/run_clm_lofo_all_folds.py --smoke --feature-schema spatial_v1 --schema-path-id E2-P2
```
