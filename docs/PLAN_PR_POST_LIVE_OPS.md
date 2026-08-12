# Plan de PRs — Post Live Ops (land + residual)

> **As of:** 2026-08-11  
> **SSOT gates:** `docs/CURRENT_STATE.md`  
> **Live Ops design:** `docs/design/LIVE_OPS_DEMO_KERNEL.md`

## Stack A — Land (thin branch)

| PR | Title | Done when |
|----|-------|-----------|
| **A1** | `feat(live-ops): status/decide/export-acta API` | HTTP live + traversal tests green |
| **A2** | `feat(spa): primary acts → Live Ops` | `runLiveAct` wired when served |
| **A3** | `feat(app): --demo-day + H1 docs` | presentador one-cmd |
| **A4** | `chore(ssot): CURRENT_STATE + make test-spa` | SSOT + CI pack |

## Stack B — Residual

| PR | Title | Done when |
|----|-------|-----------|
| **B1** | `fix(live-ops): live_ops_loopback decide honesty` | Credible field_ops card; fusion OFF |
| **B2** | `feat(spa): Último acto paths + preview` | Acta path / reasons visible |
| **B3** | `feat(live-ops): replay-third-party` | `POST /live/v1/replay-third-party` |
| **B4** | `chore(release): Live Ops markers` | `check_release_flags` asserts wire |
| **B5** | `docs(demo): START_HERE → --demo-day` | Unique third-party path |

## Rails

- No GO_Q invent · fusion OFF · no Tobarra KEEP reopen · loopback only

## Verify

```powershell
$env:PYTHONPATH = "."
make test-spa
python -m wildfire_front app --demo-day --json
python scripts/check_release_flags.py
```
