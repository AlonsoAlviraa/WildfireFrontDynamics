# Design — CLI de producto + camino enseñable (v7 teach-cli)

| Campo | Valor |
|-------|--------|
| **ID** | `DESIGN_CLI_TEACH_PRODUCT_V7` |
| **Horizon** | ~2 semanas eng (overlay post Graph **v6.1**) |
| **As of** | 2026-08-04 |
| **Status** | **SHIPPED** (2026-08-04) — PR1–PR5 in tree; re-review 0 open · check-work PASS |
| **Does not claim** | GO_Q · ml_product_go · field_ops ML fusion ON |
| **Depends on** | Graph v6.1 eng stack (E1–E3 pack/report/replay) **DONE** |

---

## 1. Problem / context

### 1.1 What is true today

Graph **v6.1** eng evidence is largely **DONE**:

| Track | State | Evidence |
|-------|-------|----------|
| E1 third-party pack | DONE | `scripts/build_demo_third_party_pack.py` → `outputs/demo_third_party/` + `dist/demo_third_party_*.zip` |
| E2 Reliability Report | DONE | `docs/RELIABILITY_GATE_REPORT_THIRD_PARTY.md` |
| E3 replay one-cmd | DONE | `scripts/run_third_party_replay.py` (exit 0 ⇔ `replay_ok`) |
| Course / teach path | DONE (docs) | `docs/CURSO_WFD_PARA_DESCONOCIDOS.md` §8.3 **4 actos** |
| START_HERE | DONE | `docs/START_HERE.md` |
| GO_MES | **true** | `docs/GO_MES_VERDICT.md` |
| GO_Q | **partial** | blocks on **human** H1/M3.2 (demo+acta), not more U-Net |

Rails (non-negotiable):

- `field_ops.allow_ml_live_in_fusion` = **false** (`config/decision_policies.json`)
- `ml_product_go` = **false**
- No invent anchors / Vp / ha
- Do **not** claim GO_Q from eng work alone

### 1.2 The product gap

Teaching and demos currently require **script archaeology**:

```text
python scripts/build_demo_multi_ccaa.py
python scripts/run_pilot_honesty_card.py ...
python scripts/build_demo_third_party_pack.py
python scripts/run_third_party_replay.py ...
python scripts/show_all.py
python -m wildfire_front decide ...
```

The product CLI (`python -m wildfire_front` / entrypoint `wildfire-front`) only exposes:

```text
demo | ingest-geotiff | incident | decide | serve-decide | export-acta | replay-decide
```

A newcomer (or the owner before a 12‑min call) cannot:

1. Print the **4-act learning path** with copy-paste commands from one CLI surface.
2. See a **gates snapshot** (GO_MES / GO_Q honesty) without opening JSON/docs.
3. Run **pack + optional replay** as a first-class product command with clear exit codes.
4. Read a Decision Card in **teach mode** (sources / weights / reasons expanded).

### 1.3 Conversation direction (authoritative)

Improve **CLI product surface + teachability**, not retrain ML or Hellín param spam.  
Human demo (H1) remains the GO_Q blocker; eng makes the path **impossible to miss**.

---

## 2. Goals and non-goals

### 2.1 Goals (acceptance = engineer ships without guessing)

| # | Goal | Acceptance criteria |
|---|------|---------------------|
| G1 | `wildfire-front teach` | Prints 4-act path + copy-paste PowerShell/bash-ish commands + doc pointers; exit 0; supports `--json` |
| G2 | `wildfire-front show` | Prints gates snapshot (GO_MES true / GO_Q partial honesty), fusion OFF, `ml_product_go` false, key paths to pack/report/course; optional open browser **off by default**; exit codes documented |
| G3 | `wildfire-front demo-third-party` | Thin wrapper: build pack + optional replay; exit codes match script contracts |
| G4 | `decide --explain` | Human-readable sources / weights / reasons / disclaimers / rails for teaching |
| G5 | Cheat sheet | `docs/CHEATSHEET_DEMO_12MIN.md` aligned with course 4 acts + 12 min guion |
| G6 | Cross-links | Light START_HERE + course pointers to teach CLI + cheat sheet |
| G7 | Tests | Unit/CLI tests for new commands + explain output shape |
| G8 | Plan overlay | Graph/status note for **v7 teach-cli** overlay — **does not claim GO_Q** |

### 2.2 Non-goals

| Non-goal | Why |
|----------|-----|
| ML retrain / U-Net hours | Graph v6.1 kill list |
| `field_ops` fusion ON / `ml_product_go=true` | Honesty rails |
| Invent H1 acta / fake third-party signature | GO_Q is human |
| O2 national unlock / Hellín grade A chase | External / eng-blocked stretch |
| New web app; Commander rewrite | Out of scope |
| 20 new subcommands | Max **3** new top-level + **1** flag on `decide` |
| Replace scripts with rewrites | Wrappers only; scripts remain source of truth |
| Make `show` rebuild hub/portal like `show_all.py` | Too heavy; `show` is **snapshot + pointers**, not full portal rebuild |

---

## 3. Current state

### 3.1 CLI surface (`wildfire_front/cli.py`)

| Command | Role |
|---------|------|
| `demo` | Synthetic e2e |
| `ingest-geotiff` | Batch LWIR → ops products |
| `incident` | doctor / update / watch / status |
| `decide` | Fire Decision Card; human output is **short** (decision, conf, policy, reasons joined) |
| `serve-decide` | HTTP POST `/v1/decide` |
| `export-acta` | Forensic bundle |
| `replay-decide` | Forensic hash verify (exit 2 if not ok) |

Global flags: `--json`, `--verbose` / `-v`, `--quiet` / `-q`.

Entry: `pyproject.toml` → `wildfire-front = wildfire_front.cli:main`.

### 3.2 Scripts that already implement product demos

