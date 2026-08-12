"""WildfireFrontDynamics command-line interface.

Human-readable by default; pass ``--json`` for machine-readable output.
"""

from __future__ import annotations

import argparse
import difflib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np

from . import __version__
from .cli_app import register_app_commands, run_app
from .cli_incident import incident_config_from_args as _incident_config_from_args
from .cli_incident import register_incident_subcommands
from .cli_map import register_map_commands, run_map
from .cli_ml import register_ml_commands, run_ml
from .cli_multihorizon import register_multihorizon_commands, run_multihorizon
from .cli_report import (
    enrich_incident_summary,
    ensure_utf8_stdio,
    print_demo_report,
    print_doctor_report,
    print_error,
    print_incident_report,
    print_ingest_report,
    print_json,
    print_status_report,
    print_watch_line,
    safe_write,
)
from .cli_teach import (
    register_teach_commands,
    run_demo_third_party,
    run_dry_run_h3,
    run_operator,
    run_show,
    run_teach,
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

  # Modo operario (única puerta de entrada; default sin COMMAND)
  wildfire-front
  wildfire-front operator
  wildfire-front operador
  wildfire-front ensayo
  wildfire-front next
  wildfire-front operator do --all
  wildfire-front operator checklist

  # Teach path (4 actos) + gates snapshot + third-party pack
  wildfire-front teach
  wildfire-front show
  wildfire-front demo-third-party
  wildfire-front dry-run-h3
  wildfire-front decide --policy field_ops --explain

  # ML lab product (not field_ops fusion · IoU ≠ ROS)
  wildfire-front ml list
  wildfire-front ml show
  wildfire-front ml doctor
  wildfire-front ml card --mode offline --scenario hold

  # Batch GeoTIFF ingest (ops products)
  wildfire-front ingest-geotiff \\
    --images artifacts/tobarra_reprojected_lwir \\
    --masks artifacts/tobarra_lwir_masks \\
    --sensor-id lwir_drone --estimated-error-m 2 \\
    --event-id tobarra_20240802 --output outputs/tobarra \\
    --operational --scientific-clean

  # Discoverability + professional brief + map + product SPA
  wildfire-front help
  wildfire-front commands
  wildfire-front brief                 # one-screen operational brief
  wildfire-front brief --role lab --json
  wildfire-front map --work-dir outputs/incidents/_sla_measure --no-live
  wildfire-front map --lat 40.9 --lon -3.1 --radius-km 40   # + FIRMS NRT if network
  wildfire-front app                   # dark ops SPA (brief + Leaflet)
  wildfire-front app --work-dir outputs/incidents/_sla_measure --open
  wildfire-front doctor              # ML lab pre-flight (offline OK)
  wildfire-front doctor --inbox D:/drops --masks D:/masks   # field incident doctor

  # Field: pre-flight check
  wildfire-front incident doctor --inbox D:/drops --masks D:/masks

  # Field: process once
  wildfire-front incident update --inbox D:/drops --work-dir outputs/incidents/IF1 --force

  # Field: live watch (Ctrl+C to stop)
  wildfire-front incident watch --inbox D:/drops --work-dir outputs/incidents/IF1

  # Machine-readable
  wildfire-front incident status --work-dir outputs/incidents/IF1 --json

notes:
  · Grupos: Operario (default · brief · app · ensayo · next) · Lab (ml) · Campo (incident · decide) · Eng (teach · show)
  · Sin COMMAND → modo operario (semáforo + 4 actos + GO_Q). Alias: operador · ops · ensayo · next
  · brief / resumen → resumen profesional + next action (JSON wfd_operator_brief_v1); no es el tablero
  · map → mapa Leaflet estado del incendio (local + FIRMS NRT); hotspots ≠ perímetro oficial
  · app → SPA ops oscura (Leaflet + dashboard); builders brief + map_status; docs/APP.md
  · help / commands → mapa de comandos (no uses solo 'doctor' sin --inbox para incident)
  · doctor (top-level) → ML lab pre-flight por defecto; con --inbox → incident doctor
  · bare ml / bare incident → hubs (exit 0); version|ver|about → --version
  · status / estado → tablero operario (incident status requiere: incident status --work-dir …)
  · Thermal mask ≠ official fire perimeter
  · 15/30/60 envelope is extrapolated guidance, NOT tactical dispatch
  · Filenames must include parseable timestamps for real LWIR frames
  · Docs: docs/START_HERE.md · docs/APP.md · docs/OPERATOR_CLI_CHANGES.md · docs/OPERATOR_UX_LOOP_LOG.md
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


def run_geotiff_ingest(
    images: Path,
    masks: Path | None,
    output: Path,
    event_id: str,
    sensor_id: str,
    estimated_error_m: float,
    band: int,
    threshold: float | None,
    speed_config: GeometrySpeedConfig | None = None,
    mad_z: float | None = None,
    respect_alpha: bool = False,
    min_component_pixels: int = 1,
    scientific_clean: bool = False,
    max_components: int = 5,
    morph_close_pixels: int = 3,
    min_component_area_m2: float = 100.0,
    operational_ref: object | None = None,
    arrival_max_cells: int = 4_000_000,
    write_operational: bool = False,
) -> dict[str, object]:
    result = ingest_geotiff_sequence(
        images,
        masks_dir=masks,
        event_id=event_id,
        sensor_id=sensor_id,
        estimated_error_m=estimated_error_m,
        band=band,
        threshold=threshold,
        mad_z=mad_z,
        respect_alpha=respect_alpha,
        min_component_pixels=min_component_pixels,
        scientific_clean=scientific_clean,
        max_components=max_components,
        morph_close_pixels=morph_close_pixels,
        min_component_area_m2=min_component_area_m2,
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

    arrival_resolution = float(resolution)
    try:
        xx, yy, arrival = reconstruct_arrival_from_components(
            list(result.observations), arrival_resolution
        )
        while arrival.size > arrival_max_cells and arrival_resolution < resolution * 32:
            arrival_resolution *= 2.0
            xx, yy, arrival = reconstruct_arrival_from_components(
                list(result.observations), arrival_resolution
            )
    except MemoryError:
        xx = np.zeros((1, 1))
        yy = np.zeros((1, 1))
        arrival = np.full((1, 1), np.nan)
        arrival_resolution = float("nan")

    speed_result = estimate_geometry_speeds(list(result.observations), speed_config)
    summary: dict[str, object] = {
        "num_observations": len(result.observations),
        "num_components": sum(len(item.components) for item in result.observations),
        "arrival_cells_observed": int((~np.isnan(arrival)).sum()),
        "arrival_resolution_m": arrival_resolution,
        **summarize_ingest_quality(result.records),
        **summarize_observation_quality(list(result.observations)),
        **summarize_geometry_speeds(speed_result),
    }
    write_all(
        output,
        None,
        list(result.observations),
        list(speed_result.estimates),
        xx,
        yy,
        arrival,
        summary,
    )

    if write_operational or scientific_clean or operational_ref is not None:
        from .front_dynamics import build_structural_operational_bundle
        from .scientific_ops import OperationalReference, write_operational_report_html

        ref = operational_ref if isinstance(operational_ref, OperationalReference) else None
        ops = build_structural_operational_bundle(
            list(result.observations),
            summary,
            speed_config=speed_config,
            ref=ref,
        )
        (output / "operational_metrics.json").write_text(
            json.dumps(ops, indent=2, default=str), encoding="utf-8"
        )
        (output / "front_dynamics.json").write_text(
            json.dumps(ops.get("structural") or {}, indent=2, default=str),
            encoding="utf-8",
        )
        write_operational_report_html(ops, event_id, output / "operational_report.html")
        try:
            from .observatory_export import export_operator_bundle

            export_operator_bundle(
                list(result.observations),
                ops,
                output,
                event_id=event_id,
            )
        except Exception as export_exc:  # noqa: BLE001 — pack must still succeed
            summary["operator_export_error"] = str(export_exc)
        summary["operational"] = {
            "quality_grade": ops.get("quality_grade"),
            "quality_label_es": ops.get("quality_label_es"),
            "speed_median_m_min": ops.get("speed_median_m_min"),
            "area_ha_max": ops.get("area_ha_max"),
            "speed_n_observable": ops.get("speed_n_observable"),
            "speed_vs_ref_ratio": ops.get("speed_vs_ref_ratio"),
            "speed_vs_ref_grade": ops.get("speed_vs_ref_grade"),
            "engine": ops.get("engine"),
            "primary_methods_used": ops.get("primary_methods_used"),
            "mean_coreg_shift_m": ops.get("mean_coreg_shift_m"),
        }
    return summary


# ── argparse builders ────────────────────────────────────────────────────────


def _add_global_flags(parser: argparse.ArgumentParser) -> None:
    g = parser.add_argument_group("output")
    g.add_argument(
        "--json",
        action="store_true",
        help="Machine-readable JSON on stdout (full detail, no human tables)",
    )
    g.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show extra detail (frame list, hybrid ROS, etc.)",
    )
    g.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress progress lines on stderr (watch mode)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wildfire-front",
        description=(
            "Wildfire Front Dynamics — reconstruct observed fire fronts from "
            "thermal GeoTIFF sequences, estimate ROS with abstention, and publish "
            "operator packs. Not validated tactical dispatch.\n\n"
            "Start here:  (no COMMAND) → operator board  ·  brief → resumen  ·  "
            "app → SPA ops  ·  map → estado espacial NRT  ·  help → role map  ·  doctor → pre-flight"
        ),
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    # ── demo ──────────────────────────────────────────────────────────────
    demo = commands.add_parser(
        "demo",
        help="Synthetic end-to-end demo with ground truth",
        description="Generate a synthetic burn, reconstruct fronts, write HTML report.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="example:\n  wildfire-front demo --output outputs/demo --seed 7",
    )
    demo.add_argument("--output", type=Path, default=Path("outputs/demo"), help="Output directory")
    demo.add_argument("--seed", type=int, default=7, help="RNG seed (default: 7)")
    demo.add_argument(
        "--position-error-m",
        type=float,
        default=0.6,
        metavar="M",
        help="One-sigma observation error in metres (default: 0.6)",
    )
    _add_global_flags(demo)

    # ── ingest-geotiff ────────────────────────────────────────────────────
    ingest = commands.add_parser(
        "ingest-geotiff",
        help="Batch-ingest a folder of georeferenced thermal GeoTIFFs",
        description=(
            "Ingest images (+ optional masks), reconstruct arrival/speeds, "
            "optionally write operational front_dynamics products."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ig = ingest.add_argument_group("paths")
    ig.add_argument(
        "--images", type=Path, required=True, metavar="DIR", help="GeoTIFF images folder"
    )
    ig.add_argument("--masks", type=Path, metavar="DIR", help="Binary masks folder (optional)")
    ig.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/geotiff-demo"),
        metavar="DIR",
        help="Output pack directory (default: outputs/geotiff-demo)",
    )
    iid = ingest.add_argument_group("identity")
    iid.add_argument("--event-id", default="geotiff_event", help="Event id")
    iid.add_argument("--sensor-id", required=True, help="Sensor id (required)")
    iid.add_argument(
        "--estimated-error-m",
        type=float,
        required=True,
        metavar="M",
        help="Declared geolocation error (m) — required",
    )
    iseg = ingest.add_argument_group("segmentation")
    iseg.add_argument("--band", type=int, default=1)
    iseg.add_argument("--threshold", type=float, help="Fixed threshold (needs no masks)")
    iseg.add_argument("--mad-z", type=float, help="MAD z-score adaptive threshold")
    iseg.add_argument(
        "--respect-alpha",
        action="store_true",
        help="Ignore transparent pixels on RGBA GeoTIFFs",
    )
    iseg.add_argument("--min-component-pixels", type=int, default=1)
    iseg.add_argument(
        "--scientific-clean",
        action="store_true",
        help="Enable morphological clean + main-front filter",
    )
    iseg.add_argument("--max-components", type=int, default=5)
    iseg.add_argument("--morph-close-pixels", type=int, default=3)
    iseg.add_argument("--min-component-area-m2", type=float, default=100.0)
    iops = ingest.add_argument_group("operational products")
    iops.add_argument(
        "--operational",
        action="store_true",
        help="Write front_dynamics + operator GIS/brief (recommended for packs)",
    )
    iops.add_argument("--ref-name", type=str, default=None)
    iops.add_argument("--ref-vp-m-min", type=float, default=None)
    iops.add_argument("--ref-area-ha", type=float, default=None)
    isp = ingest.add_argument_group("geometry speed")
    isp.add_argument("--speed-sample-spacing-m", type=float, default=2.0)
    isp.add_argument("--speed-max-normal-distance-m", type=float, default=100.0)
    isp.add_argument("--speed-observability-ratio", type=float, default=2.0)
    isp.add_argument("--speed-min-valid-fraction", type=float, default=0.25)
    isp.add_argument("--speed-max-turn-angle-deg", type=float, default=60.0)
    isp.add_argument("--speed-max-normal-to-nearest-ratio", type=float, default=2.0)
    _add_global_flags(ingest)

    # ── incident ──────────────────────────────────────────────────────────
    register_incident_subcommands(commands, add_global_flags=_add_global_flags)

    # ── ml lab product surface (list/show/predict/card/doctor) ─────────────
    register_ml_commands(commands, add_global_flags=_add_global_flags)

    # ── multi-horizon field_ops (1/3/5/12/24 h) — not ML next-day ──────────
    register_multihorizon_commands(commands, add_global_flags=_add_global_flags)

    # ── fire-status map (local GeoJSON + optional FIRMS NRT) ─────────────
    register_map_commands(commands, add_global_flags=_add_global_flags)

    # ── product SPA (Leaflet + dashboard; brief + map_status) ────────────
    register_app_commands(commands, add_global_flags=_add_global_flags)

    # ── teach / show / demo-third-party (product teach surface v7) ────────
    register_teach_commands(commands, add_global_flags=_add_global_flags)

    # ── commands / help map (discoverability) ──────────────────────────
    cmds = commands.add_parser(
        "commands",
        help="Command map by role (operator / field / lab / decision / eng)",
        description=(
            "Print a role-grouped map of CLI entry points. "
            "Use when you know the product exists but not which COMMAND. "
            "Alias: help · cmds · ayuda."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  wildfire-front help\n"
            "  wildfire-front commands\n"
            "  wildfire-front commands --json\n"
        ),
    )
    _add_global_flags(cmds)

    # ── brief / resumen (professional one-screen summary) ─────────────
    brief = commands.add_parser(
        "brief",
        help="Professional one-screen operational brief (role playbook + next action)",
        description=(
            "Executive / partner-facing brief: gates, honesty rails, next action, "
            "and a recommended command sequence for a role.\n"
            "Not the traffic-light operator board — use ``operator`` for that.\n"
            "Rails: field_ops ML fusion OFF · IoU ≠ ROS · not tactical dispatch.\n"
            "Aliases: resumen · summary · briefing."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  wildfire-front brief\n"
            "  wildfire-front brief --role field\n"
            "  wildfire-front brief --role lab --json\n"
            "  wildfire-front resumen --role decision\n"
        ),
    )
    brief.add_argument(
        "--role",
        choices=("operator", "field", "lab", "decision"),
        default="operator",
        help="Audience playbook (default: operator)",
    )
    _add_global_flags(brief)

    # ── doctor hub (ML default; incident with --inbox) ─────────────────
    doctor = commands.add_parser(
        "doctor",
        help="Pre-flight hub: ML lab (default) or incident (needs --inbox)",
        description=(
            "Top-level pre-flight without tribal knowledge of subcommands.\n"
            "  · without --inbox → ML lab doctor (offline structure OK)\n"
            "  · with --inbox    → incident doctor (field drop-zone checks)\n"
            "Also: wildfire-front ml doctor · wildfire-front incident doctor"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  wildfire-front doctor\n"
            "  wildfire-front doctor --json\n"
            "  wildfire-front doctor --inbox D:/drops --masks D:/masks\n"
            "  wildfire-front doctor --target hub\n"
        ),
    )
    doctor.add_argument(
        "--target",
        choices=("auto", "ml", "incident", "hub"),
        default="auto",
        help=(
            "auto: ml without --inbox, incident with --inbox; "
            "ml/incident force path; hub = routes only (exit 0)"
        ),
    )
    doctor.add_argument(
        "--inbox",
        type=Path,
        default=None,
        metavar="DIR",
        help="Field drop zone (implies incident doctor when target=auto)",
    )
    doctor.add_argument(
        "--work-dir",
        type=Path,
        default=None,
        metavar="DIR",
        help="Optional incident work-dir (incident doctor only)",
    )
    doctor.add_argument(
        "--masks",
        type=Path,
        default=None,
        metavar="DIR",
        help="Optional masks dir for incident doctor",
    )
    doctor.add_argument(
        "--event-id",
        default="incident",
        help="Event id for incident doctor (default: incident)",
    )
    _add_global_flags(doctor)

    # ── decide (Fire Decision Card) ─────────────────────────────────────
    decide = commands.add_parser(
        "decide",
        help="Build Fire Decision Card (GO/HOLD/ABSTAIN + metrics fusion)",
        description=(
            "Fuse optional ML / ops / open-CEMS metrics into a decision card "
            "with confidence and audit hashes. Empty sources → ABSTAIN. "
            "Default policy is 'default' (not field_ops silence rails). "
            "For field: --policy field_ops."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  wildfire-front decide --policy field_ops\n"
            "  wildfire-front decide --policy field_ops --explain\n"
            "  wildfire-front decide --list-policies\n"
            "  wildfire-front decide --work-dir outputs/incidents/IF1 --policy field_ops\n"
            "  wildfire-front decide --use-ml-v34 --policy research_open --explain\n"
        ),
    )
    decide.add_argument("--event-id", default="decision", help="Event id for the card")
    decide.add_argument(
        "--work-dir",
        type=Path,
        default=None,
        help="Optional incident work-dir (reads outbox/incident_state.json)",
    )
    decide.add_argument(
        "--open-pack",
        type=Path,
        default=None,
        help="Optional open_if pack dir (scorecard_pista_b.json)",
    )
    decide.add_argument(
        "--use-ml-v34",
        action="store_true",
        help="Include clm_ensemble_v34 manifest metrics (holdout research quality)",
    )
    decide.add_argument(
        "--ml-prediction",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "Path to ml_live_metrics_v1 JSON, or ml_prediction_v1 wrapper "
            "(e.g. outbox/ml_prediction.json with nested ml_live_metrics)"
        ),
    )
    decide.add_argument(
        "--ml-live-metrics",
        type=Path,
        default=None,
        metavar="PATH",
        dest="ml_live_metrics",
        help="Alias of --ml-prediction",
    )
    decide.add_argument(
        "--allow-ml-live-in-fusion",
        action="store_true",
        help=(
            "Opt-in: allow live ML weight in THIS decide call only "
            "(does NOT rewrite field_ops policy file; field_ops fusion stays OFF)"
        ),
    )
    decide.add_argument(
        "--ml-live-untrusted",
        action="store_true",
        help="Treat live metrics as display-only (actionable=false, weight=0)",
    )
    decide.add_argument(
        "--require-ops-for-go",
        action="store_true",
        help="Never GO without thermal ops source",
    )
    decide.add_argument(
        "--policy",
        default=None,
        metavar="ID",
        help="Decision policy id (default|field_ops|research_open|demo). See config/decision_policies.json",
    )
    decide.add_argument(
        "--list-policies",
        action="store_true",
        help="List available decision policies and exit",
    )
    decide.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write card JSON to this path",
    )
    decide.add_argument(
        "--explain",
        action="store_true",
        help=(
            "Teaching mode: expand sources/weights/reasons/disclaimers "
            "(no-op with --json; JSON remains pure card payload)"
        ),
    )
    _add_global_flags(decide)

    # ── serve-decide (minimal HTTP API) ────────────────────────────────
    serve = commands.add_parser(
        "serve-decide",
        help="Minimal HTTP API for Fire Decision Card (POST /v1/decide)",
        description=(
            "Local Decision Card HTTP server (stdlib). "
            "GET /health · GET /v1/openapi.json · POST /v1/decide. "
            "Default bind 127.0.0.1 — not production multi-tenant hosting."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "example:\n"
            "  wildfire-front serve-decide --port 8765\n"
            "  curl -s http://127.0.0.1:8765/health\n"
            "  curl -s -X POST http://127.0.0.1:8765/v1/decide "
            '-H "Content-Type: application/json" '
            '-d "{\\"use_ml_v34\\": true, \\"require_ops_for_go\\": true}"\n'
        ),
    )
    serve.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    serve.add_argument("--port", type=int, default=8765, help="Bind port (default: 8765)")
    serve.add_argument(
        "--base-dir",
        type=Path,
        default=None,
        help="Resolve relative work_dir/open_pack paths from here (default: repo root)",
    )
    _add_global_flags(serve)

    # ── export-acta (forensic bundle) ──────────────────────────────────
    acta = commands.add_parser(
        "export-acta",
        help="Write forensic acta + radio-bridge + replay sources from a Decision Card",
        description=(
            "Paid-value audit package: fire_decision_acta.md, fire_decision_radio.txt, "
            "replay_sources.json, forensic_manifest.json. Not a court PDF."
        ),
    )
    acta.add_argument(
        "--card",
        type=Path,
        default=None,
        help="Path to fire_decision_card.json (or use --work-dir outbox)",
    )
    acta.add_argument(
        "--work-dir",
        type=Path,
        default=None,
        help="Incident work-dir (uses outbox/fire_decision_card.json)",
    )
    acta.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Bundle directory (default: next to card or work_dir/outbox)",
    )
    acta.add_argument("--operator", default=None, help="Optional operator / sala label on acta")
    acta.add_argument(
        "--require-ops-for-go",
        action="store_true",
        help="Store require_ops_for_go=true in replay sources",
    )
    _add_global_flags(acta)

    # ── replay-decide (forensic verify) ────────────────────────────────
    replay = commands.add_parser(
        "replay-decide",
        help="Rebuild Decision Card from forensic sources and verify hashes",
        description=(
            "Forensic replay: load replay_sources.json (or card) and verify "
            "output_hash + decision match. Empty mismatch → replay_ok=false."
        ),
    )
    replay.add_argument(
        "--bundle",
        type=Path,
        default=None,
        help="Directory with replay_sources.json or fire_decision_card.json",
    )
    replay.add_argument(
        "--sources",
        type=Path,
        default=None,
        help="Explicit replay_sources.json path",
    )
    replay.add_argument(
        "--work-dir",
        type=Path,
        default=None,
        help="Incident work-dir (outbox forensic bundle)",
    )
    _add_global_flags(replay)

    return parser


