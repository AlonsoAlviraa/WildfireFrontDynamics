# MEGA AUDIT — Operator CLI / Product rails

| Campo | Valor |
|-------|--------|
| **As of** | 2026-08-05 |
| **Repo** | `C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics` |
| **Scope** | Product rails · CLI surface · operator/teach/ml tests · docs honesty · risks |
| **Method** | Read config + gate JSON + CLI modules + status docs; live `load_gate_snapshot()`; pytest scoped suite |
| **Honesty rule** | No invented `GO_Q=true`, no invented fusion ON, no inflated metrics |

---

## 1. Executive summary

| Dimension | Status | One-liner |
|-----------|--------|-----------|
| **Eng usability (operator CLI)** | **GREEN** | Bare CLI → operator; `ensayo` / `next` / `checklist`; eng checklist 7/7 design; UX loop plateau |
| **Product honesty rails** | **GREEN** | field_ops fusion **OFF**; `ml_product_go` **false**; GO_Q **partial**; live snapshot matches docs JSON |
| **Human / commercial gate** | **YELLOW** | H1 third-party demo + acta still open — eng cannot close GO_Q |
| **Docs consistency (numbers)** | **YELLOW** | Operator entry is aligned; CEMS pack counts and Hellín inventory row drift |
| **Overall eng ship readiness** | **GREEN** for demo path; **YELLOW** for GO_Q product close |

**Verdict for operators / eng day-use:** the repo is usable without tribal knowledge. One cold-start command surfaces traffic lights, four acts, and an explicit GO_Q human gap. Rails fail closed. Residual blockers are **human calendar (H1)** and **external data (O2, optional anchors)** — not missing CLI plumbing.

**What this audit does *not* claim:** GO_Q complete, field_ops ML live fusion ON, `ml_product_go=true`, GO_MES+, tactical dispatch readiness, or IoU as ROS.

---

## 2. Rails table

Sources checked (in load order used by `wildfire_front.product.teach_path.load_gate_snapshot`):

1. `docs/GO_MES_VERDICT.json`
2. `docs/PLAN_1_MES_GRAPH_V6_STATUS.json` (`rails` / `gates`)
3. `config/decision_policies.json` (authoritative for `field_ops.allow_ml_live_in_fusion`)
4. `docs/PLAN_ML_PRODUCT_STATUS.json` (ML lab rails; not a GO_Q flip source)

### 2.1 Live snapshot (this machine, 2026-08-05)

```text
GO_MES:                    true
GO_Q:                      partial
GO_MES_plus:               false
ml_product_go:             false
field_ops_ml_live_fusion:  OFF
presence.demo_third_party: true
presence.demo_multi_ccaa:  true
presence.pilot_honesty:    true
presence.go_mes_json:      true
presence.portal_html:      true
```

### 2.2 Policy matrix (`config/decision_policies.json`)

| Policy | `allow_ml_live_in_fusion` | `require_ops_for_go` | Role |
|--------|---------------------------:|----------------------|------|
| **default** | **false** | false | Historical product thresholds |
| **field_ops** | **false** | true | Emergency / GEACAM-style; ML-only → ABSTAIN |
| **research_open** | **true** (experimental) | false | Lab demos only — **not** field / tactical |
| **demo** | **false** | false | Labeled alias of default |

**field_ops detail (product rail under audit):**

| Field | Value |
|-------|------:|
| `allow_ml_live_in_fusion` | **false** |
| `ml_live_max_weight` | 0.2 |
| `ml_live_abstain_below` | 0.45 |
| `ml_live_veto_on_abstain` | false |
| `allow_ml_only_hold` | false |
| `go_ops_min` | 0.65 |

### 2.3 Gate documents

| Gate | Documented value | Evidence file | Audit read |
|------|------------------|---------------|------------|
| **GO_MES** | **true** (mínimo O1∧O4∧P1∧M2∧E1) | `docs/GO_MES_VERDICT.json` | Matches live snapshot |
| **GO_MES+** | **false** | same | O2 nacional / O5 2º grade A not claimed |
| **GO_Q** | **partial** | `PLAN_1_MES_GRAPH_V6_STATUS.json` rails + gates | **Not** true/complete |
| **ml_product_go** | **false** | plan rails + `PLAN_ML_PRODUCT_STATUS.json` | Fail-closed in code |
| **field_ops fusion** | **OFF** | `decision_policies.json` field_ops | Policy wins over plan string |
| **M3.2 (H1 demo)** | PENDING / TODO | plan `gates.M3.2`, track H1 | Human only |
| **M3.4 informe** | ENG_FILLED_HUMAN_FINAL | plan + `INFORME_TRIMESTRE_2026_Q_PRODUCTO.md` | Not full GO_Q alone |
| **U1 TEST honest** | true (lab) | ML status | ≠ product GO |

