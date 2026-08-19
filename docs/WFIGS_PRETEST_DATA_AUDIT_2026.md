# WFIGS pre-TEST data audit

Frozen on 2026-08-19 before materializing or evaluating the physical WFIGS
TEST cohort.

## Harvest and causal enrichment

- Historical geometry pairs audited: 3,439.
- Sentinel-2/Landsat candidates created no later than `t0`: 3,439.
- HRRR pairs valid in both time and CONUS space: 2,530.
- Pairs outside the HRRR CONUS domain: 673; these are not silently accepted.
- Weather fields come from a model run available before `t0`; imagery scene
  creation time must also be no later than `t0`.

## Physical TRAIN and VALIDATION tensors

| Split | Selected | Accepted | Rejected | Events | 6–12 h | 12–24 h | 24–48 h |
|---|---:|---:|---:|---:|---:|---:|---:|
| TRAIN | 69 | 61 | 8 | 61 | 6 | 26 | 29 |
| VALIDATION | 21 | 19 | 2 | 19 | 2 | 8 | 9 |

TRAIN rejection reasons were three insufficient-clear-pixel scenes and five
truncated `t1` geometries. Both VALIDATION rejections were truncated `t1`
geometries. Every accepted sample is one distinct fire event on a fixed
256×256 grid at 60 m and contains 13 causal input channels.

Mean valid EO coverage is 0.964 in both splits. TRAIN contains 40,808 growth
pixels over 236,642 target-extent pixels; VALIDATION contains 24,489 over
63,592. Ten TRAIN samples and one VALIDATION sample have zero new-growth pixels.
The higher VALIDATION growth prevalence is retained as cohort heterogeneity; no
balancing decision uses TEST.

## Independent tensor audit

`scripts/audit_wfigs_tensor_dataset.py` reloaded all 80 files and checked:

- shapes, finite values and valid horizons;
- binary previous-fire, valid-data and target masks;
- exact `target_growth = target_extent AND NOT previous_fire`;
- unique `pair_id` values and event-disjoint splits;
- exact recomputation of every normalization min/max from TRAIN only.

Result: **PASS, 80/80 samples audited, 0 issues**. The machine-readable source
is `outputs/ml_eval/wfigs_tensor_dataset_20260819/DATASET_AUDIT.json`.

## TEST isolation and external baseline

At freeze time there was no `test.json`, no physical TEST tensor and no WFIGS
model evaluation. The zero-shot recipe uses RCDA architecture, weights and
thresholds selected only on RCDA VALIDATION. The adapted recipe may use WFIGS
TRAIN and select epoch/threshold only on WFIGS VALIDATION. Physical WFIGS TEST
is materialized only after those recipes are frozen and is evaluated once.

The morphology comparator uses a 250 m dilation radius selected on WFIGS
VALIDATION. Evaluation now aborts unless the comparator contains exactly one
usable record for every TEST `pair_id`; missing coverage cannot become an
artificial zero-IoU baseline.

## Rights boundary

The NIFC/WFIGS ArcGIS item is publicly accessible. The project policy permits
internal non-commercial research and training, but no affirmative reuse licence
was found that authorizes redistribution of raw geometries, derived tensors or
checkpoints. Aggregate metrics, methods, code and plots may be published,
subject to final rights review. Public access alone is not treated as commercial
or redistribution permission.
