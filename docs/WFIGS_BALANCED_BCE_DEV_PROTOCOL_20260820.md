# WFIGS balanced-growth BCE DEV protocol — 2026-08-20

## Question

The control uses recall-oriented Focal-Tversky and a small front-ring BCE. This
candidate adds a class-balanced BCE over the complete incremental-growth mask,
with a fixed coefficient, to test whether sharper pixel calibration improves
event IoU without changing the source or decoder capacity.

## Fixed recipe

- Source: RCDA-VAL-selected `resunet` hybrid checkpoint, seed 47.
- WFIGS expansion TRAIN (184 events) for updates; DEV (42 events) for selection.
- RCDA TRAIN normalization; hybrid target; decoder-only; augmentation enabled.
- AdamW `lr=1e-4`, weight decay `1e-4`, batch 4, maximum 18 epochs, patience 5,
  gradient cap 5.
- Focal-Tversky alpha `0.3`, beta `0.7`, gamma `0.75`.
- Front-ring BCE weight `0.05`, radius 16 px.
- New complete-mask balanced BCE weight `0.10`, positive-weight cap 20.
- No global or far-only background BCE.
- Selection metric: event-macro growth IoU on DEV.

## Isolation and decision

The runner rejects roots containing `confirm`, `test` or `prospective`, checks
RCDA VAL source selection, and asserts WFIGS TEST is not loaded. Promotion
requires `+0.005` event-macro IoU over the residual decoder control (`0.131902`);
otherwise the candidate is rejected without replication or confirmation.

## Publication boundary

Only code, tests, protocol and sanitized aggregate DEV metrics may be published;
raw WFIGS geometries, tensors, tiles, checkpoints and per-pixel outputs remain
private.
