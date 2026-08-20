from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from scripts.run_wfigs_expansion_nightwatch import (
    PILOT_RECIPES,
    _claim_confirmation,
    _pilot_failure_record,
    _resume_confirmation,
    _validate_pilot_failure,
)
from wildfire_front.ml.wfigs_domain_adapt import WFIGSAdaptConfig
from wildfire_front.ml.wfigs_expansion import (
    fit_converted_train_normalization,
    paired_event_comparison,
    split_validation_inventory,
    validate_inventory_isolation,
)
from wildfire_front.ml.wfigs_tensor_dataset import WFIGS_CHANNELS


def _inventory(path: Path, split: str, events: list[str]) -> Path:
    rows = [
        {
            "event_id": event,
            "pair_id": f"pair-{event}",
            "split": split,
            "status": "materialized",
            "training_ready": True,
            "relative_path": f"{event}.npz",
        }
        for event in events
    ]
    path.write_text(
        json.dumps({"configuration": {"split": split}, "rows": rows}),
        encoding="utf-8",
    )
    return path


def test_validation_expansion_split_is_deterministic_and_disjoint(tmp_path: Path) -> None:
    source = _inventory(tmp_path / "source.json", "validation", [f"event-{i}" for i in range(30)])
    first = split_validation_inventory(
        source,
        development_path=tmp_path / "dev.json",
        confirmation_path=tmp_path / "confirm.json",
    )
    second = split_validation_inventory(
        source,
        development_path=tmp_path / "dev2.json",
        confirmation_path=tmp_path / "confirm2.json",
    )
    dev = json.loads((tmp_path / "dev.json").read_text())["rows"]
    confirm = json.loads((tmp_path / "confirm.json").read_text())["rows"]
    assert first == second
    assert {row["event_id"] for row in dev}.isdisjoint({row["event_id"] for row in confirm})
    assert first["development_ready"] + first["confirmation_ready"] == 30


def test_inventory_isolation_rejects_prospective_reuse(tmp_path: Path) -> None:
    train = _inventory(tmp_path / "train.json", "train", ["train"])
    dev = _inventory(tmp_path / "dev.json", "validation", ["dev"])
    confirm = _inventory(tmp_path / "confirm.json", "validation", ["confirm"])
    forbidden = _inventory(tmp_path / "forbidden.json", "test", ["confirm"])
    with pytest.raises(ValueError, match="event leakage"):
        validate_inventory_isolation(
            train_inventory_paths=[train],
            development_inventory_paths=[dev],
            confirmation_inventory_path=confirm,
            forbidden_inventory_path=forbidden,
        )


def test_paired_confirmation_bootstrap_reports_positive_delta() -> None:
    candidate = {
        "per_event": {event: {"iou": value} for event, value in {"a": 0.4, "b": 0.5}.items()}
    }
    baseline = {
        "per_event": {event: {"iou": value} for event, value in {"a": 0.1, "b": 0.2}.items()}
    }
    report = paired_event_comparison(candidate, baseline, n_resamples=100)
    assert report["events"] == 2
    assert report["paired_delta"] == pytest.approx(0.3)
    assert report["paired_delta_event_bootstrap_95_ci"][0] > 0


def test_confirmation_claim_resumes_without_reopening(tmp_path: Path) -> None:
    evidence = {"freeze": "a", "candidate": "b"}
    claim = tmp_path / "claim.json"
    result = tmp_path / "result.json"
    _claim_confirmation(claim, evidence)
    result.write_text(json.dumps({"evidence": evidence, "comparison": {}}), encoding="utf-8")
    assert _resume_confirmation(claim_path=claim, result_path=result, evidence=evidence) is not None
    with pytest.raises(ValueError, match="different frozen evidence"):
        _claim_confirmation(claim, {"freeze": "changed"})


def test_numeric_pilot_failure_is_bound_to_preregistered_recipe() -> None:
    config = WFIGSAdaptConfig(lr=5e-5, max_grad_norm=2.0, source_seeds=(47,))
    failure = _pilot_failure_record(
        name="candidate",
        config=config,
        normalization_mode="wfigs_converted_train",
        error=FloatingPointError("non-finite gradient"),
    )
    _validate_pilot_failure(
        failure,
        name="candidate",
        config=config,
        normalization_mode="wfigs_converted_train",
    )
    failure["configuration"]["lr"] = 1e-4
    with pytest.raises(ValueError, match="does not match preregistered recipe"):
        _validate_pilot_failure(
            failure,
            name="candidate",
            config=config,
            normalization_mode="wfigs_converted_train",
        )


def test_normalized_all_layer_candidate_avoids_unstable_pilot_rate() -> None:
    recipes = {name: config for name, config, _normalization in PILOT_RECIPES}
    candidate = recipes["all_intermediate_lr_wfigs_normalized"]
    assert candidate.lr == pytest.approx(5e-5)
    assert candidate.max_grad_norm == pytest.approx(2.0)


def test_converted_normalization_uses_train_only(tmp_path: Path) -> None:
    sample = tmp_path / "samples/train/pair.npz"
    sample.parent.mkdir(parents=True)
    values = np.linspace(0.1, 0.9, 16, dtype=np.float32).reshape(4, 4)
    inputs = np.stack(
        [
            values > 0.5,
            1000.0 + values,
            values,
            values * 0.9,
            values * 0.8,
            values * 2.0 - 1.0,
            np.ones_like(values),
            1.0 + values,
            values * 6.0 - 3.0,
            285.0 + values,
            values,
            30.0 + values,
            1.0 + values * 0.1,
        ],
        axis=0,
    ).astype(np.float32)
    np.savez_compressed(sample, inputs=inputs, horizon_hours=np.asarray(24.0))
    (tmp_path / "train.json").write_text(
        json.dumps(
            {
                "events": ["train-event"],
                "samples": [
                    {
                        "event_id": "train-event",
                        "pair_id": "pair",
                        "sample": "samples/train/pair.npz",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    reference = tmp_path / "reference.json"
    reference.write_text(
        json.dumps(
            {
                "fit_split": "train",
                "channel_min": [0.0] * 12,
                "channel_max": [1.0] * 12,
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "converted.json"

    report = fit_converted_train_normalization(
        dataset_root=tmp_path,
        reference_normalization_path=reference,
        output_path=output,
    )

    assert inputs.shape[0] == len(WFIGS_CHANNELS)
    assert report["fit_split"] == "train"
    assert report["test_loaded"] is False
    assert report["samples_used"] == 1
    assert len(report["channel_min"]) == 12
    assert output.is_file()

    (tmp_path / "test.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="containing TEST"):
        fit_converted_train_normalization(
            dataset_root=tmp_path,
            reference_normalization_path=reference,
            output_path=output,
        )
