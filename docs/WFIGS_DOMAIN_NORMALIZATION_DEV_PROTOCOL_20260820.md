# WFIGS converted-normalization DEV protocol — 2026-08-20

## Question

The current recipe applies RCDA TRAIN min/max statistics to converted WFIGS
physical channels. This candidate tests the alternative normalization already
fit on WFIGS expansion TRAIN only, while retaining the source checkpoint and
decoder recipe unchanged. It is a domain-shift ablation, not a new source of
labels.

## Fixed recipe

- Source: RCDA-VAL-selected `resunet` hybrid checkpoint, seed 47.
- Normalization: `normalization_wfigs_converted_train_only.json`, fitted only
  on WFIGS expansion TRAIN.
- Data: WFIGS expansion TRAIN (184 events) for updates; DEV (42 events) for
  epoch and threshold selection.
- Decoder-only adaptation, augmentation enabled, batch 4, AdamW `1e-4`, weight
  decay `1e-4`, max 18 epochs, patience 5, gradient cap 5.
- Hybrid target; focal-Tversky alpha `0.3`, beta `0.7`, gamma `0.75`.
- Front-ring BCE weight `0.05`, radius 16 px; no extra background BCE.
- Selection: DEV event-macro growth IoU.

## Isolation and decision

The runner requires the exact TRAIN-fitted converted-normalization filename,
rejects dataset roots containing `confirm`, `test` or `prospective`, validates
RCDA VAL source selection, and asserts WFIGS TEST is not loaded. The candidate
is promoted only if it exceeds the RCDA-normalized control (`0.131902`) by at
least `0.005`; otherwise it is rejected without replication or confirmation.

## Publication boundary

Only code, protocol, tests and aggregate DEV metrics may be committed. Raw
WFIGS geometries, tensors, tiles, checkpoints and per-pixel predictions remain
local and are not redistributed.
