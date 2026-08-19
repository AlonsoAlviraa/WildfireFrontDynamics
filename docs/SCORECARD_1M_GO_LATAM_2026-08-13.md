# Scorecard 30d — GO total + LATAM (2026-08-13 eng snapshot)

> **Plan SSOT:** `docs/PLAN_1M_GO_LATAM_2026-08-13.md`  
> **Window:** 2026-08-13 → 2026-09-12  
> **This file:** measured eng state mid-window / implementation half — **not** end-of-month final if humans still open.

## Gates (product)

| Gate | Measured | Value | Notes |
|------|----------|-------|-------|
| GO_MES | yes | **true** | Stamp |
| GO_Q | yes | **partial** | No signed non-PENDING acta on disk |
| GO_TOTAL | yes | **false** | Needs GO_Q complete + h1_acta |
| field_ops fusion | yes | **ON** | Human 2026-08-13; ≠ despacho |
| GO_MES+ | yes | **false** | Prep only (`docs/GO_MES_PLUS_PREP.md`) |
| FREEZE KEEP reopen | yes | **false** | Intact |
| `check_release_flags` | yes | **PASS** | Required daily |

## H1 / GO_Q path

| Item | Measured? | Result |
|------|-----------|--------|
| eng_session_ready | yes | **true** |
| go_q_met | yes | **false** |
| h1_slot | yes | **not_booked** (human) |
| record refuses PENDING | yes | exit **2** |
| Signed third-party acta | **no** | Only `ACTA_DEMO_PENDING_HUMAN.md` |
| GO_Q complete | **no** | Partial only |

## LATAM+AU lab data

| Item | Measured? | Result |
|------|-----------|--------|
| Packs open (`ml_weak`) | yes | 6 packs (4 EMSR + 2 L1 weak) |
| CONAF send_status | yes | **sent_gmail** (message id present) |
| CONAF folio OIRS | **no** | No invented folio |
| `lab_ok_conaf` | yes | **false** (no written cession) |
| real_proxy NDWS ready | yes | **n_ready=4** EMSR packs (`ndws_covariates_report.json`) |
| complete_proxy model IoU | yes (proxy) | usable-pair mean **~0.737** (Nacimiento 0.673 + NSW 0.802; 4 growth pairs). EMSR715 FEP→DEL is `incompatible_product_kind` (not growth; old 0.088 dropped from the mean, pack still listed). Model **below copy** on every usable pair. **Not** sealed transfer IoU · **not** dressed ~0.85 |
| Warp S2→CEMS proxy IoU | yes (proxy) | Perth/Nacimiento prior + EMSR408 ~0.18 + EMSR715 ~0.47 — **not** model/transfer IoU |
| LOFO non-CLM model_iou | yes (honest null) | `null` / blocked schema |
| Transfer IoU sealed | **no** | Stays null / blocked |

## B4 / B5 (GO_MES+ stretch)

| Item | Measured? | Result |
|------|-----------|--------|
| Hellín structural grade | no in-tree scorecard | **null** |
| n_grade_a_ops (in-repo) | yes | **0** |
| O2 official_national | yes | **false** / BLOCKED_EXTERNAL |
| GO_MES+ prep checklist | eng doc | `docs/GO_MES_PLUS_PREP.md` open items |

## Sector ROS / Mes2

| Item | Measured? | Result |
|------|-----------|--------|
| PR #39 sector ROS eng | yes | **merged** 2026-08-13 |
| Field-validated ROS | **no** | Eng default only — no field claim |

## Explicit not-measured / not-claims

- Not GO_Q complete / not invented tercero or acta  
- Not complete_proxy IoU as transfer IoU  
- Not CONAF cesión / lab_ok true  
- Not GO_MES+ true / not grade A invented  
- Not tactical dispatch from fusion ON  
- Not end-of-month “éxito fuerte” until H1 human path closes  

## Success class (plan §4 S4)

| Class | Met now? |
|-------|----------|
| Éxito fuerte (GO_TOTAL true) | **no** |
| Éxito honesto mínimo (eng 7/7 + pack + GO_Q partial honest + LATAM residual) | **eng half yes**; human H1 outreach still open |
| Fallo (invent gates) | **avoided** |

## Commands to re-measure

```bash
python scripts/check_release_flags.py
python scripts/prepare_h1_demo_session.py --skip-dry-run
python scripts/b4_b5_status_probe.py
python scripts/fill_latam_au_ndws_covariates.py --all --skip-dem-fetch
# inspect: data/open_if/latam_au/inventories/ndws_covariates_report.json
# inspect: outputs/ml_eval/latam_au_warp/warp_summary.json
```
