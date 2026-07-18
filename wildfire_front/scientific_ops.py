"""Scientific operators for observatory-grade fire-front products.

Goals (INFOCAM / Observatorio):
- Prefer **main-front** geometry over thousands of MAD noise flecks.
- Report **area (ha)**, **spread rate (m/min)** with uncertainty, and
  **honest abstention** when the signal is not defendable.
- Compare against operational anchors (e.g. Tobarra Vp=7 m/min) without
  claiming official perimeter accuracy.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from .geometry_speed import signed_area
from .models import FrontObservation, GeometrySpeedResult, MultiLine

try:
    from scipy import ndimage as ndi

    _HAS_SCIPY = True
except Exception:  # pragma: no cover
    _HAS_SCIPY = False


def clean_binary_mask(
    mask: np.ndarray,
    *,
    min_component_pixels: int = 500,
    morph_close_pixels: int = 3,
    max_components: int = 5,
    min_area_fraction: float = 0.02,
) -> np.ndarray:
    """Morphologically clean a fire candidate mask and keep dominant blobs.

    Parameters
    ----------
    min_component_pixels:
        Drop connected components smaller than this (noise sieve).
    morph_close_pixels:
        Closing radius in pixels to bridge small gaps inside the hot front.
    max_components:
        Keep at most this many largest components (main fronts / islands).
    min_area_fraction:
        Drop components smaller than this fraction of total positive area
        after morphological close (relative noise filter).
    """
    binary = np.asarray(mask > 0, dtype=bool)
    if not binary.any():
        return binary.astype(np.uint8)

    if _HAS_SCIPY and morph_close_pixels > 0:
        structure = np.ones((2 * morph_close_pixels + 1, 2 * morph_close_pixels + 1), dtype=bool)
        binary = ndi.binary_closing(binary, structure=structure)
        binary = ndi.binary_opening(binary, structure=np.ones((3, 3), dtype=bool))

    if _HAS_SCIPY:
        labeled, nlab = ndi.label(binary)
    else:
        # Fallback: treat whole mask as one component if no scipy.
        labeled = binary.astype(np.int32)
        nlab = 1 if binary.any() else 0

    if nlab == 0:
        return np.zeros_like(binary, dtype=np.uint8)

    areas = np.bincount(labeled.ravel())
    areas[0] = 0
    total = float(areas.sum())
    if total <= 0:
        return np.zeros_like(binary, dtype=np.uint8)

    keep_labels: list[int] = []
    order = np.argsort(areas)[::-1]
    for lab in order:
        if lab == 0:
            continue
        a = int(areas[lab])
        if a < min_component_pixels:
            continue
        if a / total < min_area_fraction and keep_labels:
            # Keep tiny islands only if nothing kept yet.
            continue
        keep_labels.append(int(lab))
        if len(keep_labels) >= max_components:
            break

    if not keep_labels:
        # Fallback: single largest blob even if below thresholds.
        largest = int(np.argmax(areas))
        if largest > 0:
            keep_labels = [largest]

    out = np.isin(labeled, keep_labels)
    return out.astype(np.uint8)


def component_area_m2(component: tuple[tuple[float, float], ...]) -> float:
    return abs(signed_area(component))


def filter_components_main_front(
    components: MultiLine,
    *,
    max_components: int = 5,
    min_area_m2: float = 100.0,
    coverage_fraction: float = 0.90,
) -> MultiLine:
    """Keep largest components that explain most of the burned area."""
    if not components:
        return ()
    scored = sorted(
        ((component_area_m2(c), c) for c in components),
        key=lambda t: t[0],
        reverse=True,
    )
    total = sum(a for a, _ in scored) or 1.0
    kept: list[tuple[tuple[float, float], ...]] = []
    cum = 0.0
    for area, comp in scored:
        if area < min_area_m2 and kept:
            continue
        kept.append(comp)
        cum += area
        if len(kept) >= max_components:
            break
        if cum / total >= coverage_fraction and kept:
            break
    return tuple(kept) if kept else (scored[0][1],)


def observation_area_m2(obs: FrontObservation) -> float:
    return float(sum(component_area_m2(c) for c in obs.components))


def observation_area_ha(obs: FrontObservation) -> float:
    return observation_area_m2(obs) / 10_000.0


@dataclass(frozen=True)
class OperationalReference:
    """External operational anchor (e.g. INFOCAM parte)."""

    name: str
    vp_m_min: float | None = None
    area_ha: float | None = None
    notes: str = ""


def _percentile(values: np.ndarray, q: float) -> float | None:
    if values.size == 0:
        return None
    return float(np.percentile(values, q))


# Extreme upper bound for local LWIR-derived front advance (m/min).
# Typical surface ROS is ~1-15 m/min; extreme runs rarely justify >>60 in this product.
MAX_PLAUSIBLE_SPEED_M_MIN = 60.0
MIN_PLAUSIBLE_DT_S = 15.0  # sub-15s pairs are usually registration noise


def summarize_main_front_speeds(
    result: GeometrySpeedResult,
    observations: list[FrontObservation],
    *,
    max_plausible_speed_m_min: float = MAX_PLAUSIBLE_SPEED_M_MIN,
) -> dict[str, Any]:
    """Summarize speeds focusing on the largest component per pair when possible."""
    all_obs = [e for e in result.estimates if e.observable and e.speed_m_min is not None]
    raw_speeds = np.asarray(
        [float(e.speed_m_min) for e in all_obs if e.speed_m_min is not None],
        dtype=float,
    )
    n_implausible = 0

    # Prefer estimates from the largest component index of each previous frame
    # when component_index is available.
    main_speeds: list[float] = []
    bearings: list[float] = []
    for e in all_obs:
        # quality_score already encodes valid normal fraction
        if e.quality_score is not None and e.quality_score < 0.25:
            continue
        dt_s = float(e.time_end_s - e.time_start_s)
        # all_obs is pre-filtered to speed_m_min is not None; re-bind for narrowing
        speed_val = e.speed_m_min
        if speed_val is None:
            continue
        spd = float(speed_val)
        if dt_s < MIN_PLAUSIBLE_DT_S:
            n_implausible += 1
            continue
        if spd > max_plausible_speed_m_min:
            n_implausible += 1
            continue
        main_speeds.append(spd)
        bearings.append(float(e.angle_deg))

    main = np.asarray(main_speeds, dtype=float)
    speeds = main  # after physical filters

    # Dominant spread direction (circular mean of bearings with high speed)
    dominant_bearing = None
    if main.size and bearings:
        top = main >= np.median(main)
        ang = np.deg2rad(np.asarray(bearings)[top[: len(bearings)] if top.size else slice(None)])
        if ang.size:
            sin_m = float(np.mean(np.sin(ang)))
            cos_m = float(np.mean(np.cos(ang)))
            dominant_bearing = float((math.degrees(math.atan2(sin_m, cos_m)) + 360.0) % 360.0)

    uncert = [float(e.uncertainty_m_min) for e in all_obs if e.uncertainty_m_min is not None]
    return {
        "speed_n_raw_observable": int(raw_speeds.size),
        "speed_n_implausible_filtered": int(n_implausible),
        "speed_n_observable": int(speeds.size),
        "speed_median_m_min": float(np.median(main)) if main.size else None,
        "speed_p25_m_min": _percentile(main, 25),
        "speed_p75_m_min": _percentile(main, 75),
        "speed_p95_m_min": _percentile(main, 95),
        "speed_mean_m_min": float(np.mean(main)) if main.size else None,
        "speed_iqr_m_min": (
            float(np.percentile(main, 75) - np.percentile(main, 25)) if main.size >= 4 else None
        ),
        "speed_uncertainty_median_m_min": (float(np.median(uncert)) if uncert else None),
        "dominant_spread_bearing_deg": dominant_bearing,
        "speed_status": "estimated" if main.size else "abstained",
        "speed_defendable": bool(main.size >= 10),
        "max_plausible_speed_m_min": max_plausible_speed_m_min,
    }


def area_evolution(observations: list[FrontObservation]) -> dict[str, Any]:
    if not observations:
        return {"area_ha_series": [], "area_ha_first": None, "area_ha_last": None}
    series = []
    for obs in observations:
        series.append(
            {
                "time_s": obs.time_s,
                "observed_at": getattr(obs, "observed_at", None) or "",
                "area_ha": observation_area_ha(obs),
                "n_components": len(obs.components),
            }
        )
    areas: list[float] = [float(s["area_ha"]) for s in series]
    return {
        "area_ha_series": series,
        "area_ha_first": areas[0],
        "area_ha_last": areas[-1],
        "area_ha_max": max(areas),
        "area_ha_min": min(areas),
        "area_non_monotonic": any(areas[i] < areas[i - 1] * 0.7 for i in range(1, len(areas))),
    }


def compare_to_reference(
    speed_median: float | None,
    area_max_ha: float | None,
    ref: OperationalReference | None,
) -> dict[str, Any]:
    if ref is None:
        return {"has_reference": False}
    out: dict[str, Any] = {
        "has_reference": True,
        "reference_name": ref.name,
        "reference_vp_m_min": ref.vp_m_min,
        "reference_area_ha": ref.area_ha,
        "reference_notes": ref.notes,
    }
    if speed_median is not None and ref.vp_m_min and ref.vp_m_min > 0:
        ratio = speed_median / ref.vp_m_min
        out["speed_vs_ref_ratio"] = ratio
        if 0.5 <= ratio <= 2.0:
            out["speed_vs_ref_grade"] = "compatible_order_of_magnitude"
        elif ratio < 0.5:
            out["speed_vs_ref_grade"] = "underestimate_or_mask_fragmented"
        else:
            out["speed_vs_ref_grade"] = "overestimate_or_noise_motion"
        out["speed_vs_ref_interpretation_es"] = _speed_interp_es(ratio, ref.vp_m_min, speed_median)
    if area_max_ha is not None and ref.area_ha and ref.area_ha > 0:
        out["area_vs_ref_ratio"] = area_max_ha / ref.area_ha
        out["area_vs_ref_interpretation_es"] = (
            f"Área máx. observada por máscara {area_max_ha:.2f} ha vs ancla "
            f"{ref.area_ha:.1f} ha (ratio {area_max_ha / ref.area_ha:.2f}). "
            "La máscara térmica candidata NO es el perímetro oficial."
        )
    return out


def _speed_interp_es(ratio: float, ref: float, est: float) -> str:
    if 0.5 <= ratio <= 2.0:
        return (
            f"Vp mediana estimada {est:.2f} m/min está en el mismo orden de magnitud "
            f"que la ancla operativa {ref:.1f} m/min (ratio {ratio:.2f}). "
            "Úsese como orientación, no como valor táctico cerrado."
        )
    if ratio < 0.5:
        return (
            f"Vp mediana {est:.2f} m/min << ancla {ref:.1f} m/min (ratio {ratio:.2f}). "
            "Probable fragmentación de máscara, matching débil o frentes poco observables. "
            "NO usar para despliegue de medios sin validación de campo."
        )
    return (
        f"Vp mediana {est:.2f} m/min >> ancla {ref:.1f} m/min (ratio {ratio:.2f}). "
        "Probable ruido, matching entre componentes incorrectos o dt pequeño. "
        "NO usar para despliegue de medios sin validación de campo."
    )


def quality_grade(metrics: dict[str, Any]) -> dict[str, Any]:
    """Assign a traffic-light grade for observatory consumers."""
    score = 0
    reasons: list[str] = []
    n_obs = int(metrics.get("num_observations") or 0)
    n_speed = int(metrics.get("speed_n_observable") or 0)
    n_comp_med = metrics.get("component_count_median")
    area_non_mono = bool(metrics.get("area_non_monotonic"))
    defendable = bool(metrics.get("speed_defendable"))

    if n_obs >= 4:
        score += 2
        reasons.append("secuencia >=4 frames")
    elif n_obs >= 2:
        score += 1
        reasons.append("secuencia corta (2-3 frames)")
    else:
        reasons.append("secuencia insuficiente")

    if n_speed >= 30:
        score += 2
        reasons.append(f"{n_speed} puntos de velocidad observables")
    elif n_speed >= 10:
        score += 1
        reasons.append(f"pocos puntos de velocidad ({n_speed})")
    else:
        reasons.append(f"velocidad casi abstención ({n_speed} puntos)")

    if n_comp_med is not None and float(n_comp_med) <= 8:
        score += 2
        reasons.append("máscara con pocos componentes (frente limpio)")
    elif n_comp_med is not None and float(n_comp_med) <= 30:
        score += 1
        reasons.append("máscara moderadamente fragmentada")
    else:
        reasons.append("máscara muy fragmentada")

    if not area_non_mono:
        score += 1
        reasons.append("área temporalmente estable")
    else:
        reasons.append("área no monótona (máscara inestable)")

    if defendable:
        score += 1

    med = metrics.get("speed_median_m_min")
    if isinstance(med, (int, float)) and med > MAX_PLAUSIBLE_SPEED_M_MIN:
        score = min(score, 2)
        reasons.append(f"Vp mediana no física ({med:.1f} m/min) — posible mismatch de frames")
    elif isinstance(med, (int, float)) and med > 30:
        score = max(0, score - 2)
        reasons.append(f"Vp elevada ({med:.1f} m/min) — revisar con cautela extrema")

    if score >= 7:
        grade, label = "A", "útil con cautela"
    elif score >= 4:
        grade, label = "B", "orientativo / revisar"
    else:
        grade, label = "C", "no usar para decisión operativa"

    return {
        "quality_grade": grade,
        "quality_label_es": label,
        "quality_score": score,
        "quality_reasons_es": reasons,
    }


def build_operational_metrics(
    observations: list[FrontObservation],
    speed_result: GeometrySpeedResult,
    base_summary: dict[str, Any],
    ref: OperationalReference | None = None,
) -> dict[str, Any]:
    area = area_evolution(observations)
    speed = summarize_main_front_speeds(speed_result, observations)
    med = speed.get("speed_median_m_min")
    amax = area.get("area_ha_max")
    cmp = compare_to_reference(
        float(med) if isinstance(med, (int, float)) else None,
        float(amax) if isinstance(amax, (int, float)) else None,
        ref,
    )
    # component stats from observations
    n_comps = [len(o.components) for o in observations]
    metrics: dict[str, Any] = {
        **base_summary,
        **area,
        **speed,
        **cmp,
        "component_count_median": float(np.median(n_comps)) if n_comps else None,
        "component_count_max": max(n_comps) if n_comps else None,
        "product": "observed_front_dynamics",
        "not_a_product": "next_day_ml_prediction",
    }
    metrics.update(quality_grade(metrics))
    return metrics


def write_operational_report_html(
    metrics: dict[str, Any],
    event_id: str,
    output_path: Any,
) -> None:
    """Spanish operational report for observatory / INFOCAM-style review."""
    from pathlib import Path

    output_path = Path(output_path)
    grade = metrics.get("quality_grade", "?")
    label = metrics.get("quality_label_es", "")
    color = {"A": "#3d9a5f", "B": "#f5b942", "C": "#d64545"}.get(str(grade), "#9eb1bd")
    reasons = metrics.get("quality_reasons_es") or []
    reasons_html = "".join(f"<li>{r}</li>" for r in reasons)
    series = metrics.get("area_ha_series") or []
    series_rows = "".join(
        f"<tr><td>{s.get('observed_at') or s.get('time_s')}</td>"
        f"<td>{s.get('area_ha', 0):.3f}</td>"
        f"<td>{s.get('n_components')}</td></tr>"
        for s in series
    )
    ref_block = ""
    if metrics.get("has_reference"):
        ref_block = f"""
        <h2>Comparación con ancla operativa</h2>
        <p><strong>{metrics.get("reference_name")}</strong> —
        Vp ref={metrics.get("reference_vp_m_min")} m/min,
        área ref={metrics.get("reference_area_ha")} ha.</p>
        <p>{metrics.get("speed_vs_ref_interpretation_es", "")}</p>
        <p>{metrics.get("area_vs_ref_interpretation_es", "")}</p>
        <p class="note">{metrics.get("reference_notes", "")}</p>
        """

    def _fmt(v: Any, nd: int = 3) -> str:
        if v is None:
            return "—"
        if isinstance(v, float):
            return f"{v:.{nd}f}"
        return str(v)

    html = f"""<!doctype html>