| Script | Make target | Exit contract |
|--------|-------------|-----------------|
| `scripts/build_demo_third_party_pack.py` | `demo-third-party` | 0 ok; **2** if `self_replay_ok` false (pack still written); flags: `--output`, `--dist`, `--no-zip` |
| `scripts/run_third_party_replay.py` | `replay-third-party` | **0** `replay_ok`; **2** mismatch; **1** usage/missing/error; flags: `--bundle`, `--sources`, `--work-dir`, `--json`, `--quiet` |
| `scripts/dry_run_demo_third_party.py` | `dry-run-demo-third-party` | rebuild + replay + `DRY_RUN_REPORT.md` (human H3 still TODO) |
| `scripts/build_demo_multi_ccaa.py` | `demo-multi-ccaa` | multi-CCAA portal |
| `scripts/run_pilot_honesty_card.py` | `pilot-honesty` | ABSTAIN lesson |
| `scripts/show_all.py` | — | rebuilds reliability/hub/portal/commander + opens browsers (heavy) |

### 3.3 Course 4-act path (canonical narrative)

From `docs/CURSO_WFD_PARA_DESCONOCIDOS.md` §8.3:

| Acto | Comando mental | Mensaje |
|------|----------------|---------|
| 1 Ver | multi-CCAA HTML | mismos gates, 3 contratos |
| 2 Callarse | pilot honesty | field_ops se calla |
| 3 Decidir | `decide` | GO/HOLD/ABSTAIN |
| 4 Probar | pack + replay | rastro offline |

12‑min structure (curso M11 / GUION): gancho → multi-CCAA → honesty → pack/replay or Card → límites + H1.

### 3.4 Gate sources of truth (for `show`)

| Gate | Read from (priority) | Expected teach value |
|------|----------------------|----------------------|
| GO_MES | `docs/GO_MES_VERDICT.json` → fallback `docs/PLAN_1_MES_GRAPH_V6_STATUS.json` rails | `true` |
| GO_Q | status JSON gates / rails | `"partial"` (string) — **never** invent `true` |
| ml_product_go | status rails / MEMORY | `false` |
| field_ops ML fusion | `config/decision_policies.json` → `policies.field_ops.allow_ml_live_in_fusion` | `false` / OFF |
| GO_MES+ | status | `false` |

### 3.5 Decide card shape (already rich enough for `--explain`)

`fire_decision_card_v1` payload includes: `decision`, `confidence_pred`, `sources[]` (id, available, weight, confidence, actionable, metrics), `reasons[]`, `disclaimers[]`, `audit.policy_id`, `audit.policy_snapshot.allow_ml_live_in_fusion`, `metrics.allow_ml_live_in_fusion`.

Today CLI only prints a one-liner of reasons. Teaching needs a **table**, not more fusion logic.

---

## 4. Proposed design

### 4.1 Architecture principles

1. **Thin CLI, fat scripts/docs** — new commands orchestrate existing modules/scripts; no duplicate pack builders.
2. **Honesty by construction** — hardcode kill-list lines in teach/show output; read gates from repo JSON, never invent GO_Q=true.
3. **Stable exit codes** — same semantics as E1/E3 scripts where wrapping them.
4. **Offline-first** — default paths under repo; no network required for teach/show/demo-third-party.
5. **Spanish OK** for human stdout (matches START_HERE / curso); machine `--json` keys in English snake_case.
6. **≤3 new top-level commands** + 1 flag: `teach`, `show`, `demo-third-party`, `decide --explain`.

### 4.2 Module layout

| Path | Responsibility |
|------|----------------|
| `wildfire_front/cli_teach.py` | **New.** Argparse registration + run handlers for `teach`, `show`, `demo-third-party` |
| `wildfire_front/cli.py` | Register new commands via `register_teach_commands(commands, add_global_flags=...)`; wire `decide --explain` |
| `wildfire_front/product/teach_path.py` | **New.** Pure data: 4-act path, gate snapshot loader, explain-card formatter |
| `wildfire_front/cli_report.py` | Optional small helpers: `print_teach_report`, `print_show_report`, `print_decide_explain` (keep cli.py thin) |
| `docs/CHEATSHEET_DEMO_12MIN.md` | **New** 1-page cheat sheet |
| `docs/START_HERE.md` | Light link to `teach` + cheat sheet |
| `docs/CURSO_WFD_PARA_DESCONOCIDOS.md` | Light link: “CLI: `wildfire-front teach`” near §8.3 / Apéndice A |
| `docs/PLAN_1_MES_GRAPH_V6_STATUS.json` | Overlay note: track `T` teach-cli items (eng), **GO_Q unchanged** |
| `.grok/graph_engineering/STATE.md` | One paragraph: v7 teach-cli overlay under eng hygiene; primary product still H1 |
| `tests/test_cli_teach_product.py` | **New** CLI contract tests |
| `Makefile` | Optional aliases: `teach`, `show-gates` (not required if CLI is enough) |

**Repo root discovery:** reuse pattern from scripts — walk from `Path.cwd()` or package parent; prefer `Path(__file__).resolve().parents[1]` when running as installed package from monorepo checkout. Document: commands assume **cwd = repo root** (same as today).

### 4.3 Command: `wildfire-front teach`

#### 4.3.1 Purpose

Print the **4-act learning path** so a human can copy-paste and teach without opening the full course.

#### 4.3.2 CLI contract

```text
wildfire-front teach [--act N] [--json] [-v] [-q]
```

| Flag | Type | Default | Behavior |
|------|------|---------|----------|
| `--act` | int `{1,2,3,4}` | omitted = all | Print only that act |
| `--json` | bool | false | Machine payload |
| `-v` / `--verbose` | bool | false | Include “no decir” kill lines per act + full doc paths |
| `-q` / `--quiet` | bool | false | Minimal: act title + primary command only |

#### 4.3.3 Human stdout (default, all acts) — required content

Must include, in order:

