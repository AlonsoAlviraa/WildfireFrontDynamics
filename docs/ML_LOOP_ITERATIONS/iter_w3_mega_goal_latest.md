# WFD ML W3 MEGA GOAL

## Met: **true** · Status: **CLOSED** (2026-08-05)

> **Follow-up:** Tobarra weight claim settled by mega goal KEEP-or-KILL → **KILL** (fresh train IoU 0.4776).  
> Hub: `docs/goals/README.md` · State: `docs/CURRENT_STATE.md` · Board: `iter_tobarra_keep_or_kill_latest.md`

## Reason

Literal C1–C5 all verified on disk: non-pack hellin_2024 has align+NPZ+frozen Head A thr=0.795 with no thr retune claim; Tobarra K1–K5 scorecard at W3 close was **INCONCLUSIVE** (v29 re-score; K1 fail) with n_leaked_train_val=0; later fresh LOFO → **KILL**. field_ops fusion false · ml_product_go false · multi-fire boards · pytest w3/align/kill green.

## Sense

# WFD W3 MEGA GOAL — SENSE

## Rails (unchanged)
| Rail | Value |
|------|--------|
| `field_ops.allow_ml_live_in_fusion` | **false** (`config/decision_policies.json`) |
| `ml_product_go` | **false** (`docs/ML_PRODUCT_SCORECARD.json` gates) |
| thr/ECE fit on U1 TEST / held-out fire TEST | **forbidden** (K4; not done this cycle) |
| IoU ≠ ROS | honored |

## (1) Git
`main...origin/main` — many modified + untracked (W3 lab scripts, w3_signal, kill scorer, etc.). Not clean.

## (2–3) Product gates
- **field_ops fusion:** `false`
- **ml_product_go:** `false` · `u1_test_honest: true` · `allow_ml_live_in_fusion_recommended: true` (recommend only; not promote)

## (4) Tobarra recipe — kill + leak
Path: `outputs/ml_eval/lab_loop/tobarra_finetune_recipe.json`  
Rec: `OPTIONAL_lofo_finetune_with_kill` · baseline Head A mean IoU **0.4894**

| ID | Rule (short) |
|----|----------------|
| K1 | held-out Tobarra IoU − baseline ≥ **0.03** |
| K2 | improvement_vs_copy ≥ **0.05** |
| K3 | n_leaked_train_val = **0** |
| K4 | no thr/ECE on U1 TEST or Tobarra test |
| K5 | ml_product_go false · field_ops fusion false |

**Leak audit:** ok · held_out `tobarra_20240802` · train/val/test **531/59/300** · **n_leaked_train_val=0** · test_foreign=0

## (5) Expert + w3 presence
- `lab_loop_v34_w3_expert_latest.json`: **present** · control_answer **YES** · rails product_go/fusion OFF · friction `hellin_unaligned_blocked_patches_tobarra_hard` (historical label; artifacts now present)
- `outputs/ml_eval/w3/*` Head A:

| Fire | Present | head_a mean_iou | n_eval | ece_full |
|------|---------|-----------------|--------|----------|
| hellin_2024 | yes + patches | **0.789** | 60 | 0.077 |
| brazatortas_2025 | yes + patches | **0.544** | 60 | 0.224 |
| retuerta_2025 | yes + patches | **0.466** | 40 | 0.333 |

Locked thr **0.795** (frozen cal; not retuned on these fires). IoU = mask quality, **not ROS**.

## (6) v29_lofo_tobarra
Dir: `outputs/ml_eval/v29_lofo_tobarra/`  
- metrics: `evaluation_metrics.json` present  
- weights: `weights_pretrained_best.pt` present (~4.3 MB)  
- Published/prior: test_iou **0.4938** · improvement_vs_copy **0.1654** · verdict GO_TRANSFER_LOFO (copy-relative)  
- Top-level metrics: model_iou **0.4938** · improvement_vs_copy **0.1654** (thresh 0.5)

## (7) Kill scorer
```
python scripts/score_tobarra_kill_criteria.py
→ verdict: INCONCLUSIVE
  K1 fail (Δ vs baseline 0.0044 < 0.03)
  K2 pass (0.165 ≥ 0.05)
  K3 pass (leak 0)
  K4 pass (eval-only scorer)
  K5 pass (rails OFF)
```
Out: `outputs/ml_eval/lab_loop/tobarra_kill_scorecard.json`

