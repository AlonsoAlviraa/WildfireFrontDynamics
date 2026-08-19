"""Reproduce the published RCDA checkpoint on the complete official TEST archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FULL_ROOT = ROOT / "data/external/rcda_net_full"
DEFAULT_OUTPUT = ROOT / "outputs/ml_eval/rcda_full_upstream/reproduction.json"
THRESHOLDS = (0.2, 0.3, 0.4, 0.5, 0.6)

UPSTREAM_MIN = np.array(
    [
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        -1.0,
        0.0163726806640625,
        -np.pi,
        270.5065612792969,
        0.0,
        0.002109996974468231,
        0.9423993229866028,
    ],
    dtype=np.float32,
)[:, None, None]
UPSTREAM_MAX = np.array(
    [
        1.0,
        3413.0,
        1.0,
        1.0,
        1.0,
        1.0,
        13.046875,
        np.pi,
        300.23919677734375,
        0.0012839797418564558,
        0.015439476817846298,
        1.270668625831604,
    ],
    dtype=np.float32,
)[:, None, None]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _uid(name: str) -> str:
    return name.rsplit("_", 1)[0]


def _confusion(probability: np.ndarray, target: np.ndarray, threshold: float) -> np.ndarray:
    prediction = probability >= threshold
    truth = target > 0.5
    return np.array(
        [
            np.logical_and(prediction, truth).sum(),
            np.logical_and(~prediction, ~truth).sum(),
            np.logical_and(prediction, ~truth).sum(),
            np.logical_and(~prediction, truth).sum(),
        ],
        dtype=np.int64,
    )


def _metrics(confusion: np.ndarray) -> dict[str, float | int]:
    tp, tn, fp, fn = (int(value) for value in confusion)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    iou = tp / (tp + fp + fn) if tp + fp + fn else 0.0
    return {
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "iou": iou,
    }


def _load_model(upstream_root: Path, weights: Path, threads: int) -> torch.nn.Module:
    sys.path.insert(0, str(upstream_root))
    from Models.RCDA import RCDA

    torch.set_num_threads(threads)
    model = RCDA()
    state = torch.load(weights, map_location="cpu", weights_only=True)
    model.load_state_dict(state)
    model.eval()
    return model


def reproduce(
    full_root: Path,
    output: Path,
    *,
    max_samples: int | None = None,
    threads: int = 8,
    reverse: bool = False,
) -> dict[str, Any]:
    upstream_root = full_root / "upstream"
    dataset_root = full_root / "dataset"
    input_root = dataset_root / "test/inputs"
    label_root = dataset_root / "test/labels"
    weights = upstream_root / "weights/rcda.pth"
    cache_root = output.parent / "predictions"
    cache_root.mkdir(parents=True, exist_ok=True)
    names = sorted(
        (path.name for path in input_root.glob("*.npy")), reverse=reverse
    )
    if max_samples is not None:
        names = names[:max_samples]
    model = _load_model(upstream_root, weights, threads)
    confusion = {threshold: np.zeros(4, dtype=np.int64) for threshold in THRESHOLDS}
    confusion_no_overlap = {
        threshold: np.zeros(4, dtype=np.int64) for threshold in THRESHOLDS
    }
    per_event: dict[str, dict[float, np.ndarray]] = defaultdict(
        lambda: {threshold: np.zeros(4, dtype=np.int64) for threshold in THRESHOLDS}
    )
    inference_seconds = 0.0
    cache_hits = 0
    started = time.perf_counter()
    for index, name in enumerate(names, start=1):
        inputs = np.load(input_root / name, allow_pickle=False)
        label = np.load(label_root / name, allow_pickle=False)
        target = label.astype(np.int8) - (inputs[0] > 0.5).astype(np.int8)
        if int((target < 0).sum()) != 0:
            raise ValueError(f"negative incremental target in {name}")
        cache_path = cache_root / f"{Path(name).stem}.npz"
        probability: np.ndarray | None = None
        if cache_path.is_file():
            cached = np.load(cache_path, allow_pickle=False)["probability"]
            if cached.dtype == np.float32:
                probability = cached
                cache_hits += 1
        if probability is None:
            normalized = (inputs - UPSTREAM_MIN) / (UPSTREAM_MAX - UPSTREAM_MIN)
            tensor = torch.from_numpy(normalized[None].astype(np.float32))
            infer_started = time.perf_counter()
            with torch.inference_mode():
                probability = model(tensor).squeeze().numpy()
            inference_seconds += time.perf_counter() - infer_started
            np.savez(
                cache_path,
                probability=probability.astype(np.float32),
            )
        uid = _uid(name)
        for threshold in THRESHOLDS:
            row = _confusion(probability, target, threshold)
            confusion[threshold] += row
            per_event[uid][threshold] += row
            if uid != "UID_FIRE_656":
                confusion_no_overlap[threshold] += row
        if index % 50 == 0 or index == len(names):
            print(
                f"[rcda] {index}/{len(names)} cache={cache_hits} "
                f"infer_s={inference_seconds:.1f}",
                flush=True,
            )
    threshold_rows = {
        str(threshold): _metrics(row) for threshold, row in confusion.items()
    }
    best_threshold = max(
        THRESHOLDS,
        key=lambda threshold: float(threshold_rows[str(threshold)]["f1"]),
    )
    no_overlap_rows = {
        str(threshold): _metrics(row)
        for threshold, row in confusion_no_overlap.items()
    }
    event_metrics = {
        uid: _metrics(rows[best_threshold]) for uid, rows in sorted(per_event.items())
    }
    event_ious = np.array(
        [float(row["iou"]) for row in event_metrics.values()], dtype=np.float64
    )
    report = {
        "schema": "wfd_rcda_full_upstream_reproduction_v1",
        "generated_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "status": "complete",
        "source": {
            "dataset": "https://zenodo.org/records/16641619",
            "upstream_repository": "https://github.com/hxxAlways/RCDA-Net",
            "upstream_commit": "f7aebf6815d10bb2312e5683469d0c902d6f19e4",
            "weights": weights.relative_to(ROOT).as_posix(),
            "weights_sha256": _sha256(weights),
        },
        "scope": {
            "split": "upstream_original_test",
            "samples": len(names),
            "events": len(per_event),
            "complete_official_test": max_samples is None and len(names) == 1630,
            "cpu_threads": threads,
            "processing_order": "reverse" if reverse else "forward",
            "cache_hits": cache_hits,
            "inference_seconds": inference_seconds,
            "wall_seconds": time.perf_counter() - started,
        },
        "normalization": {
            "kind": "upstream_fixed_extrema",
            "minimum": UPSTREAM_MIN[:, 0, 0].tolist(),
            "maximum": UPSTREAM_MAX[:, 0, 0].tolist(),
        },
        "threshold_search_on_test": {
            "thresholds": list(THRESHOLDS),
            "results": threshold_rows,
            "selected_threshold": best_threshold,
            "selected_result": threshold_rows[str(best_threshold)],
            "protocol_is_sealed": False,
        },
        "test_excluding_train_overlap_uid_656": {
            "samples": sum(not name.startswith("UID_FIRE_656_") for name in names),
            "events": len({uid for uid in per_event if uid != "UID_FIRE_656"}),
            "results_at_all_thresholds": no_overlap_rows,
            "result_at_upstream_selected_threshold": no_overlap_rows[str(best_threshold)],
            "model_selection_is_still_not_sealed": True,
        },
        "event_macro_at_selected_threshold": {
            "iou_mean": float(event_ious.mean()),
            "iou_median": float(np.median(event_ious)),
            "iou_min": float(event_ious.min()),
            "iou_max": float(event_ious.max()),
        },
        "per_event_at_selected_threshold": event_metrics,
        "interpretation": {
            "reproduces_upstream_checkpoint_bytes": True,
            "reproduces_upstream_test_threshold_search": True,
            "independent_test_claim_allowed": False,
            "new_event_disjoint_retraining_required": True,
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full-root", type=Path, default=DEFAULT_FULL_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-samples", type=int)
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--reverse", action="store_true")
    args = parser.parse_args()
    report = reproduce(
        args.full_root,
        args.output,
        max_samples=args.max_samples,
        threads=args.threads,
        reverse=args.reverse,
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "scope": report["scope"],
                "selected": report["threshold_search_on_test"]["selected_result"],
                "output": str(args.output),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
