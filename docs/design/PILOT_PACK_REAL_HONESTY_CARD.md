# Design — P1 Piloto pack real multi-fuente + informe honesty (≤2 págs)

| Field | Value |
|-------|--------|
| **Status** | IMPLEMENTED (loop-engineering 2026-07-24 · check-work PASS) · rev 3 |
| **Priority** | P1 / Sprint 2 (S2-1 … S2-4) |
| **Date** | 2026-07-24 |
| **Baseline** | `main` @ ~`573fa7a` (Sprint 1 ML live → Card done) |
| **Canonical path** | `docs/design/PILOT_PACK_REAL_HONESTY_CARD.md` |
| **Related** | `docs/PLAN_PROGRAMACION_EMAILS_20260724_POST_S1.md`, `docs/design/ML_FOCUS_PRODUCT_V1.md`, `docs/design/DEMO_MULTI_CCAA_TOBARRA_NIJAR_CAMINOMORISCO.md`, `docs/PRODUCTO_DUAL.md`, `docs/ML_LIVE_ABSTAIN_ECE_NOTE.md` |
| **Default policy** | `research_open` (experimental live fusion) |
| **Field policy** | `field_ops` (**`allow_ml_live_in_fusion=false`** always; fail-closed on unverified R1–R4) |

---

## 1. Problem

Sprint 1 proved the **ML live → Decision Card** cable with **offline fixtures** and U1-honest pitch (mean IoU eval ~0.86, ECE ~0.15; catalog holdout **0.8963 = provenance only**). Multi-CCAA **sales portal** already shows Tobarra OPS + Níjar AND + Caminomorisco EXT as maps/scorecards.

What a technical audience still does **not** see in one place:

1. **Real packs** (not only synthetic `ml_prediction_*.json`) feeding the Card path.  
2. **Multi-source honesty flags** live on the Card: ops / open / `ml_live` availability, abstain, fusion weight, policy.  
3. A **≤2-page honesty report** that narrates HOLD/ABSTAIN correctly for the three pilot fires and refuses tactical overclaim.

### Concrete engineering gap

| Gap | Evidence |
|-----|----------|
| Open industrial packs **do not** ship `scorecard_pista_b.json` | Níjar: `scorecard_and_industrial.json` + `metrics_o2.json`; Caminomorisco: `scorecard_ext_industrial.json` + `metrics_o2.json` |
| `load_open_metrics_from_pack` only reads `scorecard_pista_b.json` | `wildfire_front/product/decide_service.py` → returns `None` on AND/EXT gold packs |
| Tobarra ops live under **temporal_windows**, not incident `outbox/` | `outputs/temporal_windows/tobarra_20240802/{early,mid,late}/operational_metrics.json` + `front_dynamics.json` |
| `load_ops_metrics_from_work_dir` only knows `outbox/*` | Same module; temporal window dirs silently yield `None` |
| Sprint 1 `build_card_from_ml_doc` wires open + ml_live only | **No `ops_metrics` parameter** → Tobarra OPS cannot attach via helper as written |
| `outputs/` is gitignored | CI cannot depend on real packs under `outputs/open_if` or `outputs/temporal_windows` |

Without an adapter + ops wiring + fixture catalog + pilot orchestrator, “run Card on Níjar pack” is a false green path that degrades to **ML-only**.

---

## 2. Goals / Non-goals

### Goals

| ID | Goal | Success signal |
|----|------|----------------|
| G1 | Pack → open metrics → Decision Card for **AND (Níjar)** and **EXT (Caminomorisco)** | Card JSON lists `open_cems_perimeter` `available=true` with real `max_area_ha` (not FIRMS hull) |
| G2 | Tobarra **OPS** metrics attach without inventing ROS/Vp | Card lists `ops_thermal_front` with non-null `primary_ros_m_min` from window engine files; anchor is audit only |
| G3 | Multi-source live flags visible per site | Each card exposes `live_ok`, `live_available`, `allow_ml_live_in_fusion`, source abstain/weight |
| G4 | Offline CI path (no GPU weights, no `outputs/`) | Default pytest green via bare `--fixture-root tests/fixtures/pilot` (auto-loads `DIR/pilot_sites.json`; see §3.3.1) |
| G5 | Optional live ML when product weights exist | `--mode live` documented; not required for CI |
| G6 | ≤2-page MD honesty report + auto facts table | Pure renderer; numbers only from facts/summaries/u1; budget-tested |
| G7 | Dual-product honesty non-negotiable | Report + cards never claim tactical dispatch; field_ops fusion stays OFF; no fake R1–R4 for pretty GO |

### Non-goals (explicit out of scope)

| Non-goal | Why |
|----------|-----|
| Retrain ensemble / lower ECE via training | Lab P2 after pilot |
| `field_ops.allow_ml_live_in_fusion=true` | Policy + product gate; only after pilot + ECE decision |
| New CCAA packs (GAL, CyL, …) | No data yet; email wait |
| Progressive synthetic burn as ops ROS or timeline truth | PSB is research geometry, not official multi-step delineation |
| Invent tactical ROS/Vp from FIRMS hulls, open perimeters, or anchors alone | RULES / multi-CCAA demo gold rule |
| HTTP API changes / portal redesign | Reuse decide_service loaders; portal optional later |
| Training on fused Decision Card labels | Dual-product invariant |
| Claiming catalog IoU 0.8963 as live fire certainty | Provenance only |
| Forcing GO on open-only packs under field_ops | field_ops requires ops for GO |
| **Any change to `score_open_cems_source` / `score_ops_source` weights or thresholds** | Soft HOLD expectations must stay valid; K10 extended |
| Inventing all-True R1–R4 reliability just to emit field_ops GO | Honesty footgun |

---

## 3. Architecture

### 3.1 End-to-end flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│ scripts/run_pilot_honesty_card.py  (orchestrator; Windows-friendly)      │
│  · site catalog (default 3 pilots OR --fixture-root / --sites-config)    │
│  · mode: offline | live | from-json                                      │
│  · policies: research_open (primary) + field_ops contrast (no fake R1–R4)│
└───────────────────────────────┬──────────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
  Tobarra OPS              Níjar AND               Caminomorisco EXT
  temporal_windows         open_if pack            open_if pack
  + INFOCAM anchor         scorecard_and_*         scorecard_ext_*
        │                       │                       │
        ▼                       ▼                       ▼
 load_ops_metrics_*     load_open_metrics_from_pack (EXTENDED)
        │                       │                       │
        └───────────┬───────────┴───────────┬───────────┘
                    ▼                       ▼
         ml_live (fixture / live / json)   optional catalog ml (weight 0)
                    │
                    ▼
         build_card_from_ml_doc(..., ops_metrics=…, open_metrics=…)
           → build_decision_card (UNCHANGED fusion + fail-closed rules)
                    │
                    ▼
         outputs/pilot_honesty_card/sites/<id>/…
                    │
                    ▼
         pure render_report(facts, summaries, u1, generated_at=…)
