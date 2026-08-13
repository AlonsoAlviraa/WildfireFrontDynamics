#!/usr/bin/env python3
"""Decide on already-aligned Tobarra LWIR (no KEEP reopen, no retrain).

Uses artifacts/aligned_spatial_v1/tobarra_20240802 chain GeoTIFFs plus the
existing geotiff ingest + decide_from_request path. Does not touch
infocam_anchors, does not reopen KEEP, does not retrain.

python scripts/decide_tobarra_aligned.py
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.cli import run_geotiff_ingest  # noqa: E402
from wildfire_front.open_if.external_ros import honesty_row, utc_now  # noqa: E402
from wildfire_front.product.decide_service import decide_from_request  # noqa: E402

DEFAULT_ALIGN = ROOT / "artifacts" / "aligned_spatial_v1" / "tobarra_20240802"
DEFAULT_OUT = ROOT / "outputs" / "open_if" / "best_fires_e2e" / "tobarra_aligned_decide"
EVENT_ID = "tobarra_20240802"
# First / mid / last of chain_00 (dated, already aligned, ≥3 scenes).
DEFAULT_STEMS = (
    "2024-08-02_16-08-21-553_LWIR",
    "2024-08-02_16-15-07-320_LWIR",
    "2024-08-02_16-19-14-281_LWIR",
)


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _link_or_copy(src: Path, dest: Path) -> str:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    try:
        os.link(src, dest)
        return "hardlink"
    except OSError:
        shutil.copy2(src, dest)
        return "copy"


def _stage_chain(
    align_root: Path,
    staging: Path,
    stems: tuple[str, ...],
    chain: str,
) -> dict:
    lwir = align_root / "chains" / chain / "lwir"
    masks = align_root / "chains" / chain / "masks"
    img_out = staging / "images"
    mask_out = staging / "masks"
    staged: list[dict] = []
    for stem in stems:
        img = lwir / f"{stem}.tif"
        mask = masks / f"{stem}_mask.tif"
        if not img.is_file() or not mask.is_file():
            return {
                "ok": False,
                "reason": "missing_aligned_pair",
                "image": _rel(img),
                "mask": _rel(mask),
            }
        how_i = _link_or_copy(img, img_out / img.name)
        how_m = _link_or_copy(mask, mask_out / mask.name)
        staged.append(
            {
                "stem": stem,
                "image": _rel(img),
                "mask": _rel(mask),
                "stage_method": how_i if how_i == how_m else f"{how_i}+{how_m}",
            }
        )
    return {
        "ok": True,
        "chain": chain,
        "n_scenes": len(staged),
        "scenes": staged,
        "images_dir": _rel(img_out),
        "masks_dir": _rel(mask_out),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Decide on aligned Tobarra LWIR without KEEP")
    ap.add_argument("--align-root", type=Path, default=DEFAULT_ALIGN)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--chain", default="chain_00")
    args = ap.parse_args(argv)

    honesty = honesty_row("tobarra_aligned_decide")
    args.out.mkdir(parents=True, exist_ok=True)
    dest = args.out / "decide_report.json"

    def _write(report: dict) -> int:
        report.update(
            {
                "schema": "wfd_tobarra_aligned_decide_v1",
                "as_of_utc": utc_now(),
                "event_id": EVENT_ID,
                "honesty_class": honesty["honesty_class"],
                "grade_a_promote": False,
                "keep_reopened": False,
                "retrained": False,
                "infocam_anchors_touched": False,
                "not_product_ros": True,
                "not_tactical_dispatch": True,
                "report_path": _rel(dest),
            }
        )
        dest.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        print(json.dumps(report, indent=2, default=str))
        print(f"wrote {dest}")
        return 0 if report.get("ok") else 1

    if not args.align_root.is_dir():
        return _write(
            {
                "ok": False,
                "status": "missing_align_root",
                "align_root": _rel(args.align_root),
            }
        )

    staging = args.out / "staged"
    staged = _stage_chain(args.align_root, staging, DEFAULT_STEMS, args.chain)
    if not staged.get("ok"):
        staged["status"] = "stage_failed"
        return _write(staged)

    ingest_out = args.out / "ingest"
    try:
        summary = run_geotiff_ingest(
            staging / "images",
            staging / "masks",
            ingest_out,
            EVENT_ID,
            "lwir_drone",
            2.0,
            1,
            None,
            write_operational=True,
        )
        ingest = {
            "ok": int(summary.get("num_observations") or 0) >= 3,
            "n_accepted": int(summary.get("num_observations") or 0),
            "n_observations": int(summary.get("num_observations") or 0),
            "speed_status": summary.get("speed_status"),
            "arrival_resolution_m": summary.get("arrival_resolution_m"),
            "output": _rel(ingest_out),
        }
    except Exception as exc:  # noqa: BLE001 — persist honest fail
        return _write(
            {
                "ok": False,
                "status": "ingest_failed",
                "stage": staged,
                "error": f"{type(exc).__name__}: {exc}",
            }
        )

    work_dir = args.out / "decide_work"
    work_dir.mkdir(parents=True, exist_ok=True)
    for name in ("operational_metrics.json", "front_dynamics.json", "summary.json"):
        src = ingest_out / name
        if src.is_file():
            shutil.copy2(src, work_dir / name)

    card = decide_from_request(
        {
            "event_id": EVENT_ID,
            "work_dir": str(work_dir),
            "require_ops_for_go": True,
            "use_ml_v34": False,
            "channel": "cli",
            "write_decision_log": True,
            "write_vv_scorecard": True,
        },
        base=ROOT,
    )
    decide = {
        "decision": card.get("decision"),
        "confidence_pred": card.get("confidence_pred"),
        "confidence_pred_label": card.get("confidence_pred_label"),
        "latency_ms": card.get("latency_ms"),
        "reasons": (card.get("reasons") or [])[:16],
        "policy_id": card.get("policy_id"),
        "work_dir": _rel(work_dir),
        "note": (
            "Aligned LWIR ingest + decide. Not KEEP reopen, not retrain, "
            "not grade-A promote, not tactical dispatch."
        ),
    }
    return _write(
        {
            "ok": bool(ingest.get("ok") and decide.get("decision")),
            "status": "ok",
            "align_root": _rel(args.align_root),
            "stage": staged,
            "geotiff_ingest": ingest,
            "decide": decide,
        }
    )


if __name__ == "__main__":
    raise SystemExit(main())
