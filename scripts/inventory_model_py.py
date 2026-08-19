#!/usr/bin/env python3
"""Build the model-path audit inventory for the 2026-08-16 mega-goal.

The path list is deliberately explicit: it is the machine-readable mirror of
section 3, waves 1--5, in ``MEGA_GOAL_MODEL_DEBUG_MINPERF_2026-08-16.md``.
An initial run emits ``pending`` rows.  A closing run consumes a JSON mapping
whose values contain a final ``status`` and one-line ``note``.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "outputs" / "ml_eval" / "mega_goal_model" / "INVENTORY.json"
FINAL_STATUSES = {"audited_ok", "bug_fixed", "out_of_perf", "blocked"}

WAVES: dict[str, tuple[str, ...]] = {
    "wave_1": (
        "wildfire_front/open_if/latam_au.py",
        "scripts/run_latam_au_complete_model_iou.py",
        "scripts/run_latam_au_experimental_model_iou.py",
        "wildfire_front/ml/feature_schema.py",
        "wildfire_front/ml/dataset.py",
        "wildfire_front/ml/normalization.py",
        "wildfire_front/ml/types.py",
    ),
    "wave_2": (
        "wildfire_front/ml/unet_train.py",
        "wildfire_front/ml/train.py",
        "wildfire_front/ml/spread_predictor.py",
        "wildfire_front/ml/physics.py",
        "wildfire_front/ml/weights.py",
        "wildfire_front/ml/export_torchscript.py",
        "wildfire_front/models.py",
    ),
    "wave_3": (
        "wildfire_front/ml/clm_eval.py",
        "wildfire_front/ml/u1_eval.py",
        "wildfire_front/ml/ndws_metrics.py",
        "wildfire_front/ml/reliability_metrics.py",
        "wildfire_front/ml/nested_cv.py",
        "wildfire_front/ml/scorecard_schema.py",
        "wildfire_front/ml/protocol_rails.py",
        "wildfire_front/evaluation.py",
        "wildfire_front/metrics_protocol.py",
    ),
    "wave_4": (
        "scripts/fill_latam_au_ndws_covariates.py",
        "scripts/warp_latam_au_s2_to_cems.py",
        "scripts/adapt_latam_au_to_ndws_patches.py",
        "scripts/export_latam_au_ml_patches.py",
        "scripts/align_latam_au_era5.py",
        "scripts/build_latam_au_lofo_folds.py",
        "scripts/eval_latam_au_domain_gap.py",
        "scripts/geotiff_to_training_patches.py",
        "scripts/preprocess_clm_to_ndws_npz.py",
        "wildfire_front/open_if/stac_s2.py",
        "wildfire_front/open_if/dnbr.py",
        "wildfire_front/ml/cloud_train.py",
    ),
    "wave_5": (
        "tests/test_latam_au_code_improve.py",
        "tests/test_latam_au_product_e2e.py",
        "tests/test_latam_au_campaign.py",
        "tests/test_latam_au_p1_p2.py",
        "tests/test_latam_au_residual_backlog.py",
        "tests/test_unet_model.py",
        "tests/test_u1_honest_eval.py",
        "tests/test_ndws_metrics.py",
        "tests/test_ml_pipeline.py",
        "tests/test_ml_focus_protocol.py",
    ),
}


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_statuses(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError("status file must be a JSON object keyed by repository path")
    return doc


def build_inventory(statuses: dict[str, dict[str, Any]], *, final: bool) -> dict[str, Any]:
    expected = {path for paths in WAVES.values() for path in paths}
    extra = sorted(set(statuses) - expected)
    if extra:
        raise ValueError(f"status file contains paths outside section 3: {extra}")

    rows: list[dict[str, Any]] = []
    for wave, paths in WAVES.items():
        for rel in paths:
            supplied = statuses.get(rel) or {}
            exists = (ROOT / rel).is_file()
            status = str(supplied.get("status") or "pending")
            note = str(supplied.get("note") or ("awaiting audit" if exists else "path missing"))
            if "\n" in note or "\r" in note:
                raise ValueError(f"note must be one line: {rel}")
            if final and status not in FINAL_STATUSES:
                raise ValueError(f"non-final status for {rel}: {status}")
            if not final and status not in FINAL_STATUSES | {"pending"}:
                raise ValueError(f"invalid status for {rel}: {status}")
            rows.append(
                {
                    "wave": wave,
                    "path": rel,
                    "exists": exists,
                    "status": status,
                    "note": note,
                }
            )

    return {
        "schema": "wfd_mega_goal_model_inventory_v1",
        "goal_id": "MEGA_GOAL_MODEL_DEBUG_MINPERF_2026-08-16",
        "generated_at_utc": _utc_now(),
        "source": "docs/MEGA_GOAL_MODEL_DEBUG_MINPERF_2026-08-16.md#3-cada-py--inventario-obligatorio",
        "n_rows": len(rows),
        "n_pending": sum(row["status"] == "pending" for row in rows),
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status-file", type=Path)
    parser.add_argument("--final", action="store_true", help="reject pending or unknown statuses")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    inventory = build_inventory(_load_statuses(args.status_file), final=bool(args.final))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.out} rows={inventory['n_rows']} pending={inventory['n_pending']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