## SENSE one-liner
Rails solid · W3 Head A artifacts for hellín/brazatortas/retuerta on disk · Tobarra LOFO recipe + zero leak · v29 weights/metrics present · **TOBARRA_KILL = INCONCLUSIVE** (beats copy, fails K1 lift vs ensemble baseline) · **no** field fusion / product_go flip.

## Implement

# W3 MEGA GOAL — IMPLEMENTER close-out

**skip_train=true · extra_fire=retuerta_2025 · mega goal: MET · Tobarra weights: INCONCLUSIVE · rails locked**

## Actions taken

| # | Action | Result |
|---|--------|--------|
| 1 | Verified existing artifacts (prefer no retrain) | kill / leak / v29 / w3 Head A all on disk |
| 2 | Rails probe | `field_ops.allow_ml_live_in_fusion=false` · `ml_product_go=false` — **not flipped** |
| 3 | `python scripts/score_tobarra_kill_criteria.py` | **INCONCLUSIVE** (K1 fail, K2–K5 pass) |
| 4 | Leak re-audit | `n_leaked_train_val=0` · train/val/test 531/59/300 |
| 5 | Verify `retuerta_2025` + `hellin_2024` Head A | present, `ok=true`, locked thr 0.795 |
| 6 | `pytest tests/test_w3_signal.py tests/test_align_geotiff_stack.py tests/test_tobarra_kill_score.py -q` | **11 passed** |
| 7 | Refresh board MD + machine JSON timestamps | C1–C5 re-verified; form-feed glitches fixed in latest MD |
| 8 | Train / thr / ECE fit | **skipped** (rails + K4) |

## Rails (unchanged)

| Rail | Value | Path |
|------|--------|------|
| `field_ops.allow_ml_live_in_fusion` | **false** | `C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\config\decision_policies.json` |
| `ml_product_go` | **false** | `C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\docs\ML_PRODUCT_SCORECARD.json` |
| thr/ECE on U1 TEST / held-out fire TEST | **not done** | eval-only scorer |
| IoU ≠ ROS | honored | boards + honesty |

## Required artifacts

| Artifact | Path | Status |
|----------|------|--------|
| Tobarra kill scorecard | `C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\outputs\ml_eval\lab_loop\tobarra_kill_scorecard.json` | **INCONCLUSIVE** |
| Leak audit | `C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\outputs\ml_eval\lab_loop\tobarra_leak_audit_latest.json` | **n_leaked=0** |
| Hellín Head A | `C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\outputs\ml_eval\w3\hellin_2024\head_a_eval.json` | mean IoU **0.789** · n=60 |
| Retuerta Head A | `C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\outputs\ml_eval\w3\retuerta_2025\head_a_eval.json` | mean IoU **0.466** · n=40 |
| Machine mega board | `C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\outputs\ml_eval\lab_loop\lab_loop_v34_w3_mega_latest.json` | `mega_goal_met=true` |
| Latest board MD | `C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\docs\ML_LOOP_ITERATIONS\iter_w3_mega_goal_latest.md` | C1–C5 **YES** |
| Dated board MD | `C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\docs\ML_LOOP_ITERATIONS\iter_20260805_w3_mega.md` | refreshed UTC |

## Tobarra K1–K5 (skip_train re-score of v29)

| ID | Result | Detail |
|----|--------|--------|
| K1 | **FAIL** | lift **0.0044** &lt; 0.03 vs Head A baseline **0.489** (test IoU **0.494**) |
| K2 | **PASS** | improvement_vs_copy **0.165** ≥ 0.05 |
| K3 | **PASS** | leak **0** |
| K4 | **PASS** | scorer eval-only |
| K5 | **PASS** | fusion OFF · product_go false |

**Verdict: INCONCLUSIVE** — beats copy, fails full-recipe KEEP vs ensemble Head A baseline. No KEEP claim.

## External W3 Head A (frozen cal, thr=0.795)

| Fire | n_HeadA | mean IoU | Δ copy | ECE |
|------|--------:|---------:|-------:|----:|
| hellin_2024 | 60 | **0.789** | **+0.114** | 0.077 |
| brazatortas_2025 | 60 | 0.544 | +0.002 | 0.224 |
| retuerta_2025 | 40 | 0.466 | ~0 | 0.333 |

## Tests

```text
pytest tests/test_w3_signal.py tests/test_align_geotiff_stack.py tests/test_tobarra_kill_score.py -q
→ 11 passed
```