1. **Header**
   - Title: `WFD teach path — 4 actos`
   - Rails one-liner: `GO_MES=true · GO_Q=partial · field_ops ML fusion=OFF · ml_product_go=false`
   - Setup block:
     ```powershell
     cd <repo>
     $env:PYTHONPATH = "."
     ```
2. **Acto 1 — Ver (multi-CCAA)**  
   - Commands: `python scripts\build_demo_multi_ccaa.py` then open `outputs\demo_multi_ccaa\index.html`  
   - Docs: `docs/design/DEMO_MULTI_CCAA_TOBARRA_NIJAR_CAMINOMORISCO.md`, `docs/START_HERE.md`
3. **Acto 2 — Callarse (pilot honesty)**  
   - Commands: `python scripts\run_pilot_honesty_card.py --fixture-root tests\fixtures\pilot` + open `outputs\pilot_honesty_card\index.html`  
   - Docs: `docs/PILOT_HONESTY_CARD.md`  
   - Message: field_ops can ABSTAIN while research_open is more permissive — **not a bug**
4. **Acto 3 — Decidir (Decision Card)**  
   - Commands:
     ```text
     python -m wildfire_front decide --list-policies
     python -m wildfire_front decide --policy field_ops
     python -m wildfire_front decide --policy field_ops --explain
     ```
   - Message: empty sources → ABSTAIN is correct
5. **Acto 4 — Probar (pack + replay)**  
   - Preferred product path: `python -m wildfire_front demo-third-party --replay`  
   - Equivalent scripts / make: `build_demo_third_party_pack` + `run_third_party_replay`; `make dry-run-demo-third-party`  
   - Docs: `docs/RELIABILITY_GATE_REPORT_THIRD_PARTY.md`, `docs/METRICS_HONESTY_IOU_NE_ROS.md`  
   - Honesty: `replay_ok` = forensic consistency, **not** crypto authenticity
6. **Footer**
   - Full course: `docs/CURSO_WFD_PARA_DESCONOCIDOS.md`
   - 12 min sheet: `docs/CHEATSHEET_DEMO_12MIN.md`
   - Next human gate: H1/M3.2 demo+acta → GO_Q (not eng)
   - Kill line: never claim field_ops ML live fusion ON

#### 4.3.4 JSON schema (`teach --json`)

```json
{
  "schema": "wfd_teach_path_v1",
  "rails": {
    "GO_MES": true,
    "GO_Q": "partial",
    "ml_product_go": false,
    "field_ops_ml_live_fusion": "OFF"
  },
  "setup": {
    "powershell": ["cd <repo_root>", "$env:PYTHONPATH = \".\""]
  },
  "acts": [
    {
      "id": 1,
      "name": "ver",
      "title": "Ver (multi-CCAA)",
      "message": "mismos gates, 3 contratos",
      "commands": ["python scripts/build_demo_multi_ccaa.py", "..."],
      "docs": ["docs/..."],
      "do_not_say": ["..."]
    }
  ],
  "next_human": "H1/M3.2 demo+acta (blocks full GO_Q)",
  "course": "docs/CURSO_WFD_PARA_DESCONOCIDOS.md",
  "cheatsheet": "docs/CHEATSHEET_DEMO_12MIN.md"
}
```

#### 4.3.5 Exit codes

| Code | When |
|------|------|
| **0** | Always (print-only; no side effects) |
| **1** | Invalid `--act` or unexpected error |

#### 4.3.6 Implementation notes

- Data lives in `teach_path.py` as constants (not scraped from markdown) so tests are deterministic.
- Optional: `--act` filters `acts` list.
- Do **not** run the demo commands; teach is documentation CLI.

---

### 4.4 Command: `wildfire-front show`

#### 4.4.1 Purpose

**Gates snapshot + honesty rails + key paths** for pre-demo / status check.  
Not a full portal rebuild (`scripts/show_all.py` stays for that).

#### 4.4.2 CLI contract

```text
wildfire-front show [--open] [--json] [-v] [-q]
```

| Flag | Default | Behavior |
|------|---------|----------|
| `--open` | false | Open **existing** HTML files in browser if present (multi-CCAA, pilot honesty, PORTAL) — **does not build** |
| `--json` | false | Machine snapshot |
| `-v` | false | Extra paths (Hellín scorecard, acta template, guion 30 min) |
| `-q` | false | Only gate lines |

#### 4.4.3 What to print (human default)

```text
=== WFD show — gates snapshot ===

Gates
  GO_MES:     true          (docs/GO_MES_VERDICT.md)
  GO_Q:       partial       (blocks: H1/M3.2 human demo+acta — NOT more ML)
  GO_MES+:    false
  ml_product_go: false
  field_ops ML live fusion: OFF

Rails
  invent_vp: false | joint_k Tobarra/Hellín: false | IoU≠ROS

Key paths
  Third-party pack:     outputs/demo_third_party/
  Pack zip:             dist/demo_third_party_*.zip
  Reliability report:   docs/RELIABILITY_GATE_REPORT_THIRD_PARTY.md
  IoU ≠ ROS:            docs/METRICS_HONESTY_IOU_NE_ROS.md
  Course:               docs/CURSO_WFD_PARA_DESCONOCIDOS.md
  Cheat sheet 12 min:   docs/CHEATSHEET_DEMO_12MIN.md
  START_HERE:           docs/START_HERE.md
  Acta template (H1):   docs/ACTA_DEMO_TERCERO_TEMPLATE.md
  Status JSON:          docs/PLAN_1_MES_GRAPH_V6_STATUS.json

Presence (filesystem)
  pack dir:     OK | MISSING
  multi-ccaa:   OK | MISSING
  pilot html:   OK | MISSING
  GO_MES json:  OK | MISSING

Next
  Eng: wildfire-front teach | wildfire-front demo-third-party --replay
  Human: H3 dry-run + H1 demo+acta → GO_Q  (eng cannot close GO_Q)
```