```

### 3.2 Prefer extend, not rewrite

| Layer | Action |
|-------|--------|
| `wildfire_front/product/decide_service.py` | **Extend** open + ops loaders (canonical contract) — **sequential PRs** |
| `scripts/run_ml_live_card_demo.py` | **Extend** `build_card_from_ml_doc` with `ops_metrics`; reuse ML/U1 helpers |
| `scripts/run_pilot_honesty_card.py` | **New thin orchestrator** (multi-site + report + fixture catalog) |
| `wildfire_front/product/confidence.py` | **No** fusion / score_* weight changes |
| `config/decision_policies.json` | **No change** |

### 3.2.1 Card builder path for ops (normative — fixes Sprint 1 gap)

**Chosen path (preferred):** extend Sprint 1 helper; do **not** invent a third Card stack.

```python
# scripts/run_ml_live_card_demo.py — signature change (backward compatible)
def build_card_from_ml_doc(
    ml_doc: dict[str, Any],
    *,
    event_id: str = "ml_live_card_demo",
    policy_id: str = DEFAULT_POLICY,
    open_metrics: dict[str, Any] | None = None,
    ops_metrics: dict[str, Any] | None = None,   # NEW
    ml_metrics: dict[str, Any] | None = None,
    allow_ml_live_in_fusion: bool | None = None,
    ml_live_trusted: bool = True,
) -> dict[str, Any]:
    ...
    card = build_decision_card(
        event_id,
        ml_metrics=ml_metrics,
        ml_live_metrics=live,
        open_metrics=open_metrics,
        ops_metrics=ops_metrics,                 # NEW pass-through
        policy_id=policy_id,
        allow_ml_live_in_fusion=fusion,
        ml_live_trusted=ml_live_trusted,
        require_ops_for_go=bool(getattr(policy, "require_ops_for_go", False)),
        # reliability_gate intentionally omitted for pilot contrast (see §3.5)
    )
    return card.to_dict()
```

Also extend `run_demo(...)` with optional `ops_metrics: dict | None = None` and optional `work_dir: Path | None = None` that calls `load_ops_metrics_from_work_dir` when metrics not pre-resolved.

**Regression test (PR3 or with helper change):** Tobarra fixture window → card has source id `ops_thermal_front` with `available=true` and `metrics.primary_ros_m_min` not null.

### 3.3 Site catalog (fixed for pilot)

Default **production** paths (local full pilot when packs exist under `outputs/`):

| Site id | Display | Track | Pack / source path (repo-relative) | Primary sources on Card |
|---------|---------|-------|------------------------------------|-------------------------|
| `tobarra` | Tobarra | OPS gold | `work_dir`: `outputs/temporal_windows/tobarra_20240802/mid` · `anchor_key`: `tobarra_20240802` · `anchors_path`: `data/infocam_anchors.json` | **ops** + ml_live |
| `nijar` | Níjar | OPEN O2 AND | `open_pack`: `outputs/open_if/and_2024040053_20240606` | **open** + ml_live |
| `caminomorisco` | Caminomorisco | OPEN O2 EXT | `open_pack`: `outputs/open_if/ext_2025100393_20250729` | **open** + ml_live |

Default Tobarra window = **`mid`**. Override: `--tobarra-window early|mid|late` (rewrites `work_dir` suffix).

### 3.3.1 Site catalog schema (`pilot_sites.json` / fixture catalog)

```json
{
  "schema": "pilot_sites_catalog_v1",
  "sites": [
    {
      "site_id": "tobarra",
      "display_name": "Tobarra",
      "track": "OPS",
      "event_id": "pilot_tobarra_20240802",
      "work_dir": "ops_tobarra_min",
      "open_pack": null,
      "anchor_key": "tobarra_20240802",
      "anchors_path": "anchors_tobarra_snippet.json",
      "ml_scenario": "hold",
      "ml_prediction": null
    },
    {
      "site_id": "nijar",
      "display_name": "Níjar",
      "track": "OPEN_AND",
      "event_id": "pilot_nijar_and_2024040053",
      "work_dir": null,
      "open_pack": "open_and_min",
      "anchor_key": null,
      "anchors_path": null,
      "ml_scenario": "hold",
      "ml_prediction": null
    },
    {
      "site_id": "caminomorisco",
      "display_name": "Caminomorisco",
      "track": "OPEN_EXT",
      "event_id": "pilot_camino_ext_2025100393",
      "work_dir": null,
      "open_pack": "open_ext_min",
      "anchor_key": null,
      "anchors_path": null,
      "ml_scenario": "abstain",
      "ml_prediction": null
    }
  ]
}
```

**Catalog load and path base are independent total functions** (do not conflate):

#### Catalog load (which JSON defines the site list — first match wins)

```
if --sites-config PATH is set:
    catalog = load_json(PATH)                    # must exist or exit 2
elif --fixture-root DIR is set
     and (DIR / "pilot_sites.json").is_file():
    catalog = load_json(DIR / "pilot_sites.json")
else:
    catalog = BUILTIN_PRODUCTION_CATALOG         # §3.3 table paths
```

Notes:

- Bare `--fixture-root tests/fixtures/pilot` is **sufficient** for CI when `tests/fixtures/pilot/pilot_sites.json` exists (G4 / T6 / PR3 DoD).  
- `--sites-config` always wins for **which** catalog file is loaded (even if `--fixture-root` is also set).  
- If `--fixture-root DIR` is set but `DIR/pilot_sites.json` is missing **and** `--sites-config` is not set → fall through to **built-in production** catalog (do **not** invent paths). Pilot should log a warning: `fixture_root_without_pilot_sites_json`.  
- Optional: if both flags set, production-style paths inside an explicit `--sites-config` still resolve under fixture-root base (see path base below) — that is intentional for CI overrides.

#### Path base (resolve non-absolute relatives — first match wins)

```
if --fixture-root DIR is set:
    base = DIR
elif catalog JSON has top-level string "base":
    base = Path(catalog["base"])                 # absolute or vs project root
elif catalog was loaded from --sites-config PATH:
    base = PATH.parent
else:
    base = PROJECT_ROOT
```

For each site field `work_dir`, `open_pack`, `anchors_path`, `ml_prediction`:

```
if value is None or "":
    resolved = None
elif Path(value).is_absolute():
    resolved = Path(value)
else:
    resolved = base / value
