# Design: Hybrid short-horizon envelope 15/30/60 min (F3 mega-plan) for Tobarra-class ops

| Field | Value |
|-------|--------|
| **Title** | Hybrid short-horizon envelope v3 (15/30/60 min) — F3 mega-plan |
| **Repo** | `C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics` |
| **Date** | 2026-07-31 |
| **Revised** | 2026-07-31 (post design-review issues 1–8) |
| **Mega-plan** | `docs/MEGA_PLAN_PREDICCION_ROS_VEGETACION_TERRENO.md` §Fase 3 (F3.1–F3.5) |
| **Predecessor** | Real DEM + k calibration shipped (`outputs/fuel_stack/tobarra/`, `DESIGN_DEM_REAL_CALIBRATION.md`) |
| **User cue** | `/loop-engineering sigue con la envolvente` |
| **Status** | Implemented 2026-07-31 (envelope v3 hybrid + ensemble + Tobarra smoke) |

---

## 1. Context

### 1.1 What already ships (ground truth in repo)

| Module / path | Role today | Relevance to F3 envelope |
|---------------|------------|---------------------------|
| `wildfire_front/emergency_products.py` | `compute_short_horizon_envelope` → product **`short_horizon_envelope_v2_sector`**; sector radii = ROS×horizon; cap **40 m/min**; `envelope_to_geojson` / `write_envelope_geojson` (circle + head/rear wedges); `enrich_ops_dict` attaches envelope; honesty NOT tactical | **v2 path stays**; do not break incident pipeline |
| `wildfire_front/cn_wang_zhengfei.py` | `polar_ros_ring`, `envelope_radii_m`, CN `hybrid_ros_prior` (obs magnitude × polar shape), `hybrid_polar_to_geojson_ring` | Polar ring geometry pattern for v3 optional polar output |
| `wildfire_front/fuel/hybrid.py` | Fuel-stack `hybrid_ros_prior`: α·obs + physics shape; sectors `head_m_min` / `flank_m_min` / `rear_m_min` / `primary_m_min`; ABSTAIN only if no obs **and** physics abstained; with obs + physics abstained → `estimated_obs_only` with **null sector values** | **Primary ROS source** for v3; envelope **must repair null sectors** (§5.5) |
| `wildfire_front/fuel/rothermel_lite.py` | Sector physics; **band_p10_p90** already from wind ×{0.8,1.0,1.2} × FMC ±2% (9 samples, head only) | Reuse ensemble grid; source for labeled **`physics_only`** band (§5.4) |
| `wildfire_front/fuel/calibration.py` | k recipe Tobarra; applies to physics product | Optional: calibrate physics nested inside hybrid (already wired) |
| `scripts/build_fuel_terrain_stack.py` | DEM → stack → optional physics+hybrid → `physics_prior_tobarra.json` | Extend with `--with-envelope` (PR-D); stack CLI wind defaults → force `weather_scenario_assumed=true` |
| `wildfire_front/incident/pipeline.py` | Writes `emergency_envelope.json` + `emergency_envelope_guidance.geojson` from **v2** via `enrich_ops_dict` | **Do not flip** default incident path to v3 in F3 PRs |
| `tests/test_emergency_products.py` | v2 radii, labels, geojson closed rings, cn_hybrid wind discipline | Pattern for v3 tests |
| `outputs/fuel_stack/tobarra/` | Real GLO-30 DEM, recipe, hybrid sectors (head≈5.71, flank≈2.63, rear≈1.65 m/min @ default args) | Smoke target |

### 1.2 Measured baseline (post DEM + k, Tobarra)

From `outputs/fuel_stack/tobarra/physics_prior_tobarra.json` (2026-07-31) and live hybrid ensemble checks:

| Quantity | Value |
|----------|-------|
| DEM source | `copernicus_glo30`, slope mean **~3.29°** |
| Observed primary ROS (CLI default) | **5.71 m/min** |
| Hybrid α_obs (age~20 min) | **~0.79** |
| Hybrid sectors head/flank/rear | **5.71 / ~2.63 / ~1.65 m/min** |
| Physics raw head / cal head | **~9.72 / 5.71 m/min** (k≈0.59) |
| Physics band head p10–p90 (cal) | **~4.51 – 7.14 m/min** |

**Implied v3 envelope radii at hybrid p50 (sectors × horizon), cap 40 m/min:**

| Horizon | head_m | flank_m | rear_m |
|---------|--------|---------|--------|
| 15 min | ~85.7 | ~39.4 | ~24.7 |
| 30 min | ~171.3 | ~78.9 | ~49.4 |
| 60 min | ~342.6 | ~157.7 | ~98.7 |

**Hybrid 3×3 ensemble with obs present (honest measured behavior):**

| Sector @ 15 min | p10 | p50 | p90 | Note |
|-----------------|-----|-----|-----|------|
| head_radius_m | **85.65** | **85.65** | **85.65** | Flat: hybrid locks head to obs (`head_p = ph*(obs/ph)=obs`) |
| flank_radius_m | **~38.4** | **~39.4** | **~40.9** | Tiny residual shape sensitivity |
| rear_radius_m | similar narrow | | | |

These are **engineering guidance distances**, not official perimeters. **Do not** publish wide fake head bands under hybrid ensemble when obs is present.

### 1.3 Gap this design closes

| Mega-plan ID | Intent | Today | This design |
|--------------|--------|-------|-------------|
| **F3.1** | Front × ROS_hybrid → envelope | v2 uses **obs quartile** sectors only; fuel hybrid not extruded | **v3 hybrid** radii from `fuel.hybrid` sectors (origin extrusion lite) |
| **F3.2** | α blend + audit | ✅ `fuel/hybrid.py` | Consume α into envelope audit trail |
| **F3.3** | Ensemble → p10/p50/p90 | Physics has head band only; **no envelope radii band** | **Hybrid** ensemble (may be flat on head when obs present) **+ required labeled `physics_only` band** for non-degenerate weather sensitivity (§5.4, K6) |
| **F3.4** | Tobarra light validation | Packs exist; no envelope scorecard | Light smoke: radii monotonic, product labels, optional vs v2 order-of-magnitude |
| **F3.5** | Decision Card reasons **without** ML fusion | field_ops still hard-off fusion | Export **reasons only** (optional thin attach); **never** flip `allow_ml_live_in_fusion` |

### 1.4 Honesty rails (non-negotiable)

1. Product always `not_tactical_dispatch` / `not_dispatch` / `not_official_perimeter`.
2. **Never invent wind 270° as ops truth** on paths that claim operator weather — match `enrich_ops_dict` discipline: physics-only / hybrid physics path requires **explicit** wind (or documented CLI scenario with `weather_scenario_assumed=true`).
3. **ABSTAIN** if no ROS obs **and** physics abstained; if wind missing on physics-only path (no obs).
4. Do **not** overwrite `infocam_anchors.json` Vp/ha; do not invent official Vp.
5. Do **not** flip field_ops ML fusion / decision policies.
6. Do **not** claim official perimeter or validated tactical dispatch.
7. Cap envelope ROS at **40 m/min** (same as v2 `_ENVELOPE_MAX_ROS_M_MIN`) for extrusion safety; physics ROS cap 120 remains for potential product only.
8. Ensemble is **engineering weather sensitivity** (9-scenario grid), **not** a climate model / probabilistic fire simulation.
9. **Never invent ensemble width**: when hybrid head is obs-locked, report **flat** p10=p50=p90 and set `obs_locked_sectors`; put non-degenerate weather sensitivity only under clearly labeled **`physics_only`** (not the hybrid p50 product radii).

---

## 2. Goals / Non-goals

### Goals

1. Ship product **`short_horizon_envelope_v3_hybrid`** that:
   - Consumes hybrid sector ROS (head/flank/rear/primary) from `fuel.hybrid.hybrid_ros_prior` (and/or a precomputed hybrid dict), with **null-sector repair** (§5.5).
   - Builds **15 / 30 / 60 min** envelopes: `radius = min(ros, 40) × horizon_min`.
   - Emits JSON radii table + audit (α, method, drivers, disclaimers ES/EN).
