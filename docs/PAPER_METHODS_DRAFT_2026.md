# Wildfire front growth forecasting with event-disjoint validation

> Draft de métodos y protocolo. Las celdas `PENDING_ARTIFACT` se rellenan solo
> desde artefactos generados por los scripts citados; no contienen resultados
> inferidos ni copiados manualmente.

## Research question

We test whether explicit front-distance fields, multiscale spatial context and
weather-conditioned feature modulation improve next-perimeter growth prediction
over morphological and learned U-Net baselines while preserving generalization
across wildfire events.

## Primary dataset and event-disjoint protocol

The primary RCDA corpus contains 8,131 daily samples from 886 wildfire events
(2015–2019). Events, rather than image tiles, form the unit of allocation:
596 events (5,552 samples) are assigned to TRAIN, 106 (928) to VALIDATION and
184 (1,651) to a sealed TEST cohort. Binary duplicate checks and event-ID set
intersections are required to be empty across splits. All channel normalization
parameters are fitted on TRAIN only.

The prediction target is newly burned extent between consecutive observations,
`growth = t1_extent AND NOT t0_extent`. The model input includes the previous
extent, DEM, blue/green/red reflectance, NDVI, weather and air-density rasters,
near-front and global distance transforms, and forecast horizon. Wind direction
is represented by east (`sin`) and north (`cos`) components; geometric
augmentation reflects the corresponding component under horizontal or vertical
flips.

The six upstream RCDA weather/atmospheric channels are stored as rasters but
are spatially constant within the audited samples; the manuscript therefore
treats them as sample-level context, not as demonstrated local weather fields.
Their wind-direction bounds are `[-π, π]`, confirming radians before circular
encoding. WFIGS HRRR fields retain their spatial variation in the external
bridge.

## Architectures and preregistered search

Four spatial backbones and one conditioned variant are compared: U-Net, ASPP
U-Net, residual ASPP U-Net, RCDA and FiLM U-Net. The FiLM model aggregates
weather and horizon context to modulate deep features while retaining the full
spatial fields. A shallow physical residual prior exposes distance, horizon and
weather directly to the output logits.

The search has two validation-only phases. Phase 1 contains six architecture ×
target recipes. Phase 2 starts from the preregistered FiLM, sampling, objective
balance and model-width sweep and includes explicitly logged pre-TEST
amendments motivated only by TRAIN/VALIDATION diagnostics: a longer schedule,
balanced-precision loss, lower learning rate, growth-only ResUNet,
event-duration balancing and uniform event-mass sampling. Conditional candidates
run only while the best completed VALIDATION event-macro IoU is below 0.20. Epoch selection maximizes
event-macro growth IoU over thresholds 0.1–0.9; the final threshold is selected
once on VALIDATION over 0.05–0.95. TEST inference is disabled in both phases.
The combined winner is serialized to `FROZEN_RECIPE.json` before any new final
TEST run.

The TRAIN-only sampler audit found 15/5,552 zero-growth examples (0.27%), so
empty targets were not the dominant imbalance. The default sampler allocated
49.97% expected mass to 1–99-pixel growth fronts and retained an event-mass
coefficient of variation of 0.647; weighting each sample by the inverse number
of observations in its fire reduced that coefficient to numerical zero. This
motivated the conditional uniform-event ablation. Separately, five phase-1
probability combinations were evaluated only on VALIDATION. The best
multi-architecture ensemble scored 0.17440 versus 0.18066 for the best
individual checkpoint (Δ = −0.00626), so it was rejected before TEST.
All 5,552 TRAIN transitions retained every positive t0 pixel in t1 (zero lost
pixels), supporting the cumulative-extent interpretation of the labels.

The long-schedule run reached its last finite validation-selected checkpoint at
epoch 13 (event-macro IoU 0.16766; threshold 0.20) and encountered a non-finite
training loss at epoch 16. A complete scan of 13,002 TRAIN NPY files found no
non-finite values. We stopped the contaminated optimizer state, verified every
checkpoint tensor as finite, and reran only the standard VALIDATION evaluation;
the recovered artifact is explicitly marked as numerically truncated and never
accessed TEST. Before subsequent candidates, we registered a numerical-safety
amendment: stop optimization immediately on a non-finite loss and retain only a
verified finite VALIDATION checkpoint, fail on non-AMP non-finite gradients,
let `GradScaler` skip and downscale ordinary AMP overflow steps, and clip the
global gradient norm at 5.0. This amendment did not alter data splits, endpoints,
threshold grids, or the conditional candidate order.

