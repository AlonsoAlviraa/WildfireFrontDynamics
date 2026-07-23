# Progressive Fire Growth Simulation from Official REDIAM Final Perimeters

| Field | Value |
|-------|--------|
| **Status** | IMPLEMENTED — core PSB v1 (Mode A/B, pack attach, gold Níjar, property tests) |
| **Date** | 2026-07-23 |
| **Revised** | 2026-07-23 (design-review ISS-001…014) |
| **Track** | Pista B+ · AND REDIAM open industrial + synthetic multi-stage growth |
| **Gold pack (reference)** | `outputs/open_if/and_2024040053_20240606` (Níjar · CODIGO `2024040053` · ~2169.34 ha) |
| **Related plans** | `docs/design/ANDALUCIA_REDIAM_INDUSTRIAL_E2E_PLAN.md` (IMPLEMENTED · `GO_AND_INDUSTRIAL_E2E`), `docs/design/DEMO_MULTI_CCAA_TOBARRA_NIJAR_CAMINOMORISCO.md` |
| **Acta baseline** | `docs/AND_INDUSTRIAL_E2E_VERIFICATION.md` |
| **Attribution (mandatory)** | Fuente: REDIAM — Junta de Andalucía. Uso libre con mención de autores y propietarios. |

---

## Overview

Andalucía REDIAM provides **institutional final perimeters** (IF >10 ha, WFS / Nextcloud, native CRS typically **EPSG:3042**) of excellent geometric quality, but **not** multi-day official perimeter series for events like Níjar 2024-06-06. The industrial open pack already closes the O2 gate (official polygon + FIRMS proxy + dNBR + scorecard HOLD). What is still missing for “test as if the fire were real and burning little by little” is a **controlled, fully labeled synthetic progressive burn timeline** whose **terminal stage is exactly the official REDIAM perimeter**.

This design specifies a **Progressive Synthetic Burn (PSB)** subsystem that:

1. Takes a **final official REDIAM polygon** (including **MultiPolygon** finals such as gold Níjar) as the hard geometric ceiling.
2. Synthesizes an ordered sequence of **strictly nested** intermediate burned footprints (stages) via morphological / buffer-ring / area-fraction growth.
3. Emits open_if-compatible artifacts under **`progressive/` only** (`progressive/timeline_progressive.geojson`, stage metrics, scorecard gates) with **honest provenance**: every stage is marked `synthetic_progressive_burn`, never as real LWIR, never as confirmed tactical Vp. Official `timeline_perimeters.geojson` stays pure REDIAM final.
4. Exercises the **same ops geometry stack** (`front_dynamics` bulk/equiv-radius ROS proxies, optional sector ROS) under deterministic and Monte Carlo stress — with an explicit **adapter contract** so fusion cannot invent grade-A ops ROS from synthetic rings.
5. Ships a **high-volume property / internal-loop test factory** (“millions of micro-assertions”) without million-node pytest collection or million-minute CI.

**One-line product message (honest):**

> With perfect official final perimeters (REDIAM), we regenerate a **synthetic multi-stage growth history** that ends exactly on the institutional polygon, so we can unit-stress front dynamics, Hausdorff stage-to-stage, and open pack gates — **without inventing real multi-day O2 or tactical ROS**.

---

## Goals / Non-goals

### Goals

| ID | Goal |
|----|------|
| G1 | **Terminal fidelity:** final synthetic stage ≡ official REDIAM perimeter (exact geometry copy in pack CRS; equal-area ha QA within tolerance in metric CRS). |
| G2 | **Monotone growth:** area non-decreasing; each stage geometrically contained in the next (nested burn, optional controlled exception modes documented). |
| G3 | **Multi-step timeline:** configurable `n_stages ∈ [3, 64]` (default **12**) with explicit fractional area schedule or buffer schedule; reject outside range. |
| G4 | **Ops-stack exercise:** convert stages → `FrontObservation` sequence and run `front_dynamics` bulk estimators (`area_isotropic`, `equiv_radius`) as **proxy ROS**, labeled synthetic; never ops grade A. |
| G5 | **Pack integration:** extend AND open_if packs (gold Níjar first) with progressive layers + scorecard gates without breaking `GO_OPEN_AND_O2`. |
| G6 | **Massive tests:** property tests + internal-loop micro-assertions + seeded Monte Carlo → order of **10⁵–10⁶ assertions** in CI-friendly time (seconds–minutes, not hours); PR CI uses reduced grid ≥10⁴ asserts. |
| G7 | **Honesty by construction:** schemas, briefs, maps, and decide path never claim synthetic stages are LWIR or ASEMA-confirmed Vp. |
| G8 | **Reproducibility:** pure functions + seeds; one Makefile/script path rebuilds progressive layer on gold pack offline. |
| G9 | **Multipolygon-first:** gold Níjar (5-part MultiPolygon) is a first-class acceptance path (KD13), not a footnote. |

### Non-goals

| ID | Non-goal |
|----|----------|
| NG1 | Reconstruct the **true** multi-day Níjar fire history (no official intermediate O2 series). |
| NG2 | Produce **tactical dispatch** ROS / Vp / 15–30–60 min envelopes sold as field-validated for INFOCA/ASEMA. |
| NG3 | Replace Tobarra OPS gold (LWIR + confirmed Vp) or claim PSB ≡ thermal multi-frame. |
| NG4 | Full FARSITE / FlamMap / fuel–weather physics (optional future wind-biased morph is stretch only). |
| NG5 | Million slow **end-to-end** network or raster integration tests in CI. |
| NG6 | Invent ASEMA anchors or write Vp into `manifest.json` / `infocam_anchors.json` as `confirmed`. |
| NG7 | Treat FIRMS hull area as official burned ha (already forbidden on industrial scorecard). |
| NG8 | Merge synthetic stages into official `timeline_perimeters.geojson` without `layer_role` (forbidden; stages only under `progressive/`). |

---

## Current architecture

### Dual product + open industrial path

System is dual-product (`ARCHITECTURE.md`):

- **OPS geometry:** `wildfire_front/front_dynamics.py` (coreg, dual/triple ROS estimators, quality fusion), `geometry_speed.py`, `emergency_products.py` (`compute_sector_ros`, short-horizon envelope), `scientific_ops.py` (morphological mask clean, area helpers, `MAX_PLAUSIBLE_SPEED_M_MIN = 60.0`).
- **ML:** CLM ensemble / NDWS — **orthogonal** to this design; PSB must not train on fused labels or claim ML IoU from synthetic burn stages.
- **Open packs:** `wildfire_front/open_if/*` (timeline daily merge, dNBR/STAC helpers) + builders under `scripts/`.

Hard rule preserved: **do not mix drone ROS claims with ML IoU; do not invent tactical Vp.**

### AND REDIAM industrial stack (already implemented)

```
[A] fetch_rediam_perimeters.py
[B] inventory_rediam_and.py
[C] selection_gold.json
[D] build_and_if_pack.py  →  outputs/open_if/and_<codigo>_<fecha>/
[E] metrics_o2.json  (area, FIRMS hull proxy, Hausdorff method, dNBR)
[F] scorecard_and_industrial.json
[G] decide HOLD (open-only) + operator_brief_open_if.md
[H] verify_and_industrial_e2e.py
[I] tests/test_and_if_pack.py (+ fixtures rediam_and)
```

**Gold Níjar pack** (`and_2024040053_20240606`):

