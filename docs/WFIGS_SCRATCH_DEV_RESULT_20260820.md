# WFIGS scratch-training DEV result — 2026-08-20

## Scope and isolation

The residual U-Net was randomly initialized with seed 47 and trained on WFIGS
expansion TRAIN (184 events), with epoch/threshold selection on DEV (42
events). Confirmation and prospective TEST were not loaded or inspected.

## Result

| Recipe | DEV event-macro growth IoU | Threshold | Best epoch | Precision | Recall |
|---|---:|---:|---:|---:|---:|
| RCDA residual transfer, decoder-only control | 0.131902 | 0.30 | 12 | 0.217028 | 0.307855 |
| WFIGS scratch residual U-Net, all parameters | 0.129120 | 0.40 | 24 | 0.215094 | 0.265312 |
| Frozen residual three-seed transfer ensemble | 0.136178 | 0.30 | — | 0.226176 | 0.306567 |

Scratch training is `-0.002782` below the decoder-only transfer control and
`-0.007058` below the ensemble. The result indicates that the frozen RCDA
representation provides useful initialization/domain structure, but the current
WFIGS sample size and objective remain insufficient for a strong model.

## Decision

Reject scratch training as the production candidate. Do not replicate or open
confirmation. Preserve the transfer ensemble as the control while pursuing a
new temporal/geometry representation.

## Rights

Only code, protocol and aggregate metrics are published. WFIGS geometries,
tensors, tiles, checkpoints and per-pixel predictions remain private.