<html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Informe operativo — {event_id}</title>
<style>
body{{margin:0;background:#08131c;color:#f5f1e8;font:16px/1.45 system-ui;max-width:1000px;padding:36px;margin:auto}}
h1{{font-size:34px;margin-bottom:4px}} h2{{margin-top:28px;color:#f5b942}}
p,.note,li{{color:#9eb1bd}} .grade{{display:inline-block;background:{color};color:#08131c;font-weight:700;padding:8px 14px;border-radius:8px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:20px 0}}
article{{background:#112532;border:1px solid #26404f;border-radius:12px;padding:14px}}
span{{display:block;color:#9eb1bd;font-size:12px}} strong{{font-size:22px;color:#f5b942}}
table{{width:100%;border-collapse:collapse;background:#112532;margin-top:12px}}
th,td{{padding:8px 10px;border-bottom:1px solid #26404f;text-align:left}}
.warn{{border-left:4px solid #d64545;padding-left:12px;margin:18px 0}}
a{{color:#f5b942}}
</style>
<h1>Informe operativo de frente observado</h1>
<p>Evento <code>{event_id}</code> · producto: <strong>dinámica observada</strong> (no predicción ML)</p>
<p><span class="grade">Grado {grade} — {label}</span></p>

<div class="warn">
<strong>Límites científicos (leer antes de usar):</strong>
<ul>
<li>La máscara LWIR es un <em>candidato de frente térmico</em>, no el perímetro oficial.</li>
<li>Las velocidades usan intersección de normales con abstención cuando no hay señal defendible.</li>
<li>No sustituye partes INFOCAM/FIDIAS ni observación de campo.</li>
</ul>
</div>

<section class="grid">
<article><span>Frames aceptados</span><strong>{_fmt(metrics.get("num_observations"), 0)}</strong></article>
<article><span>Área máx. (ha)</span><strong>{_fmt(metrics.get("area_ha_max"), 2)}</strong></article>
<article><span>ROS primaria (m/min)</span><strong>{_fmt(metrics.get("speed_median_m_min"), 2)}</strong></article>
<article><span>IQR / P25–P75</span><strong>{_fmt(metrics.get("speed_p25_m_min"), 2)}–{_fmt(metrics.get("speed_p75_m_min"), 2)}</strong></article>
<article><span>Pares con ROS</span><strong>{_fmt(metrics.get("speed_n_observable"), 0)}</strong></article>
<article><span>Métodos</span><strong>{", ".join(metrics.get("primary_methods_used") or []) or "—"}</strong></article>
<article><span>Coreg. medio (m)</span><strong>{_fmt(metrics.get("mean_coreg_shift_m"), 1)}</strong></article>
<article><span>Motor</span><strong>{metrics.get("engine", "legacy")}</strong></article>
</section>

<h2>Calidad de la señal</h2>
<ul>{reasons_html}</ul>
<p class="note">Estimadores: <em>normal_ray</em> (locales), <em>area_isotropic</em> dA/(P·dt),
<em>equiv_radius</em> d√(A/π)/dt; fusión con coregistro residual entre frames.</p>

<h2>Evolución de área (proxy de máscara)</h2>
<table><thead><tr><th>Timestamp</th><th>Área ha</th><th>Componentes</th></tr></thead>
<tbody>{series_rows}</tbody></table>

{ref_block}

<h2>Artefactos técnicos</h2>
<ul>
<li><a href="report.html">Reporte técnico MVP</a></li>
<li><a href="fronts.geojson">Frentes GeoJSON</a></li>
<li><a href="local_speeds.csv">Velocidades locales CSV</a></li>
<li><a href="summary.json">summary.json</a></li>
<li><a href="operational_metrics.json">operational_metrics.json</a></li>
</ul>
<p class="note">Generado por WildfireFrontDynamics · scientific_ops</p>
</html>"""
    output_path.write_text(html, encoding="utf-8")
