# WFIGS front-geometry three-seed ensemble DEV result — 2026-08-21

## Scope

Seeds 11, 29 and 47 were adapted independently from the RCDA VAL-selected
residual hybrid checkpoints. WFIGS expansion TRAIN (184 events) was used for
updates and DEV (42 events) for epoch/threshold selection. The three adapted
models were then averaged by probability on DEV. Confirmation and prospective
TEST were not loaded or inspected.

## Result

| Recipe | DEV event-macro growth IoU | Pooled IoU | Threshold | Precision | Recall |
|---|---:|---:|---:|---:|---:|
| Frozen three-seed hybrid ensemble | 0.136178 | 0.149627 | 0.30 | 0.226176 | 0.306567 |
| Front-geometry adapted three-seed ensemble | 0.134268 | 0.150103 | 0.35 | 0.258579 | 0.263518 |

The adapted ensemble is `-0.001910` below the frozen ensemble on the primary
event-macro metric and therefore fails the preregistered `+0.005` promotion
gate. Pooled IoU and precision increase slightly, but recall drops by `0.043049`
and the event-level score is lower. The single-seed near miss was therefore not
stable across the three-seed paper recipe.

## Decision

Reject promotion and do not replicate or open confirmation. Retain the frozen
three-seed ensemble as the current DEV reference. This result supplies a useful
stability check: explicit front geometry changes the precision/recall operating
point but does not improve event-macro performance under adaptation.

## Reproducibility and rights

The report records `source_seeds=[11,29,47]`,
`include_geometry_features=true`, `trainable_scope=decoder_plus_input`,
`wfigs_test_loaded=false`, and `test_used_for_selection=false`. Only sanitized
aggregate metrics are published; WFIGS raw geometries, tensors, tiles and
checkpoints remain private and are not redistributed.
