# VISION — WildfireFrontDynamics

## What we build (today)

**Decision support for wildfires** with three honest pieces:

1. **Thermal ops** (`incident_runtime_v1`) — observed front + ROS from LWIR when a drone exists  
2. **Open perimeter** — public CEMS/EFFIS multi-day packs when there is no NDA  
3. **Fire Decision Card** — **GO / HOLD / ABSTAIN** + confidence + audit hashes  

We do **not** claim 99.9999% fire-spread accuracy. That figure, when used at all, is only the residual risk of a **silent GO** under automated gates in tests.

## North star (dream)

See the full aspirational document (Spanish):

### → [`docs/SUENOS_MAXIMOS.md`](docs/SUENOS_MAXIMOS.md)

That file is the **maximum** results and features this repository could achieve: crisis-room fusion, sub-minute Decision Cards, multi-region ML with calibration, national perimeter anchors, forensic replay, paid pilots — without lying about physics.

## Why it matters

Wildfires move faster than bureaucracy. What pays in the field is not another free map: it is knowing **when to trust**, **when to hold**, and **when the system must stay silent** — with a trail an auditor can rebuild.

## Current phase (2026-07)

| Layer | State |
|-------|--------|
| ML Spain ensemble | `clm_ensemble_v34` · U1 TEST honest ~**0.86** IoU / ECE ~**0.15** · catalog holdout **0.8963** provenance only (not live certainty) |
| Incident runtime | Outbox includes **fire_decision_card.json** on every update |
| Open CEMS | **4** packs demo-ready |
| Product gates | Metrics Hub + reliability gate + portal (`docs/PORTAL.html`) |

Near-term plan: [`docs/PLAN_3_MESES.md`](docs/PLAN_3_MESES.md)  
Start here: [`docs/START_HERE.md`](docs/START_HERE.md)

## Core principles (non-negotiable)

1. **Ops ≠ ML ≠ open** — fuse only in the Decision Card  
2. **Abstention is a feature** — empty or weak sources → ABSTAIN  
3. **Leak-free evaluation** — never tune on the holdout test  
4. **Provenance** — every metric has source, version, UTC  
5. **Champion protection** — no training loop overwrites the promoted model without gates  
6. **Honest claims** — system reliability ≠ fire prediction accuracy  

## Success (near) vs success (dream)

| Horizon | Definition |
|---------|------------|
| **Near (GO_Q)** | Decision Card in CLI + incident outbox; hub + reliability green; ≥4 open packs; v34 not regressed; pilot path or outreach evidence |
| **Dream** | Crisis room uses live FDC with multi-source fusion; 20+ IF/year audited; multi-region calibrated ML; signed API; organism pays for **trust + audit**, not for pretty maps |

Details and target tables: **`docs/SUENOS_MAXIMOS.md`**.