### 2.4 Code fail-closed behavior

| Mechanism | Behavior |
|-----------|----------|
| `load_gate_snapshot` | Default `ml_product_go=False`, fusion `"OFF"`; GO_Q never invented as true; missing → `"unknown"` |
| `operator_ux.go_q_missing_plain` | Complete only if GO_Q true/complete/done; else human checklist |
| `cli_ml` doctor / show | Asserts fusion OFF + `ml_product_go` false in human + JSON |
| CLI `--allow-ml-live-in-fusion` | Opt-in flag on `decide`; **does not** rewrite `field_ops` policy file |

**research_open fusion ON is intentional lab-only.** It must not be paraphrased as “fusion is on” for product/field claims.

---

## 3. CLI inventory

Entry: `python -m wildfire_front` / console `wildfire-front`  
Parser: `wildfire_front/cli.py` · teach/operator: `cli_teach.py` · ML: `cli_ml.py` · UX helpers: `product/operator_ux.py`

### 3.1 Bare default

```text
no args  →  argv rewritten to ["operator"]
```

Cold start lands on the operator board (semáforo + 4 actos + GO_Q gap). Invalid top-level COMMAND prints Spanish hint pointing to `ensayo` / `checklist` / `next`.

### 3.2 Top-level commands (13)

| Command | Module | Purpose |
|---------|--------|---------|
| `demo` | cli.py | Synthetic E2E demo |
| `ingest-geotiff` | cli.py | Thermal GeoTIFF batch → ops products |
| `incident` | cli_incident.py | doctor / update / watch / status |
| `ml` | cli_ml.py | ML **lab** product surface |
| `teach` | cli_teach.py | 4-act path print (no side effects) |
| `show` | cli_teach.py | Gates snapshot + paths (**no** portal rebuild) |
| `demo-third-party` | cli_teach.py | E1 pack + E3 replay wrapper |
| `dry-run-h3` | cli_teach.py | Eng H3 path; does **not** flip GO_Q |
| `operator` | cli_teach.py + operator_ux | **Primary non-code entry** |
| `decide` | cli.py + decide_service | Decision Card GO/HOLD/ABSTAIN |
| `serve-decide` | cli.py | Local HTTP POST /v1/decide |
| `export-acta` | cli.py | Forensic acta + radio + replay sources |
| `replay-decide` | cli.py | Forensic hash verify |

### 3.3 Operator subcommands

| Subcommand | Behavior |
|------------|----------|
| *(default)* / `status` | Traffic-light board |
| `checklist` | 7-item eng checklist (session-aware) |
| `do --act N` | Run act 1–4 |
| `do --all` | Full ensayo 1→4; session stamp under `outputs/operator_ux_last_run.json` |
| `explain-abstain` | Plain-language ABSTAIN |
| `next` | What eng did vs human GO_Q gap |

Make targets: `operator`, `operator-checklist`, `operator-path`, `ensayo` (= path), `operator-next`.

### 3.4 Operator aliases & expansions (`cli.py`)

| Token | Expands / aliases to |
|-------|----------------------|
| `operador`, `ops`, `estado`, `semaforo` | `operator` |
| `ensayo`, `path` | `operator do --all` |
| `next`, `go_q`, `go-q` | `operator next` |
| `checklist` | `operator checklist` |

### 3.5 ML lab subcommands (`wildfire-front ml …`)

`list` · `show` · `predict` · `card` · `doctor` · `cases` · `curve` · `freeze` · `smoke` · `lofo` · `next`

Banner contract (help + runtime): **lab product · not field_ops fusion · IoU ≠ ROS**.  
Catalog holdout **0.8963** treated as **provenance only**.

### 3.6 Teach / demo path (eng)

| Command | Role |
|---------|------|
| `teach` | Docs-only 4 acts + rails |
| `show` | Gates + key paths; optional `--open` existing HTML only |
| `demo-third-party` | Pack + replay |
| `dry-run-h3` | Full eng dry-run report; `go_q_met` stays false by design |

### 3.7 Explicitly *not* the operator door

