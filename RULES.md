# 📐 RULES — WildfireFrontDynamics Loop Engineering

## Core Loop Protocol

Every change follows this cycle. **No exceptions.**

```
1. HYPOTHESIS  → State what you expect and WHY (one sentence)
2. IMPLEMENT   → Change ONE thing only (isolate variables)
3. TEST LOCAL   → `python -m pytest tests/ -q` must pass
4. PUSH        → `git commit` + `git push origin main`
5. LAUNCH      → Kaggle kernel push
6. WAIT        → Kernel runs (~2-4h)
7. DOWNLOAD     → `kaggle kernels output`
8. ANALYZE     → Compare metrics to previous baseline
9. DECISION    → Better? New baseline. Worse? Revert.
10. DOCUMENT   → Update EXPERIMENT_TRACKER.md + MEMORY.md
11. REPEAT     → Next hypothesis from the queue
```

---

## Variable Isolation Rule

**Never change two things at once.**

- ❌ BAD: Change loss function AND learning rate AND batch size in one experiment
- ✅ GOOD: Change ONLY the loss function. Measure. Then change learning rate.

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
- **Verdict:** ✅ Better / ❌ Worse / ⚖️ Neutral
- **Next:** [What to try next]
```

---

## Revert Protocol

If an experiment makes things worse:

1. `git revert <commit>` to undo the code change
2. Document WHY it failed in `EXPERIMENT_TRACKER.md`
3. Add to "Failed Hypotheses" table (do NOT retry without modification)
4. Move to the next hypothesis in the queue

---

## Acceptance Criteria (Definition of Done)

We do NOT stop the loop until ALL minimum viable thresholds are met:

| Metric | Current | Minimum Viable | Target |
|---|---|---|---|
| IoU | 0.002 | **>0.15** | >0.30 |
| Recall | 0.002 | **>0.30** | >0.50 |
| Precision | 0.161 | **>0.30** | >0.50 |
| best_epoch | 2 | **>10** | >20 |

---

## Failed Hypotheses (DO NOT RETRY)

| # | Hypothesis | Why it failed |
|---|---|---|
| 1 | "LR too high" (v11 halved LR) | best_epoch went 3→1 |
| 2 | "Class imbalance causes low recall" (v12 pos_weight 3→8) | recall went 4.2%→0.2% |
| 3 | "Freeze conv protects features" (v12) | Result worse than baseline |

---

## Code Quality Rules

1. **Tests must pass** — `python -m pytest tests/ -q` before every push
2. **No emojis in Python code** — UTF-8 encoding issues on Windows
3. **Self-contained Kaggle scripts** — Inline model definitions to avoid import errors
4. **PyTorch ≤2.1.x** — Kaggle P100 GPU (sm_60) requires older PyTorch
5. **Commit messages** — Follow conventional commits: `feat()`, `fix()`, `docs()`, `chore()`
6. **Push to main** — No feature branches needed for solo project

---

## Kaggle Resource Rules

- **Account:** `alonsoalviraaaa` (university, 30 GPU-h/week)
- **One experiment at a time** — Don't launch parallel kernels
- **Monitor GPU time** — Track in `EXPERIMENT_TRACKER.md`
- **Always download outputs** — Save to `kaggle_outputs_vXX/`

---

## Documentation Rules

- **MEMORY.md** — Updated after every loop iteration (what worked, what didn't)
- **EXPERIMENT_TRACKER.md** — Updated after every experiment completes
- **VISION.md** — Rarely changes (north star)
- **ARCHITECTURE.md** — Updated when architecture changes
- **RULES.md** — This file. Updated when process changes