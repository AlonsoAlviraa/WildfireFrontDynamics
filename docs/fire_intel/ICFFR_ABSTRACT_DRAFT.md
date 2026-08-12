# ICFFR abstract draft (I2) — draft only

**As of:** 2026-08-04  
**Graph ID:** I2  
**Event:** 10th ICFFR + 19th IAWF Safety Summit · Coimbra · 31 Oct – 6 Nov 2026  
**URL:** https://events.adai.pt/en/10th-icffr  
**Status:** **DRAFT only** — not submitted · not peer-reviewed  

---

## Title (working)

**Multi-anchor thermal front rate-of-spread with explicit abstention: an operational honesty design for Mediterranean wildfires**

## Authors (placeholder)

*[Team / affiliation TBD — do not invent institutional endorsements]*

## Abstract (~220 words)

Operational wildfire intelligence often either over-promises forecast skill or collapses to pure simulation without measured front kinematics. We present a dual-product design that separates (i) **ops thermal front rate-of-spread (ROS)** estimated from multi-frame LWIR sequences when geometry and time support defendable motion, and (ii) **open emergency-mapping perimeters** (Copernicus EMS / EFFIS-class) as monitoring layers that never silently replace national cadastre.  

On the Spanish Mediterranean case **Tobarra (2024-08-02)** we report structural **grade A** multi-estimator ROS on the order of **~5.7 m/min** primary (sector head/flank/rear exported as guidance, not independent tactical sensors), against an INFOCAM velocity anchor, with explicit ratio reporting. Additional incidents illustrate **honest grade degradation** (e.g. Hellín) rather than parameter spam toward a second grade-A claim.  

Decision fusion is expressed as a **Decision Card** with sources, weights, and outcomes **GO / HOLD / ABSTAIN**. Machine-learning segmentation metrics (IoU) remain **provenance / lab** and are **not fused** into field recommendations (`ml_live` fusion off). Uncertainty communication follows an Orion-class separation of aleatory/epistemic concerns mapped to abstention rails — **not** renamed into evacuation orders.  

A third-party offline pack and forensic replay check internal consistency of cards without claiming cryptographic anti-forgery or fire-spread five-nines accuracy. We argue that **multi-anchor honesty + abstention** is a necessary industrial control for wildfire front products in the Mediterranean, complementary to landscape simulators (ELMFIRE/ForeFire) used only as lab priors.

## Keywords

wildfire front; rate of spread; LWIR; Copernicus EMS; decision support; abstention; Mediterranean; uncertainty

## Design points to keep if revised

| Point | Keep |
|-------|------|
| Multi-ancla (Tobarra + honest non-A) | yes |
| ABSTAIN as first-class outcome | yes |
| IoU ≠ ROS | yes |
| CEMS ≠ national O2 | yes |
| No EVAC product labels | yes |
| No fusion-ON claim | yes |

## Submission hygiene

- Deadline historically ~**15 Mar 2026** (verify on event site before submit).  
- This file is **not** a submission packet (figures, ethics, author list pending).  
- Do not cite invented metrics; pull numbers only from pack/scorecard paths.  

## Related evidence paths

- `outputs/demo_third_party/`  
- `docs/RELIABILITY_GATE_REPORT_THIRD_PARTY.md`  
- `docs/fire_intel/SECTOR_ROS_TOBARRA_NOTE.md`  
- `docs/METRICS_HONESTY_IOU_NE_ROS.md`  
