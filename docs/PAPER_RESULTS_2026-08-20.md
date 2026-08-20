# RCDA/WFIGS paper results — 2026-08-20

## Evidence status

This document reports aggregate evidence only. RCDA model selection and the
new fixed-seed replication campaign use VALIDATION exclusively. The historical
RCDA TEST result belongs to the previously frozen recipe; the later front-ring
candidate was not evaluated on that already observed TEST. The prospective
WFIGS holdout was opened once after the WFIGS source recipe was frozen.

## RCDA fixed-seed validation replications

The multitask front-ring recipe was rerun with preregistered seeds 11, 29 and
47 on the same 106-fire validation cohort. Exact staged-runner hashes were
registered before results arrived.

| Seed | Best epoch | Threshold | Event-macro growth IoU |
|---:|---:|---:|---:|
| 11 | 30 | 0.60 | 0.23003 |
| 29 | 22 | 0.80 | 0.22803 |
| 47 | 23 | 0.65 | 0.23961 |

The across-seed mean is **0.23256**, sample standard deviation **0.00619**, and
event-bootstrap 95% interval **[0.20893, 0.25741]**. The equal-weight
probability ensemble reaches **0.25369** at threshold 0.60. Its paired gain
over the strongest individual seed is **+0.01408**, with 95% interval
**[+0.00403, +0.02422]**, and it improves 68.9% of validation fires.

These are strong replicated VALIDATION results, not new TEST evidence.

## Historical sealed RCDA TEST

The recipe frozen before the historical RCDA TEST remains the only valid
result on that split. Across 184 fires, the primary three-seed mean reaches
0.18040 event-macro growth IoU and the preregistered probability ensemble
reaches 0.18693. The ensemble exceeds the strongest reproduced learned
baseline by +0.02362, with paired 95% interval [+0.01021, +0.03744]. The later
front-ring ensemble was deliberately not tested on this already observed
split.

## WFIGS TRAIN/VALIDATION source selection

The expanded tensor cohort contains 87 TRAIN and 27 VALIDATION fires. Its
independent audit reports 114/114 valid tensors, zero issues, disjoint events,
unique pair identifiers and normalization recomputed from TRAIN only.

| Frozen candidate | Members | WFIGS VAL event-macro IoU |
|---|---:|---:|
| Historical RCDA source | 3 | **0.14373** |
| Cross-source exploratory ensemble | 6 | 0.13561 |
| Front-ring replicated source | 3 | 0.12353 |

The historical source was frozen as winner before prospective TEST. Its paired
advantage over the cross-source candidate is +0.00812, with 95% interval
[-0.00586, +0.02654]. The source-selection comparison is therefore not
statistically conclusive, but the deterministic VALIDATION rule selects the
historical source.

## One-time prospective WFIGS TEST

The preregistration selected 16 fires; 10 could be physically materialized.
Before opening, event and pair-set hashes matched the preregistration exactly,
the adaptation summary hash was fixed, and no prior prospective result or TEST
tensor dataset existed. The final 124-tensor dataset contains 87 TRAIN, 27
VALIDATION and 10 TEST fires. A post-build audit reports zero issues and no
event overlap.

| Prospective setting | Fires | Event-macro growth IoU | 95% interval |
|---|---:|---:|---:|
| Adapted seed mean | 10 | 0.07631 | [0.03741, 0.12021] |
| Adapted probability ensemble | 10 | **0.08737** | [0.04507, 0.13159] |
| Geometry baseline | 10 | **0.13821** | — |

The adapted ensemble minus geometry baseline is **−0.05084**, with paired 95%
interval **[−0.12832, +0.01089]**. It improves 50% of fires, but the external
transfer gate is false. This experiment does not support a claim of external
superiority or operational generalization.

## Interpretation

The central scientific result is a contrast:

1. front-focused multitask training plus fixed-seed probability averaging
   yields a replicated and statistically positive improvement on RCDA
   VALIDATION;
2. the same front-ring source does not improve WFIGS VALIDATION transfer;
3. the best pre-frozen WFIGS-adapted model fails to beat a simple geometry
   baseline on the small prospective cohort.

This supports a paper about reproducible model selection, temporal/geographic
domain shift and the danger of treating within-dataset gains as operational
generalization. It does not support a deployment-performance claim. Further
model development must use new TRAIN/VALIDATION data or a newly preregistered
future cohort; the ten opened prospective fires must not be reused for tuning.

## Aggregate evidence artifacts

- `outputs/ml_eval/rcda_front_ring_val_replications_20260820/RCDA_VAL_REPLICATION_SUMMARY.json`
- `outputs/ml_eval/rcda_front_ring_val_replications_20260820/RCDA_VAL_ENSEMBLES.json`
- `outputs/ml_eval/wfigs_source_selection_20260820/FROZEN_WFIGS_SOURCE.json`
- `outputs/ml_eval/wfigs_prospective_final_20260820/PROSPECTIVE_OPEN_ONCE.json`
- `outputs/ml_eval/wfigs_prospective_final_20260820/WFIGS_PROSPECTIVE_TEST_EVAL.json`
- `outputs/ml_eval/wfigs_tensor_dataset_prospective_20260820/DATASET_AUDIT.json`

WFIGS records, event identifiers, geometries, tensors and derived checkpoints
remain internal under the project's research-rights policy and are not part of
the public repository.
