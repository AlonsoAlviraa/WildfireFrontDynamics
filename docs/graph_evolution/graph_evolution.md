# Graph Evolution Log — WildfireFrontDynamics

## 2026-08-04 — c5 → **v6.1** (plans + full research corpus)

**Trigger:** (1) Fuse plan post-O1 + reunión + industry → v6. (2) Expand with **all researchs** (mega SOTA, SOTA stack Lampman/Orion, fuel corpus, fire intel, CN, research/*).

**Decision:** Graph **v6.1** — human M3.2 primary; E1–E3 evidence stack; track **R-*** research-backed; critical-path research = **citations + UQ rails only** (not retrain); **0 h ML retrain** this month; horizon → **2026-09-04**.

| Node | v5 | v6 | v6.1 |
|------|----|-----|------|
| Human demo | PRIMARY | PRIMARY | PRIMARY |
| Eng evidence | missing | E-P0 | E-P0 |
| Research | lit workflow | thin | **R-P0/P1 + RESEARCH_TO_GRAPH map** |
| Industry | none | I-CAL | I-CAL |
| ML retrain | risk | killed | **0 h success metric** |

**Shipped:**  
- `docs/PLAN_1_MES_GRAPH_V6_IMPLEMENT.md` (v6.1)  
- `docs/fire_intel/RESEARCH_TO_GRAPH_V6_MAP.md`  
- `docs/PLAN_1_MES_GRAPH_V6_STATUS.json`  
- `.grok/graph_engineering/STATE.md` **v6.1**  
- `docs/graph_evolution/cycle_c5_graph_v6_implement.md`

**Rails held:** GO_MES true · fusion OFF · Lampman ≠ SLA · no EVAC labels · no invent Vp · no GO_Q without acta.

**Next:** 72 h E3→E1→E2(+R-UQ1,R-STACK-L) + R-DATA1 catalog; human demo schedule.

---

## 2026-08-04 — c5 → **v6** implement (evidence + third parties) *[superseded by v6.1 same day]*

**Trigger:** Fuse plan post-O1 + reunión senior + industry research into 1-month graph plan.  
**Superseded by:** v6.1 entry above (research expansion).

---

## 2026-08-04 — parallel implement cycle (Tracks A/B/C+D) + plan rewrite

**Trigger:** Parallel `/implement` Tracks A (Hellín eng), B (demo templates), C+D (proxy honesty + fuel maintain) + review fixes + 1-month plan rewrite.

**Decision:** Keep graph **v5** topology; **shift primary** from eng Hellín grade-A chase to **human demo M3.2**. Eng Hellín is **BLOCKED** with written evidence — not abandoned honesty, not GO_MES.

| Node | Before parallel | After 2026-08-04 |
|------|-----------------|------------------|
| Eng P1 Hellín | primary ops close | **BLOCKED** written; optional only |
| Human demo | co-primary | **PRIMARY** (templates ready) |
| Status sync | after Hellín A | after **demo / M3.4** (and any real P1 change) |
| GO_MES | blocked on P1 | still **false**; BLOCKED ≠ GO_MES |
| Anchors | 2 confirmed | same; Estrella/Cardoso stay proxy |

**Shipped (docs/product):**
- `docs/P1_HELLIN_ENG_STATUS.md` · `docs/HELLIN_TRACK_A_SCORECARD.md`
- Track B: acta + guion + informe skeleton (+ review: GO_MES Q&A + links to P1/proxy honesty)
- `docs/DATA_PROXY_HONESTY.md`
- Active plan rewrite: `docs/PLAN_1_MES_POST_O1_UNLOCK.md`
- Machine status: `docs/PLAN_1_MES_STATUS_20260804.json`
- STATE as-of 2026-08-04

**Rails held:** no invented Vp · GO_MES false · fusion OFF · no joint k.

**Next cycle success:** third-party demo acta (M3.2) and/or informe fill (M3.4); recompute GO_MES only if P1 truly closes under policy.

---

## 2026-08-04 — GO_MES mínimo declared

**Trigger:** Re-read PLAN_1_MES P1 = *incident smoke 2 real IFs without crash* (not structural grade A).

**Evidence:**
- O1: Tobarra+Hellín confirmed + ratios in-band (`anchor_scorecard.json`)
- P1: `python scripts/smoke_incident_runtime.py --p1-two-real --skip-synthetic` → both `updated`
- O4/M2/E1 already green

**Verdict:** **GO_MES=true** · `docs/GO_MES_VERDICT.md`  
**Not claimed:** GO_MES+ / O5 (Hellín still structural B) · GO_Q (demo pending)

**Graph:** primary remains **human demo M3.2**; eng grade-A Hellín is optional stretch.

---

## 2026-08-03 — c4 post-O1 → **v5**

**Trigger:** Pablo pack 0308 + Hellín **confirmed** (Vp 50) + fuel PR-α/β on `main` + `O1_GOMES_RECOMPUTE`.

**Decision:** Graph **v5** — O1 multi-ancla **PASS**; stop primary “Cardoso email for O1”.

| Node | v4 role | v5 role |
|------|---------|---------|
| External unblock | O1 Cardoso top | **Demo M3.2** top; eng P1 Hellín allowed |
| Status sync | weekly | must count **2** confirmed anchors |
| Autonomous cycle | integrity | maintain; not GO_MES main engine |
| Literature/fuel | primary science | maintain fuel/AEMET; **ops close GO_MES** |
| Fire intel | season | unchanged rails |

**Report:** [`cycle_c4_post_o1_20260803.md`](cycle_c4_post_o1_20260803.md)  
**Plan overlay:** `docs/PLAN_1_MES_POST_O1_UNLOCK.md`  
**STATE:** `.grok/graph_engineering/STATE.md` v5  

**Next cycle c5 success:** Hellín front_dynamics vs Vp 50 closes P1 → recompute GO_MES; and/or third-party demo acta.

---

## 2026-07-27 — v0 → v1 bootstrap

**Trigger:** Autonomous Graph Engineering mode activated after CI green (`907366d`) and weekly status.

**Decision:** Create first production graph `wfd-autonomous-cycle` focused on **repo integrity + dual-product honesty + CI hygiene**, not ML retrain spam.

**Why this graph first**
- Highest ROI post-CI-green: prevent honesty regressions and format drift.
- Email/data CCAA is wait-state (CyL/GAL); product demos already exist.
- Continuous value without inventing tactical ROS.

**Graph v1 topology**
```
Sense → parallel(ScanHonesty, ScanCI, ScanDualProduct) → VerifyFindings → Synthesize → EvolveLog
```

**Success metrics for cycle**
- Confirmed findings count (adversarial-survived)
- Whether local ruff/mypy would fail
- Whether scorecard/policy still honest (u1_test_honest true, ml_product_go false, field_ops fusion false)

**Next if stagnant:** spawn `wfd-pilot-regression` (tests fixtures only) or `wfd-open-pack-audit`.

## 2026-07-27 — cycle c0-bootstrap results → fix → v1.1

**Outcome:** 5/6 adversarial confirmations. Primary bug: field_ops live fusion OR-override via CLI.

**Graph decision:** keep topology; execute `fix_confirmed_locally` then re-run.

**Mutations shipped in code (not graph topology):**
- field_ops fusion hard clamp
- promote human signoff gate
- unknown policy fail-closed
- README U1 pitch
- effective fusion audit field

**Graph assets added:**
- `wfd-pilot-regression.rhai`
- `wfd-open-pack-audit.rhai` (v2 path when integrity clean)

**Scheduler:** `019fa3f50f7c` every 2h durable continuation.

## 2026-07-27 — c0-bootstrap synthesize (v1 held)

**HEAD:** `ba01ee2`  
**Report:** [`cycle_c0_bootstrap.md`](cycle_c0_bootstrap.md)  
**Prior sense:** [`cycle_c0_local_sense.md`](cycle_c0_local_sense.md)

| Metric | Value |
|--------|--------|
| confirmed_count | **5** |
| rejected/unverified | 1 |
| next_action | **fix_confirmed_locally** |
| format | pass |
| u1_test_honest | true |
| ml_product_go | false |
| field_ops catalog fusion | false (runtime OR gap confirmed) |

**Top confirmed ids**
1. `HR-field-ops-cli-or` (**bug**) — Decision Card ORs CLI/kwargs fusion under field_ops
2. `HR-readme-catalog-pitch` (suggestion) — README pitches 0.8963 without U1 / provenance label
3. `HR-promote-apply-before-signoff` (suggestion)
4. `HR-audit-fusion-snapshot-mismatch` (suggestion)
5. `HR-unknown-policy-fallback-open` (nit)

**graph_evolve (no topology fork yet):** Keep Sense→parallel scans→Verify→Synthesize; after local field_ops clamp + README U1 pitch fix, re-run same cycle before spawning pilot-regression.

**Dual-product rails:** preserved in claims; fix must not invent ROS or auto-flip `ml_product_go` / field_ops catalog policy.

---

## 2026-07-27 — c1-reverify synthesize (v1 held)

**HEAD:** `60d4d551d2fe2bb5456c7b95caee7f0d64dd5ef7`  
**Report:** [`cycle_c1_reverify.md`](cycle_c1_reverify.md)

| Metric | Value |
|--------|--------|
| confirmed_count | **6** |
| rejected/unverified | **0** |
| next_action | **fix_confirmed_locally** |
| format | pass (138 files) |
| u1_test_honest | true |
| ml_product_go | false |
| field_ops.allow_ml_live_in_fusion | false |
| research_open.allow_ml_live_in_fusion | true (experimental) |
| primary.model_iou | ~0.8569 |
| ece_patch_conf | ~0.1528 |
| prior c0 bugs re-opened | 0 |

**Top confirmed ids**
1. `HR-catalog-holdout-conf-1` (**bug**) — holdout saturates to conf 1.0 HIGH as phenomenon certainty when live absent
2. `HR-ml-only-legacy-holdout-ok` (**bug**) — holdout alone drives `ml_ok` → ML-only HOLD under non-field_ops
3. `HR-core-docs-catalog-pitch` (suggestion) — VISION/MEMORY/ARCHITECTURE/RULES/PRODUCTO_DUAL still lead 0.8963
4. `HR-metrics-hub-stale-fusion` (suggestion) — METRICS_HUB stale vs U1 / research_open
5. `HR-industrial-readiness-catalog-only` (suggestion) — snapshot catalog-only, no honesty block
6. `HR-lab-synthetic-public-scorecard` (suggestion) — lab synthetic eligible → public scorecard + apply-policy

**graph_evolve:** Keep Sense→parallel(ScanHonesty,ScanCI,ScanDualProduct)→Verify→Synthesize; add a Verify sub-check that DecisionCard.confidence_pred must not equal holdout_quality when live channel is absent, then fix confidence path before spawning pilot-regression.

**Dual-product rails:** field_ops fusion OFF; ml_product_go false; no ROS/tactical upgrade; fix must not auto-promote.

## 2026-07-27 — c1 fixes shipped

**Commit:** `c50fbb3` holdout never drives conf or ML-only HOLD (+ docs U1 + lab apply refuse).  
**Pilot:** already green 38/38.  
**Next:** c2 integrity re-run via scheduler or live workflow.

---

## 2026-07-27 — c2-post-holdout synthesize (v1 held)

**HEAD:** `c58d1186e626fd8ff5d295d330069491245e7ed2`  
**Report:** [`cycle_c2_post_holdout.md`](cycle_c2_post_holdout.md)

| Metric | Value |
|--------|--------|
| confirmed_count | **6** |
| rejected/unverified | **0** |
| next_action | **fix_confirmed_locally** |
| format | pass (138 files) |
| u1_test_honest | true |
| ml_product_go | false |
| field_ops.allow_ml_live_in_fusion | false |
| research_open.allow_ml_live_in_fusion | true (experimental) |
| primary.model_iou | ~0.8569 |
| ece_patch_conf | ~0.1528 |
| live score_ml_source cap | **0.75** (runtime honest post-c1) |
| prior c1 runtime bugs re-opened | **0** |

**Top confirmed ids**
1. `HR-stale-card-holdout-conf-1` (**bug**) — shipped commander/FIRE_DECISION_CARD/METRICS_HUB still show holdout conf=1.0 / holdout_quality=1.0 (pre-cap artifacts; live caps 0.75)
2. `HR-producto-dual-catalog-pitch` (suggestion) — PRODUCTO_DUAL leads 0.8963 without U1/provenance labels
3. `HR-guia-catalog-only-pitch` (suggestion) — GUIA demo teaches catalog 0.8963 only
4. `HR-cli-fusion-or-default-demo` (suggestion) — CLI OR enables fusion on default/demo without U1/promote gate
5. `HR-manifest-go-promote-vs-ml-product-go` (suggestion) — GO_PROMOTE vs ml_product_go=false vocabulary collision
6. `HR-industrial-readiness-catalog-only` (suggestion) — industrial snapshot catalog GO without honesty block

**graph_evolve:** Keep Sense→parallel(ScanHonesty,ScanCI,ScanDualProduct)→Verify→Synthesize; add Verify sub-check that shipped Decision Card / Metrics Hub holdout conf and holdout_quality are ≤0.75 and match live score_ml_source (fail if artifact shows 1.0), then fix_confirmed_locally before open-pack audit or pilot-regression.

**Dual-product rails:** field_ops fusion OFF; ml_product_go false; no ROS/tactical upgrade; regenerate claim surfaces only — do not auto-promote.

## 2026-07-27 — c2 fixes + open-pack-audit (shipped)

**Fixes:** claim surfaces regenerated (holdout conf **0.75**), PRODUCTO_DUAL/GUIA U1 pitch, CLI fusion OR gate, GO_PROMOTE vocabulary, industrial honesty block.  
**Open pack:** `decision_open=HOLD` contract + progressive sanitize + emsr629 quarantine (`1686123`).  
**Pilot regression:** green offline suites.

## 2026-07-29 — Graph v2: external-unblock first (stagnation diagnosis)

**Trigger:** Repo is GO_ENG; GO_MES blocked on O1 (1 anchor); autonomous honesty cycles were the wrong primary optimizer.

**Decision:** Retire 2h integrity spam as default. Primary graph = **external unblock + status sync**.

### Topology v2
```
wfd-status-sync (weekly)     → PLAN_3_MESES_STATUS + METRICS_HUB
wfd-external-unblock (main)  → one human/email next_action (O1, demo, CyL/GAL calendar)
wfd-pilot-regression         → on product code edits
wfd-autonomous-cycle         → weekly integrity only; idle if clean
wfd-open-pack-audit          → only after open pack builder changes
```

### Assets
- `.grok/workflows/wfd-external-unblock.rhai`
- `.grok/workflows/wfd-status-sync.rhai`
- `.grok/graph_engineering/STATE.md` (v2)
- `docs/PROJECT_STATUS.md` (canonical project truth)

### Rails unchanged
field_ops fusion OFF · ml_product_go false · no invented ROS · catalog 0.8963 provenance only · holdout conf ≤0.75

### Next planned
1. Human: Gmail re-auth + Cardoso Vp/ha request + third-party demo slot  
2. Graph: run `wfd-status-sync` then `wfd-external-unblock`  
3. Integrity: weekly `wfd-autonomous-cycle` only  
4. Do **not** open ML retrain loops without new non-Cardoso fire data  

## 2026-07-29 — c3 stack run (status + external + integrity)

**Gmail:** re-auth OK.  
**Reports:** status-sync ok → external-unblock O1 → autonomous findings fixed in-repo.

| Graph | Outcome |
|-------|---------|
| `wfd-status-sync` | honesty OK; next=external_unblock |
| `wfd-external-unblock` | **O1_second_anchor**; follow-up Pablo/Cardoso; code_allowed=false |
| `wfd-autonomous-cycle` | 3 claim-surface fixes shipped (hub U1 pitch, gold holdout 0.75, GO_RESEARCH_HOLDOUT vocab) |

**Detail:** [`cycle_c3_20260729.md`](cycle_c3_20260729.md)

**Human next:** one email Cardoso Vp/ha · third-party demo slot.  

## 2026-07-29 — Graph v3: fire intel scrape (mega-IF ES/FR)

**Trigger:** Need continuous open-source intelligence on 2026 mega-fires in Spain & France for fields Tobarra has and others lack (Vp, official ha, perimeter, LWIR).

### Topology addition
```
wfd-fire-intel-scrape (daily/season)
  SenseGaps → parallel(ES web, FR web, X, EFFIS/EMS) → Normalize (T0–T4) → Write inventory
```

### Bootstrap inventory
- `data/fire_intel/schema_v1.json` — Tobarra gap schema  
- `data/fire_intel/mega_fires_2026_es_fr.json` — 12 fires ES/FR (T1 press)  
- `docs/fire_intel/MEGA_FIRES_2026_ES_FR.md`  
- Anchor **stubs only** (pending_external + press ha): Burgohondo, Sierra Oeste; La Mierla updated  

### Hard rails
Press/X **never** → `confirmed` Vp/ha. Gold ops still requires parte + (for grade A) LWIR.

### Next
1. Run `wfd-fire-intel-scrape` on schedule during season  
2. EFFIS/EMS open packs for P1 fires when products exist  
3. Keep `wfd-external-unblock` for O1 emails  

## 2026-07-29 — Max-iteration data push (session)

**Launched:** fire-intel-scrape (+2) · status-sync · external-unblock (session cap 4 concurrent; autonomous/open/pilot queued after).  
**Manual parallel:** MITECO PDF download+parse · CEMS EMSR899/900/902/905 · EFFIS X complex ~65–70k · Gironde 42k · inventory v2 · cems_queue · completion matrix · plan_cycle + 38 tests.

**Hard stop on “have everything”:** open intel **MAXED**; Tobarra-class ops fields **still external**. See `docs/fire_intel/COMPLETION_MATRIX.md`.

---

## 2026-07-29 — c3-20260729 synthesize (v2 held; residual suggestions)

**HEAD:** `16861235330c31a4bb7d2d513189a28a3454a03e`  
**Report:** [`cycle_c3_20260729.md`](cycle_c3_20260729.md)  
**Worktree:** dirty (23 modified / 8 untracked) · ruff format **PASS**

| Metric | Value |
|--------|--------|
| confirmed_count | **6** |
| bugs | **0** |
| rejected/unverified | **0** |
| next_action | **run_external_unblock** |
| format | pass (138 files) |
| u1_test_honest | true |
| ml_product_go | false |
| field_ops.allow_ml_live_in_fusion | false |
| research_open.allow_ml_live_in_fusion | true (experimental) |
| primary.model_iou | ~0.8569 (U1 TEST) |
| ece_patch_conf | ~0.1528 |
| live holdout conf cap | **0.75** (METRICS_HUB / FIRE_DECISION_CARD aligned) |
| prior c0–c2 runtime bugs re-opened | **0** |

**Top confirmed ids (all suggestion)**
1. `HR-metrics-hub-catalog-primary` — hub/dashboard still pitch catalog IoU 0.8963 without U1/ECE/provenance-only label
2. `HR-gold-e2e-stale-holdout-conf-1` — GOLD_IF_E2E still holdout conf 1.0 / holdout_quality=1.000 (stale vs live 0.75)
3. `HR-go-promote-vocab-collision` — research `GO_PROMOTE` vs `ml_product_go=false` residual
4. `HR-cli-fusion-flag-misleading` — CLI help claims unlock; policy-catalog only
5. `HR-u1-abstain-rate-zero` — abstain_rate 0.0 with ECE residual ~0.15
6. `HR-hub-firms-as-open-cems` — hub max_area_ha picks la_mierla FIRMS-only as open_cems_perimeter w=0.35

**graph_evolve:** Keep v2 primary topology (external-unblock main, status-sync weekly, autonomous-cycle weekly-only); add weekly Verify artifact checks that gold E2E holdout conf ≤0.75 and hub primary ML number prefers U1 over unlabeled catalog 0.8963 — not continuous re-scan.

**Dual-product rails:** field_ops fusion OFF; ml_product_go false; no ROS/tactical upgrade; residual claim-surface backlog only — do not auto-promote; do not open ML retrain without new non-Cardoso fire data.
