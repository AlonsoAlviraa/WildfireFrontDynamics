# Handoff humano P0 — 2026-08-13

**Quién:** Alonso / humano (no Agent B).  
**Repo tip after Agent B merges:** `origin/main` @ `52b427e` (post-#47 + #39).  
**SSOT:** `docs/CURRENT_STATE.md` · `data/infocam_anchors.json` · `docs/DATA_ANCHOR_SSOT.md` · `docs/ML_LEAP_REQUEST_DATA.md`

## These leftovers do **not** close GO_Q and do **not** lift FREEZE

Completing any item below is **data / evidence / demo work**. It does **not**:

- set `GO_Q` to true / complete
- lift `FREEZE_ML_AND_REQUEST_DATA`
- reopen Tobarra KEEP (`tobarra_keep_reopen` stays **false**)
- retrain `clm_ensemble_v34`
- flip `hellin_2024` (or any other fire) to `confirmed` without the full H1–H7 + Alonso merge
- invent Vp/ha, ROS de campo, or dispatch authority

**Product remains decision support, not tactical dispatch.**

---

## P0 leftovers (humano only)

### 1. Hellín 2024 — PDF + KMZ cite (checklist H1–H7)

**SSOT today:** `hellin_2024` = `pending_external` in `data/infocam_anchors.json` (`vp_m_min` / `area_ha` / `source` all null).

**Ask:** official parte / boletín **PDF** + perimeter **KMZ/KML** with time so a **literal cite** can fill H1–H7.

| ID | Gate | Do not skip |
|----|------|-------------|
| **H1** | Literal cite (parte/boletín, date, IF name, Vp and/or ha) | No hearsay / slide / demo SPA numbers |
| **H2** | Units: `vp_m_min` m/min, `area_ha` ha | No “~50 km/h” |
| **H3** | `fire_id` stays `hellin_2024` | No new alias |
| **H4** | `source` non-empty and attributable | No “demo SPA” |
| **H5** | Same PR: status + numbers + source | No `confirmed` with nulls |
| **H6** | Alonso OK written on PR / acta | Agent does not merge promote |
| **H7** | Promote ≠ reopen Tobarra KEEP / retrain | FREEZE stays |

Checklist detail: `docs/ML_LEAP_REQUEST_DATA.md` · `docs/DATA_ANCHOR_SSOT.md`.

**Do not** edit `data/infocam_anchors.json` to `confirmed` in this handoff, in a bot PR, or without H1–H7 + Alonso.

---

### 2. Second grade-A ops fire (Cardoso preferred)

**SSOT today:** only `tobarra_20240802` is `confirmed` (Vp 7.0 m/min, 39 ha, INFOCAM 2024 parte).  
`cardoso_2025` = `pending_external`. B4 2nd grade A remains **OPEN**. GO_MES+ remains **false**.

**Ask (preferred):** Cardoso 2025 Vp media (m/min) + ha + attributable source (INFOCAM / Observatorio), if that outreach thread is live. Another complete IF is acceptable if Cardoso is blocked.

Grade A claim later requires **all** of (`docs/B4_B5_UNBLOCK_CALENDAR.md`):

1. Structural grade A on an in-repo scorecard  
2. ROS/Vp ratio in **[0.5, 2.0]**  
3. Documented Vp/ha anchor (not invented)  
4. No silent multi-IF `k` fit  
5. Scorecard JSON + MD committed  

Open LATAM/AU / PT-FireSprd / GOFER packs are **proxy / research**, not a 2nd INFOCAM grade A.

---

### 3. H1 third-party demo + signed acta

**SSOT today:** GO_Q = **partial**. Eng session pack exists; human demo does **not**.

| Artefacto | Path |
|-----------|------|
| Calendar copy/paste | `docs/H1_CALENDAR_INVITE.md` |
| 12 min cheatsheet | `docs/CHEATSHEET_DEMO_12MIN.md` |
| Runbook | `docs/H1_GO_Q_RUNBOOK.md` |
| Acta draft (not signed) | `docs/actas/ACTA_DEMO_PENDING_HUMAN.md` |
| Session snapshot | `docs/H1_DEMO_SESSION_READY.json` (`go_q_met=false`) |

**Human sequence:**

1. Schedule a **real third party** (emergencias / uni / partner). No third party → no H1.  
2. Run the 12 min demo. Verbal kill list: no invented ROS/Vp · fusion ON ≠ GO_Q complete ≠ despacho · no “apagamos incendios con IA” · sealed LOFO ~0.79 not field certainty.  
3. Fill a **real** acta: `docs/actas/ACTA_DEMO_YYYYMMDD_<org>.md` (fecha, presentador, tercero externo, checklists, firmas). **Not** the PENDING draft.  
4. Only **after** that signed acta exists, a human may run:

```powershell
python scripts/record_h1_demo_complete.py --acta docs/actas/ACTA_DEMO_YYYYMMDD_<org>.md
```

**Do not** run `record_h1_demo_complete.py` as complete against the PENDING draft (script exits 2 and must not mutate GO_Q). Agent B did **not** run it as complete.

---

## Eng inventory (does **not** close this handoff)

Agent B added a fail-closed board: `docs/WEAKNESS_BOARD.md` + `docs/WEAKNESS_BOARD.json` (`scripts/score_if_weakness_board.py`). It **measures** on-disk tif/dated-scene counts and scores R1–R6 / H1–H7 with unknown=0.

That board does **not** complete any P0 leftover above: Hellín stays `pending_external`, Cardoso is not a 2nd grade A, H1 acta is still human, GO_Q stays **partial**, FREEZE stays, no v34 retrain.

---

## Agent B already shipped (do not redo)

| PR | Merge SHA | What |
|----|-----------|------|
| [#47](https://github.com/AlonsoAlviraa/WildfireFrontDynamics/pull/47) | `ea4c7eb` | PT-FireSprd/GOFER ingest + `honesty_class` + E1 + latency; **no FREEZE lift** |
| [#39](https://github.com/AlonsoAlviraa/WildfireFrontDynamics/pull/39) | `52b427e` | `sector_ros_eng_default` + tests; fusion **ON**; **not** field ROS |

A follow-up Agent B PR may add the weakness board (scripts/tests/docs only). It does **not** close this human P0. No v34 retrain. No merge of #10 / secret-bearing base. No PII / FOI fills in git.

## Rails snapshot (post-#47 + #39, `check_release_flags.py` **PASS** 13/13)

| Rail | Value |
|------|--------|
| `check_release_flags.py` | **PASS** |
| GO_Q | **partial** |
| GO_MES | true |
| GO_MES+ | **false** |
| field_ops ML fusion | **ON** (human 2026-08-13; ≠ despacho) |
| FREEZE_ML | intact — no v34 retrain |
| `tobarra_keep_reopen` | **false** |
| Hellín | `pending_external` |
| Cardoso | `pending_external` |
| #10 | do not merge |
| Product | decision support, **not** dispatch |

```powershell
python scripts/check_release_flags.py
# expect: status=PASS exit=0 · GO_Q partial · tobarra_keep_reopen false · fusion ON
```