```

Never prefix production relatives with fixture-root unless the **catalog** itself lists those relatives **and** `--fixture-root` is the active base (CI catalogs must list fixture-relative paths only, e.g. `open_and_min` not `outputs/open_if/...`).

#### Missing path after resolve

1. Default **strict**: site status `FAIL` → process exit 2 unless `--allow-missing-pack`.  
2. With `--allow-missing-pack`: site status `SKIP`, write `site_summary.json` with `skipped=true`, `skip_reason`, and **do not** write a Card that pretends open/ops were resolved (no silent ML-only success without `honesty_flags.sources_incomplete=true`).

### 3.4 ML live channel (same Sprint 1 rules)

| Mode | When | Behavior |
|------|------|----------|
| `offline` (default) | CI + default pilot | Fixture `hold` / `abstain` / `identity` from `tests/fixtures/ml/` |
| `from-json` | Repro | Existing `ml_prediction.json` per site or global |
| `live` | Local weights present | `predict_with_uncertainty` via demo helper |

Per-site offline scenario defaults (overridable by catalog `ml_scenario` or global `--scenario`):

| Site | Default offline scenario | Intent |
|------|--------------------------|--------|
| `tobarra` | `hold` | Ops + actionable live |
| `nijar` | `hold` | Open + live HOLD monitoring |
| `caminomorisco` | `abstain` | Open present; live refuses |

### 3.5 Policy matrix (honesty contrast) — field_ops fail-closed

For each site, pilot **always** writes (when `--include-field-ops-contrast`, default **true**):

1. Card under **`research_open`** (primary demo surface).  
2. Contrast card under **`field_ops`** with **no** invented reliability gate report and **no** free-floating R1–R4 True flags.

**Product law (existing `build_decision_card`):** under `field_ops`, if pre-gate decision is `GO` and `system_reliability_pass` is false (default when R1–R4 unknown), decision is forced to **`ABSTAIN`** with reason  
`field_ops_fail_closed_reliability_unverified`.

| Site | research_open (default fixtures) | field_ops contrast (same sources, **no** reliability gate) |
|------|----------------------------------|------------------------------------------------------------|
| Tobarra ops+live hold | Often **GO** or strong **HOLD** if ops conf clears research thresholds | **HOLD or ABSTAIN** — **never claim GO** in pilot narrative; if pre-gate would be GO, expect final **ABSTAIN** + reason `field_ops_fail_closed_reliability_unverified` |
| Níjar open+live hold | **HOLD** (open and/or live) | Open-only style **HOLD** monitoring or ABSTAIN; ML-only would ABSTAIN if open missing |
| Caminomorisco open+abstain live | Open **HOLD** or ABSTAIN if open conf weak | Open **HOLD** or ABSTAIN; live weight 0 |

**Forbidden:** passing all-True `gates_ok` / `determinism_ok` / `abstention_enforced` / `provenance_ok` or a fake reliability JSON just to pretty-print field_ops GO.

**Allowed soft tests:**

- `decision_field_ops in {"HOLD", "ABSTAIN"}`  
- if research_open decision is GO and field_ops decision is ABSTAIN → assert reason contains `field_ops_fail_closed_reliability_unverified` **or** other non-GO field_ops reasons (ops threshold)  
- always assert `field_ops_allow_ml_live_in_fusion is False`

Never flip `field_ops.allow_ml_live_in_fusion`.

---

## 4. Data contracts

### 4.1 Open metrics (Card input)

Canonical dict consumed by `score_open_cems_source` / `build_decision_card(..., open_metrics=)`.

**Scoring reads only** `max_area_ha` + `n_timeline_steps`. All other keys are **audit/display** for pilot/report (source id on Card remains `open_cems_perimeter`).

```json
{
  "max_area_ha": 2169.34,
  "n_timeline_steps": 1,
  "activation": "and_2024040053_20240606",
  "O2_cems_delineation": "GO",
  "pack_id": "and_2024040053_20240606",
  "source_scorecard": "scorecard_and_industrial.json",
  "track": "Pista_B_plus_AND_REDIAM",
  "decision_open": "HOLD",
  "verdict": "GO_OPEN_AND_O2",
  "vp_invented": false,
  "firms_hull_is_official_burned_area": false,
  "attribution": "…",
  "area_source": "metrics_o2.area_rediam_ha"
}
```

**Non-None return requires:** `max_area_ha: float` (finite, ≥ 0) and `n_timeline_steps: int` (≥ 0).

### 4.2 Open pack adapter (total function)

#### 4.2.1 Scorecard discovery (simultaneous exclusive checks)

Given resolved pack dir `P`. Implement **exactly** this order (single algorithm; table and prose must not diverge):

```
# 1) Legacy CEMS
if (P / "scorecard_pista_b.json").is_file():
    return industrial_or_legacy_from_pista_b(...)   # §4.2.3; None if max_area missing

# 2) Named industrial — check BOTH files before choosing either
and_sc = P / "scorecard_and_industrial.json"
ext_sc = P / "scorecard_ext_industrial.json"
and_ok = and_sc.is_file()
ext_ok = ext_sc.is_file()
if and_ok and ext_ok:
    return None   # ambiguous malformed pack (fail honest)
if and_ok:
    return industrial_from(and_sc, kind="AND")      # source_scorecard=scorecard_and_industrial.json
if ext_ok:
    return industrial_from(ext_sc, kind="EXT")      # source_scorecard=scorecard_ext_industrial.json

# 3) Glob other industrial names (only when neither named file exists)
matches = sorted(P.glob("scorecard_*_industrial.json"))
if len(matches) == 0:
    return None
if len(matches) >= 2:
    return None   # ambiguous; reason: ambiguous_industrial_scorecards
