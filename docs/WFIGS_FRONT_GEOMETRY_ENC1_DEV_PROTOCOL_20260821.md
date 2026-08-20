# WFIGS front-geometry + enc1 DEV protocol — 2026-08-21

## Motivation

The single-seed front-geometry adapter was a near miss (`0.136740` versus the
`0.131902` control), while the three-seed ensemble was not stable. This
follow-up tests whether low-level domain shift is the bottleneck by unfreezing
the complete first residual encoder block in addition to the decoder. Deeper
encoder/context blocks remain frozen.

## Fixed recipe

- Source: RCDA-VAL-selected residual hybrid checkpoint, seed 47.
- Features: 16 encoded channels plus signed front distance and normalized
  horizontal/vertical front derivatives, derived only from `previous_fire`.
- Data: WFIGS expansion TRAIN (184 events), selection on DEV (42 events).
- RCDA TRAIN normalization; hybrid target; augmentation enabled.
- Trainable scope: full `enc1` plus decoder; `enc2`, `enc3`, `enc4` and context
  remain frozen.
- AdamW `lr=1e-4`, weight decay `1e-4`, batch 4, maximum 18 epochs, patience 5,
  gradient cap 5; focal-Tversky `(0.3, 0.7, 0.75)` and front-ring BCE `0.05`.
- Selection metric: event-macro growth IoU on DEV.

## Isolation and decision

The runner refuses roots containing `confirm`, `test` or `prospective`, checks
RCDA VAL source selection, and asserts WFIGS TEST is not loaded. Promotion
requires `+0.005` event-macro IoU over the frozen single-seed control (`0.131902`);
otherwise it is rejected without replication or confirmation.

## Publication boundary

Only code, tests, protocol and sanitized aggregate DEV metrics may be published.
WFIGS geometries, tensors, tiles, checkpoints and per-pixel outputs remain
private.
