# WFIGS multitask transfer DEV protocol — 2026-08-20

This is a directional architecture-transfer experiment after the sealed
confirmation. It does not reopen or reinterpret confirmation or prospective
data.

## Frozen scope

- Use the expansion tuning dataset only: 184 TRAIN events and 42 DEV events.
- Initialize from the RCDA `resunet_multitask` front-ring checkpoint selected
  on RCDA VAL, then adapt only on WFIGS TRAIN and select epoch/threshold on
  WFIGS DEV.
- Decoder-only adaptation, seed `0`, batch size `4`, learning rate `1e-4`,
  weight decay `1e-4`, 18-epoch ceiling, patience `5`, augmentation enabled,
  and front-ring BCE weight `0.15`.
- Refuse dataset paths containing confirmation, test, or prospective markers.
- Do not publish raw tensors, geometries, predictions, checkpoints, or
  per-event rows.

## Interpretation

This is a one-seed DEV pilot. It may nominate a candidate for a future
multi-seed replication, but it cannot create a new confirmation claim. The
original confirmation gate remains **false**.