| Field | Value |
|-------|--------|
| Municipio / provincia | NÍJAR / Almería |
| FECHA_INC | 2024-06-06 |
| area_rediam_ha | **2169.34** (equal-area EPSG:6933 from WGS84) |
| crs_native | EPSG:3042 |
| Geometry type | **MultiPolygon, 5 parts** (not a simple polygon) |
| Component areas (EPSG:6933) | ≈ **1099.96**, **1060.96**, **3.19**, **3.01**, **2.22** ha |
| Dual-lobe gap | ~**826 m** between the two large lobes |
| Centroid vs body | Global multipolygon **centroid lies outside** \(F\); `representative_point()` is inside |
| FIRMS | 85 hotspots; hull proxy; IoU buffer vs REDIAM ~0.48 |
| dNBR | GO (status present) |
| Verdict | `GO_OPEN_AND_O2` · decision_open **HOLD** |
| vp_tactical | **null** (request ASEMA for O1) |
| Key vectors | `vectors/perimeter_rediam.geojson`, native 3042 twin, FIRMS, firms_hull_proxy |

**Honesty already in pack:**

- FIRMS hull ≠ official burned area  
- No invented Vp  
- Attribution REDIAM/Junta on brief, map, scorecard, provenance  

### Firms, open_if, front_dynamics (roles relative to PSB)

| Component | Current role | PSB role |
|-----------|--------------|----------|
| **REDIAM perimeter** | Single final O2 MultiPolygon | **Ceiling geometry** and stage \(N-1\) exact copy |
| **FIRMS** | Hotspot cloud + convex hull **proxy**; Hausdorff method GO | Optional **ignition / growth seed** bias (centroid of early hotspots); never redefine final area |
| **open_if timeline** | `timeline_perimeters.geojson` = pure official final | **Stays pure.** Synthetic stages only in `progressive/timeline_progressive.geojson` |
| **front_dynamics** | Built for LWIR multi-frame observations | Consume synthetic stage rings as `projected_metric` observations; bulk ROS only as **proxy_synthetic**; see adapter contract |
| **emergency_products.sector_ros** | Head/flank/rear from bulk ROS (`method: bulk_ros_quartile_split`) | Optional demo-only; **wrap** method string to `bulk_ros_quartile_split_synthetic`; envelope `not_official_perimeter: true` |
| **synthetic.py** | Expanding noisy ellipses for pipeline demos | Orthogonal primitive; PSB is **perimeter-constrained reverse growth**, not free ellipse |
| **cn_cellular_ca.py** | Research CA sanity | Optional alternative growth engine later; **not** v1 default |

### Gap this design closes

| Need | Today | After PSB |
|------|-------|-----------|
| Multi-day official series Níjar | **None** | Synthetic stages **explicitly labeled** |
| Stress front_dynamics without LWIR AND | Not available | Yes, offline |
| Stage-to-stage Hausdorff / area growth curves | N/A | First-class metrics |
| “Millions of tests” on growth invariants | Sparse pack tests | Property + Monte Carlo factory |
| Multipolygon reverse growth on real gold | Untested | KD13 + PR5 acceptance |

---

## Proposed design

### Product identity

| Field | Value |
|-------|--------|
| Product / schema | `progressive_synthetic_burn_v1` |
| Catalog / track | Open industrial AND; **not** `front_dynamics_v1` ops gold |
| Ops method string | `proxy_ros_from_synthetic_stages` |
| Limitation tags | `synthetic_observation`, `not_real_lwir`, `not_official_intermediate_o2`, `no_tactical_vp` |

### High-level flow

```
                    official REDIAM final polygon (O2)
                    (Polygon | MultiPolygon; gold Níjar = 5 parts)
                                 │
                                 ▼
              ┌──────────────────────────────────────┐
              │  PSB engine (metric CRS, shapely)    │
              │  modes: area_fraction | buffer_rings │
              │         | morphological_growth       │
              │  multipolygon policy KD13            │
              └──────────────────┬───────────────────┘
                                 │ stages[0..N-1] nested
                                 ▼
    progressive/timeline_progressive.geojson + metrics_progressive.json
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
     open_if pack attach   FrontObservation[]   property tests
     manifest artifacts    front_dynamics       Monte Carlo
     scorecard PSB_*       (proxy ROS only)
```

### Module placement (proposed)

```
wildfire_front/
  progressive_burn/
    __init__.py
    schemas.py          # stage props, pack artifact names, honesty constants
    geometry.py         # CRS helpers, area_ha, ensure_valid, nested checks, multipolygon policy
    schedules.py        # area fraction schedules, dt grids, n_stages validation
    engines.py          # AreaFractionEngine, BufferRingEngine, MorphGrowthEngine
    pipeline.py         # final_geom → StageSequence
    to_observations.py  # StageSequence → list[FrontObservation] (adapter contract)
    metrics.py          # area growth, ROS proxy (units match front_dynamics), Hausdorff, gates
    pack_attach.py      # write progressive/* + manifest registration
scripts/
  build_progressive_burn.py       # CLI: pack or geojson → progressive layer
  verify_progressive_burn_e2e.py  # gold Níjar + fixture gates
tests/
  test_progressive_burn_unit.py
  test_progressive_burn_properties.py   # high-volume internal loops
  test_progressive_burn_pack.py
  fixtures/progressive_burn/            # tiny synthetic polygons (incl. multipolygon)
```

Keep `scripts/build_and_if_pack.py` thin: optional flag `--progressive-burn` calls into `pack_attach` rather than reimplementing geometry.

### Data model

**Stage record (logical):**

```json
{
  "stage_index": 0,
  "n_stages": 12,
  "area_fraction_target": 0.08,
  "area_fraction_actual": 0.0794,
  "area_ha": 172.3,
  "area_m2": 1723000.0,
  "time_s": 0.0,
  "dt_s_to_next": 3600.0,
  "engine": "area_fraction_erode_recover",
  "synthetic": true,
  "not_real_lwir": true,
  "not_official_intermediate_o2": true,
  "source_final": "REDIAM",
  "codigo": "2024040053",
  "n_components": 2,
  "attribution": "Fuente: REDIAM — Junta de Andalucía. …"
}
```

**StageSequence (JSON summary `metrics_progressive.json`):**

```json
{
  "schema": "progressive_synthetic_burn_v1",
  "pack_id": "and_2024040053_20240606",
  "codigo": "2024040053",
  "engine": "area_fraction_erode_recover",
  "n_stages": 12,
  "area_final_ha": 2169.34,
  "area_final_source": "rediam_official",
  "final_geom_type": "MultiPolygon",
  "final_n_parts": 5,
  "terminal_identity": {
    "exact_copy_pack_crs": true,
    "wkt_hash_match": true
  },
  "terminal_metric_qa": {
    "iou_vs_official": 1.0,
    "hausdorff_m": 0.0,
    "area_rel_err": 0.0
  },
  "monotone_area": true,
  "nested_geometry": true,
  "simplify_tolerance_m": null,
  "proxy_ros": {
    "status": "synthetic_proxy_only",
    "ops_cap_m_min": 60.0,
    "pairs": []
  },
  "honest_notes": [
    "Stages are synthetic reverse-growth from final REDIAM perimeter",
    "Not multi-day official O2",
    "Not LWIR / Heligrafics",
    "ROS figures are geometric proxies only; no tactical Vp"
  ],
  "vp_tactical": null,
  "attribution": "Fuente: REDIAM — Junta de Andalucía. …"
}
```

**GeoJSON features:** each stage as Polygon/MultiPolygon in pack CRS (WGS84 for pack consistency) + optional metric twin for precision QA. Multipart stages emit **all retained exteriors** (not largest-only).

### Pack layout extension (gold AND)

```
outputs/open_if/and_2024040053_20240606/
  … existing industrial artifacts …
  timeline_perimeters.geojson           # OFFICIAL final only — never mixed with synthetic stages
  progressive/
    timeline_progressive.geojson        # FeatureCollection stages 0..N-1 (ONLY progressive timeline)
    metrics_progressive.json
    scorecard_progressive.json          # sub-gates PSB_*
    front_dynamics_progressive.json     # optional adapter output
    map_progressive_overlay.js|snippet  # optional Leaflet layer source
  manifest.json                         # artifacts map gains progressive_* keys; optional progressive_synthetic_burn block
```

**Hard consumer rule (KD3):**

