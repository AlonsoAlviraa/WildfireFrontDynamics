# Weather Gridded Source Contract (V3)

**Status:** source selected · download path scaffolded · **not** production field  
**work_class:** `weather_gridded_v1` · lab only · fusion OFF  
**Fallback honesty path:** DEM-lapse (`scripts/stage_dem_lapse_weather.py`) remains available

## Primary source (chosen)

| Field | Value |
|-------|--------|
| **Source** | **ERA5-Land hourly** (CDS / Copernicus) — preferred when `cdsapi` + `~/.cdsapirc` |
| **Why** | Global, hourly, u10/v10 + t2m + d2m + tp; not collinear-by-construction with DEM |
| **Unblock (lab, 2026-08-07)** | **Open-Meteo Archive** multi-point IDW → DEM grid (`scripts/stage_open_meteo_weather.py`) |
| **Open-Meteo provenance** | `open_meteo_archive_interp_v1` — **not** ERA5; stronger than DEM-lapse |
| **Alt** | AEMET raster if station-interpolated grids become available with license |
| **Not allowed as “strong weather”** | Scalar AEMET station broadcast, DEM-lapse sold as reanalysis |

### Open-Meteo status (local)

See `outputs/ml_eval/weather_open_meteo_status.json` — 6/7 fires variance_gate pass (Hellín wind near-constant at archive resolution).  
Data under `data/weather_openmeteo/<weather_key>/`.

## Variable contract

| WFD key | ERA5-Land | Notes |
|---------|-----------|-------|
| `temp` / tmin/tmax | `t2m` (K→°C) | daily min/max from hourly window around fire |
| `humidity` | from `t2m`+`d2m` → RH% | must be spatial non-constant |
| `wind_speed` | `u10`,`v10` → m/s | **variance gate required** |
| `wind_dir` | atan2(u,v) degrees | non-constant |
| `precip` | `tp` m → mm | may be sparse zeros (honest) |

**Time snap:** nearest hour to each LWIR frame timestamp (document timezone UTC vs local).  
**Space:** clip to fire bbox WGS84 + 0.05° pad; resample to LWIR grid at re-emit.

## Paths

```
data/weather_era5/<weather_key>/{tmin,tmax,temp,humidity,wind_speed,wind_dir,precip}.tif
data/weather/<weather_key>/   # DEM-lapse fallback (existing)
```

## Variance gate (required before claiming WEATHER_LIFT)

For each fire, after stage:

1. `wind_speed` spatial std > 0 (or document calm event).  
2. `humidity` spatial std > 0.  
3. Collinearity audit: R²(wind_speed, elevation) and R²(humidity, elevation) written to  
   `outputs/ml_eval/weather_collinearity.json`.  
4. If both wind and RH are constant → **BLOCKED** (do not train as gridded strong).

## Ablation protocol

| Arm | Weather | Init | Pack geometry |
|-----|---------|------|---------------|
| W0 | DEM-lapse | same as W1 | identical folds |
| W1 | ERA5-Land | same | identical folds |

**Done:** `WEATHER_LIFT` if mean_W1 − mean_W0 ≥ 0.01 **or** published `WEATHER_NULL`.

## Credentials

CDS API: `~/.cdsapirc` with URL `https://cds.climate.copernicus.eu/api`  
Script: `scripts/stage_era5_land_weather.py` (scaffold; requires `cdsapi` + accepted licences on CDS).

## Rails

```json
{
  "ml_product_go": false,
  "field_ops_allow_ml_live_in_fusion": false,
  "dem_lapse_is_not_reanalysis": true,
  "press_weather_forbidden": true
}
```
