"""Incident CLI argparse helpers (extracted from cli god-file).

Argument groups and config mapping for ``wildfire-front incident *``.
Wired into ``wildfire_front.cli.build_parser`` / ``main`` so
``python -m wildfire_front`` is unchanged.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .incident import IncidentConfig

AddGlobalFlags = Callable[[argparse.ArgumentParser], None]


def add_incident_io_args(p: argparse.ArgumentParser, *, require_work: bool = True) -> None:
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


def add_incident_identity_args(p: argparse.ArgumentParser) -> None:
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


def add_incident_segmentation_args(p: argparse.ArgumentParser) -> None:
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


def add_incident_anchor_args(p: argparse.ArgumentParser) -> None:
    anc = p.add_argument_group("operational anchor (optional INFOCAM-style)")
    anc.add_argument(
        "--ref-name", type=str, default=None, help="Anchor name (e.g. INFOCAM Tobarra)"
    )
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


def add_incident_runtime_args(p: argparse.ArgumentParser) -> None:
    rt = p.add_argument_group("runtime")
    rt.add_argument(
        "--min-file-age-s",
        type=float,
        default=0.5,
        metavar="S",
        help="Ignore files newer than S seconds; also requires size-stable polls (default: 0.5)",
    )
    fdc = p.add_argument_group("decision card (outbox)")
    fdc.add_argument(
        "--open-pack",
        type=Path,
        default=None,
        metavar="DIR",
        help="Optional open CEMS pack dir fused into Fire Decision Card",
    )
    fdc.add_argument(
        "--no-ml-metrics",
        action="store_true",
        help="Do not attach ML v34 holdout metrics to the Decision Card",
    )
    fdc.add_argument(
        "--allow-go-without-ops",
        action="store_true",
        help="Allow GO without thermal ops (default: require ops for GO)",
    )
    fdc.add_argument(
        "--policy",
        default="field_ops",
        metavar="ID",
        help="Decision policy for outbox card (default: field_ops). See config/decision_policies.json",
    )


def add_all_incident_process_args(
    p: argparse.ArgumentParser,
    *,
    require_work: bool = True,
    add_global_flags: AddGlobalFlags | None = None,
) -> None:
    """Register path/identity/seg/anchor/runtime groups; optional global flags hook."""
    add_incident_io_args(p, require_work=require_work)
    add_incident_identity_args(p)
    add_incident_segmentation_args(p)
    add_incident_anchor_args(p)
    add_incident_runtime_args(p)
    if add_global_flags is not None:
        add_global_flags(p)


def incident_config_from_args(args: argparse.Namespace) -> IncidentConfig:
    from .incident import IncidentConfig

    mad_z = None if getattr(args, "no_mad", False) else getattr(args, "mad_z", 6.0)
    if getattr(args, "threshold", None) is not None:
        mad_z = None
    if (
        mad_z is None
        and getattr(args, "threshold", None) is None
        and getattr(args, "masks", None) is None
    ):
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
        open_pack_dir=getattr(args, "open_pack", None),
        include_ml_metrics=not bool(getattr(args, "no_ml_metrics", False)),
        require_ops_for_go=not bool(getattr(args, "allow_go_without_ops", False)),
        decision_policy=str(getattr(args, "policy", None) or "field_ops"),
        min_file_age_s=getattr(args, "min_file_age_s", 0.5),
    )


def register_incident_subcommands(
    commands: argparse._SubParsersAction,
    *,
    add_global_flags: AddGlobalFlags,
) -> argparse.ArgumentParser:
    """Attach ``incident`` command and its subparsers to the root CLI."""
    incident = commands.add_parser(
        "incident",
        help="Live incident runtime (watch / update / status / doctor; bare → hub)",
        description=(
            "incident_runtime_v1 — stage LWIR frames as they land, recompute "
            "observed front + ROS + emergency envelope, publish operator outbox.\n\n"
            "NOT validated tactical dispatch. Geometry-first observed products only.\n"
            "Bare `incident` (no SUBCOMMAND) prints a field hub (exit 0) — not an error."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "subcommands:\n"
            "  doctor   Pre-flight: timestamps, CRS, masks, inbox health\n"
            "  update   Process inbox once → outbox\n"
            "  watch    Poll inbox and update continuously\n"
            "  status   Read last outbox state without processing\n"
            "\n"
            "examples:\n"
            "  wildfire-front incident\n"
            "  wildfire-front incident doctor --inbox D:/drops\n"
            "  wildfire-front incident update --inbox D:/drops --work-dir outputs/incidents/IF1\n"
            "  wildfire-front incident status --work-dir outputs/incidents/IF1\n"
        ),
    )
    # Parent flags so `incident --json` works without a subcommand (hub path).
    add_global_flags(incident)
    # Bare `incident` → field hub (required=False).
    inc_subs = incident.add_subparsers(
        dest="incident_command", required=False, metavar="SUBCOMMAND"
    )

    doc = inc_subs.add_parser(
        "doctor",
        help="Pre-flight checks before a real incident",
        description="Validate inbox naming, CRS sample, masks pairing, work-dir.",
    )
    doc.add_argument("--inbox", type=Path, required=True, metavar="DIR")
    doc.add_argument("--work-dir", type=Path, default=None, metavar="DIR")
    doc.add_argument("--masks", type=Path, default=None, metavar="DIR")
    doc.add_argument("--event-id", default="incident")
    add_global_flags(doc)

    upd = inc_subs.add_parser(
        "update",
        help="Process inbox once (stage + recompute outbox)",
        description="Stage new stable GeoTIFFs and rebuild operator products.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_all_incident_process_args(upd, add_global_flags=add_global_flags)
    upd.add_argument(
        "--force",
        action="store_true",
        help="Recompute even if no new frames (refresh products)",
    )

    wat = inc_subs.add_parser(
        "watch",
        help="Poll inbox and update outbox continuously",
        description=(
            "Live loop: detect new GeoTIFFs → stage → recompute → publish. "
            "Ctrl+C stops cleanly. Prints status lines on stderr; final report on stdout."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_all_incident_process_args(wat, add_global_flags=add_global_flags)
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
    add_global_flags(st)

    return incident