def _emit(payload: dict[str, Any] | None, *, as_json: bool, human_fn, **human_kw) -> None:
    if as_json:
        if payload is not None:
            print_json(payload)
        return
    human_fn(**human_kw)


# Spanish / short aliases → canonical commands (operator UX)
_COMMAND_ALIASES: dict[str, str] = {
    "operador": "operator",
    "ops": "operator",
    "estado": "operator",
    "semaforo": "operator",
    "ayuda": "commands",
    "resumen": "brief",
    "summary": "brief",
    "briefing": "brief",
    "spa": "app",
    "console": "app",
}

# Multi-token expansions (demo rehearsal / next-step verbs)
_COMMAND_EXPANSIONS: dict[str, list[str]] = {
    "ensayo": ["operator", "do", "--all"],
    "path": ["operator", "do", "--all"],
    "next": ["operator", "next"],
    "go_q": ["operator", "next"],
    "go-q": ["operator", "next"],
    "checklist": ["operator", "checklist"],
    # Discoverability (users type "help" / "cmds" before finding --help)
    "help": ["commands"],
    "cmds": ["commands"],
    "command": ["commands"],
}

# Users type these as COMMAND instead of --version
_VERSION_TOKENS: frozenset[str] = frozenset({"version", "ver", "about"})

_ML_SUBCOMMAND_NAMES: tuple[str, ...] = (
    "list",
    "show",
    "predict",
    "card",
    "doctor",
    "cases",
    "curve",
    "freeze",
    "smoke",
    "lofo",
    "lift",
    "next",
)

