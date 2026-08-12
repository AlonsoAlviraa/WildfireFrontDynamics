#!/usr/bin/env python3
"""Tobarra multi-horizon field_ops demo (Vp 7 m/min cite).

Writes JSON + human table under outputs/multihorizon_tobarra_demo/.

Rails
-----
* field_ops product rail (not lab ML next-day IoU)
* field fusion OFF
* Vp is INFOCAM anchor cite — not invented and not rescaled onto multipass ROS
* Does not reopen Tobarra KEEP / ECE thrash

Usage
-----
  python scripts/run_multihorizon_tobarra_demo.py
  python scripts/run_multihorizon_tobarra_demo.py --ros-m-min 11.28
  python scripts/run_multihorizon_tobarra_demo.py --from-s4-board path/to/board.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.arrival_ros import (  # noqa: E402
    TOBARRA_AREA_HA,
    TOBARRA_FIRE_ID,
    TOBARRA_VP_M_MIN,
    build_s4_board,
)
from wildfire_front.multihorizon_fieldops import (  # noqa: E402
    DEFAULT_LEAD_TIMES_H,
    MultiHorizonForecast,
    build_multihorizon_forecast,
    format_multihorizon_human,
    from_s4_board_sources,
)


def _parse_leads(raw: str | None) -> list[float] | None:
    if not raw:
        return None
    return [float(x.strip()) for x in raw.split(",") if x.strip()]


def build_demo_card(
    *,
    ros_m_min: float | None,
    from_s4: Path | None,
    lead_times_h: list[float] | None,
) -> tuple[MultiHorizonForecast, dict[str, Any]]:
    meta: dict[str, Any] = {
        "fire_id": TOBARRA_FIRE_ID,
        "demo": "multihorizon_tobarra_v1",
        "created_utc": datetime.now(UTC).isoformat(),
    }
    if from_s4 is not None and from_s4.is_file():
        board = json.loads(from_s4.read_text(encoding="utf-8"))
        if not isinstance(board, dict):
            raise SystemExit(f"--from-s4-board must be JSON object: {from_s4}")
        # Prefer existing multihorizon if already attached
        existing = board.get("multihorizon_fieldops")
        if isinstance(existing, dict) and existing.get("schema") == "wfd_multihorizon_fieldops_v1":
            # Rebuild from ros to get a typed card
            card = build_multihorizon_forecast(
                float(existing["ros_m_min"]),
                lead_times_h=lead_times_h or existing.get("lead_times_h"),
                ros_source=str(existing.get("ros_source") or "s4_board"),
                extra={"from_s4_board": str(from_s4), "reused_existing": True},
            )
            meta["source"] = "s4_board_existing_multihorizon"
            return card, meta
        card = from_s4_board_sources(
            geometry_ros=board.get("geometry_ros"),
            arrival_oneill=board.get("arrival_oneill_ros"),
            fallback_ros_m_min=ros_m_min if ros_m_min is not None else TOBARRA_VP_M_MIN,
            lead_times_h=lead_times_h,
            extra={"from_s4_board": str(from_s4)},
        )
        if card is None:
            raise SystemExit("S4 board has no usable ROS for multihorizon")
        meta["source"] = "s4_board"
        return card, meta

    v = float(ros_m_min) if ros_m_min is not None else float(TOBARRA_VP_M_MIN)
    source = "user" if ros_m_min is not None else "tobarra_infocam_vp_cite"
    card = build_multihorizon_forecast(
        v,
        lead_times_h=lead_times_h,
        ros_source=source,
        extra={
            "anchor": {
                "fire_id": TOBARRA_FIRE_ID,
                "vp_m_min": TOBARRA_VP_M_MIN,
                "area_ha": TOBARRA_AREA_HA,
                "cite": "INFOCAM / data/infocam_anchors.json",
            }
        },
    )
    meta["source"] = source
    meta["ros_m_min"] = v
    return card, meta


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--ros-m-min",
        type=float,
        default=None,
        help=f"Override ROS m/min (default: Tobarra Vp {TOBARRA_VP_M_MIN})",
    )
    p.add_argument(
        "--from-s4-board",
        type=Path,
        default=None,
        help="Optional S4 board JSON (geometry / O'Neill ROS)",
    )
    p.add_argument(
        "--lead-times",
        type=str,
        default=None,
        help=f"Comma hours (default {list(DEFAULT_LEAD_TIMES_H)})",
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "outputs" / "multihorizon_tobarra_demo",
        help="Output directory",
    )
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args(argv)

    leads = _parse_leads(args.lead_times)
    card, meta = build_demo_card(
        ros_m_min=args.ros_m_min,
        from_s4=args.from_s4_board,
        lead_times_h=leads,
    )
    payload = card.as_dict()
    payload["demo_meta"] = meta

    # Mini S4-style board for the demo (uses Vp when no multipass)
    board = build_s4_board(
        status="demo_vp_cite" if meta["source"].endswith("vp_cite") else "demo",
        inventory={
            "n_frames": 0,
            "mode": "multihorizon_demo",
            "note": "No multipass frames required for Vp-cite multihorizon demo",
        },
        geometry_ros={"primary_ros_m_min": card.ros_m_min, "source": card.ros_source},
        multihorizon=payload,
        attach_multihorizon=False,
    )

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    card_path = out_dir / "multihorizon_fieldops.json"
    board_path = out_dir / "s4_board_with_multihorizon.json"
    human_path = out_dir / "multihorizon_human.txt"
    card_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    board_path.write_text(json.dumps(board, indent=2, default=str), encoding="utf-8")
    human = format_multihorizon_human(card)
    human_path.write_text(human + "\n", encoding="utf-8")

    if not args.quiet:
        print(human)
        print()
        print(f"wrote: {card_path}")
        print(f"wrote: {board_path}")
        print(f"wrote: {human_path}")
        print(
            f"ok: ros_m_min={card.ros_m_min} horizons={len(card.horizons)} "
            f"fusion={payload['rails']['field_ops_ml_live_fusion']} "
            f"iou_is_not_ros={payload['rails']['iou_is_not_ros']}"
        )
    # Non-zero advance for Tobarra Vp path
    if card.ros_m_min <= 0:
        print("error: ros_m_min must be > 0 for Tobarra demo", file=sys.stderr)
        return 1
    h1 = next((h for h in card.horizons if h.lead_time_h == 1.0), card.horizons[0])
    if h1.advance_m <= 0:
        print("error: 1h advance_m is zero", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
