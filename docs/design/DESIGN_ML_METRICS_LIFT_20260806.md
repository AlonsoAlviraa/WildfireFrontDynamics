# Design — Lift lab ML metrics (LOFO mean + weak-fold floor)

| Campo | Valor |
|-------|--------|
| **Status** | DESIGN READY (rev 2026-08-06c — D3 waiver) — **PR1–PR3a implemented** (board + projector + leak audit + kill scorer + harness); PR3b offline full LOFO not yet run; no KEEP / no PR4 promote |
| **Date** | 2026-08-06 |
| **Product rail** | `lab_ml` only (`clm_ensemble_v34`) |
| **North star** | Multi-fire **LOFO mean IoU** ↑ and **weakest-fold floor** ↑ |
| **Secondary** | Holdout U1 TEST mean IoU report-only (no silent regress) |
| **Next gate (locked)** | `W3_new_features_or_data` |
| **Related** | `docs/design/DESIGN_ML_LAB_LOOP_CONTINUOUS.md` (historical; some snapshots still stamp `ml_product_go: false` — **this design + scorecard supersede** for rails: stamp from `product_facade.DEFAULT_RAILS` / `docs/ML_PRODUCT_SCORECARD.json` only), `docs/design/LAB_UNET_SCALE_KILL_CRITERIA.md`, `docs/ML_PRODUCT_SCORECARD.json` |

---

## 1. Problem / context

Lab loop freeze + W3 multi-fire probe + Tobarra KEEP-or-KILL are **closed**. The honest picture is:

- Single-holdout U1 TEST mean IoU is **strong** (~0.86).
- Multi-fire **LOFO mean IoU is materially lower** (~0.76); weakest in-pack fold **LA_ESTRELLA_ACOM2 ~0.69**.
- Tobarra hard transfer is **KILL** (fresh IoU ~0.48). Do not reopen with same recipe thrash.
- ECE post-hoc / logistic refit on the **same** U1 TEST holdout **did not** improve TEST ECE (~0.153). Freeze stopped thrash.
- Selective / reject surface is already strong (VAL-locked thr ~0.795 → accepted IoU ~0.949; selective@80 ~0.903 beats random).
- Multihorizon **field_ops** work is orthogonal: it does **not** lift lab ML IoU. Dual rails stay dual.
- Next-gate recommended work item is **`W3_new_features_or_data`** — not more same-holdout calibration, not larger U-Net default, not Tobarra KEEP reopen.

**Why this design exists now:** metrics that can still move under protocol honesty are multi-fire generalization (LOFO mean + floor), not holdout ECE thrash or field fusion.

---

## 2. Goals and non-goals

### Goals (measurable)

| ID | Goal | Primary metric | Baseline | Target (success) | Floor (no-regress) |
|----|------|----------------|----------|------------------|--------------------|
| G1 | Raise multi-fire LOFO mean mask IoU | `model_iou_mean` on LOFO board (3 in-pack folds unless board protocol expands) | **0.7581** | **≥ 0.780** (+~0.022) | ≥ 0.750 |
| G2 | Raise weakest-fold floor | `model_iou_min` / `weakest_iou` (today LA_ESTRELLA_ACOM2) | **0.6932** | **≥ 0.720** | ≥ 0.690 |
| G3 | Preserve Δ vs copy honesty | per-fold `improvement_vs_copy_iou` | all beat copy; mean Δ ~0.301 | all folds still beat copy; mean Δ not worse by >0.02 | n_beats_copy = n_folds |
| G4 | Holdout U1 secondary no-silent-regress | U1 TEST mean IoU (`docs/ML_PRODUCT_SCORECARD.json` primary) | **0.8569** | report; **champion/PR4** only if ≥ baseline − **0.01** | ≥ 0.8469 |
| G5 | Keep reject surface protocol-clean | VAL-locked thr; TEST accepted IoU | thr **~0.795**; acc IoU **~0.949** | thr unchanged unless new VAL-only retune with new scorecard id | thr not fit on TEST/LOFO |

**Primary north star:** G1 + G2. G4 is a **required secondary gate** on any recipe that ships as a candidate lab champion member (PR4 recipe path).

### Two-tier success contract (KEEP member ≠ north-star close)

Implementers must not treat `CLOSED_KEEP` as “design done.”

| Tier | Name | When | Requirements | May PR4? |
|------|------|------|--------------|----------|
| **T1** | **KEEP / promote member** | Single experiment E2/E3/E4 kill board | Experiment profile L-checks pass (see §4.5). Incremental win vs baseline; may still miss G1/G2. | Board numbers + research weights **yes**; **champion recipe only if** `champion_candidate=true` and L4 measured pass |
| **T2** | **North-star close** | Design / ladder success closed | **G1 and G2 both met** on core-3 board under same protocol as baselines; G3 holds; rails OK. May require stacking T1 KEEPs (e.g. E3a + E4). | Full close-out MD; recipe promote still needs L4 if champion path |

**Rules:**

1. `kill_verdict=KEEP` ⇒ T1 only. Stamp `north_star_g1_met` / `north_star_g2_met` booleans on every kill JSON (may be false while KEEP is true).
2. `design_success_closed=true` only when T2 (G1∧G2) is true — never auto-inferred from a single KEEP.
3. PR4 acceptance must name which tier: **board promote (T1)** vs **north-star closeout (T2)**.

### Non-goals (explicit)

- Multihorizon field_ops feature work; field fusion **ON**; ROS claims from IoU.
- ECE same-TEST thrash (iters 2–3 already failed; freeze sealed).
- Tobarra KEEP reopen with same recipe / KILL weights (`CLOSED_KILL`).
- Larger U-Net / ResNet-50 / Swin / SegFormer as **default** lab or field product (see `LAB_UNET_SCALE_KILL_CRITERIA.md`). Residual ~1M path stays default.
- Fitting reject thr / mix / temperature on TEST, LOFO held-out fire, or W3 external.
- Auto-flip `ml_product_go` or `field_ops.allow_ml_live_in_fusion`.
- Claiming catalog holdout **0.8963** as live certainty or as U1 eval mean.
- Treating CARDOSO LOFO as independent of U1 family (honesty note: CARDOSO ≈ holdout TEST family).
- NDWS v21 (~0.22 model_iou) replacing Spain champion without a separate research protocol id.

---

## 3. Current state

### Locked baselines (do not invent different numbers)

