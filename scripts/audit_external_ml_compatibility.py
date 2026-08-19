"""Build an evidence-based compatibility matrix for external wildfire packs."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "docs" / "EXTERNAL_ML_COMPATIBILITY_AUDIT.json"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def build_audit(root: Path = ROOT) -> dict[str, Any]:
    caldor_meta = _read_json(
        root / "data/open_if/external_bridge/US_FIREBENCH_CALDOR_2021/meta.json"
    )
    caldor_channels = _read_json(root / "docs/FIREBENCH_CALDOR_CHANNEL_AUDIT.json")
    pt_meta = _read_json(
        root
        / "outputs/open_if/best_fires_e2e/pt_firesprd/geotiff"
        / "SaoJoaoPesqueira_10072020/meta.json"
    )
    latam = _read_json(
        root / "outputs/ml_eval/latam_au_complete_iou/complete_proxy_model_iou.json"
    )

    latam_pairs = [
        pair
        for pack in latam.get("packs") or []
        for pair in pack.get("pairs") or []
        if pair.get("pair_class") == "usable"
        and pair.get("complete_proxy_model_iou") is not None
    ]
    return {
        "schema": "wfd_external_ml_compatibility_audit_v1",
        "generated_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "frozen_model": "clm_ensemble_v34_legacy17_plus_prev_fire",
        "packs": [
            {
                "pack_id": "US_FIREBENCH_CALDOR_2021",
                "region": "us",
                "label_temporal_compatible": int(
                    caldor_meta.get("n_pairs_12_to_36h") or 0
                )
                > 0,
                "n_observations": int(caldor_meta.get("n_observations") or 0),
                "n_temporal_pairs_12_to_36h": int(
                    caldor_meta.get("n_pairs_12_to_36h") or 0
                ),
                "input_tensor_semantic_compatible": False,
                "rights_evaluation_in_place": bool(
                    (caldor_meta.get("rights") or {}).get("evaluation_allowed_in_place")
                ),
                "rights_training": False,
                "model_inference_allowed": False,
                "sealed_model_iou_allowed": False,
                "allowed_now": ["geometry_evaluation", "label_pair_analysis"],
                "blockers": [
                    "legacy17 covariates incomplete",
                    "station weather is restricted and not gridded",
                    "Synoptic license notice missing",
                ],
                "evidence": {
                    "channel_audit_status": caldor_channels.get("status"),
                    "n_compatible_channels": caldor_channels.get(
                        "n_compatible_channels"
                    ),
                },
            },
            {
                "pack_id": "PT_FIRESPRD_SAO_JOAO_PESQUEIRA_2020",
                "region": "pt",
                "label_temporal_compatible": bool(
                    (pt_meta.get("contract") or {}).get("meets_geotiff_r1")
                ),
                "n_observations": int(pt_meta.get("n_scenes") or 0),
                "input_tensor_semantic_compatible": False,
                "rights_evaluation_in_place": True,
                "rights_training": True,
                "model_inference_allowed": False,
                "sealed_model_iou_allowed": False,
                "allowed_now": ["geometry_evaluation", "label_progression_research"],
                "blockers": [
                    "no legacy17 covariate stack",
                    "source timestamp timezone unspecified",
                    "weather join cannot be audited until timezone is resolved",
                ],
                "evidence": {
                    "license_id": pt_meta.get("license_id"),
                    "aligned": pt_meta.get("aligned"),
                    "timestamp_tz": pt_meta.get("timestamp_tz"),
                    "not_verified_utc": pt_meta.get("not_verified_utc"),
                },
            },
            {
                "pack_id": "LATAM_AU_EMSR_REAL_PROXY",
                "region": "latam_au",
                "label_temporal_compatible": len(latam_pairs) > 0,
                "n_temporal_pairs_used": len(latam_pairs),
                "input_tensor_shape_compatible": True,
                "input_tensor_semantic_compatible": False,
                "model_inference_allowed": True,
                "model_inference_scope": "exploratory_proxy_only",
                "sealed_model_iou_allowed": False,
                "allowed_now": ["exploratory_proxy_benchmark"],
                "blockers": [
                    "not an NDWS-native stack",
                    "weather is a point-derived spatially constant field",
                    "proxy benchmark has no sealed transfer protocol",
                ],
                "evidence": {
                    "pack_macro_model_iou": latam.get(
                        "mean_complete_proxy_model_iou"
                    ),
                    "pack_macro_copy_iou": latam.get("mean_copy_baseline_iou"),
                    "pack_macro_delta_vs_copy": latam.get("mean_delta_vs_copy"),
                    "pair_macro_model_iou": latam.get(
                        "pair_macro_complete_proxy_model_iou"
                    ),
                    "pair_macro_copy_iou": latam.get(
                        "pair_macro_copy_baseline_iou"
                    ),
                    "pair_macro_delta_vs_copy": latam.get(
                        "pair_macro_delta_vs_copy"
                    ),
                    "n_pairs_beating_copy": latam.get("n_pairs_beating_copy"),
                },
            },
        ],
        "policy": {
            "neutral_or_zero_filled_covariates_are_model_incompatible": True,
            "post_fire_outcomes_are_forbidden_as_inputs": ["MTBS", "RAVG"],
            "proxy_iou_must_not_be_reported_as_sealed_transfer_iou": True,
            "model_iou_requires_real_t0_available_inputs_and_real_t1_labels": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    report = build_audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "packs": report["packs"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
