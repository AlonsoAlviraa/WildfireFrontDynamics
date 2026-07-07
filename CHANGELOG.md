# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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