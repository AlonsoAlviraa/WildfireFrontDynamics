# Current state — WildfireFrontDynamics

> **As of:** 2026-08-12  
> **Branch tip (eng):** `fix/b2-b3-flags-noise-20260810` @ `1a709a3` (SPA Live Ops + product stack pushed)  
> **Authority:** this file + live scorecards + `outputs/ml_eval/canonical/`.  
> Long form: `docs/PROJECT_STATUS.md`. Goals hub: `docs/goals/README.md`.  
> Repo map: `docs/REPO_MAP.md` · ML proven: `docs/ml/README.md`.  
> **SPA SSOT:** [`docs/APP.md`](APP.md) · Live Ops: [`docs/design/LIVE_OPS_DEMO_KERNEL.md`](design/LIVE_OPS_DEMO_KERNEL.md)  
> **Grok Bot org (teammates):** [`docs/EMPRESA_BOTS_TRABAJADORES.md`](EMPRESA_BOTS_TRABAJADORES.md)  
> **Post–Live Ops PR plan:** [`docs/PLAN_PR_POST_LIVE_OPS.md`](PLAN_PR_POST_LIVE_OPS.md)  
> SPA audit residual: [`docs/AUDIT_AND_PR_PLAN_SPA_C2_20260811.md`](AUDIT_AND_PR_PLAN_SPA_C2_20260811.md)

---

## One-line truth

**GO_MES true · GO_Q partial (H1 human) · SPA industrial C2 + Live Ops eng-shipped · `app --demo-day` primary third-party surface · ML FREEZE + REQUEST_DATA · sealed LOFO 0.788 · Tobarra KEEP KILL · fusion OFF · `ml_product_go` true (lab only).**

| Gate | Value | Notes |
|------|--------|--------|
| **GO_ENG** | **true** | CI, dual product, Decision Card, demos, Live Ops |
| **GO_MES** | **true** | O1∧O4∧P1∧M2∧E1 mínimo · `docs/GO_MES_VERDICT.md` |
| **GO_MES+** | **false** | O5 2º grade A / O2 nacional / demo firmada |
| **GO_Q** | **partial** | stack green; **H1** demo+acta tercero — **not true** without H1 |
| **ml_product_go** | **true** | lab GO ≠ field fusion |
| **field_ops ML fusion** | **OFF** | non-negotiable without human promote |
| **ML closeout** | **FREEZE_ML_AND_REQUEST_DATA** | `docs/GOAL_ML_CLOSEOUT.md` · canonical stamp |
| **SPA industrial C2** | **eng OK** | dual-mode · primary acts · `#0B1220` · Live Ops on `--serve` |
| **Live Ops / demo-day** | **eng OK** | `POST /live/v1/{status,decide,export-acta,replay-third-party}` · `go_q_met=false` always from eng |
| **Confirmed anchors** | **2** | Tobarra + Hellín 2024-07-19 (Hellín cite UNAP; **promote grade A / O5 = pending**) |
| **P0 focus board** | active | `docs/FOCUS_P0_BOARD_20260812.md` — PR#10 hold · tokens · H1 · New Bot · marketing embargo · Hellín no-promote |

---

## Product freeze (do not regress without evidence)

| Layer | ID | Honest metric |
|-------|-----|----------------|
| ML sealed LOFO | `exact_force_ema_long` residual-small | core3 mean **0.7878** · min **0.7071** |
| ML weather spatial | `era5_long` spatial_v1 + ERA5-Land | mean **0.5762** · ΔW0 **+0.019** (LIFT) |
| ML lab catalog | `clm_ensemble_v34` | holdout **0.8963** provenance only · **≠ ROS** |
| ML surface | lab reject thr ~**0.80** | iter1 reject only (no ECE thrash) |
| ML multi-fire | LOFO + Head A | Tobarra KEEP **KILL**; Hellín held useful |
| Ops | `front_dynamics_v1` | Tobarra grade **A**, ROS ~5.71 vs Vp 7 |
| Decision | Decision Card | GO / HOLD / **ABSTAIN** |
| Product SPA | `wfd_product_app_v1` | Live Ops loopback · fusion OFF · no GO_Q invent |

**Do not promote:** Open-Meteo weather, era5 multi-fire pack, era5 finetune, lofo_v4 as sealed replacement · field_ops ML live fusion ON.

---

## Mega goals (ML lab) — closed 2026-08-05

| Goal | Status | Scientific outcome |
|------|--------|-------------------|
| **W3** new fires + protocol | **MET** | Hellín / Brazatortas / Retuerta Head A frozen thr=0.795; leak=0; rails cold |
| **Tobarra KEEP-or-KILL** | **MET (process)** | Fresh LOFO train → **KILL** (K1 fail) |

| Fresh Tobarra LOFO | Value |
|--------------------|------:|
| model IoU (test) | **0.4776** |
| Δ vs copy | **+0.149** (K2 PASS) |
| Head A baseline | **0.4894** |
| K1 lift | **−0.012** (need ≥ +0.03) → **KILL** |
| leak train/val | **0** |

Boards:

- W3: `docs/ML_LOOP_ITERATIONS/iter_w3_mega_goal_latest.md`
- Tobarra: `docs/ML_LOOP_ITERATIONS/iter_tobarra_keep_or_kill_latest.md`
- Scorecard: `outputs/ml_eval/lab_loop/tobarra_keep_or_kill_scorecard.json`

**Do not** re-open Tobarra KEEP with the same recipe without new signal (features / data / protocol).  
**Do not** treat beats-copy as KEEP.

---

## What works (shippable eng) — 2026-08-12

### Product surface (primary for third parties)

