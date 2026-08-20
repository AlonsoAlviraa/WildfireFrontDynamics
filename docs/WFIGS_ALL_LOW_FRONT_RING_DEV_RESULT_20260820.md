# WFIGS all-low-rate front-ring DEV result — 2026-08-20

## Scope and isolation

The candidate updated all parameters on WFIGS expansion TRAIN (184 events) and
selected epoch/threshold on DEV (42 events). It used the RCDA-VAL-selected
residual hybrid source with RCDA TRAIN normalization. Confirmation and
prospective TEST were not loaded or inspected.

## Result

| Recipe | DEV event-macro growth IoU | Threshold | Best epoch | Precision | Recall |
|---|---:|---:|---:|---:|---:|
| Decoder-only control, seed 47 | 0.131902 | 0.30 | 12 | 0.217028 | 0.307855 |
| All-parameter `lr=1e-5` + front-ring BCE | 0.123372 | 0.30 | 18 | 0.237014 | 0.248286 |
| Frozen residual three-seed ensemble | 0.136178 | 0.30 | — | 0.226176 | 0.306567 |

The candidate is `-0.008530` below the decoder-only control and `-0.012806`
below the frozen ensemble. Its precision increase comes with a substantial
recall loss and fails the preregistered `+0.005` promotion criterion.

## Decision

Reject all-parameter low-rate adaptation. Keep the decoder-only residual
recipe and equal-weight ensemble frozen; do not replicate or open confirmation
for this candidate. Checkpoints and per-pixel outputs remain local.

## Rights and provenance

Only protocol and aggregate metrics are published. WFIGS raw geometries,
tensors, tiles and checkpoints are not redistributed.
