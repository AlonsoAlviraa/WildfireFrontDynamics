# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed — Product SPA industrial C2 closeout (2026-08-11)
- Shell **Stitch WFD Industrial C2**: dual-mode Fácil|Pro, map-first, tokens `#0B1220`, IBM Plex Sans.
- **Primary acts** always visible: Estado · Decidir · Acta (`primary-acts`); fire catalog exposes `acta_cmd`.
- Optional **`--serve`** (loopback static HTTP on output dir, default port 8766) + aliases **`spa`** / **`console`**.
- Industry stress UX rails: `docs/design/EMERGENCY_UX_INDUSTRY.md` · `docs/design/stitch_wfd_industrial/`.
- Docs: `docs/APP.md`. Tests: `test_product_app` · `test_spa_layout` · `test_plain_language_app` aligned to C2.
- **Rails frozen:** field_ops fusion OFF · not tactical dispatch · **no GO_Q invent**.

### Added — Product SPA ops console (`app`, 2026-08-10)
- **`wildfire-front app`**: professional dark ops SPA (Leaflet map + dashboard) for third-party demos.
- Builders compose **`operator_ux` brief** + **`map_status`** payload; optional Decision Card / ops metrics from `--work-dir` outbox.
- Schema **`wfd_product_app_v1`**; default offline; `--open` · `--role` · `--live` / `--fixture-csv`.
- Aliases: **`spa`** · **`console`**. Docs: `docs/APP.md`. Tests: `tests/test_product_app.py`.
- **Rails frozen:** field_ops fusion OFF · not tactical dispatch · no GO_Q invent · IoU ≠ ROS.

### Changed — Product SPA full ops console (2026-08-10)
- Fire picker: scan `outputs/incidents` + known packs; `--list-fires` / `--fire ID`.
- SPA tabs: Brief · Decisión · **Funciones** (all product CTAs) · **Nuevo IF** intake steps.
- Rebuild guidance for static HTML (copy-paste commands bound to selected work-dir).
- Modules: `product/fire_catalog.py`; expanded `app_spa` payload `fires` / `product_actions` / `new_fire_intake`.
- Docs: `docs/APP.md`. Tests: `tests/test_product_app.py`.

### Added — Fire-status map + FIRMS NRT connectivity (2026-08-10)
- **`wildfire-front map`**: Leaflet map of local fronts/envelopes + optional NASA FIRMS NRT hotspots.
- Client: area API (`FIRMS_MAP_KEY`) or public Europe VIIRS 24h CSV; offline/`--fixture-csv` paths with explicit `connectivity` status (never fake live points).
- Schema `wfd_fire_status_map_v1`; honesty rails on HTML + JSON (not dispatch; hotspots ≠ burned area; field fusion OFF).
- Docs: `docs/FIRE_STATUS_MAP.md`. Tests: `tests/test_fire_status_map.py` + `tests/fixtures/firms_sample_hotspots.csv`.

### Added — Operator CLI `brief` (2026-08-10)
- **`brief` / `resumen` / `summary` / `briefing`**: professional one-screen operational brief with gates, honesty rails, next action, and role playbook (`operator` · `field` · `lab` · `decision`).
- JSON schema **`wfd_operator_brief_v1`** (`--json`); builders in `product/operator_ux.py`.
- Discoverable from root `--help`, Start here line, and `commands` map.
- Docs: `docs/OPERATOR_CLI_CHANGES.md` (pass 3). Tests: `tests/test_operator_ux.py` brief suite.
- **Rails frozen:** field_ops fusion OFF · IoU ≠ ROS · no GO_Q invent · not tactical dispatch.

