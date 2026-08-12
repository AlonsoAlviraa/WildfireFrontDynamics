"""WildfireFrontDynamics command-line interface.

Human-readable by default; pass ``--json`` for machine-readable output.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np

from . import __version__
from .cli_incident import incident_config_from_args as _incident_config_from_args
from .cli_incident import register_incident_subcommands
from .cli_operator import dispatch_operator_command, register_operator_commands
from .cli_report import (
    enrich_incident_summary,
    print_demo_report,
    print_doctor_report,
    print_error,
    print_incident_report,
    print_ingest_report,
    print_json,
    print_status_report,
    print_watch_line,
)
from .evaluation import front_distance_metrics
from .geometry_speed import estimate_geometry_speeds, summarize_geometry_speeds
from .ingestion.geotiff import ingest_geotiff_sequence, write_ingest_manifest
from .models import GeometrySpeedConfig, ScenarioConfig
from .outputs import write_all
from .quality import summarize_ingest_quality, summarize_observation_quality
from .reconstruction import (
    estimate_local_speeds,
    reconstruct_arrival_from_components,
    reconstruct_arrival_grid,
    summarize,
)
from .synthetic import generate_observations

_EPILOG = """
examples:
  # Synthetic demo with ground truth
  wildfire-front demo --output outputs/demo

  # Batch GeoTIFF ingest (ops products)
  wildfire-front ingest-geotiff \\
    --images artifacts/tobarra_reprojected_lwir \\
    --masks artifacts/tobarra_lwir_masks \\
    --sensor-id lwir_drone --estimated-error-m 2 \\
    --event-id tobarra_20240802 --output outputs/tobarra \\
    --operational --scientific-clean

  # Field: pre-flight check
  wildfire-front incident doctor --inbox D:/drops --masks D:/masks

  # Field: process once
  wildfire-front incident update --inbox D:/drops --work-dir outputs/incidents/IF1 --force

  # Field: live watch (Ctrl+C to stop)
  wildfire-front incident watch --inbox D:/drops --work-dir outputs/incidents/IF1

  # Machine-readable
  wildfire-front incident status --work-dir outputs/incidents/IF1 --json

  # H1 / 12-min demo (operator hub)
  wildfire-front operator
  wildfire-front operator checklist
  wildfire-front operator do --act 1
  wildfire-front demo-third-party

  # Decision Card → forensic acta
  wildfire-front decide --work-dir outputs/incidents/IF1 \\
    --output outputs/incidents/IF1/outbox/fire_decision_card.json
  wildfire-front export-acta --work-dir outputs/incidents/IF1

notes:
  · Thermal mask ≠ official fire perimeter
  · 15/30/60 envelope is extrapolated guidance, NOT tactical dispatch
  · Filenames must include parseable timestamps for real LWIR frames
  · Docs: docs/INCIDENT_RUNTIME_V1.md
"""


def run_demo(output: Path, seed: int, position_error_m: float) -> dict[str, object]:
    config = ScenarioConfig(seed=seed, position_error_m=position_error_m)
    config.validate()
    observations = generate_observations(config)
    estimates = estimate_local_speeds(observations, config)
    xx, yy, arrival = reconstruct_arrival_grid(observations, config)
    metrics: dict[str, object] = dict(summarize(estimates, arrival))
    metrics["num_observations"] = len(observations)
    front_metrics = [
        front_distance_metrics(item.points, item.truth_points, sample_spacing=1.0)
        for item in observations
        if item.truth_points is not None
    ]
    if front_metrics:
        for key in front_metrics[0]:
            metrics[f"{key}_m"] = float(np.mean([item[key] for item in front_metrics]))
    write_all(output, config, observations, estimates, xx, yy, arrival, metrics)
    return metrics
