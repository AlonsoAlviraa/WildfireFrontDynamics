"""Zero-shot WFIGS evaluation for a recipe frozen entirely on RCDA VAL."""

from __future__ import annotations

import json
from pathlib import Path
from statistics import mean
from typing import Any

import numpy as np
import torch
from scipy.ndimage import distance_transform_edt
from torch.utils.data import Dataset

from wildfire_front.open_if.regional.base import _atomic_write_json, utc_now
from wildfire_front.open_if.regional.wfigs_rights import wfigs_rights_summary

from .rcda_sealed import (
    SEALED_CHANNEL_NAMES,
    HeterogeneousGrowthProbabilityEnsemble,
    ProbabilityAveragingEnsemble,
    _augment,
    build_model,
    encode_features,
    evaluate_split,
    make_loader,
    prepare_model_for_device,
)
from .wfigs_tensor_dataset import WFIGS_CHANNELS

EXTERNAL_EVAL_SCHEMA = "wfd_rcda_wfigs_external_eval_v1"
WFIGS_GEOMETRY_FEATURE_NAMES = (
    "signed_front_distance",
    "front_normal_x",
    "front_normal_y",
)
RCDA_RAW_FROM_WFIGS = (
    "previous_fire",
    "dem",
    "blue",
    "green",
    "red",
    "ndvi",
    "wind_speed",
    "wind_direction_rad",
    "temperature_k",
    "precipitation_mm",
    "humidity_pct",
    "air_density",
)

_DRY_AIR_GAS_CONSTANT_J_KG_K = 287.05


def _wfigs_to_rcda_raw(
    raw_all: np.ndarray,
    *,
    horizon_hours: float,
) -> np.ndarray:
    """Convert WFIGS/HRRR physical channels to the RCDA/MERRA-2 raw contract.

    WFIGS stores HRRR ``APCP`` as accumulated water depth in millimetres and
    ``RH`` as relative humidity in percent.  The sealed RCDA normalization was
    fitted to MERRA-2 precipitation flux (kg m-2 s-1) and near-surface specific
    humidity (kg kg-1).  Temperature (K), air density (kg m-3), wind and EO
    channels already share compatible physical units.

    The precipitation conversion assumes that the stored APCP accumulation
    spans the pair horizon.  This approximation is explicit and, importantly,
    is fixed before WFIGS TEST is materialized or evaluated.
    """

    if not np.isfinite(horizon_hours) or horizon_hours <= 0.0:
        raise ValueError("WFIGS horizon_hours must be finite and positive")

    indices = [WFIGS_CHANNELS.index(name) for name in RCDA_RAW_FROM_WFIGS]
    raw = np.asarray(raw_all[indices], dtype=np.float32).copy()

    wind_index = RCDA_RAW_FROM_WFIGS.index("wind_speed")
    precipitation_index = RCDA_RAW_FROM_WFIGS.index("precipitation_mm")
    humidity_index = RCDA_RAW_FROM_WFIGS.index("humidity_pct")
    temperature_index = RCDA_RAW_FROM_WFIGS.index("temperature_k")
    density_index = RCDA_RAW_FROM_WFIGS.index("air_density")

    raw[wind_index] = np.maximum(raw[wind_index], 0.0)
    accumulation_mm = np.maximum(raw[precipitation_index], 0.0)
    raw[precipitation_index] = accumulation_mm / (horizon_hours * 3600.0)

    temperature_k = raw[temperature_index].astype(np.float64)
    density = np.maximum(raw[density_index].astype(np.float64), 0.0)
    relative_humidity = np.clip(raw[humidity_index].astype(np.float64), 0.0, 100.0)
    pressure_pa = density * _DRY_AIR_GAS_CONSTANT_J_KG_K * temperature_k
    temperature_c = temperature_k - 273.15
    saturation_vapor_pressure_pa = 611.2 * np.exp(
        (17.67 * temperature_c) / (temperature_c + 243.5)
    )
    vapor_pressure_pa = (relative_humidity / 100.0) * saturation_vapor_pressure_pa
    vapor_pressure_pa = np.minimum(vapor_pressure_pa, pressure_pa * 0.99)
    denominator = pressure_pa - 0.378 * vapor_pressure_pa
    specific_humidity = np.divide(
        0.622 * vapor_pressure_pa,
        denominator,
        out=np.zeros_like(vapor_pressure_pa),
        where=denominator > 0.0,
    )
    raw[humidity_index] = np.nan_to_num(
        specific_humidity,
        nan=0.0,
        posinf=0.0,
        neginf=0.0,
    ).astype(np.float32)
    return raw


