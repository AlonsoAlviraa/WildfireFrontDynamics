# CURRENT_STATE — WildfireFrontDynamics

> **SSOT for release flags** (`scripts/check_release_flags.py`)  
> **As of:** 2026-08-12 (Agent B W1 honesty refresh)  
> **Companion stamp:** `docs/ML_PRODUCT_GO_STATUS.json`  
> **Bottlenecks:** `docs/BOTTLENECKS_B1_B6_STATUS.md`  
> **Anchors SSOT:** `docs/DATA_ANCHOR_SSOT.md` + `data/infocam_anchors.json`  
> **30d plan:** `docs/PLAN_30D_AGENTES_A_B_2026-08-12.md` (when merged via docs PR)  
> **Product:** decision support for wildfires — **not** tactical dispatch.

## One-line truth

**GO_MES true · GO_Q partial (H1 third-party acta) · ml_product_go true (lab only) · field_ops ML fusion OFF · FREEZE_ML_AND_REQUEST_DATA · Tobarra KEEP KILL · sealed LOFO pitch ~0.79 · catalog 0.8963 provenance only · Hellín pending_external.**

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

## Eng in flight (not gates)

| Item | State |
|------|--------|
| SPA Live Ops land (clean main) | In flight / PR #19 — supersedes #10; **do not merge #10** |
| Operator hub H1 cheatsheet | **Shipped** (#18) |
| Agent A / Agent B 30d split | Plan docs PR #20; B owns platform/data honesty |
| Decision-log + V&V sidecar | Agent B W2+ (not claimed shipped) |

## Bottlenecks snapshot (B1–B6)

| ID | Estado | Residual |
|----|--------|----------|
| **B1** H1 demo+acta | ENG READY / HUMAN OPEN | Agendar tercero + acta firmada |
| **B2** Docs/flags | MITIGADO when this file + stamp PASS `check_release_flags` | Keep SSOT aligned; GO_Q partial rail enforced |
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
- Not SPA Live Ops on main until clean #19 merges (no secret-bearing base)

## Verify (B2)

```bash
python scripts/check_release_flags.py
# expect: status=PASS exit=0
pytest tests/test_check_release_flags.py tests/test_data_anchor_honesty.py tests/test_cli_operator.py tests/test_cli_usage_errors.py -q
```