return industrial_from(matches[0], kind="OTHER")
```

There is **no** “prefer 2a then skip 2b” exclusive-if chain that can hide a coexisting EXT file. Both named files present → always `None`.

#### 4.2.2 Industrial → open_metrics mapping table

Load companions (optional files, missing = empty dict):

- `metrics_o2.json` → `m2`  
- `manifest.json` → `man`

| Output key | Required? | Source (first hit) | Default if absent |
|------------|-----------|--------------------|-------------------|
| `max_area_ha` | **yes** | `m2.area_rediam_ha` → `m2.area_rai_ha` → `m2.area_attr_ha` → `m2.max_area_ha` → `man.area_rediam_ha` → `man.area_rai_ha` → `man.area_ha` → scorecard `max_area_ha` if present | **If none → return None** (do not invent ha) |
| `n_timeline_steps` | **yes** | See §4.2.4 | int always set when returning non-None |
| `activation` | audit | `pack_id` (scorecard) → `man.pack_id` → `man.codigo` → `activation` → pack dir name | pack dir name |
| `O2_cems_delineation` | audit | gates: `O2_REDIAM` / `O2_RAI` / `O2_cems` / `O2_cems_delineation`: `PASS`→`"GO"`, `FAIL`→`"NO_GO"`, `SKIP`/other→`"SKIP"`; else scorecard field if string | `"SKIP"` |
| `pack_id` | audit | scorecard `pack_id` → `man.pack_id` → pack dir name | pack dir name |
| `source_scorecard` | audit | filename used | — |
| `track` | audit | scorecard `track` | omit key if missing |
| `decision_open` | audit | scorecard `decision_open` | omit if missing (**never invent GO**) |
| `verdict` | audit | scorecard `verdict` | omit if missing (**never upgrade PARTIAL→GO**) |
| `vp_invented` | audit | scorecard bool if present | **`false`** (default false when key missing — honesty) |
| `firms_hull_is_official_burned_area` | audit | scorecard bool if present | **`false`** |
| `attribution` | audit | scorecard → `man.attribution` | omit if missing |
| `area_source` | audit | dotted path of winning ha key, e.g. `metrics_o2.area_rediam_ha` | required when ha resolved |

**PARTIAL packs (e.g. Caminomorisco `verdict=PARTIAL`, FIRMS SKIP):**

- Still return open_metrics when `max_area_ha` resolved (official RAI/REDIAM ha).  
- Copy `verdict` and `decision_open` when present.  
- `available=true` on Card is correct (open perimeter exists); pack PARTIAL is an audit fact, not a reason to drop open.  
- Never invent FIRMS area or upgrade verdict.

#### 4.2.3 Legacy pista_b path

From `scorecard_pista_b.json` only (current behavior extended with optional passthrough):

| Output key | Source |
|------------|--------|
| `max_area_ha` | `max_area_ha` — if missing/null → return None |
| `n_timeline_steps` | `n_timeline_steps` if int else §4.2.4 |
| `activation` | `activation` |
| `O2_cems_delineation` | `O2_cems_delineation` |
| audit | `source_scorecard=scorecard_pista_b.json`; copy `vp_invented`/`firms_hull…` if present else false |

#### 4.2.4 `n_timeline_steps` decision tree (no ambiguity)

```
if (P / "timeline_perimeters.geojson").is_file():
    n = len(features)   # empty FeatureCollection → 0
elif scorecard or metrics_o2 has int n_timeline_steps:
    n = that int
elif any exists:
    P/vectors/perimeter_rediam.geojson
    P/vectors/perimeter_rai.geojson
    P/vectors/perimeter_official.geojson
    P/vectors/perimeter.geojson
    → n = 1
else:
    n = 0
```

**NEVER** read `progressive/metrics_progressive.json` `n_stages` or any PSB path.

#### 4.2.5 Forbidden keys / sources (hard ban)

Adapter **must not**:

- Set `primary_ros_m_min`, `vp_m_min`, `vp_tactical`, `ros_m_min` on open_metrics.  
- Use as `max_area_ha` any of: `area_firms_hull_ha`, `area_firms_*`, `firms_hull_*`, hull proxy areas.  
- Use progressive synthetic stages for timeline or area.  
- Upgrade `verdict` or invent `decision_open=GO` for field dispatch.

If a maintainer later “helps” by adding FIRMS ha to the area priority list, that is a **product bug** — list is closed.

### 4.3 Ops metrics (Card input)

Canonical dict for `score_ops_source` when loader returns non-None:

```json
{
  "quality_grade": "B",
  "primary_ros_m_min": 6.752,
  "n_frames_staged": 4,
  "area_ha_max": 26.55,
  "speed_vs_ref_ratio": 0.965,
  "engine": "front_dynamics_v1",
  "window": "mid",
  "fire_id": "tobarra_20240802",
  "anchor_vp_m_min": 7.0,
  "anchor_area_ha": 39.0,
  "anchor_status": "confirmed",
  "anchor_source": "INFOCAM 2024 parte operativo",
  "ros_source": "operational_metrics.speed_median_m_min"
}
```

### 4.4 Ops loader (total function)

#### 4.4.1 File resolution order in `load_ops_metrics_from_work_dir`

Given work dir `W` (allowlisted):

| Step | Path | Role |
|------|------|------|
| A | `W/outbox/fire_decision_card.json` → `metrics.ops` | existing |
| B | `W/outbox/incident_state.json` | existing |
| C | `W/outbox/operational_metrics.json` | existing |
| D | `W/operational_metrics.json` | **NEW** window root |
| E | `W/front_dynamics.json` | **NEW** ROS/grade fill-in only |
| F | `W/summary.json` → optional `metrics` object | **NEW** fill missing keys only |

Return first successful **complete** ops dict from A–C as today. For D/E/F use `operational_files_to_ops_metrics` (§4.4.2).

#### 4.4.2 `operational_files_to_ops_metrics` (normative)

Inputs: `operational_metrics: Mapping | None`, `front_dynamics: Mapping | None`, optional `summary_metrics: Mapping | None`.

**ROS priority (first finite float wins):**

1. `operational_metrics.speed_median_m_min`  
2. `operational_metrics.primary_ros_m_min`  
3. `operational_metrics.structural.primary_ros_m_min` (nested dict)  
4. `front_dynamics.primary_ros_m_min`  
5. else **ROS = None**

**If ROS is None → return `None`** (missing ops for Card purposes).  
Do **not** return grade-only / area-only partials: `score_ops_source` would mark `available=true` without ROS and mislead the pilot.

**Grade priority (for non-None return):**

1. `operational_metrics.quality_grade`  
2. `operational_metrics.structural_grade`  
3. `operational_metrics.structural.structural_grade`  
4. `front_dynamics.structural_grade`  
5. else `""` (empty string; scorer falls through to low conf — still OK if ROS present)

**`n_frames_staged` priority (first int > 0 or first present):**

1. `n_frames_staged`  
2. `n_frames`  
3. `num_observations`  
4. `observation_count`  
5. `input_count`  
6. `speed_n_observable`  
7. else `0`

**`area_ha_max`:** `area_ha_max` → `area_ha` → None  
**`speed_vs_ref_ratio`:** use existing engine value if present; do not invent from anchor unless §4.4.3 optional audit recompute.

**Step F rule:** `summary_metrics` may fill keys that are still missing after D/E; **never overwrite** a non-null ROS or grade already set from D/E. (Prevents mid `summary.json` `speed_status=abstained` from wiping defendable `operational_metrics` median.)

**`ros_source` audit string:** dotted path of winning ROS key.

#### 4.4.3 Anchor attachment (audit only)

```python
def load_infocam_anchor(
    anchors_path: Path,
    fire_id: str,
) -> dict[str, Any] | None:
    data = json.loads(anchors_path.read_text(encoding="utf-8"))
    rec = (data.get("anchors") or {}).get(fire_id)
    if not isinstance(rec, dict):
        return None
    if rec.get("status") != "confirmed":
        return None
    return rec
