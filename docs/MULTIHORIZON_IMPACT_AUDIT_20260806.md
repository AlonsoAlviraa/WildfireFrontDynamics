# MultiHorizon FieldOps — Impact audit (2026-08-06)

**Verdict: NO lift on lab ML / Tobarra / industrial gates.**  
PR1–PR4 delivered a **sell-surface field_ops API**, not a metric upgrade.

## What was measured

| Axis | Before multihorizon PRs | After PR1–PR4 | Delta |
|------|-------------------------|---------------|-------|
| Lab U1 honest mean IoU (`docs/ML_PRODUCT_SCORECARD.json`) | **0.8569** | **0.8569** | **0** |
| Catalog holdout IoU (provenance only) | 0.8963 | 0.8963 | 0 |
| Kaggle NDWS v21 `model_iou` | ~0.223 | ~0.223 | 0 (no retrain) |
| Tobarra LOFO KEEP/KILL | **KILL** (K1 lift −0.012) | **KILL** | 0 (not reopened) |
| GO_MES | false (O1/O2 external) | false | 0 |
| Field fusion | OFF | OFF | 0 (rails held) |
| Multi-horizon 1/3/5/12/24 h API | missing | **present** | product only |
| Tobarra ops ROS → multihorizon | not attached | S4 primary **6.14 m/min** → 1h **368 m** | ops path usable |

## What multihorizon actually does

Physics v1 (honest, isotropic):

\[
d_{\mathrm{m}} = \mathrm{ROS}_{m/min} \cdot h \cdot 60
\]

- Demo default: INFOCAM **Vp = 7 m/min** (cite) → 1h advance **420 m**.
- Real S4 Tobarra multipass (`outputs/tobarra_multipass_s4/s4_board.json`): geometry primary ROS **6.14 m/min** (compatible with Vp, ratio 0.88) → 1h **368 m**. O'Neill median is lower (**1.28 m/min**) — not silently averaged.
- Method label: `isotropic_ros_buffer_v1`. **Not** ML next-day IoU, not CFM, not WRF-SFIRE.

## Why this does not “improve results” (and should not claim to)

1. **Different product rail.** Lab scorecard is mask IoU / ECE. Multihorizon is field_ops geometry. Cross-claiming would violate dual-stack honesty (OroraTech / Technosylva split Burnt Area vs Fire Spread — deep research claims 95–104).
2. **No new data, no retrain, no LOFO.** Tobarra KEEP stays **CLOSED_KILL**; reopening would thrash ECE/KEEP rails.
3. **Isotropic buffer ≠ operational skill.** Industry sells wind/fuel anisotropic re-sim + re-init from IR (Technosylva &lt;30 s, WIFIRE multi-run, OroraTech 1–24 h Rothermel/ForeFire). Our v1 is a transparent envelope, not validated tactical dispatch.
4. **GO_MES still external-blocked** (O1 multi-anchor, O2 Hausdorff official) — unchanged by API surface.

## Positive (non-metric) gains

- Explicit commercial SKU shape: lead times **1 / 3 / 5 / 12 / 24 h**.
- CLI + Tobarra demo + S4/PSB hooks with rails stamps (`iou_is_not_ros`, fusion OFF).
- Path to attach **measured multipass ROS** instead of only Vp cite.

## Conclusion

| Question | Answer |
|----------|--------|
| Did results improve? | **No** on IoU / KEEP / GO_MES / NDWS. |
| Did sell surface improve? | **Yes** (multi-horizon field_ops product). |
| Next step | Expand PR plan from deep research — **physics/hybrid multihorizon + validation**, not larger U-Nets. |

See: `docs/design/PR_PLAN_MULTIHORIZON_FIELDOPS.md` (PR5+), `docs/DEEP_RESEARCH_UNET_SCALE_MULTIHORIZON_20260806.md`.

---

## Wave B note (PR5–PR13, 2026-08-06)

Wave B landed **field_ops skill-surface** (anisotropic / hybrid / re-init / GeoJSON /
multipass scorecard / decide attach / optional wind) **without** claiming lab IoU lift.

| Axis | After Wave B | Claim |
|------|--------------|-------|
| Lab U1 / catalog / NDWS IoU | unchanged | **no lift** |
| Tobarra KEEP | still KILL / not reopened | **no thrash** |
| Field fusion | OFF | rails held |
| Multihorizon methods | isotropic + `anisotropic_ros_buffer_v1` + `hybrid_sector_envelope_v1` + `reinit_multipass_v1` | product only |
| Multipass scorecard | ops envelope metrics; PARTIAL ok on short span | **not** ML IoU |
| Lab larger U-Net | kill-criteria doc; default bet false | zero field fusion |

**Do not market Wave B as IoU improvement.** Skill claims require PR8-style multipass
envelope metrics on observed progression — still PARTIAL on Tobarra’s short IR span.
