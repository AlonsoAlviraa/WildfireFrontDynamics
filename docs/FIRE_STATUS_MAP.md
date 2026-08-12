# Fire-status map (local + FIRMS NRT)

| Campo | Valor |
|-------|--------|
| **As of** | 2026-08-10 |
| **Entry** | `python -m wildfire_front map` |
| **Schema** | `wfd_fire_status_map_v1` · FIRMS fetch `wfd_firms_fetch_v1` |
| **Rails** | field_ops ML fusion **OFF** · not tactical dispatch · hotspots ≠ burned area |

---

## What it is

Interactive **Leaflet** map of fire-status geometry:

1. **Local** WFD products — `main_front.geojson`, `fronts.geojson`, emergency envelope guidance from an incident `--work-dir` / outbox, or any `--geojson`.
2. **External NRT** — NASA **FIRMS** VIIRS hotspots (when network allows).

This is **near-real-time satellite context**, not a second-by-second ops CAD or official Spanish extinction perimeter.

---

## Connectivity (can we connect?)

| Mode | Needs | Status values |
|------|--------|----------------|
| **Area API** | Free `FIRMS_MAP_KEY` | `connected` · `source_mode=area_api` |
| **Public Europe 24h CSV** | Network only (no key) | `connected` · `source_mode=public_europe_csv` |
| **Fixture CSV** | Local file (`--fixture-csv`) | `fixture` (CI / demos) |
| **Offline** | `--no-live` | `skipped` — map still builds from local layers |

**Never** invents hotspots when fetch fails (`connectivity=error`, empty features).

### Get a free MAP_KEY (optional, better bbox queries)

1. https://firms.modaps.eosdis.nasa.gov/api/map_key/
2. `set FIRMS_MAP_KEY=your_key` (PowerShell: `$env:FIRMS_MAP_KEY="..."`)
3. `python -m wildfire_front map --lat 40.9 --lon -3.1 --radius-km 40`

Without a key, the client falls back to the **public Europe VIIRS 24h CSV** and filters by bbox client-side (larger download).

---

## Commands

```text
# Local incident outbox only (offline)
python -m wildfire_front map --work-dir outputs/incidents/_sla_measure --no-live

# Local + FIRMS fixture (tests / air-gapped)
python -m wildfire_front map --bbox=-3.2,40.9,-3.0,41.05 --fixture-csv tests/fixtures/firms_sample_hotspots.csv --no-live
# or corners (avoids argparse negative-number footgun):
python -m wildfire_front map --west -3.2 --south 40.9 --east -3.0 --north 41.05 --fixture-csv tests/fixtures/firms_sample_hotspots.csv --no-live

# Attempt live FIRMS (network)
python -m wildfire_front map --lat 40.9 --lon -3.1 --radius-km 40 --output outputs/maps/mierla_nrt

# Machine-readable
python -m wildfire_front map --json --work-dir DIR --no-live
```

Artifacts (default `outputs/maps/fire_status/`):

- `fire_status_map.html` — open in browser (inline GeoJSON; works offline for local layers; basemap tiles need network)
- `fire_status_map.json` — full payload + connectivity + rails

---

## Honesty (always on map + JSON)

- **Not** validated tactical dispatch  
- FIRMS hotspot ≠ official burned area / perímetro de extinción  
- NRT latency is typically **hours**, not live radio ops  
- field_ops **ML fusion OFF** (map does not enable fusion)  
- Local envelopes remain extrapolated guidance  

---

## Code

| Module | Role |
|--------|------|
| `wildfire_front/map_status/firms_client.py` | Fetch/parse FIRMS |
| `wildfire_front/map_status/payload.py` | Compose `wfd_fire_status_map_v1` |
| `wildfire_front/map_status/html_map.py` | Leaflet HTML writer |
| `wildfire_front/cli_map.py` | CLI `map` |
| `tests/test_fire_status_map.py` | Fixture + CLI entry tests |
