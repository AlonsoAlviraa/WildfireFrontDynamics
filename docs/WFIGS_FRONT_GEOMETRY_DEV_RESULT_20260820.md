# WFIGS explicit-front-geometry DEV result — 2026-08-20

## Scope

The run used WFIGS expansion TRAIN (184 events) for updates and DEV (42
events) for epoch and threshold selection. Three target-independent channels
were appended to the 16-channel RCDA bridge: signed distance to the previous
front and its normalized horizontal/vertical derivatives. Confirmation and
prospective TEST were not loaded or inspected.

## Result

| Recipe | DEV event-macro growth IoU | Pooled IoU | Threshold | Best epoch | Precision | Recall |
|---|---:|---:|---:|---:|---:|---:|
| RCDA single-seed control, seed 47 | 0.131902 | — | 0.30 | 12 | 0.217028 | 0.307855 |
| Explicit front geometry, seed 47 | 0.136740 | 0.148653 | 0.20 | 4 | 0.255060 | 0.262712 |
| Frozen three-seed hybrid ensemble | 0.136178 | 0.149627 | 0.30 | — | 0.226176 | 0.306567 |

The geometry candidate improves the single-seed control by `+0.004838`, but
misses the preregistered `+0.005` promotion criterion by `0.000162`. Its
precision is materially higher, while recall falls by `0.045143`; pooled IoU is
also below the frozen ensemble. This is not sufficient evidence for a robust
paper-model replacement.

## Decision

Reject promotion and do not replicate or open confirmation. Retain the frozen
three-seed ensemble as the DEV reference. The result is still useful as a
near-miss representation ablation: front-relative geometry improves the
operating point but does not clear the event-level promotion gate under the
fixed low-data adaptation budget.

## Reproducibility and rights

The source checkpoint was selected on RCDA VAL. The run recorded
`include_geometry_features=true`, `trainable_scope=decoder_plus_input`,
`wfigs_test_loaded=false`, and `test_used_for_selection=false`. Only sanitized
aggregate metrics are published; WFIGS raw geometries, tensors, tiles and
checkpoints remain private and are not redistributed.