```

When attaching to ops_metrics **after** successful ROS resolve:

| Field | Rule |
|-------|------|
| `anchor_vp_m_min` | `rec.vp_m_min` if present |
| `anchor_area_ha` | `rec.area_ha` if present |
| `anchor_status` | `"confirmed"` |
| `anchor_source` | `rec.source` |
| `fire_id` | `fire_id` |
| `primary_ros_m_min` | **NEVER** set/overwrite from `vp_m_min` / press / `area_ha_press_*` |
| `speed_vs_ref_ratio` | if already set on ops → **leave**; else optional compute `primary_ros / anchor_vp` only when both finite and `anchor_vp > 0` — audit display only |

If ops ROS missing and only anchor exists → **`ops_metrics = None`** (H10/T5 single behavior).

### 4.5 ML live metrics (unchanged)

Schema `ml_live_metrics_v1` / wrapper `ml_prediction_v1` as in Sprint 1.

### 4.6 Pilot site summary artifact

`sites/<id>/site_summary.json`:

```json
{
  "schema": "pilot_honesty_site_summary_v1",
  "site_id": "nijar",
  "event_id": "pilot_nijar_and_2024040053",
  "track": "OPEN_AND",
  "policy_id": "research_open",
  "skipped": false,
  "sources_requested": {"ops": false, "open": true, "ml_live": true, "ml_holdout": false},
  "sources_resolved": {"ops": false, "open": true, "ml_live": true},
  "paths": {
    "open_pack": "tests/fixtures/pilot/open_and_min",
    "work_dir": null,
    "ml_prediction": "outputs/pilot_honesty_card/sites/nijar/ml_prediction.json"
  },
  "decision": "HOLD",
  "confidence_pred": 0.55,
  "live_ok": true,
  "live_available": true,
  "live_abstained": false,
  "allow_ml_live_in_fusion": true,
  "field_ops_allow_ml_live_in_fusion": false,
  "open_max_area_ha": 2169.34,
  "ops_primary_ros_m_min": null,
  "honesty_flags": {
    "vp_invented": false,
    "firms_hull_is_official_burned_area": false,
    "catalog_iou_is_provenance_only": true,
    "tactical_dispatch": false,
    "sources_incomplete": false
  },
  "u1_ece_patch_conf": 0.15,
  "u1_source": "scorecard",
  "card_path": "…/decision_card.json",
  "contrast_field_ops": {
    "decision": "HOLD",
    "path": "…/decision_card_field_ops.json",
    "reliability_gate_passed": false,
    "fail_closed_reason_expected_if_pre_go": "field_ops_fail_closed_reliability_unverified"
  }
}
```

### 4.7 Artifact tree (exact)

```
outputs/pilot_honesty_card/
  README.md
  pilot_manifest.json
  pilot_summary.json
  facts_table.json
  report/
    PILOT_HONESTY_CARD.md
  sites/
    tobarra/
      ml_prediction.json
      decision_card.json
      decision_card_field_ops.json
      abstain_ece_note.json
      sources.json
      site_summary.json
    nijar/
      … (same set)
    caminomorisco/
      … (same set)
```

Windows: `pathlib.Path`; JSON `ensure_ascii=False`; relative paths in manifests use `.as_posix()`.

**Docs publish:** `docs/PILOT_HONESTY_CARD.md` ← same body as `outputs/…/report/PILOT_HONESTY_CARD.md` when `--write-docs-report`.

#### 4.7.1 `sources.json` allowlist (no huge blobs)

Write **only** these keys (drop everything else, including `pairs`, geometry, base64, full scorecard gates dumps beyond booleans already in open_metrics):

| Channel | Allowed keys |
|---------|----------------|
| `open` | Exactly §4.1 keys present on resolved open_metrics |
| `ops` | §4.3 keys + `ros_source` (no `structural` nested tree, no `pairs`) |
| `ml_live` | `ml_live_metrics_v1` fields only: `schema`, `product_id`, `confidence`, `abstain`, `mean_entropy`, `member_disagreement`, `mean_margin`, `calibrator_id`, `n_members` |

### 4.8 CLI contract

```text
python scripts/run_pilot_honesty_card.py
  --mode offline|live|from-json          # default offline
  --scenario hold|abstain|identity       # optional global override of per-site ml_scenario
  --policy research_open                 # primary
  --include-field-ops-contrast / --no-field-ops-contrast
  --sites tobarra,nijar,caminomorisco    # filter; default all in catalog
  --tobarra-window mid                   # production catalog only
  --fixture-root tests/fixtures/pilot    # CI: resolve site paths under this root
  --sites-config PATH.json               # optional explicit catalog
  --out-dir outputs/pilot_honesty_card
  --write-docs-report
  --allow-missing-pack                   # SKIP incomplete sites; flag sources_incomplete
  --generated-at ISO8601                 # optional; default now UTC; tests pass fixed stamp
  --product clm_ensemble_v34
  --npz <path>                         # live mode
  --ml-prediction <path>                 # from-json helper
  --json                                 # print pilot_summary only
```

**CI / pytest default invocation (copy-pasteable) — bare fixture-root is enough:**

```powershell
$env:PYTHONPATH = "."
# G4/T6/PR3: loads tests/fixtures/pilot/pilot_sites.json automatically;
# resolves open_and_min, ops_tobarra_min, … under the same DIR.
python scripts/run_pilot_honesty_card.py `
  --mode offline `
  --fixture-root tests/fixtures/pilot `
  --out-dir $env:TEMP/pilot_honesty_ci `
  --generated-at 2026-07-24T00:00:00+00:00
```

Optional explicit catalog (same result when file is `DIR/pilot_sites.json`):

```powershell
python scripts/run_pilot_honesty_card.py `
  --mode offline `
  --fixture-root tests/fixtures/pilot `
  --sites-config tests/fixtures/pilot/pilot_sites.json `
  --out-dir $env:TEMP/pilot_honesty_ci `
  --generated-at 2026-07-24T00:00:00+00:00
```

When both flags are set: catalog load uses `--sites-config`; path base still uses `--fixture-root` (§3.3.1).

Makefile target (optional PR5): `make pilot-honesty` → offline + `--fixture-root tests/fixtures/pilot` + write-docs-report.

---

## 5. Honesty rules (dual-product — non-negotiable)

