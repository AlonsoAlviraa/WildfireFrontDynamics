# WFIGS negative-background BCE DEV protocol — 2026-08-20

## Purpose

The frozen three-seed hybrid ensemble still produces large false-positive
footprints on very small or zero-growth fires.  This DEV-only experiment adds
an explicit BCE penalty on observed non-growth pixels while keeping the RCDA
source, target definition, normalization, augmentation, optimizer and spatial
resolution fixed.

This is a preregistered diagnostic candidate, not a confirmation claim.

## Fixed recipe

- Source: RCDA `resunet` hybrid checkpoint selected on RCDA VAL, seed 47.
- WFIGS data: expansion TRAIN (184 events) for updates and expansion DEV (42
  events) for epoch/threshold selection.
- Target: hybrid extent + incremental growth; prediction remains the growth
  channel only.
- Trainable scope: decoder only; encoder/context remain frozen.
- Epochs: 18; patience: 5; batch size: 4.
- Optimizer: AdamW, learning rate `1e-4`, weight decay `1e-4`, gradient cap 5.
- Augmentation: enabled, using the existing fixed geometric/wind transform.
- Focal-Tversky: alpha `0.3`, beta `0.7`, gamma `0.75`.
- Front-ring BCE: weight `0.05`, radius 16 px.
- New negative-background BCE: weight `0.05`, applied to all pixels where the
  incremental-growth target is zero.
- Selection metric: event-macro growth IoU; threshold selected on DEV only.

## Isolation and stopping rules

The runner rejects dataset roots whose names contain `confirm`, `test`, or
`prospective`, and only loads `train.json` and `validation.json`.  It asserts
that the source checkpoint was selected on RCDA VAL and that no WFIGS TEST
artifact is loaded.  No hyperparameter changes are allowed after seeing DEV
results.  If event-macro IoU does not exceed the frozen single-seed hybrid
control (`0.131902`) by at least `0.005`, this candidate is rejected and is not
replicated or promoted to confirmation.

## Publication boundary

Only this protocol, code, tests and an aggregate sanitized DEV result may be
committed.  WFIGS geometries, tensors, tiles, checkpoints and per-pixel
predictions remain local and are not redistributed.
