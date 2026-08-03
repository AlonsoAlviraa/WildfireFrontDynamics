# PR Plan — Fuel stack · Hybrid envelope · AEMET Tobarra

| Field | Value |
|-------|--------|
| **Title** | Landing PR stack: ROS fuel/terrain + envelope v3 + AEMET weather |
| **Repo** | WildfireFrontDynamics |
| **Date** | 2026-08-03 |
| **Status** | **PR-α reviewed 0 issues** · **PR-β DoD green** (envelope+AEMET+scorecard+pipeline) · PR-11 optional |
| **Designs** | `docs/DESIGN_DEM_REAL_CALIBRATION.md` · `docs/DESIGN_ENVELOPE_V3_HYBRID.md` · `docs/MEGA_PLAN_PREDICCION_ROS_VEGETACION_TERRENO.md` |
| **Live smoke** | `python scripts/run_tobarra_aemet_pipeline.py` → scorecard **PASS** |
| **Out of scope** | O1 Cardoso Vp/ha (external) · ML fusion ON · inventing tactical ROS · committing `.env` / secrets / large GeoTIFFs |

---

## 0. Goal

Ship the **fuel–terrain physics layer** (DEM, WorldCover fuels, Rothermel-lite, hybrid ROS, envelope 15/30/60) and the **AEMET open-data weather path** as a **Graphite / plain-git PR stack**, without one mega-diff and without regressing honesty rails (`weather_scenario_assumed`, Decision Card weight 0, field_ops fusion OFF).

**Product claims this stack must preserve**

| Claim | Rule |
|-------|------|
| Physics ROS | `physics_potential_orientation_only` — not tactical dispatch |
| Hybrid head with obs | Obs-locked; envelope radii from hybrid sectors |
| AEMET incomplete dir | `dir=99` → fill library bearing + `weather_scenario_assumed=true` |
| Decision Card envelope | weight **0** (audit only) |
| Secrets | `AEMET_API_KEY` only in `.env` (gitignored) |

---

## 1. Dependency graph

```
PR-1 models+terrain+Rothermel
  ├─► PR-2 DEM+stack CLI
  │     ├─► PR-3 fuel map WorldCover
  │     │     └─► PR-4 sectors spatial + slopes
  │     └─► PR-5 calibration k (// after PR-2)
  ├─► PR-6 weather honesty + AEMET
  └─► PR-7 hybrid ROS prior
        └─► PR-8 envelope v3
              └─► PR-9 scorecard + Decision Card attach
                    └─► PR-10 pipeline CLI + status docs
                          └─► PR-11 (opt) Pablo ops perimeter eval
```

**Parallel lanes after PR-1**

| Lane | PRs | Notes |
|------|-----|--------|
| Terrain stack | 2 → 3 → 4 | DEM before spatial slopes |
| Calibration | 5 | After PR-2; re-fit after PR-3/4 |
| Weather | 6 | Mostly independent; needed before honest stack physics default |
| Product | 7 → 8 → 9 → 10 | Envelope needs hybrid |
| Ops perimeter | 11 | Optional; uses Pablo KMZ drop, not AEMET |

**Suggested merge order (linear stack)**

`1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → (11)`

---

## 2. PR catalog

### PR-1 — Fuel models + terrain helpers + Rothermel-lite core

**Branch:** `feat/fuel-models-rothermel-lite`  
**Deps:** none  

**Scope**

- Mediterranean / Scott–Burgan catalog and accessors.
- Terrain helpers (slope φ, rise/run).
- Rothermel-lite sector ROS (non-spatial dominant fuel).
- Package skeleton `wildfire_front/fuel/__init__.py` exports for this PR only.

**Files**

| Path | Action |
|------|--------|
| `wildfire_front/fuel/models.py` | add |
| `wildfire_front/fuel/terrain.py` | add |
| `wildfire_front/fuel/rothermel_lite.py` | add (core estimate only; spatial hooks can stub) |
| `wildfire_front/fuel/__init__.py` | add (partial exports) |
| `tests/test_fuel_rothermel_lite.py` | add |
| `scripts/run_rothermel_prior.py` | add (optional thin CLI) |

**DoD**

- `pytest tests/test_fuel_rothermel_lite.py -q` green.
- Head ≥ flank ≥ rear under default wind/slope.
- ABSTAIN path when wind missing (if already in core).
- No claim of tactical ROS in docstrings.

**Out:** no DEM download, no AEMET, no envelope.

---

### PR-2 — DEM resolve + fuel–terrain stack + build CLI

**Branch:** `feat/fuel-dem-stack`  
**Deps:** PR-1  