- Official final vs synthetic stages are **never mixed** in the same FeatureCollection without an explicit `layer_role` discriminator — and v1 **does not** merge into `timeline_perimeters.geojson` at all.
- Consumers read official final from industrial vectors / `timeline_perimeters.geojson`.
- Consumers read synthetic stages **only** from `progressive/timeline_progressive.geojson`.

### Integration with open_if packs

1. **Post-build attach:** after `build_and_if_pack.py` succeeds, run  
   `python scripts/build_progressive_burn.py --pack outputs/open_if/and_2024040053_20240606 --n-stages 12 --engine area_fraction`.
2. **Manifest registration (required on attach):**
   - `manifest["artifacts"]["progressive_timeline"] = "progressive/timeline_progressive.geojson"`
   - `manifest["artifacts"]["progressive_metrics"] = "progressive/metrics_progressive.json"`
   - `manifest["artifacts"]["progressive_scorecard"] = "progressive/scorecard_progressive.json"`
   - Optional: `manifest["artifacts"]["progressive_front_dynamics"] = "progressive/front_dynamics_progressive.json"`
   - `manifest["progressive_synthetic_burn"] = { "schema": "progressive_synthetic_burn_v1", "verdict": "...", "n_stages": N, "engine": "..." }`  
     **without** changing `vp_tactical`, `scorecard_verdict`, or industrial gates.
   - `provenance.json` may record PSB engine/seed/version as an additive lineage entry.
3. **Brief addendum:** append a short section to `operator_brief_open_if.md` **or** write `progressive/brief_progressive_addendum.md` linked from progressive scorecard. Text must state synthetic growth + REDIAM final attribution. Prefer **append section** when `--progressive-burn` is on the industrial builder; standalone CLI may write the side file.
4. **Decide path:** progressive pack **never** upgrades open decision from HOLD → GO field_ops. Industrial scorecard builders and `decide_service` **must not** read progressive ROS as O1 / tactical Vp. Scorecard flag `synthetic_stages_present: true` is informational only.
5. **Selection multi-IF:** apply to silver packs with same engines for regression diversity (different shapes: elongated, multipolygon, coastal irregularity).
6. **Commander / demo portal (optional):**  
   - `scripts/build_demo_multi_ccaa.py` / portal: optional “play stages” for Níjar with banner **SYNTHETIC GROWTH — ends on REDIAM official**.  
   - `scripts/build_commander_app.py` can list `progressive/timeline_progressive.geojson` if present; default off until PR demo.

### Integration with front_dynamics (normative adapter contract — PR2)

Live API notes (repo-verified):

- `run_front_dynamics(..., enable_coreg=True)` by default — coreg can shift nested synthetic rings.
- Always runs `estimate_geometry_speeds`; `_fuse_ros` can select `normal_ray` and can assign **`pair_quality "A"`** when `coreg_shift_m < 8` and ≥2 candidates.
- There is **no** `disable_normal_ray` flag today.
- `FrontObservation` requires `coordinate_system in {projected_metric, local_cartesian_m}`, closed-enough rings (**≥4 distinct samples**), and for `projected_metric` a positive `resolution_m`.
- Bulk formulas in `_pair_area_ros` use **m² and minutes** via `observation_area_m2` / `dt_min`.

**Exact recipe for `to_observations.py` + metrics path (PR2):**

1. **Coordinates:** `coordinate_system="projected_metric"`, `crs="EPSG:6933"`, `resolution_m` set (default **10.0** m, or stage simplify tolerance if simplify is on).
2. **Coreg:** call `run_front_dynamics(..., enable_coreg=False)` so nested rings are not translated.
3. **Primary ROS policy (choose one; both acceptable, document which in metrics):**
   - **Preferred A — post-process force bulk:** after `run_front_dynamics`, force each pair’s exported `primary_method` ∈ `{area_isotropic, equiv_radius}`; strip normal medians from primary selection; recompute primary from bulk fields only.
   - **Preferred B — bulk-only metrics path:** compute proxy pairs in `metrics.py` by calling the same helpers as ops (`observation_area_m2`, perimeter helpers, formulas below) and call `run_front_dynamics` only as **smoke** with documented limitations (normals may appear in raw dump but are not product primary).
4. **Quality cap:** exported `pair_quality` / `structural_grade` capped to **≤ `"B"`**; product label `synthetic_research` (never claim ops grade **A** from PSB alone). Aligns with honesty H8.
5. **Rings:** ensure ≥4 distinct samples per exterior after densify/simplify policy; first==last optional per `FrontObservation` conventions; emit **all retained exteriors** as `components` (summed area/perimeter for bulk ROS — **not** largest-only by default).
6. Set `method="synthetic_progressive_burn"`, limitations including honesty tags; `dt_assumed: true`.
7. Persist `progressive/front_dynamics_progressive.json` when the smoke/adapter path runs.

**Sector ROS wrap (ISS-011):**

```python
sector = {
    **compute_sector_ros(primary_ros_m_min, p25, p75, n_estimates=n),
    "method": "bulk_ros_quartile_split_synthetic",
    "synthetic": True,
}
# Keep short-horizon envelope not_official_perimeter: true
```

`compute_sector_ros` hardcodes `"method": "bulk_ros_quartile_split"`; callers **must** override in the dict copy. Easy to forget — unit-test the wrap.

---

## Algorithm details

All engines operate in a **metric projected CRS** (default **EPSG:6933** equal-area; alternative local center-azimuthal for ROS m/min). Input final geometry is validated (`buffer(0)` fix), non-empty, area ≥ min_ha.

### KD13 — Multipolygon policy (mandatory)

Gold Níjar is a **5-part MultiPolygon** (~1099.96 + 1060.96 + 3.19 + 3.01 + 2.22 ha). Global multipolygon **centroid lies outside** \(F\); dual lobes are separated by ~826 m. Any design that scales about multipolygon centroid will break nesting and fraction targeting.

| Rule | Normative behavior |
|------|--------------------|
| **M1 Homothety center** | Prefer `representative_point()` (or **largest-component** centroid). **NEVER** use multipolygon centroid for global homothety. |
| **M2 Mode A primary** | Prefer **global morphological erode** on the full MultiPolygon (`shapely.buffer(-d)` on the whole \(F\)). Spot-checked: erode 50–500 m yields nested multiparts on Níjar. |
| **M3 Homothety fallback** | Per-component homothety only when global erode empties or misses fraction band; scale each retained component about its own representative point / component centroid, **proportional to its share of \(A(F)\)**, then union and clip to \(F\). |
| **M4 Tiny components** | Components with area &lt; `min_component_area_ha` (default **1–5 ha**, config `min_component_area_ha=2.0`) may be empty / omitted until late stages or appear only at **terminal exact copy**. If early stages drop them, set PARTIAL reason `micro_components_deferred`. |
| **M5 Observations** | `to_observations` emits **all retained exteriors** as `components`; bulk area/perimeter are **sums** over components. Largest-only is opt-in (`main_front_only=False` by default). |
| **M6 PR5 acceptance** | Nested multipolygon stages on **real Níjar** gold pack, not only fixtures. |

Document in metrics: `final_geom_type`, `final_n_parts`, `components_dropped_early` if any.

### Common invariants (all engines)

Let \(F\) be the official final geometry, \(S_0, S_1, \ldots, S_{N-1}\) stages with \(S_{N-1} = F\) as **exact copy** in pack CRS.

