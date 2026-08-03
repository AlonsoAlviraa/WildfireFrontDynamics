# Design: Real DEM for Tobarra fuel–terrain stack + ROS calibration adjustment factor

| Field | Value |
|-------|--------|
| **Title** | Real DEM (Tobarra) + Rothermel-lite calibration factors |
| **Repo** | `C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics` |
| **Date** | 2026-07-31 |
| **Revised** | 2026-07-31 (post design-review issues 1–14) |
| **Mega-plan** | `docs/MEGA_PLAN_PREDICCION_ROS_VEGETACION_TERRENO.md` (F1.1 + F2.3) |
| **Corpus** | `data/fire_intel/literature/corpus_v1.json` (Cell2Fire adj, Cardil bias) |
| **Status** | Implemented 2026-07-31 (GLO-30 cache + k recipe Tobarra; see outputs/fuel_stack/tobarra/) |

---

## 1. Context

### 1.1 What already ships

| Module / path | Role today |
|---------------|------------|
| `wildfire_front/fuel/models.py` | Med + Scott–Burgan fuel catalog; CLC crosswalk |
| `wildfire_front/fuel/terrain.py` | `slope_array_from_dem`, `aspect_array_from_dem`, `TerrainSample`, Φ_s |
| `wildfire_front/fuel/stack.py` | `FuelTerrainStack`, **`build_synthetic_tobarra_stack` only**, `write_stack` (JSON + NPZ) |
| `wildfire_front/fuel/rothermel_lite.py` | Sector physics prior; report ratios vs obs/Vp (**no apply factor**) |
| `wildfire_front/fuel/hybrid.py` | α·obs + (1−α)·physics; **when obs present, already re-scales physics sectors onto obs head** (`scale = obs / ph`) then blends — see §5.4 |
| `scripts/build_fuel_terrain_stack.py` | Always synthetic Tobarra; optional physics |
| `scripts/run_rothermel_prior.py` | CLI physics + hybrid dump |
| `tests/test_fuel_rothermel_lite.py` | Catalog, terrain, ROS order-of-magnitude, hybrid |
| `data/infocam_anchors.json` | `tobarra_20240802`: **vp=7.0**, status=`confirmed` |
| `wildfire_front/open_if/stac_s2.py` | Pattern: urllib STAC + **windowed COG** via rasterio (reuse style) |
| `wildfire_front/ops_perimeter.py` | `METRIC_CRS` / EPSG:32630 convention for CLM metric work |
| `pyproject.toml` | Core deps already include **numpy, rasterio, affine, shapely, pyproj**; pytest markers: `requires_weights`, `slow` only |

### 1.2 Measured gap (current uncalibrated physics)

From `outputs/fuel_stack/tobarra/physics_prior_tobarra.json` (synthetic DEM mean slope ~9.2°):

| Quantity | Value |
|----------|-------|
| Physics head ROS (raw) | **~12.83 m/min** |
| Observed primary ROS (ops default) | **5.71 m/min** |
| Vp anchor (INFOCAM confirmed) | **7.0 m/min** |
| ratio raw physics/obs | ~2.25× |
| ratio raw physics/Vp | ~1.83× |
| Mega-plan §6 KPI wording | \|ROS_physics − ROS_obs\| / ROS_obs **&lt; 50%** on Tobarra head |

**Raw** relative error vs obs ≈ **124%** — raw physics fails the mega-plan gap metric.

A fit `k_head = obs / raw_head` makes **calibrated** rel err ≈ 0 **by construction** on the fit fire. That is **engineering scale bookkeeping**, not scientific validation of the Rothermel-lite model. Cardil-style honesty: **report bias (raw metrics always)**; do not present post-k ≈0 as proof that uncalibrated physics is good.

| Metric class | Meaning | Use in DoD |
|--------------|---------|------------|
| **Raw** | pre-k physics vs obs/Vp | Honesty gap; always ship; not auto-green by fit |
| **Cal (engineering)** | post-k physics vs obs/Vp | Proves apply math + recipe wiring; expected ~0 on fit fire |
| **Multi-IF / LOFO** | held-out fires | Out of scope (F4); never claimed by this design |

### 1.3 Why real DEM now

- F1.1 is still **synthetic DEM** (`synthetic=true`); slope driving Φ_s is not survey terrain.
- Real elevations change mean/p90 slope → change raw physics head → **re-fit** k factors after DEM swap (recipe must pin DEM fingerprint — §4.3).
- Free open GLO-30 avoids IGN login for CI/dev; local PNOA MDT remains preferred when the user has it.

### 1.4 Honesty rails (non-negotiable)

- Never invent or overwrite official Vp/ha in `infocam_anchors.json`.
- Calibration is **engineering** applied to **physics potential only**, not to observed ROS or anchors.
- ABSTAIN still if fuel UNKNOWN or wind missing.
- Calibrated outputs labeled `physics_potential_calibrated` (not tactical).
- `no_tactical_dispatch=True` always on physics/hybrid products.
- `field_ops` ML fusion remains OFF (out of scope; do not touch policies).
- Synthetic path remains available only with **explicit** `--allow-synthetic` (or equivalent).
- Existing `calibration` ratio block always reflects **raw (pre-k)** vs targets (§5.4).
- Fit-to-obs KPI on cal is **not** multi-IF validation; recipes must state single-fire engineering.

### 1.5 Mega-plan F2.3 status honesty

Today mega-plan marks **F2.3** ✅ as “ratio en report (uncalibrated ~1.8× Vp)” — that is **ratio diagnostics only**, which already ships. This design adds **applied k factors + versioned recipe**, which is **new work**. If docs are touched in PR-D, F2.3 must become e.g. **🟡 engineering k recipe Tobarra (single-fire; not multi-IF)**, not a full green “validated physics” claim.

---

## 2. Goals / Non-goals

### Goals

1. **Real DEM** for Tobarra AOI bbox `[-1.72, 38.58, -1.66, 38.63]` WGS84:
   - Fallback chain: **local GeoTIFF** → **cache** → **open GLO-30 download (opt-in)** → **synthetic** (explicit flag only).
   - Derive slope/aspect with existing `terrain.py` helpers.
   - Emit `FuelTerrainStack` with `synthetic=false` when DEM is real; same protocol `fuel_terrain_stack_v1`.
   - Persist geo metadata (`crs`, `transform`, `dem_source`) so GeoTIFF can be rewritten from stack alone.
   - Write NPZ + optional GeoTIFF under `outputs/fuel_stack/tobarra/`; cache DEM under `data/dem/`.
2. **Calibration adjustment factors** (Cell2Fire-style HROS/BROS/FROS; Cardil-style bias reporting):
   - Fit at least `k_head` (optional `k_flank`, `k_rear`) so **calibrated** physics sectors can match obs and/or confirmed Vp **when applied to the physics product**.
   - Persist versioned **calibration recipe JSON** with **both raw and cal residual metrics**.
   - **Physics product** is the primary consumer of k; hybrid interaction is audit-first (see §5.4 — hybrid sectors already obs-dominated when obs present).
   - Engineering check: after correct apply on fit fire, `cal_rel_err_head_vs_obs` ≈ 0 and `kpi_cal_engineering_ok=true`; **always also publish** `raw_rel_err_head_vs_obs` / `kpi_raw_rel_err_lt_0_5` (typically false today).
