# WFIGS multitask transfer DEV result — 2026-08-20

This is a sanitized, directional one-seed DEV result. It is not a new
external or confirmatory claim.

## Frozen comparison

- Expansion tuning cohort only: 184 TRAIN events and 42 DEV events.
- RCDA `resunet_multitask` source selected on RCDA VAL; WFIGS adaptation used
  decoder-only training, seed `0`, augmentation, front-ring BCE `0.15`, and
  the pre-registered 18-epoch budget.
- Confirmation and prospective manifests were not loaded.

## Result

| Candidate | DEV event-macro IoU | Threshold | Best epoch |
| --- | ---: | ---: | ---: |
| Hybrid decoder control (seed 47) | 0.131902 | 0.30 | 12 |
| Frozen three-seed hybrid ensemble | 0.136178 | 0.30 | — |
| Multitask transfer (seed 0) | 0.112394 | 0.60 | 11 |

The multitask transfer is `-0.019508` IoU below the hybrid control and
`-0.023785` below the frozen ensemble on DEV. It is rejected as the next
candidate; no multi-seed replication is warranted from this pilot.

The original confirmation gate remains **false**. Raw geometries, tensors,
predictions, checkpoints, and per-event rows remain local and are not included
in this PR.

