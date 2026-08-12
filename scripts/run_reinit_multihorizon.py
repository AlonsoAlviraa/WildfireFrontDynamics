#!/usr/bin/env python3
"""Re-init multihorizon from a new IR / multipass frame (PR9).

Reads ROS from --ros-m-min or an S4 / arrival JSON, stamps
``reinit_from_frame``, never rolls ML next-day mask as 1h truth.

Usage
-----
::

    python scripts/run_reinit_multihorizon.py --ros-m-min 6.14 --frame frame_03
    python scripts/run_reinit_multihorizon.py --from-s4-board outputs/tobarra_multipass_s4/s4_board.json \\
        --frame 2024-08-02_16-42-37-447_LWIR --method anisotropic --geojson rings.geojson
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.multihorizon_fieldops import (  # noqa: E402
    METHOD_ANISOTROPIC,
    METHOD_HYBRID,
    METHOD_ISOTROPIC,
    MultiHorizonError,
    format_multihorizon_human,
    from_s4_board_sources,
    load_weather_json,
    multihorizon_to_geojson,
    reinit_multihorizon_from_frame,
)


def _resolve_method(raw: str) -> str:
    m = raw.strip().lower()
    return {
        "isotropic": METHOD_ISOTROPIC,
        "isotropic_ros_buffer_v1": METHOD_ISOTROPIC,
        "anisotropic": METHOD_ANISOTROPIC,
        "anisotropic_ros_buffer_v1": METHOD_ANISOTROPIC,
        "hybrid": METHOD_HYBRID,
        "hybrid_sector_envelope_v1": METHOD_HYBRID,
    }.get(m, METHOD_ANISOTROPIC)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ros-m-min", type=float, default=None)
    p.add_argument("--from-s4-board", type=Path, default=None)
    p.add_argument("--frame", required=True, help="Frame id / stem for reinit stamp")
    p.add_argument("--frame-timestamp", type=str, default=None)
    p.add_argument(
        "--method",
        default="anisotropic",
        help="Parent method before reinit stamp (isotropic|anisotropic|hybrid)",
    )
    p.add_argument("--lead-times", type=str, default=None)
    p.add_argument("--weather", type=Path, default=None)
    p.add_argument("--output", "-o", type=Path, default=None)
    p.add_argument("--geojson", type=Path, default=None)
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    leads = None
    if args.lead_times:
        leads = [float(x.strip()) for x in args.lead_times.split(",") if x.strip()]

    method = _resolve_method(args.method)
    weather = load_weather_json(args.weather) if args.weather else None
    previous = None
    ros: float | None = args.ros_m_min
    ros_source = "user"

    try:
        if args.from_s4_board is not None:
            board = json.loads(Path(args.from_s4_board).read_text(encoding="utf-8"))
            if not isinstance(board, dict):
                raise MultiHorizonError("S4 board must be JSON object")
            previous = board.get("multihorizon_fieldops")
            card0 = from_s4_board_sources(
                geometry_ros=board.get("geometry_ros"),
                arrival_oneill=board.get("arrival_oneill_ros"),
                fallback_ros_m_min=ros,
            )
            if card0 is None and ros is None:
                raise MultiHorizonError("S4 board has no ROS and --ros-m-min missing")
            if card0 is not None:
                ros = float(card0.ros_m_min)
                ros_source = str(card0.ros_source)
                previous = card0.as_dict()
        if ros is None:
            raise MultiHorizonError("Provide --ros-m-min or --from-s4-board with ROS")

        card = reinit_multihorizon_from_frame(
            float(ros),
            frame_id=str(args.frame),
            frame_timestamp_utc=args.frame_timestamp,
            method=method,
            previous_card=previous,
            lead_times_h=leads,
            ros_source=f"reinit:{ros_source}",
            weather=weather,
            extra={
                "script": "run_reinit_multihorizon.py",
                "created_utc": datetime.now(UTC).isoformat(),
                "never_ml_mask_as_1h_truth": True,
            },
        )
    except (MultiHorizonError, OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"reinit-multihorizon error: {exc}", file=sys.stderr)
        return 2

    payload = card.as_dict()
    assert payload.get("reinit_from_frame") or payload.get("honesty", {}).get(
        "reinit_from_frame"
    ), "reinit stamp missing"
    # Safety: method must be reinit
    if payload.get("method") != "reinit_multipass_v1":
        print("error: method must be reinit_multipass_v1", file=sys.stderr)
        return 1

    out = args.output
    if out is None:
        out = ROOT / "outputs" / "multihorizon_reinit" / "multihorizon_fieldops.json"
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    if args.geojson is not None:
        gj = multihorizon_to_geojson(card, center_xy=(0.0, 0.0))
        Path(args.geojson).parent.mkdir(parents=True, exist_ok=True)
        Path(args.geojson).write_text(json.dumps(gj, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(format_multihorizon_human(card))
        print(f"wrote: {out}")
        if args.geojson:
            print(f"wrote geojson: {args.geojson}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