3. **Offline-safe tests**: unit tests use fixture GeoTIFF; no network in default pytest.

### Non-goals

- Full BehavePlus / FlamMap / Cell2Fire CA port.
- PNOA LiDAR CHM / real SIOSE fuel map (still proxy fuel mosaic until later F1.2/F1.3 upgrades).
- Multi-IF DEM pipeline (Cardoso, Hellín, …) beyond a reusable API (Tobarra first).
- Silent rescaling of observed ROS or rewriting INFOCAM anchors.
- Claiming mega-plan physics KPI “passed” solely because cal err ≈ 0 after fit-to-obs.
- Changing hybrid sector magnitudes when obs is present (existing obs-scale path stays default).
- New heavy deps (no boto3, no planetary-computer SDK required; urllib + rasterio only).
- Tactical dispatch claims or Decision Card policy changes.

---

## 3. Architecture

Public API names only (no diagram/API drift):

```
                    ┌─────────────────────────────────────┐
  --dem PATH        │  dem.resolve_dem()                  │
  or opt-in net     │  chain: local → cache → GLO-30 → syn│
                    └─────────────────┬───────────────────┘
                                      ▼
                    ┌─────────────────────────────────────┐
                    │  stack.build_stack_from_dem()       │
                    │  slope/aspect, fuel mosaic, meta    │
                    │  crs/transform/dem_source persisted │
                    │  synthetic=false|true               │
                    └─────────────────┬───────────────────┘
                                      ▼
                    ┌─────────────────────────────────────┐
                    │  rothermel_lite.estimate_sector_*   │  raw physics
                    └─────────────────┬───────────────────┘
                                      ▼
                    ┌─────────────────────────────────────┐
                    │  calibration.fit_* / apply_*        │
                    │  k_head · ros_head → calibrated     │
                    │  metrics: raw_* + cal_*             │
                    └─────────────────┬───────────────────┘
                                      ▼
                    ┌─────────────────────────────────────┐
                    │  hybrid.hybrid_ros_prior(..., cal)  │
                    │  sectors: existing obs-scale path   │
                    │  nested physics: cal for audit      │
                    └─────────────────────────────────────┘
```

### Module layout (new / touched)

| Path | Action |
|------|--------|
| `wildfire_front/fuel/dem.py` | **NEW** — fetch/load/cache DEM, CRS window, write cache GeoTIFF |
| `wildfire_front/fuel/calibration.py` | **NEW** — fit/apply recipe, residual metrics, load/save JSON, refuse errors |
| `wildfire_front/fuel/stack.py` | **EDIT** — `build_stack_from_dem(...)`, geo fields, keep synthetic builder |
| `wildfire_front/fuel/rothermel_lite.py` | **EDIT** — optional calibration hook; **raw** ratio block always |
| `wildfire_front/fuel/hybrid.py` | **EDIT** — nested physics audit cal; sectors keep current obs-scale math |
| `wildfire_front/fuel/__init__.py` | **EDIT** — export new public symbols |
| `scripts/build_fuel_terrain_stack.py` | **EDIT** — CLI flags for DEM source + calibration |
| `scripts/run_rothermel_prior.py` | **EDIT** — `--calibration-recipe`, `--fit-calibration` |
| `scripts/fit_ros_calibration.py` | **NEW** (optional PR) — dedicated fit CLI |
| `tests/test_fuel_dem.py` | **NEW** — fixture DEM, no network |
| `tests/test_fuel_calibration.py` | **NEW** — fit/apply/raw+cal metrics/refuse |
| `tests/fixtures/dem/` | **NEW** — see §8.1 fixture strategy (prefer generate-in-test; optional committed tiny tif for CLI DoD) |
| `.gitignore` | **EDIT** (PR-B) — ignore `data/dem/**/*.tif` (and optionally `*.npz` caches) |
| `pyproject.toml` | **EDIT** (PR-B or smoke PR) — register `integration` marker **or** use existing `slow` |
| `data/dem/README.md` | **Optional** — cache dir note |

Reuse patterns from `open_if/stac_s2.py`:
- `urllib.request` for HTTPS
- `rasterio.Env` HTTP timeouts
- windowed read / write GeoTIFF
- soft failure → structured status / typed errors (never crash-silent)

---

## 4. Data model

### 4.1 DEM resolution result

```python
@dataclass
class DemProduct:
    elevation_m: np.ndarray          # 2D float64, meters
    transform: affine.Affine         # geotransform of array
    crs: str                         # e.g. "EPSG:32630"
    cell_size_m: float               # metric pixel size used for gradient
    bbox_wgs84: list[float]          # [w,s,e,n] request bbox
    source: str                      # local_geotiff | copernicus_glo30 | synthetic
    source_uri: str | None           # path or HTTPS href
    synthetic: bool
    nodata: float | None
    cache_path: str | None
    sha256: str | None               # of cache/local elev array file when available
    notes: list[str]
```

### 4.2 FuelTerrainStack extensions (backward compatible)

Add optional fields on the dataclass (defaults preserve synthetic stacks):

```python
@dataclass
class FuelTerrainStack:
    # ... existing fields ...
    crs: str | None = None                 # e.g. "EPSG:32630"
    transform: list[float] | None = None   # affine 6-tuple (a,b,c,d,e,f)
    dem_source: str | None = None          # local_geotiff | copernicus_glo30 | synthetic
    # synthetic: bool already exists
```

**Required when `synthetic=false`:** `crs`, `transform`, `dem_source` must be non-null so `write_stack(..., save_geotiff=True)` can georeference without a live `DemProduct`.

Example meta (real DEM):

```json
{
  "protocol": "fuel_terrain_stack_v1",
  "fire_id": "tobarra_20240802",
  "synthetic": false,
  "crs": "EPSG:32630",
  "transform": [25.0, 0.0, <west>, 0.0, -25.0, <north>],
  "dem_source": "copernicus_glo30",
  "bbox_wgs84": [-1.72, 38.58, -1.66, 38.63],
  "cell_size_m": 25.0,
  "sources": [
    "copernicus_glo30",
    "clc_crosswalk_v0",
    "fuel.models.MED_* engineering priors"
  ],
  "terrain_summary": {
    "slope_deg_mean": "<float>",
    "slope_deg_p90": "<float>",
    "slope_deg_max": "<float>",
    "elevation_m_mean": "<float>",
    "elevation_m_range": ["<min>", "<max>"],
    "height_veg_m_mean": "<float>",
    "dem_source": "copernicus_glo30",
    "dem_crs": "EPSG:32630"
  },
  "notes": [
    "Real DEM elevations; fuel mosaic still engineering proxy until SIOSE/MFE",
    "Does not invent official ha or Vp"
  ]
}
```

Layers unchanged: `dem_m`, `slope_deg`, `aspect_deg`, `clc_code`, `veg_height_m`, plus `fuel_id_grid` meta.

**Optional GeoTIFF outputs** (new, next to NPZ):