#### 4.4.4 Gate loading algorithm

```text
function load_gate_snapshot(repo_root) -> dict:
  rails = {}
  # 1) Prefer GO_MES_VERDICT.json if present
  # 2) Merge PLAN_1_MES_GRAPH_V6_STATUS.json rails + gates
  # 3) Read field_ops.allow_ml_live_in_fusion from config/decision_policies.json
  # 4) Defaults if missing files (fail soft with status="unknown" for that key):
  #      GO_MES default None → print "unknown (missing docs/GO_MES_VERDICT.json)"
  #      NEVER default GO_Q to true
  #      ml_product_go default false (safe fail-closed for claims)
  #      fusion default OFF
  return snapshot
```

**Honesty rule:** if status JSON is missing/stale, print `unknown` for GO_MES/GO_Q rather than inventing true. For fusion and ml_product_go, prefer **fail-closed false/OFF** when policy file is readable; if policy unreadable, print `unknown` and exit **0** still (show is observational) unless `--strict` (see open Q — default: no `--strict` in v7).

#### 4.4.5 JSON schema (`show --json`)

```json
{
  "schema": "wfd_show_snapshot_v1",
  "as_of_files": {
    "go_mes_verdict": "docs/GO_MES_VERDICT.json",
    "plan_status": "docs/PLAN_1_MES_GRAPH_V6_STATUS.json",
    "policies": "config/decision_policies.json"
  },
  "gates": {
    "GO_MES": true,
    "GO_Q": "partial",
    "GO_MES_plus": false,
    "ml_product_go": false,
    "field_ops_ml_live_fusion": "OFF"
  },
  "paths": {
    "demo_third_party": "outputs/demo_third_party",
    "reliability_report": "docs/RELIABILITY_GATE_REPORT_THIRD_PARTY.md",
    "course": "docs/CURSO_WFD_PARA_DESCONOCIDOS.md",
    "cheatsheet": "docs/CHEATSHEET_DEMO_12MIN.md",
    "acta_template": "docs/ACTA_DEMO_TERCERO_TEMPLATE.md"
  },
  "presence": {
    "demo_third_party": true,
    "demo_multi_ccaa_index": false,
    "pilot_honesty_index": false
  },
  "claims_forbidden": [
    "GO_Q complete without M3.2",
    "field_ops ML live fusion ON",
    "ml_product_go true",
    "replay_ok means cryptographic authenticity"
  ],
  "next_human": "H1/M3.2"
}
```

#### 4.4.6 Exit codes

| Code | When |
|------|------|
| **0** | Snapshot printed (even if pack missing) |
| **1** | Unexpected error |
| **2** | Only if future `--require-pack` (optional; **not in default v7**) |

Default: missing pack is **informational**, not failure (teach path may run show before building pack).

#### 4.4.7 Relationship to `scripts/show_all.py`

| | `wildfire-front show` | `scripts/show_all.py` |
|--|----------------------|------------------------|
| Rebuild hub/portal | No | Yes |
| Open browsers | Only with `--open` | Always |
| Gates honesty snapshot | **Yes (primary)** | No explicit GO_MES table |
| Time | &lt;1 s | minutes |

Document in teach footer and START_HERE: portal rebuild remains `python scripts/show_all.py`.

---

### 4.5 Command: `wildfire-front demo-third-party`

#### 4.5.1 Purpose

Product-facing **thin wrapper** for E1 pack (+ optional E3 replay) so demos do not require remembering script paths.

#### 4.5.2 CLI contract

```text
wildfire-front demo-third-party
    [--output DIR]
    [--dist DIR]
    [--no-zip]
    [--replay | --no-replay]
    [--skip-build]
    [--json]
    [-v] [-q]
```

| Flag | Default | Behavior |
|------|---------|----------|
| `--output` | `outputs/demo_third_party` | Pass-through to build script |
| `--dist` | `dist` | Zip directory |
| `--no-zip` | false | Skip zip |
| `--replay` | **true** if we want one-command evidence; see decision below | After build, run E3 replay |
| `--no-replay` | — | Build only |
| `--skip-build` | false | Only replay existing `--output` bundle (for re-check) |
| `--json` | false | Print summary JSON on stdout |

**Default decision (Key Decision D3):** `--replay` is **ON by default** so one command matches “pack + replay_ok” demo story. Use `--no-replay` for build-only (faster iter when iterating README).

#### 4.5.3 Implementation (subprocess, not reimport-required)

Prefer **subprocess** to existing scripts for isolation and identical exit codes:

```text
1. If not skip_build:
     run: python scripts/build_demo_third_party_pack.py
            --output <output> --dist <dist> [--no-zip]
     map rc_build ∈ {0, 2, other}
2. If replay (default) and (skip_build or rc_build in {0, 2}):
     # even if self_replay during build warned, still run E3 explicitly for clear demo
     run: python scripts/run_third_party_replay.py --bundle <output> [--json if -v?]
     map rc_replay ∈ {0, 1, 2}
3. Exit code aggregation (see 4.5.4)
```

Alternatively call `build_pack()` / `load_and_replay_bundle()` in-process — **acceptable** if tests import them; must preserve exit semantics. Prefer subprocess for parity with Make targets unless import is cleaner for unit tests. **Default eng choice: in-process import** of:

- `scripts/build_demo_third_party_pack.py` via `importlib` **or** extract thin `wildfire_front.product.demo_third_party` later  
- For v7: **importlib load of scripts** (same pattern as `tests/test_demo_third_party_pack.py`) to avoid package move.

#### 4.5.4 Exit codes (mandatory)

| Code | Meaning |
|------|---------|
| **0** | Build OK (if ran) **and** (no replay **or** `replay_ok`) |
| **1** | Usage / missing inputs / unexpected exception / bundle missing when `--skip-build` |
| **2** | Build wrote pack but `self_replay_ok` false **or** replay `replay_ok` false |