### Changed — Operator CLI UX footguns (2026-08-10)
- **`help` / `commands` / `cmds` / `ayuda`**: role-grouped command map (`wfd_cli_commands_v1`).
- **`doctor` top-level**: ML lab pre-flight by default; `--inbox` → incident doctor; `--target hub` routes only.
- **`status`**: bare → operator board; `status --work-dir …` → incident status.
- Argparse errors on **known** commands: contextual hints (no operator cold-start spam).
- **`export-acta` / `replay-decide`**: friendly errors + exit 2; bare `decide` notes policy `default` vs `field_ops`.
- **UX pass 2:** bare **`ml`** → lab hub (`wfd_ml_hub_v1`); bare **`incident`** → field hub (`wfd_incident_hub_v1`); **`version` / `ver` / `about`** aliases; typo suggestions (`¿Quisiste decir?`); `ingest-geotiff` missing-args hint; root `--help` “Start here” line.
- Docs: `docs/OPERATOR_CLI_CHANGES.md`. Tests extended in `tests/test_operator_ux.py`.
- **Rails frozen:** GO_Q / fusion / ML gates unchanged (hub reports; does not flip).

### Added — S4 multipass Tobarra unlock (2026-08-05)
- `wildfire_front/arrival_ros.py` — multipass discovery + O'Neill arrival-gradient ROS + S4 board schema.
- `scripts/run_tobarra_multipass_s4.py` — end-to-end ops path on real Tobarra LWIR/masks (≥2 frames).
- Export: `outputs/tobarra_multipass_s4/` (s4_board, arrival_field, front_dynamics) — status **OK**.
- S4 re-check: `scripts/run_deep_research_s4_arrival_ros_note.py` reads multipass board; PLAN_ML_PRODUCT_STATUS S4 → OK.
- Tests: `tests/test_tobarra_multipass_s4.py` (synthetic multipass, no GPU).

### Added — Deep research S1/S3/S4 implementation (2026-08-05)
- S1: `wildfire_front/ml/lab_selective_sdc.py` + `scripts/run_lab_ml_loop_v34_selective_sdc.py` — Soft Dice Confidence proxy ranking bake-off; **KILL_SDC_PROMOTE** (keep iter1 reject).
- S3: `scripts/run_deep_research_s3_open_perimeter_board.py` — multi-pack open Hausdorff-lite board (6 packs).
- S4: `scripts/run_deep_research_s4_arrival_ros_note.py` — arrival-time ROS inventory (later unlocked via multipass export).
- Tests: `tests/test_lab_selective_sdc.py`. Boards under `outputs/ml_eval/lab_loop/` and `docs/fire_intel/`.

### Added — Deep research strategies expansion (2026-08-05)
- `/deep-research` fan-out on product strategies 2024–2026 beyond mega-research / SOTA stack corpus.
- Report: `docs/fire_intel/DEEP_RESEARCH_STRATEGIES_2024_2026.md` · claims JSON (75 survived, 0 dropped).
- Shortlist S1–S4: Soft Dice Confidence risk–coverage · morphological conformal masks · EFFIS Hausdorff-lite · arrival-time ROS (ops).
- Linked from CURRENT_STATE, goals hub, RESEARCH_TO_GRAPH_V6_MAP. No field fusion / no Tobarra KEEP reopen.

### Changed — Status / goals sync post Tobarra KILL (2026-08-05)
- Canonical snapshot: `docs/CURRENT_STATE.md` · goals hub: `docs/goals/README.md`.
- Mega goals **closed**: W3 **MET** · Tobarra KEEP-or-KILL **KILL** (fresh LOFO IoU 0.4776, K1 fail, leak 0).
- Updated: MEMORY, PROJECT_STATUS, PLAN_ML_PRODUCT_*, ML_PRODUCT_START_HERE, CHEATSHEETs, PRODUCCION_INDUSTRIAL_ESTADO, graph STATE, design ML lab loop, README, START_HERE.
- Workflows `wfd-ml-w3-mega-goal` / `wfd-ml-tobarra-keep-or-kill`: marked closed (re-audit/smoke only).
- Rails unchanged: `ml_product_go=false` · field_ops fusion OFF · product residual = **H1 GO_Q**.

