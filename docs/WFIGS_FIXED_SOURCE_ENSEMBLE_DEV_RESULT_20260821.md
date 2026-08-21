# WFIGS fixed RCDA source / three adaptation seeds DEV result — 2026-08-21

## Scope

The RCDA VAL-selected seed-47 checkpoint was held fixed while WFIGS adaptation
used RNG seeds 11, 29 and 47. The corrected combined geometry + tile-EO recipe
was trained on WFIGS expansion TRAIN (184 events), with selection on DEV (42
events). Confirmation and prospective TEST were not loaded or inspected.

## Result

| Recipe | DEV event-macro growth IoU | Pooled IoU | Threshold | Precision | Recall |
|---|---:|---:|---:|---:|---:|
| Frozen three-seed hybrid ensemble | 0.136178 | 0.149627 | 0.30 | 0.226176 | 0.306567 |
| Fixed-source adaptation ensemble | 0.140044 | 0.156678 | 0.25 | 0.240205 | 0.310616 |
| Fixed-weight grid best (equal weights, cap 12 px) | 0.140719 | 0.152906 | 0.25 | 0.238705 | 0.298445 |

Individual adaptation-seed event-macro scores were `0.140309`, `0.138084` and
`0.138828`; fixing the source seed substantially reduces variance. Nevertheless,
the equal ensemble gain is `+0.003866` and the fixed-grid sensitivity gain is
`+0.004541`, both below the preregistered `+0.005` promotion gate over the
frozen ensemble.

## Decision

Reject promotion for confirmation. Keep the fixed-source recipe as a useful
DEV research result and retain the frozen ensemble as the paper reference. Do
not inspect TEST; the remaining gap is small but must not be erased by further
DEV-only calibration.

## Reproducibility and rights

The report records fixed RCDA source seed 47, adaptation seeds `[11,29,47]`,
the corrected geometry augmentation, `include_geometry_features=true`,
`include_tile_standardized_features=true`, `wfigs_test_loaded=false`, and
`test_used_for_selection=false`. Only sanitized aggregate metrics are
published; WFIGS raw geometries, tensors, tiles and checkpoints remain private
and are not redistributed.
