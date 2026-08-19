#!/usr/bin/env python3
"""Re-evaluate sealed learned baselines with per-event metrics for paper comparisons."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import torch
from torch.utils.data import DataLoader, Dataset

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.ml.rcda_sealed import (  # noqa: E402
    SealedRCDADataset,
    build_model,
    evaluate_split,
    load_protocol,
)


class LegacyFeatureView(Dataset):
    """Project the current 16-channel encoder onto a checkpoint channel list."""

    def __init__(self, dataset: SealedRCDADataset, channel_names: list[str]) -> None:
        self.dataset = dataset
        current = [
            "previous_fire",
            "dem",
            "blue",
            "green",
            "red",
            "ndvi",
            "wind_speed",
            "wind_sin",
            "wind_cos",
            "temperature",
            "precipitation",
            "humidity",
            "air_density",
            "distance_to_front_near",
            "distance_to_front_global",
            "horizon_hours",
        ]
        aliases = {"distance_to_front": "distance_to_front_near"}
        normalized = [aliases.get(name, name) for name in channel_names]
        missing = sorted(set(normalized) - set(current))
        if missing:
            raise ValueError(f"checkpoint requests unknown channels: {missing}")
        self.indices = [current.index(name) for name in normalized]

    def __len__(self) -> int:
        return len(self.dataset)

    def __getitem__(self, index: int) -> dict[str, Any]:
        row = dict(self.dataset[index])
        row["input"] = row["input"][self.indices]
        return row


def evaluate_learned_baselines(
    checkpoint_dir: Path,
    dataset_root: Path,
    protocol_dir: Path,
    output: Path,
    *,
    batch_size: int = 8,
    threads: int = 8,
) -> dict[str, Any]:
    torch.set_num_threads(max(1, threads))
    device = torch.device("cpu")
    protocol = load_protocol(protocol_dir)
    base_dataset = SealedRCDADataset(
        dataset_root,
        protocol["manifests"]["test"],
        protocol["normalization"],
        augment=False,
    )
    reports: list[dict[str, Any]] = []
    for checkpoint_path in sorted(checkpoint_dir.glob("*_best.pt")):
        stored = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
        report_path = checkpoint_path.with_name(
            checkpoint_path.name.replace("_best.pt", "_report.json")
        )
        original = json.loads(report_path.read_text(encoding="utf-8"))
        channel_names = list(stored.get("channel_names") or [])
        if not channel_names:
            raise ValueError(f"checkpoint has no channel names: {checkpoint_path}")
        dataset = LegacyFeatureView(base_dataset, channel_names)
        loader = DataLoader(dataset, batch_size=batch_size, shuffle=False, num_workers=0)
        model = build_model(
            str(stored["model_name"]),
            in_channels=int(stored["in_channels"]),
            base=int(stored.get("base_channels") or 32),
        )
        model.load_state_dict(stored["state_dict"])
        model.eval()
        threshold = float(original["selected_threshold"])
        result = evaluate_split(
            model,
            loader,
            device,
            threshold,
            prediction_mode=str(stored.get("target_mode") or "growth"),
            paper_metrics=False,
        )
        expected = original["test_once"]
        if abs(float(result["iou"]) - float(expected["iou"])) > 1e-10:
            raise ValueError(f"pooled IoU reproduction failed for {checkpoint_path.name}")
        if abs(float(result["event_macro_iou"]) - float(expected["event_macro_iou"])) > 1e-10:
            raise ValueError(f"event IoU reproduction failed for {checkpoint_path.name}")
        reports.append(
            {
                "model_name": stored["model_name"],
                "checkpoint": checkpoint_path.relative_to(ROOT).as_posix(),
                "threshold_selected_on": original["threshold_selected_on"],
                "test_used_for_selection": original["test_used_for_selection"],
                "selected_threshold": threshold,
                "test": result,
            }
        )
    payload = {
        "schema": "wfd_rcda_learned_baselines_v1",
        "generated_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "event_disjoint": True,
        "selection_split": "val",
        "test_used_for_selection": False,
        "reports": reports,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--checkpoint-dir",
        type=Path,
        default=ROOT / "outputs/ml_eval/rcda_sealed_kaggle_20260818/rcda_sealed",
    )
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=ROOT / "data/external/rcda_net_full/dataset",
    )
    parser.add_argument(
        "--protocol-dir",
        type=Path,
        default=ROOT / "data/external/rcda_net_full/protocol",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "outputs/ml_eval/rcda_sealed_baselines/learned_baselines.json",
    )
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--threads", type=int, default=8)
    args = parser.parse_args()
    result = evaluate_learned_baselines(
        args.checkpoint_dir,
        args.dataset_root,
        args.protocol_dir,
        args.output,
        batch_size=args.batch_size,
        threads=args.threads,
    )
    print(
        json.dumps(
            [
                {
                    "model_name": row["model_name"],
                    "event_macro_iou": row["test"]["event_macro_iou"],
                    "pooled_iou": row["test"]["iou"],
                }
                for row in result["reports"]
            ],
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