Aggregation rules:

```text
if skip_build and not output.is_dir(): exit 1
if build ran and rc_build not in (0, 2): exit 1   # hard failure
if build ran and rc_build == 2 and not replay: exit 2
if replay and rc_replay == 1: exit 1
if replay and rc_replay == 2: exit 2
if build rc_build == 2 and replay rc_replay == 0: exit 0
  # note: prefer trusting explicit E3; document that self_replay warning was cleared by E3
if all good: exit 0
```

#### 4.5.5 Human stdout

```text
demo-third-party
  build:  OK | WARN_REPLAY | FAIL
  out:    outputs/demo_third_party
  zip:    dist/demo_third_party_YYYYMMDD.zip | (skipped)
  decision: GO|HOLD|ABSTAIN  policy=field_ops
  fusion: OFF  ml_product_go=false
  replay_ok: True|False|(skipped)
  reliability_report: docs/RELIABILITY_GATE_REPORT_THIRD_PARTY.md
honesty: exit 0 = forensic consistency of pack — not cryptographic authenticity
```

#### 4.5.6 What this command must NOT do

- Flip policies or set fusion ON  
- Invent ops metrics (builder already uses Tobarra anchors + illustrative CEMS proxy — leave as-is)  
- Claim GO_Q  
- Run multi-CCAA or pilot honesty (those stay Act 1–2 scripts / teach pointers)

#### 4.5.7 Make target

Optional one-liner:

```make
demo-third-party-cli:  ## Product CLI wrapper (build+replay default)
	set PYTHONPATH=. && $(PYTHON) -m wildfire_front demo-third-party
```

Existing `demo-third-party` / `replay-third-party` / `dry-run-demo-third-party` **unchanged**.

---

### 4.6 Enhancement: `decide --explain`

#### 4.6.1 Purpose

Teaching mode: expand Decision Card so a human sees **why** GO/HOLD/ABSTAIN without reading raw JSON.

#### 4.6.2 CLI contract

```text
wildfire-front decide [existing flags...] [--explain]
```

| Flag | Behavior |
|------|----------|
| `--explain` | After building card, print **expanded human report** (ignored when `--json` — JSON already full) |

When `--json` and `--explain` together: emit full card JSON only (no dual format); `--explain` is no-op. Document that.

#### 4.6.3 Human report sections (order)

1. **Decision line** (existing): `decision`, `confidence_pred`, label, `policy`, `system_reliability_pass`, `latency_ms`
2. **Policy rails**
   - `policy_id`, `require_ops_for_go`, `allow_ml_live_in_fusion` (effective)
   - Explicit line: `field_ops ML live fusion: OFF` when policy is field_ops or effective flag false
3. **Sources table** (one row per `sources[]` entry)

   | Column | From |
   |--------|------|
   | id | `source.id` |
   | available | bool |
   | weight | float |
   | conf | confidence |
   | actionable | bool |
   | note | role / source_type / abstained / not_fused if weight==0 |

4. **Reasons** — bullet list (all, not truncated to 12 when `--explain`; still cap at 40 for safety)
5. **Disclaimers** — bullet list
6. **Teach footnote**
   - `ml_clm_ensemble` weight 0 = holdout provenance, not live certainty  
   - IoU ≠ ROS (`docs/METRICS_HONESTY_IOU_NE_ROS.md`)  
   - ABSTAIN is a feature  

#### 4.6.4 Implementation

```text
# in cli.py decide branch, after payload = decide_from_request(...):
if as_json:
    print_json(payload)
elif args.explain:
    print_decide_explain(payload)  # new in cli_report or teach_path
else:
    # existing short print
```

Pure function:

```python
def format_decide_explain(card: dict[str, Any]) -> str: ...
```

No changes to fusion math, policies, or API schema.

#### 4.6.5 Exit codes

Unchanged: decide remains exit **0** on successful card (including ABSTAIN). Exit 1 only on hard errors.

#### 4.6.6 Examples (acceptance fixtures)

```powershell
# Empty → ABSTAIN + explain why no sources
python -m wildfire_front decide --policy field_ops --explain

# ML holdout present but not fused under field_ops
python -m wildfire_front decide --use-ml-v34 --policy field_ops --explain

# Research path (still not tactical)
python -m wildfire_front decide --use-ml-v34 --policy research_open --explain
```

---

### 4.7 Doc: `docs/CHEATSHEET_DEMO_12MIN.md`

#### 4.7.1 Structure (1 page, scannable)

```markdown
# Cheatsheet demo 12 min — WFD

## Rails (decir en voz alta)
GO_MES true · GO_Q partial · fusion OFF · ml_product_go false · ABSTAIN = feature

## Setup
cd repo; PYTHONPATH=.

## Timeline 12 min
| Min | Acto | Qué haces | Comando / path |
...

## 4 actos (copy-paste)
### 1 Ver ...
### 2 Callarse ...
### 3 Decidir ...
### 4 Probar ...  → wildfire-front demo-third-party

## Kill list (5)
...

## Después de la call
Acta: docs/ACTA_DEMO_TERCERO_TEMPLATE.md
No marcar GO_Q sin H1 firmada.
```

Must align with:

- Course §8.3 four acts  
- Course M11 12‑min structure  
- `docs/GUION_DEMO_30MIN_POST_O1.md` 12‑min row  
- Product CLI names from this design  

#### 4.7.2 Length target

≤ ~120 lines; no essays; tables over prose.

---

### 4.8 Cross-links (light)

#### `docs/START_HERE.md`

Add section near top (after “Qué es esto” or in “Documentos clave”):

```markdown
## Camino enseñable (CLI v7)

```powershell
python -m wildfire_front teach
python -m wildfire_front show
python -m wildfire_front demo-third-party
python -m wildfire_front decide --policy field_ops --explain
```

Cheat sheet 12 min: `docs/CHEATSHEET_DEMO_12MIN.md`  
Curso completo: `docs/CURSO_WFD_PARA_DESCONOCIDOS.md`
```

