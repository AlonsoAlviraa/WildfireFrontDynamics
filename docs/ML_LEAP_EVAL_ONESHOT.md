# ML LEAP — E1 eval one-shot (frozen calibrator)

> **As of:** 2026-08-12  
> **Plan:** `docs/PLAN_ML_LEAP_2026-08-12.md` (pack E1)  
> **Product:** `clm_ensemble_v34` · protocol `clm_holdout_test_seed42_v1`  
> **Rails:** FREEZE_ML · never fit cal on TEST · fusion OFF · IoU ≠ ROS  
> **Authority scorecard:** `docs/ML_PRODUCT_SCORECARD.json`

One-shot de **repro / drift**, no de retrain. SKIP sin weights **≠** honesty green.

---

## Comando canónico (orden)

```bash
# 1) Gates (must PASS)
python scripts/check_release_flags.py

# 2) ML smoke (CI-equivalent; does not rewrite cal)
#    (repo Makefile / CI "ML smoke test" job)

# 3) U1 TEST + frozen VAL-fit calibrator
python scripts/eval_ml_uncertainty_u1.py --split test \
  --calibrator models/clm_ensemble/uncertainty_calibration_v1.json \
  --output outputs/ml_eval/scorecards/ml_scorecard_u1_latest.json

# 4) Validate schema rails (no ROS leakage)
python scripts/validate_ml_scorecard.py outputs/ml_eval/scorecards/ml_scorecard_u1_latest.json
# or vs sealed product card:
python scripts/validate_ml_scorecard.py docs/ML_PRODUCT_SCORECARD.json
```

Windows PowerShell: `$env:PYTHONPATH = "."` si hace falta.

---

## Freeze rules (hard)

| Rule | Why |
|------|-----|
| **Do not overwrite** `models/clm_ensemble/uncertainty_calibration_v1.json` | Fit split must stay **val**; TEST-fit is refuse |
| **Do not** `--allow-identity` on honesty/promote path | Identity cal is research-only |
| **SKIP without weights/NPZ** | Exit 0 skip ≠ U1 pass; do not sell as green |
| **Compare** latest vs `docs/ML_PRODUCT_SCORECARD.json` | Drift note; do not silently replace sealed numbers |
| **No** `promote_ml_live_fusion` | fusion stays OFF |

If `eval_ml_uncertainty_u1` prints `ERROR: calibrator claims fit_split=test` → **stop**. Do not “fix” by refitting.

---

## How to read the scorecard (no vanity)

| Field | Sealed (approx) | Sell |
|-------|-----------------|------|
| `primary.model_iou` | ~0.857 (n=200 TEST) | Lab mask IoU only |
| `uncertainty.selective_iou_at_80pct_coverage` | ~0.903 | Ranking; **not** “drop 20% of fire” |
| `uncertainty.ece_patch_conf` | ~0.153 TEST | Honest residual; nested VAL ECE ~0.058 **is not TEST** |
| Catalog 0.8963 | provenance | **L4 NO-sell** as live/ROS |

Claim board: `docs/CLAIM_BOARD_ML_LEAP_2026-08-12.md` (L1 yes-with-scorecard; L4–L8 no).

---

## Drift note (template)

After a real TEST run (weights present), add a one-liner under `outputs/ml_eval/` or PR body:

```
E1 <date>: latest IoU=… ECE=… sel@80=… vs sealed 0.857 / 0.153 / 0.903
delta_iou=…  (no stamp overwrite unless Alonso + new protocol)
```

If weights missing: write `E1 SKIP: no weights/NPZ — not honesty green`.

---

## Non-goals (this pack)

- Retrain / v35 / Swin  
- Hellín promote (D0 humano)  
- Fusion ON / GO_Q true  
- Invent p95 latency (that is P1, measured only)
