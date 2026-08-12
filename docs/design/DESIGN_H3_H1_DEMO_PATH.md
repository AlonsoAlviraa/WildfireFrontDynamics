# Design — H3 dry-run (teach → demo-third-party → cheatsheet) + H1 prep → GO_Q

| Campo | Valor |
|-------|--------|
| **Status** | **SHIPPED eng** (2026-08-04) — H3 path executed; H1 prep only; GO_Q still partial |
| **As of** | 2026-08-04 |
| **Honesty** | Eng **cannot** complete H1 or flip GO_Q without real third-party signature |

---

## 1. Problem

- H3 was eng-ready (`dry_run_demo_third_party.py`) but did not run the **full human path**: `teach` → `demo-third-party` → cheatsheet presence.
- H1 (M3.2) still blocks GO_Q; need a **prep kit** so a human can close GO_Q in one session without hunting templates.

## 2. Goals

| ID | Goal | Acceptance |
|----|------|------------|
| G1 | One-command **H3 path dry-run** | Runs teach (stdout capture), show (gates), demo-third-party (pack+replay), verifies cheatsheet exists; writes report |
| G2 | CLI surface | `wildfire-front dry-run-h3` (or alias) wrapping the path |
| G3 | Report honesty | Report marks `h3_eng_ok` vs `h3_human_attestation_pending` |
| G4 | H1 prep kit | Draft acta path + runbook + checklist; **GO_Q stays partial** until signed |
| G5 | Status JSON | H3 → ENG_EXECUTED_HUMAN_ATTESTATION_PENDING or similar; H1 still TODO unless human signs |

## 3. Non-goals

- Fake third-party name / signed GO_Q
- Auto-email to third parties
- ML fusion ON
- Skip replay to force green

## 4. Design

### 4.1 H3 dry-run steps (ordered)

```text
1. teach -q           → exit 0, capture has "Acto" or acts 1-4
2. show -q / --json   → GO_Q partial, fusion OFF
3. cheatsheet exists  → docs/CHEATSHEET_DEMO_12MIN.md
4. demo-third-party   → exit 0 (replay default ON)
5. write report       → outputs/demo_third_party/H3_DRY_RUN_REPORT.md + .json
```

Optional (`--full-demo`): also multi-ccaa build + pilot honesty (heavier; default OFF for speed).

### 4.2 Report schema

```json
{
  "schema": "wfd_h3_dry_run_v1",
  "utc": "...",
  "steps": [{"id":"teach","ok":true,"rc":0}, ...],
  "gates": {"GO_MES": true, "GO_Q": "partial", "field_ops_ml_live_fusion": "OFF"},
  "h3_eng_path_ok": true,
  "h3_human_attestation_pending": true,
  "h1_status": "NOT_STARTED",
  "go_q_met": false,
  "next": "Human: walk cheatsheet 12 min + fill acta with real third party"
}
```

### 4.3 H1 prep kit

| File | Content |
|------|---------|
| `docs/actas/ACTA_DEMO_PENDING_HUMAN.md` | Copy of template with prefilled product/version/rails; blanks for human/third party |
| `docs/H1_GO_Q_RUNBOOK.md` | 1-page: before/during/after demo; how to flip status after signature |
| Script optional | `scripts/prepare_h1_acta_draft.py` copies template + injects git SHA |

**GO_Q flip rule (code must not auto-do):** only when `docs/actas/` contains signed acta with third-party name + date + presenter checkboxes, human updates PLAN status. Eng provides `scripts/record_h1_demo_complete.py --acta PATH` that **validates** required fields and then sets M3.2/H1/GO_Q — refuse if fields empty.

### 4.4 PR Plan

| PR | Content |
|----|---------|
| PR1 | `scripts/run_h3_dry_run_path.py` + CLI `dry-run-h3` + tests |
| PR2 | H1 prep kit + `record_h1_demo_complete.py` (strict validation) |
| PR3 | Status/STATE/cheatsheet/course links; execute dry-run once; report in outputs |

## 5. Key Decisions

1. **H3 eng can green the path; H3 human attestation separate.**  
2. **GO_Q only via record script after non-empty third-party fields.**  
3. Default dry-run does **not** rebuild multi-CCAA (use `--full-demo`).  
4. Spanish human reports.

## 6. Open Questions

None — defaults above.

## 7. Testing

- Unit: dry-run step aggregation with mocked subprocess.  
- Live: one real dry-run in implement phase.  
- record_h1: empty acta → exit 2; filled fixture → would update status (test with temp JSON).
