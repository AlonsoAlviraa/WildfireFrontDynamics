"""Operator-facing GIS and brief exports for observatory packs."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .models import FrontObservation
from .scientific_ops import observation_area_ha


def write_main_front_geojson(
    observations: list[FrontObservation],
    output: Path,
    *,
    event_id: str,
) -> Path:
    """Single-layer GeoJSON: main front (largest component) per timestamp."""
    features: list[dict[str, Any]] = []
    for obs in sorted(observations, key=lambda o: o.time_s):
        if not obs.components:
            continue
        # Largest component by abs area (shoelace)
        from .geometry_speed import signed_area

        main = max(obs.components, key=lambda c: abs(signed_area(c)))
        ring = [[float(x), float(y)] for x, y in main]
        if ring[0] != ring[-1]:
            ring.append(ring[0])
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "event_id": event_id,
                    "observation_id": obs.observation_id,
                    "observed_at": obs.observed_at,
                    "time_s": obs.time_s,
                    "area_ha": observation_area_ha(
                        FrontObservation(
                            observation_id=obs.observation_id,
                            event_id=obs.event_id,
                            sensor_id=obs.sensor_id,
                            time_s=obs.time_s,
                            observed_at=obs.observed_at,
                            components=(main,),
                            estimated_error_m=obs.estimated_error_m,
                            crs=obs.crs,
                            coordinate_system=obs.coordinate_system,
                            resolution_m=obs.resolution_m,
                            method=obs.method,
                        )
                    ),
                    "n_components_total": len(obs.components),
                    "layer": "main_front",
                    "crs": obs.crs,
                },
                "geometry": {"type": "Polygon", "coordinates": [ring]},
            }
        )
    fc = {
        "type": "FeatureCollection",
        "name": "main_front",
        "crs": {
            "type": "name",
            "properties": {
                "name": observations[0].crs if observations and observations[0].crs else "EPSG:32630"
            },
        },
        "features": features,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(fc, indent=2), encoding="utf-8")
    return output


def write_ros_timeline_csv(structural: dict[str, Any], output: Path) -> Path:
    """One row per consecutive pair with multi-estimator ROS."""
    pairs = structural.get("pairs") or []
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "time_start_s",
        "time_end_s",
        "dt_min",
        "area_ha_prev",
        "area_ha_curr",
        "ros_area_m_min",
        "ros_equiv_radius_m_min",
        "ros_normal_median_m_min",
        "ros_normal_n",
        "primary_ros_m_min",
        "primary_method",
        "pair_quality",
        "coreg_dx_m",
        "coreg_dy_m",
        "coreg_iou",
        "coreg_applied",
    ]
    with output.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for p in pairs:
            w.writerow(p)
    return output


def write_operator_brief_md(
    event_id: str,
    ops: dict[str, Any],
    structural: dict[str, Any],
    output: Path,
    *,
    window_label: str | None = None,
) -> Path:
    """One-page markdown brief for observatory (5-minute read)."""
    cal = structural.get("calibration") or {}
    title = f"Brief operativo — {event_id}"
    if window_label:
        title += f" ({window_label})"
    lines = [
        f"# {title}",
        "",
        f"- **Grado:** {ops.get('quality_grade')} — {ops.get('quality_label_es')}",
        f"- **ROS primaria:** {ops.get('speed_median_m_min')} m/min "
        f"(n={ops.get('speed_n_observable')})",
        f"- **Métodos:** {', '.join(ops.get('primary_methods_used') or []) or '—'}",
        f"- **Área máx (ha, proxy máscara):** {ops.get('area_ha_max')}",
        f"- **Coreg. medio (m):** {ops.get('mean_coreg_shift_m')}",
        f"- **Motor:** {ops.get('engine', structural.get('engine'))}",
        "",
    ]
    if cal.get("has_reference"):
        lines += [
            "## Ancla operativa",
            f"- Ref: {cal.get('reference_name')} Vp={cal.get('reference_vp_m_min')} "
            f"ha={cal.get('reference_area_ha')}",
            f"- Ratio crudo/ref: {cal.get('raw_vs_ref_ratio')}",
            f"- {cal.get('interpretation_es', '')}",
            "",
        ]
    lines += [
        "## Límites",
        "- Máscara térmica ≠ perímetro oficial.",
        "- ROS fusionada es orientación, no parte táctico.",
        "- No es predicción 24 h ni ML operacional.",
        "",
        "## Archivos",
        "- `operational_report.html` — informe visual",
        "- `main_front.geojson` — capa frente principal",
        "- `ros_timeline.csv` — ROS por intervalo",
        "- `front_dynamics.json` — detalle multi-estimador",
        "",
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")
    return output


def export_operator_bundle(
    observations: list[FrontObservation],
    ops: dict[str, Any],
    output_dir: Path,
    *,
    event_id: str,
    window_label: str | None = None,
) -> dict[str, str]:
    """Write main_front + timeline + brief into pack directory."""
    structural = ops.get("structural") if isinstance(ops.get("structural"), dict) else ops
    paths = {
        "main_front_geojson": str(
            write_main_front_geojson(
                observations, output_dir / "main_front.geojson", event_id=event_id
            )
        ),
        "ros_timeline_csv": str(
            write_ros_timeline_csv(structural or {}, output_dir / "ros_timeline.csv")
        ),
        "brief_md": str(
            write_operator_brief_md(
                event_id,
                ops,
                structural or {},
                output_dir / "brief_operativo.md",
                window_label=window_label,
            )
        ),
    }
    return paths
