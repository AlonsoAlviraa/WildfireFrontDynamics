"""Audit the complete RCDA archive and build event-disjoint sealed splits."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "data/external/rcda_net_full/dataset"
DEFAULT_ARCHIVE = ROOT / "data/external/rcda_net_full/dataset.rar"
DEFAULT_OUTPUT = ROOT / "data/external/rcda_net_full/protocol"
DEFAULT_DOC = ROOT / "docs/RCDA_NET_FULL_PROTOCOL.json"
NAME_RE = re.compile(r"^(UID_FIRE_(\d+))_(\d{4}-\d{2}-\d{2})\.npy$")
PUBLISHED_ARCHIVE_MD5 = "d7856d77dcb823d0bdb5e10c6bac4f87"


def _hash_file(path: Path, algorithm: str = "sha256") -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _event_rank(uid: str, seed: str) -> str:
    return hashlib.sha256(f"{seed}:{uid}".encode()).hexdigest()


def _discover(dataset_root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for original_split in ("train", "test"):
        input_root = dataset_root / original_split / "inputs"
        label_root = dataset_root / original_split / "labels"
        input_names = {path.name for path in input_root.glob("*.npy")}
        label_names = {path.name for path in label_root.glob("*.npy")}
        if input_names != label_names:
            raise ValueError(f"unpaired RCDA files in {original_split}")
        for name in sorted(input_names):
            match = NAME_RE.match(name)
            if match is None:
                raise ValueError(f"unparseable RCDA file name: {name}")
            records.append(
                {
                    "name": name,
                    "uid": match.group(1),
                    "uid_number": int(match.group(2)),
                    "date": match.group(3),
                    "year": int(match.group(3)[:4]),
                    "original_split": original_split,
                    "input": (input_root / name).relative_to(dataset_root).as_posix(),
                    "label": (label_root / name).relative_to(dataset_root).as_posix(),
                }
            )
    return records


def assign_event_splits(
    records: list[dict[str, Any]],
    *,
    validation_fraction: float = 0.15,
    seed: str = "wfd_rcda_event_split_v1",
) -> dict[str, str]:
    """Reserve all upstream TEST events, then select VAL from TRAIN-only events."""
    test_uids = {row["uid"] for row in records if row["original_split"] == "test"}
    train_only = {
        row["uid"] for row in records if row["original_split"] == "train"
    } - test_uids
    years: dict[str, set[int]] = defaultdict(set)
    for row in records:
        if row["uid"] in train_only:
            years[row["uid"]].add(int(row["year"]))
    by_year: dict[int, list[str]] = defaultdict(list)
    for uid in train_only:
        primary_year = min(years[uid])
        by_year[primary_year].append(uid)
    validation_uids: set[str] = set()
    for year, uids in by_year.items():
        ordered = sorted(uids, key=lambda uid: _event_rank(uid, f"{seed}:{year}"))
        count = max(1, round(len(ordered) * validation_fraction))
        validation_uids.update(ordered[:count])
    assignments: dict[str, str] = {}
    for uid in {row["uid"] for row in records}:
        if uid in test_uids:
            assignments[uid] = "test"
        elif uid in validation_uids:
            assignments[uid] = "val"
        else:
            assignments[uid] = "train"
    return assignments


def _manifest_payload(
    split: str,
    rows: list[dict[str, Any]],
    seed: str,
) -> dict[str, Any]:
    return {
        "schema": "wfd_rcda_event_split_manifest_v1",
        "split": split,
        "seed": seed,
        "event_disjoint": True,
        "n_events": len({row["uid"] for row in rows}),
        "n_samples": len(rows),
        "year_counts": dict(sorted(Counter(row["year"] for row in rows).items())),
        "events": sorted({row["uid"] for row in rows}),
        "samples": rows,
    }


def _scan_arrays(
    dataset_root: Path,
    manifests: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    channel_min = np.full(12, np.inf, dtype=np.float64)
    channel_max = np.full(12, -np.inf, dtype=np.float64)
    scan: dict[str, Any] = {
        "samples_scanned": 0,
        "invalid_shapes": 0,
        "nonfinite_input_values": 0,
        "nonbinary_previous_masks": 0,
        "nonbinary_labels": 0,
        "samples_with_negative_growth_after_subtraction": 0,
        "negative_growth_pixels": 0,
        "previous_positive_pixels": 0,
        "previous_retained_pixels": 0,
        "growth_positive_pixels": 0,
        "weather_constant_sample_counts": [0] * 6,
        "input_dtypes": Counter(),
        "label_dtypes": Counter(),
    }
    for split in ("train", "val", "test"):
        for row in manifests[split]:
            inputs = np.load(dataset_root / row["input"], mmap_mode="r", allow_pickle=False)
            label = np.load(dataset_root / row["label"], mmap_mode="r", allow_pickle=False)
            scan["samples_scanned"] += 1
            scan["input_dtypes"][str(inputs.dtype)] += 1
            scan["label_dtypes"][str(label.dtype)] += 1
            if inputs.shape != (12, 256, 256) or label.shape != (256, 256):
                scan["invalid_shapes"] += 1
                continue
            previous = np.asarray(inputs[0])
            target = np.asarray(label)
            scan["nonfinite_input_values"] += int(
                sum(np.size(channel) - np.isfinite(channel).sum() for channel in inputs)
            )
            previous_binary = np.logical_or(previous == 0, previous == 1)
            target_binary = np.logical_or(target == 0, target == 1)
            if not bool(previous_binary.all()):
                scan["nonbinary_previous_masks"] += 1
            if not bool(target_binary.all()):
                scan["nonbinary_labels"] += 1
            previous_fire = previous > 0.5
            next_extent = target > 0.5
            retained = np.logical_and(previous_fire, next_extent)
            negative = np.logical_and(previous_fire, ~next_extent)
            growth = np.logical_and(~previous_fire, next_extent)
            negative_count = int(negative.sum())
            scan["previous_positive_pixels"] += int(previous_fire.sum())
            scan["previous_retained_pixels"] += int(retained.sum())
            scan["growth_positive_pixels"] += int(growth.sum())
            scan["negative_growth_pixels"] += negative_count
            scan["samples_with_negative_growth_after_subtraction"] += int(
                negative_count > 0
            )
            for offset, channel_index in enumerate(range(6, 12)):
                channel = np.asarray(inputs[channel_index])
                scan["weather_constant_sample_counts"][offset] += int(
                    float(np.nanmin(channel)) == float(np.nanmax(channel))
                )
            if split == "train":
                for channel_index in range(12):
                    channel = np.asarray(inputs[channel_index])
                    channel_min[channel_index] = min(
                        channel_min[channel_index], float(np.nanmin(channel))
                    )
                    channel_max[channel_index] = max(
                        channel_max[channel_index], float(np.nanmax(channel))
                    )
    scan["input_dtypes"] = dict(scan["input_dtypes"])
    scan["label_dtypes"] = dict(scan["label_dtypes"])
    denominator = int(scan["previous_positive_pixels"])
    scan["global_previous_retained_fraction"] = (
        int(scan["previous_retained_pixels"]) / denominator if denominator else 1.0
    )
    normalization = {
        "schema": "wfd_rcda_train_only_minmax_v1",
        "fit_split": "train",
        "channel_min": channel_min.tolist(),
        "channel_max": channel_max.tolist(),
        "constant_channels": [
            index
            for index, (minimum, maximum) in enumerate(
                zip(channel_min, channel_max, strict=True)
            )
            if minimum == maximum
        ],
    }
    return scan, normalization


def build_protocol(
    dataset_root: Path,
    archive_path: Path,
    output_root: Path,
    doc_path: Path,
    *,
    validation_fraction: float = 0.15,
    seed: str = "wfd_rcda_event_split_v1",
) -> dict[str, Any]:
    records = _discover(dataset_root)
    assignments = assign_event_splits(
        records,
        validation_fraction=validation_fraction,
        seed=seed,
    )
    manifests: dict[str, list[dict[str, Any]]] = {"train": [], "val": [], "test": []}
    for row in records:
        split = assignments[row["uid"]]
        manifests[split].append({**row, "split": split})
    output_root.mkdir(parents=True, exist_ok=True)
    manifest_rows: dict[str, dict[str, Any]] = {}
    for split, rows in manifests.items():
        payload = _manifest_payload(split, rows, seed)
        path = output_root / f"{split}.json"
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        manifest_rows[split] = {
            "path": path.relative_to(ROOT).as_posix(),
            "sha256": _hash_file(path),
            "n_events": payload["n_events"],
            "n_samples": payload["n_samples"],
            "year_counts": payload["year_counts"],
        }
    scan, normalization = _scan_arrays(dataset_root, manifests)
    normalization_path = output_root / "normalization_train_only.json"
    normalization_path.write_text(
        json.dumps(normalization, indent=2) + "\n", encoding="utf-8"
    )
    uid_sets = {
        split: {row["uid"] for row in rows} for split, rows in manifests.items()
    }
    upstream_train = {
        row["uid"] for row in records if row["original_split"] == "train"
    }
    upstream_test = {
        row["uid"] for row in records if row["original_split"] == "test"
    }
    archive_md5 = _hash_file(archive_path, "md5")
    report = {
        "schema": "wfd_rcda_full_protocol_v1",
        "generated_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "status": "complete",
        "source": {
            "zenodo_record": "https://zenodo.org/records/16641619",
            "archive": archive_path.relative_to(ROOT).as_posix(),
            "archive_bytes": archive_path.stat().st_size,
            "archive_md5": archive_md5,
            "published_md5": PUBLISHED_ARCHIVE_MD5,
            "archive_hash_matches": archive_md5 == PUBLISHED_ARCHIVE_MD5,
            "upstream_commit": "f7aebf6815d10bb2312e5683469d0c902d6f19e4",
        },
        "inventory": {
            "samples": len(records),
            "input_files": len(records),
            "label_files": len(records),
            "original_train_samples": sum(
                row["original_split"] == "train" for row in records
            ),
            "original_test_samples": sum(
                row["original_split"] == "test" for row in records
            ),
            "events": len({row["uid"] for row in records}),
            "years": sorted({row["year"] for row in records}),
        },
        "upstream_leakage": {
            "event_overlap_count": len(upstream_train & upstream_test),
            "overlap_events": sorted(upstream_train & upstream_test),
            "uid_656_train_samples": sum(
                row["uid"] == "UID_FIRE_656" and row["original_split"] == "train"
                for row in records
            ),
            "uid_656_test_samples": sum(
                row["uid"] == "UID_FIRE_656" and row["original_split"] == "test"
                for row in records
            ),
            "adjacent_temporal_event_leakage": bool(upstream_train & upstream_test),
        },
        "sealed_protocol": {
            "seed": seed,
            "validation_fraction_of_train_only_events": validation_fraction,
            "upstream_test_events_reserved_for_test": True,
            "overlapping_events_moved_entirely_to_test": True,
            "train_val_test_event_disjoint": not (
                uid_sets["train"] & uid_sets["val"]
                or uid_sets["train"] & uid_sets["test"]
                or uid_sets["val"] & uid_sets["test"]
            ),
            "normalization_fit_on_train_only": True,
            "threshold_selection_split": "val",
            "test_usage": "once_after_frozen_checkpoint_and_threshold",
        },
        "manifests": manifest_rows,
        "normalization": {
            "path": normalization_path.relative_to(ROOT).as_posix(),
            "sha256": _hash_file(normalization_path),
            **normalization,
        },
        "array_audit": scan,
        "acceptance": {
            "archive_verified": archive_md5 == PUBLISHED_ARCHIVE_MD5,
            "all_8131_pairs_present": len(records) == 8131,
            "all_shapes_valid": scan["invalid_shapes"] == 0,
            "sealed_splits_event_disjoint": True,
            "ready_for_training": archive_md5 == PUBLISHED_ARCHIVE_MD5
            and len(records) == 8131
            and scan["invalid_shapes"] == 0,
            "published_checkpoint_is_valid_for_new_sealed_test": False,
        },
    }
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC)
    parser.add_argument("--validation-fraction", type=float, default=0.15)
    args = parser.parse_args()
    report = build_protocol(
        args.dataset,
        args.archive,
        args.output_root,
        args.doc,
        validation_fraction=args.validation_fraction,
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "inventory": report["inventory"],
                "upstream_leakage": report["upstream_leakage"],
                "manifests": report["manifests"],
                "acceptance": report["acceptance"],
                "doc": str(args.doc),
            },
            indent=2,
        )
    )
    return 0 if report["acceptance"]["ready_for_training"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