## One-liner

Rails solid · W3 Head A hellín/brazatortas/retuerta on disk · Tobarra zero leak · v29 re-score **INCONCLUSIVE** (K1 fail) · C1–C5 mega **MET** · **no** field fusion / product_go flip · skip_train honored.

## Adversarial

# Adversarial ML protocol skeptic — W3 MEGA GOAL

**Skeptic verdict:** Under the **literal** C1–C5 contract, **MEGA GOAL MET survives**.  
**Product-strength claims (Tobarra KEEP, multi-fire transfer, field readiness) do not.**

Independent re-checks (disk + source fields + pytest + rails JSON) match the implementer on the hard rails. Several **integrity / honesty / rubber-stamp** attacks land as residual risk, not full C1–C5 falsification.

---

## Criterion scorecard (adversarial)

| ID | Claim | Independent finding | Survives? |
|----|--------|---------------------|-----------|
| **C1 NEW_FIRE** | ≥1 non-pack fire: align + NPZ + frozen Head A thr~0.795, no thr fit on that fire | **hellin_2024**, **retuerta_2025** have align + patches + `head_a_eval.json` / NPZ; `locked_thr=0.795`; rails claim no thr retune. Hellín is real signal (IoU≈0.789, Δcopy≈+0.114). | **YES** (hellín alone) |
| **C2 TOBARRA_KILL** | K1–K5 scorecard KEEP\|KILL\|**INCONCLUSIVE**; leak=0; no thr/ECE on test | Scorecard: **INCONCLUSIVE**; K1 fail (+0.0044), K2–K5 pass; `n_leaked_train_val=0` re-verified on fold sources | **YES** (INCONCLUSIVE is allowed) |
| **C3 RAILS** | field_ops fusion false; ml_product_go false; no ECE thrash holdout TEST | `field_ops.allow_ml_live_in_fusion=false`; `gates.ml_product_go=false`; no evidence of thr/ECE fit this cycle | **YES** |
| **C4 BOARD** | multi-fire MD+JSON updated with honesty | Latest + dated MD + machine JSON; KEEP not claimed; IoU≠ROS; CARDOSO≈U1 noted | **YES** |
| **C5 TESTS** | pytest w3/align/kill green | `11 passed` re-run this session | **YES** |

**MEGA GOAL MET (literal): YES**  
**Tobarra weights KEEP: NO** (honestly **INCONCLUSIVE**)  
**Field product / fusion promote: NO**

---

## Attacks (attempted falsifications)

### A1 — Zero-leak is filename cosplay / incomplete audit
**Method:** Re-scan LOFO fold NPZ `source` fields + filenames.  
**Result:** **Attack fails.**

| Split | n | sources | missing `source` |
|-------|--:|---------|------------------|
| train | 531 | CARDOSO 200, ESTRELLA_ACOM1 200, ESTRELLA_ACOM2 131 | 0 |
| val | 59 | ESTRELLA_ACOM2 59 | 0 |
| test | 300 | tobarra_20240802 300 | 0 |

- `n_leaked_train_val = 0`, `test_foreign = 0`  
- Residual hole: audit only flags exact `source == "tobarra_20240802"`; missing source would **not** count as leak (currently 0 missing, so moot)

**Survivor:** K3 zero-leak on this fold.

---

### A2 — KEEP smuggled via copy-relative GO_TRANSFER
**Method:** Compare K1 bar vs prior v29 narrative.  
**Result:** **Attack fails** (boards do not claim KEEP).

- v29 `model_iou` @ thr **0.5** = **0.4938**; Head A baseline **0.4894** → lift **0.0044 < 0.03** → K1 **FAIL**
- K2 improvement_vs_copy **0.165 ≥ 0.05** → PASS (copy-relative only)
- Scorecard + mega JSON: `verdict: INCONCLUSIVE`, `not_keep: true`
- Note: multi-thresh table peaks higher at thr 0.6 (`model_iou`≈0.499) but **top-level uses 0.5**, so not thr-cherry-picked for max IoU

**Survivor:** No KEEP claim under full recipe.

---

### A3 — thr/ECE fit on held-out / new-fire TEST
**Method:** Inspect scorer K4, Head A caches, scorecard gates.  
**Result:** **Partial hit (process weakness), not a proven fit crime.**

