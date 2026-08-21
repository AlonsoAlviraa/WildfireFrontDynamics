# WFIGS larger TRAIN/DEV campaign protocol — 2026-08-21

## Motivation

The historical WFIGS harvest contains 15,661 events and 35,562 observations,
but the current tensor cohort has only 184 TRAIN and 42 DEV events. This
campaign materializes up to 50 input-eligible events per GACC region for TRAIN
and DEV, using the existing temporal-pair and enrichment contracts, to reduce
seed variance and increase power for the next model comparison.

## Fixed safeguards

- Splits: only existing WFIGS `train` and `validation` pair assignments.
- Selection: one pair per event, input-availability/weather/EO eligibility;
  no target-derived ranking.
- Resolution: 256×256 at 60 m; minimum valid fraction 0.70.
- Normalization: recomputed from TRAIN tensors only.
- The runner fails if a TEST manifest is materialized; confirmation/prospective
  data are not read.
- WFIGS use remains internal/noncommercial; raw/derived tensors and checkpoints
  are not published.

## Intended ML use

After the campaign passes its audit, train/validation-only experiments may be
run with the corrected geometry augmentation and fixed-source controls. Any
promotion still requires event-level replication and the +0.005 gate; this
campaign does not authorize opening the sealed TEST cohort.