### Changed — Mega audit follow-ups (2026-08-05)
- Docs: pack count honesty (11 CEMS emsr* in README); START_HERE IoU provenance-only; Hellín inventory row vs confirmed; MEMORY M3.4 wording.
- CLI: help epilog groups Operario/Lab/Campo/Eng; `decide --allow-ml-live-in-fusion` help clarifies no field_ops policy rewrite.
- Audit reports: `docs/MEGA_AUDIT_OPERATOR_CLI_20260805.md`, `docs/GMAIL_AUDIT_20260805.md` (Gmail MCP `invalid_grant`).

### Added — Operator UX mode + engineering loop (2026-08-04)
- **`wildfire-front operator`**: single entry for non-code users — traffic light (VERDE/AMARILLO/ROJO), 4 acts, plain GO_Q gap.
- Subcommands: `operator checklist` · `operator do --act 1|2|3|4` · `operator explain-abstain`.
- **ABSTAIN plain language**: short `decide` note + full Spanish box (not a bug/crash).
- Docs: `docs/OPERATOR_UX_LOOP_LOG.md` (iters 1–17 · **PLATEAU eng**; residual = H1 human).
- **Default CLI:** no COMMAND → `operator`. Top-level: **`ensayo`** · **`next`/`go_q`** · **`checklist`**. Compact ensayo (no duplicate scoreboard). Session stamp merge. Checklist honesty ≠ H1.
- Status sync: PROJECT_STATUS + MEMORY; tests `tests/test_operator_ux.py`.
- **Rails unchanged:** GO_Q remains **partial** (H1 human); field_ops ML fusion OFF; no `ml_product_go` flip.

### Added — ML lab product surface (`wildfire-front ml`, 2026-08-04)
- **`wildfire-front ml list|show|predict|card|doctor`**: lab product CLI (default `clm_ensemble_v34`). Offline list/show/doctor without weights; predict/card clean exit 1 if weights missing.
- Scorecard productization: `ml show` loads `ML_PRODUCT_SCORECARD.json` + promote record + catalog + field_ops fusion flag (`--json`).
- Docs: `docs/PLAN_ML_PRODUCT_USABLE.md`, `docs/PLAN_ML_PRODUCT_STATUS.json`, `docs/ML_PRODUCT_START_HERE.md`, `docs/CHEATSHEET_ML_LAB.md`; links in START_HERE + CURSO m6 + PROJECT_STATUS.
- Tests: `tests/test_cli_ml_product.py` (rails: `ml_product_go=false`, field_ops fusion OFF, IoU ≠ ROS).
- **Rails unchanged:** `field_ops.allow_ml_live_in_fusion=false` · no `ml_product_go` flip · catalog 0.8963 provenance only.

### Added — CLI teach product surface (v7 teach-cli, 2026-08-04)
- **`wildfire-front teach`**: 4-act learning path (ver → callarse → decidir → probar) with copy-paste commands, `--act`, `--json`.
- **`wildfire-front show`**: gates snapshot (GO_MES / GO_Q partial / fusion OFF) + key paths; optional `--open` for existing HTML.
- **`wildfire-front demo-third-party`**: thin wrapper for E1 pack + E3 replay (replay ON by default; `--no-replay` / `--skip-build`).
- **`decide --explain`**: expanded sources / weights / reasons / disclaimers for teaching (no fusion change; no-op with `--json`).
- Docs: `docs/CHEATSHEET_DEMO_12MIN.md`; light links in START_HERE + CURSO; plan track **T** (does **not** flip GO_Q).

### Fixed — ML-Sprint 2: Pre-trained weights transfer integrity (2026-07-09)
- **Root cause**: When loading v1 checkpoints into the v2 model,
  `load_pretrained_weights` emitted spurious `missing keys` / `shape mismatch`
  warnings for `fusion_gate`, `refine`, and `temporal_projection` — the three
  layers that are **intentionally** handled by smart-init. This misled
  operators into thinking the weight transfer was broken.
