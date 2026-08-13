# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added — IF weakness / candidate board (2026-08-13)
- `scripts/score_if_weakness_board.py` scores on-disk CLM + open-IF trees with fail-closed R1–R6 / H1–H7.
- Writes `docs/WEAKNESS_BOARD.json` + `.md` and `docs/IF_ONDISK_INVENTORY.json` (counts + tree fingerprints; no raw GeoTIFF hashes).
- Missing anchors / unknown `--fire-id` exit 1. Never writes `data/infocam_anchors.json`. No v34 retrain / KEEP reopen.

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