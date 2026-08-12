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

  # Decision Card → forensic acta
  wildfire-front decide --work-dir outputs/incidents/IF1 \
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
        manifest = output / "ingest_manifest.csv"
        raise ValueError(
            f"no accepted observations; inspect {manifest} for reject reasons. "
            "Example: wildfire-front ingest-geotiff "
            "--images artifacts/tobarra_reprojected_lwir "
            "--masks artifacts/tobarra_lwir_masks "
            "--sensor-id lwir_drone --estimated-error-m 2 "
            "--event-id tobarra_20240802 --output outputs/tobarra"
        )
    resolution = next(
        (item.resolution_m for item in result.observations if item.resolution_m is not None),
        None,
    )
    if resolution is None:
        raise ValueError(
            "accepted observations do not have metric resolution; "
            "GeoTIFFs must use a projected CRS in metres "
            "(see docs/GEOTIFF_INPUT_CONTRACT.md). "
            "Example: gdalwarp -t_srs EPSG:25830 in.tif out_projected.tif"
        )

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


# ─ argparse builders ──────────────────────────────────────────────────────────


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
            "operator packs. Not validated tactical dispatch."
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

    # ─ demo ───────────────────────────────────────────────────────────────────
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

    # ─ ingest-geotiff ─────────────────────────────────────────────────────────
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

    # ─ incident ───────────────────────────────────────────────────────────────
    register_incident_subcommands(commands, add_global_flags=_add_global_flags)

    # ─ decide (Fire Decision Card) ────────────────────────────────────────────
    decide = commands.add_parser(
        "decide",
        help="Build Fire Decision Card (GO/HOLD/ABSTAIN + metrics fusion)",
        description=(
            "Fuse optional ML / ops / open-CEMS metrics into a decision card "
            "with confidence and audit hashes. Empty sources → ABSTAIN."
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
        help="Allow live ML weight in multi-source fusion (default off until U1)",
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
    _add_global_flags(decide)

    # ─ serve-decide (minimal HTTP API) ────────────────────────────────────────
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

    # ─ export-acta (forensic bundle) ──────────────────────────────────────────
    acta = commands.add_parser(
        "export-acta",
        help="Write forensic acta + radio-bridge + replay sources from a Decision Card",
        description=(
            "Paid-value audit package: fire_decision_acta.md, fire_decision_radio.txt, "
            "replay_sources.json, forensic_manifest.json. Not a court PDF."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "example:\n"
            "  wildfire-front decide --work-dir outputs/incidents/IF1 \\\n"
            "    --output outputs/incidents/IF1/outbox/fire_decision_card.json\n"
            "  wildfire-front export-acta --work-dir outputs/incidents/IF1\n"
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

    # ─ replay-decide (forensic verify) ────────────────────────────────────────
    replay = commands.add_parser(
        "replay-decide",
        help="Rebuild Decision Card from forensic sources and verify hashes",
        description=(
            "Forensic replay: load replay_sources.json (or card) and verify "
            "output_hash + decision match. Empty mismatch → replay_ok=false."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=("example:\n  wildfire-front replay-decide --work-dir outputs/incidents/IF1\n"),
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


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    as_json = bool(getattr(args, "json", False))
    verbose = bool(getattr(args, "verbose", False))
    quiet = bool(getattr(args, "quiet", False))

    try:
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
                print_json(payload)
            else:
                print(f"decision: {payload.get('decision')}")
                conf = payload.get("confidence_pred")
                conf_s = f"{float(conf):.3f}" if isinstance(conf, (int, float)) else "—"
                print(f"confidence_pred: {conf_s} ({payload.get('confidence_pred_label')})")
                print(
                    f"policy: {payload.get('policy_id') or (payload.get('audit') or {}).get('policy_id')}"
                )
                print(f"system_reliability_pass: {payload.get('system_reliability_pass')}")
                print(f"latency_ms: {payload.get('latency_ms')}")
                print("reasons:", "; ".join((payload.get("reasons") or [])[:12]))
                if out:
                    print(f"wrote: {out}")
            return

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
                print_error(
                    "export-acta requires --card PATH or --work-dir with "
                    "outbox/fire_decision_card.json",
                    hint=(
                        "run decide first, then: "
                        "wildfire-front export-acta --work-dir outputs/incidents/IF1"
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
                src = _json.loads(Path(sources).read_text(encoding="utf-8"))
                result = replay_decision(src, base=Path.cwd())
            else:
                if bundle is None and work is not None:
                    bundle = Path(work) / "outbox"
                if bundle is None:
                    print_error(
                        "replay-decide requires --bundle, --sources, or --work-dir",
                        hint=(
                            "example: wildfire-front replay-decide --work-dir outputs/incidents/IF1"
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
                    raise SystemExit(2)
            return

        if args.command == "incident":
            from .incident import process_incident_once, run_incident_watch
            from .incident.doctor import (
                config_snapshot,
                doctor_incident,
                read_incident_status,
            )

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
