# WFIGS scratch-training DEV protocol — 2026-08-20

## Question

All previous candidates transferred an RCDA source. This control tests whether
the WFIGS domain is better learned directly from its 184 TRAIN events, with no
RCDA feature representation in the weights. It is a necessary baseline before
claiming that transfer learning is optimal.

## Fixed recipe

- Architecture: residual U-Net, base channels 32, random initialization.
- Seed: 47; initialization is generated inside the runner and is not imported
  from any external checkpoint.
- Data: WFIGS expansion TRAIN (184 events) for updates; DEV (42 events) for
  epoch/threshold selection.
- RCDA TRAIN normalization for the physical-channel input contract.
- All parameters trainable; hybrid target; augmentation enabled.
- AdamW `lr=1e-4`, weight decay `1e-4`, batch 4, maximum 24 epochs, patience 6,
  gradient cap 5.
- Focal-Tversky alpha `0.3`, beta `0.7`, gamma `0.75`; front-ring BCE `0.05`,
  radius 16 px.
- Selection metric: event-macro growth IoU on DEV.

## Isolation and decision

The runner refuses roots containing `confirm`, `test` or `prospective`, creates
its random source locally, loads only TRAIN/DEV manifests, and asserts WFIGS
TEST is not loaded. Promotion requires `+0.005` event-macro IoU over the
frozen decoder control (`0.131902`); otherwise it is rejected without
replication or confirmation.

## Publication boundary

Only code, protocol, tests and sanitized aggregate DEV metrics are publishable.
Raw WFIGS geometries, tensors, tiles, checkpoints and per-pixel outputs remain
private.