| Metric | Value | Source |
|--------|------:|--------|
| U1 TEST honest mean IoU | **0.8569** | `docs/ML_PRODUCT_SCORECARD.json` |
| U1 ECE | **~0.153** | same |
| Catalog holdout IoU (provenance only) | **0.8963** | catalog / scorecard provenance |
| Selective IoU @80% | **0.903** | beats random |
| Reject thr (locked iter1) | **~0.795** | lab_loop freeze / `ITER1_LOCKED_REJECT_THR` |
| Reject accepted IoU | **~0.949** | reject surface |
| LOFO mean IoU (3 folds) | **~0.758** | `lab_loop_v34_generalization_latest.json` / board |
| LOFO min | **~0.693** (LA_ESTRELLA_ACOM2) | same |
| Head A / pack LOFO mean | ~0.76 board; Tobarra Head A ~0.49 | MEMORY / Head A board |
| Tobarra LOFO KEEP | **KILL** (fresh IoU 0.478, K1 fail) | `tobarra_keep_or_kill_scorecard.json` `CLOSED_KILL` |
| NDWS v21 model_iou | **~0.223** | `outputs/kaggle_v21` |
| ml_product_go | true in scorecard (lab); field fusion **OFF** | dual rails — stamp from facade/scorecard, **not** stale `next_gate` JSON |
| Next gate recommended | **W3_new_features_or_data** | `lab_loop_v34_next_gate_latest.json` (work item id only; rails may be stale) |

### LOFO board (mask IoU protocol — not U1 Head A ECE)

| Fold | model_iou | Δ vs copy | Note |
|------|----------:|----------:|------|
| CARDOSO | 0.7978 | +0.156 | easy; ≈ U1 family |
| LA_ESTRELLA_ACOM1 | 0.7832 | +0.424 | mid |
| LA_ESTRELLA_ACOM2 | **0.6932** | +0.323 | **weakest floor** |
| **mean** | **0.7581** | **0.301** | n=3 in board |

Tobarra is **not** averaged into the 3-fold board mean used for G1; it remains hard-transfer stress (Head A ~0.49; KEEP **KILL**).

### W3 external (eval-only, frozen thr/cal) — already MET as probe

| Fire | Head A IoU | Δ vs copy | Role |
|------|-----------:|----------:|------|
| Hellín 2024 | ~0.79 | **+0.11** | best new-fire signal |
| Brazatortas 2025 | ~0.54 | ~0 | hard |
| Retuerta 2025 | ~0.47 | ~0.01 | hard probe |

W3 process goal is **MET** as *eval probes*. This design uses W3 material as **optional train-pool expansion only under kill criteria** — not thr/ECE fit on those fires.

### Champion recipe (frozen ensemble)

`models/clm_ensemble/loop_champion_recipe.json`:

- Members: `weights_v28_clm_ft.pt`, `weights_v30_ema.pt`, `weights_multi_if.pt`
- Mix VAL-only `[0.28, 0.32, 0.4]`; temps VAL-only
- Architecture default: residual small U-Net (~1M) via `unet_train` (`architecture="residual"`, `model="small"`)
- Feature reality: many legacy17 channels near-constant on CLM patches (`outputs/ml_eval/feature_signal_report.json`)
- Sealed holdout / LOFO packs on disk are **legacy17** NPZ (`n_channels=17`)

### Instrumentation already present

| Module / script | Role |
|-----------------|------|
| `wildfire_front/ml/lab_lofo_board.py` | LOFO scoreboard |
| `wildfire_front/ml/lab_lofo_head_a.py` | Head A multi-fire ECE/reject frozen |
| `wildfire_front/ml/lab_next.py` | next-gate readiness (`W3_new_features_or_data`) |
| `wildfire_front/ml/w3_signal.py` | inventory + multi-fire honesty |
| `wildfire_front/ml/product_facade.py` | dual rails, dead paths, rank/reject (**single rails source**) |
| `wildfire_front/ml/protocol_rails.py` | VAL-only thr; split roles |
| `wildfire_front/ml/feature_schema.py` | legacy17 / clean12 / physics14 / physics15 |
| `scripts/run_lab_ml_loop_v34_*.py` | loop iterations |
| `scripts/run_clm_lofo_all_folds.py` | LOFO retrain residual |
| `scripts/build_clm_lofo_splits.py` | LOFO pack rebuild |
| `scripts/analyze_feature_signal.py` | per-channel growth signal |
| `scripts/score_tobarra_kill_criteria.py` | K1–K5 sealed KILL |
| `docs/EXPERIMENT_TRACKER.md` | prior clean12/physics14/15 **NO PROMOTE** vs v21 |

### Immutable rails (design must not violate)

```
IoU ≠ ROS
field_ops fusion OFF
no ECE thrash on same U1 TEST
no Tobarra KEEP reopen (same recipe / KILL weights)
no larger U-Net/ViT as default
reject thr VAL-locked; no TEST thr fit
dual product: lab mask ≠ field multihorizon
ml_product_go never auto-flips
rails stamps: product_facade.DEFAULT_RAILS + scorecard only (not stale next_gate JSON)
```

---

## 4. Proposed design

### 4.1 Product surface (unchanged pipeline)

```
features → calibrator (VAL-fit, frozen) → rank/reject (iter1 thr ~0.795) → scorecard
```

All new experiments **report** through existing facades; they do not invent parallel thr math.

### 4.2 Metrics contract (what “improved” means)

Introduce a single machine-readable **metrics lift board** written by PR1:

**Path:** `outputs/ml_eval/lab_loop/lab_loop_v34_metrics_lift_latest.json`  
**Schema:** `wfd_ml_metrics_lift_board_v1`

```json
{
  "schema": "wfd_ml_metrics_lift_board_v1",
  "product_id": "clm_ensemble_v34",
  "product_rail": "lab_ml",
  "field_ops_allow_ml_live_in_fusion": false,
  "rails_source": "product_facade.DEFAULT_RAILS+scorecard",
  "baselines": {
    "lofo_mean_iou": 0.7580534465179306,
    "lofo_min_iou": 0.6931861844919686,
    "lofo_weakest_fold": "LA_ESTRELLA_ACOM2",
    "u1_test_mean_iou": 0.8568865373678947,
    "u1_ece": 0.15280955026564416,
    "reject_thr": 0.795,
    "reject_accepted_iou": 0.9492431452930816,
    "catalog_holdout_iou_provenance_only": 0.8963
  },
  "candidate": {
    "experiment_id": "E3a_hellin_train_pool",
    "champion_candidate": false,
    "lofo_mean_iou": null,
    "lofo_min_iou": null,
    "u1_test_mean_iou": null,
    "u1_status": "SKIPPED|MEASURED",
    "delta_lofo_mean": null,
    "delta_lofo_min": null,
    "delta_u1": null
  },
  "north_star": {
    "g1_met": false,
    "g2_met": false,
    "design_success_closed": false
  },
  "kill_verdict": "PENDING|KEEP|KILL|INCONCLUSIVE",
  "tier": "T1_KEEP_MEMBER|T2_NORTH_STAR|none",
  "rails_ok": true
}
```