| Path | Role |
|------|------|
| `python scripts/show_all.py` | Heavy portal rebuild — **eng/lab**, labeled optional in START_HERE / README |
| `python scripts/build_commander_app.py` | Commander HUD — eng |
| `wildfire-front ml *` | Lab surface, not field promote |

---

## 4. Test results

Command (as scoped):

```powershell
$env:PYTHONPATH = "."
python -m pytest tests/test_operator_ux.py tests/test_cli_teach_product.py tests/test_cli_ml_product.py -q --tb=line
```

| Result | Value |
|--------|------:|
| **Exit code** | **0** |
| **Outcome** | **All passed** (progress `........................................................................ [ 98%] . [100%]`) |
| Collected | `test_operator_ux.py` **29** · `test_cli_teach_product.py` **18** · `test_cli_ml_product.py` **26** · **total 73** |

### 4.1 What the suite hard-guards

| Guard | Where |
|-------|--------|
| `ml_product_go is False` | teach show JSON, ml show/doctor/card/freeze/smoke/lofo/next |
| `field_ops.allow_ml_live_in_fusion is False` | ml product + policy file read |
| `field_ops_ml_live_fusion == "OFF"` | teach + ml snapshots |
| GO_Q **never** true/complete in show/teach payloads | `test_cli_teach_product.py` |
| Human help never prints `field_ops fusion: ON` | ml human paths |
| IoU ≠ ROS / lab banner language | ml list/help |
| Operator bare / aliases / checklist honesty | `test_operator_ux.py` |

**Note:** OPERATOR_UX_LOOP_LOG cites “47 passed” for operator+teach only; with ML product suite the scoped total is **73**. Both are consistent if scopes differ.

---

## 5. Docs consistency

### 5.1 Operator entry vs `show_all` (aligned)

| Doc | Operator first? | `show_all` framing |
|-----|-----------------|--------------------|
| `docs/START_HERE.md` | **Yes** — bare / operator / ensayo | “Portal (opcional, pesado)” |
| `README.md` | **Yes** — operator as 1-command start | “Portal / sala de mando (opcional, eng)” |
| `docs/ONEPAGER_COMERCIAL_ES.md` | **Yes** — bare + ensayo + checklist | Commander / `show_all` eng optional |
| `docs/OPERATOR_UX_LOOP_LOG.md` | Canonical loop; plateau iters 1–17 | Explicit residual: portal ≠ operator door |
| `docs/PROJECT_STATUS.md` | Operator UX listed under shippable eng | — |
| `MEMORY.md` | Operator UX PLATEAU; residual H1 | — |
| `docs/H1_GO_Q_RUNBOOK.md` | Prep via operator checklist | dry-run / pack for eng |

**Baseline trap (fixed in loop):** early START_HERE led with `show_all` and a 13-command help wall. Iterations 4–17 moved operator to the front. **Current docs no longer present `show_all` as the sole entry.**

### 5.2 Status docs honesty (gates)

| Claim area | Consistent? | Notes |
|------------|-------------|-------|
| GO_MES true (mínimo) | Yes | Verdict JSON + PROJECT_STATUS + MEMORY + H1 runbook |
| GO_Q partial | Yes | All primary status docs |
| field_ops fusion OFF | Yes | Policies + plans + cheatsheets + kill lists |
| ml_product_go false | Yes | Including promote records and lab freeze notes |
| GO_MES+ false | Yes | Stretch list explicit |
| Eng checklist ≠ H1 | Yes | Operator log + checklist honesty strings |

### 5.3 Doc drift / claim inflation risks (honest)

| Issue | Severity | Detail |
|-------|----------|--------|
| **CEMS pack count** | Medium | `START_HERE.md`: **11** packs / ~44377 ha · `README.md`: **4** packs / ~5300 ha. Do not pick the larger number for sales without recounting `outputs/open_if/*`. |
| **0.8963 without “provenance only”** | Low–Medium | START_HERE “Tres números” lists holdout IoU bare; README correctly says provenance. Prefer README framing. |
| **Hellín inventory row** | Medium | `PROJECT_STATUS` O1 says Hellín **confirmed**, but data inventory table still marks Hellín **pending_external**. Stale table — not a gate flip, but confuses auditors. |
| **MEMORY M3.4** | Low | MEMORY: “M3.4 informe pending”; plan gate: **ENG_FILLED_HUMAN_FINAL**. Prefer plan wording. |
| **Acta draft prefill** | OK if labeled | `ACTA_DEMO_PENDING_HUMAN.md` shows GO_MES=True / GO_Q=partial / fusion OFF and **NO firmado · NO cierra GO_Q**. Correct. |

