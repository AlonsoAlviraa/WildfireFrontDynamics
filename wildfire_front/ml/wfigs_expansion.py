"""Leakage-safe WFIGS expansion and confirmation helpers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from statistics import mean
from typing import Any

import numpy as np
import torch

from wildfire_front.open_if.regional.base import _atomic_write_json, utc_now

from .rcda_sealed import (
    SEALED_CHANNEL_NAMES,
    HeterogeneousGrowthProbabilityEnsemble,
    ProbabilityAveragingEnsemble,
    build_model,
    evaluate_split,
    make_loader,
    prepare_model_for_device,
)
from .wfigs_external_eval import WFIGSExternalDataset

EXPANSION_SCHEMA = "wfd_wfigs_expansion_protocol_v1"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def set_digest(values: set[str]) -> str:
    return hashlib.sha256("\n".join(sorted(values)).encode("utf-8")).hexdigest()


def _ready_rows(document: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row
        for row in document.get("rows") or []
        if row.get("status") == "materialized" and row.get("training_ready") is True
    ]


def _confirmation_event(event_id: str) -> bool:
    """Stable one-third confirmation assignment fixed before model outcomes."""

    digest = hashlib.sha256(event_id.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % 3 == 0


def split_validation_inventory(
    source_path: Path,
    *,
    development_path: Path,
    confirmation_path: Path,
) -> dict[str, Any]:
    """Split a new validation campaign before any adaptation is trained."""

    source_path = Path(source_path)
    document = json.loads(source_path.read_text(encoding="utf-8"))
    if (document.get("configuration") or {}).get("split") != "validation":
        raise ValueError("expansion inventory is not a validation campaign")
    rows = list(document.get("rows") or [])
    development = [row for row in rows if not _confirmation_event(str(row["event_id"]))]
    confirmation = [row for row in rows if _confirmation_event(str(row["event_id"]))]

    def write_subset(path: Path, subset: list[dict[str, Any]], role: str) -> dict[str, Any]:
        ready = _ready_rows({"rows": subset})
        output = {
            **document,
            "schema": EXPANSION_SCHEMA,
            "generated_at": utc_now(),
            "parent_inventory": str(source_path.resolve()),
            "parent_inventory_sha256": sha256_file(source_path),
            "confirmation_assignment": "sha256(event_id)_uint64_mod_3_eq_0",
            "role": role,
            "rows": subset,
            "counts": {
                "rows": len(subset),
                "pairs_training_ready": len(ready),
                "events_training_ready": len({str(row["event_id"]) for row in ready}),
            },
        }
        _atomic_write_json(path, output)
        return output

    development_doc = write_subset(development_path, development, "development_validation")
    confirmation_doc = write_subset(
        confirmation_path, confirmation, "untouched_confirmation_validation"
    )
    dev_ready = _ready_rows(development_doc)
    confirm_ready = _ready_rows(confirmation_doc)
    if not dev_ready or not confirm_ready:
        raise ValueError("deterministic expansion split produced an empty ready cohort")
    return {
        "assignment": "sha256(event_id)_uint64_mod_3_eq_0",
        "development_ready": len(dev_ready),
        "confirmation_ready": len(confirm_ready),
        "development_events_sha256": set_digest({str(row["event_id"]) for row in dev_ready}),
        "confirmation_events_sha256": set_digest({str(row["event_id"]) for row in confirm_ready}),
    }


def validate_inventory_isolation(
    *,
    train_inventory_paths: list[Path],
    development_inventory_paths: list[Path],
    confirmation_inventory_path: Path,
    forbidden_inventory_path: Path,
) -> dict[str, Any]:
    """Prove event/pair isolation from the already-open prospective cohort."""

    def ids(paths: list[Path]) -> tuple[set[str], set[str]]:
        events: set[str] = set()
        pairs: set[str] = set()
        for path in paths:
            document = json.loads(Path(path).read_text(encoding="utf-8"))
            for row in _ready_rows(document):
                event = str(row["event_id"])
                pair = str(row["pair_id"])
                if event in events or pair in pairs:
                    raise ValueError("duplicate event or pair across expansion inventories")
                events.add(event)
                pairs.add(pair)
        return events, pairs

    train_events, train_pairs = ids(train_inventory_paths)
    development_events, development_pairs = ids(development_inventory_paths)
    confirmation_events, confirmation_pairs = ids([confirmation_inventory_path])
    forbidden = json.loads(Path(forbidden_inventory_path).read_text(encoding="utf-8"))
    forbidden_events = {str(row["event_id"]) for row in forbidden.get("rows") or []}
    forbidden_pairs = {str(row["pair_id"]) for row in forbidden.get("rows") or []}
    event_groups = (train_events, development_events, confirmation_events, forbidden_events)
    pair_groups = (train_pairs, development_pairs, confirmation_pairs, forbidden_pairs)
    for index, first in enumerate(event_groups):
        for second in event_groups[index + 1 :]:
            if first & second:
                raise ValueError("event leakage across TRAIN/VAL/confirmation/prospective")
    for index, first in enumerate(pair_groups):
        for second in pair_groups[index + 1 :]:
            if first & second:
                raise ValueError("pair leakage across TRAIN/VAL/confirmation/prospective")
    return {
        "event_disjoint": True,
        "pair_disjoint": True,
        "prospective_excluded": True,
        "counts": {
            "train_events": len(train_events),
            "development_events": len(development_events),
            "confirmation_events": len(confirmation_events),
            "forbidden_prospective_events": len(forbidden_events),
        },
        "digests": {
            "train_events_sha256": set_digest(train_events),
            "development_events_sha256": set_digest(development_events),
            "confirmation_events_sha256": set_digest(confirmation_events),
            "forbidden_events_sha256": set_digest(forbidden_events),
        },
    }


def evaluate_frozen_adaptation_on_validation(
    *,
    adaptation_summary_path: Path,
    dataset_root: Path,
    rcda_normalization_path: Path,
) -> dict[str, Any]:
    """Evaluate frozen thresholds on a validation-only confirmation root."""

    dataset_root = Path(dataset_root)
    if (dataset_root / "test.json").exists():
        raise ValueError("confirmation evaluator refuses a dataset containing TEST")
    adaptation = json.loads(Path(adaptation_summary_path).read_text(encoding="utf-8"))
    if adaptation.get("test_used_for_selection") is not False:
        raise ValueError("adaptation summary does not prove TEST isolation")
    if adaptation.get("wfigs_test_loaded") is not False:
        raise ValueError("adaptation summary loaded WFIGS TEST")
    manifest = json.loads((dataset_root / "validation.json").read_text(encoding="utf-8"))
    normalization = json.loads(Path(rcda_normalization_path).read_text(encoding="utf-8"))
    dataset = WFIGSExternalDataset(
        dataset_root=dataset_root,
        manifest=manifest,
        rcda_normalization=normalization,
        augment=False,
    )
    loader = make_loader(  # type: ignore[arg-type]
        dataset, batch_size=8, shuffle=False, weighted=False, num_workers=0
    )
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    models: list[torch.nn.Module] = []
    modes: list[str] = []
    reports: list[dict[str, Any]] = []
    for source in adaptation.get("reports") or []:
        config = source["config"]
        checkpoint = torch.load(Path(source["checkpoint"]), map_location=device, weights_only=False)
        if checkpoint.get("selection_split") != "wfigs_validation":
            raise ValueError("adapted checkpoint was not selected on WFIGS validation")
        if checkpoint.get("wfigs_test_evaluated") is not False:
            raise ValueError("adapted checkpoint has observed WFIGS TEST")
        model = prepare_model_for_device(
            build_model(
                str(config["model_name"]),
                in_channels=len(SEALED_CHANNEL_NAMES),
                base=int(config["base_channels"]),
            ),
            device,
        )
        model.load_state_dict(checkpoint["state_dict"])
        mode = str(config["target_mode"])
        metrics = evaluate_split(
            model,
            loader,
            device,
            float(source["selected_threshold"]),
            prediction_mode=mode,
        )
        reports.append(
            {
                "seed": int(config["seed"]),
                "threshold": float(source["selected_threshold"]),
                "metrics": metrics,
            }
        )
        models.append(model)
        modes.append(mode)
    ensemble_result = None
    frozen_ensemble = adaptation.get("ensemble")
    if frozen_ensemble:
        aggregation = str(frozen_ensemble["aggregation"])
        ensemble_model: torch.nn.Module
        if aggregation == "mean_seed_probability":
            if len(set(modes)) != 1:
                raise ValueError("mean ensemble target modes differ")
            ensemble_model = ProbabilityAveragingEnsemble(models).to(device)
            mode = modes[0]
        elif aggregation == "equal_weight_growth_probability_across_sources":
            ensemble_model = HeterogeneousGrowthProbabilityEnsemble(models, modes).to(device)
            mode = "hybrid"
        else:
            raise ValueError("unsupported frozen ensemble aggregation")
        metrics = evaluate_split(
            ensemble_model,
            loader,
            device,
            float(frozen_ensemble["selected_threshold"]),
            prediction_mode=mode,
        )
        ensemble_result = {
            "aggregation": aggregation,
            "threshold": float(frozen_ensemble["selected_threshold"]),
            "metrics": metrics,
        }
    return {
        "schema": "wfd_wfigs_frozen_confirmation_v1",
        "generated_at": utc_now(),
        "events": len(manifest.get("events") or []),
        "reports": reports,
        "ensemble": ensemble_result,
        "test_loaded": False,
        "thresholds_refit": False,
    }


def paired_event_comparison(
    candidate_metrics: dict[str, Any],
    baseline_metrics: dict[str, Any],
    *,
    seed: int = 20260824,
    n_resamples: int = 10_000,
) -> dict[str, Any]:
    """Paired event bootstrap for two frozen confirmation predictions."""

    candidate = candidate_metrics.get("per_event") or {}
    baseline = baseline_metrics.get("per_event") or {}
    if not candidate or set(candidate) != set(baseline):
        raise ValueError("paired confirmation event sets differ")
    events = sorted(candidate)
    candidate_iou = np.asarray([float(candidate[event]["iou"]) for event in events])
    baseline_iou = np.asarray([float(baseline[event]["iou"]) for event in events])
    delta = candidate_iou - baseline_iou
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, len(events), size=(n_resamples, len(events)))
    bootstrap = delta[indices].mean(axis=1)
    return {
        "events": len(events),
        "candidate_event_macro_iou": float(mean(candidate_iou)),
        "baseline_event_macro_iou": float(mean(baseline_iou)),
        "paired_delta": float(delta.mean()),
        "paired_delta_event_bootstrap_95_ci": [
            float(value) for value in np.quantile(bootstrap, [0.025, 0.975])
        ],
        "events_improved_fraction": float((delta > 0).mean()),
        "bootstrap_seed": seed,
        "bootstrap_resamples": n_resamples,
    }


__all__ = [
    "EXPANSION_SCHEMA",
    "evaluate_frozen_adaptation_on_validation",
    "paired_event_comparison",
    "set_digest",
    "sha256_file",
    "split_validation_inventory",
    "validate_inventory_isolation",
]