#### `docs/CURSO_WFD_PARA_DESCONOCIDOS.md`

Near §8.3 / Apéndice A, add:

> **CLI producto:** `python -m wildfire_front teach` imprime esta ruta.  
> **Cheatsheet 12 min:** `docs/CHEATSHEET_DEMO_12MIN.md`.

Do not rewrite the whole course.

#### Epilog in `cli.py` `_EPILOG`

Add 3 example lines for teach / show / demo-third-party.

---

### 4.9 Graph / plan status overlay (v7 teach-cli)

#### 4.9.1 Status JSON patch (`docs/PLAN_1_MES_GRAPH_V6_STATUS.json`)

Add under `tracks` (new lightweight track **T** = teach/product CLI):

```json
"T": {
  "role": "teach_cli_overlay_v7",
  "items": {
    "T1_teach_cmd": "TODO|DONE",
    "T2_show_cmd": "TODO|DONE",
    "T3_demo_third_party_cli": "TODO|DONE",
    "T4_decide_explain": "TODO|DONE",
    "T5_cheatsheet_12min": "TODO|DONE",
    "T6_crosslinks_tests": "TODO|DONE"
  },
  "note": "Eng teachability overlay. Does NOT flip GO_Q. Primary product gate remains H1/M3.2."
}
```

Keep:

```json
"rails": { "GO_Q": "partial", ... }
"gates": { "GO_Q": { "met": false, "status": "partial" } }
```

Optional `next_72h` bullet:

```text
"Eng optional: ship teach-cli v7 (teach/show/demo-third-party/explain) — does not close GO_Q"
```

#### 4.9.2 Graph STATE.md

One short paragraph under hygiene / stretch eng:

> **v7 teach-cli overlay:** product CLI `teach` / `show` / `demo-third-party` + `decide --explain` + cheatsheet. Improves teachability of v6.1 evidence stack. **Does not claim GO_Q.**

Do not bump graph mode to v7 as a GO claim — mode can remain **v6.1** with overlay note, or label `v6.1+teach-cli` without changing GO rails.

#### 4.9.3 CHANGELOG

One entry under Unreleased: teach-cli product surface.

---

### 4.10 Tests

#### File: `tests/test_cli_teach_product.py`

| Test | Assert |
|------|--------|
| `test_teach_exit_0_and_acts` | `main(["teach"])` → stdout contains Acto 1–4 keywords + fusion OFF; exit via SystemExit/return 0 |
| `test_teach_act_filter` | `--act 3` omits multi-ccaa, includes decide |
| `test_teach_json_schema` | `--json` parses; `schema == wfd_teach_path_v1`; 4 acts |
| `test_show_reads_gates` | With real repo files, GO_MES true / GO_Q partial / fusion OFF in output |
| `test_show_json_never_go_q_true` | Parsed `gates.GO_Q` is not `True` / `"true"` complete claim |
| `test_show_missing_pack_ok` | Monkeypatch absence of pack → exit 0, presence false |
| `test_demo_third_party_skip_build_missing` | `--skip-build --output tmp_empty` → exit 1 |
| `test_demo_third_party_replay_ok` | Use existing fixture pack from `tests` if available, or build to tmp (may mark `@pytest.mark.slow` if heavy); assert exit 0 and `replay_ok` |
| `test_decide_explain_abstain` | `decide --policy field_ops --explain` stdout has Sources / Reasons / ABSTAIN |
| `test_decide_explain_with_json_noop` | `--json --explain` still pure JSON card |
| `test_parser_help_lists_new_commands` | `build_parser().parse_args` / help text includes teach, show, demo-third-party |

**Reuse:** patterns from `tests/test_demo_third_party_pack.py`, `tests/test_decide_api.py` (CLI channel).

**CI budget:** teach/show pure unit; demo-third-party full build may share existing pack test (avoid double full rebuild — call `build_pack(tmp)` once and wrap CLI).

#### Doc tests

No need for markdown lint. Optional: assert `CHEATSHEET_DEMO_12MIN.md` exists and contains strings `Acto 1`, `demo-third-party`, `fusion`.

---

### 4.11 Flows

#### Flow A — First day learn (45 min)

```text
wildfire-front teach
  → run act 1 command
  → run act 2 command
  → wildfire-front decide --policy field_ops --explain
  → wildfire-front demo-third-party
  → wildfire-front show
```

#### Flow B — 5 min pre-call check

```text
wildfire-front show --open
# if pack missing:
wildfire-front demo-third-party
```

#### Flow C — Engineer PR acceptance

```text
pytest tests/test_cli_teach_product.py tests/test_demo_third_party_pack.py -q
python -m wildfire_front teach --json | python -c "import sys,json; json.load(sys.stdin)"
python -m wildfire_front show --json
```

---

## 5. Alternatives considered

| Alternative | Pros | Cons | Verdict |
|-------------|------|------|---------|
| Only improve docs (no CLI) | Zero code risk | Teach path still hidden; problem statement fails | Reject |
| `teach` as script only | Fast | Not on product entrypoint | Reject (script OK as secondary) |
| Fold show into `show_all.py` | One show concept | Heavy rebuild; wrong UX for gates | Reject; keep both |
| Many subcommands (`teach act1`, `gates`, `paths`, …) | Fine-grained | Violates “not 20 commands” | Reject |
| `decide --explain` as separate `explain-decide` | Clear name | Extra command; decide already owns card | Reject |
| Subprocess always vs importlib for pack | Subprocess = exact script | Windows quoting; slower | Prefer **importlib** like existing tests; subprocess OK fallback |
| Default `--no-replay` on demo-third-party | Faster builds | Misses demo story | Reject; default **replay ON** |
| Auto-claim GO_Q when pack green | Tempting metric | Dishonest; H1 required | **Hard reject** |

---

