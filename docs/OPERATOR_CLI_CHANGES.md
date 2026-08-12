# Operator-facing CLI changes

| Campo | Valor |
|-------|--------|
| **As of** | 2026-08-10 (UX pass 5: **`app`** product SPA) |
| **Scope** | Product SPA (Leaflet + dashboard) + prior `map` / `brief` / hubs |
| **Rails** | Scientific/ML gates **frozen** (no fusion ON, no GO_Q invent, no metric retune) |

---

## Why

Operators and eng still hit a few high-friction walls after the operator UX plateau:

1. Typing `help` / `doctor` / `status` failed with an opaque argparse error (or the wrong “modo operario” spam).
2. Missing flags on **known** commands (e.g. `incident doctor` without `--inbox`) printed the cold-start operator hint — noise, not guidance.
3. `export-acta` / `replay-decide` without paths exited with a bare string and exit 1.
4. Bare `decide` used policy `default` without saying so (field silence rails need `field_ops`).
5. Bare `ml` / bare `incident` dumped argparse “required: SUBCOMMAND” with no role map.
6. Users type `version` as a COMMAND; only `--version` worked.
7. Typos (`ml predic`, `decied`) gave no “did you mean?”.

---

## What changed (operator-visible)

### Pass 5 — new capability: `app` (product SPA)

| Before | After |
|--------|--------|
| Map-only HTML or eng-only commander rebuild for demos | **`app`** → dark ops SPA: Leaflet + brief dashboard + Decision Card/ops when `--work-dir` present |
| Brief was text-only; map was map-only | One sellable surface for third-party demos (`docs/APP.md`) |

```text
python -m wildfire_front app
python -m wildfire_front app --work-dir outputs/incidents/_sla_measure --open
python -m wildfire_front spa --role field --json
```

Schema `wfd_product_app_v1`. Builders: `product/app_spa.py` ← `operator_ux` + `map_status`.

### Pass 4 — new capability: `map` (fire-status + FIRMS NRT)

| Before | After |
|--------|--------|
| No operator map of local fronts + external NRT hotspots on CLI | **`map`** → Leaflet HTML + `wfd_fire_status_map_v1`; local outbox GeoJSON + NASA FIRMS (key or public Europe CSV); explicit connectivity; never fake live points |
| “Tiempo real” conflated with ops perimeter | Honesty: NRT hotspots ≠ burned area; not tactical dispatch; fusion OFF |

See `docs/FIRE_STATUS_MAP.md`.

```text
python -m wildfire_front map --work-dir outputs/incidents/_sla_measure --no-live
python -m wildfire_front map --lat 40.9 --lon -3.1 --radius-km 40
```

### Pass 3 — new capability: `brief`

| Before | After |
|--------|--------|
| No professional one-screen partner/operator summary (only traffic-light `operator` board) | **`brief` / `resumen` / `summary` / `briefing`** — executive brief with gates, rails, next action, role playbook. JSON: **`wfd_operator_brief_v1`**. Roles: `operator` · `field` · `lab` · `decision`. |
| Root help / command map omit a “summary” product surface | **Discoverable** in `--help`, Start here line, and `commands` map |

```text
python -m wildfire_front brief
python -m wildfire_front brief --role lab --json
python -m wildfire_front resumen --role field
```

### Pass 1–2 (still in force)

| Before | After |
|--------|--------|
| `wildfire-front help` → invalid choice | **`help` / `commands` / `cmds` / `ayuda`** → role-grouped command map (exit 0). JSON: `wfd_cli_commands_v1` |
| `wildfire-front doctor` → invalid choice | **`doctor`** → ML lab pre-flight by default; **`doctor --inbox DIR`** → incident doctor; **`--target hub`** → routes only |
| `wildfire-front status` → invalid choice | **Bare `status`** → operator board; **`status --work-dir DIR`** → `incident status` |
| Missing `--inbox` on `incident doctor` | Contextual field hint (**no** “¿Buscabas el modo operario?”) |
| Unknown COMMAND | Hint lists **help / doctor / ensayo / next** (not only operator) |
| `export-acta` / `replay-decide` bare | **`print_error` + exit 2** with copy-paste examples |
| Bare `decide` | Short output notes policy **`default`** and points to **`--policy field_ops`** |
| Operator board quick help | Mentions **help**, **doctor**, **status** |
| Bare `ml` / `incident` | **Hub exit 0** (`wfd_ml_hub_v1` / `wfd_incident_hub_v1`) with copy-paste start lines |
| `version` as COMMAND | **`version` / `ver` / `about`** → same as `--version` |
| Typos / bare `ingest-geotiff` | **¿Quisiste decir?** + ingest required-args hint |
| Root `--help` | “Start here” line: bare default · help · doctor · hubs |