| Invariant | Definition | Default tolerance / gate |
|-----------|------------|---------------------------|
| **Terminal identity (pack CRS)** | \(S_{N-1}\) is an exact geometry copy of official pack geometry | Gate `PSB_TERMINAL_IDENTITY`: same WKT/hash or object-equality after normalize; **no** re-buffer |
| **Terminal metric QA** | Optional twin compare in EPSG:6933 | Gate `PSB_TERMINAL_METRIC_QA`: IoU ≥ 0.999, Hausdorff ≤ 1 m (or 0.1% of \(\sqrt{A}\)), \(\lvert A(S_{N-1})-A(F)\rvert / A(F) \le 10^{-4}\) — used for CRS round-trip only |
| **Area monotone** | \(A(S_i) \le A(S_{i+1})\) | allow equality only if documented; strict increase preferred for fractions |
| **Nested** | \(S_i \subseteq S_{i+1}\) (within snap tolerance) | max exterior leak ≤ 1 m buffer |
| **Inside final** | \(S_i \subseteq F\) | same |
| **Fraction band (Mode A interior)** | \(\lvert f_{\mathrm{actual}} - f_{\mathrm{target}}\rvert \le \max(0.02,\ 0.05·f_{\mathrm{target}})\) | terminal \(f=1\) via exact copy (not band search) |
| **Valid geometry** | simple or fixed multipolygon | shapely `is_valid` after fix |
| **Honest props** | every feature carries synthetic flags | schema validation |
| **n_stages** | \(N \in [3, 64]\) | reject outside with clear `ValueError` |

If nesting clip / component drop moves area outside the fraction band → document fallback + PARTIAL reason `fraction_miss_after_nest_fix`.

### Mode A — Area-fraction reverse growth (default / recommended v1)

**Idea:** choose target fractions \(0 < f_0 < f_1 < \ldots < f_{N-1}=1\). For each \(f_i\), find a set \(S_i \subset F\) with \(A(S_i) \approx f_i A(F)\) that grows toward \(F\).

**Practical construction (erode-then-recover):**

1. Compute characteristic radius \(R = \sqrt{A(F)/\pi}\) (total multipolygon area).
2. Build a sequence of **erosion distances** \(d_k\) (binary search) such that  
   \(A(\mathrm{erode}(F, d_k)) / A(F) \approx f_k\) for interior stages.  
   Use `shapely.buffer(-d)` on the **full MultiPolygon** (KD13 M2).
3. If erosion empties or fragments below min area / misses fraction band, fall back to **per-component** similarity (homothety about each component’s `representative_point()` or component centroid — **never** multipolygon centroid), proportional to share of \(A(F)\), clipped to \(F\) (KD13 M1/M3).
4. Enforce nesting: \(S_i = S_i \cap S_{i+1}\) after generating from large to small or rebuild forward by cumulative union of “shells”. If post-nest fraction misses band → PARTIAL `fraction_miss_after_nest_fix`.
5. Stage \(N-1 = F\) **exactly** (copy geometry in pack CRS, do not re-buffer).

**Fraction tolerance (normative):**

- Interior stages: \(\lvert f_{\mathrm{actual}} - f_{\mathrm{target}}\rvert \le \max(0.02,\ 0.05·f_{\mathrm{target}})\).
- Terminal: \(f = 1\) via exact copy; do not binary-search terminal.

**Fraction schedules (fixed powers — no ambiguous “logistic or power”):**

| Name | Formula | Use |
|------|---------|-----|
| `linear` | \(f_i = (i+1)/N\) | Uniform area steps |
| `sqrt` | \(f_i = ((i+1)/N)^2\) | Mimics radius-linear growth (ellipse-like) |
| `early_fast` | \(f_i = ((i+1)/N)^{0.5}\) (power \(p=0.5\)) | More early growth |
| `late_fast` | \(f_i = ((i+1)/N)^{2}\) (power \(p=2\)) | Slow start, late run (wind event caricature) |
| `logistic` | \(f_i = \mathrm{clip}(1/(1+e^{-k(x_i-x_0)}))\) renormalized to end at 1.0; optional named schedule if needed | Separate from early_fast; not default |
| `custom` | explicit list of N floats ending in 1.0 | Tests / demos |

**Why default:** stable on real REDIAM shapes (including dual-lobe multipolygons via global erode); pure geometry; no fuel map dependency; trivial to property-test.

### Mode B — Buffer rings (inward shells)

1. Compute max inward distance \(D_{\max}\) via binary search until erosion empty (or use pole of inaccessibility / medial approx for speed).
2. Choose distances \(0 = d_{N-1} < d_{N-2} < \ldots < d_0 < D_{\max}\).  
   \(S_i = \mathrm{buffer}(F, -d_i)\) cleaned; last stage \(d=0 \Rightarrow F\).
3. Area fractions are **induced**, not prescribed — report actual \(f_i\).
4. Multipart: keep components above `min_component_area_ha`; drop dust; micro-islands may reappear only at terminal exact copy (KD13 M4).

**Use:** pedagogical “onion rings”; stress topology on skinny corridors (may collapse early → document SKIP stage or merge schedule).

### Mode C — Morphological growth (forward from seed)

1. **Ignition seed:**  
   - default: `representative_point()` of \(F\) (or of largest component) — **not** multipolygon centroid when it lies outside \(F\);  
   - optional: early FIRMS cluster centroid **clipped into** \(F\);  
   - optional: point on medial axis.
2. Grow by iterative **dilation of seed mask ∩ F** (raster) or successive positive buffers of a small disk ∩ \(F\) until area fractions hit targets.
3. Raster path (optional): burn mask on grid resolution \(r\) m (e.g. 20–30 m); morphological dilate; polygonize; snap to \(F\).

**Use:** when demo should “start from a point”; more parameters; v1.1 after Mode A is green.

### Multi-step timeline (time axis)

Time is **synthetic scaffolding**:

| Parameter | Default | Notes |
|-----------|---------|-------|
| `n_stages` | 12 | **Normative range:** \(N \in [3, 64]\); reject outside |
| `total_duration_s` | 24*3600 | Assumed event window (not real control time); ROS sensitive to duration — document in metrics |
| `interval_mode` | `uniform` | or match area-equal Δt inverse for constant bulk ROS |

**Constant bulk ROS schedule (optional):**  
choose target proxy ROS \(v\) (m/min), set Δt from area increments via isotropic formula with **normative units**:

\[
\Delta t_{\min} = \frac{\Delta A}{P_{\mathrm{avg}} · v},\quad \Delta t_s = 60·\Delta t_{\min}
\]

where \(\Delta A\) is in **m²**, \(P\) in **m**, \(v\) in **m/min**. Still labeled **assumed** — not ASEMA.

Store both `time_s` and `wall_clock_iso_assumed` (optional, anchored on `fecha_inc` 00:00Z) with `time_is_assumed: true`.

### FIRMS as soft prior (optional, never ceiling)

- Weight dilation toward FIRMS density (cost map) **only inside** \(F\).  
- Final stage still exactly REDIAM.  
- Metrics may report `firms_seed_used: true` + distance seed-to-centroid.  
- Scorecard remains: hull is not burned area; progressive stages are not FIRMS polygons.

### Output of ROS proxy pairs (normative units — match `front_dynamics`)

Prefer computing proxy pairs by converting stages → `FrontObservation` and reusing ops helpers (`observation_area_m2`, `total_perimeter_m` / equivalent, `_pair_area_ros` formulas) rather than reimplementing unit conversions.

For consecutive stages \((S_i, S_{i+1})\), with areas in **m²**, perimeters in **m**, times in **seconds**:

| Metric | Normative formula | Label |
|--------|-------------------|-------|
| `dt_min` | \(dt_{\min} = \Delta t_s / 60\) | assumed |
| `dA_m2` | \(A_{i+1} - A_i\) (m²) | growth |
| `dA_ha` | `area_ha[i+1] - area_ha[i]` if stages already store ha; **or** \(dA\_m2 / 10^4\) only when \(A\) is m² — **never** divide ha by 1e4 again | growth |
| `ros_area_m_min` | \(\Delta A / (P_{\mathrm{avg}} · dt_{\min})\) with \(\Delta A\) in m² | `proxy_synthetic` |
| `ros_equiv_radius_m_min` | \(\Delta\sqrt{A/\pi} / dt_{\min}\) | `proxy_synthetic` |
| `hausdorff_m` | \(H(\partial S_i, \partial S_{i+1})\) | stage geometry |
| `iou` | \(A(S_i \cap S_{i+1}) / A(S_i \cup S_{i+1})\) | nesting quality (~1 if nested) |

