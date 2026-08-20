from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import torch

import wildfire_front.ml.rcda_sealed as rcda_sealed
from wildfire_front.ml.rcda_sealed import (
    SEALED_CHANNEL_NAMES,
    ProbabilityAveragingEnsemble,
    SealedRCDADataset,
    SealedTrainConfig,
    _augment,
    _threshold_confusions,
    build_model,
    confusion,
    encode_features,
    background_bce_loss,
    focal_tversky_loss,
    load_protocol,
    train_sealed,
)


def test_probability_ensemble_matches_mean_seed_probability() -> None:
    first = torch.nn.Conv2d(2, 1, 1)
    second = torch.nn.Conv2d(2, 1, 1)
    torch.nn.init.constant_(first.weight, 0.2)
    torch.nn.init.constant_(first.bias, -0.1)
    torch.nn.init.constant_(second.weight, -0.3)
    torch.nn.init.constant_(second.bias, 0.4)
    inputs = torch.randn(3, 2, 8, 8)
    ensemble = ProbabilityAveragingEnsemble([first, second])
    expected = (torch.sigmoid(first(inputs)) + torch.sigmoid(second(inputs))) / 2.0
    actual = torch.sigmoid(ensemble(inputs))
    assert torch.allclose(actual, expected, atol=1e-6)


def _write_tiny_dataset(root: Path) -> None:
    dataset = root / "dataset"
    protocol = root / "protocol"
    for split in ("train", "val", "test"):
        (dataset / split / "inputs").mkdir(parents=True)
        (dataset / split / "labels").mkdir(parents=True)
    events = {
        "train": ["UID_FIRE_1", "UID_FIRE_2"],
        "val": ["UID_FIRE_3"],
        "test": ["UID_FIRE_4"],
    }
    samples: dict[str, list[dict[str, object]]] = {split: [] for split in events}
    rng = np.random.default_rng(0)
    for split, uids in events.items():
        for uid in uids:
            for day in (1, 2):
                name = f"{uid}_2018-08-0{day}.npy"
                previous = np.zeros((32, 32), dtype=np.float32)
                previous[8:12, 8:12] = 1.0
                label = previous.copy()
                label[8:13, 8:14] = 1.0
                inputs = rng.random((12, 32, 32), dtype=np.float32)
                inputs[0] = previous
                inputs[7] = 0.3
                rel_in = f"{split}/inputs/{name}"
                rel_lab = f"{split}/labels/{name}"
                np.save(dataset / rel_in, inputs)
                np.save(dataset / rel_lab, label.astype(bool))
                samples[split].append(
                    {
                        "name": name,
                        "uid": uid,
                        "year": 2018,
                        "input": rel_in,
                        "label": rel_lab,
                    }
                )
    for split in events:
        (protocol).mkdir(parents=True, exist_ok=True)
        (protocol / f"{split}.json").write_text(
            json.dumps(
                {
                    "schema": "wfd_rcda_event_split_manifest_v1",
                    "split": split,
                    "seed": "wfd_rcda_event_split_v1",
                    "events": events[split],
                    "samples": samples[split],
                    "n_events": len(events[split]),
                    "n_samples": len(samples[split]),
                }
            ),
            encoding="utf-8",
        )
    (protocol / "normalization_train_only.json").write_text(
        json.dumps(
            {
                "schema": "wfd_rcda_train_only_minmax_v1",
                "fit_split": "train",
                "channel_min": [0.0] * 12,
                "channel_max": [1.0] * 12,
            }
        ),
        encoding="utf-8",
    )


