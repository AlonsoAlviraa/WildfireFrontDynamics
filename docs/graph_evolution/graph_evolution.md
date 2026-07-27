# Graph Evolution Log — WildfireFrontDynamics

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

## Next planned

1. ~~fix_confirmed_locally~~ done in `c50fbb3`
2. Re-run `wfd-autonomous-cycle` as c2
3. If clean → `wfd-open-pack-audit`