**Measurement commands (canonical):**

```powershell
$env:PYTHONPATH = "."
# LOFO mask board (G1/G2)
python scripts/run_lab_ml_loop_v34_lofo_board.py
# or CLI:
python -m wildfire_front ml lofo --json

# Holdout U1 secondary (G4) — frozen cal, TEST report only
python scripts/eval_ml_uncertainty_u1.py   # existing path; do not retune thr

# Metrics lift board (PR1)
# --candidate-root: directory whose children are LOFO folds with evaluation_metrics.json
#   layout: {candidate-root}/{FOLD}/evaluation_metrics.json
#   OR pass a single LOFO board JSON via --candidate-board
python scripts/run_lab_ml_loop_v34_metrics_lift.py --candidate-root outputs/ml_eval/lofo_v1
python scripts/run_lab_ml_loop_v34_metrics_lift.py --baselines-only
```

**CLI flag contract (single name):**

| Flag | Meaning |
|------|---------|
| `--candidate-root` | Root dir with `{FOLD}/evaluation_metrics.json` children (canonical) |
| `--candidate-board` | Optional path to a pre-built LOFO board JSON instead of scanning folds |
| `--baselines-only` | Seal baselines; no candidate |

Do **not** use `--candidate-dir` (deprecated name; never ship).

**JSON paths to compare:**

| Surface | Path |
|---------|------|
| LOFO board latest | `outputs/ml_eval/lab_loop/lab_loop_v34_lofo_board_latest.json` |
| Generalization | `outputs/ml_eval/lab_loop/lab_loop_v34_generalization_latest.json` |
| Per-fold metrics | `outputs/ml_eval/lofo_v1/{FOLD}/evaluation_metrics.json` (or `lofo_v2/`, `lofo_schema_*`) |
| U1 scorecard | `docs/ML_PRODUCT_SCORECARD.json` |
| Metrics lift board | `outputs/ml_eval/lab_loop/lab_loop_v34_metrics_lift_latest.json` |
| Pack leak audit | `outputs/ml_eval/lab_loop/lofo_pack_leak_audit_latest.json` |
| Iteration MD | `docs/ML_LOOP_ITERATIONS/iter_metrics_lift_latest.md` |

### 4.3 Experiment ladder (ordered, kill-gated)

Run **in order**. Stop a branch on KILL; only promote weights/recipe that pass kill criteria. Prefer **features / data / protocol-clean retrain** before capacity.

#### E0 — Instrumentation + freeze baselines (no retrain)

**Purpose:** Make G1–G5 and T1/T2 measurable without thrash.

| Item | Detail |
|------|--------|
| Work | Metrics lift board writer; baseline seal; dead-path asserts; rails from `product_facade.DEFAULT_RAILS` + scorecard; CLI hook under `ml next` work item `W3_new_features_or_data` → substatus E0–E4 |
| Files | `wildfire_front/ml/lab_metrics_lift.py` (new), `scripts/run_lab_ml_loop_v34_metrics_lift.py`, tests |
| Train | none |
| Kill | N/A (infra) |
| Acceptance | Board writes with frozen baselines matching §3; rails field fusion OFF; refuses Tobarra KEEP reopen + same-TEST ECE thrash IDs via `refuse_dead_path`; does **not** copy rails from stale next_gate JSON |

#### E1 — Weak-fold diagnosis + feature signal (report only)

**Purpose:** Explain ACOM2 floor and constant-channel waste before any retrain.

| Item | Detail |
|------|--------|
| Work | Re-run `analyze_feature_signal.py` on LOFO train pools + ACOM2 test; fail-case stratification from `lab_loop_v34_fail_cases_test.json`; optional Head A IoU quantile buckets already in Tobarra diagnose pattern |
| Outputs | `outputs/ml_eval/lab_loop/metrics_lift_e1_signal.json` |
| Train | none |
| Kill | N/A |
| Acceptance | Document top 3 levers with evidence (e.g. constant channels, growth class imbalance, alignment quality) and map each to E2/E3/E4 |

**Default hypothesis from existing signal report:** multiple legacy17 channels have `frac_near_constant ≈ 1` and zero corr → prefer **schema cleanup / pack expansion** over capacity.

#### E2 — Feature schema / channel honesty (small train, residual default)

**Purpose:** Lift signal without larger backbone. **Cheap negative control** — escalate to E3a on KILL.

**Honesty (prior evidence):** Spain/NDWS tracker already recorded **clean12 (v23), physics14 (v25), physics15 (v26) as NO PROMOTE** vs v21 on full IoU (`docs/EXPERIMENT_TRACKER.md`). Do **one** LOFO protocol attempt per `schema_id`; on KILL do **not** thrash hyperparams — escalate to **E3a**.

##### E2 data path (mandatory — sealed packs are legacy17)

On-disk CLM holdout / `lofo_v1` packs are **legacy17** NPZ. `unet_train` derives `in_channels` from sample shape and does **not** currently take a schema flag. physics14 needs tmin/tmax + drought/FFMC at **channel-build** time, not a free subset of sealed tensors.

**Allowed paths (pick explicitly per run; record in training_summary):**

| Path id | What | When | Channel honesty |
|---------|------|------|-----------------|
| **E2-P1 subset projector** | Materialize `outputs/ml_eval/lofo_schema_clean12_subset/{FOLD}/{train,val,test}/*.npz` by **projecting** sealed legacy17 → clean12 via a **fixed channel map** in `wildfire_front/ml/feature_schema.py` (or thin `scripts/project_lofo_schema_packs.py`) | Default first E2 attempt | Drops near-constant channels only; **not** full physics14 (no true tmin/tmax split if source is single temp + constants) |
| **E2-P2 re-emit** | Re-build LOFO train/val/test under `artifacts/clm_ndws_patches/lofo_schema_{schema}/` via schema-aware builder from geotiff/source fields (`preprocess` / patch pipeline with `--schema physics14`) | Only if E2-P1 KEEP is interesting **or** E1 proves constants are not the bottleneck and true meteo channels exist | Full physics14/15; expensive |
| **E2-P3 demote** | Skip physics14 train on sealed packs; document BLOCKED without re-emit | If neither P1 nor P2 is funded | Honest non-run |

