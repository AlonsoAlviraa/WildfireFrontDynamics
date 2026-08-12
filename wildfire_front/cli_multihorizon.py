"""CLI: multi-horizon field_ops forecasts (1h / 3h / 5h / 12h / 24h).

Commercial / operational surface — not ML next-day mask IoU.
Registered from ``wildfire_front.cli.build_parser``.

Supports isotropic / anisotropic / hybrid methods, GeoJSON export,
re-init from multipass frame, and optional weather wind boost.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .cli_report import print_json
from .multihorizon_fieldops import (
    DEFAULT_LEAD_TIMES_H,
    METHOD_ANISOTROPIC,
    METHOD_HYBRID,
    METHOD_ISOTROPIC,
    METHOD_REINIT,
    MultiHorizonError,
    MultiHorizonForecast,
    build_anisotropic_multihorizon,
    build_hybrid_multihorizon,
    build_multihorizon_forecast,
    format_multihorizon_human,
    from_arrival_ros_result,
    from_psb_duration,
    load_weather_json,
    multihorizon_to_geojson,
    multipass_envelope_scorecard,
    reinit_multihorizon_from_frame,
)

AddGlobalFlags = Callable[[argparse.ArgumentParser], None]


def register_multihorizon_commands(
    commands: argparse._SubParsersAction,
    *,
    add_global_flags: AddGlobalFlags,
) -> None:
    """Attach top-level ``multihorizon`` command."""
    mh = commands.add_parser(
        "multihorizon",
        help="Multi-horizon field_ops forecast (1/3/5/12/24 h) from ROS m/min",
        description=(
            "Build multi-lead-time field_ops envelopes from scalar / sector ROS [m/min]. "
            "Methods: isotropic | anisotropic | hybrid. Not ML next-day IoU; fusion OFF."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  wildfire-front multihorizon --ros-m-min 7\n"
            "  wildfire-front multihorizon --ros-m-min 7 --method anisotropic --json\n"
            "  wildfire-front multihorizon --ros-m-min 6.14 --method hybrid --geojson out.geojson\n"
            "  wildfire-front multihorizon --tobarra-vp --method anisotropic\n"
            "  wildfire-front multihorizon --from-arrival board.json --method anisotropic\n"
            "  wildfire-front multihorizon --ros-m-min 6 --reinit-frame frame_03\n"
            "  wildfire-front multihorizon --ros-m-min 6 --weather weather.json\n"
        ),
    )
    src = mh.add_argument_group("ROS source (pick one)")
    src.add_argument(
        "--ros-m-min",
        type=float,
        default=None,
        metavar="V",
        help="Rate of spread [m/min] (geometry / ops — not mask IoU)",
    )
    src.add_argument(
        "--tobarra-vp",
        action="store_true",
        help="Use Tobarra INFOCAM Vp anchor 7 m/min (cite-only demo)",
    )
    src.add_argument(
        "--from-arrival",
        type=Path,
        default=None,
        metavar="JSON",
        help="JSON with ros_median_m_min (arrival_gradient / S4 board)",
    )
    src.add_argument(
        "--psb-duration-s",
        type=float,
        default=None,
        metavar="S",
        help="PSB total duration seconds (with --psb-area-ha → equiv isotropic ROS)",
    )
    src.add_argument(
        "--psb-area-ha",
        type=float,
        default=None,
        metavar="HA",
        help="PSB final area ha (pair with --psb-duration-s)",
    )
    mh.add_argument(
        "--method",
        type=str,
        default=METHOD_ISOTROPIC,
        choices=[
            METHOD_ISOTROPIC,
            METHOD_ANISOTROPIC,
            METHOD_HYBRID,
            "isotropic",
            "anisotropic",
            "hybrid",
        ],
        help=(
            "Forecast method (default isotropic). "
            "Aliases: isotropic|anisotropic|hybrid → full method ids."
        ),
    )
    mh.add_argument(
        "--lead-times",
        type=str,
        default=None,
        metavar="H,H,...",
        help=f"Comma-separated hours (default: {','.join(str(x) for x in DEFAULT_LEAD_TIMES_H)})",
    )
    mh.add_argument(
        "--ros-source",
        type=str,
        default=None,
        help="Override ros_source label in output",
    )
    mh.add_argument(
        "--head-bearing-deg",
        type=float,
        default=None,
        help="Head expansion bearing (deg, 0=N) for anisotropic/hybrid",
    )
    mh.add_argument(
        "--sector-head",
        type=float,
        default=None,
        help="Override head ROS m/min (else primary × 1.0)",
    )
    mh.add_argument(
        "--sector-flank",
        type=float,
        default=None,
        help="Override flank ROS m/min (else primary × 0.5)",
    )
    mh.add_argument(
        "--sector-rear",
        type=float,
        default=None,
        help="Override rear ROS m/min (else primary × 0.3)",
    )
    mh.add_argument(
        "--weather",
        type=Path,
        default=None,
        metavar="JSON",
        help="Optional weather JSON (wind_10m_ms, wind_from_deg) for PR13 boost",
    )
    mh.add_argument(
        "--no-wind",
        action="store_true",
        help="Disable wind boost even if weather present",
    )
    mh.add_argument(
        "--reinit-frame",
        type=str,
        default=None,
        metavar="FRAME_ID",
        help="Re-init path (PR9): stamp reinit_from_frame; never ML mask as 1h truth",
    )
    mh.add_argument(
        "--reinit-timestamp",
        type=str,
        default=None,
        help="Optional UTC timestamp for reinit frame",
    )
    mh.add_argument(
        "--geojson",
        type=Path,
        default=None,
        metavar="PATH",
        help="Write horizon rings GeoJSON with honesty properties (PR10)",
    )
    mh.add_argument(
        "--center-xy",
        type=str,
        default="0,0",
        metavar="X,Y",
        help="Local metric center for GeoJSON rings (default 0,0)",
    )
    mh.add_argument(
        "--scorecard",
        type=Path,
        default=None,
        metavar="PATH",
        help="Write multipass envelope scorecard JSON (ops metrics, not ML IoU)",
    )
    mh.add_argument(
        "--observed-advance-m",
        type=float,
        default=None,
        help="Observed multipass advance (m) for scorecard",
    )
    mh.add_argument(
        "--multipass-span-s",
        type=float,
        default=None,
        help="Multipass temporal span seconds (PARTIAL if short)",
    )
    mh.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        metavar="PATH",
        help="Write JSON card to path",
    )
    add_global_flags(mh)


def _parse_lead_times(raw: str | None) -> list[float] | None:
    if raw is None or not str(raw).strip():
        return None
    out: list[float] = []
    for part in str(raw).split(","):
        part = part.strip()
        if not part:
            continue
        out.append(float(part))
    return out or None


def _resolve_method(raw: str | None) -> str:
    m = (raw or METHOD_ISOTROPIC).strip().lower()
    aliases = {
        "isotropic": METHOD_ISOTROPIC,
        "isotropic_ros_buffer_v1": METHOD_ISOTROPIC,
        "anisotropic": METHOD_ANISOTROPIC,
        "anisotropic_ros_buffer_v1": METHOD_ANISOTROPIC,
        "hybrid": METHOD_HYBRID,
        "hybrid_sector_envelope_v1": METHOD_HYBRID,
        "reinit": METHOD_REINIT,
        "reinit_multipass_v1": METHOD_REINIT,
    }
    if m not in aliases:
        raise MultiHorizonError(f"unknown method {raw!r}")
    return aliases[m]


def _sector_override(args: argparse.Namespace) -> dict[str, float] | None:
    head = getattr(args, "sector_head", None)
    flank = getattr(args, "sector_flank", None)
    rear = getattr(args, "sector_rear", None)
    if head is None and flank is None and rear is None:
        return None
    out: dict[str, float] = {}
    if head is not None:
        out["head"] = float(head)
    if flank is not None:
        out["flank"] = float(flank)
    if rear is not None:
        out["rear"] = float(rear)
    return out


def _parse_center_xy(raw: str | None) -> tuple[float, float]:
    if not raw:
        return (0.0, 0.0)
    parts = str(raw).split(",")
    if len(parts) != 2:
        raise MultiHorizonError("--center-xy must be X,Y")
    return (float(parts[0].strip()), float(parts[1].strip()))


def _load_arrival_payload(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise MultiHorizonError(f"--from-arrival must be a JSON object, got {type(data)}")
    if "ros_median_m_min" in data or "ros_mean_m_min" in data or "primary_ros_m_min" in data:
        return data
    for key in ("arrival_oneill_ros", "geometry_ros", "arrival_ros", "oneill"):
        nested = data.get(key)
        if isinstance(nested, dict) and any(
            nested.get(k) is not None
            for k in ("ros_median_m_min", "ros_mean_m_min", "primary_ros_m_min", "ros_m_min")
        ):
            return nested
    return data


def _ros_from_arrival_payload(payload: dict[str, Any]) -> tuple[float, str]:
    for k in (
        "primary_ros_m_min",
        "ros_median_m_min",
        "ros_mean_m_min",
        "ros_m_min",
        "speed_median_m_min",
    ):
        if payload.get(k) is not None:
            return float(payload[k]), k
    raise MultiHorizonError("arrival payload has no usable ros_* key")


def _build_card(
    *,
    ros: float,
    ros_source: str,
    method: str,
    lead_times: list[float] | None,
    sector: dict[str, float] | None,
    head_bearing: float | None,
    weather: dict[str, Any] | None,
    apply_wind: bool,
    reinit_frame: str | None,
    reinit_ts: str | None,
    extra: dict[str, Any] | None = None,
) -> MultiHorizonForecast:
    if reinit_frame:
        return reinit_multihorizon_from_frame(
            ros,
            frame_id=reinit_frame,
            frame_timestamp_utc=reinit_ts,
            method=method if method != METHOD_REINIT else METHOD_ANISOTROPIC,
            lead_times_h=lead_times,
            ros_source=ros_source,
            sector_ros=sector,
            head_bearing_deg=head_bearing,
            weather=weather if apply_wind else None,
            extra=extra,
        )
    if method == METHOD_HYBRID:
        return build_hybrid_multihorizon(
            ros,
            lead_times_h=lead_times,
            ros_source=ros_source,
            sector_ros=sector,
            head_bearing_deg=head_bearing,
            weather=weather if apply_wind else None,
            apply_wind=apply_wind,
            extra=extra,
        )
    if method == METHOD_ANISOTROPIC:
        return build_anisotropic_multihorizon(
            ros,
            lead_times_h=lead_times,
            ros_source=ros_source,
            sector_ros=sector,
            head_bearing_deg=head_bearing,
            weather=weather if apply_wind else None,
            apply_wind=apply_wind,
            extra=extra,
        )
    return build_multihorizon_forecast(
        ros,
        lead_times_h=lead_times,
        ros_source=ros_source,
        extra=extra,
    )


def run_multihorizon(args: argparse.Namespace) -> int:
    """Execute multihorizon command; return process exit code."""
    lead_times = _parse_lead_times(getattr(args, "lead_times", None))
    as_json = bool(getattr(args, "json", False))
    ros_source_override = getattr(args, "ros_source", None)
    sector = _sector_override(args)
    head_bearing = getattr(args, "head_bearing_deg", None)
    apply_wind = not bool(getattr(args, "no_wind", False))
    reinit_frame = getattr(args, "reinit_frame", None)
    reinit_ts = getattr(args, "reinit_timestamp", None)

    try:
        method = _resolve_method(getattr(args, "method", None))
        weather = None
        weather_path = getattr(args, "weather", None)
        if weather_path is not None:
            weather = load_weather_json(weather_path)
            if weather is None:
                # Missing file → explicit fallback (not error)
                weather = None

        if getattr(args, "from_arrival", None) is not None:
            payload = _load_arrival_payload(Path(args.from_arrival))
            if method == METHOD_ISOTROPIC and not reinit_frame:
                card = from_arrival_ros_result(
                    payload,
                    lead_times_h=lead_times,
                    ros_source=ros_source_override or "arrival_ros",
                )
            else:
                ros, key = _ros_from_arrival_payload(payload)
                card = _build_card(
                    ros=ros,
                    ros_source=ros_source_override or f"arrival_ros:{key}",
                    method=method,
                    lead_times=lead_times,
                    sector=sector,
                    head_bearing=head_bearing,
                    weather=weather,
                    apply_wind=apply_wind,
                    reinit_frame=reinit_frame,
                    reinit_ts=reinit_ts,
                )
        elif getattr(args, "psb_duration_s", None) is not None:
            area = getattr(args, "psb_area_ha", None)
            if area is None:
                raise MultiHorizonError("--psb-duration-s requires --psb-area-ha")
            if method != METHOD_ISOTROPIC or reinit_frame:
                # Build equiv ROS then apply method
                from .multihorizon_fieldops import equivalent_ros_from_area_duration

                ros = equivalent_ros_from_area_duration(float(area), float(args.psb_duration_s))
                card = _build_card(
                    ros=ros,
                    ros_source=ros_source_override or "psb_equiv",
                    method=method,
                    lead_times=lead_times,
                    sector=sector,
                    head_bearing=head_bearing,
                    weather=weather,
                    apply_wind=apply_wind,
                    reinit_frame=reinit_frame,
                    reinit_ts=reinit_ts,
                    extra={
                        "psb_area_ha": float(area),
                        "psb_duration_s": float(args.psb_duration_s),
                    },
                )
            else:
                card = from_psb_duration(
                    float(args.psb_duration_s),
                    float(area),
                    lead_times_h=lead_times,
                    ros_source=ros_source_override or "psb_equiv_isotropic",
                )
        elif getattr(args, "tobarra_vp", False):
            from .arrival_ros import TOBARRA_VP_M_MIN

            card = _build_card(
                ros=float(TOBARRA_VP_M_MIN),
                ros_source=ros_source_override or "tobarra_infocam_vp_cite",
                method=method,
                lead_times=lead_times,
                sector=sector,
                head_bearing=head_bearing,
                weather=weather,
                apply_wind=apply_wind,
                reinit_frame=reinit_frame,
                reinit_ts=reinit_ts,
                extra={
                    "anchor": {
                        "fire_id": "tobarra_20240802",
                        "vp_m_min": float(TOBARRA_VP_M_MIN),
                        "cite": "INFOCAM / data/infocam_anchors.json",
                        "honesty": "Vp cite only — not rescaled onto multipass ROS",
                    }
                },
            )
        elif getattr(args, "ros_m_min", None) is not None:
            card = _build_card(
                ros=float(args.ros_m_min),
                ros_source=ros_source_override or "user",
                method=method,
                lead_times=lead_times,
                sector=sector,
                head_bearing=head_bearing,
                weather=weather,
                apply_wind=apply_wind,
                reinit_frame=reinit_frame,
                reinit_ts=reinit_ts,
            )
        else:
            raise MultiHorizonError(
                "Provide --ros-m-min, --tobarra-vp, --from-arrival, or --psb-duration-s + --psb-area-ha"
            )
    except MultiHorizonError as exc:
        print(f"multihorizon error: {exc}", flush=True)
        return 2
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"multihorizon error: {exc}", flush=True)
        return 2

    payload = card.as_dict()
    out = getattr(args, "output", None)
    if out is not None:
        path = Path(out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    geojson_path = getattr(args, "geojson", None)
    if geojson_path is not None:
        try:
            center = _parse_center_xy(getattr(args, "center_xy", "0,0"))
            gj = multihorizon_to_geojson(
                card,
                center_xy=center,
                head_bearing_deg=getattr(args, "head_bearing_deg", None),
            )
            gp = Path(geojson_path)
            gp.parent.mkdir(parents=True, exist_ok=True)
            gp.write_text(json.dumps(gj, indent=2, default=str), encoding="utf-8")
            payload["geojson_path"] = str(gp)
        except MultiHorizonError as exc:
            print(f"multihorizon geojson error: {exc}", flush=True)
            return 2

    scorecard_path = getattr(args, "scorecard", None)
    if scorecard_path is not None:
        sc = multipass_envelope_scorecard(
            card,
            lead_time_h=1.0,
            observed_advance_m=getattr(args, "observed_advance_m", None),
            multipass_span_s=getattr(args, "multipass_span_s", None),
        )
        sp = Path(scorecard_path)
        sp.parent.mkdir(parents=True, exist_ok=True)
        sp.write_text(json.dumps(sc, indent=2, default=str), encoding="utf-8")
        payload["scorecard_path"] = str(sp)

    if as_json:
        print_json(payload)
    else:
        print(format_multihorizon_human(card))
        if out is not None:
            print(f"wrote: {out}")
        if geojson_path is not None:
            print(f"wrote geojson: {geojson_path}")
        if scorecard_path is not None:
            print(f"wrote scorecard: {scorecard_path}")
    return 0
