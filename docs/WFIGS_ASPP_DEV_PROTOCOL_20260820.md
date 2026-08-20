# WFIGS ASPP-U-Net DEV protocol — 2026-08-20

## Question

The current paper control uses a residual U-Net source. This candidate tests a
different RCDA-VAL-selected encoder/context family with atrous spatial pyramid
pooling (ASPP), keeping the WFIGS adaptation and selection contract unchanged.

## Fixed recipe

- Source: RCDA `aspp_unet` hybrid checkpoint selected on RCDA VAL, seed 0.
- Data: WFIGS expansion TRAIN (184 events) for updates and DEV (42 events) for
  epoch/threshold selection.
- Normalization: frozen RCDA TRAIN min/max statistics.
- Target: hybrid extent + incremental growth; growth channel evaluated.
- Trainable scope: decoder only; ASPP encoder/context frozen.
- Epochs: 18 maximum, patience 5, batch size 4, AdamW `lr=1e-4`, weight decay
  `1e-4`, gradient cap 5.
- Augmentation: enabled; front-ring BCE weight `0.05`, radius 16 px.
- Focal-Tversky alpha `0.3`, beta `0.7`, gamma `0.75`.
- Selection metric: event-macro growth IoU on DEV only.

## Isolation and decision

The runner rejects roots containing `confirm`, `test` or `prospective`, checks
that the source was selected on RCDA VAL, and asserts WFIGS TEST is not loaded.
Promotion requires at least `+0.005` event-macro IoU over the frozen
single-seed residual control (`0.131902`); otherwise the candidate is rejected
without replication or confirmation evaluation.

## Publication boundary

Only code, tests, protocol and sanitized aggregate DEV metrics may be
published. WFIGS geometries, tensors, tiles, checkpoints and per-pixel outputs
remain local and are not redistributed.