**Forbidden:** Claiming “physics14 LOFO” while feeding unmapped legacy17 tensors; init residual weights when `in_channels` mismatches without re-init.

**training_summary must record:**

```json
{
  "feature_schema": "clean12_subset|physics14|physics15|legacy17",
  "schema_path_id": "E2-P1|E2-P2",
  "in_channels": 13,
  "init_weights_path": "...",
  "init_weights_channel_match": true
}
```

Init weights only when channel count matches; else train from same NDWS init path with matching schema or random residual init disclosed.

| Variant | Description |
|---------|-------------|
| E2a | **Default:** E2-P1 clean12_subset residual small LOFO (same fold ids as lofo_v1) |
| E2b | E2-P2 physics14/15 re-emit LOFO **only if** E2a ran once and either KEEP or E1 demands true meteo |
| E2c | Alignment / prev_fire quality audit: re-emit patches only if chain alignment bugs found |

**Protocol:**

- **VAL-only** early stop on `improvement_vs_copy_iou` (existing LOFO pattern).
- Evaluate LOFO folds with projected/re-emitted test folders (no thr fit).
- Do **not** retune ensemble mix/temps until E2 candidate exists; optional mix re-fit is **VAL-only** and requires new recipe id.
- **Stop rule:** one attempt per `schema_id` + path id; KILL → E3a.

**Kill profile:** `profile=E2` → S1–S6 (see §4.5.1). KEEP = T1 only unless G1∧G2 also met.

#### E3 — Multi-fire data expansion (W3 material as train pool — primary bet)

**Purpose:** Address single-holdout overclaim by adding **new fire diversity** into train pools for LOFO, without claiming Tobarra KEEP.

| Variant | Description |
|---------|-------------|
| E3a | Add **Hellín 2024** patches (`outputs/ml_eval/w3/hellin_2024/patches`) into multi-source pack; rebuild LOFO so when holding out Estrella/Cardoso, Hellín is in train; when holding out a new Hellín fold, report separately. **Hellín may be train-pool-only** (no LOFO fold) if test patches below 50 — see D3 applicability |
| E3b | Conditionally add Brazatortas/Retuerta **only if** Δ vs copy on frozen Head A remains non-negative **and** growth class not pure noise after min_change filter |
| E3c | Cardoso extra LWIR sequences only after **non-overlap audit** with CLM CARDOSO pack (leak audit required) |

**Pack rebuild path:**

1. Materialize NPZ with locked feature schema (prefer same schema as winning E2 if KEEP; else **legacy17** for continuity with sealed champion).
2. Extend multi-source layout under new root e.g. `artifacts/clm_ndws_patches/holdout_v1_plus_w3/` — **do not overwrite** sealed holdout_v1.
3. `build_clm_lofo_splits.py --src-root ... --out-root artifacts/clm_ndws_patches/lofo_v2/` → train under `outputs/ml_eval/lofo_v2/`.
4. **Leak audit (L5 source of truth):** `scripts/audit_lofo_pack_leak.py --lofo-root artifacts/clm_ndws_patches/lofo_v2` writes `outputs/ml_eval/lab_loop/lofo_pack_leak_audit_latest.json` with per-fold `n_leaked_train_val` by held-out `source` id (must be 0). Pack builder may also embed the same counts; scorer **reads** this JSON for L5.
5. Train residual LOFO folds via generalized `run_clm_lofo_all_folds.py` (config: residual small, composite loss, same early stop).
6. Recompute LOFO board; **never** include Tobarra KEEP reopen as success criterion.

**Board law for expanded LOFO:**

- Report **core-3 mean** (Cardoso, ACOM1, ACOM2) as G1 primary for comparability.
- Report **expanded mean** separately (core-3 + Hellín LOFO, etc.) as research — only when a proper new-fire held-out fold exists.
- Tobarra stays stress-only; success ≠ Tobarra IoU > 0.49.

**D3 new-fire fold applicability (KEEP gate — original “if any” restored):**

```
D3_applicable = expanded board has a held-out new-fire fold
                (source ∉ {CARDOSO, LA_ESTRELLA_ACOM1, LA_ESTRELLA_ACOM2, tobarra_20240802})
                with n_test ≥ 50 (and min_change≥0.02 protocol)
```

| `D3_applicable` | `profile_extra.D3` | Effect on E3 KEEP |
|-----------------|--------------------|-------------------|
| **false** (Hellín train-pool-only; n_test below 50; fold not built; eval-only probe) | `status: SKIPPED`, `pass: null` — **not FAIL** | Does **not** block KEEP; core-3 L1/L2 still decide |
| **true** (proper new-fire LOFO fold present) | MEASURED; require `improvement_vs_copy_iou ≥ +0.05` | FAIL → KILL if Δ below +0.05 |

Scorer must not invent a Hellín fold when none exists, and must not skip D3 when a qualifying fold is on the expanded board.

**Kill profile:** `profile=E3` → D1–D7 mapped to L* (see §4.5); D3 uses applicability above.

#### E4 — Selective / curriculum training for weak fold (no thrash)

**Purpose:** Raise ACOM2 floor without fitting on ACOM2 test.

| Item | Detail |
|------|--------|
| Idea | Weight sampling / change-loss toward **growth pixels** and **hard sources in train** when ACOM2 is held out (ACOM2 never seen in train by LOFO definition) |
| Levers already in `unet_train` | `change_loss_weight`, `weighted_sampler`, `pos_weight`, `target_mode="delta"` |
| Forbidden | Upsampling ACOM2 test into train; thr fit on ACOM2 test; claiming LOFO when test leaked |

**Kill profile:** `profile=E4` → C1–C3 + L5–L9 (see §4.5.1). C1 targets floor **0.720** (G2-aligned for this experiment’s purpose).

#### E5 — Ensemble recipe refresh (VAL-only, after a KEEP member)

**Purpose:** Only if E2/E3/E4 produce a **KEEP** member weight with `champion_candidate=true`.

| Item | Detail |
|------|--------|
| Work | VAL-only mix/temperature scan like historical v34 path; **never** fit on TEST |
| New recipe id | e.g. `source_mix_val_temp_calibrated_metrics_lift_v1` under `models/clm_ensemble/` |
| Kill | L4 **required MEASURED**; U1 TEST mean IoU ≥ 0.8569 − **0.01**; selective still beats random; reject thr remains VAL-locked (iter1 default unless VAL proves new thr with new freeze id) |
| Non-goal | ECE must-drop; do not thrash ECE as promotion criterion |

