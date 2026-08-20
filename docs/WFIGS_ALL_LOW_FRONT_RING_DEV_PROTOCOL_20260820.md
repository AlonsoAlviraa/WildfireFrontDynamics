# WFIGS all-low-rate front-ring DEV protocol — 2026-08-20

## Question

Decoder-only adaptation is the current control. A prior all-parameter pilot
used `3e-5` without the front-ring objective and underperformed. This
preregistered ablation tests gentle all-parameter adaptation at `1e-5` while
retaining the front-ring BCE that was successful for decoder-only adaptation.

## Fixed recipe

- Source: RCDA-VAL-selected `resunet` hybrid checkpoint, seed 47.
- Data: WFIGS expansion TRAIN (184 events), selection on DEV (42 events).
- RCDA TRAIN normalization; hybrid target; augmentation enabled.
- Trainable scope: all parameters.
- AdamW `lr=1e-5`, weight decay `1e-4`, batch 4, max 18 epochs, patience 5,
  gradient cap 5.
- Focal-Tversky alpha `0.3`, beta `0.7`, gamma `0.75`.
- Front-ring BCE weight `0.05`, radius 16 px; no other auxiliary BCE.
- Selection metric: event-macro growth IoU on DEV.

## Isolation and decision

The runner rejects roots containing `confirm`, `test` or `prospective`, checks
RCDA VAL source selection, and asserts WFIGS TEST is not loaded. Promotion
requires `+0.005` event-macro IoU over the decoder-only control (`0.131902`);
otherwise the candidate is rejected without replication or confirmation.

## Publication boundary

Only code, protocol, tests and aggregate DEV metrics are publishable. Raw
WFIGS geometries, tensors, tiles, checkpoints and per-pixel outputs remain
private.