**Scope**

- `DemProduct`, `resolve_dem` (local → cache → opt-in download → synthetic).
- `build_stack_from_dem` / write stack JSON + grids.
- CLI `scripts/build_fuel_terrain_stack.py` (stack only; physics optional later).
- `.gitignore` for `data/dem/**/*.tif`.

**Files**

| Path | Action |
|------|--------|
| `wildfire_front/fuel/dem.py` | add |
| `wildfire_front/fuel/stack.py` | add |
| `scripts/build_fuel_terrain_stack.py` | add (stack write path) |
| `tests/test_fuel_dem.py` | add |
| `.gitignore` | DEM tif rules |

**DoD**

- Offline synthetic/local DEM tests green.
- Without DEM and without `--allow-synthetic` → exit ≠ 0 (or documented legacy note).
- No silent production synthetic when download refused without flag.

**Aligns with** DESIGN_DEM PR-A/B.

---

### PR-3 — ESA WorldCover fuel map

**Branch:** `feat/fuel-worldcover-map`  
**Deps:** PR-2  

**Scope**

- Landcover → fuel_id grid; majority mix; cache under `data/fuel_map/`.
- Wire into stack builder (`--landcover`, `--allow-fuel-download`, scheme `worldcover`).
- `.gitignore` fuel map tifs.

**Files**

| Path | Action |
|------|--------|
| `wildfire_front/fuel/fuel_map.py` | add |
| `scripts/build_fuel_map.py` | add |
| `scripts/build_fuel_terrain_stack.py` | extend |
| `tests/test_fuel_map.py` | add |
| `.gitignore` | fuel_map tifs |

**DoD**

- Synthetic mosaic path tested without network.
- Dominant fuel for Tobarra-class synthetic is deterministic.
- Stack meta includes `fuel_id_dominant` / `fuel_mix` / `fuel_map_source`.

---

### PR-4 — Spatial sector fuels + DEM slope wedges

**Branch:** `feat/fuel-spatial-sectors`  
**Deps:** PR-3  

**Scope**

- Wedge majority fuel IDs (head/flank/rear).
- Wedge mean slopes from DEM `slope_deg` grid.
- Spatial method `rothermel_lite_sectors_spatial_v1` in physics report.
- Stack CLI writes `sector_fuels_*.json`, `sector_slopes_*.json`.

**Files**

| Path | Action |
|------|--------|
| `wildfire_front/fuel/sector_fuels.py` | add |
| `wildfire_front/fuel/rothermel_lite.py` | extend spatial path |
| `scripts/build_fuel_terrain_stack.py` | extend |
| `tests/test_fuel_sector_weather.py` | add (sector parts) |
| `tests/test_fuel_sector_slope_aemet.py` | add (slope parts) |

**DoD**

- East-head grass / west-rear pine unit test.
- Spatial head ≥ flank ≥ rear under asymmetric fuels.
- UNKNOWN minority ignored in majority; strict UNKNOWN majority kept.

---

### PR-5 — Calibration recipe k (honest raw + cal metrics)

**Branch:** `feat/fuel-calibration-k`  
**Deps:** PR-2 (re-fit after PR-3/4 in PR-10 smoke)  

**Scope**

- Fit/apply sector scale factors; refuse on DEM/fuel mismatch.
- Raw ratios always present; cal metrics secondary.
- CLI `--fit-calibration`, `--calibration-recipe`, `--force-recipe`.

**Files**

| Path | Action |
|------|--------|
| `wildfire_front/fuel/calibration.py` | add |
| `wildfire_front/fuel/rothermel_lite.py` | hook apply |
| `wildfire_front/fuel/hybrid.py` | audit nested cal (if hybrid already) |
| `tests/test_fuel_calibration.py` | add |
| `scripts/build_fuel_terrain_stack.py` | extend |

**DoD**

- Fit/apply unit tests; refuse does not write recipe.
- With obs head, hybrid head invariant under k (if hybrid in same stack later: re-check in PR-7).
- Exit 4 on `CalibrationRefusedError`.

**Aligns with** DESIGN_DEM PR-C.

---

### PR-6 — WeatherScenario honesty + AEMET OpenData

**Branch:** `feat/fuel-weather-aemet`  
**Deps:** PR-1 (merge early; stack hooks in later PRs rebased)  

**Scope**

