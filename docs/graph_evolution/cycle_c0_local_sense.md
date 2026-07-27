# Cycle c0 — local sense (orchestrator parallel track)

**Time:** 2026-07-27  
**HEAD:** `ba01ee2`

## Gates

| Gate | Value |
|------|-------|
| u1_test_honest | true |
| ml_product_go | false |
| allow_ml_live_in_fusion_recommended | true |
| primary.model_iou | 0.8569 |
| ece_patch_conf | 0.1528 |
| field_ops.allow_ml_live_in_fusion | false |
| research_open.allow_ml_live_in_fusion | true |

## Tooling

- ruff format: pass (138 files)
- ruff check: pass

## Dirty tree note

Uncommitted docs/cleanup/EXT forms remain local — not part of integrity of pushed `main`.

## Parallel workflow

`wfd-autonomous-cycle` c0-bootstrap active at Scan phase (honesty/ci/dual).