#### E6 — Optional external NDWS protocol (research only)

| Item | Detail |
|------|--------|
| When | Only if Spain LOFO still stuck after E2–E4 KILL |
| Rule | Separate protocol id; cannot thrash Spain champion; NDWS ~0.22 is **not** a promote path |
| Kill | Any attempt to set field fusion from NDWS → refuse |

### 4.4 Recommended execution order (defaults)

```
E0 (instrument) → E1 (diagnose) → E2a E2-P1 clean12_subset (one shot)
  → if KEEP (T1): optional E5 only if champion_candidate
  → if KILL or miss G1/G2: E3a (Hellín train-pool LOFO v2) as primary EV
  → if mean OK but floor short: E4 curriculum (stack toward T2)
  → design_success_closed only when G1∧G2
  → E6 only if stuck
```

**Default bet:** E3a multi-fire data is the highest-EV lift for G1/G2 given next_gate = `W3_new_features_or_data` and Hellín’s +0.11 Δ vs copy. E2a is a **single-shot negative control**, not a thrash loop.

### 4.5 Kill criteria master template (Tobarra K-style + profiles)

Every train experiment writes:

`outputs/ml_eval/lab_loop/metrics_lift_{experiment_id}_kill.json`

#### 4.5.1 Single L2 floor rule + north-star report fields

**One KEEP boolean for floor:**

```
L2_pass  = (lofo_min_iou >= 0.700)     # hard KEEP gate — only this decides KEEP/KILL for floor
L2_target_met = (lofo_min_iou >= 0.720) # north-star G2 report only — does NOT alone decide KEEP
```

Scorer tests assert: `verdict` uses **L2_pass** only for L2; never OR/AND with 0.720 for KEEP.

Exception **E4 profile only:** C1 uses floor **0.720** as KEEP gate for that experiment (mapped to L2 with `threshold: 0.720` and `profile: E4`).

#### 4.5.2 L4 U1 secondary (never default pass)

| Case | `u1_status` | L4 `pass` | KEEP allowed? |
|------|-------------|-----------|---------------|
| U1 not evaluated; `champion_candidate=false` | `SKIPPED` | **null / not true** — status `SKIPPED`, **not** pass | Yes for **research board T1** only |
| U1 not evaluated; `champion_candidate=true` or PR4 recipe path | missing | **false** (hard fail) | **No KEEP** for promote path |
| U1 measured | `MEASURED` | `u1_iou >= 0.8569 - 0.01` (**−0.01** only; aligned G4/D6) | If other L* pass |

**Aligned U1 regress threshold:** always **baseline − 0.01** (0.8469) for any MEASURED L4. Do **not** use −0.015. Incomplete runs never stamp L4 `pass: true`.

#### 4.5.3 Master JSON shape

```json
{
  "schema": "wfd_ml_metrics_lift_kill_v1",
  "experiment_id": "E3a_hellin_train_pool",
  "profile": "E2|E3|E4|E5",
  "champion_candidate": false,
  "verdict": "KEEP|KILL|INCONCLUSIVE",
  "tier": "T1_KEEP_MEMBER",
  "north_star_g1_met": false,
  "north_star_g2_met": false,
  "design_success_closed": false,
  "checks": {
    "L1_lofo_mean_lift": {"pass": false, "delta": 0.0, "threshold": 0.015, "value_mean": 0.0},
    "L2_weak_floor": {
      "pass": false,
      "value": 0.0,
      "threshold": 0.70,
      "L2_pass": false,
      "L2_target_met": false,
      "note": "KEEP uses L2_pass (min>=0.700) only; L2_target_met is G2 report"
    },
    "L3_all_beat_copy": {"pass": true},
    "L4_u1_no_silent_regress": {
      "pass": null,
      "status": "SKIPPED|MEASURED|REQUIRED_MISSING",
      "delta_u1": null,
      "threshold": 0.01,
      "champion_candidate": false
    },
    "L5_zero_leak": {"pass": true, "n_leaked_train_val": 0, "audit": "outputs/ml_eval/lab_loop/lofo_pack_leak_audit_latest.json"},
    "L6_no_test_thr_ece": {"pass": true},
    "L7_no_field_rails": {"pass": true, "field_ops_allow_ml_live_in_fusion": false},
    "L8_no_tobarra_keep_claim": {"pass": true},
    "L9_residual_default": {"pass": true, "larger_unet_default": false}
  },
  "profile_extra": {
    "D3": {
      "applicable": false,
      "status": "SKIPPED|MEASURED",
      "pass": null,
      "delta_vs_copy": null,
      "threshold": 0.05,
      "n_test": null,
      "fold": null,
      "note": "SKIPPED when no new-fire LOFO fold with n_test>=50; MEASURED requires delta_vs_copy>=0.05"
    }
  },
  "status": "OPEN|CLOSED_KEEP|CLOSED_KILL|INCONCLUSIVE"
}
```

**KEEP (T1)** requires all **applicable** L* for the profile with `pass: true`. L4 with `status=SKIPPED` and `champion_candidate=false` is **exempt** (not counted as pass). Incomplete train → **INCONCLUSIVE** or KILL, never KEEP.

**T2 / design_success_closed:** `north_star_g1_met && north_star_g2_met` (mean ≥ 0.780 and min ≥ 0.720) independent of whether a single experiment’s L1 threshold was only +0.015.

#### 4.5.4 Experiment → check profile table

| Profile | Mean lift (L1) | Floor (L2) | Extra KEEP checks | Rails L5–L9 |
|---------|----------------|------------|-------------------|-------------|
| **E2** (S1–S6) | Δ mean ≥ **+0.010** | L2_pass min ≥ **0.700** | S3=L3; S4→L4 if champion else SKIPPED OK; S6=L9 | L5–L9 hard |
| **E3** (D1–D7) | Δ mean ≥ **+0.015** (core-3) | L2_pass min ≥ **0.700** | **D3 if applicable:** new-fire LOFO fold with `n_test ≥ 50` → Δ vs copy ≥ **+0.05**; if not applicable → `profile_extra.D3.status=SKIPPED` (not fail, does not block KEEP). D6→L4 MEASURED if champion | L5–L9 hard |
| **E4** (C1–C3) | mean ≥ baseline − **0.005** (no free collapse) as L1 with `threshold_mode: no_regress_0.005` | **L2 threshold 0.720** (C1) | C2: CARDOSO & ACOM1 each ≥ baseline_fold − 0.02 in `profile_extra.C2_fold_stability` | L5–L9 hard |
| **E5** | optional small | L2_pass | L4 **required MEASURED** (−0.01) | L5–L9 hard |