- `WeatherScenario` sources: `observed | scenario_assumed | aemet | unknown`.
- `merge_weather_drivers`: never fill library wind under incomplete observed/aemet; dir/FMC fill → assumed stamp.
- AEMET two-step fetch; **ISO-8859-1 decode**; camelCase `hrMedia` / `racha`; `dir=99` → None.
- `load_dotenv` / `load_aemet_api_key` (no overwrite existing env).
- Scripts: `build_aemet_weather_scenario.py`; fix encoding in `fetch_aemet_fwi.py`.
- Map-note Tobarra scenario remains `scenario_assumed`.

**Files**

| Path | Action |
|------|--------|
| `wildfire_front/fuel/weather.py` | add |
| `scripts/build_aemet_weather_scenario.py` | add |
| `scripts/fetch_aemet_fwi.py` | fix decode |
| `tests/test_aemet_weather.py` | add |
| `tests/test_fuel_sector_weather.py` | honesty cases |
| `data/fuel_stack/tobarra/weather_aemet_20240802.json` | optional small fixture (no secrets) |

**DoD**

- Offline unit tests for parse + merge + dotenv (no live API required in CI).
- Live smoke optional: `@pytest.mark.slow` or manual `build_aemet_weather_scenario.py`.
- Document: key in `.env` only; never commit JWT.
- Example Tobarra day: wind 5.0 m/s, RH 22, FMC~6.56, dir variable → assumed after merge.

**Security checklist**

- [ ] `.env` in `.gitignore`
- [ ] No API key in JSON fixtures / docs / commits
- [ ] CI uses offline fixtures only

---

### PR-7 — Hybrid ROS prior (α·obs + physics shape)

**Branch:** `feat/fuel-hybrid-ros`  
**Deps:** PR-1 + PR-6 (weather stamp); spatial PR-4 optional for full path  

**Scope**

- `hybrid_ros_prior` with α aging; ABSTAIN gates.
- Wire weather merge into physics/hybrid reports.
- Stack CLI `--with-physics` path (if not already complete in PR-2).

**Files**

| Path | Action |
|------|--------|
| `wildfire_front/fuel/hybrid.py` | add |
| `wildfire_front/fuel/rothermel_lite.py` | `physics_prior_report` weather fields |
| `scripts/build_fuel_terrain_stack.py` | physics + hybrid write |
| tests hybrid honesty cases | extend |

**DoD**

- With obs present, hybrid head == obs (1e-6).
- Incomplete observed wind → physics abstain; no silent 4.4 as observed.
- Artifacts: `physics_prior_tobarra.json` includes `weather_drivers_merge`.

---

### PR-8 — Hybrid envelope v3 (15/30/60) + GeoJSON

**Branch:** `feat/envelope-v3-hybrid`  
**Deps:** PR-7  

**Scope**

- Pure radii from sector ROS × horizon; cap; polar GeoJSON.
- Ensemble: hybrid residual under α + labeled physics_only diagnostic.
- CLI `build_hybrid_envelope.py` + stack `--with-envelope --with-ensemble`.
- Status `inputs_assumed` when weather assumed.
- **Do not** flip incident pipeline default from envelope v2.

**Files**

| Path | Action |
|------|--------|
| `wildfire_front/fuel/envelope.py` | add |
| `scripts/build_hybrid_envelope.py` | add |
| `scripts/build_fuel_terrain_stack.py` | envelope flags |
| `tests/test_fuel_envelope.py` | add |
| `docs/DESIGN_ENVELOPE_V3_HYBRID.md` | ship if not already |

**DoD**

- Horizons 15/30/60 monotonic head radii.
- head ≥ flank ≥ rear radii.
- Ensemble head flat when obs-locked.
- `not_tactical_dispatch=true`.

**Aligns with** DESIGN_ENVELOPE PR-A–D.

---

### PR-9 — Envelope scorecard F3.4 + Decision Card attach F3.5

**Branch:** `feat/envelope-scorecard-card`  
**Deps:** PR-8  

**Scope**

- Multi-window scorecard (slope mean/p90, obs age).
- Pablo inventory context checks (not front ROS).
- Weather-aware scorecard (`--weather`, AEMET merge honesty info checks).
- Decision Card attach weight **0**.

**Files**

| Path | Action |
|------|--------|
| `wildfire_front/fuel/envelope_scorecard.py` | add |
| `scripts/score_tobarra_envelope.py` | add |
| `tests/test_fuel_envelope_scorecard.py` | add |
| `docs/FIRE_DECISION_CARD.json` | only if attach schema needs stub (prefer runtime attach) |

**DoD**

- Scorecard verdict PASS on Tobarra engineering windows (or documented known fails).
- Card attach never sets fusion ON / never weight>0 for envelope.
- AEMET path stamps `weather_partial_station` info when dir filled.

---

### PR-10 — Tobarra AEMET one-shot pipeline + project status

