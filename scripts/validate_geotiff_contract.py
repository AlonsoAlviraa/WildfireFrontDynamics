#!/usr/bin/env python3
"""E4 — Smoke-validate GeoTIFF against multi-provider input contract.

Checks (per file): readable · CRS · georef · resolution_m · timestamp ·
optional sidecar platform/provider_id.

Exit 0 if all files accepted or review-only; exit 2 if any rejected.
Does not invent timestamps or CRS.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TIFF_EXTENSIONS = {".tif", ".tiff"}


def _load_sidecar(tif: Path) -> dict[str, Any]:
    for cand in (
        tif.with_suffix(".json"),
        tif.with_name(tif.stem + "_meta.json"),
        tif.parent / "metadata.json",
    ):
        if cand.is_file():
            try:
                data = json.loads(cand.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(data, dict):
                return data
    return {}


def validate_one(path: Path) -> dict[str, Any]:
    from wildfire_front.ingestion.geotiff import infer_timestamp

    path = Path(path)
    report: dict[str, Any] = {
        "path": str(path).replace("\\", "/"),
        "status": "accepted",
        "reasons": [],
        "platform": None,
        "provider_id": None,
        "timestamp_utc": None,
        "crs": None,
        "resolution_m": None,
        "coordinate_system": None,
        "width": None,
        "height": None,
    }
    if not path.is_file():
        report["status"] = "rejected"
        report["reasons"].append("file_not_found")
        return report

    sidecar = _load_sidecar(path)
    report["platform"] = sidecar.get("platform")
    report["provider_id"] = sidecar.get("provider_id") or sidecar.get("sensor_id")

    try:
        import rasterio
        from affine import Affine

        with rasterio.open(path) as ds:
            report["width"] = ds.width
            report["height"] = ds.height
            report["crs"] = str(ds.crs) if ds.crs else None
            if ds.crs is None or ds.transform == Affine.identity():
                report["status"] = "rejected"
                report["reasons"].append("no_georeferencing")
            else:
                report["coordinate_system"] = (
                    "projected_metric" if ds.crs.is_projected else "geographic"
                )
                if ds.crs.is_projected:
                    report["resolution_m"] = float(
                        (abs(ds.transform.a) + abs(ds.transform.e)) / 2.0
                    )
                else:
                    report["reasons"].append("crs_not_projected_metric_ros_abstain")
                    if report["status"] == "accepted":
                        report["status"] = "review"
    except Exception as exc:  # noqa: BLE001 — contract smoke
        report["status"] = "rejected"
        report["reasons"].append(f"unreadable:{type(exc).__name__}")
        return report

    ts = infer_timestamp(path) or str(sidecar.get("timestamp_utc") or "")
    report["timestamp_utc"] = ts or None
    if not ts:
        report["reasons"].append("timestamp_missing")
        if report["status"] == "accepted":
            report["status"] = "review"

    if report["platform"] is None and report["provider_id"] is None:
        report["reasons"].append("provider_platform_unspecified")
        # soft — does not by itself reject

    if not report["reasons"] and report["status"] == "accepted":
        report["reasons"].append("ok")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate GeoTIFF input contract (E4).")
    parser.add_argument("paths", nargs="+", type=Path, help="GeoTIFF file(s) or directory")
    parser.add_argument("--json", action="store_true", help="JSON array output")
    args = parser.parse_args(argv)

    files: list[Path] = []
    for p in args.paths:
        p = Path(p)
        if p.is_dir():
            files.extend(sorted(x for x in p.rglob("*") if x.suffix.lower() in TIFF_EXTENSIONS))
        else:
            files.append(p)
    if not files:
        print("error: no GeoTIFF files found", file=sys.stderr)
        return 1

    reports = [validate_one(f) for f in files]
    rejected = sum(1 for r in reports if r["status"] == "rejected")
    review = sum(1 for r in reports if r["status"] == "review")
    accepted = sum(1 for r in reports if r["status"] == "accepted")

    if args.json:
        print(json.dumps({"n": len(reports), "reports": reports}, indent=2))
    else:
        for r in reports:
            print(
                f"{r['status']:8}  crs={r.get('crs') or '—'}  "
                f"res_m={r.get('resolution_m')}  ts={r.get('timestamp_utc') or '—'}  "
                f"{r['path']}"
            )
            for reason in r.get("reasons") or []:
                print(f"           reason: {reason}")
        print(
            f"summary: accepted={accepted} review={review} rejected={rejected} total={len(reports)}"
        )
        print(
            "invalid → ingest reject/review; Decision Card field_ops often ABSTAIN without ops ROS "
            "(see docs/GEOTIFF_INPUT_CONTRACT.md)"
        )

    return 2 if rejected else 0


if __name__ == "__main__":
    raise SystemExit(main())