All profiles serialize into the same kill JSON; tests cover each profile’s predicate — including **both D3 branches** (SKIPPED when train-pool-only / n_test below 50; MEASURED when fold present).

#### 4.5.5 Per-experiment threshold recap

| ID | Rule | Threshold |
|----|------|-----------|
| S1 / E2 L1 | LOFO mean lift vs 0.7581 | ≥ **+0.010** else KILL |
| S2 / E2 L2 | Weakest fold | **L2_pass** min ≥ **0.700** |
| D1 / E3 L1 | Core-3 LOFO mean lift | ≥ **+0.015** else KILL |
| D2 / E3 L2 | Core-3 min | **L2_pass** ≥ **0.700**; report L2_target_met for 0.720 |
| D3 / E3 extra | New-fire LOFO Δ vs copy | **If applicable** (`n_test ≥ 50` held-out new-fire fold): ≥ **+0.05** else KILL. **If not applicable** (train-pool-only / thin patches / no fold): **SKIPPED** — does not block KEEP |
| C1 / E4 L2 | ACOM2 floor | ≥ **0.720** |
| C2 | CARDOSO, ACOM1 | each within −0.02 of fold baseline |
| U1 L4 | MEASURED | ≥ **0.8569 − 0.01** |
| L5 | leak | `n_leaked_train_val == 0` from `audit_lofo_pack_leak.py` |

### 4.6 Expected scorecard deltas (honest ranges — not promises)

| Experiment | Likely LOFO mean Δ | Likely weak floor Δ | U1 | Notes |
|------------|-------------------:|--------------------:|----|-------|
| E0/E1 | 0 | 0 | 0 | instrumentation |
| E2a subset | +0.00 to +0.02 | +0.00 to +0.02 | SKIPPED or ±0.01 | prior clean12/physics14 NO PROMOTE; one shot then E3a |
| E3a Hellín pool | **+0.01 to +0.04** | **+0.01 to +0.03** | ±0.01 | primary EV; may still need E4 for G2 0.720 |
| E4 curriculum | 0 to +0.02 mean | **+0.02 to +0.04** floor | ~0 | stack toward T2 |
| E5 mix | small | small | MEASURED ±0.005 | only after KEEP member + champion path |
| Larger U-Net | forbidden as default | — | — | PR11 kill criteria |

Do **not** promise Tobarra KEEP, ECE drop, or single-shot G1∧G2 from E2 alone.

### 4.7 CLI / lab loop integration

| Command | Behavior after this design |
|---------|----------------------------|
| `python -m wildfire_front ml next` | `recommended_next` stays `W3_new_features_or_data` until T2 or human idle; expose sub-items E0–E4 readiness |
| `python -m wildfire_front ml lofo` | Prefer `lofo_v2` board if present + flag; always print core-3 vs expanded; print G1/G2 met flags |
| `python -m wildfire_front ml freeze` | unchanged rails; metrics lift does not unfreeze field |
| New | `python scripts/run_lab_ml_loop_v34_metrics_lift.py --candidate-root ...` |
| New | `python scripts/audit_lofo_pack_leak.py --lofo-root ...` |
| New | `python scripts/project_lofo_schema_packs.py --schema clean12 --src-lofo artifacts/.../lofo_v1` (E2-P1) |

---

## 5. Alternatives considered

| Alternative | Trade-off | Verdict |
|-------------|-----------|---------|
| More ECE / Platt on same U1 TEST | Already failed iters 2–3; freeze sealed | **Reject** |
| Tobarra KEEP reopen same recipe | Fresh IoU 0.478; K1 fail; CLOSED_KILL | **Reject** |
| Larger U-Net / Swin default | Cost/latency; PR11 kill; capacity ≠ LOYO win | **Reject as default**; optional research only under `LAB_UNET_SCALE_KILL_CRITERIA.md` |
| Field multihorizon to lift IoU | Impact audit: does not lift lab IoU; dual rails | **Out of scope** |
| NDWS as primary champion | model_iou ~0.22; different domain | **Research only** |
| Single-holdout hyperparam thrash | Inflates U1; widens U1−LOFO gap | **Reject** |
| **Features + multi-fire data + residual retrain** | Higher engineering cost; protocol-clean; targets G1/G2 | **Accept (this design)** |
| Selective reject thr retune on VAL | Surface already strong; low EV for LOFO mask IoU | Defer; keep iter1 thr |
| Raise E3 KEEP bars to full G1/G2 in one shot | May KILL useful incremental members; slower learning | **Reject** — use T1/T2 split instead |

---

## 6. Risks / honesty rails

| Risk | Mitigation |
|------|------------|
| Protocol inflation (new thr/mix silent) | New scorecard / recipe id; VAL-only; L6 kill |
| Treating expanded LOFO mean as core-3 | Dual report: core-3 primary for G1 |
| CARDOSO ≈ U1 double-count | Honesty notes on board; do not sell as independent gen |
| Hellín leak into holdout TEST | Separate pack root `holdout_v1_plus_w3`; never mutate sealed holdout_v1; L5 audit script |
| Claiming IoU as ROS / field readiness | Dual rails in every JSON; field fusion OFF |
| ECE thrash temptation after weak lift | Dead path refuse; freeze surface `iter1_reject_only` |
| Tobarra KEEP claim after any retrain | Scorer + `refuse_dead_path`; L8 |
| Overfitting curriculum to ACOM2 train proxies | LOFO holds ACOM2 out; C2 fold stability |
| Catalog 0.8963 sold as live | Provenance-only field in scorecard |
| CLOSED_KEEP sold as G1/G2 done | T1 vs T2 contract; `design_success_closed` only on G1∧G2 |
| physics14 on legacy17 silent mismatch | E2-P1/P2/P3 explicit paths; training_summary schema fields |
| Stale next_gate `ml_product_go: false` thrash | Rails from facade + scorecard only |
| E2 thrash after known NO PROMOTE | One shot per schema_id; escalate E3a |

---

## 7. Testing plan

### Unit / contract (CI-friendly)