Reject / flag pairs with \(\Delta t \le 0\) or empty perimeter.

**Plausible ROS caps (align with product constant):**

| Field | Default | Source / behavior |
|-------|---------|-------------------|
| `ops_cap_m_min` | **60.0** | `scientific_ops.MAX_PLAUSIBLE_SPEED_M_MIN` — same filter/fusion ceiling as `run_front_dynamics` |
| `research_cap_m_min` | optional (e.g. 200) | Research-only diagnostic; **not** default PASS threshold |

- Exceeding **ops** cap ⇒ abstain primary / `PSB_PROXY_ROS = PARTIAL` (reason `proxy_ros_exceeds_ops_cap`), **not** invented high ROS sold as PASS.
- Do **not** use 200 m/min as the default product gate.

### Optional Douglas-Peucker simplify

| Rule | Behavior |
|------|----------|
| Default | **Off** for gold verify |
| If enabled | Run **after** stage build; re-validate nested + terminal identity/metric QA; record `simplify_tolerance_m` in metrics |
| Fail | If simplify breaks nesting/terminal → do not ship simplified stages; PARTIAL or rebuild without simplify |

---

## Honesty constraints

These are **hard product rules**, enforced by schema tests and scorecard gates (same spirit as AND industrial `NO_FALSE_DISPATCH`, `vp_invented: false`).

| # | Constraint | Enforcement |
|---|------------|-------------|
| H1 | Synthetic stages **≠** real LWIR / Heligrafics frames | `not_real_lwir: true` on every stage; manifest `requires_lwir_heligraphics` remains false |
| H2 | Synthetic stages **≠** official multi-day O2 | `not_official_intermediate_o2: true`; only final = REDIAM official |
| H3 | **No invented tactical Vp** as confirmed | `vp_tactical: null`; never write `confirmed` anchor from PSB ROS |
| H4 | Proxy ROS never sold as dispatch | scorecard `SYNTHETIC_ROS_NOT_DISPATCH: PASS`; decide stays HOLD for field_ops |
| H5 | FIRMS hull still not official ha | unchanged industrial flag `firms_hull_is_official_burned_area: false` |
| H6 | Attribution REDIAM on final + progressive brief lines | string checks in tests |
| H7 | Map/UI banner required if progressive animated | “Crecimiento sintético — perímetro final oficial REDIAM” |
| H8 | Do not upgrade grade A ops from synthetic-only packs | quality grade ≤ B / `synthetic_research` |
| H9 | CI artifacts must not drop honesty keys | schema required properties |
| H10 | Decide/industrial builders never read progressive ROS as O1 | code + tests: no progressive path into `vp_tactical` / field_ops GO |

**Explicit non-claims in operator-facing text:**

- Not a reconstruction of Níjar hour-by-hour reality.  
- Not a substitute for ASEMA partes or thermal sorties.  
- Useful for **engineering validation**, demos of multi-stage UX, and invariant stress tests.

---

## Massive testing strategy

### What “millions of tests” means here

| Interpretation | In scope? |
|----------------|-----------|
| **Millions of micro-assertions** via **internal loops**, property tests, seeded Monte Carlo over geometry configs | **YES** |
| Millions of separate pytest **nodes** via multi-`@pytest.mark.parametrize` | **NO** (collection time / failure UX) |
| Million-minute wall-clock CI / full satellite E2E | **NO** |
| Nightly optional expanded Monte Carlo (still seconds–minutes) | Optional |

### Layers

#### L0 — Unit (fast, always CI)

- CRS round-trip area on fixture + gold sample (subset coords).  
- Schedule builders: fractions end at 1.0, strictly increasing; `n_stages` validation [3, 64].  
- Empty / invalid geom → clean error.  
- Honesty keys present.  
- Terminal stage **identity** on simple square/circle/REDIAM fixture.  
- Multipolygon fixture: erode nested; never scale about exterior centroid.  
- Sector ROS wrap sets `bulk_ros_quartile_split_synthetic`.  
- ROS units: m² / dt_min smoke vs `observation_area_m2` path.

#### L1 — Property tests (high volume)

**Normative implementation pattern:** one (or few) tests with **internal loops** + assertion counter + `repro:` string on failure. Multi-parametrize that creates tens of thousands of pytest nodes is **discouraged**.

```python
def test_invariants_internal_grid():
    assert_count = 0
    for seed in range(n_seeds):
        for n_stages in stage_list:
            for schedule in schedules:
                for shape_id in shapes:
                    for engine in engines:
                        seq = run_psb(...)
                        assert_count += assert_all_invariants(seq)  # many asserts
    assert assert_count >= MIN_ASSERTS
```

Optional: **Hypothesis** strategies for random polygons (hypothesis is already a dev dependency in `pyproject.toml`) as a supplement to the hand grid — not a substitute for seeded repro strings.

Example **full** L1 scale (illustrative, nightly `@pytest.mark.slow`):

| Axis | Count |
|------|-------|
| seeds | 100 |
| n_stages | 5 values (4, 6, 8, 12, 16) |
| schedules | 4 |
| base shapes | 20 synthetic (ellipse, stadium, C-shape, multipolygon, thin corridor, star-approx, REDIAM-simplified) |
| engines | 2 (area_fraction, buffer_rings) |
| assertions per case | ~15 |

\[
100 \times 5 \times 4 \times 20 \times 2 \times 15 \approx 1.2 \times 10^6 \text{ micro-assertions}
\]

**Concrete reduced PR CI grid (normative defaults):**

| Axis | PR CI value |
|------|-------------|
| seeds | 5 |
| shapes | 6 (incl. ≥1 multipolygon dual-lobe) |
| stages | {4, 8} |
| engines | 2 |
| schedules | 2 (e.g. linear, sqrt) |
| asserts/case | ≥15 |

Expected: \(\ge 5×6×2×2×2×15 = 3600\) base; with internal multipolygon/component asserts target **≥ 10⁴** total asserts documented in test output.

**Target runtime:** full L1 nightly &lt; ~10 min; PR reduced &lt; ~2 min contribution.

#### L2 — Monte Carlo stress

- Random polygons via Gaussian radial perturbation of ellipses + boolean ops; clip to bbox.  
- Random multipolygon islands inside shell.  
- Seeds fixed list + `PROGRESSIVE_BURN_MC_SEEDS` env override.  
- Failures must print `repro: --seed S --engine E --n-stages N`.

#### L3 — Pack / industrial integration (few, critical)

- Offline fixture pack build + progressive attach (mirror `test_and_if_pack.py`).  
- Gold pack path if artifacts present (skip if not in CI sandbox).  
- Scorecard: industrial gates still PASS; progressive sub-gates PASS.  
- Manifest artifacts keys present; `vp_tactical` still null; `scorecard_verdict` unchanged by PSB.  
- Decide HOLD preserved.  
- `vp_invented is False`.

#### L4 — front_dynamics proxy smoke

- Convert stages → observations with **adapter contract** (`enable_coreg=False`, projected_metric EPSG:6933, resolution_m set).  
- Assert finite proxy ROS or documented abstention under ops cap 60.  
- Assert no claim of `confirmed` anchor; pair_quality ≤ B.  
- Normal-ray not used as primary.

#### L5 — Mutation / honesty fuzz

- Strip honesty keys → schema validator fails.  
- Force `vp_tactical: 7.0` in progressive metrics → gate FAIL.  
- Claim `not_real_lwir: false` → FAIL.

### Assertion catalog (minimum)

