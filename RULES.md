# RULES — WildfireFrontDynamics Loop Engineering

## Core Loop Protocol

Every **ML experiment** follows this cycle. Product/docs-only changes may stop after TEST LOCAL.

```
1. HYPOTHESIS  → State what you expect and WHY (one sentence)
2. IMPLEMENT   → Change ONE thing only (isolate variables)
3. TEST LOCAL  → `python -m pytest tests/ -q` must pass
4. COMMIT      → Conventional commit; push branch or main as policy allows
5. LAUNCH      → Kaggle kernel push (active: v21 metadata / script) when training
6. WAIT        → Kernel runs (hours; depends on GPU quota)
7. DOWNLOAD    → `kaggle kernels output` when remote train finished
8. ANALYZE     → Compare metrics to previous baseline (manifest + tracker)
9. DECISION    → Better? New baseline. Worse? Revert.
10. DOCUMENT   → Update docs/EXPERIMENT_TRACKER.md + MEMORY.md if baseline moved
11. REPEAT     → Next hypothesis from the queue
```

Honesty notes:

- Steps 5–7 apply only when you actually train remotely. Local-only eval/smokes skip them.
- Do not treat archived scripts (`kaggle_job/archive/*`) as the default launch path.
- Active U-Net train script: `kaggle_job/run_unet_training_v21.py` with `kernel-metadata-v21.json`.
- Prefer feature branches for multi-file product work; solo micro-experiments may land on main if CI is green.

---

## Variable Isolation Rule

**Never change two things at once.**

- BAD: Change loss function AND learning rate AND batch size in one experiment
- GOOD: Change ONLY the loss function. Measure. Then change learning rate.

If you must change multiple things (e.g., new architecture), document each sub-change.

---

## Experiment Documentation Rule

After every experiment completes, log it in `docs/EXPERIMENT_TRACKER.md`:

```markdown
### vX: [Experiment Name]
- **Hypothesis:** [What we expected]
- **Change:** [What we changed — ONE thing]
- **IoU:** [value] (prev: [value], delta: [value])
- **Recall:** [value] (prev: [value], delta: [value])
- **best_epoch:** [value]
- **val_loss:** [value]
- **Verdict:** Better / Worse / Neutral
- **Next:** [What to try next]
```

Also refresh `MEMORY.md` when the **promoted product baseline** or active train path changes.

---

## Revert Protocol

If an experiment makes things worse:

1. Revert the code change (`git revert` or equivalent)
2. Document WHY it failed in `EXPERIMENT_TRACKER.md`
3. Add to "Failed Hypotheses" (do NOT retry without modification)
4. Move to the next hypothesis in the queue

---

## Acceptance Criteria (Definition of Done)

Product gates differ by domain. Do **not** use the old A3C-era IoU ~0.002 table as current truth.

### ML research (NDWS) — production baseline `ndws_v21`

| Metric | Current (v21) | Stretch gate (historical G1) |
|--------|---------------|------------------------------|
| Test IoU | **0.226** | ≥ 0.25 |
| Δ vs copy IoU | **+0.076** | ≥ +0.09 |

v21 remains research/production NDWS until a run honestly beats both gates.

### ML Spain emergency — default `clm_ensemble_v34`

| Metric | Current (v34 holdout) | Floor (do not ship below without decision) |
|--------|----------------------|--------------------------------------------|
| U1 TEST honest mean IoU (lab pitch) | ~**0.86** | primary public claim surface |
| Catalog holdout IoU (provenance only) | **0.8963** | not live certainty · not ROS · not ops |
| Δ vs copy IoU (catalog) | **+0.2545** | positive vs copy required |
| Growth IoU (catalog) | **0.9071** | track; do not optimize on test |

Single specialist `clm_v28`: IoU **0.838**, Δ **+0.196**.

### Ops / Decision Card

| Gate | Rule |
|------|------|
| Ops ≠ ML | Never report drone ROS as ML IoU |
| Abstention | Weak/empty sources → ABSTAIN |
| Reliability claim | Only PASS when a real gate result exists (no hard-coded five-nines) |

---

## Failed Hypotheses (DO NOT RETRY unchanged)

| # | Hypothesis | Why it failed |
|---|------------|---------------|
| 1 | "LR too high" (v11 halved LR) | best_epoch collapsed further in A3C era |
| 2 | "Class imbalance alone" (extreme pos_weight) | recall collapsed |
| 3 | "Freeze conv protects features" (v12-style) | worse than baseline |
| 4 | Ensemble mix tuned on holdout test | leakage; mix/temps only on VAL |

---

## Code Quality Rules

1. **Tests must pass** — `python -m pytest tests/ -q` before every push (~270+ functions / ~40 files)
2. **No emojis in Python code** — UTF-8 / console issues on Windows
3. **Self-contained Kaggle scripts when pushed** — avoid broken import paths on the kernel
4. **PyTorch** — respect GPU capability of the target kernel (historical P100 needed ≤2.1.x)
5. **Commit messages** — conventional commits: `feat()`, `fix()`, `docs()`, `chore()`
6. **Lint scope matches CI** — `ruff check wildfire_front tests scripts`; format `wildfire_front tests`
7. **Legacy** — A3C and mega/v13 scripts are archive/legacy; do not re-document them as active

---

## Kaggle Resource Rules

- One remote experiment at a time unless quota is explicitly managed
- Track GPU time and outcomes in `docs/EXPERIMENT_TRACKER.md`
- Prefer `kernel-metadata-v21.json` for U-Net production path
- Download outputs; do not leave the only copy on Kaggle
- Archive scripts under `kaggle_job/archive/` are for replay, not default push

---

## Documentation Rules

| File | When to update |
|------|----------------|
| `MEMORY.md` | Product baseline or active train path changed |
| `docs/EXPERIMENT_TRACKER.md` | Every completed experiment |
| `VISION.md` | Rarely (north star) |
| `ARCHITECTURE.md` | Architecture or product surface changed |
| `RULES.md` | Process / gates changed |
| `models/*/manifest.json` | When promoting weights (metrics + protocol) |

Scientific integrity: keep `observed` / `inferred` / `ground_truth` separate; no train leakage; provenance hashes for new artifacts.
