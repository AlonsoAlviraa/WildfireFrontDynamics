---
name: Bug report
about: Report a reproducible issue in the pipeline (ingestion, geometry, ML, provenance)
title: "[BUG] "
labels: bug, triage
assignees: ''
---

## Summary
A clear 1-2 sentence description of the bug.

## Steps to reproduce
1.
2.
3.

## Expected behavior
What you expected to happen.

## Actual behavior
What actually happened (include error/traceback).

## Environment
- OS: [e.g. Windows 11, Ubuntu 22.04]
- Python: [e.g. 3.11.9]
- Commit / branch: [e.g. `4c0584a` / `main`]

## Evidence
Logs, screenshots, or output of the affected command.

## Affected component
- [ ] Core pipeline (`synthetic`, `reconstruction`, `geometry_speed`)
- [ ] GeoTIFF ingestion (`wildfire_front.ingestion.geotiff`)
- [ ] ML pipeline (`wildfire_front.ml.*`)
- [ ] CLI (`wildfire_front.cli`)
- [ ] Provenance / identity (`identity.py`, manifests)
- [ ] Other:

## Severity
- [ ] Blocker (prevents release)
- [ ] Major (incorrect results)
- [ ] Minor (cosmetic / edge case)