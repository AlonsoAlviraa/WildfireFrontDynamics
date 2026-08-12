# DEM cache (fuel–terrain stack)

Caches for Tobarra / IF AOIs:

- `tobarra/glo30_window.tif` — windowed Copernicus GLO-30 (created with `--allow-download`)
- `tobarra/dem_manifest.json` — provenance

GeoTIFF caches are **gitignored**. Prefer local PNOA MDT when available:

```bash
python scripts/build_fuel_terrain_stack.py --fire tobarra --dem path/to/mdt.tif --with-physics --fit-calibration
```

Download open GLO-30 (opt-in network):

```bash
python scripts/build_fuel_terrain_stack.py --fire tobarra --allow-download --with-physics --fit-calibration
```
