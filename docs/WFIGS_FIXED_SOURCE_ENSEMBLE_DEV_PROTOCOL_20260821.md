# WFIGS fixed-source / three-adaptation-seed DEV protocol — 2026-08-21

## Motivation

The RCDA source seed 47 is the strongest and most repeatable source checkpoint
in the current DEV pilots, while changing the source seed produced large
variance. This experiment fixes the RCDA VAL-selected seed-47 weights and
varies only the WFIGS adaptation RNG (11, 29, 47), testing whether source
initialization is the dominant factor.

## Fixed recipe

- One source: RCDA-VAL-selected residual hybrid seed 47.
- Adaptation seeds: 11, 29 and 47; mean-probability ensemble.
- Features: 16 RCDA channels + signed front geometry + four valid-pixel
  median/IQR EO residual channels.
- Vector-correct geometry augmentation; WFIGS expansion TRAIN (184 events),
  selection on DEV (42 events).
- Decoder plus both residual input projections trainable; deeper encoder/context
  frozen; AdamW `1e-4`, batch 4, 18 epochs/patience 5, front-ring BCE `0.05`.
- Selection metric: event-macro growth IoU on DEV.

## Isolation and decision

The runner verifies the fixed source was selected on RCDA VAL, refuses roots
containing `confirm`, `test` or `prospective`, and asserts WFIGS TEST is not
loaded. Promotion requires `+0.005` event-macro IoU over the frozen three-seed
reference (`0.136178`); otherwise confirmation remains closed.

## Publication boundary

Only code, tests, protocol and sanitized aggregate metrics may be published.
WFIGS geometries, tensors, tiles, checkpoints and per-pixel outputs remain
private.