---

## Commands cheat (new / fixed)

```text
python -m wildfire_front                 # operator board (unchanged)
python -m wildfire_front brief           # professional brief + next action
python -m wildfire_front brief --role lab --json
python -m wildfire_front app             # NEW: dark ops SPA (Leaflet + dashboard)
python -m wildfire_front app --work-dir outputs/incidents/_sla_measure --open
python -m wildfire_front map --work-dir … --no-live   # map-only
python -m wildfire_front help            # command map
python -m wildfire_front doctor          # ML lab doctor
python -m wildfire_front doctor --inbox D:/drops
python -m wildfire_front status          # operator board
python -m wildfire_front status --work-dir outputs/incidents/IF1
python -m wildfire_front ml              # ML lab hub (exit 0)
python -m wildfire_front incident        # field hub (exit 0)
python -m wildfire_front version         # same as --version
python -m wildfire_front decide --policy field_ops
python -m wildfire_front export-acta --card path/to/fire_decision_card.json
python -m wildfire_front replay-decide --work-dir outputs/incidents/IF1
```

---

## Exit codes (usage / doctor)

| Situation | Exit |
|-----------|-----:|
| `commands` / `help` / operator board | 0 |
| `brief` / `resumen` / `summary` | 0 |
| `app` / `spa` / `console` (SPA build OK) | 0 |
| `app --work-dir` missing path | 2 |
| bare `ml` / bare `incident` (hubs) | 0 |
| `version` / `ver` / `about` | 0 |
| `doctor` (ML, structure report) | 0 (missing weights still 0) |
| `doctor --target incident` without `--inbox` | 2 |
| `doctor --inbox …` with FAIL checks | 1 |
| `export-acta` / `replay-decide` missing inputs | 2 |
| Forensic `replay_ok=false` | 2 |
| Unknown COMMAND / typo | argparse 2 + unknown-command hint (+ suggestions) |

---

## Unchanged (frozen)

- Operator cold start, `ensayo` / `next` / `checklist` / ABSTAIN plain language
- `ml_product_go` / field_ops fusion OFF / GO_Q partial honesty
- ML lab scorecard math, reject thr freeze, LOFO / W3 rails
- Incident runtime products and Decision Card fusion policy files
- Hub payload **reports** frozen gates; it does **not** flip them

---

## Tests

Real entrypoint (`wildfire_front.cli.main`):

- `tests/test_operator_ux.py` — help/commands, status routes, doctor hub, bare ml/incident hubs, version aliases, typo suggestions, ML gates freeze, export/replay exit 2, decide policy note
- `tests/test_product_app.py` — product SPA builders + CLI `app` / alias `spa`
- `tests/test_fire_status_map.py` — map + FIRMS fixture
- `tests/test_cli_report.py` — parser registers `commands` + `doctor`
- `tests/test_cli_ml_product.py` — ML list/show rails (unchanged contract)

```powershell
$env:PYTHONPATH = "."
python -m pytest tests/test_product_app.py tests/test_operator_ux.py tests/test_cli_report.py tests/test_cli_ml_product.py tests/test_decide_cli.py -q --tb=line
```

---

## See also

- `docs/APP.md` — product SPA (Leaflet + dashboard)
- `docs/FIRE_STATUS_MAP.md` — map-only CLI
- `docs/OPERATOR_UX_LOOP_LOG.md` — plateau iters 1–17 (operator path)
- `docs/MEGA_AUDIT_OPERATOR_CLI_20260805.md` — rails + inventory
- `docs/START_HERE.md` — human entry