## 6. Risks / honesty rails

| Risk | Mitigation |
|------|------------|
| Engineer or operator claims GO_Q because teach-cli shipped | teach/show footer + status JSON note + tests that GO_Q stays partial |
| `show` invents green gates if JSON missing | Print `unknown`; never default GO_Q true |
| Wrapper drifts from scripts | Import same `build_pack` / replay functions; one test path |
| `demo-third-party` exit 0 misread as “third party signed” | Stdout honesty line every run |
| `--explain` truncates critical reason | Cap 40; print count if truncated |
| Windows paths in teach output | Prefer `scripts\` in PowerShell blocks; also show `python -m` forms |
| Scope creep into Commander/UI | Explicit non-goal |
| Slow CI from full pack rebuild | Share tmp pack with existing third-party tests; mark slow if needed |

**Kill list (must appear in teach -v and cheatsheet):**

1. No field_ops ML live fusion ON  
2. No ml_product_go true  
3. No invent Vp/ha  
4. No IoU = ROS  
5. No GO_Q without M3.2 human acta  
6. No replay_ok = crypto authenticity  

---

## 7. Testing plan

### 7.1 Unit / CLI

- `tests/test_cli_teach_product.py` as §4.10  
- Extend lightly if `cli_report` formatters need pure function tests without argparse

### 7.2 Regression

- Existing `tests/test_demo_third_party_pack.py` must stay green  
- Existing decide API tests unchanged  
- Manual: `python -m wildfire_front --help` lists new commands

### 7.3 Manual acceptance (eng, 15 min)

| Step | Pass |
|------|------|
| `teach` copy-paste act 3 | ABSTAIN + explain readable |
| `demo-third-party` | exit 0, `replay_ok: True` |
| `show` | GO_MES true, GO_Q partial, fusion OFF |
| Open cheatsheet | 12 min table matches course acts |
| Confirm GO_Q not flipped in status JSON | partial / met false |

### 7.4 Human (out of eng scope)

H3 dry-run + H1 demo+acta — **not** required to merge teach-cli PRs.

---

## 8. ## Key Decisions

| ID | Decision | Rationale |
|----|----------|-----------|
| **D1** | New top-level commands: `teach`, `show`, `demo-third-party` only | Matches goals; avoids command sprawl |
| **D2** | Implement handlers in `cli_teach.py` + pure data in `product/teach_path.py` | Keeps `cli.py` from growing further; testable pure formatters |
| **D3** | `demo-third-party` **defaults to replay ON** (`--no-replay` to skip) | One-command evidence story = pack + replay_ok |
| **D4** | `show` is **snapshot + paths**, not portal rebuild | `show_all.py` remains heavy path; show must be &lt;1 s |
| **D5** | Gates: read JSON/policy files; **never invent GO_Q=true**; missing → `unknown` | Honesty rails |
| **D6** | `decide --explain` is a **presentation flag only** — no fusion/API schema change | Lowest risk teaching win |
| **D7** | Pack wrapper reuses E1/E3 code paths (importlib or direct functions); exit **0/1/2** aligned with scripts | Parity with Make / third-party tests |
| **D8** | Human stdout Spanish-friendly; `--json` English schema ids `wfd_teach_path_v1` / `wfd_show_snapshot_v1` | Project convention |
| **D9** | Graph overlay track **T** under v6.1; **do not** claim GO_Q or rename product GO | Plan honesty |
| **D10** | Cheat sheet path fixed: `docs/CHEATSHEET_DEMO_12MIN.md` | Single bookmark for 12 min demos |
| **D11** | `--open` on show is opt-in; never auto-open by default | Non-destructive CLI; CI-safe |
| **D12** | Max 3 new commands + 1 flag; no Commander rewrite | Scope control |

---

## 9. ## Open Questions

| # | Question | Default if unanswered |
|---|----------|----------------------|
| Q1 | Should `demo-third-party` default `--replay` ON or OFF? | **ON** (D3) |
| Q2 | In-process import vs subprocess for pack build? | **importlib** of script module (like existing tests) |
| Q3 | Add `--strict` to `show` (exit 2 if pack missing)? | **No** in v7 |
| Q4 | Bump graph mode label to `v6.1+teach` vs keep `v6.1`? | Keep **v6.1** + overlay note in STATE |
| Q5 | Should `teach` detect OS and print bash vs PowerShell? | Print **PowerShell primary** (owner OS) + note `python -m` portable |
| Q6 | Makefile targets for teach/show? | **Optional**; CLI is enough for v7 |
| Q7 | Include dry-run report (`dry_run_demo_third_party`) under demo-third-party? | **No** — keep H3 script separate; teach points to `make dry-run-demo-third-party` |
| Q8 | Locale: force Spanish only? | Mixed OK; key rails words stay GO_MES/GO_Q/ABSTAIN |

---

## 10. ## PR Plan

Ordered, incremental. Each PR mergeable alone. **Max 5 PRs.**

### PR1 — Foundations: teach path data + `teach` + `show` + tests

| Field | Content |
|-------|---------|
| **Depends** | none |
| **Files** | `wildfire_front/product/teach_path.py` (new); `wildfire_front/cli_teach.py` (new); `wildfire_front/cli.py` (register); `wildfire_front/cli_report.py` (optional print helpers); `tests/test_cli_teach_product.py` (teach/show cases) |
| **Description** | Implement `teach` and `show` with flags/exit codes/JSON schemas per §4.3–4.4. Gate loader + 4-act constants. No pack wrapper yet. |
| **Acceptance** | `python -m wildfire_front teach` exit 0, acts 1–4 present; `show --json` has GO_Q partial / fusion OFF; pytest green; help lists commands |
| **Honesty** | Footer never claims GO_Q complete |

### PR2 — `demo-third-party` CLI wrapper

| Field | Content |
|-------|---------|
| **Depends** | PR1 (parser registration pattern) — soft; can land after if `cli_teach.py` exists |
| **Files** | `wildfire_front/cli_teach.py` (add command); `tests/test_cli_teach_product.py` (wrapper cases); optionally `Makefile` one target |
| **Description** | Thin wrapper §4.5: build pack + default replay; exit 0/1/2; human honesty line |
| **Acceptance** | `python -m wildfire_front demo-third-party --no-zip` exit 0 on clean repo; `--skip-build` missing → 1; tamper path still covered by existing pack tests |
| **Honesty** | Stdout: forensic consistency disclaimer |

### PR3 — `decide --explain`

| Field | Content |
|-------|---------|
| **Depends** | none strictly; can parallel PR1 if careful on `cli.py` conflicts — prefer after PR1 |
| **Files** | `wildfire_front/cli.py`; `wildfire_front/product/teach_path.py` or `cli_report.py` (`format_decide_explain`); `tests/test_cli_teach_product.py` |
| **Description** | Add `--explain` presentation only §4.6 |
| **Acceptance** | Empty `decide --policy field_ops --explain` shows ABSTAIN + sources empty/reasons; `--json --explain` pure JSON |
| **Honesty** | Footnote IoU≠ROS; fusion OFF visible for field_ops |

### PR4 — Docs: cheatsheet + cross-links

| Field | Content |
|-------|---------|
| **Depends** | PR1–PR3 ideally (so commands exist); can draft cheatsheet early with planned command names |
| **Files** | `docs/CHEATSHEET_DEMO_12MIN.md` (new); `docs/START_HERE.md`; `docs/CURSO_WFD_PARA_DESCONOCIDOS.md` (light); `wildfire_front/cli.py` `_EPILOG`; `CHANGELOG.md` |
| **Description** | 12‑min 1-pager aligned with 4 acts; START_HERE + course pointers |
| **Acceptance** | Cheatsheet contains 4 actos, `teach`, `demo-third-party`, kill list, acta path; START_HERE links work |
| **Honesty** | Explicit “no GO_Q without H1” |

### PR5 — Graph/status overlay + Makefile polish

| Field | Content |
|-------|---------|
| **Depends** | PR1–PR4 (mark T* DONE) |
| **Files** | `docs/PLAN_1_MES_GRAPH_V6_STATUS.json`; `.grok/graph_engineering/STATE.md`; optional `Makefile`; optional `docs/INFORME_TRIMESTRE_2026_Q_PRODUCTO.md` one-line “teach-cli eng” if desired |
| **Description** | Track **T** items DONE; note overlay; **GO_Q remains partial**; next_72h human H1 still primary |
| **Acceptance** | Status JSON still `GO_Q.met: false`; T items done; STATE mentions teach-cli without claiming GO_Q |
| **Honesty** | **Mandatory review:** no gate flips |

---

### PR dependency graph

```text
PR1 (teach+show)
  ├──► PR2 (demo-third-party)
  ├──► PR3 (decide --explain)
  └──► PR4 (docs) ──► PR5 (status overlay)
