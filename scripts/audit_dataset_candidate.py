"""Audit a candidate GeoTIFF dataset for the next validation milestone."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from dataclasses import asdict
from pathlib import Path


def _format_value(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.3f}"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def classify_candidate(records: list[dict[str, object]], observation_count: int) -> str:
    """Classify a candidate using only auditable ingest outcomes."""

    accepted = [record for record in records if record.get("status") == "accepted"]
    reasons = {str(record.get("reason") or "") for record in records}
    has_metric_observations = any(
        record.get("coordinate_system") == "projected_metric" for record in accepted
    )
    has_temporal_sequence = observation_count >= 2
    if has_metric_observations and has_temporal_sequence:
        return "ready_for_dynamics"
    if accepted or "crs_not_projected_metric" in reasons or "missing_timestamp" in reasons:
        return "segmentation_only"
    return "rejected"


def write_markdown_audit(summary: dict[str, object], output: Path) -> None:
    """Write a compact human audit from candidate_audit.json content."""

    output.parent.mkdir(parents=True, exist_ok=True)
    dataset_id = str(summary.get("event_id") or "unknown_dataset")
    classification = str(summary.get("classification") or "unknown")
    reference_available = bool(summary.get("front_distance_metrics_available"))
    metric_rows = [
        ("Classification", classification),
        ("Input count", summary.get("input_count", 0)),
        ("Accepted inputs", summary.get("accepted_inputs", 0)),
        ("Review inputs", summary.get("review_inputs", 0)),
        ("Rejected inputs", summary.get("rejected_inputs", 0)),
        ("Observation count", summary.get("observation_count", 0)),
        ("Median interval s", summary.get("interval_s_median", "unknown")),
        ("Positive pixel fraction median", summary.get("positive_pixel_fraction_median", "unknown")),
    ]
    if reference_available:
        metric_rows.extend(
            [
                ("Independent references", summary.get("independent_reference_count", 0)),
                ("Reference matches", summary.get("front_reference_match_count", 0)),
                ("Mean front distance m", summary.get("reference_front_distance_mean_m", "unknown")),
                ("P95 front distance m", summary.get("reference_front_distance_p95_m", "unknown")),
                ("Hausdorff front distance m", summary.get("reference_front_hausdorff_m", "unknown")),
            ]
        )

    rows = "\n".join(f"| {name} | {_format_value(value)} |" for name, value in metric_rows)
    reference_note = (
        "Independent reference metrics are available for this candidate."
        if reference_available
        else "No independent reference metrics are available; do not report front accuracy."
    )
    content = f"""# Auditoría de candidato: {dataset_id}

**Clasificación:** `{classification}`

## Fuentes

- Imágenes: `{summary.get("images", "")}`
- Máscaras observadas: `{summary.get("masks", "")}`
- Anotaciones independientes: `{summary.get("annotations", "") or "not_provided"}`

## Resultado

| Métrica | Valor |
|---|---:|
{rows}

## Interpretación

{reference_note}

