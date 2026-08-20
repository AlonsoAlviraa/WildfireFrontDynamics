# WFIGS balanced-growth BCE DEV result — 2026-08-20

## Scope and isolation

The candidate used WFIGS expansion TRAIN (184 events) for updates and DEV (42
events) for epoch/threshold selection. It started from the RCDA-VAL-selected
residual hybrid seed 47 and used decoder-only adaptation. Confirmation and
prospective TEST were not loaded or inspected.

## Result

| Recipe | DEV event-macro growth IoU | Threshold | Best epoch | Precision | Recall |
|---|---:|---:|---:|---:|---:|
| Frozen residual decoder control, seed 47 | 0.131902 | 0.30 | 12 | 0.217028 | 0.307855 |
| Balanced-growth BCE weight `0.10` | 0.129834 | 0.50 | 18 | 0.228356 | 0.283420 |
| Frozen residual three-seed ensemble | 0.136178 | 0.30 | — | 0.226176 | 0.306567 |

The candidate is `-0.002068` below the single-seed control and `-0.006345`
below the ensemble. The precision increase is accompanied by lower recall and
lower event-macro IoU, so the preregistered `+0.005` promotion criterion fails.

## Decision

Reject balanced-growth BCE. Do not replicate or open confirmation; retain the
Focal-Tversky/front-ring residual control. The checkpoint and per-pixel output
remain private and are not part of this PR.

## Rights

Only code, protocol and aggregate metrics are published. WFIGS geometries,
tensors, tiles and checkpoints are not redistributed.