| # | Rule | Enforcement |
|---|------|-------------|
| H1 | Ops ≠ ML; fuse only at Decision Card | Separate loaders; single `build_decision_card` via extended helper |
| H2 | Never train on fused labels | No training scripts touched |
| H3 | No invented tactical ROS/Vp from open packs or FIRMS hulls | Adapter bans ROS keys + `area_firms*` as area |
| H4 | Catalog holdout IoU 0.8963 is **provenance only** | When live channel requested: live/fused conf path; `catalog_iou_is_provenance_only: true`; exact disclaimer substring |
| H5 | VAL-only calibrate/mix; TEST report-only for ML claims | Pilot does not fit calibrators |
| H6 | `field_ops.allow_ml_live_in_fusion` stays **false** | Assert in summaries |
| H7 | research_open live fusion is **experimental lab** | Report banner |
| H8 | Open-only / ML-only never claim tactical dispatch | Card disclaimers + report |
| H9 | Progressive synthetic stages ≠ official multi-step timeline | Adapter ignores PSB |
| H10 | Anchor Vp only when `status=confirmed`; **never** sole/primary ROS | ROS None → ops_metrics None |
| H11 | Missing pack → SKIP/FAIL; never fabricate scorecard; no silent ML-only without `sources_incomplete` | CLI flags |
| H12 | ABSTAIN is a success when reliability is weak | Report + notes |
| H13 | field_ops contrast does **not** invent R1–R4 PASS | No reliability_gate in pilot contrast call |

---

## 6. Report structure (≤2 pages)

### 6.1 Pure renderer contract

```python
def render_report(
    facts: dict[str, Any],
    site_summaries: list[dict[str, Any]],
    u1: dict[str, Any],
    *,
    generated_at: str,
    pilot_manifest: dict[str, Any] | None = None,
) -> str:
    """Deterministic MD. No wall clock. No literal ha/ROS in template source."""
```

- Tests pass fixed `generated_at="2026-07-24T00:00:00+00:00"`.  
- **All numeric claims** (ha, ROS, Vp, conf, ECE, IoU) are interpolated from `facts_table.rows[*]`, `site_summaries`, or `u1` fields.  
- Template source may contain **labels only** (e.g. `"area_ha"`, `"primary_ros_m_min"`), never hardcoded `2169`, `2680`, `7.0`, `0.8963` as claim values (0.8963 may appear only as the provenance constant **read from** `u1["catalog_holdout_iou_provenance"]`).

### 6.2 Budget (enforced)

| Budget | Limit | Test |
|--------|------:|------|
| Non-empty lines | ≤ **90** | `assert len(nonempty_lines) <= 90` |
| Words (whitespace split) | ≤ **1200** | `assert word_count <= 1200` |
| Required honesty substrings | exact list | see §6.4 |

Generator **hard-fails** (exit 2 / raise) if budget exceeded.

### 6.3 Markdown outline (templates interpolate)

```markdown
# Piloto honesty — Decision Card multi-fuente
{site_names_joined}
Generated: {generated_at} · policy primary: {policy} · product: {product_id}

## 0. Banner de honestidad (dual product)
- Ops (front_dynamics_v1) ≠ ML (máscara + fiabilidad de parche)
- Fusión solo en Decision Card; field_ops live fusion = OFF
- No es orden táctica de despacho
- U1 TEST honest ({u1_source}): IoU eval ≈ {mean_iou} · sel@80 ≈ {sel80} · ECE ≈ {ece}
- Catalog holdout {catalog_iou} = provenance only (not live certainty)

## 1. Tabla de hechos (auto from facts_table.json)
| Site | Track | Sources | Decision (research_open) | conf | live_ok | Decision (field_ops) | Key number | Notes |
| … one row per facts_table.rows … |

## 2. Lectura por incendio
### {display_name} ({track})
- Key number: {key_number_label} = {key_number_value} (source: {key_number_source})
- Card research_open: {decision} · conf={confidence_pred} · live_ok={live_ok}
- field_ops contrast: {decision_field_ops} (no fake R1–R4; fusion OFF)
- Honesty: vp_invented={…}; firms_hull≠burned; sources_incomplete={…}

## 3. Contraste de políticas
- research_open: lab / open-friendly HOLD; experimental live fusion
- field_ops: require_ops_for_go; live fusion OFF; fail-closed ABSTAIN if GO without verified reliability
  (reason field_ops_fail_closed_reliability_unverified) — pilot does not invent gates

## 4. Límites y no-claims
- Not multi-CCAA “works across all Spain”
- FIRMS hull ≠ official burned area
- No retrain in this pilot
- ml_product_go remains false until product gates

## 5. Artefactos
- {artifact paths from pilot_manifest}
```

### 6.4 Required honesty substrings (tests)

Report body must contain all of:

1. `field_ops` + `OFF` (or `allow_ml_live_in_fusion` false narrative already in banner)  
2. `provenance only`  
3. `Not a tactical dispatch` **or** `No es orden táctica`  
4. `Ops` and `ML` dual product distinction  
5. Each configured site `display_name`  
6. `field_ops_fail_closed_reliability_unverified` **or** explicit sentence that field_ops contrast does not invent R1–R4 GO  

### 6.5 U1 source labeling

`load_u1_honesty_snapshot` must return / pilot must set:

- `u1_source`: `"scorecard"` if `docs/ML_PRODUCT_SCORECARD.json` (or override path) loaded primary metrics; else `"fallback"`  
- Banner prints `U1 TEST honest (scorecard|fallback): …`  
- Never present fallback numbers as if freshly measured on the three fires

### 6.6 `facts_table.json` row schema

```json
{
  "schema": "pilot_honesty_facts_table_v1",
  "rows": [
    {
      "site_id": "nijar",
      "display_name": "Níjar",
      "track": "OPEN_AND",
      "sources": "open+ml_live",
      "decision_research_open": "HOLD",
      "confidence_pred": 0.55,
      "live_ok": true,
      "live_available": true,
      "live_abstained": false,
      "allow_ml_live_in_fusion": true,
      "decision_field_ops": "HOLD",
      "key_number_label": "area_ha",
      "key_number_value": 2169.34,
      "key_number_source": "metrics_o2.area_rediam_ha",
      "pack_verdict": "GO_OPEN_AND_O2",
      "honesty_note": "No tactical Vp; open HOLD"
    }
  ]
}
```

Row builders pull `key_number_value` from resolved open/ops metrics only (cards/sources), never template literals.

---

## 7. Testing

### 7.1 Test matrix

