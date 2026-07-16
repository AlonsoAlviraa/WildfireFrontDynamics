# ML Engineering Loop Rails

Three rails only for ML after 2026-07-15:

| Rail | Question | Example single_change |
|------|----------|------------------------|
| **Features** | New informative inputs? | `schema=physics14` → `physics15` (+wind_upslope) |
| **Temporal** | Multi-timestep context? | `sequence_length=3` |
| **Transfer** | Real-fire holdout? | CLM test Δ copy |

## Gates

| Gate | Target | Status (2026-07-15) |
|------|--------|---------------------|
| G0 | v21 IoU 0.226, Δ +0.076 (any_fire 979) | **GO** product `ndws_v21` |
| G1 | IoU ≥ 0.25, Δ ≥ +0.09 same protocol | **OPEN** — v25/v26 features **NO_PROMOTE**; **v27 T=2** running |
| G2 | Δ copy > 0 on CLM **test** holdout | **GO** product `clm_v28` (IoU 0.838, Δ +0.196) |

Feature rail closed for G1 (physics14/15 did not beat v21). Temporal rail is the active G1 fight.

## Queue

See `scripts/experiment_queue_features.json` (v25+). Active G1 attempt:

```bash
cp kaggle_job/kernel-metadata-v27.json kaggle_job/kernel-metadata.json
kaggle kernels push -p kaggle_job
```

Kernel: `alonsoalviraaaa/wildfire-front-training-v27-temporal-t2`
## Kill list

filter-only · pos_weight-only · EMA/focal without new signal · train-CLM as transfer GO · promote NDWS without G1
