# WFIGS far-background BCE DEV protocol — 2026-08-20

## Rationale

The spatial DEV decoder showed that restricting predicted growth to 12 pixels
from the observed t0 front gives a small event-macro gain, while the global
negative-background BCE candidate did not. This follow-up tests the same prior
inside training: penalize false-positive growth only beyond 12 pixels from the
t0 front, leaving near-front background unconstrained by this auxiliary term.

## Frozen recipe

- Source: RCDA-VAL-selected `resunet` hybrid checkpoint, seed 47.
- Data: WFIGS expansion TRAIN (184 events) for updates; expansion DEV (42
  events) for epoch/threshold selection.
- Target: hybrid extent + incremental growth; growth channel is evaluated.
- Trainable scope: decoder only; encoder/context frozen.
- 18 epochs maximum, patience 5, batch size 4, AdamW `lr=1e-4`, weight decay
  `1e-4`, gradient cap 5.
- Augmentation enabled.
- Focal-Tversky alpha `0.3`, beta `0.7`, gamma `0.75`.
- Front-ring BCE weight `0.05`, radius 16 px.
- Far-background BCE weight `0.05`, applied only to target-zero pixels whose
  encoded t0-front distance is at least 12 px.
- Global negative-background BCE weight: `0.0`.
- Selection metric: event-macro growth IoU; threshold selected on DEV only.

## Isolation and decision rule

The runner rejects roots containing `confirm`, `test` or `prospective` and only
loads TRAIN/DEV manifests. It validates RCDA VAL source selection and asserts
that WFIGS TEST is not loaded. The candidate is promoted only if it exceeds the
frozen single-seed control (`0.131902`) by at least `0.005`; otherwise it is
rejected without replication or confirmation evaluation.

## Publication boundary

Only code, tests, protocol and aggregate DEV metrics are publishable. Raw
WFIGS geometries, tensors, tiles, checkpoints and per-pixel predictions remain
local under the source's noncommercial/internal-use conditions.