_INCIDENT_SUBCOMMAND_NAMES: tuple[str, ...] = ("doctor", "update", "watch", "status")


def _has_flag(argv: list[str], *names: str) -> bool:
    """True if any of ``--flag`` or ``--flag=value`` appears in argv."""
    for a in argv:
        for n in names:
            if a == n or a.startswith(f"{n}="):
                return True
    return False


def _rewrite_argv(raw: list[str]) -> list[str]:
    """Cold-start default, aliases, expansions, and status/doctor footguns."""
    if not raw:
        return ["operator"]
    head = str(raw[0])
    rest = list(raw[1:])

    # status: bare → operator board; with --work-dir → incident status
    if head == "status":
        if _has_flag(rest, "--work-dir"):
            return ["incident", "status", *rest]
        return ["operator", *rest]

    if head in _COMMAND_EXPANSIONS:
        return [*_COMMAND_EXPANSIONS[head], *rest]
    if head in _COMMAND_ALIASES:
        return [_COMMAND_ALIASES[head], *rest]
    return raw

# Canonical top-level commands (keep in sync with build_parser registrations)
_TOP_LEVEL_COMMANDS: frozenset[str] = frozenset(
    {
        "demo",
        "ingest-geotiff",
        "incident",
        "ml",
        "multihorizon",
        "teach",
        "show",
        "demo-third-party",
        "dry-run-h3",
        "operator",
        "commands",
        "brief",
        "map",
        "app",
        "doctor",
        "decide",
        "serve-decide",
        "export-acta",
        "replay-decide",
    }
)