| Check | Finding |
|-------|---------|
| K4 in scorer | **`pass: True` hardcoded** — “this scorer does not fit thr/ECE”; does **not** audit historical v29 train logs |
| W3 Head A | `locked_thr=0.795`; calibrator path production; code comment fit_split=`lofo_test` means **never use for fit** |
| ECE on new fires | **Reported** (hellín 0.077, braz 0.224, retuerta 0.333), not used to retune thr |
| U1 / product | `ml_product_go=false`; cal fit claimed VAL-only |

**Survivor:** No evidence of thr/ECE **fit** on Tobarra test or new-fire TEST this cycle.  
**Does not survive as strong assurance:** K4 is a rubber stamp, not an independent historical audit.

---

### A4 — field_ops / product_go flipped
**Method:** Read `config/decision_policies.json` + `docs/ML_PRODUCT_SCORECARD.json`.  
**Result:** **Attack fails for named rails.**

- `policies.field_ops.allow_ml_live_in_fusion` = **false**
- `gates.ml_product_go` = **false**
- **Adjacent risk:** `research_open.allow_ml_live_in_fusion` = **true** (experimental); `allow_ml_live_in_fusion_recommended` = **true** — recommend ≠ promote, but easy misread

**Survivor:** C3 field_ops + ml_product_go rails.

---

### A5 — IoU sold as ROS
**Method:** Board MD + mega JSON + scorecard honesty.  
**Result:** **Attack fails.** Explicit IoU ≠ ROS / not tactical language present.

---

### A6 — “New fire Head A” is theater (quality / provenance)
**Method:** Features, counts, mtimes.  
**Result:** **Strong hit on quality; C1 structure still holds via hellín.**

#### hellin_2024 — **real C1 survivor**
- align + 320 patches + NPZ + Head A  
- mean IoU **0.789**, Δcopy **+0.114**, locked thr **0.795**, abstain@lock ~0.52  
- Feature variance non-degenerate  

#### retuerta_2025 — **structure OK, signal null**
- align + 300 patches + Head A present  
- mean IoU **0.466** ≈ copy (Δ ~ 0)  
- **`features` has 1 unique row** (all patches same diagnostics)  
- conf_band std ~0 → constant conf **0.8079**  
- ECE **0.333**, abstain@0.795 = **0** (locked thr does nothing)  
- C1 “has frozen Head A” yes; “transfer works” **no**

#### brazatortas_2025 — **stale Head A vs disk patches**
| Artifact | Fact |
|----------|------|
| disk patches | **57** |
| `head_a_features` rows | **60** |
| `align_and_patch.json` `n_total` | **80** |
| Head A mtime | **08:31:51Z** |
| patches mtime | **08:39–08:42Z** (after Head A) |

→ Head A was built on an **older patch set**, then patches rewritten. Board still quotes n_HeadA=60 / n_disk=57 without flagging **cache/disk desync**.

**Does not kill C1** (hellín + retuerta structure), **does kill** any claim that “all three external fires have current, matched Head A.”

---

### A7 — C2 “done this cycle” implies fresh LOFO train
**Method:** skip_train + metrics provenance.  
**Result:** **Narrative attack hits; criterion still allows re-score.**

- C2 is **re-score of prior** `v29_lofo_tobarra/evaluation_metrics.json`  
- Weights present (~4.3 MB) but **not retrained** this cycle  
- Boards disclose skip_train — honesty OK if reader notices  

---

### A8 — Tests lock the mega claims
**Method:** Read tests + re-run.  
**Result:** **Weak green.**

```text
pytest tests/test_w3_signal.py tests/test_align_geotiff_stack.py tests/test_tobarra_kill_score.py -q
→ 11 passed
```

| Gap | Detail |
|-----|--------|
| Kill test | Accepts any of KEEP\|KILL\|INCONCLUSIVE; does **not** assert K1 fail or leak==0 |
| Leak test | Synthetic fold only; does not pin production fold |
| W3 tests | Soft-skip if caches missing; do not assert hellín IoU or retuerta degeneracy |

**Survivor:** C5 as “pytest green.”  
**Does not survive:** “tests prove mega goal content.”

---

### A9 — K1 protocol apples-to-oranges
**Admitted in scorecard honesty** and correct to flag:

- K1: LOFO specialist **mask IoU @ thr 0.5** vs ensemble **Head A mean IoU** baseline  
- Protocols differ; near-zero lift may partly be metric mismatch, not only “model bad”  
- Still: recipe defines K1 this way → **KEEP blocked** under full recipe