```

PR2 and PR3 can proceed in parallel after PR1.  
If staffing is one engineer: **PR1 → PR3 → PR2 → PR4 → PR5** (explain is smaller/higher teach value mid-path).

---

## 11. Implementation sketch (for PR1 — no ambiguity)

### 11.1 `register_teach_commands` signature

```python
def register_teach_commands(
    commands: argparse._SubParsersAction,
    *,
    add_global_flags: Callable[[argparse.ArgumentParser], None],
) -> None: ...
```

### 11.2 `main` dispatch additions

```python
if args.command == "teach":
    return run_teach(args)  # sys.exit inside or raise SystemExit(code)
if args.command == "show":
    return run_show(args)
if args.command == "demo-third-party":
    raise SystemExit(run_demo_third_party(args))
```

Note: existing `main` uses bare `return` (exit 0) and `raise SystemExit(n)` for errors. Match that style. For `demo-third-party`, always `raise SystemExit(code)` including 0 for consistency with replay tools — **or** return on 0; pick one: **`raise SystemExit(code)` always** for this command so 2 propagates cleanly.

### 11.3 Repo root helper

```python
def repo_root() -> Path:
    # wildfire_front/product/teach_path.py → parents[2] = repo
    return Path(__file__).resolve().parents[2]
```

CLI may also accept cwd if files not found (document: run from repo root).

---

## 12. Success metrics (eng, 2 weeks)

| Metric | Target |
|--------|--------|
| New top-level commands | 3 (`teach`, `show`, `demo-third-party`) |
| New decide flag | 1 (`--explain`) |
| Tests green | `test_cli_teach_product` + existing third-party pack |
| Time to first teach path | `teach` &lt; 1 s |
| Time to evidence | `demo-third-party` one command → replay_ok |
| GO_Q claim | **still false/partial** after all PRs |

---

## 13. References (repo)

| Path | Role |
|------|------|
| `wildfire_front/cli.py` | CLI entry |
| `config/decision_policies.json` | field_ops fusion OFF |
| `docs/CURSO_WFD_PARA_DESCONOCIDOS.md` | 4 actos + 12 min |
| `docs/START_HERE.md` | On-ramp |
| `docs/GO_MES_VERDICT.md` | GO_MES true |
| `docs/PLAN_1_MES_GRAPH_V6_STATUS.json` | rails / GO_Q partial |
| `scripts/build_demo_third_party_pack.py` | E1 |
| `scripts/run_third_party_replay.py` | E3 |
| `docs/RELIABILITY_GATE_REPORT_THIRD_PARTY.md` | E2 |
| `docs/ACTA_DEMO_TERCERO_TEMPLATE.md` | H1 template |
| `docs/GUION_DEMO_30MIN_POST_O1.md` | Demo script |
| `docs/FIRE_DECISION_CARD.json` | Card shape sample |

---

*Design complete. Engineer can implement PR1 without guessing flags, exit codes, or honesty rails.*