2. Optionally emit **polar / ellipse-class ring GeoJSON** in **EPSG:32630** meters about an origin (stack centroid, last main_front centroid, or CLI `--origin-xy`).
3. **Ensemble bands** (PR-C):
   - **Hybrid ensemble** (product path): 3×3 wind/FMC through `hybrid_ros_prior` → p10/p50/p90 radii; **expect flat head when obs present**.
   - **Physics-only ensemble** (diagnostic, required when ensemble enabled): re-run physics 9-grid (or scale `band_p10_p90`) → radii band **labeled not-p50-product**.
4. **ABSTAIN** rules as §1.4; status machine §4.1 / §5.5.
5. **Wire**:
   - Prefer new module `wildfire_front/fuel/envelope.py` (keep v2 untouched).
   - CLI `scripts/build_hybrid_envelope.py` and/or `build_fuel_terrain_stack.py --with-envelope`.
   - Artifacts under `outputs/fuel_stack/tobarra/envelope_*.json` + `.geojson`.
6. **Tests**: offline pure math; null hybrid sectors; flat head ensemble; optional geojson ring closed.
7. Mega-plan F3 status update (honest 🟡/✅) only in PR-D docs touch.

### Non-goals

- Replacing or breaking **v2** `short_horizon_envelope_v2_sector` in incident `emergency_envelope.json` (default path stays v2).
- Full Huygens / FARSITE / level-set front normal propagation (F3.1 **lite** = origin-extruded sector/polar envelope, not pixel mask CA).
- Multi-IF LOFO envelope validation (F4).
- Climate-scale ensembles, stochastic weather generators, ML residual U-Net on envelope.
- Flipping `field_ops` ML fusion or inventing GO from physics-only envelope.
- Official perimeter product or CEMS replacement.
- Changing `fuel.hybrid.hybrid_ros_prior` signature defaults (Q6: leave research defaults; envelope shields ops).

---

## 3. Architecture

### 3.1 Layering

```
┌─────────────────────────────────────────────────────────────────┐
│ CLI / scripts                                                    │
│  build_hybrid_envelope.py                                        │
│  build_fuel_terrain_stack.py --with-envelope                     │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│ fuel.envelope  (NEW)  product: short_horizon_envelope_v3_hybrid │
│  extract_sector_ros / obs_only_sector_recipe                    │
│  compute_hybrid_envelope(...)                                   │
│  ensemble_sector_ros_samples + physics_only band                │
│  hybrid_envelope_to_geojson(...) / write_*                      │
│  ellipse_polar_ring / radius_at_bearing                         │
└──────────────┬─────────────────────────┬────────────────────────┘
               │                         │
    ┌──────────▼──────────┐   ┌──────────▼──────────────────────┐
    │ fuel.hybrid         │   │ fuel.rothermel_lite             │
    │ hybrid_ros_prior    │   │ estimate_sector_ros_physics     │
    │ α, sectors, ABSTAIN │   │ band grid wind±20% FMC±2%       │
    └──────────┬──────────┘   └─────────────────────────────────┘
               │
    ┌──────────▼──────────┐   ┌─────────────────────────────────┐
    │ fuel.calibration    │   │ emergency_products (v2, KEEP)   │
    │ recipe k (optional) │   │ incident pipeline unchanged     │
    └─────────────────────┘   │ geo patterns reusable by import │
                              └─────────────────────────────────┘
```

**Design rule:** v3 lives under `fuel/` (physics/hybrid product line). v2 stays under `emergency_products` (ops observed-ROS product line). Sharing is **one-way**: `fuel.envelope` may import pure helpers from `emergency_products` (cap, circle ring) or reimplement tiny geometry to avoid coupling; incident pipeline does **not** auto-switch to v3.

### 3.2 F3.1 interpretation (honest scope)

Mega-plan wording: “normal al frente × ROS_hybrid → máscara/envolvente”.

**This design ships envelope extrusion, not front-normal mask:**

| Mode | Description | PR |
|------|-------------|-----|
| **A. Sector table** | head/flank/rear radii × horizons (required) | PR-A |
| **B. Sector GIS** | flank circle + head/rear wedges (reuse v2 geojson pattern) | PR-B |
| **C. Polar ring** | continuous ring from ellipse blend of head/flank/rear | PR-B |
| **D. Ensemble band** | hybrid p10/p50/p90 + labeled physics_only | PR-C |

True front-normal propagation from `main_front.geojson` vertices is **out of scope** for F3 PRs (future F3.1-full / F6 GIS). Document origin as **centroid / CLI xy**, not “perimeter evolution”.

### 3.3 Data flow (Tobarra smoke)

```
obs_ros=5.71, wind_10m_ms=4.4, wind_from=270, fmc=7, slope≈3.29°
  (CLI: --preset tobarra_scenario OR explicit wind + --weather-scenario-assumed)
        │
        ▼
hybrid_ros_prior(...)  → status, sectors {head_m_min,...}, α
        │
        ├─ status == abstained ──► envelope abstained
        │
        ▼
extract_sector_ros(hybrid, observed_ros=...)
  if any sector null + has obs → obs_only recipe (head=obs, flank=0.5*obs, rear=0.3*obs)
  if any sector null + no obs → abstain invalid_or_missing_sector_ros
        │
        ▼
radii_from_sector_ros(...) → envelopes[15,30,60]
        │
        ├─ with_ensemble + complete weather:
        │     hybrid 9-grid → often flat head; obs_locked_sectors=["head"]
        │     physics_only 9-grid → non-degenerate head band (diagnostic)
        │  incomplete weather → ensemble_meta.enabled=false, no invented wind
        │
        ▼
envelope_v3.json  +  envelope_v3.geojson (+ _utm.geojson if projected)
```

### 3.4 Relationship to CN polar hybrid

| Aspect | CN `cn_wang_zhengfei.hybrid_ros_prior` | Fuel `fuel.hybrid.hybrid_ros_prior` + v3 envelope |
|--------|----------------------------------------|--------------------------------------------------|
| Physics engine | Wang/Mao polar R0 | Rothermel-lite Med fuels |
| Magnitude | scale polar mean/head to **obs** | α blend + obs-scale shape when obs present |
| Wind defaults | functions accept default 270° | envelope kwargs default **None**; CLI scenario explicit |
| Envelope product | `envelope_radii_m` + `cn_hybrid_polar_envelope` | **`short_horizon_envelope_v3_hybrid`** |
| Use | research / optional `cn_hybrid=True` | Tobarra fuel-stack product line |

v3 **does not** depend on CN code at runtime; may **copy bearing conventions** (0=N +y, 90=E +x) and GeoJSON property patterns.

---

## 4. Data model

### 4.1 Schema: `short_horizon_envelope_v3_hybrid` (JSON)

Normative Tobarra-like example with **honest hybrid ensemble** (flat head) and **separate physics_only** diagnostic:

