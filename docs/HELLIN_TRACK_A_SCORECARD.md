# Hellín Track A — front_dynamics vs Vp 50

**Generated:** 2026-08-04T09:00:17.106095+00:00

## Result

| Field | Value |
|-------|-------|
| Structural grade | **B** |
| Primary ROS | **27.934 m/min** (n=1) |
| Methods | area_isotropic |
| Vp anchor | **50.0 m/min** (boletín UNAP) |
| Ratio ROS/Vp | **0.559** |
| In band [0.5, 2.0] | **yes** |
| Grade A eligible | **NO** |
| P1 second IF closed | **NO** |
| GO_MES | **NO_GO_MES** |

## Interpretation

ROS primaria 27.93 m/min vs ancla 50.0 m/min (ratio 0.56): mismo orden de magnitud. No se reescala en silencio; se reporta crudo.

## Honesty

- No silent rescale of ROS to Vp
- Grade A eligible requires structural A AND ratio in [0.5,2]; grade B or out-of-band ⇒ not A
- Do NOT fit single k calibration Tobarra(7) and Hellin(50)
- Mask ROS is orientation only — not tactical dispatch
- Area series in pack max ~44 ha vs boletin 100 ha* — FOV/mask incompleteness likely
- P1 eng BLOCKED note: docs/P1_HELLIN_ENG_STATUS.md

## Best-of-run table

| Attempt | Params | Grade | ROS | Ratio | In band | Keep? |
|---------|--------|-------|-----|-------|---------|-------|
| 1h v1 | frames=16 side=4000 minpx=150 | A | 10.98 | 0.220 | no | no (out of band) |
| 1h v2 | frames=12 side=2200 minpx=100 | B | 24.54 | 0.491 | no | no |
| 1h pair / restore | frames=10 side=2500 minpx=800 | B | **27.93** | **0.559** | **yes** | **YES — best** |
| Track-A extra | frames=14 side=3000 minpx=120 | B | 14.27 | 0.285 | no | no (regressed) |

No attempt closed **grade A + in-band**. See `docs/P1_HELLIN_ENG_STATUS.md`.

## Files

- `outputs/observatorio/hellin_2024/track_a_scorecard.json`
- `docs/O1_GOMES_RECOMPUTE_20260803.json`
- `docs/P1_HELLIN_ENG_STATUS.md`
- Pack: `outputs/observatorio/hellin_2024`
