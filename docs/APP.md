# APP — Product SPA (industrial C2)

Operator-facing SPA for WildfireFrontDynamics: map-first shell, Decision Card,
primary acts **Estado · Decidir · Acta**. **Not** tactical dispatch.

## Quick start

```powershell
cd <repo>
$env:PYTHONPATH = "."

# Build + open static HTML (copy-CLI path if Live Ops offline)
python -m wildfire_front app --fire _sla_measure --open

# Live Ops on loopback (POST /live/v1/*) — preferred for dry-run eng
python -m wildfire_front app --fire _sla_measure --serve
# → http://127.0.0.1:8766/

# H1 presenter one-shot (does NOT set GO_Q)
python -m wildfire_front app --demo-day

# Aliases
python -m wildfire_front spa --open
python -m wildfire_front console --fire _sla_measure --serve
python -m wildfire_front commands --json
```

## Live Ops (with `--serve`)

| Method | Path | Role |
|--------|------|------|
| GET | `/live/v1/health` | health |
| POST | `/live/v1/status` | lightweight outbox status |
| POST | `/live/v1/decide` | Decision Card via loopback channel |
| POST | `/live/v1/export-acta` | forensic acta |
| POST | `/live/v1/replay-third-party` | pack replay consistency |

Without serve: UI **copy-CLI fallback** (`liveUnavailableFallback`) — no bare HTTP 501.

Design: `docs/design/LIVE_OPS_DEMO_KERNEL.md`.

## Demo dry-run eng (A2 / A6)

1. Rails aloud: GO_MES true · GO_Q partial · fusion OFF · ABSTAIN = feature.
2. `app --serve --fire _sla_measure` (or `--demo-day`).
3. In browser: **Estado → Decidir → Acta** (Último acto shows result / path).
4. Offline path: open static SPA, same buttons → CLI copied, not invented GO_Q.
5. SPA panel **Ensayo H1 eng** (`data-marker="h1-rehearsal"`) shows `go_q_met=false` always on this product surface — eng dry-run ≠ third-party acta.
6. SPA **Escala SR** (`data-marker="sr-ladder"`) is support/recommendation only — Claims Guardian non-claims (no field GO sell).
7. Cheatsheet: `docs/CHEATSHEET_DEMO_12MIN.md`.

## Honesty rails (UI)

- field_ops ML fusion **OFF**
- Confidence band = **prediction quality**, **no es ROS** · IoU ≠ ROS
- SPA marker `uncertainty-bar` / payload `uncertainty_bar`: fill from existing `confidence_pred` only (no invented scores, never ROS)
- Never invent GO_Q / scores / tactical dispatch claims
- Decision may **ABSTAIN** / **HOLD** (feature)

## Code map (Agent A ownership)

| Path | Role |
|------|------|
| `wildfire_front/product/app_spa.py` | payload builder |
| `wildfire_front/product/app_spa_html.py` | CSS / shell / JS |
| `wildfire_front/product/spa_honesty_ui.py` | Uncertainty bar + H1 eng / SR ladder / decision-log UI helpers |
| `wildfire_front/product/live_ops.py` | Live Ops handlers |
| `wildfire_front/cli_app.py` | `app` CLI + loopback server |
| `wildfire_front/map_status/**` | map payload / FIRMS / html map |
| `tests/test_spa_*.py`, `test_product_app.py`, … | SPA pack |
| `make test-spa` | pytest pack |

## Verify

```powershell
make test-spa
# or
python -m pytest tests/test_product_app.py tests/test_spa_layout.py tests/test_plain_language_app.py tests/test_check_release_flags.py tests/test_app_spa_security.py tests/test_spa_live_ops.py -q
```
