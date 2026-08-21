# WFIGS corrected geometry augmentation three-seed replication — 2026-08-21

## Motivation

The corrected single-seed combined recipe cleared the DEV gate after making
front-normal augmentation physically consistent. This replication measures
whether that corrected gain survives the three RCDA paper seeds; the earlier
uncorrected implementation is excluded.

## Fixed recipe

- Sources: RCDA-VAL-selected residual hybrid checkpoints, seeds 11, 29 and 47.
- Features: 16 RCDA channels + signed front distance/normal channels + four
  valid-pixel median/IQR EO residuals.
- Augmentation: vector-correct flips/quarter-turns for front normals and wind.
- Data: WFIGS expansion TRAIN (184 events), selection on DEV (42 events).
- Trainable scope: decoder plus both residual input projections; AdamW `1e-4`,
  batch 4, 18 epochs/patience 5, focal-Tversky `(0.3,0.7,0.75)`, front-ring
  BCE `0.05`.
- Seed aggregation: mean probability; selection on event-macro growth IoU.

## Isolation and decision

The runner requires RCDA VAL-only source proof, refuses roots containing
`confirm`, `test` or `prospective`, and asserts WFIGS TEST is not loaded.
Promotion requires a stable `+0.005` event-macro gain over the frozen ensemble
(`0.136178`); otherwise confirmation remains closed.

## Publication boundary

Only code, tests, protocol and sanitized aggregate metrics may be published.
WFIGS geometries, tensors, tiles, checkpoints and per-pixel outputs remain
private.
