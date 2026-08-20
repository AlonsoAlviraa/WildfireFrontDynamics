#!/usr/bin/env python3
"""Assemble independently adapted WFIGS seeds and evaluate their VAL ensemble."""

from __future__ import annotations

import argparse
import json
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
    build_model,
    make_loader,
    prepare_model_for_device,
    select_threshold_on_val,
)
from wildfire_front.ml.wfigs_domain_adapt import ADAPTATION_SCHEMA  # noqa: E402
from wildfire_front.ml.wfigs_external_eval import WFIGSExternalDataset  # noqa: E402
from wildfire_front.open_if.regional.base import _atomic_write_json, utc_now  # noqa: E402


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_adaptation_replications(
    paths: list[Path],
    *,
    expected_seeds: tuple[int, ...],
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    if len(paths) != len(expected_seeds) or len(set(expected_seeds)) != len(
        expected_seeds
    ):
        raise ValueError("one independent adaptation is required for every unique seed")
    reports: list[dict[str, Any]] = []
    canonical_adaptation: dict[str, Any] | None = None
    canonical_source: dict[str, Any] | None = None
    canonical_counts: dict[str, Any] | None = None
    event_cohort: set[str] | None = None
    for path, expected_seed in zip(paths, expected_seeds, strict=True):
        summary = _read(path)
        rows = summary.get("reports") or []
        if not (
            summary.get("schema") == ADAPTATION_SCHEMA
            and summary.get("test_used_for_selection") is False
            and summary.get("wfigs_test_loaded") is False
            and len(rows) == 1
            and rows[0].get("threshold_selected_on") == "wfigs_validation"
            and rows[0].get("test_evaluated") is False
        ):
            raise ValueError("adaptation replication is not an isolated VAL-only run")
        report = dict(rows[0])
        seed = int((report.get("config") or {}).get("seed"))
        if seed != expected_seed:
            raise ValueError("adaptation replication seed order differs from registration")
        checkpoint = Path(str(report.get("checkpoint") or ""))
        if not checkpoint.is_file():
            checkpoint = path.parent / checkpoint.name
        if not checkpoint.is_file():
            raise FileNotFoundError(f"adapted checkpoint is missing for seed {seed}")
        report["checkpoint"] = str(checkpoint.resolve())
        adaptation = dict(summary.get("configuration") or {})
        adaptation.pop("source_seeds", None)
        if canonical_adaptation is None:
            canonical_adaptation = adaptation
        elif adaptation != canonical_adaptation:
            raise ValueError("WFIGS adaptation configurations differ beyond source seed")
        source_config = {
            key: value
            for key, value in (report.get("config") or {}).items()
            if key != "seed"
        }
        if canonical_source is None:
            canonical_source = source_config
        elif source_config != canonical_source:
            raise ValueError("RCDA source configurations differ beyond seed")
        counts = dict(summary.get("counts") or {})
        counts.pop("reports", None)
        if canonical_counts is None:
            canonical_counts = counts
        elif counts != canonical_counts:
            raise ValueError("WFIGS adaptation replications use different cohorts")
        events = set(report["validation"]["selected"]["per_event"])
        if event_cohort is None:
            event_cohort = events
        elif events != event_cohort:
            raise ValueError("WFIGS adaptation VAL fire cohorts differ")
        reports.append(report)
    assert canonical_adaptation is not None
    assert canonical_counts is not None
    return reports, canonical_adaptation, canonical_counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summary", type=Path, nargs="+")
    parser.add_argument("--seed", type=int, action="append", default=[])
    parser.add_argument("--wfigs-dataset", type=Path, required=True)
    parser.add_argument("--rcda-normalization", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    seeds = tuple(args.seed or (11, 29, 47))
    reports, adaptation, counts = validate_adaptation_replications(
        args.summary,
        expected_seeds=seeds,
    )
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
        batch_size=int(adaptation["batch_size"]),
        shuffle=False,
        weighted=False,
        num_workers=int(adaptation["num_workers"]),
    )
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    models = []
    target_modes = set()
    for report, seed in zip(reports, seeds, strict=True):
        config = report["config"]
        checkpoint = torch.load(report["checkpoint"], map_location=device, weights_only=False)
        if not (
            checkpoint.get("selection_split") == "wfigs_validation"
            and checkpoint.get("wfigs_test_evaluated") is False
            and int(checkpoint.get("seed")) == seed
        ):
            raise ValueError(f"adapted checkpoint boundary is invalid for seed {seed}")
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
        target_modes.add(str(config["target_mode"]))
    if len(target_modes) != 1:
        raise ValueError("adapted checkpoint target modes differ")
    ensemble = ProbabilityAveragingEnsemble(models)
    threshold, validation = select_threshold_on_val(
        ensemble,
        loader,
        device,
        prediction_mode=target_modes.pop(),
        selection_metric="event_macro_iou",
    )
    result = {
        "schema": ADAPTATION_SCHEMA,
        "generated_at": utc_now(),
        "device": str(device),
        "configuration": {**adaptation, "source_seeds": list(seeds)},
        "counts": {**counts, "reports": len(reports)},
        "reports": reports,
        "ensemble": {
            "aggregation": "mean_seed_probability",
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
            "independent_adaptations_reused_without_retraining": True,
            "source_seed_order_registered": True,
            "wfigs_test_performance_known": False,
            "public_checkpoint_release_allowed": False,
        },
    }
    args.output.mkdir(parents=True, exist_ok=True)
    output_path = args.output / "WFIGS_ADAPTATION_VAL_ONLY.json"
    _atomic_write_json(output_path, result)
    print(json.dumps(result["ensemble"]["validation"]["selected"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