| Test | Asserts |
|------|---------|
| `tests/test_lab_metrics_lift.py` (new) | baselines seal; delta math; T1 vs T2; L2_pass vs L2_target_met; L4 SKIPPED ≠ pass; dead paths refuse |
| `tests/test_lab_metrics_lift_kill_profiles.py` (new) | E2/E3/E4/E5 profile predicates; incomplete train ≠ KEEP |
| `tests/test_lab_lofo_board.py` (extend) | core-3 vs expanded keys; weakest fold |
| `tests/test_lab_next.py` (extend) | W3 work item lists E0–E4; no Tobarra reopen READY |
| `tests/test_lofo_pack_leak.py` (new) | synthetic leak → n_leaked > 0; clean pack → 0 |
| `tests/test_project_lofo_schema.py` (new) | legacy17→clean12 channel count; honesty fields |
| Existing freeze/smoke/rails | still green; fusion OFF |

### Integration (local GPU/CPU)

```powershell
$env:PYTHONPATH = "."
pytest tests/test_lab_metrics_lift.py tests/test_lab_metrics_lift_kill_profiles.py tests/test_lab_lofo_board.py tests/test_lab_next.py tests/test_lofo_pack_leak.py -q
python scripts/run_lab_ml_loop_v34_metrics_lift.py --baselines-only
# After a train experiment:
python scripts/run_lab_ml_loop_v34_lofo_board.py
python scripts/run_lab_ml_loop_v34_metrics_lift.py --candidate-root outputs/ml_eval/lofo_v2
python scripts/audit_lofo_pack_leak.py --lofo-root artifacts/clm_ndws_patches/lofo_v2
```

### Acceptance for “metrics improved”

| Claim | Required |
|-------|----------|
| T1 KEEP member | kill_verdict KEEP; profile L* pass; north_star flags honest (may be false) |
| T2 design success closed | G1 ∧ G2 on core-3; G3; rails OK |
| Champion / recipe PR4 | T1 or T2 + L4 MEASURED pass (−0.01) + human gate |
| Incomplete train | INCONCLUSIVE or KILL — never KEEP |

### Smoke rails (always)

- `python -m wildfire_front ml smoke`
- `python -m wildfire_front ml freeze` still lab_usable; field OFF

---

## 8. Key Decisions

| # | Decision | Default |
|---|----------|---------|
| KD1 | North star is **LOFO mean + weak-fold floor**, not U1 ECE | Locked |
| KD2 | Residual ~1M remains default architecture | Locked (PR11) |
| KD3 | Primary data bet is **Hellín-in-train-pool (E3a)** after cheap one-shot E2a | Locked |
| KD4 | Comparability board = **core-3** (Cardoso, ACOM1, ACOM2); expanded mean secondary | Locked |
| KD5 | Tobarra is stress-only; KEEP reopen forbidden | Locked |
| KD6 | Reject thr stays **iter1 ~0.795** unless new VAL freeze id | Locked |
| KD7 | New packs under `lofo_v2` / `holdout_v1_plus_w3` / `lofo_schema_*` — never mutate sealed holdout_v1 | Locked |
| KD8 | **T1 KEEP:** L1 profile-specific; **L2_pass = min ≥ 0.700** (E4: 0.720). **T2 close:** mean ≥ **0.780** and min ≥ **0.720**. L2_target_met is report-only for non-E4 | Locked |
| KD9 | Field fusion stays **OFF**; multihorizon out of scope for this design | Locked |
| KD10 | Champion/recipe promote is human-gated PR4 only after KEEP + L4 MEASURED | Locked |
| KD11 | ECE improvement is **not** a success criterion for this ladder | Locked |
| KD12 | E2 default = **E2-P1 clean12_subset projector**; physics14 only via **E2-P2 re-emit**; one shot per schema_id | Locked |
| KD13 | U1 L4 threshold always **−0.01** when MEASURED; SKIPPED ≠ pass; required on champion path | Locked |
| KD14 | CLI flag is **`--candidate-root`** only | Locked |
| KD15 | Rails stamps from **product_facade + scorecard**, not stale next_gate JSON | Locked |
| KD16 | E3 **D3** applicable only if new-fire LOFO fold with `n_test ≥ 50`; else SKIPPED (not FAIL) | Locked |

---

## 9. Open Questions

Prefer resolved defaults so implementation can proceed. Residual questions (non-blocking):

| Q | Resolution (default) |
|---|----------------------|
| Include ACOM1/ACOM2 as separate sources vs merged Estrella? | **Keep separate folds** (current board law) |
| Hellín LOFO fold count / min patches? | Require ≥50 test patches with min_change≥0.02 to be a **KEEP-gated fold** (D3 applicable); else train-pool-only / eval-only and **D3 SKIPPED** |
| Should metrics lift flip `ml_product_go`? | **No** — human promote separate |
| CPU-only train acceptable? | Yes for smoke epochs / PR3a; full KEEP (PR3b) needs same device class as prior LOFO or disclose |
| Raise single-experiment KEEP to full G1/G2? | **No** — T1/T2 split (Issue 1 resolution) |

No open questions block PR1–PR2.

---

## 10. PR Plan

Incremental, ordered. Do not merge train promote before instrumentation.

### PR1 — Instrumentation: metrics lift board + kill schema

| Field | Content |
|-------|---------|
| **Title** | `lab(ml): metrics lift board + kill schema (E0)` |
| **Deps** | none |
| **Files** | `wildfire_front/ml/lab_metrics_lift.py` (new); `scripts/run_lab_ml_loop_v34_metrics_lift.py` (new); `wildfire_front/ml/lab_next.py` (W3 sub-items E0–E4 readiness); `tests/test_lab_metrics_lift.py` (new); optional `docs/ML_LOOP_ITERATIONS/iter_metrics_lift_baseline.md` |
| **Description** | Seal baselines from existing LOFO board + U1 scorecard; write `lab_loop_v34_metrics_lift_latest.json` with T1/T2 fields; assert dead paths; rails from facade+scorecard. CLI: `--candidate-root`, `--baselines-only`, optional `--candidate-board`. No retrain. |
| **Acceptance** | (1) `--baselines-only` produces JSON with LOFO mean **0.7581**, min **0.6932**, U1 **0.8569**; (2) pytest green including L2_pass vs L2_target_met and L4 SKIPPED; (3) `ml next` still recommends `W3_new_features_or_data` with E0 DONE; (4) rails field fusion OFF; (5) flag name is `--candidate-root` only |

### PR2 — Feature/data path: signal + schema project + W3 pack + leak audit