**Branch:** `feat/tobarra-aemet-pipeline`  
**Deps:** PR-6 + PR-9 (+ stack PRs 2–5, 7–8)  

**Scope**

- `scripts/run_tobarra_aemet_pipeline.py` orchestrates weather → stack physics+envelope → scorecard → summary JSON.
- Stack/envelope CLI: `--fetch-aemet`, `--aemet-date`, `--aemet-station`.
- Docs: `docs/PROJECT_STATUS.md` AEMET row; this PR plan; optional mega-plan checklist tick.
- Full package exports in `fuel/__init__.py`.

**Files**

| Path | Action |
|------|--------|
| `scripts/run_tobarra_aemet_pipeline.py` | add |
| `scripts/build_fuel_terrain_stack.py` | `--fetch-aemet` |
| `scripts/build_hybrid_envelope.py` | `--fetch-aemet` |
| `wildfire_front/fuel/__init__.py` | complete exports |
| `docs/PROJECT_STATUS.md` | update |
| `docs/design/PR_PLAN_FUEL_AEMET_ENVELOPE.md` | this file |
| `outputs/fuel_stack/tobarra/*` | **do not commit** (gitignore) |

**DoD**

```powershell
pytest tests/test_aemet_weather.py tests/test_fuel_*.py -q
python scripts/run_tobarra_aemet_pipeline.py   # needs .env if no cache
# aemet_pipeline_summary.json: scorecard_verdict PASS
```

- Documented commands in PROJECT_STATUS / START_HERE snippet.
- No secrets in repo.

---

### PR-11 — (Optional) Pablo GEACAM Tobarra perimeter eval

**Branch:** `feat/ops-perimeter-pablo-tobarra`  
**Deps:** none hard (nice after PR-2 for context)  

**Scope**

- `wildfire_front/ops_perimeter.py` KMZ/KML → GeoJSON / ha growth.
- `scripts/eval_tobarra_pablo_perimeters.py`.
- Local inventory under `data/real_if/pablo_geacam_20260730_tobarra/` (README + inventory; binary KMZ policy: prefer LFS or local-only).
- Tests with synthetic polygons if raw KMZ not committed.

**Files**

| Path | Action |
|------|--------|
| `wildfire_front/ops_perimeter.py` | add |
| `scripts/eval_tobarra_pablo_perimeters.py` | add |
| `tests/test_ops_perimeter.py` | add |
| `data/real_if/pablo_geacam_20260730_tobarra/README.md` | add |
| `data/real_if/pablo_geacam_20260730_tobarra/inventory.json` | add |

**DoD**

- ha@18:30 / 21:43 match inventory if KMZ present; else skip/mark.
- Explicit: polygon growth ≠ Vp front ROS.

---

## 3. What not to put in these PRs

| Leave out | Why |
|-----------|-----|
| `.env` / API keys | secrets |
| `outputs/**` regenerable artifacts | gitignore + size |
| Large DEM/WorldCover GeoTIFFs | cache only |
| Pablo raw Dropbox dumps beyond inventory policy | privacy/size |
| ML fusion / promote live field_ops | product freeze |
| Invented Cardoso Vp/ha in `infocam_anchors.json` | O1 honesty |
| Unrelated hub/scorecard churn from other sessions | separate PR lane |

---

## 4. CI / test matrix per PR

| PR | Required pytest |
|----|-----------------|
| 1 | `test_fuel_rothermel_lite` |
| 2 | `test_fuel_dem` + PR-1 |
| 3 | `test_fuel_map` + PR-2 |
| 4 | `test_fuel_sector_*` (sector cases) |
| 5 | `test_fuel_calibration` |
| 6 | `test_aemet_weather` + weather honesty in `test_fuel_sector_weather` |
| 7 | hybrid + weather honesty |
| 8 | `test_fuel_envelope` |
| 9 | `test_fuel_envelope_scorecard` |
| 10 | full `tests/test_fuel_*.py` + `test_aemet_weather` |
| 11 | `test_ops_perimeter` |

**Live AEMET:** never required in CI. Manual/opt-in only.

---

## 5. Landing strategy (working tree already full)

Code is largely present uncommitted. Two valid approaches:

### A — Surgical stack (preferred for review)

1. Create empty branch from `main`.
2. Cherry-pick / checkout **only the files of PR-1**, commit, open PR.
3. Stack PR-2…PR-10 on top (Graphite `gt create` / plain `git checkout -b`).
4. Re-run DoD tests at each layer.

### B — Fat intermediate then split