| ID | Test | Location | Weights | Asserts |
|----|------|----------|---------|---------|
| T1 | Open adapter AND fixture → keys + area source | `tests/test_open_metrics_pack_adapter.py` | No | `max_area_ha`, `n_timeline_steps` int, no ROS, no firms ha |
| T2 | Open adapter EXT PARTIAL still returns ha | same | No | `verdict` copied if present; ha from `area_rai_ha` |
| T3 | Legacy pista_b still works | same | No | regression |
| T4 | Both AND+EXT named industrial files → None; ≥2 glob matches → None | same | No | fail honest (Issue 14) |
| T4b | Bare `--fixture-root` loads `DIR/pilot_sites.json` without `--sites-config` | `tests/test_pilot_honesty_card.py` | No | G4/T6 catalog total (Issue 13) |
| T5 | Ops window fixture → ROS + grade | `tests/test_ops_metrics_work_dir.py` | No | non-null `primary_ros_m_min` |
| T5b | ROS priority includes `structural.primary_ros_m_min` | same | No | fixture with only nested ROS works |
| T5c | Grade-only / anchor-only → **None** | same | No | single contract |
| T5d | summary F does not overwrite D ROS | same | No | |
| T6 | Pilot offline 3-site via bare `--fixture-root` only | `tests/test_pilot_honesty_card.py` | No | artifact tree; no `outputs/open_if`; no required `--sites-config` |
| T7 | open_metrics never contain ROS keys | same | No | JSON walk |
| T8 | field_ops fusion false; decision in HOLD/ABSTAIN | same | No | no invented GO requirement |
| T8b | If research GO and field ABSTAIN → reason contains fail-closed string **or** document ops-threshold path | same | No | |
| T9 | Live path honesty for catalog IoU | same | No | see §7.1.1 |
| T10 | Report pure render budget + substrings + fixed generated_at | same | No | ≤90 lines, ≤1200 words |
| T11 | `build_card_from_ml_doc` ops pass-through | `tests/test_ml_live_card_demo.py` extend | No | ops_thermal_front available |
| T12 | Optional `@requires_weights` live smoke | optional | Yes | skip if no weights |

#### 7.1.1 T9 enforceable predicates

When offline **hold** fixture + open and/or ops present under `research_open`:

1. Card `sources` includes id `ml_live_reliability` (or alias `ml_live`) with `available=true`.  
2. `confidence_pred` is **not** equal to catalog holdout IoU `0.8963` (tolerance 1e-9).  
3. `site_summary.honesty_flags.catalog_iou_is_provenance_only is True`.  
4. `site_summary` or report contains Sprint 1 style phrase:  
   `Catalog holdout` + `provenance only` (or exact honesty list entry from demo summary).  
5. If live actionable: live source `actionable=true` and conf from live/fuse path (not holdout_quality role alone).

### 7.2 CI fixtures (commit small JSON only)

```
tests/fixtures/pilot/
  pilot_sites.json                 # catalog with relative paths
  open_and_min/
    scorecard_and_industrial.json
    metrics_o2.json                # area_rediam_ha only (no firms ha needed)
    manifest.json
  open_ext_min/
    scorecard_ext_industrial.json  # verdict PARTIAL
    metrics_o2.json                # area_rai_ha
    manifest.json
  ops_tobarra_min/
    operational_metrics.json       # speed_median + quality_grade (+ optional structural)
    front_dynamics.json            # backup ROS
  anchors_tobarra_snippet.json     # anchors.tobarra_20240802 status=confirmed
```

Default pytest **never** requires `outputs/open_if` or `outputs/temporal_windows`.

### 7.3 Offline default commands

```powershell
$env:PYTHONPATH = "."
python -m pytest tests/test_open_metrics_pack_adapter.py tests/test_ops_metrics_work_dir.py tests/test_pilot_honesty_card.py tests/test_ml_live_card_demo.py -q
```

Full local pilot (optional; production paths):

```powershell
$env:PYTHONPATH = "."
python scripts/run_pilot_honesty_card.py --mode offline --write-docs-report
```

---

## 8. Alternatives considered

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| **A. Extend loaders + extend `build_card_from_ml_doc` + thin pilot** | One Card path; ops wired; CLI/API inherit | Shared service edits need sequential PRs | **PICK** |
| B. Copy industrial → `scorecard_pista_b.json` at pack build | No loader change | Dual truth; rename lies | Reject |
| C. Parallel pilot stack bypassing decide_service | Fast demo | Dual product drift | Reject |
| D. Pilot calls `build_decision_card` only; demo helpers ML-only | Avoids demo edit | Two call styles | Rejected in favor of A (single helper) |
| E. Progressive `n_stages` as timeline | Higher open conf | Dishonest | Reject |
| F. Fake R1–R4 True for field_ops GO in report | Pretty GO | Honesty footgun | Reject |

---

## 9. Implementation sketch (engineer-ready)

### 9.1 `decide_service.py`

1. Helpers: `_load_json_obj`, `industrial_scorecard_to_open_metrics`, `operational_files_to_ops_metrics`, `load_infocam_anchor` (anchor may live in pilot script if preferred — **prefer decide_service or small `pilot_sources.py` only if needed**; default: keep loaders in decide_service, anchor helper next to pilot OK).  
2. `load_open_metrics_from_pack` = §4.2 total function.  
3. `load_ops_metrics_from_work_dir` = §4.4 total function.  
4. **Do not** change score_* in confidence.py.

### 9.2 `run_ml_live_card_demo.py` + `run_pilot_honesty_card.py`

1. **PR3 scope:** extend `build_card_from_ml_doc(..., ops_metrics=None)` pass-through (§3.2.1); extend `run_demo` optionally.  
2. Pilot orchestrator: load catalog → resolve paths under fixture-root → for each site:
   - resolve open via `load_open_metrics_from_pack`
   - resolve ops via `load_ops_metrics_from_work_dir` + optional anchor attach
   - ML via fixture/live/json
   - `build_card_from_ml_doc(..., ops_metrics=ops, open_metrics=open)`
   - field_ops contrast **without** reliability_gate
   - write allowlisted `sources.json`, cards, notes, site_summary  
3. `render_report(...)` pure; budget enforce.  
4. Exit 0 if all sites OK or SKIP-with-allow; exit 2 on FAIL/budget/write error.

### 9.3 Soft checks on decisions

Use `decision in {"HOLD", "GO", "ABSTAIN"}` and source `available` flags — **not** exact confidence floats. Soft HOLD expectations for open packs assume **unchanged** `score_open_cems_source` (§2 non-goal).

---

## 10. Rollout / DoD checklist (maps to S2 + PRs)

| Sprint task | Maps to | DoD |
|-------------|---------|-----|
| **S2-4** | **Precondition before PR1 merge** | `main` CI green on baseline; if red, fix first (no owner PR — process gate) |
| **S2-1** | **PR1 + PR2 + PR3** | Loaders + ops-wired Card helper + pilot script offline 3-site with fixtures |
| **S2-3** | **Tests in PR1–PR3** (not a separate PR) | Fixture pytest green without weights / without `outputs/` packs |
| **S2-2** | **PR4** | ≤2p report pure render + docs publish |

---

