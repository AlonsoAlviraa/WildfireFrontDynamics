"""Smoke test for VAL-only WFIGS domain adaptation."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import torch

from wildfire_front.ml.rcda_sealed import build_model
from wildfire_front.ml.wfigs_domain_adapt import (
    WFIGSAdaptConfig,
    adapt_frozen_rcda_on_wfigs,
    configure_trainable_scope,
    set_adaptation_train_mode,
)
from wildfire_front.ml.wfigs_tensor_dataset import WFIGS_CHANNELS


def _sample(root: Path, split: str, pair: str, event: str) -> dict:
    path = root / f"samples/{split}/{pair}.npz"
    path.parent.mkdir(parents=True, exist_ok=True)
    inputs = np.zeros((len(WFIGS_CHANNELS), 32, 32), dtype=np.float32)
    inputs[0, 14:18, 14:18] = 1.0
    target_extent = inputs[0].astype(np.uint8)
    target_extent[12:20, 12:20] = 1
    target_growth = np.logical_and(target_extent > 0, inputs[0] == 0).astype(np.uint8)
    np.savez_compressed(
        path,
        inputs=inputs,
        target_growth=target_growth,
        target_extent=target_extent,
        horizon_hours=np.asarray(12.0, dtype=np.float32),
    )
    return {
        "pair_id": pair,
        "event_id": event,
        "sample": path.relative_to(root).as_posix(),
    }


def test_domain_adaptation_never_requires_wfigs_test(tmp_path: Path) -> None:
    progress: list[dict] = []
    dataset = tmp_path / "dataset"
    train = [_sample(dataset, "train", "train-pair", "train-event")]
    validation = [_sample(dataset, "validation", "val-pair", "val-event")]
    (dataset / "train.json").write_text(
        json.dumps({"events": ["train-event"], "samples": train}), encoding="utf-8"
    )
    (dataset / "validation.json").write_text(
        json.dumps({"events": ["val-event"], "samples": validation}), encoding="utf-8"
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
    source_checkpoint = tmp_path / "source.pt"
    model = build_model("unet", in_channels=16, base=8)
    torch.save({"selection_split": "val", "state_dict": model.state_dict()}, source_checkpoint)
    final = tmp_path / "final.json"
    final.write_text(
        json.dumps(
            {
                "test_used_for_selection": False,
                "reports": [
                    {
                        "local_checkpoint": str(source_checkpoint),
                        "config": {
                            "seed": 11,
                            "model_name": "unet",
                            "base_channels": 8,
                            "target_mode": "hybrid",
                        },
                    },
                    {
                        "local_checkpoint": str(source_checkpoint),
                        "config": {
                            "seed": 29,
                            "model_name": "unet",
                            "base_channels": 8,
                            "target_mode": "hybrid",
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    report = adapt_frozen_rcda_on_wfigs(
        final_summary_path=final,
        wfigs_dataset_root=dataset,
        rcda_normalization_path=normalization,
        output_root=tmp_path / "adapted",
        adaptation=WFIGSAdaptConfig(
            epochs=1,
            batch_size=1,
            patience=0,
            tversky_alpha=0.7,
            tversky_beta=0.3,
            tversky_gamma=0.6,
            target_mode="growth",
            augment=False,
        ),
        progress_callback=progress.append,
    )
    assert report["counts"]["reports"] == 2
    assert report["wfigs_test_loaded"] is False
    assert report["reports"][0]["test_evaluated"] is False
    assert report["reports"][0]["threshold_selected_on"] == "wfigs_validation"
    adapted_checkpoint = torch.load(
        report["reports"][0]["checkpoint"], map_location="cpu", weights_only=False
    )
    assert adapted_checkpoint["target_mode"] == "growth"
    assert report["ensemble"]["aggregation"] == "mean_seed_probability"
    assert report["ensemble"]["members"] == 2
    assert report["ensemble"]["threshold_selected_on"] == "wfigs_validation"
    assert report["ensemble"]["test_evaluated"] is False
    assert len(progress) == 2
    assert {row["seed"] for row in progress} == {11, 29}
    assert all(row["epoch"] == 1 for row in progress)
    assert all(row["selection_split"] == "wfigs_validation" for row in progress)
    assert all(row["test_evaluated"] is False for row in progress)
    assert report["configuration"]["tversky_alpha"] == 0.7
    assert report["configuration"]["tversky_beta"] == 0.3
    assert report["configuration"]["tversky_gamma"] == 0.6
    assert report["configuration"]["target_mode"] == "growth"
    assert report["configuration"]["augment"] is False


def test_decoder_scope_freezes_encoder_parameters_and_statistics() -> None:
    model = build_model("resunet", in_channels=16, base=8)

    trainable = configure_trainable_scope(model, "decoder")
    set_adaptation_train_mode(model, "decoder")

    assert trainable
    assert all(not parameter.requires_grad for parameter in model.enc1.parameters())
    assert all(parameter.requires_grad for parameter in model.dec1.parameters())
    assert model.enc1.training is False
    assert model.dec1.training is True


def test_all_scope_keeps_every_parameter_trainable() -> None:
    model = build_model("resunet", in_channels=16, base=8)

    trainable = configure_trainable_scope(model, "all")

    assert sum(parameter.numel() for parameter in trainable) == sum(
        parameter.numel() for parameter in model.parameters()
    )
