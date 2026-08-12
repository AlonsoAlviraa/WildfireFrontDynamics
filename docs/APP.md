# Product SPA — WFD OPS CONSOLE

| Campo | Valor |
|-------|--------|
| **As of** | 2026-08-11 |
| **Entry** | `python -m wildfire_front app` |
| **Schema** | `wfd_product_app_v1` |
| **UI** | Stitch «WFD Industrial C2» · dual-mode Fácil/Pro |
| **Builders** | `operator_ux` brief · `map_status` Leaflet payload · `fire_catalog` |
| **Rails** | field_ops ML fusion **OFF** · not tactical dispatch · no GO_Q invent · IoU ≠ ROS |

---

## What it is

A **sellable industrial ops console** (EOC / C2 / GIS density) for third-party demos — not a raw CLI wall.

**Industry stress UX** (`docs/design/EMERGENCY_UX_INDUSTRY.md`):

1. **Dual mode** — Fácil default; Pro one click (no feature cut).
2. **Priority first** — 3 primary acts always visible (**Estado · Decidir · Acta**).
3. **One task** — progressive disclosure (accordion actions, tabs).
4. **Touch ≥48px** · short labels · color-coded GO/HOLD/ABSTAIN.
5. **Defaults** — richest fire auto-selected · rebuild bound to work-dir.
6. **Offline-critical** — static SPA + local GeoJSON (tiles need network).

**UI tokens (Stitch Industrial C2):** bg `#0B1220` · panel `#111827` · IBM Plex Sans · map-first ~68%.

---

## One command

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "."
$env:PYTHONIOENCODING = "utf-8"

# Listar incendios descubiertos
python -m wildfire_front app --list-fires

# Consola en un incendio (recomendado)
python -m wildfire_front app --fire _sla_measure --open
# o:
python -m wildfire_front app --work-dir outputs/incidents/_sla_measure --open

# Sin work-dir: elige el mejor incendio del catálogo automáticamente
python -m wildfire_front app --open

# Role + JSON
python -m wildfire_front app --role field --fire _sla_measure --json

# Aliases (same as app)
python -m wildfire_front spa --open
python -m wildfire_front console --fire _sla_measure --open

# Opcional: servir SPA por HTTP local (evita file://; Ctrl+C para parar)
python -m wildfire_front app --fire _sla_measure --serve
python -m wildfire_front app --serve --port 8766
```

Artifacts (default `outputs/app/`):

| File | Content |
|------|---------|
| `index.html` | Self-contained SPA (Leaflet CDN + inline payload) |
| `app_payload.json` | Full `wfd_product_app_v1` model |

---

## Shell layout

```
┌─ top 48px: W WFD OPS | incidente | chips | Fácil|Pro | ? ─┐
│ map ~68%                             │ rail ≤380px         │
│  HUD + legend + FAB                  │ GO/HOLD/ABSTAIN     │
│                                      │ KPI 2×2             │
│                                      │ next one-liner      │
│                                      │ Estado|Decidir|Acta │
│                                      │ Abrir | Mapa        │
│                                      │ tabs + content      │
└──────────────────────────────────────┴─────────────────────┘
```

| Zone | Behaviour |
|------|-----------|
| **Primary acts** | `btn-act-status` · `btn-act-decide` · `btn-act-acta` — copy CLI bound to selected fire |
| **Último acto** | Panel with last copied cmd + timestamp (+ optional outbox snapshot); **no** shell-exec from browser |
| **Role seg** | Ops · Campo · Lab · Decisión — Pro rebuild includes `--role`; Fácil shows label/hint |
| **Fácil** | CLI hidden (`.adv`); plain CTAs + toast |
| **Pro** | Shows raw `python -m wildfire_front …` in actions/intake; optional bridge refresh |
| **Tabs** | Overview · Decisión · Acciones · Nuevo · Términos · Lista |
| **Acciones** | Full `product_actions` inventory (~35 CTAs); accordion + Copiar |

Inventario de CTAs: `wildfire_front/product/fire_catalog.product_action_catalog` + plain layer `plain_language.py`.

La SPA es **estática** por defecto. Con `--all-fires` / `--pack-fires` el selector cambia IF **empaquetados** en cliente (cap 8); fuera del pack = regenerar (Abrir consola).

---

## Flags

| Flag | Default | Notes |
|------|---------|--------|
| `--work-dir DIR` | none | Reads outbox GeoJSON, `fire_decision_card.json`, `operational_metrics.json` |
| `--fire ID` | none | Catalog id from `--list-fires` |
| `--list-fires` | off | Print catalog and exit |
| `--output DIR` | `outputs/app` | HTML + JSON |
| `--role` | `operator` | `operator` · `field` · `lab` · `decision` (also UI role-seg) |
| `--geojson PATH` | — | Extra layers (repeatable) |
| `--open` | off | Open browser (`file://` on `index.html`) |
| `--serve` | off | After write: **loopback-only** (`127.0.0.1`) HTTP on **output_dir only**; path traversal rejected; no CORS; open `http://127.0.0.1:PORT/` (Ctrl+C stop). Never binds `0.0.0.0` by default. **Live Ops ON**: same-origin `POST /live/v1/{status,decide,export-acta}` run real product code (work_dir allowlisted under repo; fusion OFF). |
| `--demo-day` | off | H1 presentador one-shot: default fire `_sla_measure`, Live Ops, check third-party pack + reliability paths, print 5-line card, serve SPA. **Does not set GO_Q.** Implies serve (use `--json` for CI snapshot without hang). |
| `--port` | `8766` | Port for `--serve` / `--demo-day` (not `serve-decide` 8765) |
| `--bridge-decide URL` | off | Optional live Decision Card bridge (**hostname** must be exactly `127.0.0.1` / `localhost` / `::1`). With **`--serve`**, SPA proxies same-origin `POST /bridge/v1/decide` → upstream (avoids browser CORS). Pro «Refrescar card»; silent offline fallback. Pair with `serve-decide --base-dir <repo>` so relative `work_dir` resolves. No fusion. Prefer **Live Ops** `/live/v1/decide` (built-in) over external bridge for demos. |
| `--all-fires` / `--pack-fires` | off | Multi-IF pack (client switch hero/map; cap N) |
| `--pack-cap N` | `8` | Max fires in pack (hard max 8) |
| `--live` | off | Attempt FIRMS network |
| `--no-live` | — | Explicit offline |
| `--fixture-csv` | — | Offline FIRMS points for CI / air-gap |
| `--lat` / `--lon` / `--bbox` | — | Map focus / FIRMS bbox |
| `--ui-mode` | `simple` | `simple` (Fácil) · `advanced` (Pro) |
| `--json` | off | Print full payload to stdout |
| `--title` | `WFD OPS` | HTML title |