- **SPA industrial C2 + Live Ops Kernel**
  - CLI: `python -m wildfire_front app` · aliases `spa` · `console`
  - **Presentador one-shot:** `python -m wildfire_front app --demo-day`
  - Loopback serve: `--serve` → same-origin  
    `POST /live/v1/status` · `/decide` · `/export-acta` · `/replay-third-party`
  - Dual-mode Fácil|Pro · primary acts Estado · Decidir · Acta  
  - Multi-fire pack (`--all-fires` / `--pack-fires`, cap 8)  
  - Docs: `docs/APP.md` · `docs/design/LIVE_OPS_DEMO_KERNEL.md` · `docs/CHEATSHEET_DEMO_12MIN.md`
- **H1 eng prep (no GO_Q flip):** `scripts/prepare_h1_demo_session.py` · `docs/H1_*` · acta draft PENDING  
- **Release hygiene:** `scripts/check_release_flags.py` (SPA markers + Live Ops + demo-day) · `make test-spa`

### Core product

- Operator UX: `python -m wildfire_front operator` (plateau eng; residual = H1 human)
- Decision Card + incident outbox + `serve-decide` (optional `--bridge-decide`; prefer Live Ops)
- Open packs CEMS / AND / EXT + third-party pack + replay (`scripts/run_third_party_replay.py`)
- ML lab CLI: `ml list|show|cases|curve|freeze|smoke|lofo|next|doctor|card|predict`
- Tobarra AEMET envelope path (fusion weight 0)
- Graph v6.1: primary = **H1 human** + evidence show; research R\* **0 h retrain**

### SPA / Live Ops residual gates

| Gate | Eng control | Residual |
|------|-------------|----------|
| GO_Q | **must stay partial** unless H1 closes | human demo+acta |
| field_ops fusion | **OFF** | no flip without promote |
| SPA markers | `make test-spa` + release flags | closed eng |
| Multi-IF switch | `--pack-fires` / `--all-fires` | cap N=8 |
| Live Decision Card | **`/live/v1/decide`** (`live_ops_loopback`) | outbox may differ; ABSTAIN valid |
| Demo-day | `app --demo-day` | pack/reliability **presence**; human show |
| E1–E3 evidence | eng surface via demo-day + Replay | human presents to third party |

---

## What is blocked / next (priority)

| Priority | Item | Owner |
|----------|------|--------|
| **P0 product** | **H1** demo tercero + acta firmada → GO_Q (**not eng-closable**) | human calendar · `FOCUS_P0_BOARD` §3 |
| **P0 SPA merge** | PR **#10 HOLD** until clean history path (secrets once in branch history) | eng · board §1 |
| **P0 security** | Rotate OAuth/tokens that lived in historical Gmail/outreach dumps | human · board §2 |
| **P0 evidence show** | Run `app --demo-day` + pack + reliability in front of third party | human + eng prep done |
| **P0 marketing** | **EMBARGO** outbound until Claims clear | Claims + human · board §5 |
| **P0 Hellín** | No promote grade A / O5 / pitch without verified cite; promote SSOT **pending** | eng + human · board §6 |
| **P0 lab (done)** | S1 SDC KILL promote · S3 open H-lite · S4 multipass Tobarra OK | lab closed |
| **P1 data** | O2 perímetro nacional / O5 2º grade A (B4/B5) | external |
| **P1 ML data** | **Chain_honest multi-day IF** (FOV + timestamps ERA5) | data + lab |
| **P2 ML** | Residual-small thrash only with **new data class** | lab |
| **P2 ops** | Grok Bot teammates onboarding (optional): `docs/EMPRESA_BOTS_TRABAJADORES.md` | human |
| — | CyL 4082 / GAL Extinción waits | transparency |

**Research:** `docs/fire_intel/DEEP_RESEARCH_STRATEGIES_2024_2026.md` (75 claims verified).

### Explicit non-goals

- Flip field_ops fusion without human promote  
- ECE post-hoc thrash on U1 / Tobarra TEST  
- Claim IoU = ROS · FIRMS = perímetro oficial  
- Invent GO_Q / `go_q_met=true` from eng scripts  
- Substitute autonomous honesty cycles for H1  
- Commit oversized Kaggle spatial zips / raw 20260803 drop (local only; gitignored)

---

## Commands (status hygiene)

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "."

# Presentador H1 / third party (primary)
python -m wildfire_front app --demo-day
# Snapshot CI (no hang):  python -m wildfire_front app --demo-day --json

python -m wildfire_front operator
python -m wildfire_front ml freeze
python -m wildfire_front ml show
python scripts/check_release_flags.py
make test-spa
python scripts/prepare_h1_demo_session.py
```

---

## Doc map (SSOT)

| Doc | Role |
|------|------|
| **`docs/CURRENT_STATE.md`** | **This file — gates + freeze** |
| **`docs/FOCUS_P0_BOARD_20260812.md`** | **Active focus: #10 hold · tokens · H1 · New Bot · marketing · Hellín** |
| `docs/START_HERE.md` | Onboarding 2 min |
| `docs/APP.md` | SPA + Live Ops flags/API |
| `docs/design/LIVE_OPS_DEMO_KERNEL.md` | Live Ops design |
| `docs/EMPRESA_BOTS_TRABAJADORES.md` | Grok Bot teammates (product 2026-08-11) |
| `docs/PLAN_PR_POST_LIVE_OPS.md` | Land + residual PR stack |
| `docs/H1_GO_Q_RUNBOOK.md` · `docs/CHEATSHEET_DEMO_12MIN.md` | H1 human path |
| `docs/GOAL_ML_CLOSEOUT.md` · `docs/ml/README.md` | ML freeze |
| `docs/REPO_MAP.md` | Folder map |
| `docs/MEGA_AUDIT_SELL_20260805.md` | Sell residual (H1) |

Goals detail: **`docs/goals/README.md`**.
