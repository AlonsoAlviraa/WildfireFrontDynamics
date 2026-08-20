#!/usr/bin/env python3
"""Build an exploratory equal-weight ensemble across frozen WFIGS sources."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import torch
from torch import nn

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.ml.rcda_sealed import (  # noqa: E402
    SEALED_CHANNEL_NAMES,
    build_model,
    make_loader,
    prediction_logits,
    prepare_model_for_device,
    select_threshold_on_val,
)
from wildfire_front.ml.wfigs_domain_adapt import ADAPTATION_SCHEMA  # noqa: E402
from wildfire_front.ml.wfigs_external_eval import WFIGSExternalDataset  # noqa: E402
from wildfire_front.open_if.regional.base import _atomic_write_json, utc_now  # noqa: E402


class GrowthHeadProbabilityEnsemble(nn.Module):
    """Average growth probabilities from models with heterogeneous heads."""

    def __init__(self, models: list[nn.Module], target_modes: list[str]) -> None:
        super().__init__()
        if len(models) < 2 or len(models) != len(target_modes):
            raise ValueError("cross-source ensemble requires aligned models and modes")
        self.models = nn.ModuleList(models)
        self.target_modes = tuple(target_modes)

    def forward(self, tensor: torch.Tensor) -> torch.Tensor:
        probabilities = torch.stack(
            [
                torch.sigmoid(prediction_logits(model(tensor), mode))
                for model, mode in zip(self.models, self.target_modes, strict=True)
            ],
            dim=0,
        ).mean(dim=0)
        return torch.logit(probabilities.clamp(1e-6, 1.0 - 1e-6))


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_sources(paths: list[Path]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if len(paths) < 2:
        raise ValueError("cross-source ensemble requires at least two sources")
    reports: list[dict[str, Any]] = []
    source_rows = []
    canonical_counts: dict[str, Any] | None = None
    canonical_events: set[str] | None = None
    for path in paths:
        summary = _read(path)
        ensemble = summary.get("ensemble") or {}
        rows = summary.get("reports") or []
        if not (
            summary.get("schema") == ADAPTATION_SCHEMA
            and summary.get("test_used_for_selection") is False
            and summary.get("wfigs_test_loaded") is False
            and len(rows) >= 3
            and ensemble.get("threshold_selected_on") == "wfigs_validation"
            and ensemble.get("test_used_for_selection") is False
            and ensemble.get("test_evaluated") is False
        ):
            raise ValueError("source is not an isolated multi-seed WFIGS VAL ensemble")
        counts = dict(summary.get("counts") or {})
        counts.pop("reports", None)
        if canonical_counts is None:
            canonical_counts = counts
        elif counts != canonical_counts:
            raise ValueError("cross-source ensembles use different WFIGS cohorts")
        events = set(ensemble["validation"]["selected"]["per_event"])
        if canonical_events is None:
            canonical_events = events
        elif events != canonical_events:
            raise ValueError("cross-source ensemble VAL fire cohorts differ")
        for report in rows:
            checkpoint = Path(str(report.get("checkpoint") or ""))
            if not checkpoint.is_file():
                checkpoint = path.parent / checkpoint.name
            if not checkpoint.is_file():
                raise FileNotFoundError("cross-source adapted checkpoint is missing")
            localized = dict(report)
            localized["checkpoint"] = str(checkpoint.resolve())
            reports.append(localized)
        source_rows.append(
            {
                "summary": str(path.resolve()),
                "summary_sha256": _sha256(path),
                "members": len(rows),
                "val_event_macro_iou": ensemble["validation"]["selected"][
                    "event_macro_iou"
                ],
            }
        )
    assert canonical_counts is not None
    return reports, {"counts": canonical_counts, "sources": source_rows}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, action="append", required=True)
    parser.add_argument("--wfigs-dataset", type=Path, required=True)
    parser.add_argument("--rcda-normalization", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    reports, provenance = validate_sources(args.source)
    normalization = _read(args.rcda_normalization)
    if normalization.get("fit_split") != "train":
        raise ValueError("RCDA normalization was not fitted on TRAIN")
    validation_manifest = _read(args.wfigs_dataset / "validation.json")
    validation_set = WFIGSExternalDataset(
        dataset_root=args.wfigs_dataset,
        manifest=validation_manifest,
        rcda_normalization=normalization,
        augment=False,
    )
    loader = make_loader(
        validation_set,
        batch_size=4,
        shuffle=False,
        weighted=False,
        num_workers=0,
    )
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    models: list[nn.Module] = []
    modes: list[str] = []
    for report in reports:
        config = report["config"]
        checkpoint = torch.load(report["checkpoint"], map_location=device, weights_only=False)
        if not (
            checkpoint.get("selection_split") == "wfigs_validation"
            and checkpoint.get("wfigs_test_evaluated") is False
            and int(checkpoint.get("seed")) == int(config["seed"])
        ):
            raise ValueError("cross-source checkpoint crossed the TEST boundary")
        model = prepare_model_for_device(
            build_model(
                str(config["model_name"]),
                in_channels=len(SEALED_CHANNEL_NAMES),
                base=int(config["base_channels"]),
            ),
            device,
        )
        model.load_state_dict(checkpoint["state_dict"])
        model.eval()
        models.append(model)
        modes.append(str(config["target_mode"]))
    ensemble = GrowthHeadProbabilityEnsemble(models, modes)
    threshold, validation = select_threshold_on_val(
        ensemble,
        loader,
        device,
        prediction_mode="hybrid",
        selection_metric="event_macro_iou",
    )
    result = {
        "schema": ADAPTATION_SCHEMA,
        "generated_at": utc_now(),
        "device": str(device),
        "configuration": {
            "aggregation": "equal_weight_growth_probability_across_sources",
            "source_summaries": provenance["sources"],
            "selection_split": "wfigs_validation",
            "exploratory_post_pilot_candidate": True,
        },
        "counts": {**provenance["counts"], "reports": len(reports)},
        "reports": reports,
        "ensemble": {
            "aggregation": "equal_weight_growth_probability_across_sources",
            "members": len(models),
            "selected_threshold": threshold,
            "threshold_selected_on": "wfigs_validation",
            "validation": validation,
            "test_used_for_selection": False,
            "test_evaluated": False,
        },
        "test_used_for_selection": False,
        "wfigs_test_loaded": False,
        "claims": {
            "exploratory_post_pilot_candidate": True,
            "wfigs_test_performance_known": False,
            "public_checkpoint_release_allowed": False,
        },
    }
    args.output.mkdir(parents=True, exist_ok=True)
    output_path = args.output / "WFIGS_ADAPTATION_VAL_ONLY.json"
    _atomic_write_json(output_path, result)
    selected = result["ensemble"]["validation"]["selected"]
    print(
        json.dumps(
            {
                "members": len(models),
                "selected_threshold": threshold,
                "val_event_macro_iou": selected["event_macro_iou"],
                "test_evaluated": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