def test_encode_features_uses_train_stats_and_circular_wind() -> None:
    raw = np.zeros((12, 8, 8), dtype=np.float32)
    raw[0, 2:4, 2:4] = 1.0
    raw[7] = np.pi / 2
    encoded = encode_features(
        raw,
        channel_min=np.zeros(12, dtype=np.float32),
        channel_max=np.ones(12, dtype=np.float32),
        horizon_hours=24.0,
    )
    assert encoded.shape[0] == len(SEALED_CHANNEL_NAMES)
    assert np.allclose(encoded[7], 1.0, atol=1e-5)
    assert np.allclose(encoded[8], 0.0, atol=1e-5)
    assert encoded[13, 2, 2] == 0.0
    assert encoded[13, 0, 0] > encoded[13, 2, 5]
    assert encoded[14, 2, 2] == 0.0
    assert encoded[15].min() == encoded[15].max() == 0.5


def test_augment_reflects_the_correct_wind_component(monkeypatch) -> None:
    features = np.zeros((16, 4, 5), dtype=np.float32)
    features[7] = 0.6  # east = sin(direction)
    features[8] = 0.8  # north = cos(direction)
    targets = np.zeros((2, 4, 5), dtype=np.float32)

    vertical_draws = iter((1.0, 0.0))
    monkeypatch.setattr("wildfire_front.ml.rcda_sealed.random.random", lambda: next(vertical_draws))
    monkeypatch.setattr("wildfire_front.ml.rcda_sealed.random.choice", lambda _values: 0)
    vertical, _ = _augment(features.copy(), targets.copy())
    assert np.allclose(vertical[7], 0.6)
    assert np.allclose(vertical[8], -0.8)

    horizontal_draws = iter((0.0, 1.0))
    monkeypatch.setattr(
        "wildfire_front.ml.rcda_sealed.random.random", lambda: next(horizontal_draws)
    )
    horizontal, _ = _augment(features.copy(), targets.copy())
    assert np.allclose(horizontal[7], -0.6)
    assert np.allclose(horizontal[8], 0.8)


def test_focal_tversky_is_lower_when_prediction_matches() -> None:
    target = torch.zeros(1, 1, 4, 4)
    target[:, :, 1:3, 1:3] = 1.0
    perfect = torch.logit(target.clamp(1e-4, 1 - 1e-4))
    wrong = torch.full_like(perfect, -4.0)
    assert float(focal_tversky_loss(perfect, target)) < float(focal_tversky_loss(wrong, target))


def test_background_bce_rewards_suppressed_non_growth_logits() -> None:
    target = torch.zeros(1, 1, 4, 4)
    target[:, :, 1, 1] = 1.0
    suppressed = torch.full_like(target, -4.0)
    elevated = torch.full_like(target, 4.0)
    assert float(background_bce_loss(suppressed, target)) < float(
        background_bce_loss(elevated, target)
    )


def test_background_bce_is_zero_for_all_growth_target() -> None:
    target = torch.ones(1, 1, 2, 2)
    logits = torch.zeros_like(target)
    assert float(background_bce_loss(logits, target)) == 0.0


def test_event_balance_power_removes_duration_mass_from_sample_weight(tmp_path: Path) -> None:
    _write_tiny_dataset(tmp_path)
    manifest_path = tmp_path / "protocol/train.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["samples"] = [
        row
        for row in manifest["samples"]
        if row["uid"] == "UID_FIRE_1" or row["name"].endswith("2018-08-01.npy")
    ]
    normalization = json.loads(
        (tmp_path / "protocol/normalization_train_only.json").read_text(encoding="utf-8")
    )
    dataset = SealedRCDADataset(
        tmp_path / "dataset", manifest, normalization, augment=False
    )
    long_index = next(i for i, row in enumerate(dataset.samples) if row["uid"] == "UID_FIRE_1")
    short_index = next(i for i, row in enumerate(dataset.samples) if row["uid"] == "UID_FIRE_2")
    long_weight = dataset.sample_weight(long_index, event_balance_power=1.0)
    short_weight = dataset.sample_weight(short_index, event_balance_power=1.0)
    assert long_weight == short_weight / 2.0