```json
{
  "schema": "short_horizon_envelope_v3_hybrid",
  "product": "short_horizon_envelope_v3_hybrid",
  "status": "inputs_assumed",
  "reason": null,
  "reasons": [
    "weather_scenario_assumed_not_live_met",
    "ensemble_hybrid_head_obs_locked"
  ],
  "not_tactical_dispatch": true,
  "not_official_perimeter": true,
  "not_dispatch": true,
  "label_en": "HYBRID short-horizon envelope (obs×physics) — NOT validated tactical dispatch, NOT official perimeter",
  "label_es": "Envolvente híbrida de horizonte corto (obs×física) — NO es despacho táctico validado ni perímetro oficial",
  "horizons_min": [15, 30, 60],
  "ros_cap_m_min": 40.0,
  "method": "hybrid_sector_extrusion_v1",
  "origin": {
    "xy_m": [612345.0, 4278901.0],
    "crs": "EPSG:32630",
    "source": "cli | stack_centroid | main_front_last_centroid | none"
  },
  "hybrid_audit": {
    "alpha_obs": 0.7889,
    "hybrid_method": "hybrid_obs_physics_v1",
    "hybrid_status": "estimated",
    "fuel_id": "MED_MAQUIS_LOW",
    "observed_ros_m_min": 5.71,
    "obs_age_minutes": 20.0,
    "weather_scenario_assumed": true,
    "wind_10m_ms": 4.4,
    "wind_from_deg": 270.0,
    "dead_fmc_pct": 7.0,
    "slope_deg": 3.294,
    "calibration_recipe_id": "tobarra_20240802_med_maquis_low_v1",
    "product_claim": "hybrid_orientation_with_uncertainty",
    "sector_source": "hybrid_sectors"
  },
  "sector_ros_m_min": {
    "head": 5.71,
    "flank": 2.6291,
    "rear": 1.6452,
    "primary": 5.1457
  },
  "envelopes": [
    {
      "horizon_min": 15,
      "head_radius_m": 85.65,
      "flank_radius_m": 39.44,
      "rear_radius_m": 24.68,
      "primary_radius_m": 77.19,
      "head_ros_m_min": 5.71,
      "flank_ros_m_min": 2.6291,
      "rear_ros_m_min": 1.6452,
      "primary_ros_m_min": 5.1457,
      "head_bearing_deg": 90.0,
      "ensemble": {
        "kind": "hybrid_engineering_wind_fmc_grid",
        "n_scenarios": 9,
        "obs_locked_sectors": ["head"],
        "head_radius_m": {"p10": 85.65, "p50": 85.65, "p90": 85.65},
        "flank_radius_m": {"p10": 38.39, "p50": 39.44, "p90": 40.88},
        "rear_radius_m": {"p10": 24.1, "p50": 24.68, "p90": 25.3},
        "note": "Hybrid head locked to observed ROS under obs-scale construction; flat band is expected, not a bug"
      },
      "ensemble_physics_only": {
        "kind": "physics_engineering_wind_fmc_grid",
        "not_product_p50": true,
        "label_en": "Physics-only weather sensitivity — NOT the hybrid product radii; orientation diagnostic",
        "label_es": "Sensibilidad meteorológica solo-física — NO son los radios del producto híbrido; diagnóstico",
        "n_scenarios": 9,
        "head_radius_m": {"p10": 67.64, "p50": 85.65, "p90": 107.16},
        "flank_radius_m": {"p10": null, "p50": null, "p90": null},
        "rear_radius_m": {"p10": null, "p50": null, "p90": null},
        "source": "estimate_sector_ros_physics_9grid_or_band_p10_p90_scaled"
      }
    }
  ],
  "ensemble_meta": {
    "enabled": true,
    "wind_factors": [0.8, 1.0, 1.2],
    "fmc_deltas_pct": [-2.0, 0.0, 2.0],
    "hybrid_ensemble": {
      "enabled": true,
      "obs_locked_sectors": ["head"],
      "note_en": "Hybrid 9-scenario band: residual shape sensitivity under α. With observed ROS, head is typically flat (p10=p50=p90). Not free weather uncertainty of unobserved fire. Not a climate ensemble.",
      "note_es": "Banda híbrida 9 escenarios: sensibilidad residual de forma bajo α. Con ROS observada, la cabeza suele ser plana (p10=p50=p90). No es incertidumbre libre de fuego no observado. No es ensemble climático."
    },
    "physics_only_ensemble": {
      "enabled": true,
      "required_when_with_ensemble": true,
      "not_product_p50": true,
      "note_en": "Physics-only engineering band (wind ±20%, FMC ±2%) for diagnostic width. Does not replace hybrid p50 radii.",
      "note_es": "Banda de ingeniería solo-física (viento ±20%, FMC ±2%) para ancho diagnóstico. No sustituye los radios p50 híbridos."
    }
  },
  "capped": false,
  "fire_id": "tobarra_20240802",
  "created_at": "ISO-8601"
}
```

**Note on physics_only numbers in example:** head p10/p50/p90 above use cal physics head band ~[4.51, 5.71, 7.14] × 15 when available from recipe path, or recompute 9-grid; flank/rear may be filled when full 9-grid sector samples exist. Implementers must **compute** from live physics, not hardcode example.

### 4.1.1 Status semantics (envelope product)

| envelope `status` | When | envelopes |
|-------------------|------|-----------|
| `ok` | Usable sectors; weather not flagged assumed | populated |
| `inputs_assumed` | Usable sectors **and** `weather_scenario_assumed` and/or origin assumed | **populated** + reasons |
| `abstained` | No usable sectors after repair; hybrid abstained; invalid ROS; physics-only path missing wind | `[]` + reason |
| `error` | Unexpected exception at boundary | `[]` |

### 4.1.2 Hybrid status → envelope status (normative map)

| `hybrid["status"]` | Sector values | Envelope outcome |
|--------------------|---------------|------------------|
| `abstained` | n/a | `status=abstained`, reason from hybrid / `no_obs_and_physics_abstained` |
| `estimated` | finite head/flank/rear | extract sectors; envelope `ok` **or** `inputs_assumed` if scenario flag |
| `estimated_obs_only` | often **all null** | **must** run obs-only recipe if `observed_ros` finite (§5.5); then `ok` / `inputs_assumed`; else abstain |
| missing hybrid, has obs, no wind | n/a | obs-only recipe inside envelope; reason `physics_skipped_no_wind` |
| missing hybrid, no obs, no wind | n/a | `abstained`, `no_obs_and_missing_wind` |

**Always** propagate hybrid `reasons` list into envelope `reasons` (append, do not drop).

Prefer **populated envelopes + `inputs_assumed`** when `weather_scenario_assumed=true` (not abstain).

### 4.1.3 Field naming vs hybrid vs v2 (normative map)

| Concept | Hybrid input key | Envelope product key | v2 envelope key |
|---------|------------------|----------------------|-----------------|
| Head ROS | `sectors.head_m_min` | `sector_ros_m_min.head` and per-horizon `head_ros_m_min` | `sector_ros_m_min.head` / `head_ros_m_min` |
| Flank ROS | `sectors.flank_m_min` | `sector_ros_m_min.flank` / `flank_ros_m_min` | same pattern |
| Rear ROS | `sectors.rear_m_min` | `sector_ros_m_min.rear` / `rear_ros_m_min` | same pattern |
| Primary ROS | `sectors.primary_m_min` | `sector_ros_m_min.primary` / `primary_ros_m_min` | `ros_m_min` isotropic |
| Head radius | — | `head_radius_m` | `head_radius_m` |
| Product id | — | `short_horizon_envelope_v3_hybrid` | `short_horizon_envelope_v2_sector` |

**v3 per-horizon ROS fields:** use **`head_ros_m_min` / `flank_ros_m_min` / `rear_ros_m_min`** (same as v2) — **not** `*_ros_m_min_used`. Drop the earlier draft `*_used` suffix for consistency.

**Aliases when reading hybrid:** accept only the hybrid keys above; if a caller passes a pre-normalized dict with short keys `head`/`flank`/`rear`, `extract_sector_ros` may accept both via:

```python
def _get_sector(sectors: Mapping[str, Any], name: str) -> float | None:
    # name in {"head","flank","rear","primary"}
    for key in (f"{name}_m_min", name):
        if key in sectors and sectors[key] is not None:
            v = float(sectors[key])
            if math.isfinite(v) and v >= 0:
                return v
    return None
```

**v2 compatibility:** do **not** set `product` to v2 name. Consumers that only know v2 must not silently treat v3 as v2.

### 4.2 GeoJSON FeatureCollection properties

Each feature:

