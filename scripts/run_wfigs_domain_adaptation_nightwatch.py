#!/usr/bin/env python3
"""Run preregistered WFIGS adaptation, then evaluate its frozen seeds once."""

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

from wildfire_front.ml.wfigs_domain_adapt import (  # noqa: E402
    WFIGSAdaptConfig,
    adapt_frozen_rcda_on_wfigs,
)
from wildfire_front.ml.wfigs_external_eval import (  # noqa: E402
    evaluate_adapted_rcda_on_wfigs,
)
from wildfire_front.open_if.regional.base import _atomic_write_json, utc_now  # noqa: E402


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
        "--dataset-root",
        type=Path,
        default=ROOT / "outputs/ml_eval/wfigs_tensor_dataset_20260819",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "outputs/ml_eval/wfigs_domain_adaptation_20260819",
    )
    parser.add_argument("--poll-seconds", type=int, default=60)
    parser.add_argument("--max-hours", type=float, default=18.0)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    state_path = args.output / "STATE.json"
    deadline = time.monotonic() + args.max_hours * 3600.0
    data_state_path = args.dataset_root / "NIGHTWATCH_STATE.json"
    final_summary = args.rcda_work / "FINAL_SUMMARY_PAPER_METRICS.json"
    while not final_summary.is_file() or _read(data_state_path).get("phase") != "complete":
        _atomic_write_json(
            state_path,
            {
                "phase": "waiting_for_rcda_final_and_wfigs_train_val",
                "updated_at": utc_now(),
                "rcda_final_ready": final_summary.is_file(),
                "wfigs_train_val_ready": _read(data_state_path).get("phase") == "complete",
                "wfigs_test_loaded": False,
            },
        )
        if time.monotonic() >= deadline:
            raise TimeoutError("domain-adaptation prerequisites did not finish")
        time.sleep(max(10, args.poll_seconds))

    _atomic_write_json(
        state_path,
        {"phase": "training_on_wfigs_train_val_only", "updated_at": utc_now()},
    )
    adaptation = adapt_frozen_rcda_on_wfigs(
        final_summary_path=final_summary,
        wfigs_dataset_root=args.dataset_root,
        rcda_normalization_path=(
            ROOT / "data/external/rcda_net_full/protocol/normalization_train_only.json"
        ),
        output_root=args.output,
        adaptation=WFIGSAdaptConfig(),
    )
    adaptation_path = args.output / "WFIGS_ADAPTATION_VAL_ONLY.json"
    external_state_path = args.dataset_root / "EXTERNAL_NIGHTWATCH_STATE.json"
    while (
        not (args.dataset_root / "test.json").is_file()
        or _read(external_state_path).get("phase") != "complete"
    ):
        _atomic_write_json(
            state_path,
            {
                "phase": "adapted_recipe_frozen_waiting_for_wfigs_test",
                "updated_at": utc_now(),
                "adaptation_counts": adaptation["counts"],
                "wfigs_test_loaded": False,
            },
        )
        if time.monotonic() >= deadline:
            raise TimeoutError("WFIGS TEST campaign did not finish")
        time.sleep(max(10, args.poll_seconds))

    result_path = args.output / "WFIGS_ADAPTED_TEST_EVAL.json"
    result = evaluate_adapted_rcda_on_wfigs(
        adaptation_summary_path=adaptation_path,
        wfigs_dataset_root=args.dataset_root,
        rcda_normalization_path=(
            ROOT / "data/external/rcda_net_full/protocol/normalization_train_only.json"
        ),
        geometry_baseline_path=(
            ROOT / "data/open_if/wfigs_history_2020_2026/ml/GEOMETRY_BASELINE.json"
        ),
        output_path=result_path,
    )
    final = {
        "phase": "complete",
        "status": "complete",
        "updated_at": utc_now(),
        "wfigs_test_loaded_after_recipe_freeze": True,
        "result": str(result_path),
        "summary": result["summary"],
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
