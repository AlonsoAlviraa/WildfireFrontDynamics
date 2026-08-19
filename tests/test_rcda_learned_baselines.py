from __future__ import annotations

import torch
from torch.utils.data import Dataset

from scripts.evaluate_rcda_learned_baselines import LegacyFeatureView


class _OneRow(Dataset):
    def __len__(self) -> int:
        return 1

    def __getitem__(self, index: int):
        assert index == 0
        return {
            "input": torch.arange(16, dtype=torch.float32)[:, None, None],
            "target": torch.zeros(1, 1, 1),
            "uid": "fire",
        }


def test_legacy_feature_view_maps_near_distance_and_skips_global_distance():
    names = [
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
        "distance_to_front",
        "horizon_hours",
    ]

    row = LegacyFeatureView(_OneRow(), names)[0]

    assert row["input"].shape == (15, 1, 1)
    assert row["input"][:, 0, 0].tolist() == [*map(float, range(14)), 15.0]