| File | Content |
|------|---------|
| `outputs/fuel_stack/tobarra/dem_m.tif` | elevation |
| `outputs/fuel_stack/tobarra/slope_deg.tif` | slope |
| `outputs/fuel_stack/tobarra/aspect_deg.tif` | aspect |
| `outputs/fuel_stack/tobarra/fuel_terrain_grids.npz` | existing |
| `outputs/fuel_stack/tobarra/fuel_terrain_stack.json` | meta (includes crs/transform/dem_source) |
| `outputs/fuel_stack/tobarra/dem_manifest.json` | source, checksum, CRS, bbox, fetched_at |

Cache (network downloads only):

| Path | Role |
|------|------|
| `data/dem/tobarra/glo30_window.tif` | cached AOI window (metric CRS preferred) |
| `data/dem/tobarra/dem_manifest.json` | provenance for cache |

`.gitignore` (PR-B): add `data/dem/**/*.tif` so multi‑MB caches are not committed; keep optional `data/dem/**/README.md` tracked if present.

### 4.3 Calibration recipe schema (`ros_calibration_recipe_v1`)

```json
{
  "schema": "ros_calibration_recipe_v1",
  "recipe_id": "tobarra_20240802_med_maquis_low_v1",
  "version": 1,
  "created_at": "2026-07-31T12:00:00+00:00",
  "fire_id": "tobarra_20240802",
  "fuel_id": "MED_MAQUIS_LOW",
  "mode": "uniform_from_head",
  "dem_binding": {
    "dem_source": "copernicus_glo30",
    "dem_cache_sha256": "<hex or null>",
    "stack_terrain_fingerprint": {
      "slope_deg_mean": 9.24,
      "slope_deg_p90": 13.65,
      "elevation_m_range": [654.0, 745.0]
    }
  },
  "weather_scenario": {
    "wind_10m_ms": 4.4,
    "wind_from_deg": 270.0,
    "dead_fmc_pct": 7.0,
    "slope_deg_used": 9.24,
    "slope_source": "stack_terrain_summary.mean"
  },
  "targets": {
    "observed_ros_head_m_min": 5.71,
    "observed_ros_source": "ops_default_primary_cli",
    "vp_anchor_m_min": 7.0,
    "vp_status": "confirmed",
    "vp_source": "data/infocam_anchors.json#tobarra_20240802",
    "fit_target": "observed_ros_head"
  },
  "raw_physics": {
    "method": "rothermel_lite_sectors_v1",
    "ros_head_m_min": 12.8307,
    "ros_flank_m_min": 5.7738,
    "ros_rear_m_min": 0.8105
  },
  "factors": {
    "k_head": 0.445,
    "k_flank": 0.445,
    "k_rear": 0.445
  },
  "calibrated_physics": {
    "ros_head_m_min": 5.71,
    "ros_flank_m_min": 2.569,
    "ros_rear_m_min": 0.361
  },
  "metrics": {
    "raw_rel_err_head_vs_obs": 1.2471,
    "raw_rel_err_head_vs_vp": 0.833,
    "raw_abs_err_head_vs_obs_m_min": 7.1207,
    "kpi_raw_rel_err_lt_0_5": false,
    "cal_rel_err_head_vs_obs": 0.0,
    "cal_rel_err_head_vs_vp": 0.184,
    "cal_abs_err_head_vs_obs_m_min": 0.0,
    "kpi_cal_engineering_ok": true,
    "ratio_raw_head_to_obs": 2.247,
    "ratio_raw_head_to_vp": 1.833,
    "honesty": "cal_err~0 after fit-to-obs is by construction; raw metrics are the model gap"
  },
  "product_claim": "physics_potential_calibrated",
  "no_tactical_dispatch": true,
  "honesty_notes": [
    "Factors scale engineering physics potential only; do not overwrite INFOCAM Vp",
    "Single-scenario fit on Tobarra; not multi-IF LOFO validated",
    "Re-fit required after dem_source / DEM fingerprint or fuel_id change",
    "cal_rel_err_head_vs_obs ≈ 0 does not mean raw physics meets mega-plan KPI",
    "field_ops must not treat calibrated physics as dispatch GO"
  ],
  "literature_refs": [
    "kim_2025_cell2fire / Cell2Fire HROS-BROS-FROS adjustment factors",
    "cardil_2023_ops_ros_bias protocol (report bias, do not silent-fix obs)"
  ]
}
```

**Factor modes** (top-level `mode` field — **not** inside `factors`):

| Mode | Definition |
|------|------------|
| `uniform_from_head` | `k_flank = k_rear = k_head = target / raw_head` (v1 default) |
| `per_sector` | Independent k if flank/rear targets exist (optional later) |
| `head_only` | Apply k to head; leave flank/rear raw but flag `partial_calibration` |

**Fit target priority (config):**

1. Default `fit_target="observed_ros_head"` when obs &gt; 0 (engineering cal toward ops ROS).
2. Optional `fit_target="vp_anchor"` when only confirmed Vp available.
3. Optional `fit_target="blend"` with `k = target_blend / raw_head` where `target_blend = w*obs + (1-w)*vp` and `w` default 0.7; document weights in recipe.

**Clamp:** `k_* ∈ [0.05, 5.0]`; outside → refuse fit via `CalibrationRefusedError` (`status=calibration_refused_extreme_k`). Never write recipe JSON on refuse.

**DEM binding / re-fit (K12):**

- Recipe **must** store `dem_binding.dem_source` and preferably `stack_terrain_fingerprint` (+ `dem_cache_sha256` when file exists).
- Default `apply_calibration`: if current stack `dem_source` ≠ recipe `dem_binding.dem_source` → **refuse apply** unless `--force-recipe`.
- Optional soft check: if fingerprint mean slope differs by &gt; 1.0° without source change → hard-warn in notes; still require `--force-recipe` to apply if implementer enables strict mode (default: **source match required**, fingerprint logged).

### 4.4 PhysicsPriorResult extensions

Do **not** break existing fields. Add optional fields on dict outputs / dataclass:

```python
# PhysicsPriorResult additions (optional, default None / False)
product_claim: str  # "physics_potential_orientation_only" | "physics_potential_calibrated"
calibration_applied: bool = False
calibration_recipe_id: str | None = None
k_factors: dict[str, float] | None = None  # numeric only
ros_head_raw_m_min: float | None = None  # pre-k, when calibrated
ros_flank_raw_m_min: float | None = None
ros_rear_raw_m_min: float | None = None
```

When calibrated:
- `ros_head_m_min` etc. hold **calibrated** values.
- `*_raw_m_min` preserve pre-k.
- `product_claim = "physics_potential_calibrated"`.
- `no_tactical_dispatch` remains `True`.

---

## 5. APIs (concrete)

### 5.1 `wildfire_front/fuel/dem.py`

