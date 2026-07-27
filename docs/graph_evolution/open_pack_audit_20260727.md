# Open pack audit — 2026-07-27

**Workflow:** `wfd-open-pack-audit`  
**next_action:** `fix_labels` (executed)

## Findings → actions

| Sev | Finding | Action |
|-----|---------|--------|
| H | AND progressive `primary_ros_m_min` / grade A | Sanitized summary via `_sanitize_psb_fd_summary` |
| M | CEMS scorecard GO-only | Builder now emits `decision_open=HOLD` + not-tactical flags; patched emsr578/581/583/632 scorecards |
| M | Brief m/min lead | Patched briefs; `_render_brief` already ha/day preferred |
| M | manifest ros_proxy bare m/min | Patched proxy flags/keys on manifests + index |
| M | emsr629 incomplete | `QUARANTINE_INCOMPLETE.md` added |
| L | la_mierla scorecard | `decision_open=HOLD` |
| L | tests GO-only | Assert `decision_open` HOLD/ABSTAIN |
| L | demo ML | PASS control (no change) |

## Tracked code

- `scripts/build_open_if_pack.py` — scorecard honesty fields
- `tests/test_open_if_pack.py` — contract tests

## Note

`outputs/` is gitignored. Pack JSON/MD fixes apply **locally** for demos; re-run builders on clean machines to regenerate.

## next_action after this

`idle` on open packs until next integrity cycle, or rebuild packs fully when CEMS vectors present.
