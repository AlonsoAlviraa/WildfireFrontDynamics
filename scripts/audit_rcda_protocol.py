"""Audit RCDA-Net public samples and upstream evaluation protocol."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SAMPLE = ROOT / "data/external/rcda_net_public_sample"
DEFAULT_OUTPUT = ROOT / "docs/RCDA_NET_PROTOCOL_AUDIT.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def audit_sample(sample_root: Path) -> dict[str, Any]:
    sample_root = Path(sample_root)
    meta_path = sample_root / "meta.json"
    meta = (
        json.loads(meta_path.read_text(encoding="utf-8"))
        if meta_path.is_file()
        else {}
    )
    rows: list[dict[str, Any]] = []
    for input_path in sorted((sample_root / "inputs").glob("*.npy")):
        label_path = sample_root / "labels" / input_path.name
        if not label_path.is_file():
            continue
        inputs = np.load(input_path, allow_pickle=False)
        label = np.load(label_path, allow_pickle=False)
        if inputs.shape != (12, 256, 256) or label.shape != (256, 256):
            rows.append(
                {
                    "file": input_path.name,
                    "ok": False,
                    "input_shape": list(inputs.shape),
                    "label_shape": list(label.shape),
                }
            )
            continue
        previous = inputs[0] > 0.5
        next_extent = label > 0.5
        overlap = int(np.logical_and(previous, next_extent).sum())
        previous_count = int(previous.sum())
        next_count = int(next_extent.sum())
        derived_increment = next_extent.astype(np.int8) - previous.astype(np.int8)
        weather_constant = [
            bool(np.nanmin(inputs[channel]) == np.nanmax(inputs[channel]))
            for channel in range(6, 12)
        ]
        rows.append(
            {
                "file": input_path.name,
                "ok": True,
                "input_sha256": _sha256(input_path),
                "label_sha256": _sha256(label_path),
                "previous_positive_pixels": previous_count,
                "label_positive_pixels": next_count,
                "previous_retained_fraction": (
                    overlap / previous_count if previous_count else 1.0
                ),
                "new_growth_pixels": int((derived_increment > 0).sum()),
                "negative_after_upstream_subtraction": int(
                    (derived_increment < 0).sum()
                ),
                "all_six_weather_channels_spatially_constant": all(
                    weather_constant
                ),
            }
        )

    valid = [row for row in rows if row.get("ok")]
    expected_hashes = meta.get("files") or {}
    hashes_match = all(
        row.get("input_sha256") == expected_hashes.get(f"inputs/{row['file']}")
        and row.get("label_sha256") == expected_hashes.get(f"labels/{row['file']}")
        for row in valid
    )
    cumulative_labels = bool(valid) and all(
        float(row["previous_retained_fraction"]) == 1.0 for row in valid
    )
    return {
        "schema": "wfd_rcda_protocol_audit_v1",
        "generated_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "ok": bool(valid) and hashes_match,
        "sample_scope": len(valid),
        "sample_hashes_match_manifest": hashes_match,
        "sample_rows": rows,
        "label_semantics": {
            "zenodo_description": "increment_mask",
            "observed_public_sample": (
                "next_cumulative_extent" if cumulative_labels else "ambiguous"
            ),
            "upstream_loader_operation": "label_minus_input_channel_0",
            "subtraction_produces_binary_growth_on_public_sample": bool(valid)
            and all(int(row["negative_after_upstream_subtraction"]) == 0 for row in valid),
            "documentation_and_bytes_disagree": cumulative_labels,
        },
        "protocol_findings": {
            "train_script_uses_test_every_epoch": True,
            "early_stopping_selects_best_epoch_on_test": True,
            "eval_script_selects_threshold_on_test": True,
            "separate_validation_split_present": False,
            "normalization_extrema_provenance_documented": False,
            "event_uid_disjointness_train_test_verified": False,
            "published_test_result_is_sealed": False,
        },
        "wfd_compatibility": {
            "same_task_incremental_growth": True,
            "same_input_schema": False,
            "rcda_channels": 12,
            "wfd_legacy_channels_plus_previous_fire": 18,
            "direct_weight_transfer_allowed": False,
            "numeric_comparison_allowed": False,
        },
        "required_reproduction_protocol": [
            "split by UID fire event before patch sampling",
            "create disjoint TRAIN, VAL and TEST event groups",
            "fit normalization and choose threshold on TRAIN/VAL only",
            "run TEST once with frozen epoch and threshold",
            "report copy, dilated-copy, transition IoU, AP, FCER and boundary metrics",
            "publish train/val/test UID lists and per-event scores",
        ],
        "sources": {
            "dataset": "https://zenodo.org/records/16641619",
            "dataset_loader": "https://raw.githubusercontent.com/hxxAlways/RCDA-Net/main/dataset.py",
            "train": "https://raw.githubusercontent.com/hxxAlways/RCDA-Net/main/train.py",
            "eval": "https://raw.githubusercontent.com/hxxAlways/RCDA-Net/main/eval.py",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample-root", type=Path, default=DEFAULT_SAMPLE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = audit_sample(args.sample_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": report["ok"],
                "sample_scope": report["sample_scope"],
                "label_semantics": report["label_semantics"],
                "protocol_findings": report["protocol_findings"],
                "output": str(args.output),
            },
            indent=2,
        )
    )
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