```python
TOBARRA_BBOX_WGS84 = (-1.72, 38.58, -1.66, 38.63)  # w,s,e,n
DEFAULT_CELL_M = 25.0
DEFAULT_CRS = "EPSG:32630"  # UTM 30N working grid (ops_perimeter METRIC_CRS convention)
# PNOA often ETRS89 / EPSG:25830 — reproject into DEFAULT_CRS; slope is relative.

class DemFetchError(Exception):
    """Network / remote DEM failure."""

class DemUnavailableError(Exception):
    """No local/cache/download/synthetic path succeeded."""
    def __init__(self, reasons: list[str]):
        self.reasons = reasons
        super().__init__("; ".join(reasons))

def load_dem_geotiff(
    path: Path | str,
    *,
    bbox_wgs84: Sequence[float] | None = None,
    target_crs: str = DEFAULT_CRS,
    cell_size_m: float = DEFAULT_CELL_M,
) -> DemProduct:
    """Load local DEM; optional clip+reproject to metric grid.
    Requires rasterio. Raises FileNotFoundError / ValueError.
    """

def glo30_tile_ids_for_bbox(bbox_wgs84: Sequence[float]) -> list[str]:
    """Return 1° GLO-30 COG tile keys covering bbox (N## / E###|W###)."""

def glo30_public_href(tile_id: str) -> str:
    """HTTPS object URL for AWS Open Data copernicus-dem-30m COG.
    Pattern (document + implement defensively):
      https://copernicus-dem-30m.s3.amazonaws.com/
      Copernicus_DSM_COG_10_{NS}{lat:02d}_00_{EW}{lon:03d}_00_DEM/
      Copernicus_DSM_COG_10_{NS}{lat:02d}_00_{EW}{lon:03d}_00_DEM.tif
    Tobarra (~38.6N, 1.7W) → tile N38 W002 (verify at implement time with HEAD).
    """

def download_glo30_window(
    bbox_wgs84: Sequence[float],
    cache_path: Path,
    *,
    cell_size_m: float = DEFAULT_CELL_M,
    target_crs: str = DEFAULT_CRS,
    timeout_s: int = 60,
    force: bool = False,
) -> DemProduct:
    """If cache exists and force=False, load cache (no network).
    Else windowed read of GLO-30 COG(s) via rasterio+HTTPS, reproject to grid,
    write cache GeoTIFF + dem_manifest.json. On network failure raise DemFetchError.
    Expected first-fetch size for Tobarra window: order of a few MB (windowed COG),
    not full 1° tile dump. Timeout default 60s; connect 15s.
    """

def resolve_dem(
    *,
    bbox_wgs84: Sequence[float] = TOBARRA_BBOX_WGS84,
    local_path: Path | str | None = None,
    cache_dir: Path | None = None,
    allow_download: bool = False,  # DEFAULT OFF — opt-in only
    dem_fallback: str | None = None,  # None | "pc" (Planetary Computer STAC)
    allow_synthetic: bool = False,
    cell_size_m: float = DEFAULT_CELL_M,
    synthetic_n: int = 40,
    synthetic_seed: int = 42,
) -> DemProduct:
    """Fallback chain:
    1. local_path if provided and exists
    2. cache_dir / 'glo30_window.tif' if present (no flag required)
    3. if allow_download: download_glo30_window → cache
       - on 403/timeout: if dem_fallback=='pc', try PC STAC once; else raise
    4. if allow_synthetic: build synthetic elev from stack helper
    else raise DemUnavailableError with reasons.
    """
```

**CRS / grid algorithm (implement exactly):**

1. Parse request bbox WGS84.
2. Use `rasterio.warp.transform_bounds("EPSG:4326", target_crs, *bbox)`.
3. Build destination transform with `from_origin` / `from_bounds` at `cell_size_m`.
4. `reproject` elevation with `Resampling.bilinear` (or average for downsampling).
5. Mask nodata; fill only if &lt;1% holes (else leave NaN and note).
6. `cell_size_m` used for `np.gradient` in slope/aspect (physical metres).

**Rasterio:** already a **core** dependency. No graceful import-skip for production stack builders. Tests that need GeoTIFF use the same pattern as `tests/test_dataset_dem_align.py` (`pytest.mark.skipif(rasterio is None)` only as safety).

### 5.2 `wildfire_front/fuel/stack.py` additions

```python
def build_stack_from_dem(
    dem: DemProduct,
    *,
    fire_id: str = "tobarra_20240802",
    fuel_mode: str = "synthetic_mosaic",  # v1 only; real CLC later
    seed: int = 42,
) -> FuelTerrainStack:
    """Build stack grids from DemProduct.elevation_m.
    slope/aspect via terrain.slope_array_from_dem / aspect_array_from_dem
    with dem.cell_size_m. Fuel mosaic: reuse synthetic_mosaic logic for Tobarra
    until real CLC raster exists (honest notes).
    synthetic flag = dem.synthetic.
    Persist crs, transform (6-tuple), dem_source from DemProduct.
    """

def write_stack(
    stack: FuelTerrainStack,
    out_dir: Path,
    *,
    save_npz: bool = True,
    save_geotiff: bool = False,  # NEW default False for back-compat
) -> dict[str, str]:
    """Write JSON + NPZ. If save_geotiff and stack.crs/transform present,
    write dem_m/slope_deg/aspect_deg GeoTIFFs from stack.layers without
    requiring a live DemProduct.
    """
```

Keep `build_synthetic_tobarra_stack` unchanged for unit tests and offline demos (may leave `crs`/`transform` null or set a documented synthetic local CRS).

### 5.3 `wildfire_front/fuel/calibration.py`

```python
class CalibrationRefusedError(Exception):
    """Fit or apply refused. CLI maps to exit code 4."""
    def __init__(self, status: str, details: dict[str, Any] | None = None, message: str = ""):
        self.status = status  # e.g. calibration_refused_extreme_k | dem_source_mismatch | fuel_id_mismatch
        self.details = details or {}
        super().__init__(message or status)


@dataclass
class CalibrationRecipe:
    schema: str
    recipe_id: str
    version: int
    fire_id: str
    fuel_id: str
    mode: str                          # top-level, NOT inside factors
    dem_binding: dict[str, Any]
    weather_scenario: dict[str, Any]
    targets: dict[str, Any]
    raw_physics: dict[str, Any]
    factors: dict[str, float]          # k_head required; k_flank/k_rear optional; floats only
    calibrated_physics: dict[str, Any]
    metrics: dict[str, Any]            # raw_* + cal_* + kpi_* split
    product_claim: str
    no_tactical_dispatch: bool
    honesty_notes: list[str]
    literature_refs: list[str]
    created_at: str

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CalibrationRecipe": ...


def fit_sector_scale_factors(
    raw: PhysicsPriorResult | dict[str, Any],
    *,
    observed_ros_head_m_min: float | None,
    vp_anchor_m_min: float | None = None,
    vp_status: str | None = None,
    fit_target: str = "observed_ros_head",  # observed_ros_head | vp_anchor | blend
    blend_w_obs: float = 0.7,
    mode: str = "uniform_from_head",
    fire_id: str = "tobarra_20240802",
    weather_scenario: dict[str, Any] | None = None,
    dem_binding: dict[str, Any] | None = None,
) -> CalibrationRecipe:
    """Compute k factors.
    Raises CalibrationRefusedError if raw head missing/≤0 or k outside [0.05, 5]
    or fit target unavailable.
    vp_anchor only used if vp_status == 'confirmed' (caller responsibility).
    Metrics always include raw_rel_err_* and cal_rel_err_*.
    """


def apply_calibration(
    raw: PhysicsPriorResult,
    recipe: CalibrationRecipe | dict[str, Any],
    *,
    current_dem_source: str | None = None,
    force: bool = False,
) -> PhysicsPriorResult:
    """Return new result with scaled sectors; raw stored; product_claim calibrated.
    If raw.status == abstained → return abstained unchanged (no k magic).
    If current_dem_source set and != recipe.dem_binding.dem_source and not force:
      raise CalibrationRefusedError(status='dem_source_mismatch').
    fuel_id mismatch → refuse unless force.
    """


def residual_metrics(
    *,
    ros_head_raw: float,
    ros_head_cal: float | None,
    observed_ros_head_m_min: float | None,
    vp_anchor_m_min: float | None,
) -> dict[str, Any]:
    """Return raw_rel_err_head_vs_obs, cal_rel_err_head_vs_obs,
    kpi_raw_rel_err_lt_0_5, kpi_cal_engineering_ok, ratios, honesty string.
    """


def load_recipe(path: Path | str) -> CalibrationRecipe: ...
def save_recipe(recipe: CalibrationRecipe, path: Path | str) -> Path:
    """Write only after successful fit; never call on refuse path."""
```