After the primary Kaggle account exhausted its 30-hour weekly GPU allowance, we
shared the two private RCDA datasets read-only with a second account and moved
the remaining validation runs to a T4. A partial CPU precision run was stopped
for backend migration and excluded from selection. Every accepted Kaggle run
contains exactly one validation recipe and is recorded with its runner SHA-256;
checkpoints or metrics are never combined across duplicate backend attempts.
The precision-balanced T4 run subsequently reached its finite best at epoch 13
(VALIDATION event-macro IoU 0.17056; threshold 0.05) and encountered a
non-finite loss at epoch 21. We applied the same preregistered recovery rule:
optimization stopped, every retained tensor was verified finite, and the
checkpoint was re-evaluated on all 928 VALIDATION samples only. Because it did
not exceed the phase-1 leader, the conditional lower-learning-rate recipe was
launched next. The runner now emits a completed, explicitly truncated report
from a late finite checkpoint instead of losing the whole kernel artifact.

The lower-learning-rate ResUNet completed its validation-only schedule with a
best checkpoint at epoch 27 and threshold 0.05. Its event-macro IoU was 0.19411
over the same 106 VALIDATION fires (event-bootstrap 95% interval
0.17244–0.21723), compared with 0.18021 for the phase-1 ResUNet leader. The
paired mean improvement was 0.01390 and its descriptive bootstrap interval
crossed zero narrowly (−0.00013 to 0.02870); the new checkpoint won on 62.3% of
events. It improved all four duration strata and all four growth-size quartiles
(stratum deltas 0.0122–0.0169), with no significant monotonic association
between IoU and duration (Spearman ρ=0.10, p=0.30) or growth support
(ρ≈0, p=0.96). Pooled precision increased from 0.18274 to 0.19723 while recall
changed from 0.37674 to 0.37064; recall beyond 10.5 pixels from the observed
front increased from 0.13805 to 0.14436. These are interim model-selection results, not confirmatory TEST
evidence. The conditional growth-only, event-balanced, uniform-event and FiLM
candidates remain eligible while the completed VALIDATION leader is below
0.20; TEST remains unobserved. A small validation-only decoder grid subsequently
improved the same checkpoint to 0.19839 event-macro IoU (pooled IoU 0.14885)
using a one-pixel dilation and retention of components connected to t0. This
corresponded to a paired event-level delta of +0.00428 (10,000-resample 95%
bootstrap CI -0.00126 to +0.00991; wins on 57.55% of events). Because the
interval includes zero and the decoder was selected on VALIDATION, this is
descriptive rather than confirmatory evidence. The decoder remains provisional
until the remaining preregistered candidates complete.

Equal-weight late ensembles did not improve the individual checkpoint:
`low_lr + phase1` reached 0.19333 (Δ −0.00078 versus `low_lr`) and the
three-model `low_lr + phase1 + growth` ensemble reached 0.19195. They were
rejected on VALIDATION. The preregistered bounded leader-weight grid then found
one improvement: `low3_phase1_growth`, equivalent to weights 3:1:1, reached
0.19736 event-macro IoU (Δ +0.00325 versus `low_lr`) at threshold 0.40. It is
retained as the sole multi-model candidate; the weight search is closed and no
further ensemble tuning is permitted before TEST. The separately selected
single-checkpoint spatial decoder remains numerically higher on VALIDATION at
0.19839, with the uncertainty caveat above.

## Final primary evaluation

The frozen recipe is trained with seeds 11, 29 and 47. Each seed selects its
epoch and threshold on VALIDATION and performs exactly one TEST evaluation.
The primary endpoint is mean event-macro growth IoU across seeds. Uncertainty is
estimated by a paired 95% event bootstrap; a one-sided paired Wilcoxon test is
reported as a secondary contrast.

The strict gate requires: three completed preregistered seeds; mean event-macro
IoU ≥ 0.20; every seed above the strongest reproduced learned baseline; and a
positive lower bootstrap bound versus that strongest baseline. The historical
U-Net and RCDA checkpoints are independently re-evaluated on all 184 TEST
events to reconstruct paired per-event metrics.

The morphological comparator uses dilation radius 6, chosen solely by
VALIDATION event-macro growth IoU, and reaches 0.12724 on TEST. An earlier
radius-3 artifact (0.12186) had selected by pooled VALIDATION IoU; it is retained
as a labelled legacy artifact but is not the official comparator because its
selection endpoint did not match the paper's primary metric.

Secondary endpoints include pooled growth IoU, average precision, FCER-restricted
IoU and calibration, ECE, selective error at 80% coverage, AURC, FCER capture,
symmetric boundary F1 and recall beyond 10.5 pixels from the observed front.

## External WFIGS cohort

The WFIGS harvest contains 35,562 historical observations from 15,661 events.
After temporal, semantic and geometry rejection, 3,439 pairs remain. Candidate
scenes must be acquired and created in STAC before `t0`. Crops are fixed at
256×256 pixels and 60 m resolution and are positioned using `t0` only; `t1` is
used solely as the label and a truncation QA check. Inputs comprise Sentinel-2
reflectance and scene classification, Copernicus GLO-30 DEM and a NOAA HRRR run
available before `t0` that covers the complete forecast horizon.

