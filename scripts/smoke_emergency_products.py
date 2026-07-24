#!/usr/bin/env python3
"""Single emergency smoke: dual ML ready + CLM Δ>0 + Tobarra ops pack + envelope."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.ml.ndws_metrics import evaluate_sample  # noqa: E402
from wildfire_front.ml.product_catalog import (  # noqa: E402
    list_products,
    load_predictor_for_product,
)


def main() -> int:
    report: dict = {"ok": True, "checks": {}}

    products = list_products()
    report["products"] = products
    ready = {p["id"]: bool(p.get("ready")) for p in products}
    # Require dual core + ensemble when present in catalog
    need = {"ndws_v21", "clm_v28"}
    report["checks"]["dual_ready"] = need.issubset(set(ready)) and all(ready.get(k) for k in need)
    ens_key = "clm_ensemble_v34" if "clm_ensemble_v34" in ready else "clm_ensemble_v30"
    if ens_key in ready:
        report["checks"]["ensemble_ready"] = bool(ready[ens_key])
        if not ready[ens_key]:
            report["ok"] = False
    if not report["checks"]["dual_ready"]:
        report["ok"] = False

    # CLM smoke (prefer ensemble, always also check v28)
    test_dir = ROOT / "artifacts" / "clm_ndws_patches" / "holdout_v1" / "test"
    paths = sorted(test_dir.glob("*.npz"))[:12]
    if not paths:
        report["checks"]["clm_delta"] = False
        report["ok"] = False
        report["clm_error"] = "no holdout test patches"
    else:
        for pid in ("clm_v28", "clm_ensemble_v34", "clm_ensemble_v30"):
            if pid not in ready or not ready.get(pid):
                continue
            pred = load_predictor_for_product(pid)
            ious, copies = [], []
            for path in paths:
                with np.load(path) as d:
                    pp = pred.predict(d["sequence"], d["current_fire"])
                    s = evaluate_sample(pp, d["current_fire"], d["target_fire"])
                    ious.append(s["model_full"].iou)
                    copies.append(s["copy_full"].iou)
            delta = float(np.mean(np.array(ious) - np.array(copies)))
            report["checks"][f"{pid}_mean_delta"] = delta
            report["checks"][f"{pid}_delta_positive"] = delta > 0
            if delta <= 0:
                report["ok"] = False
        # backward-compatible key
        report["checks"]["clm_mean_delta"] = report["checks"].get("clm_v28_mean_delta")
        report["checks"]["clm_delta_positive"] = report["checks"].get(
            "clm_v28_delta_positive", False
        )

    # Tobarra ops
    pack = ROOT / "outputs" / "observatorio" / "tobarra_20240802"
    ops_path = pack / "operational_metrics.json"
    report["checks"]["tobarra_ops_present"] = ops_path.is_file()
    if ops_path.is_file():
        ops = json.loads(ops_path.read_text(encoding="utf-8"))
        report["tobarra"] = {
            "quality_grade": ops.get("quality_grade"),
            "ros": ops.get("speed_median_m_min"),
            "speed_status": ops.get("speed_status"),
            "has_sector_ros": "sector_ros" in ops,
            "has_envelope": "short_horizon_envelope" in ops
            or (pack / "emergency_envelope.json").is_file(),
        }
        if ops.get("quality_grade") is None and ops.get("speed_status") is None:
            report["ok"] = False
        # second IF
        for other in ("cardoso_2025", "hellin_2024", "brazatortas_2025"):
            op = ROOT / "outputs" / "observatorio" / other / "operational_metrics.json"
            if op.is_file():
                o = json.loads(op.read_text(encoding="utf-8"))
                report["second_if"] = {
                    "fire_id": other,
                    "quality_grade": o.get("quality_grade"),
                    "ros": o.get("speed_median_m_min"),
                    "has_sector_ros": "sector_ros" in o,
                }
                break
    else:
        report["ok"] = False

    report["emergency_ml_product"] = "clm_v28"
    report["ndws_note"] = "ndws_v21 research baseline only — not emergency primary"
    report["ops_product"] = "front_dynamics_v1"

    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
