# GO_MES+ prep-only checklist (no flag flip)

> **As of:** 2026-08-13 eng snapshot  
> **Rule:** `GO_MES+` stays **false** until criteria are real. This file is **prep only**.  
> **Plan IDs:** W3-M1 / W4 stretch · companion `docs/B4_B5_UNBLOCK_CALENDAR.md` · probe `docs/B4_B5_STATUS.json`

## Definition (honest)

GO_MES+ requires **all** of (product rails — not marketing):

1. **2nd grade A ops** IF with in-repo scorecard (structural A + ROS/Vp in-band + documented Vp/ha + no silent k-fit)  
2. **O2 national path honesty** (FOI/partner response path — not inventing cadastre)  
3. **H1** path advanced (GO_Q complete preferred; at minimum eng-ready without invented acta)

## Open checklist

### B4 — 2nd grade A

| Item | Status | Owner | Note |
|------|--------|-------|------|
| Hellín `pending_external` | open | human | Cite + Alonso promote; not eng invent |
| Hellín scorecard in-tree | missing / null grade | eng+human | Probe sets grade null if absent |
| 2nd complete IF package from partner | open | human | Request via outreach |
| In-repo scorecard grade A for 2nd IF | open | eng after data | Do not hardcode A |
| Re-run `b4_b5_status_probe.py` after scorecards | open | eng | Writes `docs/B4_B5_STATUS.json` |

### B5 / O2

| Item | Status | Owner | Note |
|------|--------|-------|------|
| O2 national perimeter | BLOCKED_EXTERNAL | human | FOI/partner |
| CyL silence window respect | calendar | human | See B4_B5 calendar |
| EFFIS/CEMS open proxy | dual-track only | eng | **≠** official cadastre |
| No invent `official_national=true` | rail | eng | Probe stays false without evidence |

### H1 linkage

| Item | Status |
|------|--------|
| GO_Q | **partial** (human acta) |
| h1_slot | **not_booked** until Alonso books |
| GO_MES+ flip | **forbidden** in this prep doc |

## Explicit non-claims

- Not GO_MES+ true  
- Not grade A invented  
- Not O2 nacional closed  
- Not GO_Q complete without acta  
- fusion ON ≠ GO_MES+

## Commands

```bash
python scripts/b4_b5_status_probe.py
python scripts/check_release_flags.py   # GO_MES+ must stay false
```