1. One WIP branch `wip/fuel-aemet-all` with full tree (never merge as-is).
2. Use `git reset` / path commits to carve PR-1…N in order.
3. Or `git checkout main -- <paths>` inverse to leave only current PR paths.

### C — Collapse if time-boxed (current landing path)

| Collapsed | Contains | Status 2026-08-03 |
|-----------|----------|-------------------|
| **PR-α Core physics** | PR-1 + 2 + 3 + 4 + 5 + 7 | **DONE** — `/implement` 0 open issues · 87 tests |
| **PR-β Envelope + AEMET** | PR-6 + 8 + 9 + 10 | **DONE DoD** — pipeline PASS · `tests/test_pr_beta_envelope_aemet.py` |
| **PR-γ (optional)** | PR-11 Pablo perímetros | Pending if not landed with ops_perimeter |

**PR-β verify**

```powershell
pytest tests/test_aemet_weather.py tests/test_fuel_envelope.py `
  tests/test_fuel_envelope_scorecard.py tests/test_pr_beta_envelope_aemet.py -q
python scripts/run_tobarra_aemet_pipeline.py   # uses .env or cached weather
```

Still keep secrets out; never commit `.env` / large GeoTIFFs / `outputs/`.

---

## 6. Suggested PR titles (conventional commits)

1. `feat(fuel): Mediterranean models + Rothermel-lite core`
2. `feat(fuel): DEM resolve + terrain stack builder`
3. `feat(fuel): ESA WorldCover fuel map for Tobarra stack`
4. `feat(fuel): spatial sector fuels and DEM slope wedges`
5. `feat(fuel): honest k calibration recipe (raw+cal metrics)`
6. `feat(fuel): WeatherScenario honesty + AEMET OpenData path`
7. `feat(fuel): hybrid ROS prior with weather merge`
8. `feat(envelope): hybrid short-horizon v3 15/30/60 + ensemble`
9. `feat(envelope): Tobarra scorecard F3.4 + Decision Card weight-0 attach`
10. `feat(ops): Tobarra AEMET end-to-end pipeline + status docs`
11. `feat(ops): Pablo GEACAM Tobarra perimeter eval (optional)`

---

## 7. Key decisions (for reviewers)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| AEMET encoding | try utf-8 → iso-8859-1 → cp1252 | Real datos payloads use latin-1 accents |
| AEMET dir 99 | `wind_from_deg=None` then library fill + assumed | AEMET code for variable; honesty > false azimuth |
| Default station | 8175 Albacete Base Aérea | Regional climatology, not on-fire tower — notes must say so |
| Envelope product | v3 hybrid parallel to v2 | Do not break incident `emergency_products` v2 default |
| Envelope on Decision Card | weight 0 | Audit only; no dispatch |
| Calibration k | engineering single-fire | Not multi-IF LOFO science pass |
| Fuel dominant Tobarra | MED_GRASS from WorldCover | Replaces synthetic maquis overprediction |

---

## 8. Open / follow-up (not this stack)

| ID | Item | Owner |
|----|------|--------|
| O1 | Cardoso Vp/ha second anchor | Human / Pablo |
| O2 | Official national perimeter | Observatorio |
| W1 | AEMET hourly / nearer station than 8175 | Eng after O1 |
| W2 | Multi-IF DEM stacks beyond Tobarra | Eng |
| W3 | Flip incident pipeline to envelope v3 | Product decision later |

---

## 9. Acceptance snapshot (post PR-10)

From live run 2026-08-03 (`outputs/fuel_stack/tobarra/aemet_pipeline_summary.json` regenerable):

| Metric | Value |
|--------|--------|
| weather_source | `aemet` |
| physics_head_m_min | ~6.19 |
| hybrid_head_m_min | 5.71 |
| envelope head 15′ | 85.65 m |
| scorecard | **PASS** |
| assumed reason | partial fill `wind_from_deg` (AEMET dir=99) |

---

## 10. Execute next

```text
# After this plan is approved:
/execute-plan docs/design/PR_PLAN_FUEL_AEMET_ENVELOPE.md
# or manual Graphite stack PR-1…PR-10
```

Human gate before any PR that touches Gmail, remote force-push, or production secrets.

---

## 11. Checklist for merge of final stack

- [ ] All listed pytest green on CI
- [ ] No `.env` / JWT in git history of branch
- [ ] `outputs/` and large tifs not committed
- [ ] PROJECT_STATUS AEMET row honest (assumed partial dir)
- [ ] field_ops fusion still OFF
- [ ] infocam Cardoso still `pending_external` / null Vp
- [ ] Optional: PR-11 Pablo perimeter separate or same train
)
