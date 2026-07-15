#!/usr/bin/env python3
"""Write outputs/observatorio/priority_stack_scorecard.json for priorities 1–4."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.ml.product_catalog import list_products  # noqa: E402


def _load(path: Path) -> dict:
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def main() -> int:
    products = list_products()
    dual_ready = all(p.get("ready") for p in products) and len(products) >= 2
    anchors = _load(ROOT / "outputs" / "observatorio" / "anchor_scorecard.json")
    haus = _load(ROOT / "outputs" / "observatorio" / "hausdorff_multi_if.json")
    official = _load(
        ROOT / "outputs" / "observatorio" / "tobarra_20240802" / "hausdorff_official_status.json"
    )
    tobarra_proxy = _load(
        ROOT / "outputs" / "observatorio" / "tobarra_20240802" / "hausdorff_report.json"
    )

    p1 = {
        "id": "dual_product",
        "priority": 1,
        "status": "DONE" if dual_ready else "INCOMPLETE",
        "products": products,
        "cli": "python scripts/predict_spread.py --list-products",
        "docs": "docs/PRODUCTO_DUAL.md",
        "catalog": "models/catalog.json",
        "smoke_clm_v28_n20": {
            "mean_iou": 0.7128,
            "mean_copy": 0.5532,
            "delta": 0.1596,
            "note": "holdout test first 20 patches local smoke",
        },
    }

    o1 = (anchors.get("O1_multi_anchor") or {}).get("verdict", "UNKNOWN")
    o5 = (anchors.get("O5_second_grade_A") or {}).get("verdict", "UNKNOWN")
    p2 = {
        "id": "infocam_anchors",
        "priority": 2,
        "status": "TOOLING_DONE_DATA_BLOCKED",
        "O1": o1,
        "O5": o5,
        "n_confirmed": anchors.get("n_confirmed_anchors"),
        "n_in_band": anchors.get("n_in_band"),
        "n_grade_a": anchors.get("n_grade_a"),
        "anchors_file": "data/infocam_anchors.json",
        "scorecard": "outputs/observatorio/anchor_scorecard.json",
        "blocked_reason": anchors.get("blocked_reason"),
        "action_required": "INFOCAM Vp/ha for Cardoso, Hellín, La Estrella (see docs/SOLICITUD_DATOS_OBSERVATORIO.md)",
    }

    n_proxy = sum(1 for f in (haus.get("fires") or []) if f.get("status") == "OK_PROXY")
    p3 = {
        "id": "perimeter_hausdorff",
        "priority": 3,
        "status": "PROXY_DONE_OFFICIAL_BLOCKED",
        "O2_official": official.get("verdict", "UNKNOWN"),
        "o2_official_flag": bool(official.get("o2_official")),
        "temporal_proxy_fires": n_proxy,
        "tobarra_temporal": tobarra_proxy.get("summary"),
        "multi_if": "outputs/observatorio/hausdorff_multi_if.json",
        "cli": "python scripts/eval_perimeter_hausdorff.py --observed ... --mode official|temporal|kmz_footprint",
        "note": "KMZ LatLonQuad is image footprint, not fire perimeter. Official GeoJSON required for O2 GO.",
    }

    p4 = {
        "id": "ml_g1_physics15",
        "priority": 4,
        "status": "LAUNCHED_OR_QUEUED",
        "rail": "features",
        "schema": "physics15",
        "kernel": "alonsoalviraaaa/wildfire-front-training-v26-physics15",
        "script": "kaggle_job/run_unet_training_v26_physics15.py",
        "gate": "G1 IoU>=0.25 and delta>=+0.09 vs v21 baseline (0.226 / +0.076)",
        "promote_only_if": "beats G1 on same NDWS any_fire protocol",
        "transfer_note": "CLM G2 already GO via v28 (separate product)",
    }

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "title": "Priority stack 1–4 (dual + anchors + Hausdorff + physics15)",
        "priorities": [p1, p2, p3, p4],
        "honest_ceiling": {
            "O1": "PARTIAL (1 confirmed INFOCAM anchor)",
            "O2": "BLOCKED without official perimeter vector",
            "O5": "NO_GO (1× grade A)",
            "G1": "pending v26 physics15 Kaggle result",
            "G2": "GO on CLM holdout via clm_v28",
            "ops": "Tobarra grade A ratio ~0.82 vs INFOCAM 7 m/min",
        },
    }

    out = ROOT / "outputs" / "observatorio" / "priority_stack_scorecard.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print("Wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
