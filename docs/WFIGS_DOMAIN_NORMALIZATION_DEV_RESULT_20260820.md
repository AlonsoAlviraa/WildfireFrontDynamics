# WFIGS converted-normalization DEV result — 2026-08-20

## Scope

The run used WFIGS expansion TRAIN (184 events) for updates and DEV (42 events)
for epoch/threshold selection. The converted normalization was fitted on TRAIN
only. Confirmation and prospective TEST were not loaded or inspected.

## Result

| Recipe | DEV event-macro growth IoU | Threshold | Best epoch | Precision | Recall |
|---|---:|---:|---:|---:|---:|
| RCDA TRAIN normalization control, seed 47 | 0.131902 | 0.30 | 12 | 0.217028 | 0.307855 |
| WFIGS converted TRAIN normalization, seed 47 | 0.130501 | 0.35 | 12 | 0.224243 | 0.280337 |
| Frozen three-seed hybrid ensemble | 0.136178 | 0.30 | — | 0.226176 | 0.306567 |

The domain-normalized candidate is `-0.001401` below the single-seed control
and `-0.005678` below the frozen ensemble. Its precision increase is not enough
to compensate for the recall loss, and it fails the preregistered `+0.005`
promotion criterion.

## Decision

Reject the WFIGS converted-normalization candidate. Keep RCDA TRAIN
normalization frozen for the paper recipe; do not replicate or open
confirmation. The local checkpoint and tensors remain private and are not part
of this PR.

## Provenance and rights

The source checkpoint was selected on RCDA VAL, the run asserted
`wfigs_test_loaded=false`, and only sanitized aggregate metrics are published.
WFIGS raw geometries, tensors, tiles and checkpoints are not redistributed.