1. `is_valid` after fix for all stages  
2. areas finite and ≥ 0  
3. area monotone non-decreasing  
4. nested containment (buffered tolerance)  
5. all stages ⊆ final  
6. terminal **identity** (pack CRS) + optional metric QA  
7. fraction targets within \(\max(0.02, 0.05·f)\) band (Mode A interior)  
8. `n_stages` match feature count; \(N \in [3,64]\)  
9. time_s monotone  
10. synthetic honesty flags  
11. attribution non-empty on pack attach  
12. proxy ROS None or ≥ 0; if finite and &gt; `ops_cap_m_min` (60) → PARTIAL/abstain not silent PASS  
13. determinism: same seed → identical WKT hash  
14. multipolygon: no stage outside final; all retained components in observations  
15. empty erosion handled without crash  
16. simplify off by default; if on, re-validate + `simplify_tolerance_m` recorded  

### Fixtures

| Fixture | Purpose |
|---------|---------|
| Unit square / circle metric | Analytical fractions |
| Thin rectangle | Buffer collapse edge case |
| Multipolygon two lobes (~equal area, gap) | Component policy / no exterior-centroid scale |
| Multipolygon with micro-islands | min_component_area_ha deferral |
| `tests/fixtures/rediam_and/sample_perim_3042.geojson` | Real CRS path |
| Optional simplified Níjar exterior (light) | Gold-like without huge coords |

### CI policy

Repo today: `pyproject.toml` has only `requires_weights` marker; CI runs full `pytest` with coverage. PSB **requires**:

1. Register `@pytest.mark.slow` in `[tool.pytest.ini_options] markers` in `pyproject.toml`.  
2. PR CI: `pytest -m "not slow"` (or equivalent workflow filter) so full L1/L2 does not break PR.  
3. Nightly/manual: full grid + MC with slow mark.

```text
PR CI:   L0 + L1-reduced (internal loops, ≥10⁴ asserts) + L3 fixture + L5   (< ~2 min)
Nightly: L1-full @slow + L2 + L4                                           (< ~10 min)
Manual:  gold Níjar progressive rebuild
```

---

## Integration with open_if packs and demo portal (optional)

### open_if

| Hook | Behavior |
|------|----------|
| `build_and_if_pack.py --progressive-burn` | After industrial pack, invoke PSB attach + manifest keys |
| `build_progressive_burn.py --pack DIR` | Standalone recompute + manifest patch |
| `verify_and_industrial_e2e.py` | Optional layer `progressive_burn_present` **non-blocking** for `GO_AND_INDUSTRIAL_E2E` (PSB is additive) |
| `verify_progressive_burn_e2e.py` | Dedicated GO_PROGRESSIVE_SYNTHETIC |
| Index / `and_index.html` | Badge “PSB” if progressive/ exists |

### Demo portal (optional PR)

- Multi-CCAA Níjar card: secondary button “Synthetic growth (demo)”.  
- Animation of stage polygons with permanent disclaimer strip.  
- KPI: final ha matches REDIAM 2169.34; stages N; engine name.  
- **Not** a sales claim of real multi-day O2.

### Commander (optional)

- Load `progressive/timeline_progressive.geojson` if file present; same disclaimer as portal.  
- Never load synthetic features from official `timeline_perimeters.geojson`.

---

## Metrics

### Geometry / growth

| Metric | Definition | Gate (default) |
|--------|------------|----------------|
| `area_ha[i]` | Equal-area ha of stage i | finite, monotone |
| `area_m2[i]` | Equal-area m² (authoritative for ROS) | finite |
| `area_fraction_actual[i]` | \(A_i / A_F\) | interior: \(\lvert f_a - f_t\rvert \le \max(0.02, 0.05·f_t)\); terminal 1.0 exact |
| `growth_ha[i→i+1]` | \(A_{i+1}-A_i\) in ha | ≥ 0 |
| `growth_ha_per_h` | growth / assumed hours | informational |
| `perimeter_m[i]` | sum of exteriors (+ holes policy) | > 0 for non-empty |

### ROS proxy

| Metric | Gate |
|--------|------|
| `ros_area_m_min` | ≥ 0 or null; not labeled confirmed; units m² / (m · min) |
| `ros_equiv_radius_m_min` | same |
| `ops_cap_m_min` | default **60.0** (`MAX_PLAUSIBLE_SPEED_M_MIN`) |
| `ros_proxy_cap_flag` | exceed ops cap ⇒ abstain / `PSB_PROXY_ROS=PARTIAL`, not PASS with invented high ROS |
| `research_cap_m_min` | optional diagnostic only |

### Hausdorff / agreement

| Metric | Use |
|--------|-----|
| `hausdorff_stage_m[i,i+1]` | Smoothness of growth steps |
| `hausdorff_stage_to_final_m[i]` | Approaches 0 as i → N-1 |
| `iou_stage_to_final[i]` | Approaches 1 |
| Terminal identity | exact pack-CRS copy — `PSB_TERMINAL_IDENTITY` |
| Terminal metric QA | IoU/Hausdorff/area_rel on 6933 twin — `PSB_TERMINAL_METRIC_QA` |

### Pack / product gates (`scorecard_progressive.json`)

| Gate | PASS if |
|------|---------|
| `PSB_TERMINAL_IDENTITY` | exact copy of official pack geometry |
| `PSB_TERMINAL_METRIC_QA` | optional 6933 twin IoU/Hausdorff/area (when computed) |
| `PSB_MONOTONE_AREA` | non-decreasing areas |
| `PSB_NESTED` | containment checks |
| `PSB_FRACTION_BAND` | Mode A interior fractions within ε |
| `PSB_HONESTY` | all honesty keys + vp null |
| `PSB_PROXY_ROS` | computed under ops cap, explicit abstain, or SKIP — never silent over-cap PASS |
| `PSB_REPRO` | seed + engine recorded |
| `PSB_NO_FALSE_DISPATCH` | no field_ops GO from PSB alone |
| `PSB_MANIFEST` | progressive artifact keys registered when attached |

Verdict:

- **GO_PROGRESSIVE_SYNTHETIC** — all required PASS  
- **PARTIAL** — engine fallback, micro-components deferred, fraction_miss_after_nest_fix, buffer collapse documented, or proxy over ops cap abstained  
- **NO_GO** — terminal identity fail, honesty fail, crash, n_stages invalid  

Industrial AND verdict `GO_OPEN_AND_O2` remains independent (PSB failure must not silently rewrite REDIAM metrics).

---

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Users / demo audience confuse synthetic stages with real multi-day O2 | High (trust) | Separate `progressive/` directory only; schema flags; map banner; brief wording; tests H1–H10; no MAY-merge into official timeline |
| Negative buffer collapses corridors → empty stages | Medium | Fallback per-component homothety (KD13); PARTIAL gate; min area; reduce n_stages |
| Multipolygon / dual-lobe / centroid outside F | **High** on gold | KD13: global erode primary; never multipolygon centroid; PR5 multipolygon acceptance |
| Overclaim proxy ROS as tactical | High | Same as industrial: HOLD, vp null, mutation tests; decide never reads progressive ROS as O1 |
| Unit bugs (ha vs m², s vs min) | High | Normative formulas = `front_dynamics._pair_area_ros`; reuse `observation_area_m2` |
| Cap mismatch 200 vs ops 60 | Medium | Default ops_cap=60; PARTIAL on exceed |
| Floating CRS / area drift WGS84 vs metric | Medium | All area in EPSG:6933; terminal identity in pack CRS; metric QA separate |
| CI time explosion / collection explosion | Medium | Internal-loop property tests; `@pytest.mark.slow`; PR `not slow`; reduced grid |
| Gold pack size growth (many stages geojson) | Low | Cap default N=12; simplify **default off**; if on, re-validate + record tolerance |
| FIRMS-seeded growth misread as FIRMS perimeter product | Medium | Props `seed_source: firms_centroid_clipped`; still synthetic |
| Coupling PSB bugs into industrial E2E false red | Medium | Progressive verify separate; industrial gate non-blocking |
| Normal-ray / grade A on coarse rings | Medium | Adapter: enable_coreg=False; force bulk primary; quality ≤ B |
| front_dynamics API has no disable_normal_ray | Medium | Post-process or bulk-only metrics path (documented) |

