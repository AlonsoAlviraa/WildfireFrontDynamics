"""Re-evaluate the frozen CLM ensemble with transition, FCER, and boundary metrics."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.ml.clm_eval import evaluate_clm_weights

DEFAULT_MANIFEST = ROOT / "models" / "clm_ensemble" / "manifest.json"
DEFAULT_DATA = ROOT / "artifacts" / "clm_ndws_patches" / "holdout_v1" / "test"
DEFAULT_OUT = ROOT / "outputs" / "ml_eval" / "global_metrics_2026" / "clm_ensemble_v34.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--max-patches", type=int, default=400)
    parser.add_argument("--device", default=None)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    weights = [ROOT / value for value in manifest["members"]]
    metrics = evaluate_clm_weights(
        weights,
        args.data_dir,
        max_patches=args.max_patches,
        threshold=float(manifest.get("threshold", 0.5)),
        device=args.device,
        ensemble_mode=str(manifest.get("ensemble_mode", "mean_prob")),
        member_weights=manifest.get("member_weights"),
        temperatures=manifest.get("member_temperatures"),
    )
    aggregate = metrics["aggregate"]
    report = {
        "schema": "wfd_global_front_metrics_reeval_v1",
        "generated_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "product_id": manifest.get("id"),
        "protocol": manifest.get("protocol"),
        "split": "test",
        "action": "evaluate_frozen",
        "data_dir": str(args.data_dir).replace("\\", "/"),
        "n_patches": metrics["n_patches"],
        "members": manifest["members"],
        "member_weights": manifest.get("member_weights"),
        "member_temperatures": manifest.get("member_temperatures"),
        "threshold": metrics["threshold"],
        "primary": {
            "model_iou": metrics["model_iou"],
            "copy_baseline_iou": metrics["copy_baseline_iou"],
            "improvement_vs_copy_iou": metrics["improvement_vs_copy_iou"],
            "model_growth_transition_iou": metrics["model_growth_transition_iou"],
            "model_change_transition_iou": metrics["model_change_transition_iou"],
            "model_growth_average_precision_macro": metrics[
                "model_growth_average_precision_macro"
            ],
            "model_growth_fcer_iou": metrics["model_growth_fcer_iou"],
            "model_growth_fcer_average_precision_macro": metrics[
                "model_growth_fcer_average_precision_macro"
            ],
            "observed_growth_fcer_capture_macro": metrics[
                "observed_growth_fcer_capture_macro"
            ],
            "model_front_boundary_f1_macro": metrics["model_front_boundary_f1_macro"],
            "improvement_vs_dilated_copy_front_boundary_f1": metrics[
                "improvement_vs_dilated_copy_front_boundary_f1"
            ],
            "model_growth_fcer_ece_macro": metrics["model_growth_fcer_ece_macro"],
            "model_growth_fcer_selective_error_80_macro": metrics[
                "model_growth_fcer_selective_error_80_macro"
            ],
            "model_growth_fcer_aurc_macro": metrics["model_growth_fcer_aurc_macro"],
            "observed_growth_fcer_prevalence_macro": metrics[
                "observed_growth_fcer_prevalence_macro"
            ],
        },
        "semantics": {
            "transition": aggregate["transition_metric_semantics"],
            "fcer": aggregate["fcer_semantics"],
            "boundary": aggregate["boundary_metric_semantics"],
            "fcer_calibration": aggregate["fcer_calibration_semantics"],
            "fcer_is_not_standalone": True,
            "target_conditioned_legacy_metrics_not_used_for_claims": True,
        },
        "aggregate": aggregate,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), **report["primary"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