- **Fix**: Smart-init keys are now filtered from `missing` / `shape_mismatch`
  lists *before* warnings are emitted. The loader's diagnostic output now
  reflects only genuinely problematic keys.
- **Verification**: Added regression test
  `test_load_pretrained_weights_filters_smart_init_from_warnings`. Full suite
  passes (105/105) even with `-W error::UserWarning`.

### Added — ML-Sprint 1: Real-fire training pipeline completion (2026-07-09)
- **Pipeline Stage 5**: `scripts/geotiff_to_training_patches.py` — closes the gap
  between mask-materialization and cloud training by exporting GeoTIFF pairs
  into `.npz` patches matching the `NpzWildfireDataset` contract
  (sequence `(3,16,30,30)`, current/target fire `(30,30)`).  Includes
  provenance `manifest.json` and optional DEM/NDVI/FSM/weather enrichment.
- **Tests**: `tests/test_geotiff_to_patches.py` (3 new tests verifying
  contract shapes, dataset round-trip, and max_patches limit).

### Fixed — CRS contract unification (2026-07-09)
- `wildfire_front/geometry_speed.py` now accepts `local_cartesian_m`
  (used by `synthetic.py`) alongside `projected_metric`, and allows
  `crs=None` when both observations are consistent. Previously, mixing
  synthetic data (`crs=None`) with real data or using `local_cartesian_m`
  raised a false validation error.
- Added 2 new tests covering the CRS unification (`local_cartesian_m`
  accepted, mixed CRS rejected).

### Added — Production hardening (2026-07-07)
- **Containerization**: Multi-stage `Dockerfile` (builder + runtime) with non-root
  user, healthcheck, OCI labels, and layer caching via `.dockerignore`.
- **Security**: `SECURITY.md` with responsible disclosure policy and SLA.
- **Dependency governance**: `.github/dependabot.yml` (pip, GitHub Actions, Docker).
- Real wildfire data ingestion completed: `hellin_2024`, `retuerta_2025`,
  `brazatortas_2025` (70 new TIFs, 32 masks). `la_estrella_acom2_2024` completed
  (67 TIFs; 50 frames rejected by quality control).

### Added — Engineering baseline
- Professional development workflow: `Makefile`, `CONTRIBUTING.md`, `LICENSE`.
- CI/CD pipeline with concurrency control and pip caching.
- Ruff linting + formatting and mypy strict type-checking.
- Meta-labeler test suite (11 tests: entropy, features, train/predict,
  single-class guard, save/load, determinism).
- Batch processing pipeline for multi-fire ingestion.
- MIT license declaration in `pyproject.toml`.

### Changed
- CI mypy step now blocks on errors (removed `|| true`).
- README restructured with badges, clear sections, and professional layout.
- GitHub Actions workflows use `cache: pip` for faster runs.
- `REPO_ANALYSIS.md` updated to reflect production-ready status and real metrics.

### Fixed
- Ruff lint errors in `wildfire_front/ml/` module (3 auto-fixed).

## [0.1.0] - 2026-07-07

### Added
- Synthetic wildfire front generation with known ground truth.
- GeoTIFF ingestion pipeline with leak-free observed/inferred/GT separation.
- SHA-256 content hashing for artifact traceability.
- Adaptive MAD-based thermal segmentation.
- Non-radial local speed estimation with uncertainty quantification.
- Self-contained HTML report generation.
- ML model definitions (A3C PerCell LSTM) and training pipeline.
- Real wildfire data ingestion: Tobarra, Cardoso, La Estrella ACOM1.
- Scientific documentation suite (architecture, provenance, contracts).

[Unreleased]: https://github.com/AlonsoAlviraa/WildfireFrontDynamics/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/AlonsoAlviraa/WildfireFrontDynamics/releases/tag/v0.1.0