No evidence in primary gate JSON of `GO_Q=true` or field_ops fusion ON.

---

## 6. Data / honesty — what is solid vs fragile

### Solid (cite freely with path)

- GO_MES mínimo components documented in `docs/GO_MES_VERDICT.json` (Tobarra grade A ratio, Hellín grade B in-band, P1 two-real smoke, catalog IoU provenance, CI/smokes).
- Dual product separation: ops ROS ≠ ML IoU (`METRICS_HONESTY_IOU_NE_ROS`, ML CLI banner).
- Decision Card empty sources → ABSTAIN under field_ops; explained in operator UX.
- Lab loop freeze: `lab_usable` without `ml_product_go` / field promote (`PLAN_ML_PRODUCT_STATUS.json`).
- LOFO mean IoU lower than U1 holdout (~0.76 vs ~0.86) — docs already warn not to over-claim single holdout.

### Fragile / do not inflate

- Catalog **0.8963** as live certainty or field confidence.
- **research_open** fusion ON as product default.
- `replay_ok` as cryptographic authenticity (teach kill list forbids this).
- Operator checklist 7/7 as “demo to third party done”.
- Optional CLI flag `--allow-ml-live-in-fusion` on a single `decide` call as “policy flipped”.
- Pack hectare maxima without pack inventory audit.

---

## 7. Risks / blockers

### H1 — GO_Q human (primary product blocker)

| Item | Status |
|------|--------|
| Runbook | `docs/H1_GO_Q_RUNBOOK.md` ready |
| Acta template / draft | `docs/ACTA_DEMO_TERCERO_TEMPLATE.md` · `docs/actas/ACTA_DEMO_PENDING_HUMAN.md` (unsigned) |
| Record script | `scripts/record_h1_demo_complete.py` (rejects placeholders) |
| Eng dry-run | `dry-run-h3` / pack present; human attestation pending |
| **GO_Q** | Remains **partial** until real external demo + signed acta |

**Eng cannot close GO_Q** by more ML, more loops, or more CLI features. Stated everywhere that matters.

### External data (secondary)

| ID | Status | Impact |
|----|--------|--------|
| **O2** perímetro nacional | BLOCKED / external | GO_MES+ / national Hausdorff path |
| **O5** second grade A | OPEN (Hellín remains B) | GO_MES+ only; not GO_MES minimum |
| Cardoso Vp / 3rd anchor | pending_external | Optional multi-anchor strength |
| CyL / GAL silence rules | wait / process | Outreach calendar, not CLI |
| Gmail MCP OAuth | expired (status note) | Outreach tooling only |

### Engineering residual (non-blocking for operator UX)

- Heavy multi-CCAA rebuild not needed if artifacts exist (`--no-build`).
- Not all repo scripts under `operator` (by design: 4 demo acts only).
- ML W3 signal / Hellín patches: lab track; does not flip rails.

---

## 8. Top 5 frictions remaining (ranked)

Operator UX eng loop self-declares **PLATEAU** (iters 1–17); residual is mostly **outside code**. Remaining frictions ranked for a real operator / auditor:

| Rank | Friction | Type | Severity | Notes |
|-----:|----------|------|----------|-------|
| **1** | **H1 third-party demo + signed acta** | Human | High | Only path to GO_Q complete |
| **2** | **Doc number drift (CEMS packs, Hellín inventory)** | Docs | Medium | Can produce accidental claim inflation if START_HERE/table copied into pitches |
| **3** | **`--help` still shows 13 commands** after operator is default | UX | Low | Bare default fixed cold start; curious users still see a large surface |
| **4** | **PYTHONPATH / install ritual** | Env | Low–Medium | Docs assume `$env:PYTHONPATH="."` or editable install; not zero-setup for all machines |
| **5** | **`decide --allow-ml-live-in-fusion` opt-in flag** | Honesty edge | Low | Correct as escape hatch; risk if demos use it without labeling experimental |

No eng friction found that blocks: open board → run 4 acts → know GO_Q gap, given artifacts already on disk.

---

## 9. Recommended CLI improvements (concrete, minimal)

Only if reopening the UX loop; **do not** claim these as required for GO_Q.