```json
{
  "type": "Feature",
  "properties": {
    "product": "short_horizon_envelope_v3_hybrid",
    "horizon_min": 15,
    "sector": "flank_isotropic | head | rear | polar_p50 | polar_p10 | polar_p90 | physics_only_polar_p10 | physics_only_polar_p90",
    "radius_m": 39.44,
    "ros_m_min": 2.6291,
    "percentile": null,
    "not_official_perimeter": true,
    "not_tactical_dispatch": true,
    "not_dispatch": true,
    "not_product_p50": false,
    "label_en": "...",
    "label_es": "...",
    "fire_id": "tobarra_20240802",
    "crs_note": "EPSG:32630 meters (utm sibling) or WGS84 primary"
  },
  "geometry": { "type": "Polygon", "coordinates": [ /* closed ring */ ] }
}
```

Collection-level `properties` mirror envelope status, `n_features`, `center_xy`, product name. Physics-only rings must set `not_product_p50: true`.

### 4.3 Output paths (Tobarra convention)

| Artifact | Path |
|----------|------|
| Envelope JSON | `outputs/fuel_stack/tobarra/envelope_v3_hybrid.json` |
| GeoJSON WGS84 | `outputs/fuel_stack/tobarra/envelope_v3_hybrid.geojson` |
| GeoJSON UTM | `outputs/fuel_stack/tobarra/envelope_v3_hybrid_utm.geojson` |
| Optional polar-only | `outputs/fuel_stack/tobarra/envelope_v3_polar.geojson` |
| Build report hook | `build_report.json` → `paths.envelope`, `hybrid_envelope` summary |

Filenames may accept CLI `--tag` suffix later; defaults above are DoD for PR-D smoke.

### 4.4 Origin resolution order

1. Explicit `--origin-xy EASTING,NORTHING` (EPSG:32630 assumed unless `--origin-lonlat`).
2. `--origin-from-main-front path/to/main_front.geojson` → last ring centroid (`emergency_products.load_main_front_centroids`).
3. Stack bbox center projected to EPSG:32630 (from `FuelTerrainStack.bbox_wgs84` via existing geo helpers or simple mean lon/lat → UTM).
4. If none: JSON still valid **without** geometry (`origin.source=none`); GeoJSON write **abstains** geometry (`reason=no_center`) — same as v2 `envelope_to_geojson`.

---

## 5. APIs (concrete)

### 5.1 New module `wildfire_front/fuel/envelope.py`

```python
from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Mapping, Sequence

ENVELOPE_MAX_ROS_M_MIN = 40.0
DEFAULT_HORIZONS_MIN: tuple[int, ...] = (15, 30, 60)
PRODUCT_V3 = "short_horizon_envelope_v3_hybrid"

# Obs-only sector recipe (matches fuel.hybrid blend targets when physics missing)
OBS_FLANK_FRAC = 0.5
OBS_REAR_FRAC = 0.3


def cap_ros(ros_m_min: float, cap: float = ENVELOPE_MAX_ROS_M_MIN) -> float:
    ...


def obs_only_sector_ros(observed_ros_m_min: float) -> dict[str, float]:
    """head=obs, flank=0.5*obs, rear=0.3*obs, primary=obs; then clamp head>=flank>=rear."""
    ...


def extract_sector_ros(
    hybrid: Mapping[str, Any] | None,
    *,
    observed_ros_m_min: float | None = None,
) -> tuple[dict[str, float] | None, list[str]]:
    """Return ({head,flank,rear,primary}, reasons) or (None, reasons) if unusable.

    Reads hybrid['sectors']['head_m_min'] etc. If any null/non-finite and
    observed_ros finite → obs_only_sector_ros + reason hybrid_sectors_null_obs_only.
    """
    ...


def radii_from_sector_ros(
    head: float,
    flank: float,
    rear: float,
    *,
    primary: float | None = None,
    horizons_min: Sequence[int] = DEFAULT_HORIZONS_MIN,
    cap_m_min: float = ENVELOPE_MAX_ROS_M_MIN,
    head_bearing_deg: float | None = None,
) -> list[dict[str, Any]]:
    """Pure math: list of per-horizon radius entries (no I/O, no hybrid call).

    Per-horizon keys: head_radius_m, flank_radius_m, rear_radius_m,
    primary_radius_m, head_ros_m_min, flank_ros_m_min, rear_ros_m_min,
    primary_ros_m_min  (v2-aligned names; no *_used suffix).
    """
    ...


def compute_hybrid_envelope(
    hybrid: Mapping[str, Any] | None = None,
    *,
    # --- or build hybrid internally ---
    observed_ros_m_min: float | None = None,
    fuel_id: str = "MED_MAQUIS_LOW",
    wind_10m_ms: float | None = None,       # default None — never 4.4 silently
    wind_from_deg: float | None = None,     # default None — never 270 silently
    slope_deg: float = 5.0,
    dead_fmc_pct: float | None = None,      # required for ensemble; None ok for obs-only
    obs_age_minutes: float | None = 20.0,
    calibration_recipe: Any | None = None,
    dem_source: str | None = None,
    # --- envelope controls ---
    horizons_min: Sequence[int] = DEFAULT_HORIZONS_MIN,
    head_bearing_deg: float | None = None,
    origin_xy: tuple[float, float] | None = None,
    origin_source: str = "none",
    fire_id: str = "",
    with_ensemble: bool = False,
    weather_scenario_assumed: bool = False,
) -> dict[str, Any]:
    """Build short_horizon_envelope_v3_hybrid document.

    Wind discipline: kwargs default None. Never invent 270° / 4.4 m/s.
    Null hybrid sectors: repaired via obs_only_sector_ros when obs present.
    Ensemble: see §5.4 — requires complete weather inputs; else disabled.
    """
    ...


def resolve_ensemble_weather(
    hybrid: Mapping[str, Any] | None,
    *,
    wind_10m_ms: float | None,
    wind_from_deg: float | None,
    dead_fmc_pct: float | None,
    fuel_id: str | None,
    slope_deg: float | None,
    observed_ros_m_min: float | None,
) -> dict[str, Any] | None:
    """Return complete weather dict for ensemble or None if incomplete.

    Prefer explicit kwargs; else hybrid['physics']['drivers'] when all present.
    Never fill wind 270/4.4 when missing.
    """
    ...


def ensemble_sector_ros_samples(
    *,
    observed_ros_m_min: float | None,
    fuel_id: str,
    wind_10m_ms: float,
    wind_from_deg: float,
    slope_deg: float,
    dead_fmc_pct: float,
    obs_age_minutes: float | None,
    calibration_recipe: Any | None = None,
    dem_source: str | None = None,
    wind_factors: Sequence[float] = (0.8, 1.0, 1.2),
    fmc_deltas_pct: Sequence[float] = (-2.0, 0.0, 2.0),
) -> list[dict[str, float]]:
    """Hybrid path: list of {head,flank,rear,primary} ROS per scenario.

    After each hybrid call, run extract_sector_ros (null repair). Skip
    scenarios that still lack sectors.
    """
    ...


def physics_only_sector_ros_samples(
    *,
    fuel_id: str,
    wind_10m_ms: float,
    wind_from_deg: float,
    slope_deg: float,
    dead_fmc_pct: float,
    calibration_recipe: Any | None = None,
    dem_source: str | None = None,
    wind_factors: Sequence[float] = (0.8, 1.0, 1.2),
    fmc_deltas_pct: Sequence[float] = (-2.0, 0.0, 2.0),
) -> list[dict[str, float]]:
    """Physics-only 9-grid sector ROS (for diagnostic ensemble_physics_only)."""
    ...


def attach_ensemble_to_envelopes(
    envelopes: list[dict[str, Any]],
    hybrid_samples: list[dict[str, float]],
    physics_samples: list[dict[str, float]] | None,
    *,
    horizons_min: Sequence[int],
    cap_m_min: float = ENVELOPE_MAX_ROS_M_MIN,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Attach ensemble + ensemble_physics_only; set obs_locked_sectors when p10≈p90."""
    ...


def radius_at_bearing(
    delta_deg: float, head: float, flank: float, rear: float
) -> float:
    """Normative polar radius at angle delta from head bearing (deg). See §5.3."""
    ...


def ellipse_polar_ring(
    cx: float,
    cy: float,
    head_radius_m: float,
    flank_radius_m: float,
    rear_radius_m: float,
    head_bearing_deg: float,
    *,
    n: int = 72,
) -> list[list[float]]:
    """Closed ring via radius_at_bearing. Bearing 0=+y (N), 90=+x (E)."""
    ...


def hybrid_envelope_to_geojson(
    envelope: Mapping[str, Any],
    *,
    center_xy: tuple[float, float] | None = None,
    include_wedges: bool = True,
    include_polar: bool = True,
    include_ensemble_rings: bool = False,
    include_physics_only_rings: bool = False,
    fire_id: str = "",
) -> dict[str, Any]:
    ...


def write_hybrid_envelope_json(envelope: Mapping[str, Any], path: Path) -> None:
    ...


def write_hybrid_envelope_geojson(
    envelope: Mapping[str, Any],
    path: Path,
    *,
    center_xy: tuple[float, float] | None = None,
    write_wgs84: bool = True,
    **geo_kwargs: Any,
) -> dict[str, Any]:
    """Mirror emergency_products.write_envelope_geojson CRS behavior (UTM sibling)."""
    ...


def envelope_decision_reasons(envelope: Mapping[str, Any]) -> list[str]:
    """Honest reasons for Decision Card / briefing (F3.5 lite). No policy fusion."""
    ...
```

