## Summary
Brief description of what this PR changes and why.

## Type of change
- [ ] Bug fix (non-breaking)
- [ ] New feature (non-breaking)
- [ ] Breaking change (affects existing API/data products)
- [ ] Documentation only
- [ ] Test / CI improvement

## Scientific checklist
- [ ] `observed` / `inferred` / `ground_truth` separation preserved
- [ ] No ground-truth leakage (train/val/test splits remain disjoint)
- [ ] Abstention logic intact (uncertainty still yields ABSTAIN)
- [ ] Provenance: SHA-256 manifests written for new artifacts
- [ ] Ensemble mix/temperatures not tuned on holdout test / LOFO-CARDOSO

## Data changes
- [ ] No new data ingested
- [ ] New data ingested — manifest + audit doc updated
- [ ] Ingestion contract (`docs/GEOTIFF_INPUT_CONTRACT.md`) still satisfied

## Quality gates
- [ ] `ruff check wildfire_front tests scripts` passes
- [ ] `ruff format --check wildfire_front tests` passes
- [ ] `mypy wildfire_front --ignore-missing-imports` passes
- [ ] `python -m pytest tests/ -q` passes (~270+ test functions / ~40 modules)
- [ ] Product paths updated if relevant (`incident/`, `product/`, `open_if/`, catalog v21/v34)
- [ ] `ARCHITECTURE.md` / product docs updated when surface changes

## Related issues
Closes #
