# WFIGS physically consistent geometry augmentation — 2026-08-21

## Motivation

The combined geometry + tile-EO recipe cleared the DEV gate for seed 47 but
replicated weakly across seeds. Audit found that spatial flips/rotations moved
the appended front-normal channels without transforming their vector signs.
This candidate fixes that implementation bug while keeping the learned recipe,
loss, budget and data splits unchanged.

## Fixed recipe

- Source: RCDA-VAL-selected residual hybrid checkpoint, seed 47.
- Features: 16 RCDA channels + signed front geometry (distance, normal x/y) +
  four valid-pixel median/IQR EO residuals.
- Augmentation: horizontal/vertical reflections and quarter-turns now apply the
  corresponding vector transformation to `front_normal_x/y`; wind channels
  retain their existing physical transformation.
- Data: WFIGS expansion TRAIN (184 events), selection on DEV (42 events).
- Trainable scope: decoder plus both residual input projections; same AdamW
  `1e-4`, batch 4, 18 epochs/patience 5, front-ring BCE `0.05`.
- Selection metric: event-macro growth IoU on DEV.

## Isolation and decision

The runner refuses roots containing `confirm`, `test` or `prospective`, checks
RCDA VAL source selection, and asserts WFIGS TEST is not loaded. Promotion
requires `+0.005` event-macro IoU over the frozen residual control (`0.131902`);
otherwise it is rejected without replication or confirmation.

## Publication boundary

Only code, tests, protocol and sanitized aggregate metrics may be published.
WFIGS geometries, tensors, tiles, checkpoints and per-pixel outputs remain
private.
