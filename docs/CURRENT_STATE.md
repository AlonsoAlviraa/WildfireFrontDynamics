# CURRENT_STATE — WildfireFrontDynamics

> **SSOT for release flags** (`scripts/check_release_flags.py`)  
> **As of:** 2026-08-12 (Mes2 PR3-A shipped · Mes3 plan filed)  
> **Companion stamp:** `docs/ML_PRODUCT_GO_STATUS.json`  
> **Bottlenecks:** `docs/BOTTLENECKS_B1_B6_STATUS.md`  
> **Anchors SSOT:** `docs/DATA_ANCHOR_SSOT.md` + `data/infocam_anchors.json`  
> **30d plan:** `docs/PLAN_30D_AGENTES_A_B_2026-08-12.md`  
> **Mes2 PR3:** `docs/PLAN_MES2_PR3_AGENTES_A_B.md` · handoff `docs/HANDOFF_MES2_PR3_HUMANOS_2026-08-12.md`  
> **Mes 3 (12 sep–11 oct):** `docs/PLAN_MES3_AGENTES_A_B_2026-09-12.md` · handoff `docs/HANDOFF_MES3_HUMANOS_2026-09-12.md`  
> **ML leap:** `docs/PLAN_ML_LEAP_2026-08-12.md` · D0 `docs/ML_LEAP_REQUEST_DATA.md` · E1 `docs/ML_LEAP_EVAL_ONESHOT.md` · claims `docs/CLAIM_BOARD_ML_LEAP_2026-08-12.md`  

> **Product:** decision support for wildfires — **not** tactical dispatch.

## One-line truth

**GO_MES true · GO_Q partial (H1 third-party acta) · ml_product_go true (lab only) · field_ops ML fusion OFF · FREEZE_ML_AND_REQUEST_DATA · Tobarra KEEP KILL · sealed LOFO pitch ~0.79 · catalog 0.8963 provenance only · Hellín pending_external · SPA Live Ops on main (#19) · Mes2 eng shipped (#31/#32/#34/#35/#38) · Mes3 plan filed.**

## Gates

| Gate | Value |
|------|--------|
| **GO_MES** | **true** |
| **ml_product_go** | **true** |
| **field_ops ML fusion** | **OFF** |
| **GO_Q** | **partial** |
| **GO_MES+** | **false** |

### Gate notes (aligned to stamp + B1–B6)

| Gate | Note |
|------|------|
| GO_MES | Mínimo mes (B2 aligned). Stamp `GO_MES=true`. |
| ml_product_go | Lab product only (`clm_ensemble_v34`). **≠** field fusion. |
| field_ops ML fusion | Non-negotiable **OFF** until human promote + evidence. |
| GO_Q | Stack eng-ready; stays **partial** until third-party demo + signed acta (`record_h1_demo_complete.py`). Never invent GO_Q true from PENDING draft. |
| GO_MES+ | Still open: 2nd grade A ops (B4) / O2 nacional (B5) / H1 demo. |

## Rails (non-negotiable)

- **field_ops ML fusion OFF** — `field_ops_allow_ml_live_in_fusion=false` in stamp; do not promote live ML into field fusion without human signoff.
- **FREEZE_ML_AND_REQUEST_DATA** — Tobarra KEEP reopen = **false** (B6 process KILL). No thrash retrain; pitch sealed LOFO ~0.79; request data instead.
- **GO_Q = partial** until real third-party demo + signed acta. Eng prep (`prepare_h1_demo_session.py`) may set `eng_session_ready=true` while `go_q_met=false`.
- **Hellín / 2nd grade A** — only `tobarra_20240802` is `confirmed` in `data/infocam_anchors.json`. Hellín stays `pending_external` until cite + human promote (`docs/DATA_ANCHOR_SSOT.md`).
- Catalog holdout IoU **0.8963** is **provenance only** — not live fire certainty, not ROS, not tactical speed.
- Decision Card may **ABSTAIN** / **HOLD**; that is a feature.
- IoU is not ROS / Vp.

## Eng status (not gates)

| Item | State |
|------|--------|
| SPA Live Ops on clean main | **Shipped** (#19) — supersedes #10 (do not revive secret-bearing base) |
| Operator hub H1 cheatsheet | **Shipped** (#18); B3 smoke/rails (#22) |
| Agent A / Agent B 30d plan | **Shipped** docs (#20) |
| Agent B W1 honesty rails | **Shipped** (#21) — GO_Q/GO_MES+/FREEZE + Hellín checklist |
| Mes2 PR1-A uncertainty bar | **Shipped** (#32) — no-ROS copy |
| Mes2 PR1-B decision-log + ACK sidecar | **Shipped** (#31) — `decision_log.py` allowlisted work_dir |
| Mes2 PR2-A decision-log UI + ACK | **Shipped** (#35) — SPA wire to real sidecar |
| Mes2 PR2-B V&V scorecard stub | **Shipped** (#34) — `vv_sidecar` eng_stub, no field claims |
| Mes2 PR3-A H1 / split-conf polish | **Shipped** (#38) |
| Mes2 PR3-B sector ROS eng + tests | **In flight** (#39) — merge before Mes3 W1-B if still open |
| Mes 3 plan (humanos A/B) | **Filed** — `PLAN_MES3_AGENTES_A_B_2026-09-12.md` (no gate flips) |
| ML leap program | **Filed** — `PLAN_ML_LEAP_2026-08-12.md` (FREEZE intact; no v35) |
| ML leap D0 REQUEST_DATA | **In flight** — P0/P1/P2 + Hellín H1–H7; no promote |
| ML leap E1 eval oneshot | **Doc shipped with D0** — frozen cal TEST path; SKIP ≠ green |

## Bottlenecks snapshot (B1–B6)

| ID | Estado | Residual |
|----|--------|----------|
| **B1** H1 demo+acta | ENG READY / HUMAN OPEN | Agendar tercero + acta firmada |
| **B2** Docs/flags | MITIGADO when this file + stamp PASS `check_release_flags` | Keep SSOT aligned; GO_Q partial + GO_MES+ false + FREEZE rails enforced |
| **B3** Repo noise | MITIGADO | `.gitignore` AI/data caches |
| **B4** 2nd grade A | OPEN | Datos 2º IF / scorecards; Hellín not promoted |
| **B5** O2 nacional | OPEN / BLOCKED | FOI/partner; no flag invention |
| **B6** Tobarra LOFO | CLOSED process (KILL) | FREEZE + REQUEST_DATA |

## Explicit non-claims

- Not tactical dispatch / not “apagamos incendios con IA”
- Not field_ops ML fusion ON
- Not GO_Q complete without demo+acta tercero
- Not GO_MES+ without 2nd grade A + O2 path honesty + H1
- Not Tobarra KEEP reopen without new data/signal
- Not ROS / Vp from catalog IoU
- Not Hellín confirmed Vp/ha without cite + Alonso promote
- Not merge of `fix/b2-b3-flags-noise*` / PR #10 secret-bearing base
- Not PR3-A/B code shipped until those PRs merge (docs plan only)

## Verify (B)

```bash
python scripts/check_release_flags.py
# expect: status=PASS exit=0
pytest tests/test_check_release_flags.py tests/test_data_anchor_honesty.py tests/test_cli_operator.py tests/test_cli_usage_errors.py -q
```