def _front_geometry_features(previous_fire: np.ndarray) -> np.ndarray:
    """Encode front-relative geometry without using the future target.

    The signed distance is positive outside the previous perimeter and
    negative inside.  The two normalized finite-difference derivatives provide
    a local outward normal wherever the distance field has a gradient.  All
    channels are bounded, deterministic and derived only from ``previous_fire``.
    """

    previous = np.asarray(previous_fire, dtype=np.float32) > 0.5
    outside = distance_transform_edt(~previous).astype(np.float32)
    inside = distance_transform_edt(previous).astype(np.float32)
    signed = np.clip((outside - inside) / 32.0, -1.0, 1.0)
    gradient_y, gradient_x = np.gradient(signed)
    magnitude = np.hypot(gradient_x, gradient_y)
    normal_x = np.divide(
        gradient_x,
        magnitude,
        out=np.zeros_like(gradient_x, dtype=np.float32),
        where=magnitude > 1e-6,
    )
    normal_y = np.divide(
        gradient_y,
        magnitude,
        out=np.zeros_like(gradient_y, dtype=np.float32),
        where=magnitude > 1e-6,
    )
    return np.stack([signed, normal_x, normal_y]).astype(np.float32)


def _paired_event_bootstrap(
    reports: list[dict[str, Any]],
    baseline: dict[str, Any],
    *,
    n_resamples: int = 10_000,
    seed: int = 20260820,
) -> dict[str, Any]:
    """Compare the across-seed event mean with a fixed event-level baseline."""

    baseline_rows = baseline.get("per_event") or {}
    model_rows = [(report.get("metrics") or {}).get("per_event") or {} for report in reports]
    if not model_rows or not baseline_rows:
        raise ValueError("paired WFIGS comparison requires model and baseline events")
    event_set = set(baseline_rows)
    if any(set(rows) != event_set for rows in model_rows):
        raise ValueError("WFIGS model and geometry baseline event sets differ")
    events = sorted(event_set)
    baseline_iou = np.asarray([float(baseline_rows[event]) for event in events])
    seed_iou = np.asarray(
        [[float(rows[event]["iou"]) for event in events] for rows in model_rows],
        dtype=np.float64,
    )
    model_iou = seed_iou.mean(axis=0)
    delta = model_iou - baseline_iou
    rng = np.random.default_rng(seed)

    def ci(values: np.ndarray) -> list[float]:
        means = np.empty(n_resamples, dtype=np.float64)
        for start in range(0, n_resamples, 500):
            count = min(500, n_resamples - start)
            indices = rng.integers(0, values.size, size=(count, values.size))
            means[start : start + count] = values[indices].mean(axis=1)
        return [float(value) for value in np.quantile(means, [0.025, 0.975])]

    return {
        "events": len(events),
        "uncertainty_unit": "fire_event",
        "bootstrap_resamples": n_resamples,
        "bootstrap_seed": seed,
        "model_seed_mean_event_macro_iou": float(model_iou.mean()),
        "model_event_bootstrap_95_ci": ci(model_iou),
        "geometry_baseline_event_macro_iou": float(baseline_iou.mean()),
        "paired_delta": float(delta.mean()),
        "paired_delta_event_bootstrap_95_ci": ci(delta),
        "events_improved_fraction": float((delta > 0).mean()),
    }