**Apply math:**

```
ros_head_cal  = clip(k_head  * ros_head_raw,  0, 120)
ros_flank_cal = clip(k_flank * ros_flank_raw, 0, 120)
ros_rear_cal  = clip(k_rear  * ros_rear_raw,  0, 120)
```

Uncertainty band: scale `band_p10_p90` head bounds by `k_head` as well (same engineering factor).

### 5.4 `rothermel_lite.physics_prior_report` / hybrid

#### Physics report (ratio block = always raw)

```python
def physics_prior_report(
    ...,
    calibration_recipe: CalibrationRecipe | dict | Path | None = None,
    fit_calibration: bool = False,
    # fit uses observed_ros_m_min / vp_anchor_m_min already on the function
) -> dict[str, Any]:
    prior_raw = estimate_sector_ros_physics(...)
    # 1) ALWAYS compute existing key "calibration" from prior_raw (pre-k) vs obs/Vp
    #    so ratio_physics_head_to_obs stays ~2.25 on current Tobarra defaults even
    #    after recipe apply — never recompute ratios from post-k head.
    # 2) If recipe path: apply_calibration(prior_raw, recipe) → prior_cal
    # 3) Top-level ros_head_m_min etc. follow product: calibrated if recipe applied,
    #    else raw. Always include physics_raw when calibrated.
```

**Back-compat (required):**

| Key | Content |
|-----|---------|
| `calibration` | **Always raw-vs-target ratios** (today’s semantics). Regression: with recipe, `ratio_physics_head_to_obs ≈ raw/obs` (~2.25), **not** ~1.0 |
| `calibration_recipe` | Factors + split metrics when fit/applied |
| `physics_raw` | Raw sectors when recipe applied |
| `product_claim` | `physics_potential_orientation_only` or `physics_potential_calibrated` |
| `no_tactical_dispatch` | always `true` |

#### Hybrid interaction (critical — do not over-claim)

**Fact (current code):** when `observed_ros_m_min` is present and physics head &gt; 0, hybrid does:

```text
scale = obs / ph
head_p = ph * scale   # == obs
… then blend(obs, head_p) with α
```

So hybrid **head sector is obs-dominated** regardless of whether `ph` is raw 12.83 or cal 5.71 (`scale` becomes ~1.0 after cal). **Calibration does not change hybrid sector KPI when obs is present.**

**Required design for hybrid:**

1. **Primary consumer of k** = physics product / `physics_prior_report` / recipe JSON — **not** hybrid sector magnitudes.
2. When `calibration_recipe` is passed:
   - Always `apply_calibration` for the nested **`physics`** object and set `physics_product_claim`.
   - **Default** hybrid sector path: keep existing obs-scale math (use **raw or cal** `ph` only as shape source; with obs present, head remains ≈ obs). Document that recipe presence is **audit** on nested physics.
3. Optional future mode (not required for PR-C DoD): `hybrid_physics_source="raw"|"calibrated"` only affects the physics side used when **obs is missing** (α=0 pure-physics hybrid). When obs present, sectors stay current behavior unless a later design revisits this.
4. **Unit test (required):** with obs=5.71 and Tobarra defaults, hybrid `sectors.head_m_min` matches within 1e-6 **with and without** recipe applied.
5. **Do not** claim “hybrid ROS changes” as a calibration KPI.

```python
def hybrid_ros_prior(
    observed_ros_m_min: float | None,
    *,
    ...,
    calibration_recipe: CalibrationRecipe | dict | Path | None = None,
) -> dict[str, Any]:
    phys_raw = estimate_sector_ros_physics(...)
    phys_for_audit = phys_raw
    if calibration_recipe is not None:
        phys_for_audit = apply_calibration(phys_raw, load_if_needed(calibration_recipe))
    # Sector construction: KEEP existing logic using phys_raw head for scale
    # (or phys_for_audit — numerically equivalent when obs present and k fitted to obs).
    # Prefer phys_raw for scale to make “no sector change” obvious and stable.
    ph = phys_raw.ros_head_m_min
    ...  # existing scale/blend
    return {
        "status": ...,
        "method": "hybrid_obs_physics_v1",
        "sectors": {...},  # unchanged semantics when obs present
        "physics": phys_for_audit.to_dict(),  # calibrated when recipe present
        "physics_raw": phys_raw.to_dict() if calibration_recipe else None,
        "physics_product_claim": phys_for_audit.product_claim,
        "product_claim": "hybrid_orientation_with_uncertainty",
        "no_tactical_dispatch": True,
        "calibration_note": (
            "nested physics may be calibrated; hybrid sectors remain obs-scaled "
            "when observed ROS is present"
        ),
    }
```

### 5.5 CLI: `scripts/build_fuel_terrain_stack.py`

```text
python scripts/build_fuel_terrain_stack.py --fire tobarra [options]

--dem PATH              Local GeoTIFF (PNOA MDT or cache). Highest priority.
--dem-cache DIR         Default: data/dem/tobarra
--allow-download        Opt-in GLO-30 HTTPS if no local/cache.
                        Also enabled if env WFD_ALLOW_DEM_DOWNLOAD=1.
                        DEFAULT OFF (library + CLI).
--dem-fallback {none,pc}  Default none. "pc" = Planetary Computer STAC after AWS fail.
--allow-synthetic       Fall back to synthetic DEM (must be explicit for non-test)
--force-recipe          Allow apply despite dem_source / fuel_id mismatch
--cell-m 25
--save-geotiff
--with-physics
--fit-calibration       Fit recipe from obs/Vp after physics (writes recipe only on success)
--calibration-recipe PATH   Load existing recipe and apply to physics product
--obs-ros 5.71
--vp                    default: load confirmed from infocam_anchors.json
--fit-target observed_ros_head|vp_anchor|blend
--out outputs/fuel_stack/tobarra
```

**Default behavior (honesty + offline-friendly):**

