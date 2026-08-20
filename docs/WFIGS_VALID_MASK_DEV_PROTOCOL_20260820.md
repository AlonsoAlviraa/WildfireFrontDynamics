# WFIGS explicit valid-mask DEV protocol — 2026-08-20

## Motivation

The WFIGS tensors contain an explicit `valid_data` channel, but the existing
RCDA adapter discarded it while converting physical channels. DEV inspection
found invalid pixels in 25/42 events. This candidate appends that mask as a
17th feature and lets only the first input projection plus decoder adapt; the
pretrained encoder representation remains frozen.

## Fixed recipe

- Source: RCDA-VAL-selected residual hybrid checkpoint, seed 47.
- Features: existing 16 encoded channels plus binary WFIGS `valid_data` mask.
- Data: WFIGS expansion TRAIN (184 events), selection on DEV (42 events).
- RCDA TRAIN normalization; hybrid target; augmentation enabled.
- Trainable scope: decoder plus `enc1.body.0` input projection only.
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