class WFIGSExternalDataset(Dataset):
    """Map WFIGS physical tensors to the sealed RCDA input contract."""

    def __init__(
        self,
        *,
        dataset_root: Path,
        manifest: dict[str, Any],
        rcda_normalization: dict[str, Any],
        augment: bool = False,
        include_valid_mask: bool = False,
        include_geometry_features: bool = False,
    ) -> None:
        self.dataset_root = Path(dataset_root)
        self.samples = list(manifest.get("samples") or [])
        self.channel_min = np.asarray(rcda_normalization["channel_min"], dtype=np.float32)
        self.channel_max = np.asarray(rcda_normalization["channel_max"], dtype=np.float32)
        self.augment = augment
        self.include_valid_mask = include_valid_mask
        self.include_geometry_features = include_geometry_features
        if self.channel_min.shape != (12,) or self.channel_max.shape != (12,):
            raise ValueError("RCDA normalization must contain 12 raw channels")

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> dict[str, Any]:
        row = self.samples[index]
        with np.load(self.dataset_root / row["sample"], allow_pickle=False) as artifact:
            raw_all = np.asarray(artifact["inputs"], dtype=np.float32)
            target = np.asarray(artifact["target_growth"], dtype=np.float32)
            extent = np.asarray(artifact["target_extent"], dtype=np.float32)
            horizon = float(np.asarray(artifact["horizon_hours"]).item())
        valid = raw_all[WFIGS_CHANNELS.index("valid_data")] > 0.5
        for name in ("blue", "green", "red", "ndvi"):
            channel = raw_all[WFIGS_CHANNELS.index(name)]
            fill = float(np.median(channel[valid])) if valid.any() else 0.0
            channel[~valid] = fill
        raw = _wfigs_to_rcda_raw(raw_all, horizon_hours=horizon)
        features = encode_features(
            raw,
            channel_min=self.channel_min,
            channel_max=self.channel_max,
            horizon_hours=horizon,
        )
        if self.include_geometry_features:
            features = np.concatenate(
                [features, _front_geometry_features(raw_all[WFIGS_CHANNELS.index("previous_fire")])],
                axis=0,
            )
        if self.include_valid_mask:
            features = np.concatenate(
                [features, valid[None].astype(np.float32)],
                axis=0,
            )
        if self.augment:
            features, targets = _augment(features, np.stack([target, extent]))
            target, extent = targets[0], targets[1]
        return {
            "input": torch.from_numpy(np.ascontiguousarray(features)),
            "target": torch.from_numpy(target[None].copy()),
            "extent_target": torch.from_numpy(extent[None].copy()),
            "name": str(row["pair_id"]),
            "uid": str(row["event_id"]),
            "horizon_hours": horizon,
        }


def _geometry_baseline(
    path: Path, pair_ids: set[str]
) -> dict[str, Any]:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if (document.get("selection") or {}).get("test_not_used_for_selection") is not True:
        raise ValueError("WFIGS geometry baseline radius was not selected on validation")
    radius = int(document["selection"]["growth_transition_iou"]["selected_radius_m"])
    rows = [
        row
        for row in document.get("per_pair") or []
        if str(row.get("pair_id")) in pair_ids and row.get("status") == "usable"
    ]
    covered_pair_ids = {str(row["pair_id"]) for row in rows}
    missing_pair_ids = sorted(pair_ids - covered_pair_ids)
    if missing_pair_ids:
        raise ValueError(
            "WFIGS geometry baseline does not cover every TEST pair: "
            f"{missing_pair_ids[:5]}"
        )
    if len(rows) != len(covered_pair_ids):
        raise ValueError("WFIGS geometry baseline contains duplicate TEST pair rows")
    by_event: dict[str, list[float]] = {}
    for row in rows:
        value = float(row["radii"][str(radius)]["growth_transition_iou"])
        by_event.setdefault(str(row["event_id"]), []).append(value)
    per_event = {event: mean(values) for event, values in by_event.items()}
    return {
        "selected_radius_m": radius,
        "selected_on": "wfigs_validation",
        "test_used_for_selection": False,
        "event_macro_growth_iou": mean(per_event.values()) if per_event else 0.0,
        "events": len(per_event),
        "pairs": len(covered_pair_ids),
        "coverage_complete": True,
        "per_event": per_event,
    }


