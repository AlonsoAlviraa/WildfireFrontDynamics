#!/usr/bin/env python3
"""One-shot: rebuild VAL lab scorecard from fit metrics_on_val (not for CI).

Honesty:
  * VAL-only U1 → recommended false, u1_val_optimistic true, u1_test_honest false.
  * Writes **VAL-only** paths (never overwrites honest TEST as "latest").
  * If an honest TEST scorecard exists, copies it to ml_scorecard_latest.json
    so DEFAULT_OUT points at TEST truth, not optimistic VAL.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "outputs" / "ml_eval" / "scorecards"
HONEST_TEST = OUT_DIR / "ml_scorecard_u1_test.json"
LATEST = OUT_DIR / "ml_scorecard_latest.json"
VAL_DATED = OUT_DIR / "ml_scorecard_val_u1_real_20260723.json"
VAL_TAGGED = OUT_DIR / "ml_scorecard_u1_val.json"


def main() -> int:
    cal_path = ROOT / "models" / "clm_ensemble" / "uncertainty_calibration_v1.json"
    cal = json.loads(cal_path.read_text(encoding="utf-8"))
    m = cal.get("metrics_on_val") or {}

    u1a = bool(m.get("u1a_selective_ge_full_minus_eps"))
    u1b = bool(m.get("beats_random_selective"))
    u1 = u1a and u1b
    val_mean = float(m.get("full_coverage_mean_iou") or 0.0)

    doc = {
        "schema": "ml_scorecard_v1",
        "product_id": "clm_ensemble_v34",
        "protocol": "clm_holdout_test_seed42_v1",
        "split": "val",
        "action": "scorecard",
        "calibrator_fit_split": "val",
        "u1_eval_split": "val",
        "tuning": {
            "mix_split": "val",
            "temperature_split": "val",
            "uncertainty_calibration_split": "val",
        },
        "primary": {
            "model_iou": val_mean,
            "n_patches": int(m.get("n_patches") or 0),
            "model_iou_split": "val",
            "model_iou_source": "eval_split_mean",
        },
        "uncertainty": {
            "ece_patch_conf": m.get("ece_patch_conf"),
            "selective_iou_at_80pct_coverage": m.get("selective_iou_at_80pct_coverage"),
            "beats_random_selective": u1b,
            "delta_vs_random": m.get("delta_vs_random"),
            "n_patches": m.get("n_patches"),
            "tau_iou": 0.5,
            "coverage": 0.8,
        },
        "gates": {
            "U1a_selective_ge_full_minus_eps": u1a,
            "U1_selective_beats_random": u1b,
            "U1b_selective_beats_random": u1b,
            "u1_val_passed": u1,
            "u1_val_lab_pass": u1,
            "u1_val_optimistic": u1,  # same-split as fit
            "u1_test_honest": False,  # VAL-only — never honest promote
            "ml_product_go": False,
            # Honest rule: VAL lab pass must NOT recommend fusion
            "allow_ml_live_in_fusion_recommended": False,
            "reasons": (
                ["u1_not_eval_on_test", "u1_val_optimistic_same_split_as_fit"]
                if u1
                else ["U1_fail"]
            ),
        },
        "allow_ml_live_in_fusion_recommended": False,
        "provenance": {
            "calibrator_path": str(cal_path.relative_to(ROOT)).replace("\\", "/"),
            "fit_data_dir": m.get("fit_data_dir"),
            "fit_split": "val",
            "calibrator_fit_split": "val",
            "u1_eval_split": "val",
            "n_patches": m.get("n_patches"),
            "device": "cpu",
            "positive_rate_iou_ge_0_5": m.get("positive_rate"),
            "catalog_holdout_test_reference": {
                "test_iou": 0.8963,
                "improvement_vs_copy_iou": 0.2545,
                "copy_baseline_iou": 0.6418,
                "model_iou_growth": 0.9071,
                "note": "Published TEST metrics; not the VAL mean IoU in primary.model_iou.",
            },
            "source": "fit_ml_uncertainty_calibration.py full VAL",
            "scorecard_role": "val_lab_optimistic_not_promote",
            "caveats": [
                "U1 computed on same VAL set used to fit calibrator (optimistic; not nested CV).",
                "allow_ml_live_in_fusion_recommended stays false until U1 on TEST with frozen cal.",
                "Production DecisionPolicy.allow_ml_live_in_fusion stays false until human promote.",
                "Catalog test IoU 0.8963 is a different split/metric surface than VAL mean IoU.",
                "ml_scorecard_latest.json is the honest TEST scorecard when present (not this VAL file).",
            ],
        },
    }

    from wildfire_front.ml.scorecard_schema import validate_ml_scorecard

    fails = validate_ml_scorecard(doc)
    doc["schema_validation"] = {"pass": len(fails) == 0, "fails": fails}

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # VAL snapshots only — never write VAL content into latest.
    val_paths = [VAL_DATED, VAL_TAGGED]
    for p in val_paths:
        p.write_text(json.dumps(doc, indent=2), encoding="utf-8")

    latest_source = None
    if HONEST_TEST.is_file():
        shutil.copyfile(HONEST_TEST, LATEST)
        latest_source = str(HONEST_TEST.relative_to(ROOT)).replace("\\", "/")
        # Annotate latest with pointer so operators know role
        latest_doc = json.loads(LATEST.read_text(encoding="utf-8"))
        prov = dict(latest_doc.get("provenance") or {})
        prov["scorecard_role"] = "honest_test_u1_default_latest"
        prov["note_latest"] = (
            "DEFAULT_OUT / ml_scorecard_latest.json mirrors honest TEST U1; "
            "VAL lab is ml_scorecard_u1_val.json / ml_scorecard_val_u1_real_*.json."
        )
        latest_doc["provenance"] = prov
        LATEST.write_text(json.dumps(latest_doc, indent=2), encoding="utf-8")
    else:
        latest_source = None

    print(
        json.dumps(
            {
                "u1_verdict": "U1_VAL_LAB_PASS" if u1 else "U1_FAIL",
                "u1a": u1a,
                "u1b": u1b,
                "allow_ml_live_in_fusion_recommended": False,
                "u1_test_honest": False,
                "u1_val_optimistic": u1,
                "ml_product_go": False,
                "metrics_on_val": m,
                "schema_ok": len(fails) == 0,
                "wrote_val": [str(p) for p in val_paths],
                "wrote_latest_from_honest_test": latest_source,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
