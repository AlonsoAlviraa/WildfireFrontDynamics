# Live Ops Demo Kernel

## Goal

Turn industrial SPA C2 from “copy CLI and open terminal” into a **loopback Live Ops Kernel**: with `app --serve` / `app --demo-day`, primary acts **Estado · Decidir · Acta** run real product code and show results in Último acto — without inventing GO_Q or flipping fusion.

## Endpoints (same-origin, loopback only)

| Method | Path | Implementation |
|--------|------|----------------|
| GET | `/live/v1/health` | `live_ops.handle_health` |
| POST | `/live/v1/status` | Lightweight outbox JSON (no `incident.pipeline` import) |
| POST | `/live/v1/decide` | `decide_from_request` · channel `live_ops_loopback` · `field_ops` · fusion OFF |
| POST | `/live/v1/export-acta` | `forensics.write_forensic_bundle` |
| POST | `/live/v1/replay-third-party` | Pack forensic replay (`replay_ok` consistency only) |

Body: `{ "work_dir": "<rel under repo>", "policy_id": "field_ops", "event_id": "…" }`  
Path allowlist: resolve under serve `live_base_dir` (default `cwd` / repo). Rejects `..`, missing dirs, escapes.

## CLI

```powershell
python -m wildfire_front app --fire _sla_measure --serve
python -m wildfire_front app --demo-day          # default fire + pack/reliability checks + serve
python -m wildfire_front app --demo-day --json   # CI snapshot (no hang)
```

## Honesty rails (always)

- `field_ops_ml_live_fusion = OFF`
- `go_q_invent_forbidden = true` · demo-day never sets `go_q_met`
- Not tactical dispatch · IoU ≠ ROS · FIRMS ≠ perimeter
- No free-form shell from browser (fixed argv / importable functions only)

## Code

- `wildfire_front/product/live_ops.py` — handlers + dispatch + demo-day artifact checks  
- `wildfire_front/cli_app.py` — `_SafeSPARequestHandler` live routes · `--demo-day`  
- `wildfire_front/product/app_spa.py` — `live_ops` payload block  
- `wildfire_front/product/app_spa_html.py` — primary acts → `runLiveAct` when served  
- `tests/test_spa_live_ops.py`

## Non-goals

- GO_Q complete / signed acta invent  
- Fusion ON · cloud multi-tenant · offline basemap tiles  
