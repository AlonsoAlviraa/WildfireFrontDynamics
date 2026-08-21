# WFIGS corrected geometry augmentation three-seed result — 2026-08-21

## Scope

The physically corrected combined geometry + tile-EO recipe was adapted from
RCDA VAL-selected residual checkpoints for seeds 11, 29 and 47. WFIGS expansion
TRAIN (184 events) was used for updates and DEV (42 events) for epoch/threshold
selection. Confirmation and prospective TEST were not loaded or inspected.

## Result

| Recipe | DEV event-macro growth IoU | Pooled IoU | Threshold | Precision | Recall |
|---|---:|---:|---:|---:|---:|
| Frozen three-seed hybrid ensemble | 0.136178 | 0.149627 | 0.30 | 0.226176 | 0.306567 |
| Corrected combined-feature ensemble | 0.138085 | 0.151251 | 0.35 | 0.253519 | 0.272698 |

Per-seed event-macro scores were `0.133352` (seed 11), `0.128868` (seed 29),
and `0.138828` (seed 47). The equal-weight ensemble gain is only `+0.001907`
over the frozen reference, below the preregistered `+0.005` stability gate.
Precision and pooled IoU rise, but recall falls and the event-level improvement
is not robust across initializations.

## Decision

Reject promotion and close this feature family for the current paper recipe.
Do not open confirmation or inspect TEST. The corrected augmentation remains in
the codebase as the physically valid implementation, while the uncorrected
single-seed result is explicitly non-promotable.

## Reproducibility and rights

The report records `source_seeds=[11,29,47]`,
`include_geometry_features=true`, `include_tile_standardized_features=true`,
`trainable_scope=decoder_plus_input`, `wfigs_test_loaded=false`, and
`test_used_for_selection=false`. Only sanitized aggregate metrics are
published; WFIGS raw geometries, tensors, tiles and checkpoints remain private
and are not redistributed.