## 11. Key Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| K1 | **Extend** `load_open_metrics_from_pack` for industrial scorecards | Single truth per pack; CLI/API inherit |
| K2 | Area from **metrics_o2 / manifest** official keys only; **ban `area_firms*`** | Honesty; industrial scorecards lack max_area_ha |
| K3 | `n_timeline_steps` from real timeline / perimeter files / 0; never PSB | Honesty |
| K4 | Window-root ops load with structural ROS priority; **None if ROS missing** | Tobarra layout; no grade-only ops |
| K5 | Anchor audit only; never primary ROS from Vp | Dual-product |
| K6 | **Extend `build_card_from_ml_doc` with `ops_metrics`** | Fixes Sprint 1 gap; one helper for pilot |
| K7 | Offline scenarios hold/hold/abstain | Multi-outcome narrative |
| K8 | field_ops contrast without fake R1–R4; expect HOLD/ABSTAIN not GO | Matches fail-closed product law |
| K9 | `outputs/pilot_honesty_card/` + `docs/PILOT_HONESTY_CARD.md` | Repo convention |
| K10 | No fusion **and no score_open/score_ops formula** changes | Soft tests stable |
| K11 | CI via `--fixture-root` + `tests/fixtures/pilot/` | `outputs/` gitignored |
| K12 | Honesty banner + catalog provenance flag mandatory | Non-negotiable |
| K13 | PR1 → PR2 sequential on `decide_service.py` (no parallel) | Reviewable, conflict-free |
| K14 | Report pure function + budget + no literal ha in templates | Determinism + honesty |
| K15 | Catalog load vs path base are **two** total functions; bare `--fixture-root` auto-loads `DIR/pilot_sites.json` | G4/T6 without guessing (Issue 13) |
| K16 | Named AND+EXT industrial scorecards checked **simultaneously**; both present → None | Fail-honest total discovery (Issue 14) |

---

## 12. Open Questions

| # | Question | Default if unresolved |
|---|----------|----------------------|
| Q1 | Commander/metrics hub industrial scorecards same PR as adapter? | **No** — follow-up |
| Q2 | Tobarra default window mid vs early? | **`mid`** |
| Q3 | Anchor helper in decide_service vs pilot-only? | **Pilot-only** is OK if loaders stay pure; attach in pilot after load |
| Q4 | importlib demo helpers vs package extract? | **importlib first** |
| Q5 | Commit regenerated docs report in PR4? | **Yes** |

---

## 13. PR Plan (ordered — **no parallel** on `decide_service.py`)

### PR1 — Open metrics adapter (industrial + legacy)

| | |
|--|--|
| **Title** | `fix(product): load open metrics from AND/EXT industrial scorecards` |
| **Depends on** | S2-4 precondition: main CI green |
| **Files** | `wildfire_front/product/decide_service.py`; `tests/test_open_metrics_pack_adapter.py`; `tests/fixtures/pilot/open_and_min/*`; `tests/fixtures/pilot/open_ext_min/*` |
| **Description** | Implement §4.2 total function. Preserve pista_b. Ban firms ha / ROS keys. PARTIAL returns ha. Multi-match → None. |
| **DoD** | Adapter tests green; fixture AND/EXT areas resolve |

### PR2 — Ops metrics from temporal window layout

| | |
|--|--|
| **Title** | `fix(product): load ops metrics from operational_metrics/front_dynamics dirs` |
| **Depends on** | **PR1** (same module sequential) |
| **Files** | `wildfire_front/product/decide_service.py`; `tests/test_ops_metrics_work_dir.py`; `tests/fixtures/pilot/ops_tobarra_min/*` |
| **Description** | Implement §4.4 including `structural.primary_ros_m_min`, ROS-required return None, F non-overwrite. |
| **DoD** | Window fixture → non-null ROS; anchor-only → None |

### PR3 — Pilot orchestrator + ops-wired card helper

| | |
|--|--|
| **Title** | `feat(pilot): multi-pack honesty card offline orchestrator` |
| **Depends on** | PR1 + PR2 |
| **Files** | `scripts/run_ml_live_card_demo.py` (`ops_metrics` pass-through); `scripts/run_pilot_honesty_card.py`; `tests/test_pilot_honesty_card.py`; `tests/test_ml_live_card_demo.py` (ops regression); `tests/fixtures/pilot/pilot_sites.json`; `tests/fixtures/pilot/anchors_tobarra_snippet.json` |
| **Description** | Fixture catalog CLI; 3-site offline; field_ops contrast without fake reliability; sources allowlist; T6–T9/T11. |
| **DoD** | Bare `--fixture-root tests/fixtures/pilot` (no `--sites-config` required) writes 3 cards with ops on Tobarra; auto-loads `pilot_sites.json`; pytest offline green |

### PR4 — ≤2-page report + docs publish

| | |
|--|--|
| **Title** | `docs(pilot): honesty report ≤2p from Decision Cards` |
| **Depends on** | PR3 |
| **Files** | report renderer (in pilot script or `wildfire_front/product/pilot_report.py`); `docs/PILOT_HONESTY_CARD.md`; facts_table wiring; T10 |
| **Description** | Pure `render_report`; budget ≤90 lines / ≤1200 words; numbers only from facts/summaries/u1; u1_source label. |
| **DoD** | Budget test green; required honesty substrings; fixed `generated_at` deterministic |

### PR5 — (Optional) Makefile + cross-links

| | |
|--|--|
| **Title** | `chore(pilot): make pilot-honesty + doc cross-links` |
| **Depends on** | PR4 |
| **Files** | `Makefile`; pointers in multi-CCAA design / POST_S1 plan; demo help text |
| **DoD** | `make pilot-honesty` runs fixture-root offline path |

### Explicitly not in these PRs

- Retrain / ECE lab  
- field_ops fusion ON  
- New CCAA packs  
- Portal HTML redesign  
- Commander industrial migration  
- Fake reliability unlock for field_ops GO  

---

## 14. Risks & mitigations

| Risk | Mitigation |
|------|------------|
| Open conf low with `n_timeline_steps=1` | Soft check `decision in {HOLD,GO}` + `open available`; **do not** change score_open formula |
| Tobarra ROS null in some windows | Default mid; structural + front_dynamics priority; else None honest |
| Real packs absent in CI | `--fixture-root` only path for pytest |
| field_ops GO expectation from sales narrative | Document fail-closed; report HOLD/ABSTAIN |
| Report drift of ha literals | Pure interpolate; ban template literals |
| Merge conflicts on decide_service | PR1 → PR2 sequential (K13) |

---

## 15. References (repo)

- `scripts/run_ml_live_card_demo.py` — Sprint 1 Card demo (extend ops_metrics)  
- `wildfire_front/product/decide_service.py` — source loaders  
- `wildfire_front/product/confidence.py` — score_* + field_ops fail-closed  
- `config/decision_policies.json`  
- Pack paths under `outputs/open_if/…` (local only)  
- `outputs/temporal_windows/tobarra_20240802/`  
- `data/infocam_anchors.json`  
- `docs/design/ML_FOCUS_PRODUCT_V1.md`  
- `docs/PLAN_PROGRAMACION_EMAILS_20260724_POST_S1.md`  

---

*End of design rev 3 — P1 Piloto pack real multi-fuente + informe honesty.*
