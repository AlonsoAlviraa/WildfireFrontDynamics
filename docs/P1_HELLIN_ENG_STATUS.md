# P1 Hellín — Engineering status (Track A + GO_MES clarify)

**Date:** 2026-08-12 (promote SSOT clarified)  
**Anchor O1:** cite UNAP boletín 2024-07-20 — **Vp = 50 m/min**, area 100 ha* (estimated, non-official)  
**Promote SSOT:** **`pending`** — do **not** promote grade A / O5 / commercial pitch without re-verified cite + human OK  
**Focus board:** `docs/FOCUS_P0_BOARD_20260812.md` §6

## Two different “P1” meanings

| Meaning | Definition | Status |
|---------|------------|--------|
| **P1 plan mínimo (GO_MES)** | `incident_runtime` smoke on **2 real IFs without crash** | **PASS** — `smoke_incident_runtime.py --p1-two-real` |
| **P1/O5 eng stretch** | 2º IF structural **grade A** + ratio in-band | **ENG BLOCKED** for Hellín (best **B** / 0.56) |

**GO_MES uses the plan-minimum row.** Grade A is **GO_MES+ / O5**, not GO_MES.

## Verdict (ops pack Hellín)

Hellín can sit as **O1 second anchor with cite** (Vp 50). Ops pack is **grade B, ratio in band** at best. **Product/O5 promote remains pending.**

| Gate | Result |
|------|--------|
| O1 multi-anchor + ratios in band | **PASS** (with documented cite) |
| P1 smoke 2 real IFs | **PASS** |
| O5 second grade A | **NO** — only Tobarra is A |
| GO_MES (plan mínimo) | **GO_MES** — `docs/GO_MES_VERDICT.md` |
| Structural grade A + in-band Hellín | **ENG BLOCKED** (rules vs Vp=50) |
| **Promote SSOT** | **pending** — no pitch as grade A / official ha |

**Do not invent Vp/ha. Do not joint-k Tobarra(7)+Hellín(50). Do not silent-rescale ROS to Vp. Do not promote without cite re-verify.**

## Best retained pack (canonical)

```
python scripts/build_observatory_pack.py --fires hellin_2024 --max-frames 10 --max-side 2500
# default --min-component-pixels 800
python scripts/score_hellin_track_a.py
```

| Metric | Value |
|--------|-------|
| Structural grade | **B** (“orientativo — muestra corta”) |
| Primary ROS | **27.934 m/min** (n=1, method `area_isotropic`) |
| Vp | 50.0 m/min |
| Ratio ROS/Vp | **0.559** |
| In band [0.5, 2.0] | **yes** |
| Grade A eligible | **NO** |
| P1 closed | **NO** |
| Pack path | `outputs/observatorio/hellin_2024` |

## Attempts (evidence)

| Attempt | Params | Staged frames | Grade | ROS m/min | Ratio | In band | Notes |
|---------|--------|---------------|-------|-----------|-------|---------|-------|
| 1h-loop v1 | max-frames=16, max-side=4000, min-comp=150 | 12 | **A** | 10.98 | 0.220 | **NO** | Structural A only — ROS too low vs Vp50 |
| 1h-loop v2 | max-frames=12, max-side=2200, min-comp=100 | 9 | B | 24.54 | 0.491 | **NO** | Near band floor (0.5) |
| 1h-loop pair (best) | max-frames=10, max-side=2500, min-comp=800 | 9 | B | **27.93** | **0.559** | **yes** | **Canonical best** |
| Track-A extra (2026-08-04) | max-frames=14, max-side=3000, min-comp=120 | 11 | B | 14.27 | 0.285 | **NO** | n_primary=2; longer Δt pair dilutes median; **regressed** |
| Restore after extra | max-frames=10, max-side=2500 | 9 | B | 27.93 | 0.559 | yes | Re-applied best params |

Sources: `outputs/plan_1h_loop/hour_loop_report.json`, this session rebuild + score.

## Why grade A + in-band is not reachable with current rules + data

Structural grade A in `wildfire_front/front_dynamics.py` requires **all** of:

1. `primary_ros_n >= 3`
2. `0.3 <= median_primary_ros <= 25` m/min
3. multi-method **or** mean coreg shift &lt; 15 m

In-band vs Vp=50 requires:

- `25 <= primary_ros <= 100` m/min  (ratio ∈ [0.5, 2.0])

**Intersection of (2) and in-band is only ROS ≈ 25 m/min** (a razor edge). Empirical packs never hit that edge with n≥3:

- When structural **A** is achieved (attempt v1), median ROS is ~11 m/min → ratio ~0.22 **out of band**.
- When ratio is **in band** (best pack), n_primary=1 and ROS ~28 → grade **B** (“muestra corta”), and ROS already **above** the structural-A ceiling of 25.

Additional data limits:

- Only **16** LWIR masks / **36** reprojected frames; densest temporal window still dominated by **abstained_dt** pairs (sub-minute dt).
- Area series max ~**44 ha** vs boletín **100 ha*** → FOV / mask incompleteness (not full fire footprint).
- Primary method is almost always single-estimator `area_isotropic` (no multi-estimator A path).

## Blocked reason (eng)

**P1 / O5 cannot be closed by further mask-parameter tuning alone.**  
Trade-off is structural: rules that award grade A cap ROS at 25 m/min; Hellín’s confirmed Vp is 50, so honest in-band ROS sits near/above that cap while sample size stays n=1–2 under real pair geometry.

Unblocking options (policy / product, not silent k-fit):

1. **Accept eng BLOCKED** for GO_MES: keep Hellín as confirmed anchor + grade-B in-band ops; require a different second grade-A IF for O5/P1.
2. **Policy change** (explicit, versioned): separate “anchor compatibility grade” from structural grade A, or raise structural-A ROS ceiling for high-Vp fires without rescaling.
3. **New data**: full-perimeter series / longer valid dt pairs that yield n_primary≥3 near ~25 m/min without inventing speeds — low probability given FOV gap.

## Honesty

- No silent rescale of ROS to Vp.
- No joint k Tobarra(7) + Hellín(50).
- Mask ROS is orientation / order-of-magnitude only — not tactical dispatch.
- Grade A without in-band does **not** close P1 Track A (`grade_a_eligible = structural_A AND in_band`).

## Related files

- Scorecard: `docs/HELLIN_TRACK_A_SCORECARD.md` / `.json`
- Pack score: `outputs/observatorio/hellin_2024/track_a_scorecard.json`
- Front dynamics: `outputs/observatorio/hellin_2024/front_dynamics.json`
- GO_MES recompute: `docs/O1_GOMES_RECOMPUTE_20260803.json`
- Anchors: `data/infocam_anchors.json`
- Loop evidence: `outputs/plan_1h_loop/hour_loop_report.json`
