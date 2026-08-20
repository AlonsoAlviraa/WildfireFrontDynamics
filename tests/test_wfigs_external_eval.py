"""Tests for the fixed RCDA-to-WFIGS feature bridge."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import torch

from wildfire_front.ml.rcda_sealed import build_model
from wildfire_front.ml.wfigs_external_eval import (
    RCDA_RAW_FROM_WFIGS,
    WFIGSExternalDataset,
    _geometry_baseline,
    _wfigs_to_rcda_raw,
    evaluate_adapted_rcda_on_wfigs,
    evaluate_frozen_rcda_on_wfigs,
)
from wildfire_front.ml.wfigs_tensor_dataset import WFIGS_CHANNELS


def test_wfigs_weather_units_are_converted_to_rcda_contract() -> None:
    inputs = np.zeros((len(WFIGS_CHANNELS), 2, 2), dtype=np.float32)
    inputs[WFIGS_CHANNELS.index("temperature_k")] = 293.15
    inputs[WFIGS_CHANNELS.index("air_density")] = 1.204
    inputs[WFIGS_CHANNELS.index("humidity_pct")] = 60.0
    inputs[WFIGS_CHANNELS.index("precipitation_mm")] = 36.0
    inputs[WFIGS_CHANNELS.index("wind_speed")] = -2.0

    raw = _wfigs_to_rcda_raw(inputs, horizon_hours=24.0)

    precipitation = raw[RCDA_RAW_FROM_WFIGS.index("precipitation_mm")]
    humidity = raw[RCDA_RAW_FROM_WFIGS.index("humidity_pct")]
    wind = raw[RCDA_RAW_FROM_WFIGS.index("wind_speed")]
    assert np.allclose(precipitation, 36.0 / (24.0 * 3600.0))
    assert np.allclose(humidity, 0.0087, rtol=0.05)
    assert np.all(wind == 0.0)


def test_wfigs_weather_conversion_requires_positive_horizon() -> None:
    inputs = np.zeros((len(WFIGS_CHANNELS), 1, 1), dtype=np.float32)
    with pytest.raises(ValueError, match="finite and positive"):
        _wfigs_to_rcda_raw(inputs, horizon_hours=0.0)


def test_external_dataset_maps_physical_channels_without_using_valid_mask_as_rcda_raw(
    tmp_path: Path,
) -> None:
    sample = tmp_path / "samples/test/pair.npz"
    sample.parent.mkdir(parents=True)
    inputs = np.stack(
        [np.full((8, 8), index, dtype=np.float32) for index in range(len(WFIGS_CHANNELS))]
    )
    inputs[WFIGS_CHANNELS.index("valid_data")] = 1.0
    inputs[WFIGS_CHANNELS.index("valid_data"), 0, 0] = 0.0
    inputs[WFIGS_CHANNELS.index("blue"), 0, 0] = 0.0
    np.savez_compressed(
        sample,
        inputs=inputs,
        target_growth=np.eye(8, dtype=np.uint8),
        target_extent=np.eye(8, dtype=np.uint8),
        horizon_hours=np.asarray(24.0, dtype=np.float32),
    )
    manifest = {
        "samples": [
            {
                "pair_id": "pair",
                "event_id": "event",
                "sample": sample.relative_to(tmp_path).as_posix(),
            }
        ]
    }
    dataset = WFIGSExternalDataset(
        dataset_root=tmp_path,
        manifest=manifest,
        rcda_normalization={"channel_min": [0.0] * 12, "channel_max": [20.0] * 12},
    )
    row = dataset[0]
    assert row["input"].shape == (16, 8, 8)
    assert row["uid"] == "event"
    assert "valid_data" not in RCDA_RAW_FROM_WFIGS
    assert float(row["horizon_hours"]) == 24.0
    assert float(row["input"][2, 0, 0]) == float(row["input"][2, 0, 1])


def test_geometry_manifest_contract_is_event_identified(tmp_path: Path) -> None:
    manifest = tmp_path / "test.json"
    manifest.write_text(
        json.dumps({"samples": [{"pair_id": "p", "event_id": "e"}]}),
        encoding="utf-8",
    )
    assert json.loads(manifest.read_text())["samples"][0]["event_id"] == "e"


def test_geometry_baseline_requires_complete_test_pair_coverage(tmp_path: Path) -> None:
    baseline = tmp_path / "geometry.json"
    baseline.write_text(
        json.dumps(
            {
                "selection": {
                    "test_not_used_for_selection": True,
                    "growth_transition_iou": {"selected_radius_m": 250},
                },
                "per_pair": [],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="does not cover every TEST pair"):
        _geometry_baseline(baseline, {"missing-pair"})


def test_zero_shot_evaluator_uses_frozen_threshold_once(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    sample = dataset / "samples/test/pair.npz"
    sample.parent.mkdir(parents=True)
    inputs = np.zeros((len(WFIGS_CHANNELS), 32, 32), dtype=np.float32)
    inputs[WFIGS_CHANNELS.index("valid_data")] = 1.0
    inputs[WFIGS_CHANNELS.index("previous_fire"), 14:18, 14:18] = 1.0
    extent = inputs[0].astype(np.uint8)
    extent[12:20, 12:20] = 1
    growth = np.logical_and(extent > 0, inputs[0] == 0).astype(np.uint8)
    np.savez_compressed(
        sample,
        inputs=inputs,
        target_growth=growth,
        target_extent=extent,
        horizon_hours=np.asarray(12.0, dtype=np.float32),
    )
    (dataset / "test.json").write_text(
        json.dumps(
            {
                "events": ["event"],
                "samples": [
                    {
                        "pair_id": "pair",
                        "event_id": "event",
                        "sample": sample.relative_to(dataset).as_posix(),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    normalization = tmp_path / "normalization.json"
    normalization.write_text(
        json.dumps(
            {
                "fit_split": "train",
                "channel_min": [0.0] * 12,
                "channel_max": [1.0] * 12,
            }
        ),
        encoding="utf-8",
    )
    checkpoint = tmp_path / "checkpoint.pt"
    model = build_model("unet", in_channels=16, base=8)
    torch.save(
        {"selection_split": "val", "state_dict": model.state_dict()}, checkpoint
    )
    final = tmp_path / "final.json"
    final.write_text(
        json.dumps(
            {
                "test_used_for_selection": False,
                "reports": [
                    {
                        "local_checkpoint": str(checkpoint),
                        "selected_threshold": 0.5,
                        "config": {
                            "seed": 11,
                            "model_name": "unet",
                            "base_channels": 8,
                            "target_mode": "growth",
                        },
                    }
                    ,
                    {
                        "local_checkpoint": str(checkpoint),
                        "selected_threshold": 0.5,
                        "config": {
                            "seed": 29,
                            "model_name": "unet",
                            "base_channels": 8,
                            "target_mode": "growth",
                        },
                    },
                ],
                "ensemble": {
                    "aggregation": "mean_seed_probability",
                    "threshold_selected_on": "val",
                    "selected_threshold": 0.5,
                    "test_used_for_selection": False,
                },
            }
        ),
        encoding="utf-8",
    )
    baseline = tmp_path / "geometry.json"
    baseline.write_text(
        json.dumps(
            {
                "selection": {
                    "test_not_used_for_selection": True,
                    "growth_transition_iou": {"selected_radius_m": 250},
                },
                "per_pair": [
                    {
                        "pair_id": "pair",
                        "event_id": "event",
                        "status": "usable",
                        "radii": {"250": {"growth_transition_iou": 0.1}},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    report = evaluate_frozen_rcda_on_wfigs(
        final_summary_path=final,
        wfigs_dataset_root=dataset,
        rcda_normalization_path=normalization,
        geometry_baseline_path=baseline,
        output_path=tmp_path / "external.json",
    )
    assert report["events"] == 1
    assert report["reports"][0]["threshold"] == 0.5
    assert report["ensemble"]["threshold"] == 0.5
    assert report["summary"]["ensemble_event_macro_iou"] is not None
    assert report["summary"]["paired_event_analysis"]["events"] == 1
    assert len(
        report["summary"]["paired_event_analysis"][
            "paired_delta_event_bootstrap_95_ci"
        ]
    ) == 2
    assert report["summary"]["ensemble_paired_event_analysis"]["events"] == 1
    assert report["protocol"]["wfigs_test_used_for_selection"] is False


def test_adapted_evaluator_uses_val_selected_ensemble_once(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    sample = dataset / "samples/test/pair.npz"
    sample.parent.mkdir(parents=True)
    inputs = np.zeros((len(WFIGS_CHANNELS), 32, 32), dtype=np.float32)
    inputs[WFIGS_CHANNELS.index("valid_data")] = 1.0
    inputs[WFIGS_CHANNELS.index("previous_fire"), 14:18, 14:18] = 1.0
    extent = inputs[0].astype(np.uint8)
    extent[12:20, 12:20] = 1
    growth = np.logical_and(extent > 0, inputs[0] == 0).astype(np.uint8)
    np.savez_compressed(
        sample,
        inputs=inputs,
        target_growth=growth,
        target_extent=extent,
        horizon_hours=np.asarray(12.0, dtype=np.float32),
    )
    (dataset / "test.json").write_text(
        json.dumps(
            {
                "events": ["event"],
                "samples": [
                    {
                        "pair_id": "pair",
                        "event_id": "event",
                        "sample": sample.relative_to(dataset).as_posix(),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    normalization = tmp_path / "normalization.json"
    normalization.write_text(
        json.dumps(
            {
                "fit_split": "train",
                "channel_min": [0.0] * 12,
                "channel_max": [1.0] * 12,
            }
        ),
        encoding="utf-8",
    )
    checkpoint = tmp_path / "adapted.pt"
    model = build_model("unet", in_channels=16, base=8)
    torch.save(
        {
            "selection_split": "wfigs_validation",
            "wfigs_test_evaluated": False,
            "state_dict": model.state_dict(),
        },
        checkpoint,
    )
    adaptation = tmp_path / "adaptation.json"
    adaptation.write_text(
        json.dumps(
            {
                "test_used_for_selection": False,
                "wfigs_test_loaded": False,
                "reports": [
                    {
                        "checkpoint": str(checkpoint),
                        "selected_threshold": 0.5,
                        "test_evaluated": False,
                        "config": {
                            "seed": seed,
                            "model_name": "unet",
                            "base_channels": 8,
                            "target_mode": "growth",
                        },
                    }
                    for seed in (11, 29)
                ],
                "ensemble": {
                    "aggregation": "mean_seed_probability",
                    "members": 2,
                    "selected_threshold": 0.45,
                    "threshold_selected_on": "wfigs_validation",
                    "test_used_for_selection": False,
                    "test_evaluated": False,
                },
            }
        ),
        encoding="utf-8",
    )
    baseline = tmp_path / "geometry.json"
    baseline.write_text(
        json.dumps(
            {
                "selection": {
                    "test_not_used_for_selection": True,
                    "growth_transition_iou": {"selected_radius_m": 250},
                },
                "per_pair": [
                    {
                        "pair_id": "pair",
                        "event_id": "event",
                        "status": "usable",
                        "radii": {"250": {"growth_transition_iou": 0.1}},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    report = evaluate_adapted_rcda_on_wfigs(
        adaptation_summary_path=adaptation,
        wfigs_dataset_root=dataset,
        rcda_normalization_path=normalization,
        geometry_baseline_path=baseline,
        output_path=tmp_path / "adapted_external.json",
    )
    assert report["ensemble"]["threshold"] == 0.45
    assert report["ensemble"]["threshold_selected_on"] == "wfigs_validation"
    assert report["summary"]["ensemble_event_macro_iou"] is not None
    assert report["summary"]["ensemble_paired_event_analysis"]["events"] == 1
    assert report["protocol"]["wfigs_test_used_for_selection"] is False


def test_adapted_evaluator_supports_cross_source_growth_heads(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    sample = dataset / "samples/test/pair.npz"
    sample.parent.mkdir(parents=True)
    inputs = np.zeros((len(WFIGS_CHANNELS), 16, 16), dtype=np.float32)
    inputs[WFIGS_CHANNELS.index("valid_data")] = 1.0
    inputs[WFIGS_CHANNELS.index("previous_fire"), 7:9, 7:9] = 1.0
    extent = inputs[0].astype(np.uint8)
    extent[6:10, 6:10] = 1
    growth = np.logical_and(extent > 0, inputs[0] == 0).astype(np.uint8)
    np.savez_compressed(
        sample,
        inputs=inputs,
        target_growth=growth,
        target_extent=extent,
        horizon_hours=np.asarray(12.0, dtype=np.float32),
    )
    (dataset / "test.json").write_text(
        json.dumps(
            {
                "events": ["event"],
                "samples": [
                    {
                        "pair_id": "pair",
                        "event_id": "event",
                        "sample": sample.relative_to(dataset).as_posix(),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    normalization = tmp_path / "normalization.json"
    normalization.write_text(
        json.dumps(
            {
                "fit_split": "train",
                "channel_min": [0.0] * 12,
                "channel_max": [1.0] * 12,
            }
        ),
        encoding="utf-8",
    )
    model_specs = (("unet", "hybrid"), ("resunet_multitask", "multitask"))
    reports = []
    for seed, (model_name, target_mode) in zip((11, 29), model_specs, strict=True):
        checkpoint = tmp_path / f"adapted-{seed}.pt"
        model = build_model(model_name, in_channels=16, base=8)
        torch.save(
            {
                "selection_split": "wfigs_validation",
                "wfigs_test_evaluated": False,
                "state_dict": model.state_dict(),
            },
            checkpoint,
        )
        reports.append(
            {
                "checkpoint": str(checkpoint),
                "selected_threshold": 0.5,
                "test_evaluated": False,
                "config": {
                    "seed": seed,
                    "model_name": model_name,
                    "base_channels": 8,
                    "target_mode": target_mode,
                },
            }
        )
    adaptation = tmp_path / "adaptation-cross.json"
    adaptation.write_text(
        json.dumps(
            {
                "test_used_for_selection": False,
                "wfigs_test_loaded": False,
                "reports": reports,
                "ensemble": {
                    "aggregation": "equal_weight_growth_probability_across_sources",
                    "members": 2,
                    "selected_threshold": 0.45,
                    "threshold_selected_on": "wfigs_validation",
                    "test_used_for_selection": False,
                    "test_evaluated": False,
                },
            }
        ),
        encoding="utf-8",
    )
    baseline = tmp_path / "geometry.json"
    baseline.write_text(
        json.dumps(
            {
                "selection": {
                    "test_not_used_for_selection": True,
                    "growth_transition_iou": {"selected_radius_m": 250},
                },
                "per_pair": [
                    {
                        "pair_id": "pair",
                        "event_id": "event",
                        "status": "usable",
                        "radii": {"250": {"growth_transition_iou": 0.1}},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    report = evaluate_adapted_rcda_on_wfigs(
        adaptation_summary_path=adaptation,
        wfigs_dataset_root=dataset,
        rcda_normalization_path=normalization,
        geometry_baseline_path=baseline,
        output_path=tmp_path / "cross-external.json",
    )

    assert report["ensemble"]["aggregation"] == (
        "equal_weight_growth_probability_across_sources"
    )
    assert report["ensemble"]["members"] == 2