def build_commands_map() -> dict[str, Any]:
    """Role-grouped CLI map for ``commands`` / ``help`` (discoverability)."""
    return {
        "schema": "wfd_cli_commands_v1",
        "entry": "python -m wildfire_front",
        "default": "operator (when no COMMAND)",
        "groups": [
            {
                "id": "operator",
                "title": "Operario (única puerta · <30 s)",
                "commands": [
                    {"cmd": "(none) / operator / operador / ops / status / estado", "why": "tablero semáforo + 4 actos + GO_Q"},
                    {"cmd": "brief / resumen / summary", "why": "resumen profesional + next action + JSON v1"},
                    {"cmd": "app / spa / console [--work-dir] [--open] [--serve] [--ui-mode simple|advanced]", "why": "SPA industrial C2: dual-mode Fácil|Pro · Estado/Decidir/Acta · opcional HTTP local"},
                    {"cmd": "ensayo", "why": "4 actos compactos (do --all)"},
                    {"cmd": "next / go_q", "why": "qué falta para GO_Q (humano)"},
                    {"cmd": "checklist", "why": "checklist 7 ítems eng"},
                    {"cmd": "operator do --act 1|2|3|4", "why": "un acto encapsulado"},
                    {"cmd": "operator explain-abstain", "why": "ABSTAIN ≠ bug"},
                ],
            },
            {
                "id": "preflight",
                "title": "Doctor / pre-flight",
                "commands": [
                    {"cmd": "doctor", "why": "ML lab pre-flight (offline OK)"},
                    {"cmd": "doctor --inbox DIR", "why": "field incident doctor"},
                    {"cmd": "ml doctor", "why": "lab weights / catalog / rails"},
                    {"cmd": "incident doctor --inbox DIR", "why": "timestamps / CRS / masks"},
                    {"cmd": "brief --role field|lab|decision", "why": "playbook profesional por rol"},
                ],
            },
            {
                "id": "field",
                "title": "Campo (incident runtime)",
                "commands": [
                    {"cmd": "incident update --inbox … --work-dir …", "why": "procesar inbox una vez"},
                    {"cmd": "incident watch --inbox … --work-dir …", "why": "loop en vivo"},
                    {"cmd": "incident status --work-dir …", "why": "leer outbox (NO es 'status' suelto)"},
                    {"cmd": "map --work-dir … [--no-live]", "why": "mapa estado (local + FIRMS NRT opcional)"},
                    {"cmd": "app --work-dir … --open", "why": "SPA mapa + Decision Card + brief (demo sala)"},
                    {"cmd": "ingest-geotiff --images … --sensor-id … --estimated-error-m …", "why": "batch térmico"},
                ],
            },
            {
                "id": "decision",
                "title": "Decision Card",
                "commands": [
                    {"cmd": "decide --policy field_ops", "why": "GO/HOLD/ABSTAIN (field silence rails)"},
                    {"cmd": "decide --list-policies", "why": "políticas disponibles"},
                    {"cmd": "export-acta --card … | --work-dir …", "why": "acta + radio + replay sources"},
                    {"cmd": "replay-decide --bundle … | --work-dir …", "why": "verificar hashes forenses"},
                    {"cmd": "serve-decide --port 8765", "why": "HTTP local POST /v1/decide"},
                ],
            },
            {
                "id": "lab",
                "title": "ML lab (≠ field fusion · IoU ≠ ROS)",
                "commands": [
                    {"cmd": "ml list / show / doctor", "why": "catálogo + scorecard + pre-flight"},
                    {"cmd": "ml cases / curve / freeze / smoke / lofo / next", "why": "teaching + freeze surface"},
                    {"cmd": "ml predict --list-products", "why": "productos listos (weights)"},
                    {"cmd": "ml card --mode offline --scenario hold", "why": "demo Decision Card offline"},
                ],
            },
            {
                "id": "eng",
                "title": "Eng / teach",
                "commands": [
                    {"cmd": "teach / show", "why": "4 actos docs + gates snapshot"},
                    {"cmd": "demo-third-party / dry-run-h3", "why": "pack + replay / H3 eng path"},
                    {"cmd": "demo", "why": "sintético E2E"},
                    {"cmd": "multihorizon …", "why": "forecast 1/3/5/12/24 h (field_ops, not ML next-day)"},
                ],
            },
        ],
        "common_footguns": [
            {
                "tried": "help / doctor / status",
                "instead": "help→commands · doctor→ml lab pre-flight · status→operator board",
            },
            {
                "tried": "ml / incident sin SUBCOMMAND",
                "instead": "bare → hub (exit 0); o ml list / incident doctor --inbox …",
            },
            {
                "tried": "version (como COMMAND)",
                "instead": "wildfire-front --version  ·  o alias: version / ver / about",
            },
            {
                "tried": "incident status (sin --work-dir)",
                "instead": "incident status --work-dir outputs/incidents/IF1",
            },
            {
                "tried": "decide vacío parece roto",
                "instead": "ABSTAIN es feature; operator explain-abstain · --policy field_ops",
            },
            {
                "tried": "export-acta / replay-decide sin paths",
                "instead": "--card / --bundle / --work-dir con outbox",
            },
        ],
        "docs": [
            "docs/START_HERE.md",
            "docs/OPERATOR_UX_LOOP_LOG.md",
            "docs/OPERATOR_CLI_CHANGES.md",
        ],
    }


