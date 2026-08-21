# WFIGS combined geometry + tile-EO DEV protocol — 2026-08-21

## Motivation

Two target-independent feature families showed complementary signals: explicit
front geometry improved event-level IoU for one seed, while robust per-tile EO
residuals improved pooled IoU. This fixed ablation appends all seven channels to
test whether their combination is useful without changing the decoder budget.

## Fixed recipe

- Source: RCDA-VAL-selected residual hybrid checkpoint, seed 47.
- Features: 16 encoded RCDA channels + three signed-distance/normal channels +
  four valid-pixel median/IQR EO residual channels.
- Data: WFIGS expansion TRAIN (184 events), selection on DEV (42 events).
- RCDA TRAIN normalization; hybrid target; augmentation enabled.
- Trainable scope: decoder plus both residual input projections; deeper encoder
  and context remain frozen.
- AdamW `lr=1e-4`, weight decay `1e-4`, batch 4, maximum 18 epochs, patience 5,
  gradient cap 5; focal-Tversky `(0.3, 0.7, 0.75)` and front-ring BCE `0.05`.
- Selection metric: event-macro growth IoU on DEV.

## Isolation and decision

The runner refuses roots containing `confirm`, `test` or `prospective`, checks
RCDA VAL source selection, and asserts WFIGS TEST is not loaded. Promotion
requires `+0.005` event-macro IoU over the frozen residual control (`0.131902`);
otherwise it is rejected without replication or confirmation.

## Publication boundary

Only code, tests, protocol and sanitized aggregate DEV metrics may be published.
WFIGS geometries, tensors, tiles, checkpoints and per-pixel outputs remain
private.