### 5.2 Pure extrusion math (normative)

For each sector ROS \(r\) and horizon \(h\) minutes:

\[
R = \min(r, R_{\mathrm{cap}}) \cdot h, \quad R_{\mathrm{cap}} = 40~\mathrm{m/min}
\]

Ordering enforced for readability (same as v2):

```text
head_ros >= flank_ros >= rear_ros  (after cap, clamp down the chain)
```

If hybrid already provides ordered sectors, re-assert clamp after cap.

**Primary radius:** `primary_ros × h` for isotropic reference; GIS default isotropic ring uses **flank** (v2 pattern) unless polar-only.

### 5.3 Polar / ellipse radius model (PR-B) — normative only

Given head bearing \(\beta\) (deg from north), for sample angle \(\theta\):

\[
\delta = ((\theta - \beta + 180) \bmod 360) - 180 \in [-180, 180]
\]

**Only** this implementation is normative (engineering polar, not Huygens):

```python
import math

def radius_at_bearing(delta_deg: float, head: float, flank: float, rear: float) -> float:
    d = math.radians(delta_deg)
    H = max(0.0, math.cos(d)) ** 2
    Rr = max(0.0, math.cos(d + math.pi)) ** 2
    s = H + Rr
    if s > 1.0:
        H, Rr = H / s, Rr / s
        F = 0.0
    else:
        F = 1.0 - s
    return head * H + flank * F + rear * Rr
```

**Edge checks (tests must assert within float tol):**

| \(\delta\) | Expected radius |
|------------|-----------------|
| 0° | **head** |
| ±90° | **flank** |
| ±180° | **rear** |

Ring construction: for `i in 0..n-1`, `θ = 360*i/n`, `δ = θ - head_bearing` (normalized to [-180,180]), `R = radius_at_bearing(δ, ...)`, then `x = cx + R*sin(θ)`, `y = cy + R*cos(θ)`; close ring with first point.

### 5.4 Ensemble (PR-C) — hybrid + physics_only

#### 5.4.1 Prerequisites (`with_ensemble=True`)

Required finite inputs (from kwargs **or** `hybrid["physics"]["drivers"]` when complete):

- `wind_10m_ms`, `wind_from_deg`, `dead_fmc_pct`, `fuel_id`, `slope_deg`

If incomplete:

```text
ensemble_meta.enabled = false
ensemble_meta.reason = "ensemble_missing_weather_inputs"
# Do NOT attach envelopes[*].ensemble or ensemble_physics_only
# Do NOT invent wind 270 / 4.4 / fmc 7
```

When calling with precomputed `hybrid` only (stack path): pull drivers from `hybrid["physics"]["drivers"]` if keys `wind_10m_ms`, `wind_from_deg`, `dead_fmc_pct`, `fuel_id`/`drivers.fuel_id`, `slope_deg` all present; else disable ensemble.

#### 5.4.2 Hybrid ensemble (product residual band)

For each pair `(wind_factor, fmc_delta)` in the 3×3 grid:

1. Call `hybrid_ros_prior(obs, wind_10m_ms=w0*wf, dead_fmc_pct=max(2, fmc+df), wind_from_deg=..., ...)`.
2. `sectors, _ = extract_sector_ros(hybrid_i, observed_ros_m_min=obs)` — **always** null-repair.
3. Collect sector ROS; skip if still missing.
4. For each sector and horizon: `R = min(ros, cap) * h`; percentiles p10/p50/p90.

**Expected Tobarra-with-obs behavior (normative honesty):**

- Hybrid construction: when `obs` and `ph>0`, `head_p = ph * (obs/ph) = obs`, so `blend(obs, head_p) ≡ obs` for all weather → **head p10 = p50 = p90**.
- Set `obs_locked_sectors: ["head"]` when `abs(p90-p10) < 1e-6` (or relative tol 1e-9 on radius).
- Flank/rear may show **small** residual width (order few percent) — report true values, do not inflate.

#### 5.4.3 Physics-only ensemble (required diagnostic when hybrid ensemble runs)

When hybrid ensemble is enabled and weather complete, **also** populate `envelopes[*].ensemble_physics_only` and `ensemble_meta.physics_only_ensemble`:

**Preferred:** full 9-grid via `estimate_sector_ros_physics` (or `ros_potential` head/flank/rear angles) with same wind/FMC factors → percentiles per sector.

**Fallback:** scale existing `PhysicsPriorResult.band_p10_p90["head_m_min"]` × horizon for head only; flank/rear null with reason `physics_band_head_only`.

Labels (required on block):

- `not_product_p50: true`
- `kind: physics_engineering_wind_fmc_grid`
- ES/EN note: diagnostic weather sensitivity; **does not replace** hybrid product radii

**Never** promote physics_only p50 into `head_radius_m` when obs hybrid path is active.

#### 5.4.4 F3.3 honesty for Tobarra-with-obs

| Band | Information content with obs | Product use |
|------|------------------------------|-------------|
| Hybrid ensemble head | **Zero width** (obs-locked) | Report honestly flat; reason `ensemble_hybrid_head_obs_locked` |
| Hybrid ensemble flank/rear | Small residual | Residual shape sensitivity under α |
| Physics-only head | Non-degenerate (~wind/FMC grid) | Diagnostic only; F3.3 “useful band” lives here when obs present |

Mega-plan F3.3 status after PR-D: **🟡** hybrid residual ensemble + physics_only diagnostic (not climate; not free head uncertainty under obs).

### 5.5 Sector extraction, ABSTAIN, wind discipline (normative algorithm)

