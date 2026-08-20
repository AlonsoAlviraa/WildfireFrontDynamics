# WFIGS negative-background BCE DEV result — 2026-08-20

## Scope

This report is limited to WFIGS expansion DEV (42 event-disjoint events). The
184-event TRAIN split was used for updates. Confirmation and prospective TEST
were not loaded, selected on, or inspected.

## Fixed candidate

The candidate used the RCDA-VAL-selected `resunet` hybrid source, seed 47,
decoder-only adaptation, 18 epochs maximum with patience 5, AdamW at `1e-4`,
augmentation, front-ring BCE weight `0.05`, and the preregistered
negative-background BCE weight `0.05`. The growth threshold was selected on DEV.

## Result

| Candidate | DEV event-macro growth IoU | Threshold | Best epoch | Precision | Recall |
|---|---:|---:|---:|---:|---:|
| Frozen hybrid control, seed 47 | 0.131902 | 0.30 | 12 | 0.217028 | 0.307855 |
| Negative-background BCE, seed 47 | 0.131685 | 0.30 | 12 | 0.218800 | 0.304634 |
| Frozen three-seed hybrid ensemble | 0.136178 | 0.30 | — | 0.226176 | 0.306567 |

The candidate delta is `-0.000217` versus the single-seed control and
`-0.004494` versus the frozen ensemble. It therefore fails the preregistered
`+0.005` promotion criterion. The modest precision increase does not offset
the recall loss or the lower event-macro IoU.

## Decision

Reject the negative-background BCE candidate. Do not replicate it, open
confirmation, or alter the frozen ensemble. The local checkpoint and raw
per-pixel outputs remain private and are not part of this PR.

## Provenance and rights

The source was selected on RCDA VAL; WFIGS selection was DEV-only and the run
asserted `wfigs_test_loaded=false`. WFIGS remains a public source used under its
noncommercial/internal training terms. This PR publishes only code, protocol
and aggregate metrics, not WFIGS geometries, tensors, tiles or checkpoints.
