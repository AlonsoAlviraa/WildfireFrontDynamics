from __future__ import annotations

import json
from pathlib import Path

import pytest
import torch
from torch import nn

from scripts.ensemble_wfigs_adaptation_sources import (
    GrowthHeadProbabilityEnsemble,
    validate_sources,
)


class _OneHead(nn.Module):
    def forward(self, tensor: torch.Tensor) -> torch.Tensor:
        return torch.zeros((tensor.shape[0], 1, *tensor.shape[-2:]))


class _TwoHead(nn.Module):
    def forward(self, tensor: torch.Tensor) -> torch.Tensor:
        one = torch.ones((tensor.shape[0], 1, *tensor.shape[-2:]))
        return torch.cat((one, -one), dim=1)


def _source(tmp_path: Path, name: str, *, test_evaluated: bool = False) -> Path:
    reports = []
    for seed in (11, 29, 47):
        checkpoint = tmp_path / f"{name}-{seed}.pt"
        checkpoint.write_bytes(b"checkpoint")
        reports.append(
            {
                "config": {"seed": seed},
                "checkpoint": str(checkpoint),
                "test_evaluated": False,
            }
        )
    path = tmp_path / f"{name}.json"
    path.write_text(
        json.dumps(
            {
                "schema": "wfd_rcda_wfigs_domain_adaptation_v1",
                "test_used_for_selection": False,
                "wfigs_test_loaded": False,
                "counts": {"train_events": 87, "validation_events": 27},
                "reports": reports,
                "ensemble": {
                    "threshold_selected_on": "wfigs_validation",
                    "test_used_for_selection": False,
                    "test_evaluated": test_evaluated,
                    "validation": {
                        "selected": {
                            "event_macro_iou": 0.2,
                            "per_event": {"fire-a": {"iou": 0.2}},
                        }
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def test_growth_ensemble_accepts_one_and_two_head_models() -> None:
    model = GrowthHeadProbabilityEnsemble(
        [_OneHead(), _TwoHead()],
        ["hybrid", "multitask"],
    )
    output = model(torch.zeros((2, 16, 4, 4)))

    expected = (torch.tensor(0.5) + torch.sigmoid(torch.tensor(1.0))) / 2
    assert output.shape == (2, 1, 4, 4)
    assert torch.allclose(torch.sigmoid(output), expected.expand_as(output))


def test_sources_require_same_val_cohort_and_no_test(tmp_path: Path) -> None:
    first = _source(tmp_path, "old")
    second = _source(tmp_path, "front")
    reports, provenance = validate_sources([first, second])
    assert len(reports) == 6
    assert len(provenance["sources"]) == 2

    contaminated = _source(tmp_path, "contaminated", test_evaluated=True)
    with pytest.raises(ValueError, match="VAL ensemble"):
        validate_sources([first, contaminated])
