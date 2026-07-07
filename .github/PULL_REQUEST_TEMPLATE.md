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
- [ ] Abstention logic intact (uncertainty still yields abstention)
- [ ] Provenance: SHA-256 manifests written for new artifacts

## Data changes
- [ ] No new data ingested
- [ ] New data ingested — manifest + audit doc updated
- [ ] Ingestion contract (`docs/GEOTIFF_INPUT_CONTRACT.md`) still satisfied

## Quality gates
- [ ] `ruff check .` passes
- [ ] `python -m pytest tests/ -q` passes (96 tests)
- [ ] `REPO_ANALYSIS.md` updated if scope changed

## Related issues
Closes #