def format_commands_map_human(payload: dict[str, Any] | None = None) -> str:
    """Human command map for ``wildfire-front commands`` / ``help``."""
    data = payload or build_commands_map()
    lines = [
        "╔══════════════════════════════════════════════════════════╗",
        "║  WFD · mapa de comandos (por rol)                        ║",
        "╚══════════════════════════════════════════════════════════╝",
        "",
        f"  Entrada:  {data.get('entry')}",
        f"  Default:  {data.get('default')}",
        "",
    ]
    for g in data.get("groups") or []:
        lines.append(f"── {g.get('title')} ──")
        for row in g.get("commands") or []:
            cmd = str(row.get("cmd") or "")
            why = str(row.get("why") or "")
            lines.append(f"  {cmd}")
            if why:
                lines.append(f"      → {why}")
        lines.append("")
    lines.append("── Footguns frecuentes ──")
    for f in data.get("common_footguns") or []:
        lines.append(f"  · {f.get('tried')}")
        lines.append(f"      → {f.get('instead')}")
    lines.append("")
    lines.append("  Más: wildfire-front COMMAND --help · docs/START_HERE.md")
    lines.append("")
    return "\n".join(lines)


def _suggest_close(token: str, choices: Sequence[str], *, n: int = 3) -> list[str]:
    """Typo suggestions (difflib); empty if nothing close enough."""
    t = str(token or "").strip()
    if not t:
        return []
    # Include common aliases in the pool for better Spanish/short matches
    pool = sorted({*choices, *_COMMAND_ALIASES.keys(), *_COMMAND_EXPANSIONS.keys()})
    return difflib.get_close_matches(t, pool, n=n, cutoff=0.55)


def _print_unknown_command_hint(token: str) -> None:
    """Friendly hint only for *unknown* top-level COMMANDs (not missing flags)."""
    import sys as _sys

    sugg = _suggest_close(token, sorted(_TOP_LEVEL_COMMANDS))
    sugg_line = ""
    if sugg:
        sugg_line = f"  ¿Quisiste decir?: {' · '.join(sugg)}\n"

    print(
        "\n"
        f"Comando desconocido: {token!r}\n"
        f"{sugg_line}"
        "  python -m wildfire_front                 # tablero operario (default)\n"
        "  python -m wildfire_front help            # mapa de comandos\n"
        "  python -m wildfire_front ensayo          # 4 actos compactos\n"
        "  python -m wildfire_front doctor          # pre-flight ML lab\n"
        "  python -m wildfire_front next            # qué falta para GO_Q\n"
        "  python -m wildfire_front --version       # versión (también: version / ver)\n"
        "Docs: docs/START_HERE.md · docs/OPERATOR_UX_LOOP_LOG.md\n",
        file=_sys.stderr,
    )


def _print_operator_hint() -> None:
    """Backward-compatible name: unknown-command operator path hint."""
    _print_unknown_command_hint("?")


def _print_contextual_argparse_hint(raw: list[str]) -> None:
    """Extra hints for known commands with missing args (not operator-mode spam)."""
    import sys as _sys

    if not raw:
        return
    head = str(raw[0])
    rest = [str(x) for x in raw[1:]]
    blob = " ".join(rest).lower()

    if head == "incident":
        if not rest or rest[0] in ("-h", "--help"):
            return
        sub = rest[0] if rest else ""
        if sub.startswith("-"):
            return
        if sub == "doctor" and "--inbox" not in blob:
            print(
                "\n"
                "hint: incident doctor needs a drop zone:\n"
                "  wildfire-front incident doctor --inbox DIR [--masks DIR]\n"
                "  or:  wildfire-front doctor --inbox DIR\n",
                file=_sys.stderr,
            )
        elif sub == "status" and "--work-dir" not in blob:
            print(
                "\n"
                "hint: incident status needs a workspace (not bare 'status'):\n"
                "  wildfire-front incident status --work-dir outputs/incidents/IF1\n"
                "  bare 'status' / 'estado' → operator board (not field outbox)\n",
                file=_sys.stderr,
            )
        elif sub in ("update", "watch") and ("--inbox" not in blob or "--work-dir" not in blob):
            print(
                "\n"
                "hint: incident update/watch need both paths:\n"
                "  wildfire-front incident update --inbox DIR --work-dir DIR [--force]\n"
                "  wildfire-front incident watch  --inbox DIR --work-dir DIR\n",
                file=_sys.stderr,
            )
        elif sub not in _INCIDENT_SUBCOMMAND_NAMES:
            close = _suggest_close(sub, _INCIDENT_SUBCOMMAND_NAMES)
            extra = f"  ¿Quisiste decir?: {' · '.join(close)}\n" if close else ""
            print(
                "\n"
                "hint: incident subcommands: doctor | update | watch | status\n"
                f"{extra}"
                "  bare 'incident' → field hub\n"
                "  wildfire-front incident --help\n",
                file=_sys.stderr,
            )
    elif head == "doctor" and "--inbox" not in blob and any(
        t in blob for t in ("incident",)
    ):
        print(
            "\n"
            "hint: field doctor needs --inbox:\n"
            "  wildfire-front doctor --inbox DIR\n",
            file=_sys.stderr,
        )
    elif head == "ml":
        if not rest or str(rest[0]).startswith("-"):
            return
        sub = rest[0]
        if sub not in _ML_SUBCOMMAND_NAMES:
            close = _suggest_close(sub, _ML_SUBCOMMAND_NAMES)
            extra = f"  ¿Quisiste decir?: {' · '.join(close)}\n" if close else ""
            print(
                "\n"
                "hint: ml subcommands: "
                f"{' '.join(_ML_SUBCOMMAND_NAMES)}\n"
                f"{extra}"
                "  bare 'ml' → lab hub (exit 0)\n"
                "  wildfire-front ml --help\n",
                file=_sys.stderr,
            )
    elif head == "ingest-geotiff":
        print(
            "\n"
            "hint: ingest-geotiff needs images + sensor identity:\n"
            "  wildfire-front ingest-geotiff \\\n"
            "    --images DIR --sensor-id lwir_drone --estimated-error-m 2 \\\n"
            "    [--masks DIR] --output outputs/pack --operational\n"
            "  See: wildfire-front ingest-geotiff --help\n",
            file=_sys.stderr,
        )
    elif head == "export-acta":
        print(
            "\n"
            "hint: export-acta needs a card path or incident work-dir:\n"
            "  wildfire-front export-acta --card path/to/fire_decision_card.json\n"
            "  wildfire-front export-acta --work-dir outputs/incidents/IF1\n",
            file=_sys.stderr,
        )
    elif head == "replay-decide":
        print(
            "\n"
            "hint: replay-decide needs forensic inputs:\n"
            "  wildfire-front replay-decide --bundle DIR\n"
            "  wildfire-front replay-decide --sources replay_sources.json\n"
            "  wildfire-front replay-decide --work-dir outputs/incidents/IF1\n",
            file=_sys.stderr,
        )