---

## Key Decisions (mandatory)

| # | Decision | Rationale |
|---|----------|-----------|
| KD1 | **Final stage is always the official REDIAM geometry (exact copy in pack CRS), not a re-buffered approximation** | Preserves O2 integrity; gate `PSB_TERMINAL_IDENTITY` |
| KD2 | **Default engine = area-fraction reverse growth (global negative buffer + per-component homothety fallback)** | Stable on real AND shapes including dual-lobe multipolygons; easy invariants |
| KD3 | **Progressive artifacts live only under `progressive/` with explicit synthetic schema; official `timeline_perimeters.geojson` stays pure; never overwrite `perimeter_rediam` or mislabel as CEMS multi-day** | Prevents honest-data accidents |
| KD4 | **PSB does not invent or confirm tactical Vp; decide remains HOLD for field_ops; decide never reads progressive ROS as O1** | Continues AND industrial honesty contract |
| KD5 | **front_dynamics on PSB uses bulk/equiv-radius proxies only by default; enable_coreg=False; quality ≤ B / synthetic_research; normal-ray not primary** | Avoid false high-frequency ROS and false grade A |
| KD6 | **“Millions of tests” = internal-loop property/Monte Carlo micro-assertions, not million pytest nodes or million E2E jobs** | CI realism + still extreme coverage |
| KD7 | **PSB is additive: industrial `GO_OPEN_AND_O2` does not require PSB; PSB has its own verdict** | No regression on implemented AND E2E |
| KD8 | **Metric CRS for computation; pack publish WGS84 GeoJSON like other open_if vectors** | Consistent with `build_and_if_pack.py` |
| KD9 | **Gold path prioritizes Níjar `and_2024040053_20240606`; silver packs follow** | Best-known REDIAM gold; multipolygon-first |
| KD10 | **FIRMS may bias seed only; never changes final area or replaces REDIAM** | Satellites remain proxy |
| KD11 | **Implementation language/stack: shapely + pyproj inside `wildfire_front/progressive_burn/`; CLI in `scripts/`** | Matches AND pack tooling |
| KD12 | **Attribution string REDIAM/Junta required on progressive metrics and brief addendum** | Legal/provenance parity |
| KD13 | **Multipolygon policy: global morphological erode primary; never multipolygon centroid for homothety; per-component homothety fallback proportional to area share; micro-islands may defer to terminal; to_observations emits all retained exteriors; PR5 requires real Níjar nested multipolygon** | Gold geometry is 5-part MultiPolygon; centroid outside F |
| KD14 | **ROS units and caps match ops: ΔA m², P m, dt_min = dt_s/60; ops_cap = MAX_PLAUSIBLE_SPEED_M_MIN (60)** | Avoid unit bugs and false PASS over 60 m/min |
| KD15 | **n_stages ∈ [3, 64], default 12; reject outside** | Single validated range |
| KD16 | **Manifest registers progressive_* artifacts; progressive_synthetic_burn block does not alter vp_tactical or industrial scorecard_verdict** | Discoverability without contaminating O2 |

---

## Open Questions

| # | Question | Suggested default |
|---|----------|-------------------|
| OQ1 | Raster morphological engine in v1 or only v1.1? | **v1.1** — vector Mode A/B first |
| OQ2 | Should `timeline_perimeters.geojson` include synthetic features or stay pure official? | **Stay pure (hard rule)**; progressive dir only — see KD3 / NG8 |
| OQ3 | Assumed total duration default 24 h vs multi-day for large IF? | 24 h demo; CLI override; document ROS sensitivity |
| OQ4 | Include wind-biased anisotropic growth (affine stretch before clip)? | Stretch non-goal v1; optional v1.2 |
| OQ5 | Nightly MC seed count (100 vs 1000)? | 100 default nightly; 1000 manual; wire `@pytest.mark.slow` first |
| OQ6 | Expose progressive animation in multi-CCAA portal in first demo PR? | Optional last PR; docs-first OK |
| OQ7 | When ASEMA Vp arrives for Níjar, calibrate assumed Δt so proxy ROS ~ Vp? | Allowed only as **scenario**, still not confirmed intermediate O2; anchor remains separate file |

---

## PR Plan (mandatory, incremental)

### PR1 — Core engine + schemas (no pack mutation)

**Scope:**

- `wildfire_front/progressive_burn/` with schemas, geometry (incl. KD13 multipolygon helpers), schedules (`n_stages` validation, fixed schedule powers), Mode A engine, Mode B engine, pipeline API.  
- Unit tests L0 + small property grid (incl. multipolygon fixture).  
- Docs: this design already in `docs/design/AND_PROGRESSIVE_BURN_SIMULATION.md`.

**Acceptance:**

- Terminal **identity** + monotone + nested on fixtures (single + multipolygon).  
- Honesty constants exported.  
- Homothety never uses multipolygon centroid when exterior.  
- No dependency on live WFS/FIRMS.

### PR2 — Metrics + front_dynamics adapter

**Scope:**

- `metrics.py` (area, Hausdorff, proxy ROS pairs with **normative units** and ops_cap 60).  
- `to_observations.py` + adapter contract (`enable_coreg=False`, projected_metric, quality cap, all components).  
- Sector ROS wrap test.  
- Tests L4 reduced.

**Acceptance:**

- Proxy ROS finite on circle linear growth with assumed Δt; formulas match `_pair_area_ros` units.  
- Over ops cap → PARTIAL/abstain not PASS.  
- Output JSON includes `proxy_synthetic`, null Vp, pair_quality ≤ B.

### PR3 — Pack attach + CLI + AND fixture test

**Scope:**

- `pack_attach.py`, `scripts/build_progressive_burn.py`.  
- Optional flag on `build_and_if_pack.py`.  
- Manifest `artifacts.progressive_*` + `progressive_synthetic_burn` block.  
- Brief addendum path.  
- `tests/test_progressive_burn_pack.py` offline.  
- Write `progressive/*` on temp pack from REDIAM fixture.

**Acceptance:**

- Industrial scorecard fields unchanged when PSB attached (`vp_tactical`, `scorecard_verdict`).  
- Progressive scorecard GO on fixture.  
- Manifest lists progressive artifacts.  
- Brief addendum mentions synthetic + REDIAM final.

### PR4 — Massive property / Monte Carlo suite

**Preferred ordering:** **PR1 → PR2 → PR4** so metrics asserts (Hausdorff, proxy ROS, caps) are available.  
Alternatively split:

- **PR4a** geometry invariants only (after PR1).  
- **PR4b** metrics asserts (after PR2).

**Scope:**

- `tests/test_progressive_burn_properties.py` with **internal loops** (not multi-parametrize explosion).  
- Register `@pytest.mark.slow` in `pyproject.toml`; document CI `pytest -m "not slow"`.  
- Concrete reduced PR CI grid (seeds=5, shapes=6, stages={4,8}, engines=2, …).  
- Optional Hypothesis strategies.  
- Repro seed messaging.

**Acceptance:**

- Documented assertion count ≥ 10⁴ in default CI config; ≥ 10⁵ in nightly.  
- Runtime budgets met.  
- No flaky non-seeded randomness.

### PR5 — Gold Níjar progressive rebuild + verify script

**Scope:**

- Run PSB on `outputs/open_if/and_2024040053_20240606` (or rebuild pack then attach).  
- **First-class multipolygon acceptance:** nested MultiPolygon stages on real 5-part Níjar.  
- `scripts/verify_progressive_burn_e2e.py` → pack-local verification JSON.  
- Makefile target `progressive-burn-nijar` (alongside `and-industrial-e2e`).

**Acceptance:**

