# PR Plan — MultiHorizon FieldOps (1h / 3h / 5h / 12h / 24h)

**Date:** 2026-08-06  
**Impact audit:** `docs/MULTIHORIZON_IMPACT_AUDIT_20260806.md` → **NO_METRIC_LIFT** on IoU/KEEP/GO_MES; product surface only.  
**Research base:** `docs/DEEP_RESEARCH_UNET_SCALE_MULTIHORIZON_20260806.md` (104 verified claims).  
**Rails:** fusion OFF · IoU ≠ ROS · no Tobarra KEEP reopen · no ECE thrash · lab ML path unchanged · **no larger U-Net as default bet**.

## Problem

Industry sells **1–24 h** re-sim (Technosylva, OroraTech, WIFIRE). Our ML product is **next-day mask**.  
Dual stack must expose **explicit multi-horizon field_ops** and then **close the skill gap** vs anisotropic hybrid ops — without pretending lab IoU is ROS.

## Honest status after PR1–PR4

| Delivered | Skill impact |
|-----------|--------------|
| Isotropic `d = ROS × h × 60` + CLI + S4/PSB hooks | **API / sell shape** |
| Tobarra Vp demo + S4 ROS attach path | Provenance, not Hausdorff win |
| Lab IoU / Tobarra KEEP / GO_MES | **Unchanged** |

**Do not claim metric improvement until PR8 (multipass validation) shows positive envelope skill.**

---

## PR DAG (full)

```text
                    ┌─► PR5 sector anisotropic ──┐
PR1 core ─► PR2 ─► PR3 ─► PR4                    ├─► PR8 multipass validate ─► PR9 re-init loop
                    └─► PR6 S4 re-export ROS ─────┤         │
                    └─► PR7 hybrid Rothermel/fuel ─┘         │
                                                            ▼
PR10 GeoJSON/ops export ◄── PR8/9                 PR11 lab track (optional lightweight only)
PR12 operator/decide surface ◄── PR10             PR13 wind stack (when AEMET/fuel fresh)
```

### Wave A — shipped

| PR | Deliverable | Acceptance | Status |
|----|-------------|------------|--------|
| **PR1** | `wildfire_front/multihorizon_fieldops.py` | Lead times (1,3,5,12,24); isotropic; rails; JSON card | **done** |
| **PR2** | `arrival_ros` + PSB hooks | Multihorizon from measured ROS; honesty stamps | **done** |
| **PR3** | CLI `multihorizon` + Tobarra demo | JSON out; non-zero 1h advance | **done** |
| **PR4** | `tests/test_multihorizon_fieldops.py` | Green; IoU≠ROS asserts | **done** |

### Wave B — skill gap (research-driven)

| PR | Deliverable | Why (research claim IDs) | Acceptance | Status |
|----|-------------|--------------------------|------------|--------|
| **PR5** | **Sector anisotropic multihorizon** (`head/flank/rear`) via obs shape + `fuel.envelope` | Ops products sell head ROS / intensity bands (OroraTech 32; Technosylva IAA 1–2 h 28); isotropic under-sells fronts | head ≥ flank ≥ rear; method `anisotropic_ros_buffer_v1`; field_ops; tests | **done** |
| **PR6** | **S4 multipass re-export** with multihorizon from **geometry primary ROS** | Cardil/FireGuard multi-pass culture (101); S4 ~6.14 m/min @ Tobarra | script/board writes multihorizon; Vp vs geometry delta documented | **done** |
| **PR7** | **Hybrid multihorizon 1–24 h** via `fuel.envelope` sector shape | Industry Fire Spread = Rothermel/ForeFire (95–97); hybrid preferred (59, 77) | method `hybrid_sector_envelope_v1`; commercial hours; guidance not tactical | **done** |
| **PR8** | **Multipass validation scorecard** — envelope @ lead τ vs observed progression | Ops ROS on progression polygons (101); NIST LOFM ≠ burn scar lab (104) | JSON scorecard; metrics **not** ML IoU; PARTIAL if short span | **done** |
| **PR9** | **Re-init loop** on new IR frame | WIFIRE multi-run (35); ELMFIRE re-init (37) | CLI/script; stamps `reinit_from_frame`; never ML mask as 1h truth | **done** |
| **PR10** | **Ops export GeoJSON** of horizon rings | OroraTech GeoJSON/KML (95, 97) | honesty props; CLI `--geojson` | **done** |
| **PR11** | **Lab track only** — kill-criteria for larger U-Nets; no retrain | Larger models lose/tie LOYO (3, 8, 43) | written kill-criteria; **zero** field fusion | **done** (docs + rails) |
| **PR12** | **Operator / decide surface** — multihorizon on Decision Card | Dual SKU (95–100) | field when ops ROS; ABSTAIN if none; fusion OFF | **done** |
| **PR13** | **Wind / weather optional boost** | Technosylva 1 h WRF (26); misaligned weather hurts (44) | weather present → boost + provenance; missing → PR5/PR7 fallback | **done** |

