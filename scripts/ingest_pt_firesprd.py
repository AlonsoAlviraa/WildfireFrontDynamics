#!/usr/bin/env python3
"""Use one PT-FireSprd L1 fire: inventory → aligned GeoTIFF → ingest → decide.

python scripts/ingest_pt_firesprd.py
python scripts/ingest_pt_firesprd.py --fire Gouveia_10082015
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.open_if.pt_firesprd import (  # noqa: E402
    default_extracted,
    inventory_l1_pack,
    materialize_geotiff_scenes,
    run_geotiff_ingest,
    select_ingest_fire,
    write_decide_open_pack,
)
from wildfire_front.product.decide_service import decide_from_request  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Ingest one PT-FireSprd L1 fire")
    ap.add_argument("--fire", default=None, help="Folder name, e.g. Gouveia_10082015")
    ap.add_argument(
        "--out",
        type=Path,
        default=ROOT / "outputs" / "open_if" / "best_fires_e2e" / "pt_firesprd",
    )
    ap.add_argument("--max-scenes", type=int, default=8)
    args = ap.parse_args(argv)

    extracted = default_extracted(ROOT)
    if not extracted.is_dir():
        print(
            "error: PT-FireSprd not extracted. Run scripts/download_open_ros_packs.py",
            file=sys.stderr,
        )
        return 1

    inv = inventory_l1_pack(extracted)
    chosen = None
    if args.fire:
        for row in inv["fires"]:
            if row.get("fire_id") == args.fire:
                chosen = row
                break
        if chosen is None:
            print(f"error: fire not found: {args.fire}", file=sys.stderr)
            return 2
    else:
        chosen = select_ingest_fire(inv["fires"])
    if chosen is None:
        report = {
            "ok": False,
            "reason": "no_r1_fire",
            "n_shapefiles": inv["n_shapefiles"],
            "n_fires_r1": inv["n_fires_r1"],
        }
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "ingest_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 1

    shp = Path(chosen["shp"])
    ingest_dir = args.out / "geotiff" / chosen["fire_id"]
    mat = materialize_geotiff_scenes(shp, ingest_dir, max_scenes=args.max_scenes)
    ingest = None
    decide = None
    if mat.get("ok"):
        ingest = run_geotiff_ingest(ingest_dir, fire_id=chosen["fire_id"])
        open_pack = args.out / "open_pack" / chosen["fire_id"]
        write_decide_open_pack(ingest_dir, open_pack, fire_id=chosen["fire_id"])
        work_dir = args.out / "decide_work" / chosen["fire_id"]
        work_dir.mkdir(parents=True, exist_ok=True)
        card = decide_from_request(
            {
                "event_id": chosen["fire_id"],
                "open_pack": str(open_pack),
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
            "open_pack": str(open_pack.relative_to(ROOT)).replace("\\", "/"),
            "note": (
                "decide source id may read open_cems_perimeter (legacy loader). "
                "Pack is PT-FireSprd L1 proxy, not CEMS."
            ),
        }

    report = {
        "ok": bool(mat.get("ok") and (ingest or {}).get("ok")),
        "chosen": {
            "fire_id": chosen.get("fire_id"),
            "year": chosen.get("year"),
            "n_dated_scenes": chosen.get("n_dated_scenes"),
            "meets_geotiff_r1": chosen.get("meets_geotiff_r1"),
        },
        "n_fires_r1": inv["n_fires_r1"],
        "n_shapefiles": inv["n_shapefiles"],
        "materialize": {
            "ok": mat.get("ok"),
            "reason": mat.get("reason"),
            "n_scenes": (mat.get("meta") or {}).get("n_scenes"),
            "aligned": (mat.get("meta") or {}).get("aligned"),
            "crs": (mat.get("meta") or {}).get("crs"),
        },
        "geotiff_ingest": ingest,
        "decide": decide,
        "not_product_ros": True,
        "not_official_ha": True,
        "not_tactical_dispatch": True,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    dest = args.out / "ingest_report.json"
    dest.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))
    print(f"wrote {dest}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