---

## Survivors (what holds under pressure)

1. **Rails:** `field_ops.allow_ml_live_in_fusion=false`, `ml_product_go=false`  
2. **Tobarra LOFO leak:** true zero target leak on fold sources (531/59/300)  
3. **Kill verdict honesty:** **INCONCLUSIVE**, not KEEP; K1 fail explicit  
4. **Hellín frozen Head A:** strong non-pack transfer signal under thr 0.795  
5. **Boards:** multi-fire MD+JSON updated; IoU≠ROS; CARDOSO≈U1; catalog 0.8963 provenance-only  
6. **pytest suite named for C5:** green (11)  
7. **No thr/ECE retune evidence** on new fires / holdout this cycle (report-only ECE)

---

## Residual risks (ordered)

| # | Risk | Severity | Why it matters |
|---|------|----------|----------------|
| R1 | **Brazatortas Head A cache ≠ current patches** (60 vs 57; Head A older than patches) | High integrity | External W3 table row is stale; board overstates “verified” multi-fire set |
| R2 | **Retuerta Head A degenerate** (1 unique feature row; conf constant; IoU≈copy) | High product | “extra_fire=retuerta_2025” adds coverage theater, not transfer evidence |
| R3 | **K4 rubber-stamp** (`pass=True` always in scorer) | High protocol | Cannot certify historical thr/ECE discipline on v29 from scorecard alone |
| R4 | **`research_open` live fusion true** + scorecard `…_recommended: true` | Med ops | Mis-promotion path if wrong policy / “recommended” read as GO |
| R5 | **skip_train INCONCLUSIVE** frozen as mega close-out | Med roadmap | No path this cycle to K1 KEEP; easy to over-sell “Tobarra recipe complete” |
| R6 | **K1 protocol mismatch** (LOFO thr0.5 vs ensemble Head A) | Med science | KEEP/KILL sensitivity depends on metric definition |
| R7 | **Tests don’t pin leak=0 / K1 fail / fire integrity** | Med CI | Green tests tolerate false KEEP or silent leak regression |
| R8 | **Leak audit exact string only** | Low (today) | Missing/renamed `source` would not flag leak |
| R9 | **Git dirty main** | Process | Harder audit of what changed vs claimed |
| R10 | **Hellín n_HeadA=60 << n_disk=320** (subsample) | Low–med | Documented; variance of “strong” claim depends on subsample policy |

---

## Red lines checked (flags)

| Forbidden / claimed | Status |
|---------------------|--------|
| thr/ECE **fit** on U1 TEST / held-out fire TEST | **Not observed** this cycle; K4 not independently audited for v29 history |
| `field_ops` fusion flip | **No** — still false |
| `ml_product_go` flip | **No** — still false |
| IoU-as-ROS | **Not** on boards |
| KEEP despite K1 fail | **Not claimed** |
| Zero-leak | **Holds** on independent source audit |
| Partial mega as MET | N/A — they claim full MET; **literal C1–C5 support it** |

---

## Bottom line

```text
MEGA GOAL MET (C1–C5 literal) ........ SURVIVES
Tobarra KEEP ......................... DEAD (INCONCLUSIVE; K1 fail)
Zero leak ............................ SURVIVES
Rails (field_ops + product_go) ....... SURVIVE
New-fire scientific transfer ......... PARTIAL (hellín yes; retuerta null; braz stale)
K4 as assurance ...................... WEAK (hardcoded pass)
Tests as claim lock .................. WEAK green
```

**One-liner for the board:**  
Rails + leak + INCONCLUSIVE kill score + hellín frozen Head A + green tests justify **literal mega MET**; do **not** upgrade to KEEP, multi-fire product readiness, or matched retuerta/brazatortas signal without re-building Head A caches against current patches and fixing K4/tests to assert content, not ceremony.

### Immediate integrity fixes (not required for literal MET, required for honest multi-fire board)

1. Rebuild **brazatortas** Head A from current 57 patches; re-quote n and IoU.  
2. Flag **retuerta** as null-feature / copy-tied transfer, not a second success.  
3. Replace K4 hardcoded pass with train-log / config audit (or explicit `unknown` if unauditable).  
4. Harden tests: `n_leaked_train_val==0`, verdict≠KEEP while K1 fails, Head A n ≤ disk patches.