Temporal archive availability alone is insufficient: the HRRR raster must also
contain the event bbox. This spatial audit leaves 2,530 pairs with a valid
space-time HRRR contract and rejects 673 outside the CONUS domain. The pilot is
balanced by geographic region and uses one pair per event. TRAIN, VALIDATION and
TEST events remain disjoint.

Two external settings are preregistered. Zero-shot transfer applies the frozen
RCDA weights and thresholds unchanged. Domain adaptation initializes those same
three checkpoints, trains only on WFIGS TRAIN, and selects epoch and threshold
only on WFIGS VALIDATION. A secondary adapted-seed probability ensemble also
selects its single threshold only on WFIGS VALIDATION. WFIGS TEST is materialized after both recipes are
frozen and is evaluated once. A morphological dilation radius selected only on
WFIGS VALIDATION is the external baseline.

The pre-TEST physical cohort contains 61 TRAIN and 19 VALIDATION fires, with one
pair per event and 13 channels on a fixed 256×256, 60 m grid. Horizon counts for
6–12/12–24/24–48 h are 6/26/29 in TRAIN and 2/8/9 in VALIDATION. Mean valid EO
coverage is 0.964 in both splits. Growth pixels represent 17.2% of target extent
in TRAIN and 38.5% in VALIDATION; this observed cohort heterogeneity is retained
and reported rather than rebalanced using any TEST information. An independent
audit reloaded all 80 tensors and found zero integrity or leakage issues.

## Rights and reproducibility

WFIGS source access is public, and the local policy permits internal,
non-commercial scientific analysis. No affirmative redistribution licence was
found for raw or derived data; therefore WFIGS tensors and derived checkpoints
are not released. Code, schemas, hashes, aggregate metrics and procedures can be
published independently, subject to final rights review. This restriction is
not used to imply that research use and commercial redistribution are legally
equivalent.

## Result tables populated from artifacts

### Table 1 — Validation-only architecture search

Source: `COMBINED_TUNING_SUMMARY.json` (`test_evaluated=false`).

| Rank | Recipe | Target | Best epoch | VAL threshold | VAL event-macro IoU |
|---:|---|---|---:|---:|---:|
| PENDING_ARTIFACT | PENDING_ARTIFACT | PENDING_ARTIFACT | PENDING_ARTIFACT | PENDING_ARTIFACT | PENDING_ARTIFACT |

### Table 2 — Sealed RCDA TEST

Source: `PAPER_SCORECARD.json` and `FINAL_SUMMARY_PAPER_METRICS.json`.

| Model | Seeds | Event-macro growth IoU | Paired Δ vs strongest | 95% CI | Gate |
|---|---:|---:|---:|---|---|
| Dilated copy (radius 6 selected on VAL event-macro IoU) | — | 0.12724 | — | — | baseline |
| Historical U-Net | 1 | 0.16331 | — | — | reproduced |
| Historical RCDA | 1 | 0.15635 | — | — | reproduced |
| Frozen candidate | 11/29/47 | PENDING_ARTIFACT | PENDING_ARTIFACT | PENDING_ARTIFACT | PENDING_ARTIFACT |

### Table 3 — External WFIGS TEST

Sources: `WFIGS_EXTERNAL_EVAL.json` and `WFIGS_ADAPTED_TEST_EVAL.json`.

| Setting | Events | Event-macro growth IoU | Geometry baseline | All seeds above baseline |
|---|---:|---:|---:|---|
| Frozen RCDA zero-shot | PENDING_ARTIFACT | PENDING_ARTIFACT | PENDING_ARTIFACT | PENDING_ARTIFACT |
| WFIGS domain-adapted | PENDING_ARTIFACT | PENDING_ARTIFACT | PENDING_ARTIFACT | PENDING_ARTIFACT |

## Reproduction entry points

- `scripts/run_rcda_paper_nightwatch.py`: two-stage VAL search, recipe freeze,
  final RCDA TEST and scorecard.
- `scripts/audit_rcda_training_sampler.py`: TRAIN-only sampling-mass audit.
- `scripts/tune_rcda_val_ensembles.py`: VAL-only probability-ensemble audit.
- `scripts/register_rcda_pretest_decisions.py`: pre-TEST decision and code-hash
  registry; refuses to run after a final candidate artifact exists.
- `scripts/materialize_wfigs_training_campaign.py`: bounded physical tensor
  campaign.
- `scripts/run_wfigs_data_nightwatch.py`: expanded TRAIN, isolated VALIDATION
  and train-only normalization.
- `scripts/audit_wfigs_tensor_dataset.py`: independent tensor, target, split
  and train-only-normalization integrity audit.
- `scripts/run_wfigs_external_validation_nightwatch.py`: post-freeze WFIGS TEST
  and zero-shot evaluation.
- `scripts/run_wfigs_domain_adaptation_nightwatch.py`: VAL-only adaptation and
  single post-freeze TEST evaluation.
