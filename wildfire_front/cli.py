"""WildfireFrontDynamics command-line interface.

Human-readable by default; pass ``--json`` for machine-readable output.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from . import __version__
from .cli_report import (
    enrich_incident_summary,
    print_demo_report,
    print_doctor_report,
    print_error,
    print_ingest_report,
    print_incident_report,
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


def _add_incident_io_args(p: argparse.ArgumentParser, *, require_work: bool = True) -> None:
    io = p.add_argument_group("paths")
    io.add_argument(
        "--inbox",
        type=Path,
        required=True,
        metavar="DIR",
        help="Folder receiving new LWIR GeoTIFFs (drop zone)",
    )
    io.add_argument(
        "--work-dir",
        type=Path,
        required=require_work,
        metavar="DIR",
        help="Incident workspace: stage/ + outbox/ (created if missing)",
    )
    io.add_argument(
        "--masks",
        type=Path,
        metavar="DIR",
        help="Optional external masks ({stem}.tif or {stem}_mask.tif). Disables MAD.",
    )


def _add_incident_identity_args(p: argparse.ArgumentParser) -> None:
    idg = p.add_argument_group("identity")
    idg.add_argument(
        "--event-id",
        default="incident",
        help="Incident / fire id (default: incident)",
    )
    idg.add_argument(
        "--sensor-id",
        default="lwir_drone",
        help="Sensor id for provenance (default: lwir_drone)",
    )
    idg.add_argument(
        "--estimated-error-m",
        type=float,
        default=2.0,
        metavar="M",
        help="Declared one-sigma geolocation error in metres (default: 2)",
    )


def _add_incident_segmentation_args(p: argparse.ArgumentParser) -> None:
    seg = p.add_argument_group("segmentation")
    seg.add_argument("--band", type=int, default=1, help="Raster band index (default: 1)")
    seg.add_argument(
        "--threshold",
        type=float,
        metavar="VAL",
        help="Fixed radiometric threshold (mutually exclusive with MAD)",
    )
    seg.add_argument(
        "--mad-z",
        type=float,
        default=6.0,
        metavar="Z",
        help="MAD z-score when no --masks (default: 6)",
    )
    seg.add_argument(
        "--no-mad",
        action="store_true",
        help="Disable MAD (requires --masks or --threshold)",
    )
    seg.add_argument(
        "--respect-alpha",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Ignore transparent pixels when thresholding (default: true)",
    )
    seg.add_argument(
        "--min-component-pixels",
        type=int,
        default=200,
        metavar="N",
        help="Drop flecks smaller than N pixels (default: 200)",
    )
    seg.add_argument(
        "--scientific-clean",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Morphological clean + main-front filter (default: true)",
    )
    seg.add_argument(
        "--max-components",
        type=int,
        default=5,
        metavar="N",
        help="Keep largest N components after clean (default: 5)",
    )
    seg.add_argument(
        "--morph-close-pixels",
        type=int,
        default=3,
        metavar="N",
        help="Morphological close radius in pixels (default: 3)",
    )
    seg.add_argument(
        "--min-component-area-m2",
        type=float,
        default=100.0,
        metavar="M2",
        help="Min component area in m² (default: 100)",
    )


def _add_incident_anchor_args(p: argparse.ArgumentParser) -> None:
    anc = p.add_argument_group("operational anchor (optional INFOCAM-style)")
    anc.add_argument("--ref-name", type=str, default=None, help="Anchor name (e.g. INFOCAM Tobarra)")
    anc.add_argument(
        "--ref-vp-m-min",
        type=float,
        default=None,
        metavar="M_MIN",
        help="Reference rate of spread (m/min) for grade ratio",
    )
    anc.add_argument(
        "--ref-area-ha",
        type=float,
        default=None,
        metavar="HA",
        help="Reference burned area (ha)",
    )


def _add_incident_runtime_args(p: argparse.ArgumentParser) -> None:
    rt = p.add_argument_group("runtime")
    rt.add_argument(
        "--min-file-age-s",
        type=float,
        default=0.5,
        metavar="S",
        help="Ignore files newer than S seconds; also requires size-stable polls (default: 0.5)",
    )


def _add_all_incident_process_args(p: argparse.ArgumentParser, *, require_work: bool = True) -> None:
    _add_incident_io_args(p, require_work=require_work)
    _add_incident_identity_args(p)
    _add_incident_segmentation_args(p)
    _add_incident_anchor_args(p)
    _add_incident_runtime_args(p)
    _add_global_flags(p)


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
    ig.add_argument("--images", type=Path, required=True, metavar="DIR", help="GeoTIFF images folder")
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
    incident = commands.add_parser(
        "incident",
        help="Live incident runtime (watch / update / status / doctor)",
        description=(
            "incident_runtime_v1 — stage LWIR frames as they land, recompute "
            "observed front + ROS + emergency envelope, publish operator outbox.\n\n"
            "NOT validated tactical dispatch. Geometry-first observed products only."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "subcommands:\n"
            "  doctor   Pre-flight: timestamps, CRS, masks, inbox health\n"
            "  update   Process inbox once → outbox\n"
            "  watch    Poll inbox and update continuously\n"
            "  status   Read last outbox state without processing\n"
        ),
    )
    inc_subs = incident.add_subparsers(
        dest="incident_command", required=True, metavar="SUBCOMMAND"
    )

    # doctor
    doc = inc_subs.add_parser(
        "doctor",
        help="Pre-flight checks before a real incident",
        description="Validate inbox naming, CRS sample, masks pairing, work-dir.",
    )
    doc.add_argument("--inbox", type=Path, required=True, metavar="DIR")
    doc.add_argument("--work-dir", type=Path, default=None, metavar="DIR")
    doc.add_argument("--masks", type=Path, default=None, metavar="DIR")
    doc.add_argument("--event-id", default="incident")
    _add_global_flags(doc)

    # update
    upd = inc_subs.add_parser(
        "update",
        help="Process inbox once (stage + recompute outbox)",
        description="Stage new stable GeoTIFFs and rebuild operator products.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _add_all_incident_process_args(upd)
    upd.add_argument(
        "--force",
        action="store_true",
        help="Recompute even if no new frames (refresh products)",
    )

    # watch
    wat = inc_subs.add_parser(
        "watch",
        help="Poll inbox and update outbox continuously",
        description=(
            "Live loop: detect new GeoTIFFs → stage → recompute → publish. "
            "Ctrl+C stops cleanly. Prints status lines on stderr; final report on stdout."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _add_all_incident_process_args(wat)
    loop = wat.add_argument_group("watch loop")
    loop.add_argument(
        "--interval-s",
        type=float,
        default=2.0,
        metavar="S",
        help="Poll interval seconds (default: 2)",
    )
    loop.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        metavar="N",
        help="Stop after N poll loops (default: forever)",
    )
    loop.add_argument(
        "--max-frames",
        type=int,
        default=None,
        metavar="N",
        help="Stop once staged frame count reaches N",
    )
    loop.add_argument(
        "--once",
        action="store_true",
        help="Single forced update then exit (like update --force)",
    )
    loop.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Exit the loop if pipeline returns error",
    )
    loop.add_argument(
        "--no-lock",
        action="store_true",
        help="Do not acquire exclusive work-dir lock (not recommended)",
    )

    # status
    st = inc_subs.add_parser(
        "status",
        help="Show last incident state without processing",
        description="Read outbox/incident_state.json + operational metrics.",
    )
    st.add_argument(
        "--work-dir",
        type=Path,
        required=True,
        metavar="DIR",
        help="Incident workspace containing outbox/",
    )
    _add_global_flags(st)

    # ── decide (Fire Decision Card) ─────────────────────────────────────
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
        help="Include clm_ensemble_v34 manifest metrics",
    )
    decide.add_argument(
        "--require-ops-for-go",
        action="store_true",
        help="Never GO without thermal ops source",
    )
    decide.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write card JSON to this path",
    )
    _add_global_flags(decide)

    return parser


def _incident_config_from_args(args: argparse.Namespace):
    from .incident import IncidentConfig

    mad_z = None if getattr(args, "no_mad", False) else getattr(args, "mad_z", 6.0)
    if getattr(args, "threshold", None) is not None:
        mad_z = None
    if mad_z is None and getattr(args, "threshold", None) is None and getattr(args, "masks", None) is None:
        raise ValueError("--no-mad requires --masks or --threshold (or omit --no-mad)")
    return IncidentConfig(
        event_id=args.event_id,
        sensor_id=args.sensor_id,
        estimated_error_m=args.estimated_error_m,
        inbox=args.inbox,
        work_dir=args.work_dir,
        masks_dir=getattr(args, "masks", None),
        band=getattr(args, "band", 1),
        threshold=getattr(args, "threshold", None),
        mad_z=mad_z,
        respect_alpha=bool(getattr(args, "respect_alpha", True)),
        min_component_pixels=getattr(args, "min_component_pixels", 200),
        scientific_clean=bool(getattr(args, "scientific_clean", True)),
        max_components=getattr(args, "max_components", 5),
        morph_close_pixels=getattr(args, "morph_close_pixels", 3),
        min_component_area_m2=getattr(args, "min_component_area_m2", 100.0),
        ref_name=getattr(args, "ref_name", None),
        ref_vp_m_min=getattr(args, "ref_vp_m_min", None),
        ref_area_ha=getattr(args, "ref_area_ha", None),
        min_file_age_s=getattr(args, "min_file_age_s", 0.5),
    )


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
                write_operational=bool(args.operational) or ref is not None or bool(args.scientific_clean),
            )
            print_ingest_report(
                args.output, metrics, as_json=as_json, event_id=args.event_id
            )
            return

        if args.command == "decide":
            from .product.confidence import build_decision_card
            import json as _json

            ml_m = ops_m = open_m = None
            if getattr(args, "use_ml_v34", False):
                man = Path("models/clm_ensemble/manifest.json")
                if man.is_file():
                    ml_m = (_json.loads(man.read_text(encoding="utf-8"))).get("metrics")
            if getattr(args, "work_dir", None):
                st_path = Path(args.work_dir) / "outbox" / "incident_state.json"
                if st_path.is_file():
                    st = _json.loads(st_path.read_text(encoding="utf-8"))
                    ops_m = {
                        "quality_grade": st.get("quality_grade"),
                        "primary_ros_m_min": st.get("primary_ros_m_min"),
                        "n_frames_staged": st.get("n_frames_staged")
                        or st.get("n_frames_seen"),
                        "area_ha_max": st.get("area_ha_max"),
                        "speed_vs_ref_ratio": st.get("speed_vs_ref_ratio"),
                    }
            if getattr(args, "open_pack", None):
                scp = Path(args.open_pack) / "scorecard_pista_b.json"
                if scp.is_file():
                    sc = _json.loads(scp.read_text(encoding="utf-8"))
                    open_m = {
                        "max_area_ha": sc.get("max_area_ha"),
                        "n_timeline_steps": sc.get("n_timeline_steps"),
                        "activation": sc.get("activation"),
                        "O2_cems_delineation": sc.get("O2_cems_delineation"),
                    }
            card = build_decision_card(
                args.event_id,
                ml_metrics=ml_m,
                ops_metrics=ops_m,
                open_metrics=open_m,
                require_ops_for_go=bool(getattr(args, "require_ops_for_go", False)),
            )
            payload = card.to_dict()
            out = getattr(args, "output", None)
            if out:
                Path(out).parent.mkdir(parents=True, exist_ok=True)
                Path(out).write_text(
                    _json.dumps(payload, indent=2, default=str), encoding="utf-8"
                )
            if as_json:
                print_json(payload)
            else:
                print(f"decision: {card.decision.value}")
                print(
                    f"confidence_pred: {card.confidence_pred:.3f} ({card.confidence_pred_label})"
                )
                print(f"system_reliability_pass: {card.system_reliability_pass}")
                print("reasons:", "; ".join(card.reasons[:12]))
                if out:
                    print(f"wrote: {out}")
            return

        if args.command == "incident":
            from .incident.doctor import (
                config_snapshot,
                doctor_incident,
                read_incident_status,
            )
            from .incident import process_incident_once, run_incident_watch

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
                    "interrupted": bool(last.get("interrupted") or result.get("last", {}).get("interrupted")),
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