Siguiente acción: {summary.get("next_action", "not_available")}
"""
    output.write_text(content, encoding="utf-8")


def summarize_reference_metrics(
    observations: Iterable[object],
    references: Iterable[object],
    *,
    sample_spacing: float = 1.0,
) -> dict[str, object]:
    """Compare observed fronts with independent references matched by timestamp."""

    from wildfire_front.evaluation import front_distance_metrics

    reference_by_time = {item.observed_at: item for item in references}  # type: ignore[attr-defined]
    matched: list[dict[str, float]] = []
    for observation in observations:
        reference = reference_by_time.get(observation.observed_at)  # type: ignore[attr-defined]
        if reference is None:
            continue
        matched.append(
            front_distance_metrics(
                observation.components[0],  # type: ignore[attr-defined]
                reference.components[0],
                sample_spacing=sample_spacing,
            )
        )
    if not matched:
        return {
            "independent_reference_count": len(reference_by_time),
            "front_reference_match_count": 0,
            "front_distance_metrics_available": False,
        }

    metric_names = matched[0].keys()
    summary: dict[str, object] = {
        "independent_reference_count": len(reference_by_time),
        "front_reference_match_count": len(matched),
        "front_distance_metrics_available": True,
    }
    for name in metric_names:
        values = [item[name] for item in matched]
        summary[f"reference_{name}_m"] = sum(values) / len(values)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit whether a GeoTIFF sequence is usable for front-dynamics validation."
    )
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--masks", type=Path)
    parser.add_argument("--annotations", type=Path, help="Independent front-reference masks matched by filename")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--event-id", default="candidate_event")
    parser.add_argument("--sensor-id", required=True)
    parser.add_argument("--estimated-error-m", type=float, required=True)
    parser.add_argument("--band", type=int, default=1)
    parser.add_argument("--threshold", type=float)
    parser.add_argument("--mad-z", type=float)
    parser.add_argument("--markdown-output", type=Path, help="Optional Markdown audit report path")
    return parser


def audit_candidate(
    images: Path,
    *,
    masks: Path | None,
    annotations: Path | None,
    output: Path,
    event_id: str,
    sensor_id: str,
    estimated_error_m: float,
    band: int = 1,
    threshold: float | None = None,
    mad_z: float | None = None,
) -> dict[str, object]:
    from wildfire_front.ingestion.geotiff import ingest_geotiff_sequence, write_ingest_manifest
    from wildfire_front.quality import summarize_ingest_quality, summarize_observation_quality

    result = ingest_geotiff_sequence(
        images,
        masks_dir=masks,
        event_id=event_id,
        sensor_id=sensor_id,
        estimated_error_m=estimated_error_m,
        band=band,
        threshold=threshold,
        mad_z=mad_z,
    )
    output.mkdir(parents=True, exist_ok=True)
    write_ingest_manifest(result.records, output / "ingest_manifest.csv")

    record_dicts = [asdict(record) for record in result.records]
    classification = classify_candidate(record_dicts, len(result.observations))
    summary = {
        "classification": classification,
        "images": str(images),
        "masks": str(masks) if masks else "",
        "annotations": str(annotations) if annotations else "",
        "event_id": event_id,
        "sensor_id": sensor_id,
        "observation_count": len(result.observations),
        "next_action": _next_action(classification),
        **summarize_ingest_quality(result.records),
        **summarize_observation_quality(list(result.observations)),
    }
    if annotations:
        reference_result = ingest_geotiff_sequence(
            images,
            masks_dir=annotations,
            event_id=event_id,
            sensor_id=f"{sensor_id}_independent_reference",
            estimated_error_m=0.0,
            band=band,
        )
        write_ingest_manifest(reference_result.records, output / "reference_ingest_manifest.csv")
        summary.update(
            summarize_reference_metrics(
                result.observations,
                reference_result.observations,
                sample_spacing=max(estimated_error_m, 1.0),
            )
        )
    (output / "candidate_audit.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    args = build_parser().parse_args()

    # Imports used by audit_candidate are lazy so --help works without rasterio installed.
    summary = audit_candidate(
        args.images,
        masks=args.masks,
        annotations=args.annotations,
        output=args.output,
        event_id=args.event_id,
        sensor_id=args.sensor_id,
        estimated_error_m=args.estimated_error_m,
        band=args.band,
        threshold=args.threshold,
        mad_z=args.mad_z,
    )
    if args.markdown_output:
        write_markdown_audit(summary, args.markdown_output)
    print(json.dumps(summary, indent=2))


def _next_action(classification: str) -> str:
    if classification == "ready_for_dynamics":
        return "run full ingest-geotiff pipeline and compare against independent annotations"
    if classification == "segmentation_only":
        return "use for mask/segmentation work, but do not report metric speed validation"
    return "fix input contract issues before using this candidate"


if __name__ == "__main__":
    main()
