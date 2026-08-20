# WFIGS ASPP-U-Net DEV result — 2026-08-20

## Scope and isolation

The ASPP-U-Net source was adapted using WFIGS expansion TRAIN (184 events) and
selected on DEV (42 events). The source was selected on RCDA VAL. Confirmation
and prospective TEST were not loaded or inspected.

## Result

| Recipe | DEV event-macro growth IoU | Threshold | Best epoch | Precision | Recall |
|---|---:|---:|---:|---:|---:|
| Residual hybrid decoder control, seed 47 | 0.131902 | 0.30 | 12 | 0.217028 | 0.307855 |
| ASPP-U-Net hybrid decoder, seed 0 | 0.122170 | 0.20 | 12 | 0.209034 | 0.300170 |
| Frozen residual three-seed ensemble | 0.136178 | 0.30 | — | 0.226176 | 0.306567 |

The ASPP candidate is `-0.009732` below the residual single-seed control and
`-0.014008` below the frozen ensemble. Its lower precision and recall confirm
that this RCDA source family does not transfer as well to the WFIGS domain
under the fixed decoder-only recipe.

## Decision

Reject the ASPP-U-Net candidate. Do not replicate, ensemble, or open
confirmation for it. The checkpoint and per-pixel outputs remain private and
are not included in this PR.

## Rights and provenance

Only aggregate metrics and methodology are published. WFIGS geometries,
tensors, tiles and model checkpoints are not redistributed.