| Scenario | Behavior |
|----------|----------|
| `--dem` present | Real DEM stack, `synthetic=false` |
| Cache hit under `--dem-cache` | Real DEM, no network, **no** `--allow-download` needed |
| No local/cache, no `--allow-download` / env | Exit **3** (unless `--allow-synthetic`) — fail loud, no hang |
| `--allow-download` or `WFD_ALLOW_DEM_DOWNLOAD=1` | Try GLO-30; cache; on 403 message: pass `--dem PATH` or `--dem-fallback pc` |
| Download fails, no synthetic | Exit 3 |
| `--allow-synthetic` | Synthetic path; honest_label includes synthetic |
| `--fit-calibration` refuse | Exit **4**; do not write recipe |

CI/default tests never download: use fixture `--dem` path from test-generated file.

### 5.6 CLI: fit-only (optional script)

```text
python scripts/fit_ros_calibration.py \
  --fuel MED_MAQUIS_LOW --wind-ms 4.4 --slope 9.24 --fmc 7 \
  --obs-ros 5.71 --vp 7 --fit-target observed_ros_head \
  --dem-source synthetic \
  --out outputs/fuel_stack/tobarra/calibration_recipe_v1.json
```

Or fold into `run_rothermel_prior.py --fit-calibration --out-recipe ...`.

---

## 6. DEM source details (GLO-30)

### 6.1 Preferred open source (no IGN login)

| Priority | Source | Auth | Notes |
|----------|--------|------|-------|
| 0 | User local GeoTIFF | none | PNOA MDT05/MDT25 or any elev GeoTIFF |
| 1 | Cache `data/dem/tobarra/glo30_window.tif` | none | Offline after first success; no download flag |
| 2 | **AWS Open Data COP-DEM GLO-30** COG HTTPS | none | Primary download; **opt-in** only |
| 3 | Planetary Computer STAC `cop-dem-glo-30` | none | Only if `--dem-fallback pc` |
| 4 | Synthetic | explicit flag | Tests / wiring only |

**Do not** require OpenTopography API key for v1.

### 6.2 Implementation notes for AWS GLO-30

- Public dataset registry: AWS Open Data `copernicus-dem-30m`.
- Windowed read with rasterio VSI curl settings (copy from `stac_s2.read_cog_window`).
- **Size/time budget:** windowed AOI for Tobarra ≈ few MB; timeout 60s total / 15s connect. Do not download full continental tiles.
- Corporate networks may block anonymous S3 (HTTP 403) → surface exit 3 with message to use `--dem PATH` or `--dem-fallback pc`.
- Tobarra bbox → tile N38/W002 (verify with HEAD); implement `glo30_tile_ids_for_bbox` for multi-tile.
- Vertical unit: metres; note `vertical_ref: "copernicus_glo30_as_delivered"`.
- Horizontal working grid: EPSG:32630; PNOA ETRS89 (EPSG:25830) reprojected — see manifest note.

### 6.3 Local PNOA path

User may pass e.g. `--dem D:\gis\MDT25_tobarra.tif`. Code must:
- Accept any single-band elev GeoTIFF with CRS
- Clip to bbox if dem larger than AOI
- Reproject if CRS ≠ target
- Mark `source=local_geotiff`, `synthetic=false`

### 6.4 Manifest (`dem_manifest.json`)

```json
{
  "schema": "wfd_dem_manifest_v1",
  "fire_id": "tobarra_20240802",
  "bbox_wgs84": [-1.72, 38.58, -1.66, 38.63],
  "source": "copernicus_glo30",
  "source_uri": "https://...",
  "cache_path": "data/dem/tobarra/glo30_window.tif",
  "crs": "EPSG:32630",
  "horizontal_crs_note": "EPSG:32630 working grid; PNOA ETRS89 (EPSG:25830) reprojected when provided; slope relative",
  "vertical_ref": "copernicus_glo30_as_delivered",
  "cell_size_m": 25.0,
  "shape": [H, W],
  "elevation_m_range": [min, max],
  "fetched_at": "ISO-8601",
  "synthetic": false,
  "sha256": "<of cache file>",
  "approx_fetch_bytes": "<optional>"
}
```

---

## 7. Failure modes

| Failure | Detection | Behavior |
|---------|-----------|----------|
| Missing local DEM path | `Path.is_file()` false | Fall through chain |
| Corrupt/unreadable GeoTIFF | rasterio open error | Raise / exit 2 with message |
| CRS missing on local DEM | `src.crs is None` | Refuse (no silent assume); exit 2 |
| Network timeout / 403 / 404 on GLO-30 | urllib/rasterio error | Soft fail → if `--dem-fallback pc` try once → else exit 3 (message: pass `--dem PATH`) unless `--allow-synthetic` |
| Empty elev / all nodata | `np.nanmax` nan | Refuse stack build |
| Extreme k outside [0.05, 5] | fit check | `CalibrationRefusedError(status=calibration_refused_extreme_k)`; exit 4; **do not write** recipe |
| Raw head ≤ 0 / missing | fit check | Same refuse path, exit 4 |
| Vp status not `confirmed` | anchor load | Do not use as fit target; may still report ratio only |
| Fuel UNKNOWN / wind None | existing | ABSTAIN; no calibration apply |
| Recipe fuel_id ≠ run fuel_id | apply check | `CalibrationRefusedError` unless `--force-recipe` |
| Recipe dem_source ≠ current | apply check | `CalibrationRefusedError(dem_source_mismatch)` unless `--force-recipe` |
| rasterio missing (broken env) | import | Fail clearly — core dep |
| User forgets honesty flags | CLI | Synthetic only if `--allow-synthetic`; download only if opt-in |

**Exit codes (scripts):**

| Code | Meaning |
|------|---------|
| 0 | Success |
| 2 | Bad args / bad local DEM / CRS |
| 3 | DEM unavailable (network/cache) without synthetic allowed |
| 4 | Calibration refused (`CalibrationRefusedError`) |

---

## 8. Testing

### 8.1 Unit tests (no network)

**Fixture strategy (PR-A):** Prefer **generate GeoTIFF in test** via rasterio into `tmp_path` (or session-scoped temp file) so CI does not depend on a binary committed before PR-A lands. For CLI DoD that needs a stable path, either:

- generate under `tmp_path` and pass that path to the script in a subprocess test, **or**
- commit a tiny `tests/fixtures/dem/tobarra_tiny.tif` (32×32) once generated in PR-A.

Do **not** require a pre-existing binary on a clean checkout without either generation or commit in the same PR.

**`tests/test_fuel_dem.py`**

1. Generate fixture DEM (plane or mild dome) via rasterio (32×32, EPSG:32630, 25 m, elev ~700±30 m).
2. `load_dem_geotiff` returns shape, finite elev, `synthetic=False`.
3. `build_stack_from_dem` → `synthetic is False`, `crs`/`transform`/`dem_source` set, slope mean &gt; 0; `write_stack(..., save_geotiff=True)` produces georeferenced tifs from stack meta alone.
4. `glo30_tile_ids_for_bbox(TOBARRA_BBOX)` contains expected tile id string (pure function, no IO).
5. `resolve_dem(local_path=fixture, allow_download=False)` succeeds.
6. `resolve_dem(local_path=None, allow_download=False, allow_synthetic=False)` raises `DemUnavailableError`.
7. `resolve_dem(..., allow_synthetic=True)` returns synthetic product.
8. Cache hit: pre-write cache geotiff; `allow_download=False` loads cache.

