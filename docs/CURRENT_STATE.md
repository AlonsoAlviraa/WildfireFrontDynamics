# Current state — WildfireFrontDynamics

> **As of:** 2026-08-11  
> **Authority:** this file + live scorecards + `outputs/ml_eval/canonical/`.  
> Long form: `docs/PROJECT_STATUS.md`. Goals hub: `docs/goals/README.md`.  
> Repo map: `docs/REPO_MAP.md` · ML proven: `docs/ml/README.md`.  
> **SPA SSOT:** `docs/APP.md` · audit + 10-PR residual plan:  
> [`docs/AUDIT_AND_PR_PLAN_SPA_C2_20260811.md`](AUDIT_AND_PR_PLAN_SPA_C2_20260811.md)

---

## One-line truth

**GO_MES true · GO_Q partial (H1) · SPA industrial C2 shippable eng · ML thrash FREEZE + REQUEST_DATA · sealed LOFO 0.788 · weather ERA5 long +0.019 · Tobarra KEEP KILL · fusion OFF · `ml_product_go` true.**

| Gate | Value | Notes |
|------|--------|--------|
| **GO_ENG** | **true** | CI, dual product, Decision Card, demos |
| **GO_MES** | **true** | O1∧O4∧P1∧M2∧E1 mínimo · `docs/GO_MES_VERDICT.md` |
| **GO_MES+** | **false** | O5 2º grade A / O2 nacional / demo |
| **GO_Q** | **partial** | stack green; **H1** demo+acta tercero pending — **not true** without H1 |
| **ml_product_go** | **true** | lab GO ≠ field fusion |
| **field_ops ML fusion** | **OFF** | non-negotiable without human promote |
| **ML closeout** | **FREEZE_ML_AND_REQUEST_DATA** | `docs/GOAL_ML_CLOSEOUT.md` · canonical stamp |
| **SPA industrial C2** | **eng OK** | dual-mode · primary acts · `#0B1220` · Live Ops on `--serve` |
| **Live Ops / demo-day** | **eng OK** | `app --demo-day` · fusion OFF · residual = H1 human (G10) |
| **Confirmed anchors** | **2** | Tobarra + Hellín 2024-07-19 |

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

**Do not promote:** Open-Meteo weather, era5 multi-fire pack, era5 finetune, lofo_v4 as sealed replacement.

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

## What works (shippable eng)

- **Product SPA industrial C2 + Live Ops** (`app` / `spa` / `console`): map-first, dual-mode Fácil|Pro, primary acts Estado·Decidir·Acta **execute on loopback** (`--serve` / `--demo-day` → `POST /live/v1/*`), role switcher, multi-fire pack, third-party pack checks · doc `docs/APP.md` · `docs/design/LIVE_OPS_DEMO_KERNEL.md`
- Operator UX: `python -m wildfire_front operator` (plateau eng; residual = H1 human)
- Decision Card + incident outbox + `serve-decide` (optional SPA bridge when flagged)
- Open packs CEMS / AND / EXT + third-party pack + replay
- ML lab CLI: `ml list|show|cases|curve|freeze|smoke|lofo|next|doctor|card|predict`
- Tobarra AEMET envelope path (fusion weight 0)
- Graph v6.1: primary = H1 + E1–E3; research R\* **0 h retrain** as main engine

### SPA residual gates (audit 2026-08-11)

| Gate | Eng control | Residual |
|------|-------------|----------|
| GO_Q | **must stay partial** unless H1 closes | human demo+acta |
| field_ops fusion | **OFF** | no flip without promote |
| SPA markers | CI pack `make test-spa` + release flags | G7 closed |
| Multi-IF live switch | optional `--pack-fires` / `--all-fires` | size cap N=8 |
| Live Decision Card | **`/live/v1/decide`** (preferred) · optional `--bridge-decide` | offline embed if no serve |
| Demo-day | `app --demo-day` | pack + reliability presence; `go_q_met=false` |

Full gap table G1–G10 + 10-PR stack: **`docs/AUDIT_AND_PR_PLAN_SPA_C2_20260811.md`**.

---

## What is blocked / next (priority)

| Priority | Item | Owner |
|----------|------|--------|
| **P0 product** | **H1** demo tercero + acta → GO_Q (**not eng-closable**) | human calendar |
| **P0 evidence** | E1–E3 pack + Reliability + replay — **eng surface:** `app --demo-day` + live Replay (presence + `replay_ok`); residual = human show | eng done / human demo |
| **P0 lab (done 2026-08-05)** | S1 SDC **KILL promote** (keep iter1 reject) · S3 open H-lite board · S4 arrival multipass Tobarra **OK** (`outputs/tobarra_multipass_s4/`) | lab |
| **P1 data** | O2 perímetro nacional / O5 2º grade A | external |
| **P1 ML data** | **Chain_honest multi-day IF** (FOV alineado + timestamps ERA5) — no thrash recipe | data + lab |
| **P2 ML** | Frozen residual-small thrash; only re-open with new data class | lab |
| — | CyL 4082 / GAL Extinción waits | transparency |

**Research expansion (2026-08-05):** `docs/fire_intel/DEEP_RESEARCH_STRATEGIES_2024_2026.md` (75 claims verified, 0 dropped).

Explicit non-goals while blocked:

- Flip field_ops fusion without human promote (`ml_product_go` already promoted 2026-08-05; lab GO ≠ field fusion)  
- ECE post-hoc on U1 / Tobarra TEST  
- Claim IoU = ROS  
- More autonomous honesty cycles as substitute for H1  

---

## Commands (status hygiene)

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "."
python -m wildfire_front operator
python -m wildfire_front app --fire _sla_measure --open
python -m wildfire_front ml freeze
python -m wildfire_front ml show
python scripts/check_release_flags.py
make test-spa
```

Goals detail: **`docs/goals/README.md`**.  
SPA product: **`docs/APP.md`**.  
SPA audit / residual: **`docs/AUDIT_AND_PR_PLAN_SPA_C2_20260811.md`**.  
ML lab entry: **`docs/ML_PRODUCT_START_HERE.md`**.  
**Mega auditoría venta:** **`docs/MEGA_AUDIT_SELL_20260805.md`** (qué falta para vender piloto).