```
inputs: hybrid dict | None, observed_ros, wind_10m_ms, wind_from_deg, ...

# --- obtain hybrid if needed ---
IF hybrid is None:
  has_obs = observed_ros is finite and > 0
  has_wind = wind_from_deg is not None AND wind_10m_ms is not None

  IF not has_obs AND not has_wind:
    → abstained, reason=no_obs_and_missing_wind

  IF not has_obs AND has_wind:
    → hybrid = hybrid_ros_prior(None, wind_..., ...)  # physics path
    IF hybrid.status == abstained → envelope abstained

  IF has_obs AND not has_wind:
    → DO NOT call hybrid_ros_prior expecting usable sectors
       (live code returns estimated_obs_only with sectors all null
        when wind_10m_ms=None and physics abstains)
    → sectors = obs_only_sector_ros(obs)
    → reasons += ["physics_skipped_no_wind"]
    → hybrid_audit.sector_source = "obs_only_envelope_recipe"
    → skip to radii (status ok unless weather_scenario_assumed)

  IF has_obs AND has_wind:
    → hybrid = hybrid_ros_prior(obs, wind_..., ...)  # pass explicit wind only

# --- extract / repair sectors ---
sectors, extract_reasons = extract_sector_ros(hybrid, observed_ros_m_min=observed_ros)
reasons += extract_reasons + (hybrid.reasons if hybrid else [])

IF sectors is None:
  → abstained, reason=invalid_or_missing_sector_ros

# extract_sector_ros detail:
#   read head = hybrid.sectors.head_m_min (or alias head)
#   if ANY of head/flank/rear is null/non-finite:
#     if observed_ros finite:
#       return obs_only_sector_ros(obs), ["hybrid_sectors_null_obs_only"]
#     else:
#       return None, ["invalid_or_missing_sector_ros"]
#   if hybrid.status == abstained: return None (caller already handled)

# --- status ---
IF weather_scenario_assumed:
  status = inputs_assumed
ELSE:
  status = ok

# --- ensemble ---
IF with_ensemble:
  weather = resolve_ensemble_weather(...)
  IF weather is None:
    ensemble_meta.enabled = false, reason=ensemble_missing_weather_inputs
  ELSE:
    hybrid_samples = ensemble_sector_ros_samples(**weather, observed_ros=...)
    physics_samples = physics_only_sector_ros_samples(**weather)
    attach both; set obs_locked_sectors as needed
```

**Never** set operational `wind_from_deg=270` or `wind_10m_ms=4.4` inside library defaults for `compute_hybrid_envelope`.

Contrast: `fuel.hybrid.hybrid_ros_prior` still has signature defaults 270/4.4 for research CLIs — **out of scope to change** (Q6). Envelope layer must pass explicit kwargs or skip calling hybrid when wind missing.

### 5.6 Exports from `fuel/__init__.py`

Add (PR-A/B):

```python
from .envelope import (
    PRODUCT_V3,
    compute_hybrid_envelope,
    radii_from_sector_ros,
    extract_sector_ros,
    obs_only_sector_ros,
    write_hybrid_envelope_json,
    # geojson writers in PR-B
)
```

Do not remove existing exports.

### 5.7 CLI `scripts/build_hybrid_envelope.py`

**No silent numeric wind defaults.** Wind is either omitted (obs-only path) or set explicitly / via preset.

```text
usage: build_hybrid_envelope.py [-h]
    [--fire tobarra]
    [--obs-ros 5.71]
    [--wind-ms FLOAT]          # optional; no default
    [--wind-from FLOAT]        # optional; no default
    [--fmc FLOAT]              # optional; no default (use with wind or preset)
    [--preset tobarra_scenario]
        # sets wind_ms=4.4, wind_from=270, fmc=7, weather_scenario_assumed=true
        # (and optionally slope/fuel from stack if present)
    [--weather-scenario-assumed]
        # required when --wind-ms/--wind-from provided without --preset
        # (makes status=inputs_assumed; fails closed if wind set without this flag
        #  OR without --preset — implementers: require flag for honesty)
    [--slope-deg FLOAT]        # default: from stack terrain if present, else error if physics needed
    [--fuel-id MED_MAQUIS_LOW]
    [--calibration-recipe PATH]
    [--dem-source ...]
    [--origin-xy E,N] [--origin-lonlat LON,LAT]
    [--origin-from-main-front PATH]
    [--horizons 15,30,60]
    [--with-ensemble]
    [--with-geojson / --no-geojson]
    [--include-polar] [--include-wedges]
    [--out-dir outputs/fuel_stack/tobarra]
```

**CLI honesty rules:**

1. If `--wind-ms` or `--wind-from` is set without `--preset` and without `--weather-scenario-assumed` → exit 2 with message requiring the flag (prevents looking like live met).
2. `--preset tobarra_scenario` sets scenario wind **and** forces `weather_scenario_assumed=true`.
3. Obs-only: pass `--obs-ros` without wind → valid; no 270 invented.
4. Ensemble requires wind+fmc (from preset or flags); else ensemble disabled with reason.

Exit codes:

| code | meaning |
|------|---------|
| 0 | ok, inputs_assumed, or intentional abstain written |
| 2 | bad args / unknown fire / wind without scenario flag |
| 3 | missing stack/recipe when required |
| 4 | error building envelope |

### 5.8 Flag on `build_fuel_terrain_stack.py`

```text
--with-envelope          # after hybrid, call compute_hybrid_envelope + write artifacts
--with-ensemble-envelope # implies ensemble on envelope (PR-C)
```

PR-D wires:

- If `--with-physics` and `--with-envelope`, reuse the same hybrid dict already computed (no double hybrid for p50).
- Stack CLI currently defaults `--wind-ms 4.4`, `--wind-from 270`: when wiring envelope, **always** pass `weather_scenario_assumed=True` into `compute_hybrid_envelope` (stack path is inherently scenario weather).
- For ensemble, pass the same CLI weather kwargs (complete → ensemble on; never re-default inside envelope).
- Origin: stack bbox center UTM or optional main_front path later.

### 5.9 Optional Decision Card reasons (F3.5 lite)

**Not** a fusion change. Thin helper `envelope_decision_reasons`.

Examples:

- `hybrid_envelope_ok_15_30_60`
- `hybrid_envelope_abstained:no_obs_and_physics_abstained`
- `weather_scenario_assumed_not_live_met`
- `ensemble_engineering_only`
- `ensemble_hybrid_head_obs_locked`
- `ensemble_physics_only_diagnostic`
- `ensemble_missing_weather_inputs`
- `hybrid_sectors_null_obs_only`
- `not_official_perimeter`

May be printed in CLI summary and stored under envelope `reasons`. **Do not** call policy engine or flip GO.

---

## 6. Failure modes

| Failure | Detection | Response |
|---------|-----------|----------|
| No obs + physics abstained | hybrid status | `status=abstained`, empty envelopes, reason propagated |
| Invalid ROS (NaN, negative) | finite check | abstain `invalid_ros` |
| Wind missing on physics-only (no obs) | explicit | abstain; never invent 270° |
| Wind missing but obs present | §5.5 | **obs-only recipe inside envelope** (do not trust hybrid null sectors); reason `physics_skipped_no_wind` |
| Hybrid `estimated_obs_only` with null sectors | extract_sector_ros | repair via obs-only if obs finite; else abstain |
| Cap hit | ros > 40 | `capped=true`; radii use 40 |
| No origin for GeoJSON | center_xy None | empty features + `no_center`; JSON radii still ok |
| Calibration recipe DEM mismatch | `CalibrationRefusedError` | CLI exit 4; do not silent force |
| `with_ensemble` but incomplete weather | resolve_ensemble_weather | `ensemble_meta.enabled=false`, reason `ensemble_missing_weather_inputs`; **no invented wind** |
| Ensemble all hybrid scenarios unusable | empty samples | disable hybrid ensemble block; physics_only may still attach if samples exist |
| Hybrid head flat under obs | p10≈p90 | report flat; `obs_locked_sectors=["head"]`; reason `ensemble_hybrid_head_obs_locked` |
| Double product confusion | consumer reads v2 name | v3 always distinct product string |
| Incident pipeline regression | tests | v2 tests green; v3 not auto-wired to emergency_envelope.json |
| Overclaim hybrid band as weather free uncertainty | labels | flat head + physics_only labeled `not_product_p50` |
| field_ops fusion accidentally enabled | out of scope | **do not touch** `config/decision_policies.json` |

---

## 7. Testing

### 7.1 New `tests/test_fuel_envelope.py` (offline, no network)