### Wave C — explicitly out of scope / kill list

| Item | Reason |
|------|--------|
| Bigger U-Net / ViT as primary field product | Research: capacity ≠ LOYO win (3, 8, 43); cost/latency (46) |
| ML multi-day heads sold as tactical 1 h | Cadence mismatch LEO/satellite (87–90); LA 2025 life-safety window &lt;24 h (39, 41) |
| Field fusion ON from lab `ml_product_go` | Dual product rails immutable |
| Tobarra KEEP reopen / ECE thrash | CLOSED_KILL; separate mega-goal only |
| FireBench full LES train as ops SKU | Sim-to-real gap (24); optional research later |
| Claiming isotropic multihorizon improved IoU | Impact audit: **false** |

---

## Physics roadmap (honest)

| Method id | Formula / idea | Use when |
|-----------|----------------|----------|
| `isotropic_ros_buffer_v1` | \(d = v h 60\) circle/buffer | PR1–4 baseline |
| `anisotropic_ros_buffer_v1` | sector radii from head/flank/rear | PR5 |
| `hybrid_sector_envelope_v1` | obs × physics shape, horizons 1–24 h | PR7 |
| `reinit_multipass_v1` | recompute ROS each IR update | PR9 |

**Not** ML IoU. Never label model_iou as ROS.

---

## Priority order for next implementation sprint

1. **PR6** (cheap win: attach real S4 ROS to demos/boards)  
2. **PR5** (anisotropic — biggest credibility jump vs isotropic)  
3. **PR8** (prove/falsify skill on multipass — only path to claim “better results”)  
4. **PR7** + **PR9** + **PR10** (hybrid + re-init + export)  
5. **PR12** (operator surface)  
6. **PR13** (weather) when fuel/weather stack ready  
7. **PR11** only if lab NDWS track needs experiments — never blocks field_ops

---

## Files already delivered (Wave A)

| Path | Role |
|------|------|
| `wildfire_front/multihorizon_fieldops.py` | Core isotropic + from_s4 / from_psb |
| `wildfire_front/arrival_ros.py` | `build_s4_board` attaches multihorizon |
| `wildfire_front/progressive_burn/pipeline.py` | PSB → multihorizon |
| `wildfire_front/cli_multihorizon.py` | CLI |
| `scripts/run_multihorizon_tobarra_demo.py` | Tobarra demo |
| `tests/test_multihorizon_fieldops.py` | Tests |
| `docs/MULTIHORIZON_IMPACT_AUDIT_20260806.{md,json}` | Metric honesty |

### Quick verify (Wave A + B)

```bash
python -m wildfire_front multihorizon --tobarra-vp
python -m wildfire_front multihorizon --ros-m-min 6.14 --method anisotropic --geojson /tmp/mh.geojson
python -m wildfire_front multihorizon --ros-m-min 6.14 --method hybrid --json
python -m wildfire_front multihorizon --ros-m-min 6.14 --reinit-frame frame_03
python scripts/run_multihorizon_tobarra_demo.py
python scripts/run_reinit_multihorizon.py --ros-m-min 6.14 --frame frame_03
pytest tests/test_multihorizon_fieldops.py -q
```

### S4 measured ROS check (no code change required)

```text
geometry primary_ros ≈ 6.14 m/min → 1h advance ≈ 368 m
Vp cite 7.0 m/min → 1h advance = 420 m
O'Neill median ≈ 1.28 m/min (do not silently average into primary)
```

---

## Non-goals (unchanged)

- Retrain U-Net larger as the sell product  
- ML multi-day heads as field 1 h product  
- Field fusion ON  
- Inventing multipass IR if missing  
- Reopening Tobarra KEEP / ECE thrash  

## References (deep research)

Commercial dual stack: claims **26–41**, **95–104**.  
Model scale: claims **1–8**, **42–45**.  
Hybrid physics: claims **57–79**.  
Multi-step / re-init: claims **80–94**.
