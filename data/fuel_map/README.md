# Fuel map cache

Land-cover → fuel model grids for IF stacks.

## Preferred sources

1. **Local CLC / SIOSE-derived raster** (codes → `fuel.models` crosswalk)
2. **ESA WorldCover 10 m** (open AWS COGs) via `--allow-fuel-download`
3. Synthetic mosaic (engineering only)

## Tobarra

```bash
# Download WorldCover window (opt-in network) + rebuild stack
python scripts/build_fuel_map.py --allow-download --with-stack
# or
python scripts/build_fuel_terrain_stack.py --fire tobarra --allow-fuel-download --with-physics
```

Cache: `data/fuel_map/tobarra/worldcover_window.tif` (gitignored).

## Multi-fire (spatial_v1)

```bash
# Resolve only (exit 0 if present, 2 if missing)
python scripts/build_fuel_map.py --fire hellin_2024 --resolve-only
python scripts/build_fuel_map.py --fire CARDOSO --allow-download
python scripts/build_fuel_map.py --fire LA_ESTRELLA_ACOM1 --allow-download

# Inventory weather + fuel for all core fires
python scripts/build_spatial_v1_weather_rasters.py --inventory-only
```

Cache keys match DEM keys: `cardoso`, `la_estrella_acom1`, `la_estrella_acom2`,
`hellin`, `tobarra`, `brazatortas`, `retuerta` under `data/fuel_map/<key>/`.

## Honesty

WorldCover/CLC → MED fuel is an **engineering crosswalk**, not UCO40/Vega field plots.
SIOSE/MFE custom maps can be passed with `--landcover path.tif --scheme clc`.
Download is **opt-in** (`--allow-download`); no silent network.
