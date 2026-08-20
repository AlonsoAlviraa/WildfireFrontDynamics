# WFIGS learned-valid-mask DEV result — 2026-08-20

## Scope

The run used the WFIGS expansion TRAIN split (184 events) for updates and the
sealed DEV/validation split (42 events) for epoch and threshold selection. The
explicit WFIGS `valid_data` mask was appended as a seventeenth input feature;
the RCDA residual U-Net source weights were retained and only the decoder plus
the two residual input projections were trainable. Confirmation and
prospective TEST were not loaded or inspected.

## Result

| Recipe | DEV event-macro growth IoU | Pooled IoU | Threshold | Best epoch | Precision | Recall |
|---|---:|---:|---:|---:|---:|---:|
| RCDA single-seed control, seed 47 | 0.131902 | — | 0.30 | 12 | 0.217028 | 0.307855 |
| Learned `valid_data` feature, seed 47 | 0.134848 | 0.149817 | 0.15 | 8 | 0.223636 | 0.312181 |
| Frozen three-seed hybrid ensemble | 0.136178 | 0.149627 | 0.30 | — | 0.226176 | 0.306567 |

The learned-mask candidate improves the single-seed control by only
`+0.002946`, below the preregistered `+0.005` promotion criterion. It also
remains below the frozen three-seed ensemble on event-macro IoU (`-0.001330`)
and changes the operating point to a low threshold, so it is not a robust
replacement for the paper recipe.

## Decision

Reject promotion of the learned-valid-mask candidate. Keep the current frozen
RCDA normalization and ensemble as the DEV reference, and do not replicate or
open confirmation on the basis of this run. The experiment is useful as a
negative representation result: exposing WFIGS validity to the decoder did not
remove the domain/label mismatch under the fixed low-data adaptation budget.

## Reproducibility and rights

The source checkpoint was selected on RCDA VAL. The run recorded
`include_valid_mask=true`, `trainable_scope=decoder_plus_input`,
`wfigs_test_loaded=false`, and `test_used_for_selection=false`. Only sanitized
aggregate metrics are published; WFIGS raw geometries, tensors, tiles and
checkpoints remain private and are not redistributed.