def test_uniform_event_sampling_assigns_equal_total_mass_per_fire(tmp_path: Path) -> None:
    _write_tiny_dataset(tmp_path)
    manifest = json.loads((tmp_path / "protocol/train.json").read_text(encoding="utf-8"))
    manifest["samples"] = [
        row
        for row in manifest["samples"]
        if row["uid"] == "UID_FIRE_1" or row["name"].endswith("2018-08-01.npy")
    ]
    normalization = json.loads(
        (tmp_path / "protocol/normalization_train_only.json").read_text(encoding="utf-8")
    )
    dataset = SealedRCDADataset(tmp_path / "dataset", manifest, normalization, augment=False)
    mass: dict[str, float] = {}
    for index, row in enumerate(dataset.samples):
        mass[str(row["uid"])] = mass.get(str(row["uid"]), 0.0) + dataset.sample_weight(
            index, sampling_strategy="uniform_events"
        )
    assert mass == {"UID_FIRE_1": 1.0, "UID_FIRE_2": 1.0}


def test_sampler_rejects_unknown_strategy(tmp_path: Path) -> None:
    _write_tiny_dataset(tmp_path)
    manifest = json.loads((tmp_path / "protocol/train.json").read_text(encoding="utf-8"))
    normalization = json.loads(
        (tmp_path / "protocol/normalization_train_only.json").read_text(encoding="utf-8")
    )
    dataset = SealedRCDADataset(tmp_path / "dataset", manifest, normalization, augment=False)
    with pytest.raises(ValueError, match="sampling_strategy"):
        dataset.sample_weight(0, sampling_strategy="unknown")


def test_load_protocol_rejects_event_leak(tmp_path: Path) -> None:
    _write_tiny_dataset(tmp_path)
    leaked = json.loads((tmp_path / "protocol/test.json").read_text(encoding="utf-8"))
    leaked["events"].append("UID_FIRE_1")
    (tmp_path / "protocol/test.json").write_text(json.dumps(leaked), encoding="utf-8")
    try:
        load_protocol(tmp_path / "protocol")
    except ValueError as exc:
        assert "disjoint" in str(exc)
    else:
        raise AssertionError("leaking protocol must fail")


def test_train_sealed_selects_on_val_and_tests_once(tmp_path: Path) -> None:
    _write_tiny_dataset(tmp_path)
    report = train_sealed(
        SealedTrainConfig(
            dataset_root=str(tmp_path / "dataset"),
            protocol_dir=str(tmp_path / "protocol"),
            output_dir=str(tmp_path / "out"),
            model_name="unet",
            seed=0,
            epochs=1,
            batch_size=2,
            patience=1,
            num_workers=0,
            amp=False,
            smoke=True,
        )
    )
    assert report["threshold_selected_on"] == "val"
    assert report["test_used_for_selection"] is False
    assert report["normalization_fit_split"] == "train"
    assert report["config"]["max_grad_norm"] == 5.0
    assert {"python", "torch", "numpy", "scipy", "cuda_runtime", "cudnn"} <= set(
        report["software_versions"]
    )
    assert report["determinism"] == {
        "cudnn_deterministic": True,
        "cudnn_benchmark": False,
    }
    assert "test_once" in report
    assert "far_gt_10_5px_recall" in report["test_once"]
    assert Path(report["checkpoint"]).is_file()
    payload = torch.load(report["checkpoint"], map_location="cpu", weights_only=False)
    assert payload["selection_split"] == "val"
    assert payload["in_channels"] == len(SEALED_CHANNEL_NAMES)
    assert "test" not in payload


