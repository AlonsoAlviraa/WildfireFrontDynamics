from __future__ import annotations

import csv
import html
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np

from .models import FrontObservation, ScenarioConfig, SpeedEstimate


def _closed(points: tuple[tuple[float, float], ...]) -> list[list[float]]:
    coordinates = [[round(x, 4), round(y, 4)] for x, y in points]
    return coordinates if coordinates and coordinates[0] == coordinates[-1] else coordinates + [coordinates[0]]


def _geometry(components: tuple[tuple[tuple[float, float], ...], ...]) -> dict[str, object]:
    coordinates = [_closed(component) for component in components]
    if len(coordinates) == 1:
        return {"type": "LineString", "coordinates": coordinates[0]}
    return {"type": "MultiLineString", "coordinates": coordinates}


def write_geojson(observations: list[FrontObservation], output: Path) -> None:
    features: list[dict[str, object]] = []
    for observation in observations:
        geometries = [("observed", observation.components)]
        if observation.truth_components:
            geometries.append(("ground_truth", observation.truth_components))
        for status, components in geometries:
            features.append(
                {
                    "type": "Feature",
                    "properties": {
                        "observation_id": observation.observation_id,
                        "event_id": observation.event_id,
                        "observed_at": observation.observed_at,
                        "time_s": observation.time_s,
                        "status": status,
                        "crs": observation.crs,
                        "coordinate_system": observation.coordinate_system,
                        "source_uri": observation.source_uri,
                        "source_sha256": observation.source_sha256,
                        "resolution_m": observation.resolution_m,
                        "method": observation.method,
                        "limitations": list(observation.limitations),
                        "component_count": len(components),
                        "estimated_error_m": observation.estimated_error_m if status == "observed" else 0.0,
                    },
                    "geometry": _geometry(components),
                }
            )
    payload = {
        "type": "FeatureCollection",
        "internal_export_warning": (
            "Coordinates may be projected. This internal export is not RFC 7946 compliant; inspect each feature CRS."
        ),
        "features": features,
    }
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_manifest(observations: list[FrontObservation], output: Path) -> None:
    fields = [
        "observation_id",
        "event_id",
        "sensor_id",
        "observed_at",
        "time_s",
        "status",
        "estimated_error_m",
        "crs",
        "coordinate_system",
        "resolution_m",
        "source_uri",
        "source_sha256",
        "method",
        "limitations",
        "component_count",
        "point_count",
    ]
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for observation in observations:
            writer.writerow(
                {
                    "observation_id": observation.observation_id,
                    "event_id": observation.event_id,
                    "sensor_id": observation.sensor_id,
                    "observed_at": observation.observed_at,
                    "time_s": observation.time_s,
                    "status": observation.status,
                    "estimated_error_m": observation.estimated_error_m,
                    "crs": observation.crs or "",
                    "coordinate_system": observation.coordinate_system or "",
                    "resolution_m": "" if observation.resolution_m is None else observation.resolution_m,
                    "source_uri": observation.source_uri or "",
                    "source_sha256": observation.source_sha256 or "",
                    "method": observation.method,
                    "limitations": "|".join(observation.limitations),
                    "component_count": len(observation.components),
                    "point_count": sum(len(component) for component in observation.components),
                }
            )


def write_arrival_csv(xx: np.ndarray, yy: np.ndarray, arrival: np.ndarray, output: Path) -> None:
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["x", "y", "arrival_time_s", "state", "provenance"])
        for x, y, time_s in zip(xx.ravel(), yy.ravel(), arrival.ravel()):
            writer.writerow(
                [
                    x,
                    y,
                    "" if np.isnan(time_s) else time_s,
                    "unobserved" if np.isnan(time_s) else "burned",
                    "none" if np.isnan(time_s) else "inferred_from_observed_geometries",
                ]
            )


def write_speeds_csv(estimates: list[SpeedEstimate], output: Path) -> None:
    with output.open("w", newline="", encoding="utf-8") as handle:
        fields = list(SpeedEstimate.__dataclass_fields__.keys())
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for estimate in estimates:
            writer.writerow(asdict(estimate))


