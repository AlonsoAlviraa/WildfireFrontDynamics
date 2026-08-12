#!/usr/bin/env python3
"""Deep-research S3: multi-pack open perimeter Hausdorff-lite board (no live EFFIS).

Uses existing open_if packs + summarize_open_perimeter_attempt (R-A1).
Does **not** claim national O2 unlock.

Usage
-----
::

    $env:PYTHONPATH = "."
    python scripts/run_deep_research_s3_open_perimeter_board.py
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

from scripts.summarize_open_perimeter_attempt import summarize_pack  # noqa: E402

DEFAULT_PACKS = [
    "emsr578",
    "emsr581",
    "emsr583",
    "and_2024040053_20240606",
    "and_2024140035_20240712",
    "ext_2025060450_20250814",
]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--open-root",
        type=Path,
        default=ROOT / "outputs" / "open_if",
    )
    p.add_argument(
        "--packs",
        nargs="*",
        default=DEFAULT_PACKS,
        help="Pack folder names under open_if",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=ROOT / "outputs" / "open_perimeter_attempts" / "deep_research_s3_board.json",
    )
    p.add_argument(
        "--md",
        type=Path,
        default=ROOT / "docs" / "fire_intel" / "OPEN_PERIMETER_S3_BOARD.md",
    )
    p.add_argument("--no-md", action="store_true")
    args = p.parse_args(argv)

    rows: list[dict[str, Any]] = []
    for name in args.packs:
        pack = args.open_root / name
        if not pack.is_dir():
            rows.append(
                {
                    "pack_id": name,
                    "status": "MISSING",
                    "note": f"path not found: {pack}",
                }
            )
            continue
        try:
            summary = summarize_pack(pack)
        except Exception as exc:  # noqa: BLE001 — board must continue
            rows.append(
                {
                    "pack_id": name,
                    "status": "ERROR",
                    "note": f"{type(exc).__name__}: {exc}",
                }
            )
            continue
        # Also load metrics_o2 if present (REDIAM Hausdorff already computed)
        o2 = None
        o2_path = pack / "metrics_o2.json"
        if o2_path.is_file():
            try:
                o2 = json.loads(o2_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                o2 = None
        rows.append(
            {
                "pack_id": name,
                "status": "OK",
                "n_vector_products": int(
                    summary.get("n_vector_files") or len(summary.get("vector_files") or [])
                ),
                "intra_hausdorff_lite_m": summary.get("hausdorff_lite_intra_pack_m"),
                "hausdorff_pair": summary.get("hausdorff_lite_pair"),
                "o2_national": summary.get("O2_national_official"),
                "activation": summary.get("activation"),
                "max_area_ha": summary.get("max_area_ha"),
                "metrics_o2": {
                    "hausdorff_m": (o2 or {}).get("hausdorff_m"),
                    "hausdorff_status": (o2 or {}).get("hausdorff_status"),
                    "area_rediam_ha": (o2 or {}).get("area_rediam_ha"),
                    "ratio_hull_vs_rediam": (o2 or {}).get("ratio_hull_vs_rediam"),
                    "iou_firms_buffer_vs_rediam": (o2 or {}).get("iou_firms_buffer_vs_rediam"),
                }
                if o2
                else None,
                "honesty": [
                    "Open / CEMS / REDIAM is not national cadastre O2",
                    "Hausdorff-lite is proxy geometry",
                    str(summary.get("note") or ""),
                ],
                "summary_path": str(
                    (
                        ROOT
                        / "outputs"
                        / "open_perimeter_attempts"
                        / name
                        / "perimeter_summary.json"
                    ).as_posix()
                ),
            }
        )
        # Persist per-pack summary under attempts
        att = ROOT / "outputs" / "open_perimeter_attempts" / name
        att.mkdir(parents=True, exist_ok=True)
        (att / "perimeter_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    ok_n = sum(1 for r in rows if r.get("status") == "OK")
    board = {
        "schema": "deep_research_s3_open_perimeter_board_v1",
        "created_utc": datetime.now(UTC).isoformat(),
        "strategy": "S3_open_perimeter_hausdorff_lite",
        "deep_research": "docs/fire_intel/DEEP_RESEARCH_STRATEGIES_2024_2026.md",
        "n_packs_requested": len(args.packs),
        "n_packs_ok": ok_n,
        "verdict": "BOARD_OK" if ok_n >= 1 else "NO_PACKS",
        "o2_national": False,
        "note": (
            "Local open packs only — no live EFFIS WFS download this run. "
            "Use metrics_o2 Hausdorff when REDIAM present; else intra-pack lite."
        ),
        "rows": rows,
        "rails": {
            "ml_product_go": False,
            "field_ops_allow_ml_live_in_fusion": False,
            "claims_national_o2": False,
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(board, indent=2), encoding="utf-8")

    if not args.no_md:
        lines = [
            "# Open perimeter S3 board (deep research)",
            "",
            f"**UTC:** {board['created_utc']}",
            f"**Verdict:** {board['verdict']} · packs OK **{ok_n}/{len(args.packs)}**",
            "",
            "> Not national O2. Hausdorff is proxy. IoU ≠ ROS.",
            "",
            "| Pack | Status | Intra H-lite (m) | O2 metrics H (m) | area REDIAM ha |",
            "|------|--------|-----------------:|-----------------:|---------------:|",
        ]
        for r in rows:
            o2 = r.get("metrics_o2") or {}
            lines.append(
                f"| {r.get('pack_id')} | {r.get('status')} | "
                f"{r.get('intra_hausdorff_lite_m') if r.get('intra_hausdorff_lite_m') is not None else '—'} | "
                f"{o2.get('hausdorff_m') if o2.get('hausdorff_m') is not None else '—'} | "
                f"{o2.get('area_rediam_ha') if o2.get('area_rediam_ha') is not None else '—'} |"
            )
        lines += [
            "",
            "## Honesty",
            "",
            "- CEMS / REDIAM / FIRMS hull ≠ cadastre nacional",
            "- No Vp invented",
            "- Live EFFIS WFS left for future when network + license path ready",
            "",
            f"Machine: `{args.out.as_posix()}`",
            "",
        ]
        args.md.parent.mkdir(parents=True, exist_ok=True)
        args.md.write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps({"ok": True, "out": str(args.out), "n_ok": ok_n}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