| Test | Assert |
|------|--------|
| `test_radii_from_sector_ros_basic` | 5.71/2.63/1.65 × 15 = expected rounded radii |
| `test_radii_ordering_head_ge_flank_ge_rear` | monotonic sectors after clamp |
| `test_ros_cap_40` | ros=100 → radius uses 40×h; `capped` true |
| `test_horizons_15_30_60` | three entries; linear scaling with h |
| `test_field_names_v2_aligned` | per-horizon has `head_ros_m_min` not `head_ros_m_min_used` |
| `test_extract_sector_ros_from_hybrid_keys` | reads `head_m_min` → product `head` |
| `test_null_hybrid_sectors_obs_only_repair` | hybrid dict status `estimated_obs_only` with all null sectors + obs=5.71 → radii from 5.71/2.855/1.713 |
| `test_abstain_no_obs_no_physics` | status abstained, envelopes [] |
| `test_no_invented_wind_ops_path` | `compute_hybrid_envelope(observed=None, wind_from_deg=None, wind_10m_ms=None)` abstains; no 270 in hybrid_audit |
| `test_obs_only_without_wind` | has obs, no wind → ok; reasons include `physics_skipped_no_wind`; finite radii |
| `test_product_name_v3` | `product == short_horizon_envelope_v3_hybrid` |
| `test_labels_not_dispatch_es_en` | ES+EN not-dispatch |
| `test_from_hybrid_dict` | pass full hybrid with finite sectors without re-running physics |
| `test_status_inputs_assumed_when_scenario` | weather_scenario_assumed → status inputs_assumed, envelopes populated |
| `test_hybrid_status_estimated_maps_ok` | hybrid estimated + no scenario → ok |
| `test_ensemble_head_flat_when_obs_present` (PR-C) | p10==p50==p90 for head within 1e-6; `obs_locked_sectors` contains `head` |
| `test_ensemble_p_order` (PR-C) | p10 ≤ p50 ≤ p90 for each sector that has samples |
| `test_ensemble_physics_only_present` (PR-C) | when ensemble enabled + weather complete → `ensemble_physics_only` with `not_product_p50` |
| `test_ensemble_disabled_missing_weather` (PR-C) | hybrid dict only, no drivers/weather kwargs → ensemble_meta.enabled false, no invented wind |
| `test_ensemble_meta_engineering_label` | notes mention engineering / not climate; physics_only notes present |
| `test_radius_at_bearing_edges` (PR-B) | δ=0→head, ±90→flank, ±180→rear |
| `test_geojson_ring_closed` (PR-B) | first==last; len≥4 |
| `test_geojson_properties_honesty` | not_official_perimeter, not_tactical_dispatch |
| `test_ellipse_head_longer_than_rear` | R(δ=0) > R(δ=180) when head>rear |
| `test_write_json_roundtrip` | tmp_path write/read |

### 7.2 Regression

- All existing `tests/test_emergency_products.py` stay green (v2 untouched).
- `tests/test_fuel_rothermel_lite.py`, `tests/test_fuel_calibration.py` unchanged behavior.

### 7.3 PR-D smoke (manual / optional subprocess)

```text
python scripts/build_hybrid_envelope.py --fire tobarra --with-ensemble \
  --preset tobarra_scenario \
  --calibration-recipe outputs/fuel_stack/tobarra/ros_calibration_recipe.json \
  --slope-deg 3.294
```

Expect:

- Files under `outputs/fuel_stack/tobarra/envelope_v3_*`
- Head 15 min radius ~85.65 m
- Hybrid ensemble head flat; physics_only head band non-degenerate when weather complete
- `weather_scenario_assumed: true`, status `inputs_assumed`

---

## 8. Key Decisions

| ID | Decision | Rationale |
|----|----------|-----------|
| **K1** | New module `fuel/envelope.py`; **do not** mutate v2 product | Isolates hybrid product line; prevents ops pack break |
| **K2** | Product id **`short_horizon_envelope_v3_hybrid`** | Distinct from v2 and `cn_hybrid_polar_envelope` |
| **K3** | F3.1 lite = **origin-extruded** sector/polar envelope, not CA mask | Shipable incremental; honest mega-plan partial |
| **K4** | Envelope ROS cap **40 m/min** (v2 parity) | Safety for GIS rings |
| **K5** | Ensemble grid = **same 3×3** as rothermel_lite (wind ±20%, FMC ±2%) | Reuse proven engineering band; **not climate** |
| **K6** | Hybrid ensemble is **product residual** path; with obs, **head is expected flat**. PR-C **requires** labeled **`ensemble_physics_only`** for non-degenerate weather width. Never invent hybrid head uncertainty. | F3.2+F3.3 honesty for Tobarra-with-obs |
| **K7** | Wind discipline at **envelope API**: defaults `None`; no silent 270°/4.4 | Match `enrich_ops_dict(cn_hybrid)` honesty |
| **K8** | GeoJSON CRS: WGS84 primary + `*_utm.geojson` sibling | Leaflet + QGIS UTM |
| **K9** | Polar shape = **`radius_at_bearing` cos² blend** only (normative §5.3) | Deterministic; edge tests at 0/±90/±180 |
| **K10** | Incident pipeline **stays on v2** | Avoid dual products in emergency_envelope.json without migration plan |
| **K11** | F3.5 = **reasons strings only**; no ML fusion / policy edits | Rails: field_ops fail-closed remains |
| **K12** | Prefer incremental PRs A→D | Pure math first; GIS; ensemble honesty; CLI/docs |
| **K13** | Null hybrid sectors → **obs-only recipe inside envelope** (`head=obs, flank=0.5*obs, rear=0.3*obs`) | Live hybrid returns nulls on `estimated_obs_only`; do not TypeError |
| **K14** | Per-horizon field names **v2-aligned** (`head_ros_m_min`, not `*_used`); map from hybrid `head_m_min` | Avoid KeyError / dual conventions |
| **K15** | CLI: no numeric wind defaults; use `--preset tobarra_scenario` or explicit wind + `--weather-scenario-assumed` | argparse cannot distinguish default vs user 270 |

---

## 9. Open Questions

| # | Question | Default if unresolved |
|---|----------|----------------------|
| Q1 | Should v3 ever replace v2 inside `incident/pipeline.py` `emergency_envelope.json`? | **No** in F3 |
| Q2 | Full physics polar (many bearings) vs ellipse blend for GIS? | **Ellipse blend** (K9); `--physics-polar` deferred |
| Q3 | When obs present, jitter **obs** (±IQR) for hybrid ensemble width? | **No** — do not silent-noise obs; flat head + physics_only diagnostic |
| Q4 | Default Tobarra origin if no main_front? | Stack bbox center UTM of TOBARRA_BBOX_WGS84 |
| Q5 | Attach v3 into `cli_report` / Decision Card pack? | PR-D optional print only |
| Q6 | Should `fuel.hybrid` drop default wind 270? | **Out of scope** for F3; envelope shields ops |
| Q7 | Multi-horizon FeatureCollection with ensemble rings? | Default: ensemble **numbers in JSON**; geojson p10/p90 only if `--include-ensemble-rings`; physics_only rings only if `--include-physics-only-rings` |
| Q8 | Physics_only flank/rear: full 9-grid vs head-only band fallback? | Prefer full grid; head-only fallback ok with null flanks |

---

## 10. PR Plan

### PR-A — Pure math envelope from hybrid sectors + tests

**Scope**

- Add `wildfire_front/fuel/envelope.py` with:
  - `cap_ros`, `obs_only_sector_ros`, `extract_sector_ros`, `radii_from_sector_ros`
  - `compute_hybrid_envelope` (no geojson, no ensemble required)
  - ABSTAIN / null-sector repair / wind discipline §5.5
  - Status map §4.1.2; field map §4.1.3
  - `write_hybrid_envelope_json`
- Export from `fuel/__init__.py`
- `tests/test_fuel_envelope.py`: pure math, labels, abstain, no invented wind, null hybrid sectors repair, field names

**DoD**

- `pytest tests/test_fuel_envelope.py -q` green
- v2 emergency tests still green
- Product name v3; ES/EN not-dispatch labels
- From hybrid dict Tobarra-like sectors → 15 min head radius ≈ 85.65 m
- Null-sector hybrid dict + obs → finite obs-only radii (not crash)

**Out of scope:** geojson, ensemble, scripts, mega-plan doc edits

