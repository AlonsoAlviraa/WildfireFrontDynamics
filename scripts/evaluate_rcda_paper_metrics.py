#!/usr/bin/env python3
"""Re-evaluate frozen RCDA checkpoints locally with AP, FCER and boundary metrics."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.ml.rcda_sealed import (  # noqa: E402
    SEALED_CHANNEL_NAMES,
    ProbabilityAveragingEnsemble,
    SealedRCDADataset,
    build_model,
    evaluate_split,
    evaluate_split_postprocessed,
    load_protocol,
    make_loader,
    prepare_model_for_device,
)


def verify_cross_backend_reproduction(
    local: dict[str, Any],
    remote: dict[str, Any],
    *,
    label: str,
    max_changed_pixel_fraction: float = 1e-6,
    max_iou_delta: float = 1e-5,
    max_event_macro_delta: float = 1e-5,
) -> dict[str, Any]:
    """Verify CPU metrics against the authoritative GPU result.

    Convolution kernels can differ by a few floating-point ulps across CUDA
    and oneDNN. Pixels whose probabilities lie almost exactly on the frozen
    threshold may consequently change class. We accept at most one changed
    prediction per million evaluated pixels and keep the GPU confusion matrix
    as the confirmatory primary result. The local pass contributes only the
    backend-independent secondary metrics.
    """

    keys = ("tp", "tn", "fp", "fn")
    if any(key not in local or key not in remote for key in keys):
        raise ValueError(f"{label}: missing confusion counts")
    local_total = sum(int(local[key]) for key in keys)
    remote_total = sum(int(remote[key]) for key in keys)
    if local_total != remote_total:
        raise ValueError(
            f"{label}: evaluated pixel totals differ ({local_total} != {remote_total})"
        )
    changed_pixels = sum(abs(int(local[key]) - int(remote[key])) for key in keys) // 2
    allowed_changed_pixels = max(
        1,
        int(math.ceil(remote_total * float(max_changed_pixel_fraction))),
    )
    iou_delta = float(local["iou"]) - float(remote["iou"])
    event_macro_delta = float(local["event_macro_iou"]) - float(
        remote["event_macro_iou"]
    )
    if changed_pixels > allowed_changed_pixels:
        raise ValueError(
            f"{label}: CPU/GPU predictions differ at {changed_pixels} pixels; "
            f"allowed {allowed_changed_pixels}"
        )
    if abs(iou_delta) > max_iou_delta:
        raise ValueError(
            f"{label}: CPU/GPU IoU delta {iou_delta} exceeds {max_iou_delta}"
        )
    if abs(event_macro_delta) > max_event_macro_delta:
        raise ValueError(
            f"{label}: CPU/GPU event-macro delta {event_macro_delta} exceeds "
            f"{max_event_macro_delta}"
        )
    return {
        "authoritative_primary_backend": "kaggle_t4_gpu",
        "secondary_metrics_backend": "local_cpu",
        "evaluated_pixels": remote_total,
        "changed_predictions_upper_bound": changed_pixels,
        "changed_prediction_fraction": changed_pixels / remote_total,
        "allowed_changed_prediction_fraction": max_changed_pixel_fraction,
        "pooled_iou_delta_local_minus_remote": iou_delta,
        "event_macro_iou_delta_local_minus_remote": event_macro_delta,
        "max_iou_delta": max_iou_delta,
        "max_event_macro_delta": max_event_macro_delta,
        "within_tolerance": True,
    }


def evaluate_final_checkpoints(
    final_summary_path: Path,
    checkpoint_dir: Path,
    dataset_root: Path,
    protocol_dir: Path,
    output_path: Path,
) -> dict:
    summary = json.loads(Path(final_summary_path).read_text(encoding="utf-8"))
    if summary.get("schema") != "wfd_rcda_paper_final_v1":
        raise ValueError("unexpected final summary schema")
    protocol = load_protocol(Path(protocol_dir))
    test_set = SealedRCDADataset(
        Path(dataset_root),
        protocol["manifests"]["test"],
        protocol["normalization"],
        augment=False,
    )
    test_loader = make_loader(
        test_set,
        batch_size=8,
        shuffle=False,
        weighted=False,
        num_workers=0,
    )
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    seed_models = []
    for report in summary.get("reports") or []:
        config = report["config"]
        checkpoint_name = Path(report["checkpoint"]).name
        checkpoint_path = Path(checkpoint_dir) / checkpoint_name
        local_sha256 = hashlib.sha256(checkpoint_path.read_bytes()).hexdigest()
        if local_sha256 != report.get("checkpoint_sha256"):
            raise ValueError(f"checkpoint SHA-256 mismatch: {checkpoint_path}")
        payload = torch.load(checkpoint_path, map_location=device, weights_only=False)
        if payload.get("selection_split") != "val":
            raise ValueError(f"checkpoint was not selected on VAL: {checkpoint_path}")
        model = prepare_model_for_device(
            build_model(
                str(config["model_name"]),
                in_channels=len(SEALED_CHANNEL_NAMES),
                base=int(config["base_channels"]),
            ),
            device,
        )
        model.load_state_dict(payload["state_dict"])
        seed_models.append(model)
        metrics = evaluate_split(
            model,
            test_loader,
            device,
            float(report["selected_threshold"]),
            prediction_mode=str(config["target_mode"]),
            paper_metrics=True,
        )
        remote = report.get("test_once") or {}
        reproduction = verify_cross_backend_reproduction(
            metrics,
            remote,
            label=checkpoint_name,
        )
        report["test_once"]["paper_metrics"] = metrics["paper_metrics"]
        report["paper_metrics_recomputed_from_frozen_checkpoint"] = True
        report["local_checkpoint"] = str(checkpoint_path)
        report["local_checkpoint_sha256_verified"] = True
        report["local_cpu_reproduction"] = reproduction
    ensemble_report = summary.get("ensemble")
    if ensemble_report:
        if len(seed_models) < 2:
            raise ValueError("ensemble report requires at least two seed checkpoints")
        ensemble_model = ProbabilityAveragingEnsemble(seed_models).to(device)
        config = summary["reports"][0]["config"]
        ensemble_metrics = evaluate_split(
            ensemble_model,
            test_loader,
            device,
            float(ensemble_report["selected_threshold"]),
            prediction_mode=str(config["target_mode"]),
            paper_metrics=True,
        )
        remote = ensemble_report.get("test_once") or {}
        reproduction = verify_cross_backend_reproduction(
            ensemble_metrics,
            remote,
            label="mean_seed_probability_ensemble",
        )
        ensemble_report["test_once"]["paper_metrics"] = ensemble_metrics[
            "paper_metrics"
        ]
        ensemble_report["paper_metrics_recomputed_from_frozen_checkpoints"] = True
        ensemble_report["local_cpu_reproduction"] = reproduction
    decoder_report = summary.get("decoder")
    if decoder_report:
        if len(seed_models) < 2:
            raise ValueError("decoder report requires the seed probability ensemble")
        decoder_model = ProbabilityAveragingEnsemble(seed_models).to(device)
        config = summary["reports"][0]["config"]
        decoder_metrics = evaluate_split_postprocessed(
            decoder_model,
            test_loader,
            device,
            float(decoder_report["threshold"]),
            prediction_mode=str(config["target_mode"]),
            dilation_radius=int(decoder_report["dilation_radius_px"]),
            require_t0_connection=bool(
                decoder_report["require_t0_connection"]
            ),
        )
        remote = decoder_report.get("test_once") or {}
        reproduction = verify_cross_backend_reproduction(
            decoder_metrics,
            remote,
            label="spatial_decoder",
        )
        decoder_report["recomputed_from_frozen_checkpoints"] = True
        decoder_report["local_cpu_reproduction"] = reproduction
    summary["schema"] = "wfd_rcda_paper_final_metrics_v1"
    summary["paper_metrics_recomputed_locally"] = True
    summary["paper_metrics_device"] = str(device)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("final_summary", type=Path)
    parser.add_argument("--checkpoint-dir", type=Path, required=True)
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
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summary = evaluate_final_checkpoints(
        args.final_summary,
        args.checkpoint_dir,
        args.dataset_root,
        args.protocol_dir,
        args.output,
    )
    print(json.dumps({"reports": len(summary["reports"]), "output": str(args.output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