def evaluate_frozen_rcda_on_wfigs(
    *,
    final_summary_path: Path,
    wfigs_dataset_root: Path,
    rcda_normalization_path: Path,
    geometry_baseline_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    """Evaluate fixed RCDA checkpoints/thresholds once on WFIGS TEST."""

    final = json.loads(Path(final_summary_path).read_text(encoding="utf-8"))
    if final.get("test_used_for_selection") is not False:
        raise ValueError("final RCDA summary does not prove TEST isolation")
    manifest = json.loads((Path(wfigs_dataset_root) / "test.json").read_text(encoding="utf-8"))
    normalization = json.loads(Path(rcda_normalization_path).read_text(encoding="utf-8"))
    if normalization.get("fit_split") != "train":
        raise ValueError("RCDA normalization was not fitted on TRAIN")
    dataset = WFIGSExternalDataset(
        dataset_root=wfigs_dataset_root,
        manifest=manifest,
        rcda_normalization=normalization,
    )
    loader = make_loader(
        dataset,
        batch_size=8,
        shuffle=False,
        weighted=False,
        num_workers=0,
    )
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    reports: list[dict[str, Any]] = []
    seed_models: list[torch.nn.Module] = []
    for source_report in final.get("reports") or []:
        config = source_report["config"]
        checkpoint_path = Path(source_report["local_checkpoint"])
        checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
        if checkpoint.get("selection_split") != "val":
            raise ValueError(f"checkpoint not selected on RCDA VAL: {checkpoint_path}")
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
        seed_models.append(model)
        threshold = float(source_report["selected_threshold"])
        metrics = evaluate_split(
            model,
            loader,
            device,
            threshold,
            prediction_mode=str(config["target_mode"]),
            paper_metrics=True,
        )
        reports.append(
            {
                "seed": int(config["seed"]),
                "model_name": config["model_name"],
                "target_mode": config["target_mode"],
                "threshold": threshold,
                "threshold_selected_on": "rcda_validation",
                "wfigs_test_used_for_selection": False,
                "metrics": metrics,
            }
        )
    ensemble_result = None
    frozen_ensemble = final.get("ensemble")
    if frozen_ensemble:
        if (
            frozen_ensemble.get("aggregation") != "mean_seed_probability"
            or frozen_ensemble.get("threshold_selected_on") != "val"
            or frozen_ensemble.get("test_used_for_selection") is not False
        ):
            raise ValueError("RCDA ensemble was not frozen on RCDA VAL")
        ensemble_model = ProbabilityAveragingEnsemble(seed_models).to(device)
        ensemble_threshold = float(frozen_ensemble["selected_threshold"])
        ensemble_metrics = evaluate_split(
            ensemble_model,
            loader,
            device,
            ensemble_threshold,
            prediction_mode=str(final["reports"][0]["config"]["target_mode"]),
            paper_metrics=True,
        )
        ensemble_result = {
            "aggregation": "mean_seed_probability",
            "threshold": ensemble_threshold,
            "threshold_selected_on": "rcda_validation",
            "wfigs_test_used_for_selection": False,
            "metrics": ensemble_metrics,
        }
    pair_ids = {str(row["pair_id"]) for row in manifest.get("samples") or []}
    baseline = _geometry_baseline(geometry_baseline_path, pair_ids)
    model_values = [float(row["metrics"]["event_macro_iou"]) for row in reports]
    paired = _paired_event_bootstrap(reports, baseline)
    external_signal = (
        bool(model_values)
        and all(value > baseline["event_macro_growth_iou"] for value in model_values)
        and float(paired["paired_delta_event_bootstrap_95_ci"][0]) > 0.0
    )
    ensemble_paired = (
        _paired_event_bootstrap([ensemble_result], baseline, seed=20260821)
        if ensemble_result
        else None
    )
    report = {
        "schema": EXTERNAL_EVAL_SCHEMA,
        "generated_at": utc_now(),
        "device": str(device),
        "events": len({str(row["event_id"]) for row in manifest.get("samples") or []}),
        "samples": len(manifest.get("samples") or []),
        "reports": reports,
        "ensemble": ensemble_result,
        "geometry_baseline": baseline,
        "summary": {
            "model_event_macro_iou_mean": mean(model_values) if model_values else 0.0,
            "geometry_baseline_event_macro_iou": baseline["event_macro_growth_iou"],
            "all_seeds_above_geometry_baseline": bool(model_values)
            and all(value > baseline["event_macro_growth_iou"] for value in model_values),
            "paired_event_analysis": paired,
            "external_transfer_signal_gate": external_signal,
            "ensemble_event_macro_iou": (
                float(ensemble_result["metrics"]["event_macro_iou"])
                if ensemble_result
                else None
            ),
            "ensemble_paired_event_analysis": ensemble_paired,
        },
        "protocol": {
            "architecture_selected_on": "rcda_validation",
            "threshold_selected_on": "rcda_validation",
            "wfigs_test_used_for_selection": False,
            "wfigs_geometry_baseline_radius_selected_on": "wfigs_validation",
            "one_pair_per_event_in_materialization_campaign": True,
            "ensemble_threshold_selected_on": "rcda_validation"
            if ensemble_result
            else None,
        },
        "rights": wfigs_rights_summary(),
        "claims": {
            "external_evaluation_executed": True,
            "operational_generalization_proven": False,
            "public_checkpoint_or_tensor_release_allowed": False,
        },
    }
    _atomic_write_json(output_path, report)
    return report


def evaluate_adapted_rcda_on_wfigs(
    *,
    adaptation_summary_path: Path,
    wfigs_dataset_root: Path,
    rcda_normalization_path: Path,
    geometry_baseline_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    """Evaluate WFIGS-VAL-selected adapted checkpoints once on WFIGS TEST."""

    adaptation = json.loads(Path(adaptation_summary_path).read_text(encoding="utf-8"))
    if adaptation.get("test_used_for_selection") is not False:
        raise ValueError("adaptation summary does not prove TEST isolation")
    if adaptation.get("wfigs_test_loaded") is not False:
        raise ValueError("adaptation process loaded WFIGS TEST")
    dataset_root = Path(wfigs_dataset_root)
    manifest = json.loads((dataset_root / "test.json").read_text(encoding="utf-8"))
    normalization = json.loads(Path(rcda_normalization_path).read_text(encoding="utf-8"))
    dataset = WFIGSExternalDataset(
        dataset_root=dataset_root,
        manifest=manifest,
        rcda_normalization=normalization,
    )
    loader = make_loader(
        dataset,
        batch_size=8,
        shuffle=False,
        weighted=False,
        num_workers=0,
    )
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    reports: list[dict[str, Any]] = []
    adapted_models: list[torch.nn.Module] = []
    adapted_target_modes: list[str] = []
    for source in adaptation.get("reports") or []:
        config = source["config"]
        checkpoint_path = Path(source["checkpoint"])
        checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
        if not (
            checkpoint.get("selection_split") == "wfigs_validation"
            and checkpoint.get("wfigs_test_evaluated") is False
            and source.get("test_evaluated") is False
        ):
            raise ValueError(f"adapted checkpoint not selected on WFIGS VAL: {checkpoint_path}")
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
        threshold = float(source["selected_threshold"])
        metrics = evaluate_split(
            model,
            loader,
            device,
            threshold,
            prediction_mode=str(config["target_mode"]),
            paper_metrics=True,
        )
        reports.append(
            {
                "seed": int(config["seed"]),
                "threshold": threshold,
                "threshold_selected_on": "wfigs_validation",
                "wfigs_test_used_for_selection": False,
                "metrics": metrics,
            }
        )
        adapted_models.append(model)
        adapted_target_modes.append(str(config["target_mode"]))
    pair_ids = {str(row["pair_id"]) for row in manifest.get("samples") or []}
    baseline = _geometry_baseline(geometry_baseline_path, pair_ids)
    ensemble_result = None
    ensemble_paired = None
    ensemble_source = adaptation.get("ensemble")
    if ensemble_source:
        aggregation = str(ensemble_source.get("aggregation") or "")
        if (
            aggregation
            not in {
                "mean_seed_probability",
                "equal_weight_growth_probability_across_sources",
            }
            or ensemble_source.get("threshold_selected_on") != "wfigs_validation"
            or ensemble_source.get("test_used_for_selection") is not False
            or ensemble_source.get("test_evaluated") is not False
            or int(ensemble_source.get("members") or 0) != len(adapted_models)
        ):
            raise ValueError("adapted ensemble violates WFIGS VAL/TEST isolation")
        if aggregation == "mean_seed_probability":
            if len(set(adapted_target_modes)) != 1:
                raise ValueError("mean-seed ensemble target modes differ")
            ensemble_model = ProbabilityAveragingEnsemble(adapted_models).to(device)
            ensemble_prediction_mode = adapted_target_modes[0]
        else:
            ensemble_model = HeterogeneousGrowthProbabilityEnsemble(
                adapted_models,
                adapted_target_modes,
            ).to(device)
            ensemble_prediction_mode = "hybrid"
        ensemble_threshold = float(ensemble_source["selected_threshold"])
        ensemble_metrics = evaluate_split(
            ensemble_model,
            loader,
            device,
            ensemble_threshold,
            prediction_mode=ensemble_prediction_mode,
            paper_metrics=True,
        )
        ensemble_result = {
            "aggregation": aggregation,
            "members": len(adapted_models),
            "threshold": ensemble_threshold,
            "threshold_selected_on": "wfigs_validation",
            "wfigs_test_used_for_selection": False,
            "metrics": ensemble_metrics,
        }
        ensemble_paired = _paired_event_bootstrap(
            [{"metrics": ensemble_metrics}], baseline, seed=20260823
        )
    values = [float(row["metrics"]["event_macro_iou"]) for row in reports]
    paired = _paired_event_bootstrap(reports, baseline, seed=20260822)
    adapted_signal = (
        bool(values)
        and all(value > baseline["event_macro_growth_iou"] for value in values)
        and float(paired["paired_delta_event_bootstrap_95_ci"][0]) > 0.0
    )
    report = {
        "schema": "wfd_rcda_wfigs_adapted_test_v1",
        "generated_at": utc_now(),
        "device": str(device),
        "events": len({str(row["event_id"]) for row in manifest.get("samples") or []}),
        "samples": len(manifest.get("samples") or []),
        "reports": reports,
        "ensemble": ensemble_result,
        "geometry_baseline": baseline,
        "summary": {
            "adapted_event_macro_iou_mean": mean(values) if values else 0.0,
            "geometry_baseline_event_macro_iou": baseline["event_macro_growth_iou"],
            "all_seeds_above_geometry_baseline": bool(values)
            and all(value > baseline["event_macro_growth_iou"] for value in values),
            "paired_event_analysis": paired,
            "ensemble_event_macro_iou": (
                ensemble_result["metrics"]["event_macro_iou"]
                if ensemble_result
                else None
            ),
            "ensemble_paired_event_analysis": ensemble_paired,
            "adapted_transfer_signal_gate": adapted_signal,
        },
        "protocol": {
            "source_architecture_selected_on": "rcda_validation",
            "adapted_epoch_and_threshold_selected_on": "wfigs_validation",
            "wfigs_test_used_for_selection": False,
            "adapted_ensemble_threshold_selected_on": (
                "wfigs_validation" if ensemble_result else None
            ),
        },
        "rights": wfigs_rights_summary(),
        "claims": {
            "domain_adapted_test_evaluation_executed": True,
            "zero_shot_generalization": False,
            "operational_generalization_proven": False,
            "public_checkpoint_or_tensor_release_allowed": False,
        },
    }
    _atomic_write_json(output_path, report)
    return report


__all__ = [
    "EXTERNAL_EVAL_SCHEMA",
    "RCDA_RAW_FROM_WFIGS",
    "WFIGSExternalDataset",
    "_wfigs_to_rcda_raw",
    "evaluate_adapted_rcda_on_wfigs",
    "evaluate_frozen_rcda_on_wfigs",
]
