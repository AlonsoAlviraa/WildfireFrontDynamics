#!/usr/bin/env python3
"""Deep-research S4: arrival-time ROS honesty note + multipass re-check.

Prefer multipass export from ``scripts/run_tobarra_multipass_s4.py``.
Does **not** invent multi-pass if missing. When
``outputs/tobarra_multipass_s4/s4_board.json`` exists with status OK,
S4 re-check passes.

Usage
-----
::

    $env:PYTHONPATH = "."
    python scripts/run_deep_research_s4_arrival_ros_note.py
    python scripts/run_deep_research_s4_arrival_ros_note.py --run-multipass
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.arrival_ros import (  # noqa: E402
    discover_multipass_chain,
    strip_frame_objects,
)

MULTIPASS_BOARD = ROOT / "outputs" / "tobarra_multipass_s4" / "s4_board.json"
DEFAULT_IMAGES = ROOT / "artifacts" / "tobarra_reprojected_lwir"
DEFAULT_MASKS = ROOT / "artifacts" / "tobarra_lwir_masks"


def _load(path: Path) -> Any | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _find_tobarra_artifacts() -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    candidates = [
        ROOT / "outputs" / "tobarra_multipass_s4",
        ROOT / "outputs" / "tobarra_demo",
        ROOT / "outputs" / "tobarra_lwir",
        ROOT / "outputs" / "incidents",
        ROOT / "outputs" / "gold_e2e",
        ROOT / "outputs" / "observatorio" / "tobarra_20240802",
    ]
    patterns = (
        "*geometry*",
        "*arrival*",
        "*ros*",
        "*front_dynamics*",
        "*metrics*.json",
        "*summary*.json",
        "*s4_board*",
        "*operational*",
    )
    for base in candidates:
        if not base.is_dir() and not base.is_file():
            continue
        if base.is_file() and base.suffix.lower() == ".json":
            paths = [base]
        else:
            paths = []
            for pat in patterns:
                paths.extend(base.rglob(pat))
        for p in paths:
            if p.suffix.lower() != ".json":
                continue
            rel = str(p.relative_to(ROOT)).replace("\\", "/")
            data = _load(p)
            if not isinstance(data, dict):
                continue
            keys = set(data.keys())
            interesting = {
                k
                for k in keys
                if any(
                    s in k.lower()
                    for s in (
                        "ros",
                        "arrival",
                        "geometry",
                        "speed",
                        "vp",
                        "head",
                        "hybrid",
                        "status",
                        "primary",
                    )
                )
            }
            if not interesting and "schema" not in data:
                continue
            hits.append(
                {
                    "path": rel,
                    "schema": data.get("schema"),
                    "status": data.get("status") or data.get("verdict"),
                    "interesting_keys": sorted(interesting)[:30],
                    "sample": {
                        k: data.get(k)
                        for k in list(interesting)[:12]
                        if not isinstance(data.get(k), (dict, list))
                    },
                }
            )
    seen: set[str] = set()
    uniq: list[dict[str, Any]] = []
    for h in hits:
        if h["path"] in seen:
            continue
        seen.add(h["path"])
        uniq.append(h)
    return uniq[:40]


def _status_from_multipass(board: dict[str, Any] | None, chain: dict[str, Any]) -> str:
    """Derive S4 status from multipass export + on-disk chain discovery."""
    if isinstance(board, dict):
        st = board.get("status") or board.get("verdict")
        if st in ("OK", "BLOCKED_MULTI_PASS_EXPORT"):
            return str(st)
        if st:
            return str(st)
    if chain.get("n_frames", 0) >= 2:
        # Chain exists but dedicated multipass export not run / incomplete
        return "MULTIPASS_CHAIN_PRESENT_EXPORT_PENDING"
    return "BLOCKED_MULTI_PASS_EXPORT"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--out",
        type=Path,
        default=ROOT / "outputs" / "ml_eval" / "lab_loop" / "deep_research_s4_arrival_ros.json",
    )
    p.add_argument(
        "--md",
        type=Path,
        default=ROOT / "docs" / "fire_intel" / "ARRIVAL_TIME_ROS_S4_NOTE.md",
    )
    p.add_argument("--no-md", action="store_true")
    p.add_argument(
        "--run-multipass",
        action="store_true",
        help="Invoke scripts/run_tobarra_multipass_s4.py before inventory",
    )
    p.add_argument(
        "--multipass-mode",
        choices=("auto", "ingest", "reuse"),
        default="auto",
    )
    args = p.parse_args(argv)

    multipass_rc: int | None = None
    multipass_fail_closed: str | None = None
    if args.run_multipass:
        cmd = [
            sys.executable,
            str(ROOT / "scripts" / "run_tobarra_multipass_s4.py"),
            "--mode",
            args.multipass_mode,
        ]
        completed = subprocess.run(cmd, cwd=str(ROOT), check=False)
        multipass_rc = int(completed.returncode)

    multipass = _load(MULTIPASS_BOARD)
    if not isinstance(multipass, dict):
        multipass = None

    chain = discover_multipass_chain(DEFAULT_IMAGES, DEFAULT_MASKS, require_mask=True)
    chain_json = strip_frame_objects(chain)

    code = {
        "geometry_speed": (ROOT / "wildfire_front" / "geometry_speed.py").is_file(),
        "arrival_ros": (ROOT / "wildfire_front" / "arrival_ros.py").is_file(),
        "reconstruct_arrival": True,
        "cli_ops_path": (ROOT / "wildfire_front" / "cli.py").is_file(),
        "multipass_runner": (ROOT / "scripts" / "run_tobarra_multipass_s4.py").is_file(),
        "oneill_formula": "ROS_m_min = 60 / |grad T_s| (arrival-time gradient)",
        "lampman_note": "Method anchor only — do not use grassland MAE as Tobarra SLA",
    }
    arts = _find_tobarra_artifacts()
    status = _status_from_multipass(multipass, chain)

    # Promote to OK only when multipass board is OK
    if isinstance(multipass, dict) and multipass.get("status") == "OK":
        status = "OK"

    # Fail-closed when multipass was invoked and did not succeed:
    # - rc 2 → trust rewritten board if present (usually BLOCKED), else BLOCKED
    # - other non-zero → crash / unexpected; do not keep a stale OK board
    if args.run_multipass and multipass_rc is not None and multipass_rc != 0:
        board_status = multipass.get("status") if isinstance(multipass, dict) else None
        if multipass is None:
            status = "BLOCKED_MULTI_PASS_EXPORT"
            multipass_fail_closed = "multipass_runner_failed_no_board"
        elif board_status == "OK":
            status = "BLOCKED_MULTI_PASS_EXPORT"
            multipass_fail_closed = "multipass_runner_failed_stale_ok_board"
        else:
            status = str(board_status or "BLOCKED_MULTI_PASS_EXPORT")
            multipass_fail_closed = "multipass_runner_nonzero_board_not_ok"

    envelope_paths = list((ROOT / "outputs").rglob("*envelope*scorecard*.json"))[:5]
    env_refs = [str(p.relative_to(ROOT)).replace("\\", "/") for p in envelope_paths if p.is_file()]

    board = {
        "schema": "deep_research_s4_arrival_ros_v1",
        "created_utc": datetime.now(UTC).isoformat(),
        "strategy": "S4_arrival_time_ros_geometry",
        "deep_research": "docs/fire_intel/DEEP_RESEARCH_STRATEGIES_2024_2026.md",
        "status": status,
        "verdict": status,
        "code_capabilities": code,
        "multipass_chain": {
            "n_frames": chain_json.get("n_frames"),
            "n_with_timestamp": chain_json.get("n_with_timestamp"),
            "first_timestamp_utc": chain_json.get("first_timestamp_utc"),
            "last_timestamp_utc": chain_json.get("last_timestamp_utc"),
            "span_s": chain_json.get("span_s"),
            "images_dir": chain_json.get("images_dir"),
            "masks_dir": chain_json.get("masks_dir"),
            "status": chain_json.get("status"),
        },
        "multipass_export": {
            "path": str(MULTIPASS_BOARD.relative_to(ROOT)).replace("\\", "/")
            if MULTIPASS_BOARD.is_file()
            else None,
            "status": multipass.get("status") if isinstance(multipass, dict) else None,
            "primary_ros_m_min": (multipass.get("geometry_ros") or {}).get("primary_ros_m_min")
            if isinstance(multipass, dict)
            else None,
            "oneill_ros_median_m_min": (multipass.get("arrival_oneill_ros") or {}).get(
                "ros_median_m_min"
            )
            if isinstance(multipass, dict)
            else None,
            "anchor_compare": multipass.get("anchor_compare")
            if isinstance(multipass, dict)
            else None,
            "runner_returncode": multipass_rc,
            "fail_closed_reason": multipass_fail_closed,
        },
        "exit_policy": {
            "ok_exit_0": "status == OK",
            "nonzero_exit": "status != OK (S4 gate for automation)",
            "run_multipass_stale_ok": "fail closed → BLOCKED_MULTI_PASS_EXPORT",
        },
        "tobarra_artifact_hits": arts,
        "envelope_refs": env_refs,
        "experiment_recipe": {
            "cmd": "python scripts/run_tobarra_multipass_s4.py",
            "recheck": "python scripts/run_deep_research_s4_arrival_ros_note.py",
            "success": "arrival grid + ROS m/min table vs Vp without quoting ML IoU",
            "kill": "single frame or coreg fail → BLOCKED note, no invented ROS",
        },
        "rails": {
            "ml_product_go": False,
            "field_ops_allow_ml_live_in_fusion": False,
            "iou_is_not_ros": True,
            "lampman_mae_not_sla": True,
        },
        "honesty": [
            "Arrival-time ROS is geometry of progression, not mask IoU",
            "Multi-pass frames must exist on disk; never invent Tobarra gold ROS",
            "If no multi-pass export → BLOCKED_MULTI_PASS_EXPORT (honest)",
            "Lampman MAE is method cite only",
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(board, indent=2), encoding="utf-8")

    if not args.no_md:
        lines = [
            "# Arrival-time ROS (deep research S4)",
            "",
            f"**UTC:** {board['created_utc']}",
            f"**Status:** **{status}**",
            "",
            "## Method (literature + WFD)",
            "",
            "- O'Neill et al. (IJWF 2024): arrival-time raster → "
            "**ROS = 60 / |∇T| m/min** (geometry, not IoU).",
            "- Lampman et al. (IJWF 2026): multi-pass TIR method anchor — **not** Tobarra SLA.",
            "- WFD: `wildfire_front/geometry_speed.py` + `arrival_ros.py` + "
            "`reconstruct_arrival_from_components` + multipass runner.",
            "",
            "## Multi-pass discovery",
            "",
            f"- On-disk paired frames: **{chain_json.get('n_frames')}**",
            f"- Window: `{chain_json.get('first_timestamp_utc')}` → "
            f"`{chain_json.get('last_timestamp_utc')}`",
            f"- Multipass export status: **{(board.get('multipass_export') or {}).get('status')}**",
            f"- Primary ROS: `{(board.get('multipass_export') or {}).get('primary_ros_m_min')}` m/min",
            f"- O'Neill median: `{(board.get('multipass_export') or {}).get('oneill_ros_median_m_min')}` m/min",
            "",
            "## On-disk inventory (this run)",
            "",
            f"- Artifact hits scanned: **{len(arts)}**",
        ]
        for h in arts[:12]:
            lines.append(
                f"- `{h['path']}` status={h.get('status')} keys={h.get('interesting_keys')}"
            )
        if not arts:
            lines.append("- No Tobarra geometry/arrival JSON found under outputs probes.")
        lines += [
            "",
            "## Kill / success",
            "",
            "| | |",
            "|--|--|",
            "| Success | Multi-frame export → arrival + ROS vs Vp table |",
            "| Kill / blocked | Single frame or coreg fail → document BLOCKED |",
            "",
            "## Rails",
            "",
            "- ml_product_go false · fusion OFF · IoU ≠ ROS",
            "",
            f"Machine: `{args.out.as_posix()}`",
            "Runner: `python scripts/run_tobarra_multipass_s4.py`",
            "",
        ]
        args.md.parent.mkdir(parents=True, exist_ok=True)
        args.md.write_text("\n".join(lines), encoding="utf-8")

    gate_ok = status == "OK"
    print(
        json.dumps(
            {
                "ok": gate_ok,
                "status": status,
                "out": str(args.out),
                "multipass_runner_returncode": multipass_rc,
                "fail_closed_reason": multipass_fail_closed,
            },
            indent=2,
        )
    )
    # Exit 0 only when S4 multipass status is OK (automation gate).
    return 0 if gate_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