def test_train_sealed_fails_fast_on_nonfinite_loss(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_tiny_dataset(tmp_path)

    def nonfinite_loss(*args, **kwargs):  # noqa: ANN002, ANN003
        logits = args[0]
        return torch.full((), float("nan"), device=logits.device, requires_grad=True)

    monkeypatch.setattr(rcda_sealed, "objective_loss", nonfinite_loss)
    with pytest.raises(FloatingPointError, match=r"epoch=1 batch=0"):
        train_sealed(
            SealedTrainConfig(
                dataset_root=str(tmp_path / "dataset"),
                protocol_dir=str(tmp_path / "protocol"),
                output_dir=str(tmp_path / "nonfinite"),
                model_name="unet",
                epochs=1,
                batch_size=2,
                num_workers=0,
                amp=False,
                smoke=True,
            )
        )


def test_train_sealed_retains_finite_checkpoint_after_late_nonfinite_loss(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_tiny_dataset(tmp_path)
    original_loss = rcda_sealed.objective_loss
    calls = 0

    def late_nonfinite_loss(*args, **kwargs):  # noqa: ANN002, ANN003
        nonlocal calls
        calls += 1
        if calls > 2:
            logits = args[0]
            return torch.full((), float("nan"), device=logits.device, requires_grad=True)
        return original_loss(*args, **kwargs)

    monkeypatch.setattr(rcda_sealed, "objective_loss", late_nonfinite_loss)
    report = train_sealed(
        SealedTrainConfig(
            dataset_root=str(tmp_path / "dataset"),
            protocol_dir=str(tmp_path / "protocol"),
            output_dir=str(tmp_path / "late_nonfinite"),
            model_name="unet",
            epochs=2,
            batch_size=2,
            num_workers=0,
            amp=False,
            smoke=True,
            evaluate_test=False,
            compute_paper_metrics=False,
        )
    )

    assert report["best_epoch"] == 1
    assert report["test_evaluated"] is False
    assert report["training_termination"]["status"] == (
        "truncated_after_nonfinite_optimization"
    )
    assert report["training_termination"]["failed_epoch"] == 2
    assert report["training_termination"]["checkpoint_finite"] is True


def test_vectorized_threshold_confusions_match_scalar_reference() -> None:
    rng = np.random.default_rng(4)
    probabilities = rng.random((6, 7))
    target = rng.random((6, 7)) > 0.7
    thresholds = (0.1, 0.35, 0.5, 0.9)
    predictions = probabilities[None] >= np.asarray(thresholds)[:, None, None]

    rows = _threshold_confusions(predictions, target)

    expected = np.stack([confusion(row, target) for row in predictions])
    assert np.array_equal(rows, expected)


def test_film_model_has_weather_distance_residual_prior() -> None:
    model = build_model("film_unet", in_channels=16, base=16)
    inputs = torch.zeros(2, 16, 32, 32)
    inputs[:, 13] = torch.linspace(0, 1, 32)[None, None, :]
    inputs[:, 15] = 0.5

    output = model(inputs)

    assert output.shape == (2, 1, 32, 32)
    assert tuple(model.PRIOR_CHANNELS) == (6, 7, 8, 9, 10, 11, 12, 13, 14, 15)


def test_multitask_resunet_has_distinct_growth_and_extent_heads() -> None:
    model = build_model("resunet_multitask", in_channels=16, base=16)

    output = model(torch.zeros(2, 16, 32, 32))

    assert output.shape == (2, 2, 32, 32)
    growth = rcda_sealed.prediction_logits(output, "multitask")
    assert growth.shape == (2, 1, 32, 32)


def test_multitask_objective_rewards_correct_growth_and_extent_heads() -> None:
    growth = torch.zeros(1, 1, 4, 4)
    growth[:, :, 2, 2] = 1.0
    extent = torch.zeros_like(growth)
    extent[:, :, 1:3, 1:3] = 1.0
    inputs = torch.zeros(1, 16, 4, 4)
    correct = torch.cat(
        [
            torch.logit(growth.clamp(1e-4, 1 - 1e-4)),
            torch.logit(extent.clamp(1e-4, 1 - 1e-4)),
        ],
        dim=1,
    )
    swapped = correct.flip(1)
    config = SealedTrainConfig(
        dataset_root="unused",
        protocol_dir="unused",
        output_dir="unused",
        model_name="resunet_multitask",
        target_mode="multitask",
    )

    correct_loss = rcda_sealed.objective_loss(correct, inputs, growth, extent, config)
    swapped_loss = rcda_sealed.objective_loss(swapped, inputs, growth, extent, config)

    assert float(correct_loss) < float(swapped_loss)


def test_front_ring_bce_rewards_correct_growth_inside_physical_ring() -> None:
    inputs = torch.zeros(1, 16, 4, 4)
    inputs[:, 13] = 1.0
    inputs[:, 13, 1:3, 1:3] = 0.25
    target = torch.zeros(1, 1, 4, 4)
    target[:, :, 2, 2] = 1.0
    correct = torch.full_like(target, -4.0)
    correct[:, :, 2, 2] = 4.0
    wrong = -correct

    correct_loss = rcda_sealed.front_ring_bce_loss(
        correct,
        inputs,
        target,
        radius_px=16.0,
    )
    wrong_loss = rcda_sealed.front_ring_bce_loss(
        wrong,
        inputs,
        target,
        radius_px=16.0,
    )

    assert float(correct_loss) < float(wrong_loss)


def test_front_ring_bce_ignores_logits_outside_selected_radius() -> None:
    inputs = torch.zeros(1, 16, 4, 4)
    inputs[:, 13] = 1.0
    inputs[:, 13, 1:3, 1:3] = 0.25
    target = torch.zeros(1, 1, 4, 4)
    first = torch.zeros_like(target)
    second = first.clone()
    second[:, :, 0, 0] = 100.0

    first_loss = rcda_sealed.front_ring_bce_loss(
        first,
        inputs,
        target,
        radius_px=16.0,
    )
    second_loss = rcda_sealed.front_ring_bce_loss(
        second,
        inputs,
        target,
        radius_px=16.0,
    )

    assert torch.equal(first_loss, second_loss)


def test_multitask_prediction_rejects_single_head_output() -> None:
    with pytest.raises(ValueError, match="two output channels"):
        rcda_sealed.prediction_logits(torch.zeros(1, 1, 4, 4), "multitask")


def test_multitask_training_is_validation_only_and_checkpointed(tmp_path: Path) -> None:
    _write_tiny_dataset(tmp_path)

    report = train_sealed(
        SealedTrainConfig(
            dataset_root=str(tmp_path / "dataset"),
            protocol_dir=str(tmp_path / "protocol"),
            output_dir=str(tmp_path / "multitask"),
            model_name="resunet_multitask",
            run_name="multitask-smoke",
            target_mode="multitask",
            front_ring_bce_weight=0.15,
            front_ring_radius_px=16.0,
            evaluate_test=False,
            compute_paper_metrics=False,
            seed=0,
            epochs=1,
            batch_size=2,
            patience=1,
            num_workers=0,
            amp=False,
            smoke=True,
            base_channels=8,
        )
    )

    assert report["test_evaluated"] is False
    assert report["config"]["target_mode"] == "multitask"
    assert report["config"]["front_ring_bce_weight"] == 0.15
    checkpoint = torch.load(report["checkpoint"], map_location="cpu", weights_only=False)
    assert checkpoint["model_name"] == "resunet_multitask"
    assert checkpoint["target_mode"] == "multitask"


def test_tuning_mode_never_evaluates_test(tmp_path: Path) -> None:
    _write_tiny_dataset(tmp_path)
    report = train_sealed(
        SealedTrainConfig(
            dataset_root=str(tmp_path / "dataset"),
            protocol_dir=str(tmp_path / "protocol"),
            output_dir=str(tmp_path / "tune"),
            model_name="aspp_unet",
            run_name="tune-hybrid",
            target_mode="hybrid",
            evaluate_test=False,
            seed=0,
            epochs=1,
            batch_size=2,
            patience=1,
            num_workers=0,
            amp=False,
            smoke=True,
        )
    )
    assert report["test_evaluated"] is False
    assert "test_once" not in report
    assert report["val"]["selection_metric"] == "event_macro_iou"
    assert report["history"][0]["val_selection_metric"] == "event_macro_iou"
    assert report["history"][0]["val_selection_threshold"] in {value / 10 for value in range(1, 10)}