1. **Sync doc numbers** (not CLI code): reconcile CEMS pack count/ha between START_HERE and README; fix Hellín row in PROJECT_STATUS inventory; align MEMORY M3.4 with ENG_FILLED.
2. **START_HERE “Tres números”**: always suffix holdout IoU with “provenance only · not live certainty · not ROS”.
3. **Optional help grouping**: in argparse description/epilog, one line “Operario: (default) · Lab: ml · Campo: incident/decide · Eng: show_all script” — no new subcommands.
4. **`decide` help**: one-line note that `--allow-ml-live-in-fusion` does not change `field_ops` policy file (reduces demo misuse).
5. **Keep plateau**: no new operator verbs until a real operator sticks; H1 calendar is higher ROI than another alias.

---

## 10. What must NOT be claimed

| Forbidden claim | Truth |
|-----------------|-------|
| `GO_Q=true` / complete / closed | **partial** until H1 M3.2 acta |
| `field_ops.allow_ml_live_in_fusion=true` / fusion ON for field | **false** / **OFF** |
| `ml_product_go=true` | **false** (lab freeze ≠ promote) |
| `GO_MES+=true` | **false** |
| Eng closed GO_Q via checklist / dry-run-h3 / pack | Eng path only; human attestation required |
| IoU (0.8963 or ~0.86) = ROS or tactical accuracy | Separate layers; IoU ≠ ROS |
| Catalog holdout = live certainty | Provenance only |
| `research_open` fusion ON = product default | Experimental lab policy only |
| `replay_ok` = cryptographic authenticity | Forensic consistency only |
| ABSTAIN = product bug | Feature under field_ops honesty |
| Operator 7/7 = third-party demo done | Session/artifacts readiness only |
| Silent GO under missing sources | Designed not to; residual silent-GO is a **test suite** reliability framing, not fire prediction % |
| “We extinguish fires with AI” | Out of scope; decision support only |

---

## 11. Evidence index (absolute paths)

| Artifact | Path |
|----------|------|
| Policies | `C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\config\decision_policies.json` |
| GO_MES | `...\docs\GO_MES_VERDICT.json` |
| Graph rails | `...\docs\PLAN_1_MES_GRAPH_V6_STATUS.json` |
| ML rails | `...\docs\PLAN_ML_PRODUCT_STATUS.json` |
| CLI root | `...\wildfire_front\cli.py` |
| Teach / operator CLI | `...\wildfire_front\cli_teach.py` |
| ML CLI | `...\wildfire_front\cli_ml.py` |
| Operator UX | `...\wildfire_front\product\operator_ux.py` |
| Gate loader | `...\wildfire_front\product\teach_path.py` |
| Operator log | `...\docs\OPERATOR_UX_LOOP_LOG.md` |
| START_HERE | `...\docs\START_HERE.md` |
| PROJECT_STATUS | `...\docs\PROJECT_STATUS.md` |
| MEMORY | `...\MEMORY.md` |
| H1 runbook | `...\docs\H1_GO_Q_RUNBOOK.md` |
| Tests | `...\tests\test_operator_ux.py`, `test_cli_teach_product.py`, `test_cli_ml_product.py` |

---

## 12. One-paragraph close

WildfireFrontDynamics operator CLI is **eng-GREEN**: cold start defaults to a honest traffic-light board, four teachable acts, and an explicit “only human closes GO_Q” message; **73** scoped product tests pass; **field_ops fusion stays OFF** and **`ml_product_go` stays false** in config, status JSON, and live loaders. Product close remains **YELLOW** solely because **GO_Q is partial (H1)**. Do not invent complete gates, field fusion, or metric inflation to make the slide greener.

---

## 13. Post-audit actions (same day)

| Action | Status |
|--------|--------|
| Sync README pack count with inventory (11 emsr*) | **DONE** |
| START_HERE IoU “provenance only · not ROS” | **DONE** |
| PROJECT_STATUS Hellín inventory row vs confirmed anchor | **DONE** |
| MEMORY M3.4 wording vs ENG_FILLED | **DONE** |
| CLI epilog groups (Operario / Lab / Campo / Eng) | **DONE** |
| `decide --allow-ml-live-in-fusion` help honesty | **DONE** |
| Gmail full-box verify | **BLOCKED** `invalid_grant` — see `docs/GMAIL_AUDIT_20260805.md` |

*Audit generated 2026-08-05. Values read from repo files and live `load_gate_snapshot()`; not a third-party demo acta.*