**`tests/test_fuel_calibration.py`**

1. Fit raw head 12.83, obs 5.71 → `k_head ≈ 5.71/12.83`; **`raw_rel_err_head_vs_obs ≈ 1.25`**, **`cal_rel_err_head_vs_obs ≈ 0`**, `kpi_raw_rel_err_lt_0_5 is False`, `kpi_cal_engineering_ok is True`.
2. Apply then check sectors scaled; raw preserved; `product_claim == "physics_potential_calibrated"`; `no_tactical_dispatch is True`.
3. ABSTAIN input → apply is no-op abstain.
4. Extreme raw (head 0.001 vs obs 50) → `CalibrationRefusedError`; no recipe file.
5. Vp-only fit with `fit_target=vp_anchor` → head_cal ≈ 7.0.
6. Round-trip `save_recipe` / `load_recipe`; `mode` top-level; `factors` floats only.
7. **Hybrid stability:** with obs present, hybrid head within 1e-6 with/without recipe.
8. **Raw ratio regression:** `physics_prior_report` with recipe → `calibration.ratio_physics_head_to_obs` ≈ raw/obs (~2.25), not ~1.0.
9. `dem_source_mismatch` refuse unless force.

**Extend `tests/test_fuel_rothermel_lite.py`**

- Keep uncalibrated OOM test.
- Report with recipe includes raw ratio block + recipe metrics.

### 8.2 Optional live smoke

Prefer **`@pytest.mark.slow`** (already registered) **plus** env skip:

```python
@pytest.mark.slow
@pytest.mark.skipif(os.environ.get("WFD_ALLOW_DEM_DOWNLOAD") != "1", reason="network")
def test_glo30_download_tobarra_smoke(tmp_path):
    ...
```

If a dedicated marker is desired, PR-B may add to `pyproject.toml`:

```toml
"integration: optional network/live resource tests",
```

Do **not** introduce unregistered `@pytest.mark.integration` without the pyproject edit.

### 8.3 DoD metrics (Tobarra scenario)

| Check | Gate |
|-------|------|
| Recipe schema + apply correctness | **PR-C required** |
| `raw_rel_err_head_vs_obs` present and honest (typically &gt; 0.5 today) | **PR-C/D required** |
| `cal_rel_err_head_vs_obs` ≈ 0 after fit-to-obs (`kpi_cal_engineering_ok`) | **PR-C** engineering wiring only — **not** “mega-plan science pass” |
| `kpi_raw_rel_err_lt_0_5` | Informational; may stay false until fuels/model improve |
| Hybrid head unchanged with/without recipe when obs present | **PR-C required** |
| Real DEM stack `synthetic=false` + geo meta | **PR-A/B/D** |
| Re-fit recipe after DEM source change | **PR-D** |

---

## 9. Key Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| K1 | **Fallback chain** local → cache → GLO-30 HTTPS (opt-in) → synthetic (explicit) | Offline after first fetch; no IGN login; honesty on synthetic |
| K2 | **AWS COP-DEM GLO-30 COG** as primary open download | No API key; same urllib/rasterio stack as STAC dNBR |
| K3 | **UTM 30N (EPSG:32630)** working grid for Tobarra | Metric cell size; matches `ops_perimeter` METRIC_CRS; PNOA ETRS89 reprojected |
| K4 | **Keep fuel mosaic synthetic** in v1 real-DEM stack | DEM unblocks F1.1; real CLC separate; notes must say so |
| K5 | **Calibration = multiplicative sector k** (Cell2Fire-style) | Interpretable; recipe-versioned; corpus-aligned |
| K6 | **Default fit target = observed head ROS**; Vp only if confirmed | Engineering cal; Vp never overwritten |
| K7 | **Uniform k from head** as v1 mode | Single DoF; mode field top-level |
| K8 | **Preserve `calibration` ratio block as always-raw**; sibling `calibration_recipe` | Back-compat; Cardil-style bias report |
| K9 | **Label `physics_potential_calibrated`** + `no_tactical_dispatch=True` | Product honesty |
| K10 | **No new Python dependencies** | rasterio/numpy/urllib already available |
| K11 | **Unit tests never hit network** | Fixture/generated GeoTIFF only |
| K12 | **Re-fit after DEM change; recipe binds `dem_source` (+ fingerprint)** | Refuse apply on mismatch unless `--force-recipe` |
| K13 | **ABSTAIN gates unchanged** | k cannot invent data |
| K14 | **CLI exit 3** when DEM blocked; **exit 4** on calibration refuse | Fail loud |
| K15 | **`allow_download` default False**; opt-in CLI flag or `WFD_ALLOW_DEM_DOWNLOAD=1` | No interactive-detection; no surprise hangs |
| K16 | **Physics product is primary k consumer; hybrid sectors stay obs-scaled when obs present** | Matches existing hybrid.py; avoid vacuous hybrid KPI claims |
| K17 | **Split raw vs cal metrics; never treat fit-to-obs cal err as mega-plan science pass** | Avoids vacuous DoD |
| K18 | **Stack persists `crs`/`transform`/`dem_source`** when non-synthetic | F1.1 GeoTIFF without live DemProduct |

---

## 10. Open Questions

| # | Question | Default if unresolved |
|---|----------|------------------------|
| Q1 | Exact AWS path template for GLO-30 COG (region suffix / naming) | HEAD probe on candidate base URLs; document working URL in dem_manifest |
| Q2 | Download default on/off? | **OFF** — explicit `--allow-download` or env `=1` (resolved) |
| Q3 | Obs ROS 5.71 provenance: hardcode CLI default vs load from pack? | Keep CLI default 5.71; optional `--obs-from-pack` later |
| Q4 | Fit-to-obs makes cal KPI trivial — multi-IF holdout? | Single-fire engineering only; LOFO is F4; raw metrics always published |
| Q5 | Apply k inside `ros_potential_m_min` or sector/report layer? | **Sector/report layer only** |
| Q6 | Commit GLO-30 cache under `data/dem/`? | **No** — gitignore `data/dem/**/*.tif`; tests use generated fixtures |
| Q7 | Vertical datum GLO-30 vs PNOA | Accept for slope; manifest notes absolute elev secondary |
| Q8 | Planetary Computer automatic fallback? | **Off** unless `--dem-fallback pc` |

---

## 11. PR Plan

Small, testable PRs. No git commit from design phase.

### PR-A — DEM load + real stack builder (offline)

**Scope**

- Add `wildfire_front/fuel/dem.py` with `load_dem_geotiff`, `DemProduct`, `resolve_dem` (local + cache load + synthetic; **download not implemented** — if `allow_download` True, raise clear `DemFetchError("download not implemented until PR-B")`).
- Add `build_stack_from_dem` in `stack.py`; geo fields; `write_stack(..., save_geotiff=)`.
- Tests generate fixture DEM in `tmp_path` (optional committed tiny tif).
- Wire CLI: `--dem`, `--allow-synthetic`, refuse silent synthetic; **no default download**.

