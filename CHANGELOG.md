# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Professional development workflow: `Makefile`, `CONTRIBUTING.md`, `LICENSE`.
- CI/CD pipeline with concurrency control and pip caching.
- Ruff linting + formatting and mypy strict type-checking.
- Meta-labeler test suite (8 tests covering temporal consistency).
- Batch processing pipeline for multi-fire ingestion.
- MIT license declaration in `pyproject.toml`.

### Changed
- CI mypy step now blocks on errors (removed `|| true`).
- README restructured with badges, clear sections, and professional layout.
- GitHub Actions workflows use `cache: pip` for faster runs.

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