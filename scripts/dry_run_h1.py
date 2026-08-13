#!/usr/bin/env python3
"""W4-A: H1 dry-run stamp. Not an acta. Never sets GO_Q / go_q_met true.

Does **not** call record_h1_demo_complete success path.

python scripts/dry_run_h1.py
python scripts/dry_run_h1.py --out docs/H1_DRY_RUN.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "docs" / "H1_DRY_RUN.json"


def _snapshot_field_ops_fusion() -> str:
    """Catalog rail first (same as check_release_flags); fail-closed OFF."""
    try:
        from wildfire_front.product.policy import field_ops_ml_live_fusion_rail

        rail = str(field_ops_ml_live_fusion_rail()).upper()
        if rail in {"ON", "OFF"}:
            return rail
    except Exception:
        pass
    stamp_path = ROOT / "docs" / "ML_PRODUCT_GO_STATUS.json"
    try:
        stamp = json.loads(stamp_path.read_text(encoding="utf-8"))
        rails = stamp.get("rails") or {}
        fusion = str(rails.get("field_ops_fusion") or "").upper()
        if fusion in {"ON", "OFF"}:
            return fusion
        if stamp.get("field_ops_allow_ml_live_in_fusion") is True:
            return "ON"
    except (OSError, json.JSONDecodeError, TypeError, AttributeError):
        pass
    return "OFF"


def build_dry_run_stamp(*, now: datetime | None = None) -> dict[str, Any]:
    ts = now or datetime.now(UTC)
    as_of = ts.strftime("%Y-%m-%dT%H:%M:%SZ") if ts.tzinfo else ts.isoformat() + "Z"
    fusion = _snapshot_field_ops_fusion()
    return {
        "schema": "wfd_h1_dry_run_v1",
        "as_of_utc": as_of,
        "go_q_met": False,
        "GO_Q": "partial",
        "not_third_party_acta": True,
        "not_signed_acta": True,
        "product_unlock": False,
        "calls_record_h1_demo_complete": False,
        "field_ops_fusion": fusion,
        "note": f"dry-run ≠ acta · no inventa GO_Q · fusion {fusion} ≠ despacho",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Write H1 dry-run stamp (go_q_met=false; not acta)."
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    stamp = build_dry_run_stamp()
    if stamp["go_q_met"] is True or stamp["GO_Q"] != "partial":
        print("error: dry-run must not set GO_Q / go_q_met true", file=sys.stderr)
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(stamp, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": True,
                "out": str(args.out),
                "go_q_met": False,
                "GO_Q": "partial",
                "not_third_party_acta": True,
                "not_signed_acta": True,
                "calls_record_h1_demo_complete": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
