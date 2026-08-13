# CURRENT_STATE — WildfireFrontDynamics

> **SSOT for release flags** (`scripts/check_release_flags.py`)  
> **As of:** 2026-08-13 (1M S1–S4 eng half · H1 slot **not_booked** · fusion ON · GO_Q partial · #39 merged)  
> **Companion stamp:** `docs/ML_PRODUCT_GO_STATUS.json`  
> **Bottlenecks:** `docs/BOTTLENECKS_B1_B6_STATUS.md`  
> **Anchors SSOT:** `docs/DATA_ANCHOR_SSOT.md` + `data/infocam_anchors.json`  
> **1M plan (13 ago–12 sep):** `docs/PLAN_1M_GO_LATAM_2026-08-13.md` · GO total `docs/GO_TOTAL_STATUS.json`  
> **30d plan (A/B surface):** `docs/PLAN_30D_AGENTES_A_B_2026-08-12.md`  
> **Mes2 PR3:** `docs/PLAN_MES2_PR3_AGENTES_A_B.md` · handoff `docs/HANDOFF_MES2_PR3_HUMANOS_2026-08-12.md`  
> **Mes 3 (12 sep–11 oct):** `docs/PLAN_MES3_AGENTES_A_B_2026-09-12.md` · handoff `docs/HANDOFF_MES3_HUMANOS_2026-09-12.md`  
> **ML leap:** `docs/PLAN_ML_LEAP_2026-08-12.md` · D0 `docs/ML_LEAP_REQUEST_DATA.md` · E1 `docs/ML_LEAP_EVAL_ONESHOT.md` · E1b `docs/ML_LEAP_SELECTIVE_FNR.md` · claims `docs/CLAIM_BOARD_ML_LEAP_2026-08-12.md`  
> **LATAM+AU campaign:** `docs/PLAN_ML_DATA_LATAM_AU_2026-08-13.md` · status `docs/data_campaigns/LATAM_AU_CAMPAIGN_STATUS.md`  

> **Product:** decision support for wildfires — **not** tactical dispatch.

## One-line truth

**GO_MES true · GO_Q partial (H1 third-party acta) · ml_product_go true (lab) · field_ops ML fusion ON · FREEZE_ML_AND_REQUEST_DATA · Tobarra KEEP KILL · sealed LOFO pitch ~0.79 · catalog 0.8963 provenance only · Hellín pending_external · SPA Live Ops on main (#19) · Mes2 eng shipped (#31/#32/#34/#35/#38) · CLI/front #43 · V&V UI #45 · Mes3 plan filed.**

## Gates

| Gate | Value |
|------|--------|
| **GO_MES** | **true** |
| **ml_product_go** | **true** |
| **field_ops ML fusion** | **ON** |
| **GO_Q** | **partial** |
| **GO_MES+** | **false** |

### Gate notes (aligned to stamp + B1–B6)

| Gate | Note |
|------|------|
| GO_MES | Mínimo mes (B2 aligned). Stamp `GO_MES=true`. |
| ml_product_go | Lab product only (`clm_ensemble_v34`). **≠** field fusion. |
| field_ops ML fusion | **ON** (human promote 2026-08-13). Live ML may enter Decision Card under `field_ops` (max weight 0.20, abstain_below 0.45). **≠** despacho táctico. GO_Q sigue partial. |
| GO_Q | Stack eng-ready; stays **partial** until third-party demo + signed acta (`record_h1_demo_complete.py`). Never invent GO_Q true from PENDING draft. |
| GO_MES+ | Still open: 2nd grade A ops (B4) / O2 nacional (B5) / H1 demo. |

## Rails (non-negotiable)

- **field_ops ML fusion ON** — `field_ops_allow_ml_live_in_fusion=true` (human 2026-08-13). Still **not** tactical dispatch; ABSTAIN/HOLD remain features; IoU ≠ ROS.
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
| Mes2 PR3-B sector ROS eng + tests | **Shipped** (#39 merged 2026-08-13) — `sector_ros_eng_default` (physics/quartile; **not** field-validated ROS / not tactical) |
| 1M plan eng half (S1–S4) | **In progress / eng snapshot** — `PLAN_1M_GO_LATAM_2026-08-13.md` · exec `PLAN_1M_EXECUTION_STATUS.json` · H1 `h1_slot=not_booked` |
| H1 calendar slot | **not_booked** (human Alonso) — eng pack ready; no invented tercero |
| Mes 3 plan (humanos A/B) | **Filed** — `PLAN_MES3_AGENTES_A_B_2026-09-12.md` (no gate flips) |
| Mes3 W1-A V&V UI read | **Shipped** — SPA `vv-scorecard` read-only #34; empty honest; no field scores |
| field_ops ML live fusion | **ON** — human promote 2026-08-13 (catalog + stamp; ≠ despacho; GO_Q partial) |
| ML leap program | **Filed** — `PLAN_ML_LEAP_2026-08-12.md` (FREEZE intact; no v35) |
| ML leap D0 REQUEST_DATA | **Shipped** docs (#42) — P0/P1/P2 + Hellín H1–H7; no promote |
| ML leap E1 eval oneshot | **Doc shipped** (#42) — frozen cal TEST path; SKIP ≠ green |
| ML leap E1b selective/FNR | **Filed** — `ML_LEAP_SELECTIVE_FNR.md` (method; @50/@90 not run; no L6) |
| IF weakness / candidate board | **Shipped** — `docs/WEAKNESS_BOARD.md` (R1–R6 / H1–H7 fail-closed; measured on-disk counts; no Vp/ha invention; no FREEZE lift / no KEEP reopen) |
| Weakness-board SPA (read-only) | **Shipped** — `data-marker="weakness-board"`; missing JSON → honest empty; 2ª ancla hidden unless JSON `grade_a_ops_anchors>=2` **and** two confirmed cited fires |
| PR #48 weakness board | **Open** on `feat/agent-b-weakness-board` until Tests CI green (do not merge red) |
| Hellín/Cardoso outreach templates | **Filed, not sent** — `docs/data_campaigns/HELLIN_CARDOSO_OUTREACH/` (`sent=false`, owner=human) |
| no-cite = no-promote | **Hardened** — `scripts/refuse_promote_without_cite.py`; H1=0 / null vp/ha/source cannot confirm; `--attempt-promote --fire-id hellin_2024` exits 1 |
| H1 dry-run | **≠ acta** — `scripts/dry_run_h1.py` pins `go_q_met=false` · `not_third_party_acta=true` · `not_signed_acta=true` |
| Human leftovers (GAP) | Hellín cite · Cardoso Vp/ha · R4 cession · H1 demo+acta — owner=human; do not invent |

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
- field_ops ML fusion **ON** ≠ GO_Q complete ≠ despacho táctico
- Not GO_Q complete without demo+acta tercero
- Not GO_MES+ without 2nd grade A + O2 path honesty + H1
- Not Tobarra KEEP reopen without new data/signal
- Not ROS / Vp from catalog IoU
- Not Hellín confirmed Vp/ha without cite + Alonso promote
- Not merge of `fix/b2-b3-flags-noise*` / PR #10 secret-bearing base
- Not PR3-B field-validated ROS / GO_Q (sector ROS is **default eng** only)
- Not PR3-A/B remaining items as complete beyond what this table lists

## Verify (B)

```bash
python scripts/check_release_flags.py
# expect: status=PASS exit=0
pytest tests/test_check_release_flags.py tests/test_data_anchor_honesty.py tests/test_cli_operator.py tests/test_cli_usage_errors.py -q
```
