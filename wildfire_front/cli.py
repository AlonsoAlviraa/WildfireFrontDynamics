from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from .ingestion.geotiff import ingest_geotiff_sequence, write_ingest_manifest
from .models import ScenarioConfig
from .outputs import write_all
from .reconstruction import (
    estimate_local_speeds,
    real_speed_abstention,
    reconstruct_arrival_from_components,
    reconstruct_arrival_grid,
    summarize,
)
from .synthetic import generate_observations


def run_demo(output: Path, seed: int, position_error_m: float) -> dict[str, object]:
    config = ScenarioConfig(seed=seed, position_error_m=position_error_m)
    config.validate()
    observations = generate_observations(config)
    estimates = estimate_local_speeds(observations, config)
    xx, yy, arrival = reconstruct_arrival_grid(observations, config)
    metrics = summarize(estimates, arrival)
    metrics["num_observations"] = len(observations)
    write_all(output, config, observations, estimates, xx, yy, arrival, metrics)
    return metrics


def run_geotiff_ingest(
    images: Path,
    masks: Path | None,
    output: Path,
    event_id: str,
    sensor_id: str,
    estimated_error_m: float,
    band: int,
    threshold: float | None,
) -> dict[str, object]:
    result = ingest_geotiff_sequence(
        images,
        masks_dir=masks,
        event_id=event_id,
        sensor_id=sensor_id,
        estimated_error_m=estimated_error_m,
        band=band,
        threshold=threshold,
    )
    output.mkdir(parents=True, exist_ok=True)
    write_ingest_manifest(result.records, output / "ingest_manifest.csv")
    if not result.observations:
        raise ValueError("no accepted observations; inspect ingest_manifest.csv")
    resolution = next(
        (item.resolution_m for item in result.observations if item.resolution_m is not None),
        None,
    )
    if resolution is None:
        raise ValueError("accepted observations do not have metric resolution")
    xx, yy, arrival = reconstruct_arrival_from_components(list(result.observations), resolution)
    summary: dict[str, object] = {
        "num_observations": len(result.observations),
        "num_components": sum(len(item.components) for item in result.observations),
        "accepted_inputs": sum(record.status == "accepted" for record in result.records),
        "review_inputs": sum(record.status == "review" for record in result.records),
        "rejected_inputs": sum(record.status == "rejected" for record in result.records),
        "arrival_cells_observed": int((~np.isnan(arrival)).sum()),
        **real_speed_abstention(list(result.observations)),
    }
    write_all(output, None, list(result.observations), [], xx, yy, arrival, summary)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wildfire-front", description="Wildfire Front Dynamics MVP")
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="Run the synthetic end-to-end MVP")
    demo.add_argument("--output", type=Path, default=Path("outputs/demo"))
    demo.add_argument("--seed", type=int, default=7)
    demo.add_argument("--position-error-m", type=float, default=0.6, help="One-sigma observation error in metres")
    ingest = commands.add_parser("ingest-geotiff", help="Ingest georeferenced GeoTIFF images and masks")
    ingest.add_argument("--images", type=Path, required=True)
    ingest.add_argument("--masks", type=Path)
    ingest.add_argument("--output", type=Path, default=Path("outputs/geotiff-demo"))
    ingest.add_argument("--event-id", default="geotiff_event")
    ingest.add_argument("--sensor-id", required=True)
    ingest.add_argument("--estimated-error-m", type=float, required=True)
    ingest.add_argument("--band", type=int, default=1)
    ingest.add_argument("--threshold", type=float)
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "demo":
            metrics = run_demo(args.output, args.seed, args.position_error_m)
        else:
            metrics = run_geotiff_ingest(
                args.images,
                args.masks,
                args.output,
                args.event_id,
                args.sensor_id,
                args.estimated_error_m,
                args.band,
                args.threshold,
            )
        print(json.dumps({"output": str(args.output), "metrics": metrics}, indent=2))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