| Field | Content |
|-------|---------|
| **Title** | `lab(ml): schema project + W3 pack builder + leak audit (E1/E2/E3 prep)` |
| **Deps** | PR1 |
| **Files** | `scripts/analyze_feature_signal.py` (LOFO multi-root); `scripts/project_lofo_schema_packs.py` (new, E2-P1); `scripts/build_clm_lofo_splits.py` (`--src-root` / `--out-root`); `scripts/build_holdout_v1_plus_w3.py` (new or thin wrapper); `scripts/audit_lofo_pack_leak.py` (new — L5 producer); `wildfire_front/ml/feature_schema.py` (channel map for subset projector); optional schema flag on `UNetTrainConfig` / dataloader; `tests/test_project_lofo_schema.py`, `tests/test_lofo_pack_leak.py`; docs honesty (E2 NO PROMOTE prior) |
| **Description** | E1 report; E2-P1 projector from sealed legacy17 → clean12_subset under `lofo_schema_clean12_subset/`; ability to build `holdout_v1_plus_w3` + `lofo_v2` without mutating holdout_v1; leak audit JSON for L5. |
| **Acceptance** | (1) E1 JSON written; (2) dry-run pack build lists sources including hellin_2024 when patches present; (3) `audit_lofo_pack_leak.py` dry-run writes `lofo_pack_leak_audit_latest.json` with `n_leaked_train_val`; (4) projector produces declared `feature_schema` + `in_channels` in a sample training_summary stub; (5) no champion weight changes; (6) tests green |

### PR3a — Train harness + kill scorer + smoke (CI-mergeable)

| Field | Content |
|-------|---------|
| **Title** | `lab(ml): metrics-lift kill scorer + LOFO train harness (PR3a CI)` |
| **Deps** | PR2 |
| **Files** | `scripts/run_clm_lofo_all_folds.py` (configurable roots/schema/summary fields); `scripts/score_metrics_lift_kill_criteria.py` (new, profiles E2/E3/E4/E5, L1–L9); `tests/test_lab_metrics_lift_kill_profiles.py`; optional smoke 1-epoch dry-run behind `--smoke` |
| **Description** | Scorer + harness only. No requirement for full multi-epoch core-3 retrain to merge. Incomplete train fixtures assert INCONCLUSIVE/KILL not KEEP. E3 D3 applicability: SKIPPED vs MEASURED both unit-tested. |
| **Acceptance** | (1) kill scorer unit tests for all profiles; (2) L4 SKIPPED/REQUIRED_MISSING cases; (3) L2_pass vs L2_target_met; (4) incomplete train ≠ KEEP; (5) **D3 SKIPPED when not applicable does not block KEEP**; **D3 MEASURED requires Δ ≥ +0.05**; (6) field fusion OFF; (7) optional `--smoke` path exits 0 without KEEP claim |

### PR3b — Offline full LOFO run + kill stamp (artifact / lab iteration)

| Field | Content |
|-------|---------|
| **Title** | `lab(ml): offline LOFO E2a/E3a run + kill stamp (PR3b artifacts)` |
| **Deps** | PR3a |
| **Files** | outputs under `outputs/ml_eval/lofo_schema_*` / `lofo_v2/`; kill JSON under lab_loop; metrics lift board deltas; iteration MD draft |
| **Description** | Full residual LOFO for E2a then E3a (as scheduled). Score KEEP/KILL. **Do not** update champion recipe here. |
| **Acceptance** | (1) Full core-3 eval board for candidate; (2) kill JSON KEEP\|KILL\|INCONCLUSIVE with T1/T2 flags; (3) metrics lift board filled; (4) L5 audit attached when pack is lofo_v2; (5) U1 only if champion_candidate |

### PR4 — Board promote: LOFO board + optional recipe (human-gated)

| Field | Content |
|-------|---------|
| **Title** | `lab(ml): promote metrics-lift board (human-gated T1/T2)` |
| **Deps** | PR3b with **KEEP** (T1) and/or G1∧G2 (T2) |
| **Files** | `lab_loop_v34_lofo_board_latest.json`; generalization latest; `docs/ML_LOOP_ITERATIONS/iter_metrics_lift_latest.md`; if champion: recipe with **new id** + L4 MEASURED; scorecard only if U1 re-eval human OK; **never** flip field fusion |
| **Description** | Explicitly state promote tier: **T1 board promote** vs **T2 north-star closeout**. Champion update only if `champion_candidate` KEEP + L4 MEASURED + human review. |
| **Acceptance** | (1) Board MD shows core-3 mean/min vs baselines + `g1_met`/`g2_met`/`design_success_closed`; (2) KEEP kill JSON linked; (3) PR description names T1 vs T2; (4) honesty rails unchanged; (5) if no KEEP, docs-only KILL close-out |

### PR dependency graph

```
PR1 (instrument)
  └── PR2 (schema project + pack + leak audit)
        └── PR3a (harness + kill scorer, CI)
              └── PR3b (offline full LOFO + kill stamp)
                    └── PR4 (promote T1 board / T2 close / optional recipe)  [requires KEEP or honest KILL docs]
```

### Out-of-scope PRs (do not open under this design)

- Multihorizon field_ops fusion unlock
- Tobarra KEEP retrain thrash
- ECE same-TEST post-hoc
- Res50/Swin as default product

---

## Appendix A — File map (implementation anchors)

| Path | Role |
|------|------|
| `wildfire_front/ml/product_facade.py` | rails, dead paths, rank/reject (**rails source**) |
| `wildfire_front/ml/protocol_rails.py` | VAL-only thr; split actions |
| `wildfire_front/ml/lab_lofo_board.py` | LOFO scoreboard |
| `wildfire_front/ml/lab_next.py` | next gate |
| `wildfire_front/ml/w3_signal.py` | external inventory |
| `wildfire_front/ml/feature_schema.py` | clean12/physics14/15 + subset map |
| `wildfire_front/ml/unet_train.py` | residual train loop |
| `models/clm_ensemble/loop_champion_recipe.json` | frozen mix |
| `outputs/ml_eval/lofo_v1/*/evaluation_metrics.json` | baseline folds |
| `outputs/ml_eval/w3/hellin_2024/patches/` | E3a source |
| `docs/EXPERIMENT_TRACKER.md` | clean12/physics14 NO PROMOTE |
| `docs/design/LAB_UNET_SCALE_KILL_CRITERIA.md` | capacity kill |
| `docs/design/DESIGN_ML_LAB_LOOP_CONTINUOUS.md` | lab loop context (rails may be stale) |

## Appendix B — One-liner

**Lift multi-fire LOFO mean and ACOM2 floor via instrumentation → one-shot schema subset (or re-emit) → Hellín-inclusive data pack → residual retrain with profiled L1–L9 kill criteria; T1 KEEP is incremental, T2 closes only when G1∧G2; leave ECE thrash, Tobarra KEEP, larger U-Net default, and field fusion alone.**