def write_svg(observations: list[FrontObservation], output: Path) -> None:
    width, height, margin = 900, 620, 60
    points = np.vstack(
        [np.asarray(component) for observation in observations for component in observation.components]
    )
    min_x, min_y = np.min(points, axis=0)
    max_x, max_y = np.max(points, axis=0)
    span_x = max(float(max_x - min_x), 1.0)
    span_y = max(float(max_y - min_y), 1.0)
    min_x, max_x = float(min_x - span_x * 0.08), float(max_x + span_x * 0.08)
    min_y, max_y = float(min_y - span_y * 0.08), float(max_y + span_y * 0.08)

    def project(point: tuple[float, float]) -> tuple[float, float]:
        x, y = point
        return (
            margin + (x - min_x) / (max_x - min_x) * (width - 2 * margin),
            height - margin - (y - min_y) / (max_y - min_y) * (height - 2 * margin),
        )

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#08131c"/>',
        '<text x="60" y="35" fill="#f5f1e8" font-family="Arial" font-size="22">Evolución de geometrías observadas</text>',
    ]
    colors = ["#f5b942", "#f28c28", "#e85d3f", "#cf3c4f", "#a72f61", "#74356f"]
    for index, observation in enumerate(observations):
        color = colors[index * len(colors) // len(observations)]
        if observation.truth_components:
            for component in observation.truth_components:
                truth = " ".join(f"{x:.1f},{y:.1f}" for x, y in map(project, component))
                lines.append(f'<polygon points="{truth}" fill="none" stroke="#7b8790" stroke-width="1" opacity=".45"/>')
        for component in observation.components:
            observed = " ".join(f"{x:.1f},{y:.1f}" for x, y in map(project, component))
            lines.append(f'<polygon points="{observed}" fill="none" stroke="{color}" stroke-width="2" opacity=".9"/>')
    lines.extend(
        [
            '<text x="60" y="590" fill="#9eb1bd" font-family="Arial" font-size="14">Gris: ground truth opcional · Color: observación</text>',
            "</svg>",
        ]
    )
    output.write_text("\n".join(lines), encoding="utf-8")


def write_report(
    summary: dict[str, object],
    config: ScenarioConfig | None,
    observations: list[FrontObservation],
    output: Path,
) -> None:
    cards = "".join(
        f'<article><span>{html.escape(key.replace("_", " "))}</span><strong>{value:.3f}</strong></article>'
        if isinstance(value, float)
        else f'<article><span>{html.escape(key.replace("_", " "))}</span><strong>{html.escape(str(value))}</strong></article>'
        for key, value in summary.items()
        if not isinstance(value, (list, dict))
    )
    first = observations[0]
    context = {
        "source": first.source_uri or "synthetic",
        "crs": first.crs or first.coordinate_system or "unknown",
        "resolution_m": first.resolution_m if first.resolution_m is not None else "unknown",
        "method": first.method,
        "declared_error_m": first.estimated_error_m,
        "components": sum(len(item.components) for item in observations),
        "limitations": ", ".join(sorted({limit for item in observations for limit in item.limitations})) or "none",
        "speed_abstention_reasons": ", ".join(summary.get("speed_abstention_reasons", [])) or "none",
    }
    context_rows = "".join(
        f"<tr><th>{html.escape(str(key).replace('_', ' '))}</th><td>{html.escape(str(value))}</td></tr>"
        for key, value in context.items()
    )
    subtitle = (
        f"MVP sintético auditable · evento <code>{html.escape(config.event_id)}</code> · seed {config.seed}"
        if config
        else f"Ingesta GeoTIFF auditable · evento <code>{html.escape(first.event_id)}</code>"
    )
    document = f"""<!doctype html>
<html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Wildfire Front Dynamics MVP</title>
<style>
body{{margin:0;background:#08131c;color:#f5f1e8;font:16px system-ui;max-width:1200px;padding:40px;margin:auto}}
h1{{font-size:42px;margin-bottom:6px}} p{{color:#9eb1bd}} .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px;margin:28px 0}}
article{{background:#112532;border:1px solid #26404f;border-radius:12px;padding:18px}}span{{display:block;color:#9eb1bd;font-size:13px}}strong{{font-size:24px;color:#f5b942;word-break:break-word}}
img{{width:100%;background:#08131c;border-radius:12px;border:1px solid #26404f}}code{{color:#f5b942}}
table{{width:100%;border-collapse:collapse;background:#112532;margin:24px 0}}th,td{{padding:10px;text-align:left;border-bottom:1px solid #26404f}}th{{color:#9eb1bd}}
</style>
<h1>Wildfire Front Dynamics</h1>
<p>{subtitle}</p>
<section class="grid">{cards}</section>
<table>{context_rows}</table>
<img src="fronts.svg" alt="Evolución de geometrías">
<p>Una geometría derivada de máscara no constituye un frente activo validado. Consulta los manifiestos y limitaciones.</p>
</html>"""
    output.write_text(document, encoding="utf-8")


def write_all(
    output_dir: Path,
    config: ScenarioConfig | None,
    observations: list[FrontObservation],
    estimates: list[SpeedEstimate],
    xx: np.ndarray,
    yy: np.ndarray,
    arrival: np.ndarray,
    summary: dict[str, object],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_manifest(observations, output_dir / "observations_manifest.csv")
    write_geojson(observations, output_dir / "fronts.geojson")
    write_arrival_csv(xx, yy, arrival, output_dir / "arrival_time.csv")
    write_speeds_csv(estimates, output_dir / "local_speeds.csv")
    write_svg(observations, output_dir / "fronts.svg")
    write_report(summary, config, observations, output_dir / "report.html")
    payload = {"config": asdict(config) if config else None, "metrics": summary}
    (output_dir / "summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