---

### PR-B — Polar / sector GeoJSON + origin metric

**Scope**

- `radius_at_bearing`, `ellipse_polar_ring`, `hybrid_envelope_to_geojson`, `write_hybrid_envelope_geojson`
- CRS pattern from `emergency_products.write_envelope_geojson` / `geo_crs`
- Features: flank isotropic + head/rear wedges + polar p50 ring
- Origin resolution helpers
- Tests: edge angles, closed ring, honesty properties, head longer than rear

**DoD**

- Writing to tmp_path produces valid FeatureCollection
- UTM sibling when center looks projected
- No change to incident pipeline

---

### PR-C — Ensemble p10/p50/p90 (hybrid residual + physics_only)

**Scope**

- `resolve_ensemble_weather`, `ensemble_sector_ros_samples`, `physics_only_sector_ros_samples`, `attach_ensemble_to_envelopes`
- `with_ensemble=True` on `compute_hybrid_envelope`
- `ensemble_meta` hybrid + physics_only honesty labels
- Optional geojson ensemble / physics_only rings behind flags
- Tests: **flat head when obs present**, p-order, physics_only present + `not_product_p50`, ensemble disabled without weather (no invented wind)

**DoD**

- Tobarra-like call with ensemble:
  - hybrid head p10=p50=p90=85.65 (tol)
  - `obs_locked_sectors` includes `head`
  - `ensemble_physics_only` populated with non-degenerate head band when weather complete
- Notes state non-climate engineering band
- Runtime offline acceptable (< few seconds, ~9 hybrid + 9 physics)

**Out of scope:** claiming free head weather uncertainty under obs as hybrid product

---

### PR-D — CLI + Tobarra smoke + mega-plan F3 status

**Scope**

- `scripts/build_hybrid_envelope.py` with **no wind numeric defaults**, `--preset tobarra_scenario`, required scenario flag discipline
- `build_fuel_terrain_stack.py --with-envelope` (+ ensemble flag); force `weather_scenario_assumed=True` when using stack wind defaults
- Write `outputs/fuel_stack/tobarra/envelope_v3_hybrid.json` (+ geojson)
- Light F3.4 smoke
- Docs: update mega-plan F3 rows honestly:

| ID | Status after PR-D (proposed) |
|----|------------------------------|
| F3.1 | 🟡 origin-extruded hybrid envelope (not front-normal mask) |
| F3.2 | ✅ α in hybrid audit (pre-existing) consumed by v3 |
| F3.3 | 🟡 hybrid residual ensemble (head often flat with obs) + physics_only diagnostic band (not climate) |
| F3.4 | 🟡 Tobarra smoke / order-of-magnitude only |
| F3.5 | 🟡 reasons strings only; field_ops ML fusion still off |

- `envelope_decision_reasons` helper
- **Do not** edit `decision_policies.json` fusion flags
- **Do not** invent Vp/ha

**DoD**

- CLI exit 0 with `--preset tobarra_scenario --with-ensemble`
- Artifacts present; flat hybrid head + physics_only in JSON
- Mega-plan text does not claim full green F3 validation

---

## 11. Implementation sketch (reference only)

### 11.1 Minimal sector extract + radii

```python
def obs_only_sector_ros(observed_ros_m_min: float) -> dict[str, float]:
    obs = float(observed_ros_m_min)
    head = obs
    flank = min(obs * OBS_FLANK_FRAC, head)
    rear = min(obs * OBS_REAR_FRAC, flank)
    return {
        "head": round(head, 4),
        "flank": round(flank, 4),
        "rear": round(rear, 4),
        "primary": round(obs, 4),
    }


def radii_from_sector_ros(head, flank, rear, *, primary=None, horizons_min=(15, 30, 60),
                          cap_m_min=40.0, head_bearing_deg=None):
    h = min(float(head), cap_m_min)
    f = min(float(flank), h)
    r = min(float(rear), f)
    p = min(float(primary if primary is not None else f), cap_m_min)
    out = []
    for horizon in horizons_min:
        th = float(horizon)
        entry = {
            "horizon_min": int(horizon),
            "head_radius_m": round(h * th, 2),
            "flank_radius_m": round(f * th, 2),
            "rear_radius_m": round(r * th, 2),
            "primary_radius_m": round(p * th, 2),
            "head_ros_m_min": round(h, 4),
            "flank_ros_m_min": round(f, 4),
            "rear_ros_m_min": round(r, 4),
            "primary_ros_m_min": round(p, 4),
        }
        if head_bearing_deg is not None:
            entry["head_bearing_deg"] = round(float(head_bearing_deg) % 360.0, 2)
        out.append(entry)
    return out
```

### 11.2 Consuming existing hybrid (Tobarra)

```python
from wildfire_front.fuel.hybrid import hybrid_ros_prior
from wildfire_front.fuel.envelope import compute_hybrid_envelope

hybrid = hybrid_ros_prior(
    5.71,
    fuel_id="MED_MAQUIS_LOW",
    wind_10m_ms=4.4,
    wind_from_deg=270.0,
    slope_deg=3.294,
    dead_fmc_pct=7.0,
    calibration_recipe="outputs/fuel_stack/tobarra/ros_calibration_recipe.json",
    dem_source="copernicus_glo30",
)
env = compute_hybrid_envelope(
    hybrid,
    observed_ros_m_min=5.71,
    wind_10m_ms=4.4,
    wind_from_deg=270.0,
    dead_fmc_pct=7.0,
    slope_deg=3.294,
    fuel_id="MED_MAQUIS_LOW",
    with_ensemble=True,
    weather_scenario_assumed=True,
    head_bearing_deg=90.0,
    fire_id="tobarra_20240802",
)
# env["envelopes"][0]["ensemble"]["head_radius_m"]["p10"] == 85.65  # flat
# env["envelopes"][0]["ensemble_physics_only"]["not_product_p50"] is True
```

### 11.3 Module docstring rails

```text
Engineering hybrid short-horizon envelope (F3). NOT tactical dispatch.
NOT official perimeter. Hybrid ensemble head is often flat when obs present;
physics_only band is diagnostic only. Ensemble is weather sensitivity, not climate.
Does not replace emergency_products short_horizon_envelope_v2_sector.
Never invent wind 270° as ops truth.
```

---

## 12. Acceptance checklist (whole feature)

- [ ] `short_horizon_envelope_v3_hybrid` JSON with 15/30/60 head/flank/rear radii
- [ ] Hybrid α + sector ROS in audit; hybrid key map `*_m_min` → short keys
- [ ] Null hybrid sectors repaired via obs-only recipe when obs present
- [ ] ABSTAIN paths tested (no obs+physics fail; no invented wind)
- [ ] Optional polar/wedge GeoJSON EPSG:32630 + WGS84
- [ ] Hybrid ensemble honest (flat head with obs); physics_only diagnostic band
- [ ] CLI: no silent wind defaults; preset or scenario flag
- [ ] Tobarra outputs under `outputs/fuel_stack/tobarra/`
- [ ] v2 incident path unchanged
- [ ] field_ops ML fusion untouched
- [ ] Mega-plan F3 status honest (not over-green)
- [ ] Tests offline green

---

## 13. References (in-repo)

- `docs/MEGA_PLAN_PREDICCION_ROS_VEGETACION_TERRENO.md` — Fase 3
- `docs/DESIGN_DEM_REAL_CALIBRATION.md` — DEM + k predecessor
- `wildfire_front/emergency_products.py` — v2 envelope + geojson
- `wildfire_front/fuel/hybrid.py` — hybrid sectors + α; null sectors on estimated_obs_only
- `wildfire_front/fuel/rothermel_lite.py` — wind/FMC band grid
- `wildfire_front/cn_wang_zhengfei.py` — polar ring pattern
- `outputs/fuel_stack/tobarra/physics_prior_tobarra.json` — baseline numbers
- `data/infocam_anchors.json` — Vp 7.0 confirmed (read-only)