- Terminal identity: exact copy; ha ~2169.34.  
- Nested multipolygon stages; micro-islands policy documented if PARTIAL.  
- `GO_PROGRESSIVE_SYNTHETIC` or PARTIAL with reasons.  
- Industrial acta still GO.  
- Simplify default off for gold verify.

### PR6 — (Optional) Portal / commander UX

**Scope:**

- Demo multi-CCAA or map.html layer toggle for progressive stages from `progressive/timeline_progressive.geojson` only.  
- Permanent disclaimer UI.  
- Screenshots/notes in demo handoff if needed.

**Acceptance:**

- Cannot view animation without visible synthetic labeling.  
- HOLD / no Vp claims in UI copy.  
- Official timeline layer remains pure.

### PR dependency graph

```
PR1 ──► PR2 ──► PR4 (preferred: metrics-heavy asserts after adapter)
 │        └──► PR3 ──► PR5
 │              └──► PR4a (geometry-only parallel OK after PR1)
PR3/PR5 ──► PR6 (optional)
```

Preferred path for quality of property tests: **PR1 → PR2 → PR4**. Geometry-only PR4a may parallel PR2 if scoped.

### Out of order forbidden

- Portal animation before honesty schema (no PR6 before PR1/PR3).  
- Writing Vp confirmed from proxy ROS (never).  
- Replacing official perimeter layer with a stage (never).  
- Merging synthetic features into `timeline_perimeters.geojson` (never in v1).  
- Treating multipolygon centroid as homothety center (never).

---

## Implementation sketch (non-normative API)

```python
# wildfire_front/progressive_burn/pipeline.py (sketch)

from wildfire_front.scientific_ops import MAX_PLAUSIBLE_SPEED_M_MIN

@dataclass(frozen=True)
class ProgressiveBurnConfig:
    n_stages: int = 12  # validated ∈ [3, 64]
    engine: str = "area_fraction"  # area_fraction | buffer_rings | morph_forward
    schedule: str = "sqrt"  # linear | sqrt | early_fast | late_fast | logistic | custom
    total_duration_s: float = 86400.0
    metric_crs: str = "EPSG:6933"
    seed: int = 0
    min_area_ha: float = 0.01
    min_component_area_ha: float = 2.0  # micro-islands may defer (KD13)
    fraction_abs_tol: float = 0.02
    fraction_rel_tol: float = 0.05  # band = max(abs, rel * f_target)
    ops_cap_m_min: float = MAX_PLAUSIBLE_SPEED_M_MIN  # 60.0
    research_cap_m_min: float | None = None
    simplify_tolerance_m: float | None = None  # default off (None)
    main_front_only: bool = False  # observations: all components by default
    # honesty baked in at emit time

def validate_config(config: ProgressiveBurnConfig) -> None:
    if not (3 <= config.n_stages <= 64):
        raise ValueError(f"n_stages must be in [3, 64], got {config.n_stages}")

def build_stage_sequence(final_geom, config: ProgressiveBurnConfig) -> StageSequence:
    ...
```

CLI:

```powershell
$env:PYTHONPATH = "."
python scripts/build_progressive_burn.py `
  --pack outputs/open_if/and_2024040053_20240606 `
  --n-stages 12 `
  --engine area_fraction `
  --schedule sqrt `
  --seed 0

python scripts/verify_progressive_burn_e2e.py
pytest tests/test_progressive_burn_unit.py tests/test_progressive_burn_properties.py -q -m "not slow"
```

---

## Success criteria (design done → eng ready)

1. Engineers can implement PR1 without open product questions on honesty or multipolygon policy (KD13).  
2. Níjar gold remains the narrative anchor: **official final perimeter perfect (5-part MultiPolygon); growth history synthetic and labeled**.  
3. Test strategy delivers extreme invariant coverage without CI collapse (markers + internal loops).  
4. No path from PSB to false tactical GO; ROS units/caps match ops.  
5. Incremental PRs keep `GO_AND_INDUSTRIAL_E2E` green throughout.  
6. Adapter contract for `front_dynamics` is implementable against the live API without a new disable_normal_ray flag (post-process or bulk-only path).

---

## References (in-repo)

| Path | Why |
|------|-----|
| `docs/design/ANDALUCIA_REDIAM_INDUSTRIAL_E2E_PLAN.md` | Industrial AND E2E contract |
| `docs/AND_INDUSTRIAL_E2E_VERIFICATION.md` | Gold Níjar acta |
| `outputs/open_if/and_2024040053_20240606/` | Gold pack (MultiPolygon final) |
| `outputs/open_if/and_2024040053_20240606/vectors/perimeter_rediam.geojson` | 5-part ceiling geometry |
| `scripts/build_and_if_pack.py` | Pack builder / FIRMS / metrics_o2 / manifest.artifacts |
| `wildfire_front/front_dynamics.py` | Bulk ROS estimators (`_pair_area_ros`, `run_front_dynamics`, fusion) |
| `wildfire_front/scientific_ops.py` | `MAX_PLAUSIBLE_SPEED_M_MIN = 60.0`, `observation_area_m2` |
| `wildfire_front/emergency_products.py` | Sector ROS / envelope honesty (`bulk_ros_quartile_split`) |
| `wildfire_front/synthetic.py` | Free ellipse synthetic (contrast) |
| `wildfire_front/open_if/timeline.py` | Daily open timeline merge patterns |
| `tests/test_and_if_pack.py` | Offline AND pack test style |
| `pyproject.toml` | pytest markers (add `slow`); hypothesis dev dep |
| `docs/design/DEMO_MULTI_CCAA_TOBARRA_NIJAR_CAMINOMORISCO.md` | Demo narrative Níjar |
| `ARCHITECTURE.md` | Dual product rules |

---

## Revision Summary (2026-07-23 design review)

Addressed ISS-001…014 from design review. Status remains **DESIGN — ready for incremental implementation** (blockers resolved on paper).

| Issue | Change |
|-------|--------|
| ISS-001 | **KD13** multipolygon policy; gold Níjar measured parts; global erode primary; no multipolygon centroid; all components in observations; PR5 multipolygon acceptance |
| ISS-002 | Normative ROS formulas matching `front_dynamics` (m², dt_min); dA_ha without double /1e4; prefer ops helpers |
| ISS-003 | Default `ops_cap_m_min=60` from `MAX_PLAUSIBLE_SPEED_M_MIN`; research_cap optional; over cap → PARTIAL/abstain |
| ISS-004 | Exact adapter recipe: projected_metric EPSG:6933, enable_coreg=False, bulk primary force or bulk-only metrics, quality ≤ B, ≥4 samples, all components |
| ISS-005 | Internal loops normative; register `@pytest.mark.slow`; PR CI reduced grid; Hypothesis optional |
| ISS-006 | Fraction ε = max(0.02, 0.05·f); terminal exact; PARTIAL `fraction_miss_after_nest_fix` |
| ISS-007 | Manifest progressive_* artifacts + progressive_synthetic_burn block; brief addendum; decide never reads PSB ROS as O1 |
| ISS-008 | Overview/pack: only `progressive/timeline_progressive.geojson`; official timeline pure; NG8 |
| ISS-009 | `n_stages ∈ [3, 64]`, default 12; G3 aligned |
| ISS-010 | Split `PSB_TERMINAL_IDENTITY` vs `PSB_TERMINAL_METRIC_QA` |
| ISS-011 | Sector wrap `{**compute_sector_ros(...), "method": "bulk_ros_quartile_split_synthetic", "synthetic": True}` |
| ISS-012 | Simplify default off; re-validate if on; record `simplify_tolerance_m` |
| ISS-013 | Prefer PR1→PR2→PR4; optional PR4a/PR4b split |
| ISS-014 | `early_fast` p=0.5; `late_fast` p=2; logistic separate named schedule |

---

*End of design — Progressive Synthetic Burn v1 for perfect Andalucía REDIAM final perimeters.*