---

## Honesty (always on HTML + JSON)

- **Not** validated tactical dispatch  
- Thermal mask / WFD envelope ≠ official extinction perimeter  
- FIRMS NRT hotspot ≠ burned area (latency hours, not radio ops)  
- field_ops **ML fusion OFF** (app does not enable fusion)  
- **GO_Q** never invented complete — residual is human H1 when partial  
- **ABSTAIN** is product behaviour, not a crash  

---

## Code

| Module | Role |
|--------|------|
| `wildfire_front/product/app_spa.py` | `build_product_app_payload` · `write_product_app` |
| `wildfire_front/product/app_spa_html.py` | Industrial C2 HTML renderer |
| `wildfire_front/product/live_ops.py` | Live Ops Kernel: status / decide / export-acta |
| `wildfire_front/product/fire_catalog.py` | Fire picker + `product_actions` inventory |
| `wildfire_front/product/operator_ux.py` | Brief / gates / next action |
| `wildfire_front/map_status/` | Local layers + FIRMS |
| `wildfire_front/cli_app.py` | CLI `app` / aliases `spa` · `console` · `--serve` / `--demo-day` |
| `tests/test_product_app.py` | Builders + real entrypoint |
| `tests/test_spa_live_ops.py` | Live Ops HTTP + path safety + demo-day rails |

Design refs:

- `docs/design/EMERGENCY_UX_INDUSTRY.md`
- `docs/design/stitch_wfd_industrial/`
- `docs/design/LIVE_OPS_DEMO_KERNEL.md`

---

## Live Ops (loopback)

With `app --serve` (or `--demo-day`):

| Method | Path | Product path |
|--------|------|----------------|
| GET | `/live/v1/health` | Liveness + honesty rails |
| POST | `/live/v1/status` | Lightweight outbox JSON (state/card/ops; no heavy pipeline import) |
| POST | `/live/v1/decide` | `decide_from_request` · channel `live_ops_loopback` · **field_ops** · fusion OFF |
| POST | `/live/v1/export-acta` | `write_forensic_bundle` on work_dir outbox |
| POST | `/live/v1/replay-third-party` | Forensic pack replay (`replay_ok` = consistency, not crypto) |

Body: `{"work_dir": "outputs/incidents/_sla_measure", "policy_id": "field_ops"}`  
`work_dir` must resolve under the repo (or serve base); `..` rejected. No free-form shell from the browser.  
`file://` open: acts fall back to **copy CLI** (static mode).

---

## Demo script (third party, ~3 min)

1. `python -m wildfire_front app --demo-day`  (or `--fire _sla_measure --serve`)  
2. Point at **hero decision** + confidence (GO/HOLD/ABSTAIN).  
3. Tap **Estado · Decidir · Acta** — **live** results in Último acto (not only copy).  
4. Map: cyan = local front/envelope · pink = FIRMS if loaded.  
5. Rails chips: Fusion OFF · Live Ops · no despacho · NRT ≠ perímetro.  
6. **Do not claim** “we extinguish fires” or invent GO_Q complete.

Safe claim:

> “Decision support: thermal ops + open perimeters when available, explicit abstention when sources are weak — with an audit trail.”

---

## Tests

```powershell
$env:PYTHONPATH = "."
python -m pytest tests/test_product_app.py tests/test_spa_layout.py tests/test_plain_language_app.py tests/test_check_release_flags.py -q --tb=line
# or:
make test-spa
```

Release honesty gate (SPA markers · fusion OFF · GO_Q not true without H1):

```powershell
python scripts/check_release_flags.py
```

---

## See also

- `docs/AUDIT_AND_PR_PLAN_SPA_C2_20260811.md` — audit + residual G1–G10  
- `docs/FIRE_STATUS_MAP.md` — map-only CLI  
- `docs/OPERATOR_CLI_CHANGES.md` — operator CLI passes  
- `docs/START_HERE.md` — human entry (third-party = app)  
- `docs/CHEATSHEET_DEMO_12MIN.md` — full 12 min pitch  
- `docs/H1_GO_Q_RUNBOOK.md` — closing GO_Q (human)  
