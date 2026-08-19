#!/usr/bin/env python3
"""After all recipes are frozen, materialize WFIGS TEST and evaluate once."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.ml.wfigs_external_eval import (  # noqa: E402
    evaluate_frozen_rcda_on_wfigs,
)
from wildfire_front.ml.wfigs_tensor_dataset import WFIGSTensorDatasetBuilder  # noqa: E402
from wildfire_front.open_if.regional.base import _atomic_write_json, utc_now  # noqa: E402
from wildfire_front.open_if.regional.wfigs_campaign import WFIGSTensorCampaign  # noqa: E402


def _read(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rcda-work",
        type=Path,
        default=ROOT / "outputs/ml_eval/rcda_paper_nightwatch_20260819",
    )
    parser.add_argument(
        "--history-root",
        type=Path,
        default=ROOT / "data/open_if/wfigs_history_2020_2026",
    )
    parser.add_argument(
        "--train-root",
        type=Path,
        default=ROOT / "outputs/ml_eval/wfigs_training_campaign_20260819",
    )
    parser.add_argument(
        "--validation-root",
        type=Path,
        default=ROOT / "outputs/ml_eval/wfigs_validation_campaign_20260819",
    )
    parser.add_argument(
        "--test-root",
        type=Path,
        default=ROOT / "outputs/ml_eval/wfigs_test_campaign_20260819",
    )
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=ROOT / "outputs/ml_eval/wfigs_tensor_dataset_20260819",
    )
    parser.add_argument("--test-events-per-region", type=int, default=3)
    parser.add_argument("--poll-seconds", type=int, default=60)
    parser.add_argument("--max-hours", type=float, default=14.0)
    args = parser.parse_args()
    state_path = args.dataset_root / "EXTERNAL_NIGHTWATCH_STATE.json"
    deadline = time.monotonic() + args.max_hours * 3600.0
    rcda_state_path = args.rcda_work / "STATE.json"
    data_state_path = args.dataset_root / "NIGHTWATCH_STATE.json"
    while True:
        rcda_state = _read(rcda_state_path)
        data_state = _read(data_state_path)
        rcda_ready = rcda_state.get("phase") == "complete" and rcda_state.get("status") == "complete"
        data_ready = data_state.get("phase") == "complete"
        _atomic_write_json(
            state_path,
            {
                "phase": (
                    "waiting_after_recoverable_upstream_error"
                    if rcda_state.get("status") == "error"
                    or data_state.get("status") == "error"
                    else "waiting_for_frozen_rcda_and_wfigs_train_val"
                ),
                "updated_at": utc_now(),
                "rcda_ready": rcda_ready,
                "wfigs_train_val_ready": data_ready,
                "rcda_status": rcda_state.get("status"),
                "wfigs_data_status": data_state.get("status"),
                "test_materialized": False,
                "test_evaluated": False,
            },
        )
        if rcda_ready and data_ready:
            break
        if time.monotonic() >= deadline:
            raise TimeoutError("external-validation prerequisites did not finish")
        time.sleep(max(10, args.poll_seconds))

    _atomic_write_json(
        state_path,
        {"phase": "materializing_untouched_wfigs_test", "updated_at": utc_now()},
    )
    test_campaign = WFIGSTensorCampaign(
        history_root=args.history_root,
        output_root=args.test_root,
        split="test",
        events_per_region=args.test_events_per_region,
        size=256,
        resolution_m=60.0,
        min_valid_fraction=0.70,
    ).run()
    _atomic_write_json(
        state_path,
        {
            "phase": "building_dataset_with_frozen_test",
            "updated_at": utc_now(),
            "test_materialized": True,
            "test_evaluated": False,
            "test_counts": test_campaign["counts"],
        },
    )
    WFIGSTensorDatasetBuilder(
        inventory_paths=[
            args.train_root / "INVENTORY.json",
            args.validation_root / "INVENTORY.json",
            args.test_root / "INVENTORY.json",
        ],
        output_root=args.dataset_root,
    ).build()
    external_path = args.dataset_root / "WFIGS_EXTERNAL_EVAL.json"
    external = evaluate_frozen_rcda_on_wfigs(
        final_summary_path=args.rcda_work / "FINAL_SUMMARY_PAPER_METRICS.json",
        wfigs_dataset_root=args.dataset_root,
        rcda_normalization_path=(
            ROOT / "data/external/rcda_net_full/protocol/normalization_train_only.json"
        ),
        geometry_baseline_path=(
            args.history_root / "ml/GEOMETRY_BASELINE.json"
        ),
        output_path=external_path,
    )
    final = {
        "phase": "complete",
        "status": "complete",
        "updated_at": utc_now(),
        "test_materialized": True,
        "test_evaluated": True,
        "external_report": str(external_path),
        "summary": external["summary"],
    }
    _atomic_write_json(state_path, final)
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/refresh_rcda_paper_console.py")],
        cwd=ROOT,
        check=True,
    )
    print(json.dumps(final, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
