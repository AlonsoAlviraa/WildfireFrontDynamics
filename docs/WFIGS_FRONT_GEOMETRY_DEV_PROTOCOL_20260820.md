# WFIGS explicit-front-geometry DEV protocol — 2026-08-20

## Motivation

The RCDA feature bridge already exposes unsigned distance from the previous
perimeter, but it does not expose which direction the front is facing. This
candidate appends three deterministic channels derived only from
`previous_fire`: signed front distance (positive outside) and the normalized
horizontal/vertical derivatives of that field. No future perimeter, hotspot or
target pixel is used to construct the features.

## Fixed recipe

- Source: RCDA-VAL-selected residual hybrid checkpoint, seed 47.
- Features: existing 16 encoded channels plus three front-geometry channels.
- Data: WFIGS expansion TRAIN (184 events), selection on DEV (42 events).
- RCDA TRAIN normalization; hybrid target; augmentation enabled.
- Trainable scope: decoder plus both residual `enc1` input projections;
  deeper encoder and context remain frozen.
- AdamW `lr=1e-4`, weight decay `1e-4`, batch 4, maximum 18 epochs, patience 5,
  gradient cap 5.
- Focal-Tversky alpha `0.3`, beta `0.7`, gamma `0.75`; front-ring BCE `0.05`,
  radius 16 px.
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