def _is_known_top_level(token: str) -> bool:
    return (
        token in _TOP_LEVEL_COMMANDS
        or token in _COMMAND_ALIASES
        or token in _COMMAND_EXPANSIONS
        or token in _VERSION_TOKENS
        or token == "status"  # smart rewrite (operator vs incident)
    )


def build_incident_hub() -> dict[str, Any]:
    """Discoverability hub for bare ``incident`` (field runtime)."""
    return {
        "schema": "wfd_incident_hub_v1",
        "banner": "incident_runtime_v1 · NOT tactical dispatch · geometry-first",
        "subcommands": list(_INCIDENT_SUBCOMMAND_NAMES),
        "start_here": [
            {
                "cmd": "wildfire-front incident doctor --inbox DIR [--masks DIR]",
                "why": "pre-flight timestamps / CRS / masks",
            },
            {
                "cmd": "wildfire-front incident update --inbox DIR --work-dir DIR",
                "why": "procesar inbox una vez → outbox",
            },
            {
                "cmd": "wildfire-front incident watch --inbox DIR --work-dir DIR",
                "why": "loop en vivo (Ctrl+C)",
            },
            {
                "cmd": "wildfire-front incident status --work-dir DIR",
                "why": "leer outbox (NO es bare 'status')",
            },
        ],
        "aliases_note": (
            "bare 'status' / 'estado' → operator board; "
            "field status needs: incident status --work-dir …"
        ),
        "also": {
            "doctor_top": "wildfire-front doctor --inbox DIR",
            "operator": "wildfire-front  |  wildfire-front operator",
        },
    }


def format_incident_hub_human(payload: dict[str, Any] | None = None) -> str:
    data = payload or build_incident_hub()
    lines = [
        "╔══════════════════════════════════════════════════════════╗",
        "║  WFD · incident hub  (campo · no dispatch táctico)       ║",
        "╚══════════════════════════════════════════════════════════╝",
        "",
        f"  {data.get('banner')}",
        "",
        "── Empieza aquí ──",
    ]
    for row in data.get("start_here") or []:
        lines.append(f"  {row.get('cmd')}")
        if row.get("why"):
            lines.append(f"      → {row['why']}")
    lines.append("")
    lines.append(f"  SUBCOMMANDS: {' '.join(data.get('subcommands') or [])}")
    lines.append(f"  Nota: {data.get('aliases_note')}")
    also = data.get("also") or {}
    if also.get("doctor_top"):
        lines.append(f"  Top doctor: {also['doctor_top']}")
    if also.get("operator"):
        lines.append(f"  Operario:   {also['operator']}")
    lines.append("  Más: wildfire-front incident --help")
    lines.append("")
    return "\n".join(lines)


def run_incident_hub(args: argparse.Namespace) -> int:
    """Bare ``incident`` — exit 0 hub."""
    payload = build_incident_hub()
    if bool(getattr(args, "json", False)):
        print_json(payload)
    else:
        import sys as _sys

        _sys.stdout.write(format_incident_hub_human(payload))
    return 0


def run_doctor_hub(args: argparse.Namespace) -> int:
    """Top-level doctor: ML lab by default; incident when --inbox (or target)."""
    import sys as _sys

    as_json = bool(getattr(args, "json", False))
    target = str(getattr(args, "target", "auto") or "auto")
    inbox = getattr(args, "inbox", None)

    if target == "auto":
        target = "incident" if inbox is not None else "ml"

    if target == "hub":
        payload = {
            "schema": "wfd_doctor_hub_v1",
            "routes": {
                "ml": "wildfire-front doctor  |  wildfire-front ml doctor",
                "incident": "wildfire-front doctor --inbox DIR  |  wildfire-front incident doctor --inbox DIR",
                "operator": "wildfire-front  |  wildfire-front status",
            },
            "note": (
                "Bare 'doctor' = ML lab pre-flight (offline OK). "
                "Field checks require --inbox. Not tactical dispatch."
            ),
        }
        if as_json:
            print_json(payload)
        else:
            print("WFD · doctor hub (elige un camino)")
            print("  ML lab (default):  wildfire-front doctor")
            print("                     wildfire-front ml doctor")
            print("  Field incident:    wildfire-front doctor --inbox DIR [--masks DIR]")
            print("                     wildfire-front incident doctor --inbox DIR")
            print("  Operator board:    wildfire-front  |  wildfire-front status")
            print("  Nota: mask térmica ≠ perímetro oficial · no dispatch táctico")
        return 0

    if target == "incident":
        if inbox is None:
            print_error(
                "incident doctor requires --inbox DIR",
                hint=(
                    "wildfire-front doctor --inbox D:/drops [--masks D:/masks]\n"
                    "  or: wildfire-front incident doctor --inbox D:/drops\n"
                    "  ML lab only: wildfire-front doctor   (or --target ml)"
                ),
            )
            return 2
        from .incident.doctor import doctor_incident

        report = doctor_incident(
            inbox=inbox,
            work_dir=getattr(args, "work_dir", None),
            masks_dir=getattr(args, "masks", None),
            event_id=str(getattr(args, "event_id", None) or "incident"),
        )
        if as_json:
            print_json(
                {
                    "schema": "wfd_doctor_hub_v1",
                    "target": "incident",
                    "report": report,
                }
            )
        else:
            print("── doctor → incident (field) ──")
            print_doctor_report(report, as_json=False)
        return 0 if report.get("ok") else 1

    # target == ml
    from .cli_ml import build_ml_doctor_report, format_ml_doctor_human

    report = build_ml_doctor_report()
    if as_json:
        print_json(
            {
                "schema": "wfd_doctor_hub_v1",
                "target": "ml",
                "report": report,
                "also": {
                    "incident": "wildfire-front doctor --inbox DIR",
                    "hub": "wildfire-front doctor --target hub",
                },
            }
        )
    else:
        if not bool(getattr(args, "quiet", False)):
            print("── doctor → ML lab (offline OK; not field_ops fusion) ──")
            print("  field path: wildfire-front doctor --inbox DIR")
            print("  routes:     wildfire-front doctor --target hub")
            print("")
        _sys.stdout.write(format_ml_doctor_human(report))
    return 0