**Deps:** none new.

**DoD**

- `pytest tests/test_fuel_dem.py tests/test_fuel_rothermel_lite.py` green.
- CLI with generated/local `--dem` writes `synthetic=false` stack with `crs`/`transform`/`dem_source`.
- Without `--dem` and without `--allow-synthetic` → non-zero exit (3 if no cache).

**Files:** `fuel/dem.py`, `fuel/stack.py`, `fuel/__init__.py`, `scripts/build_fuel_terrain_stack.py`, `tests/test_fuel_dem.py`, optional fixture tif.

---

### PR-B — GLO-30 download + cache (opt-in)

**Scope**

- Implement `glo30_tile_ids_for_bbox`, `download_glo30_window`, cache under `data/dem/tobarra/`.
- `resolve_dem` full chain; `dem_manifest.json` with CRS notes.
- `--allow-download` / `WFD_ALLOW_DEM_DOWNLOAD=1` opt-in only; `--dem-fallback pc` optional.
- `.gitignore`: `data/dem/**/*.tif`.
- Live smoke: `@pytest.mark.slow` + env gate (or register `integration` marker in pyproject).

**Deps:** none new.

**DoD**

- Offline cache hit unit-tested without download flag.
- Manual online smoke documents working HTTPS template.
- 403 surfaces exit 3 with “pass --dem PATH”.

**Files:** `fuel/dem.py`, scripts, tests, `.gitignore`, optional `pyproject.toml` marker.

---

### PR-C — Calibration factors + recipe (honest metrics)

**Scope**

- Add `wildfire_front/fuel/calibration.py` (`CalibrationRefusedError`, raw+cal metrics, dem_binding).
- Hook apply into `physics_prior_report` (ratios always raw) and hybrid (audit nested physics; sectors stable).
- `tests/test_fuel_calibration.py` per §8.1.
- CLI: `--fit-calibration`, `--calibration-recipe`, `--force-recipe`; exit 4 on refuse.

**Deps:** none new. Parallelizable after PR-A (synthetic DEM fine; re-fit after PR-B).

**DoD**

- Fit/apply correctness; recipe schema; refuse path no file write.
- `raw_*` and `cal_*` metrics both present; `kpi_cal_engineering_ok` after fit; **`kpi_raw_rel_err_lt_0_5` not required true**.
- With recipe: `calibration.ratio_physics_head_to_obs` remains raw ratio.
- Hybrid head with obs present: invariant with/without recipe (1e-6).
- ABSTAIN unchanged; `no_tactical_dispatch` true.
- **Not a DoD:** “mega-plan KPI green” from cal alone.

**Files:** `fuel/calibration.py`, `fuel/rothermel_lite.py`, `fuel/hybrid.py`, `fuel/__init__.py`, scripts, tests.

---

### PR-D — End-to-end Tobarra artifacts

**Scope**

- Full: resolve DEM → stack → physics → fit → hybrid audit.
- Artifacts under `outputs/fuel_stack/tobarra/`:
  - `fuel_terrain_stack.json` (`synthetic=false` if DEM real; geo meta present)
  - `dem_manifest.json`
  - `calibration_recipe_v1.json` (raw+cal metrics, dem_binding)
  - `physics_prior_tobarra.json` (raw ratios + recipe)
  - `build_report.json` with both metric classes
- Optional docs: mega-plan F2.3 → **🟡 engineering k recipe Tobarra (single-fire; not multi-IF)**; F1.1 note real DEM if applicable.
- Re-fit recipe after switching DEM source.

**Deps:** PR-A + PR-B + PR-C.

**DoD**

- `build_report.json` includes `dem.synthetic`, `metrics.raw_*`, `metrics.cal_*`, `no_tactical_dispatch`.
- Does **not** claim LOFO validation or silent mega-plan science pass from k alone.

---

### PR sizing / order

```
PR-A (offline DEM stack) → PR-B (opt-in download) → PR-C (calibration, honest metrics) → PR-D (e2e)
         ↘ PR-C can parallelize after PR-A (re-fit on real DEM in PR-D)
```

---

## 12. Example implementer sequences

### Offline / CI

```powershell
pytest tests/test_fuel_dem.py tests/test_fuel_calibration.py tests/test_fuel_rothermel_lite.py -q

# fixture path from test or pre-generated tiny dem
python scripts/build_fuel_terrain_stack.py --fire tobarra `
  --dem path\to\tobarra_tiny.tif `
  --with-physics --fit-calibration `
  --out outputs/fuel_stack/tobarra_ci
```

### Dev machine with network (opt-in)

```powershell
$env:WFD_ALLOW_DEM_DOWNLOAD = "1"
python scripts/build_fuel_terrain_stack.py --fire tobarra `
  --allow-download --save-geotiff --with-physics --fit-calibration `
  --fit-target observed_ros_head `
  --out outputs/fuel_stack/tobarra
# subsequent runs hit data/dem/tobarra/glo30_window.tif without env
```

### Apply frozen recipe only

```powershell
python scripts/run_rothermel_prior.py `
  --calibration-recipe outputs/fuel_stack/tobarra/calibration_recipe_v1.json `
  --out outputs/fuel_stack/tobarra/rothermel_prior_calibrated.json
```

---

## 13. Honesty checklist (ship gate)

- [ ] No writes to `infocam_anchors.json` Vp/ha
- [ ] `synthetic=true` only with explicit allow path
- [ ] Download only with opt-in flag/env
- [ ] Calibrated product claim string distinct
- [ ] `no_tactical_dispatch=true` on physics + hybrid
- [ ] ABSTAIN still on UNKNOWN fuel / missing wind
- [ ] Recipe includes honesty_notes + literature refs + dem_binding
- [ ] Raw and cal residual metrics both present
- [ ] `calibration` ratios remain pre-k
- [ ] Hybrid sector stability test with obs present
- [ ] Default pytest: zero network
- [ ] No vacuous “mega-plan KPI passed” from fit-to-obs alone
- [ ] F2.3 docs (if touched) say engineering single-fire, not LOFO-validated

---

## 14. References (in-repo)

- Mega-plan F1.1 / F2.3 / KPI: `docs/MEGA_PLAN_PREDICCION_ROS_VEGETACION_TERRENO.md`
- Corpus: `data/fire_intel/literature/corpus_v1.json` (`kim_2025_cell2fire`, `cardil_2023_ops_ros_bias`)
- Anchors: `data/infocam_anchors.json`
- STAC/COG pattern: `wildfire_front/open_if/stac_s2.py`
- Metric CRS convention: `wildfire_front/ops_perimeter.py` (`METRIC_CRS`)
- DEM gradient honesty (ML): `wildfire_front/ml/dataset.py` `_load_or_synthesize_dem`, `tests/test_dataset_dem_align.py`
- Hybrid obs-scale: `wildfire_front/fuel/hybrid.py` (lines ~82–91)
- Current uncalibrated artifact: `outputs/fuel_stack/tobarra/physics_prior_tobarra.json`
)
