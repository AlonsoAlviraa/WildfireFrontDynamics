"""Audit the staged FireBench Caldor benchmark without changing product flags.

The audit distinguishes the observational Caldor benchmark from the synthetic
FireBench simulation corpus, checks temporal usability, and fails closed on
mixed/unknown component rights.
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

from wildfire_front.open_if.external_ros import inventory_caldor_kml  # noqa: E402

DEFAULT_PACK = ROOT / "data" / "external" / "firebench" / "caldor_2021" / "v2026.1"
DEFAULT_OUT = ROOT / "outputs" / "data_audits" / "firebench_caldor_2026_1.json"

EXPECTED_OPEN_NOTICES = frozenset({"calfire.txt", "LANDFIRE.txt", "mtbs.txt", "NIFC.txt", "ravg.txt"})


def _h5_inventory(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"status": "missing", "path": path.as_posix()}
    result: dict[str, Any] = {
        "status": "present_not_inspected",
        "path": path.as_posix(),
        "bytes": path.stat().st_size,
    }
    try:
        import h5py
    except ImportError:
        result["reason"] = "h5py_not_installed"
        return result
    with h5py.File(path, "r") as dataset:
        result.update(
            {
                "status": "inspected",
                "root_groups": sorted(dataset.keys()),
                "root_attributes": {
                    str(key): str(value) for key, value in dataset.attrs.items()
                },
                "polygon_count": len(dataset.get("polygons", {})),
                "weather_station_count": len(dataset.get("time_series", {})),
                "spatial_layer_count": len(dataset.get("spatial_2d", {})),
            }
        )
    return result


def audit_firebench_caldor(pack: Path) -> dict[str, Any]:
    pack = Path(pack)
    kml = inventory_caldor_kml(pack / "kml")
    notice_dir = pack / "DATA_LICENSES"
    present_notices = (
        {path.name for path in notice_dir.glob("*.txt")} if notice_dir.is_dir() else set()
    )
    h5 = _h5_inventory(pack / "Caldor.h5")
    weather_present = int(h5.get("weather_station_count", 0)) > 0
    rights_gaps = []
    if not EXPECTED_OPEN_NOTICES.issubset(present_notices):
        rights_gaps.append(
            "missing_expected_notices:"
            + ",".join(sorted(EXPECTED_OPEN_NOTICES - present_notices))
        )
    if weather_present and not any("synoptic" in name.lower() for name in present_notices):
        rights_gaps.append("synoptic_weather_notice_missing")

    temporal_ok = bool(kml.get("n_pairs_12_to_36h", 0))
    return {
        "schema": "wfd_firebench_caldor_audit_v1",
        "dataset": "FireBench: 2021 Caldor Benchmarks for Fire Models",
        "version": "2026.1",
        "source": "https://zenodo.org/records/19041000",
        "newer_version": "https://zenodo.org/records/20279621",
        "pack": pack.as_posix(),
        "task_class": "observational_fire_model_benchmark",
        "not_the_synthetic_firebench_corpus": True,
        "kml": kml,
        "h5": h5,
        "rights": {
            "notices_present": sorted(present_notices),
            "gaps": rights_gaps,
            "commercial_training": "blocked" if rights_gaps else "review_required",
            "redistribution": "blocked" if rights_gaps else "review_required",
        },
        "readiness": {
            "temporal_pairs_available": temporal_ok,
            "next_day_tensor_ready": False,
            "requires_geometry_raster_bridge": True,
            "requires_covariate_alignment": True,
            "requires_rights_resolution": bool(rights_gaps),
            "eligible_for_product_promotion": False,
        },
        "pass_for_lab_bridge": bool(kml.get("ok")) and temporal_ok,
        "pass_for_training": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, default=DEFAULT_PACK)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--strict", action="store_true", help="exit 2 while rights gaps remain")
    args = parser.parse_args()
    report = audit_firebench_caldor(args.pack)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(args.out), "pass_for_lab_bridge": report["pass_for_lab_bridge"], "rights": report["rights"]}, ensure_ascii=False))
    if args.strict and report["rights"]["gaps"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