def main(argv: Sequence[str] | None = None) -> None:
    # Windows PowerShell default charmap/cp1252 cannot print ╔ ≠ · etc.
    ensure_utf8_stdio()

    raw_in = list(argv) if argv is not None else None
    if raw_in is None:
        import sys as _sys

        raw_in = list(_sys.argv[1:])
    # Preserve original head for unknown-command hints (before rewrite)
    original_head = str(raw_in[0]) if raw_in else ""

    # version / ver / about as COMMAND (users rarely type --version first)
    if original_head in _VERSION_TOKENS:
        safe_write(f"wildfire-front {__version__}")
        return

    raw = _rewrite_argv(raw_in)

    parser = build_parser()
    try:
        args = parser.parse_args(raw)
    except SystemExit as exc:
        # Invalid usage: contextual hints. Operator board only for *unknown* COMMAND.
        code = exc.code
        if code not in (0, None) and raw_in and not str(raw_in[0]).startswith("-"):
            head = original_head
            if not _is_known_top_level(head):
                _print_unknown_command_hint(head)
            else:
                # Prefer rewritten argv for subcommand context (status→incident, etc.)
                _print_contextual_argparse_hint(raw)
        raise
    as_json = bool(getattr(args, "json", False))
    verbose = bool(getattr(args, "verbose", False))
    quiet = bool(getattr(args, "quiet", False))

    try:
        if args.command == "commands":
            payload = build_commands_map()
            if as_json:
                print_json(payload)
            else:
                safe_write(format_commands_map_human(payload), end="")
            return

        if args.command == "brief":
            from .product.operator_ux import (
                build_operator_brief,
                format_operator_brief_human,
            )

            role = str(getattr(args, "role", "operator") or "operator")
            payload = build_operator_brief(role=role)
            if as_json:
                print_json(payload)
            else:
                safe_write(format_operator_brief_human(payload), end="")
            return

        if args.command == "map":
            raise SystemExit(run_map(args))

        if args.command == "app":
            raise SystemExit(run_app(args))

        if args.command == "doctor":
            raise SystemExit(run_doctor_hub(args))

        if args.command == "demo":
            metrics = run_demo(args.output, args.seed, args.position_error_m)
            print_demo_report(args.output, metrics, as_json=as_json)
            return

        if args.command == "ingest-geotiff":
            from .scientific_ops import OperationalReference

            ref = None
            if args.ref_vp_m_min is not None or args.ref_area_ha is not None:
                ref = OperationalReference(
                    name=args.ref_name or "operational_anchor",
                    vp_m_min=args.ref_vp_m_min,
                    area_ha=args.ref_area_ha,
                )
            metrics = run_geotiff_ingest(
                args.images,
                args.masks,
                args.output,
                args.event_id,
                args.sensor_id,
                args.estimated_error_m,
                args.band,
                args.threshold,
                GeometrySpeedConfig(
                    sample_spacing_m=args.speed_sample_spacing_m,
                    max_normal_distance_m=args.speed_max_normal_distance_m,
                    observability_ratio=args.speed_observability_ratio,
                    min_valid_fraction=args.speed_min_valid_fraction,
                    max_turn_angle_deg=args.speed_max_turn_angle_deg,
                    max_normal_to_nearest_ratio=args.speed_max_normal_to_nearest_ratio,
                ),
                args.mad_z,
                args.respect_alpha,
                args.min_component_pixels,
                scientific_clean=bool(args.scientific_clean),
                max_components=args.max_components,
                morph_close_pixels=args.morph_close_pixels,
                min_component_area_m2=args.min_component_area_m2,
                operational_ref=ref,
                write_operational=bool(args.operational)
                or ref is not None
                or bool(args.scientific_clean),
            )
            print_ingest_report(args.output, metrics, as_json=as_json, event_id=args.event_id)
            return

        if args.command == "decide":
            import json as _json

            from .product.decide_service import decide_from_request
            from .product.policy import list_policies

            if getattr(args, "list_policies", False):
                rows = list_policies()
                if as_json:
                    print_json({"policies": rows})
                else:
                    for r in rows:
                        print(
                            f"{r.get('id'):<16} require_ops={r.get('require_ops_for_go')}  "
                            f"{r.get('label')}"
                        )
                return

            ml_pred = getattr(args, "ml_prediction", None) or getattr(args, "ml_live_metrics", None)
            payload = decide_from_request(
                {
                    "event_id": args.event_id,
                    "use_ml_v34": bool(getattr(args, "use_ml_v34", False)),
                    "work_dir": str(args.work_dir) if getattr(args, "work_dir", None) else None,
                    "open_pack": str(args.open_pack) if getattr(args, "open_pack", None) else None,
                    "require_ops_for_go": bool(getattr(args, "require_ops_for_go", False)),
                    "policy_id": getattr(args, "policy", None),
                    "ml_prediction": str(ml_pred) if ml_pred is not None else None,
                    "allow_ml_live_in_fusion": bool(
                        getattr(args, "allow_ml_live_in_fusion", False)
                    ),
                    "ml_live_trusted": not bool(getattr(args, "ml_live_untrusted", False)),
                    "channel": "cli",
                },
                base=Path.cwd(),
            )
            out = getattr(args, "output", None)
            if out:
                Path(out).parent.mkdir(parents=True, exist_ok=True)
                Path(out).write_text(_json.dumps(payload, indent=2, default=str), encoding="utf-8")
            if as_json:
                # --explain is a no-op with --json (pure card JSON only)
                print_json(payload)
            elif getattr(args, "explain", False):
                from .product.operator_ux import format_abstain_plain
                from .product.teach_path import format_decide_explain

                if str(payload.get("decision", "")).upper() == "ABSTAIN":
                    print(format_abstain_plain(payload), end="")
                print(format_decide_explain(payload), end="")
                if out:
                    print(f"wrote: {out}")
            else:
                print(f"decision: {payload.get('decision')}")
                conf = payload.get("confidence_pred")
                conf_s = f"{float(conf):.3f}" if isinstance(conf, (int, float)) else "—"
                print(f"confidence_pred: {conf_s} ({payload.get('confidence_pred_label')})")
                policy_id = payload.get("policy_id") or (payload.get("audit") or {}).get(
                    "policy_id"
                )
                print(f"policy: {policy_id}")
                if not getattr(args, "policy", None) and str(policy_id or "") in (
                    "default",
                    "",
                    "None",
                ):
                    print(
                        "policy note: using 'default' (not field_ops). "
                        "Field silence rails: --policy field_ops · list: --list-policies"
                    )
                print(f"system_reliability_pass: {payload.get('system_reliability_pass')}")
                print(f"latency_ms: {payload.get('latency_ms')}")
                print("reasons:", "; ".join((payload.get("reasons") or [])[:12]))
                # Plain language when silent — operator must not think it is broken
                if str(payload.get("decision", "")).upper() == "ABSTAIN":
                    print(
                        "nota: ABSTAIN = el producto se calla a propósito "
                        "(faltan fuentes). No es un bug. "
                        "Detalle: python -m wildfire_front operator explain-abstain"
                    )
                if out:
                    print(f"wrote: {out}")
            return

        if args.command == "ml":
            raise SystemExit(run_ml(args))

        if args.command == "multihorizon":
            raise SystemExit(run_multihorizon(args))

        if args.command == "teach":
            raise SystemExit(run_teach(args))

        if args.command == "show":
            raise SystemExit(run_show(args))

        if args.command == "demo-third-party":
            raise SystemExit(run_demo_third_party(args))

        if args.command == "dry-run-h3":
            raise SystemExit(run_dry_run_h3(args))

        if args.command == "operator":
            raise SystemExit(run_operator(args))

        if args.command == "serve-decide":
            from .product.api_server import serve as serve_decide_api

            serve_decide_api(
                host=str(args.host),
                port=int(args.port),
                base_dir=getattr(args, "base_dir", None),
                verbose=verbose,
            )
            return

        if args.command == "export-acta":
            import json as _json

            from .product.forensics import write_forensic_bundle

            card_path: Path | None = getattr(args, "card", None)
            work = getattr(args, "work_dir", None)
            if card_path is None and work is not None:
                card_path = Path(work) / "outbox" / "fire_decision_card.json"
            if card_path is None or not Path(card_path).is_file():
                detail = (
                    f"card not found: {card_path}"
                    if card_path is not None
                    else "no --card and no --work-dir"
                )
                print_error(
                    f"export-acta requires a Decision Card ({detail})",
                    hint=(
                        "wildfire-front export-acta --card path/to/fire_decision_card.json\n"
                        "  or: wildfire-front export-acta --work-dir outputs/incidents/IF1\n"
                        "  first: wildfire-front decide --policy field_ops --output card.json\n"
                        "  incident outbox card is written by incident update/watch"
                    ),
                )
                raise SystemExit(2)
            card = _json.loads(Path(card_path).read_text(encoding="utf-8"))
            out_dir = getattr(args, "output", None)
            if out_dir is None:
                out_dir = Path(card_path).parent
            paths = write_forensic_bundle(
                out_dir,
                card,
                require_ops_for_go=bool(getattr(args, "require_ops_for_go", False)),
                operator=getattr(args, "operator", None),
            )
            if as_json:
                print_json(paths)
            else:
                print("forensic bundle written:")
                for k, v in paths.items():
                    print(f"  {k}: {v}")
            return

        if args.command == "replay-decide":
            import json as _json

            from .product.forensics import load_and_replay_bundle, replay_decision

            bundle = getattr(args, "bundle", None)
            sources = getattr(args, "sources", None)
            work = getattr(args, "work_dir", None)
            if sources is not None:
                src_path = Path(sources)
                if not src_path.is_file():
                    print_error(
                        f"replay sources not found: {src_path}",
                        hint="wildfire-front replay-decide --sources path/to/replay_sources.json",
                    )
                    raise SystemExit(2)
                src = _json.loads(src_path.read_text(encoding="utf-8"))
                result = replay_decision(src, base=Path.cwd())
            else:
                if bundle is None and work is not None:
                    bundle = Path(work) / "outbox"
                if bundle is None:
                    print_error(
                        "replay-decide requires --bundle, --sources, or --work-dir",
                        hint=(
                            "wildfire-front replay-decide --bundle DIR\n"
                            "  wildfire-front replay-decide --sources replay_sources.json\n"
                            "  wildfire-front replay-decide --work-dir outputs/incidents/IF1\n"
                            "  first: export-acta writes replay_sources.json next to the card"
                        ),
                    )
                    raise SystemExit(2)
                result = load_and_replay_bundle(bundle, base=Path.cwd())
            if as_json:
                # omit full nested card if quiet? keep full for audit
                print_json(result)
            else:
                ok = result.get("replay_ok")
                print(f"replay_ok: {ok}")
                print(
                    f"decision: expected={result.get('expected_decision')} "
                    f"got={result.get('got_decision')} match={result.get('match_decision')}"
                )
                print(f"output_hash match: {result.get('match_output_hash')}")
                if not ok:
                    print_error(
                        "forensic replay mismatch (replay_ok=false)",
                        hint=(
                            "re-export acta from the same card, or inspect "
                            "match_decision / match_output_hash above"
                        ),
                    )
                    raise SystemExit(2)
            return

        if args.command == "incident":
            from .incident import process_incident_once, run_incident_watch
            from .incident.doctor import (
                config_snapshot,
                doctor_incident,
                read_incident_status,
            )

            # Bare `incident` → field hub (exit 0)
            if getattr(args, "incident_command", None) is None:
                raise SystemExit(run_incident_hub(args))

            if args.incident_command == "doctor":
                report = doctor_incident(
                    inbox=args.inbox,
                    work_dir=args.work_dir,
                    masks_dir=args.masks,
                    event_id=args.event_id,
                )
                print_doctor_report(report, as_json=as_json)
                if not report.get("ok"):
                    raise SystemExit(1)
                return

            if args.incident_command == "status":
                report = read_incident_status(args.work_dir)
                report = enrich_incident_summary(report)
                print_status_report(report, as_json=as_json, verbose=verbose)
                if report.get("status") == "error":
                    raise SystemExit(1)
                if report.get("status") == "no_state":
                    raise SystemExit(2)
                return

            config = _incident_config_from_args(args)

            if args.incident_command == "update":
                summary = process_incident_once(config, force=bool(args.force))
                summary = enrich_incident_summary(summary)
                summary["config"] = config_snapshot(config)
                print_incident_report(
                    summary, as_json=as_json, verbose=verbose, title="incident update"
                )
                if summary.get("status") == "error":
                    raise SystemExit(1)
                return

            if args.incident_command == "watch":

                def _on_update(s: dict[str, Any]) -> None:
                    if quiet:
                        return
                    print_watch_line(s, verbose=verbose)

                result = run_incident_watch(
                    config,
                    interval_s=args.interval_s,
                    max_iterations=args.max_iterations,
                    max_frames=args.max_frames,
                    once=bool(args.once),
                    stop_on_error=bool(args.stop_on_error),
                    on_update=_on_update,
                    use_lock=not bool(getattr(args, "no_lock", False)),
                )
                last = enrich_incident_summary(result.get("last") or {})
                last["config"] = config_snapshot(config)
                last["watch"] = {
                    "mode": result.get("mode"),
                    "iterations": result.get("iterations"),
                    "interrupted": bool(
                        last.get("interrupted") or result.get("last", {}).get("interrupted")
                    ),
                }
                # Full final report (human or json)
                if as_json:
                    print_json(
                        {
                            "product": "incident_runtime_v1",
                            "command": "watch",
                            "mode": result.get("mode"),
                            "iterations": result.get("iterations"),
                            "last": last,
                            "config": config_snapshot(config),
                        }
                    )
                else:
                    print_incident_report(
                        last,
                        as_json=False,
                        verbose=verbose,
                        title=f"incident watch ({result.get('mode')}, {result.get('iterations')} iter)",
                    )
                if last.get("status") == "error":
                    raise SystemExit(1)
                return

            print_error(f"unknown incident subcommand: {args.incident_command}")
            raise SystemExit(2)

        print_error(f"unknown command: {getattr(args, 'command', None)}")
        raise SystemExit(2)

    except ValueError as exc:
        print_error(str(exc), hint="see wildfire-front COMMAND --help")
        raise SystemExit(2) from exc
    except FileNotFoundError as exc:
        print_error(str(exc))
        raise SystemExit(2) from exc
