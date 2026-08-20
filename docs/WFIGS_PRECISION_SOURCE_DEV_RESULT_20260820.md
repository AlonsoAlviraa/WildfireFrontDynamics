# WFIGS precision-tuned source DEV result — 2026-08-20

## Scope and isolation

The precision-oriented RCDA residual source was adapted on WFIGS expansion
TRAIN (184 events) and selected on DEV (42 events). The source itself was
selected on RCDA VAL. Confirmation and prospective TEST were not loaded or
inspected.

## Result

| Recipe | DEV event-macro growth IoU | Threshold | Best epoch | Precision | Recall |
|---|---:|---:|---:|---:|---:|
| Recall-oriented residual decoder control, seed 47 | 0.131902 | 0.30 | 12 | 0.217028 | 0.307855 |
| Precision-oriented RCDA source, seed 0 | 0.111499 | 0.10 | 18 | 0.210362 | 0.257742 |
| Frozen residual three-seed ensemble | 0.136178 | 0.30 | — | 0.226176 | 0.306567 |

The candidate is `-0.020403` below the residual decoder control and `-0.024680`
below the ensemble. The source-level precision orientation did not transfer to
WFIGS under adaptation and actually reduced both precision and recall at its
DEV-selected threshold.

## Decision

Reject the precision-oriented source. Do not replicate, ensemble, or open
confirmation. Keep the residual hybrid decoder/ensemble frozen as the current
control. Local checkpoints and per-pixel outputs are not included in this PR.

## Rights and provenance

Only aggregate metrics and methodology are published. WFIGS geometries,
tensors, tiles and checkpoints remain private.
