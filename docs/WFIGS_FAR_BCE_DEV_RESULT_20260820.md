# WFIGS far-background BCE DEV result — 2026-08-20

## Scope

This is a DEV-only result on the WFIGS expansion split: 184 TRAIN events for
updates and 42 DEV events for epoch/threshold selection. Confirmation and
prospective TEST were not loaded or inspected.

## Candidate and controls

The candidate used the RCDA-VAL-selected hybrid `resunet` source (seed 47),
decoder-only adaptation, augmentation, 18-epoch maximum with patience 5,
front-ring BCE weight `0.05`, and far-background BCE weight `0.05` on target-zero
pixels at least 12 px from the t0 front. The threshold was selected on DEV.

| Recipe | DEV event-macro growth IoU | Threshold | Best epoch | Precision | Recall |
|---|---:|---:|---:|---:|---:|
| Frozen hybrid control, seed 47 | 0.131902 | 0.30 | 12 | 0.217028 | 0.307855 |
| Far-background BCE, seed 47 | 0.131897 | 0.30 | 12 | 0.217157 | 0.307464 |
| Frozen three-seed hybrid ensemble | 0.136178 | 0.30 | — | 0.226176 | 0.306567 |

The candidate delta is `-0.000005` versus the single-seed control and
`-0.004281` versus the frozen ensemble. The tiny precision increase is offset
by a recall decrease and no event-macro gain.

## Decision

Reject the far-background BCE candidate. Do not replicate or promote it to
confirmation. The local checkpoint and per-pixel outputs remain private and
are not included in this PR.

## Provenance and rights

The source checkpoint was selected on RCDA VAL; WFIGS selection was DEV-only,
and the run asserted `wfigs_test_loaded=false`. WFIGS is used as a public source
under its noncommercial/internal training terms. This PR contains only code,
protocol and aggregate metrics, not raw WFIGS geometries, tensors, tiles or
checkpoints.
