"""Protocol definitions for ML models used by the training loop.

These protocols break circular type dependencies between the external
``models`` package (PyTorch ``nn.Module`` implementations) and the
``wildfire_front.ml`` training utilities, letting mypy verify the
custom helper methods without importing the concrete model classes.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Protocol, runtime_checkable

import torch
from torch import nn

if TYPE_CHECKING:
    from torch.nn.modules.module import _IncompatibleKeys


@runtime_checkable
class LocalSpreadModel(Protocol):
    """Structural type for A3C-style per-cell models with local-spread helpers.

    Mirrors the relevant subset of ``nn.Module`` so concrete modules
    (e.g. ``A3C_PerCellModel_LSTM``) are structurally compatible.
    """

    def forward(
        self, sequence: torch.Tensor, current_fire: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor]:
        ...

    def get_burning_cells(self, current_fire: torch.Tensor) -> list[tuple[int, int]]:
        ...

    def predict_8_neighbors(
        self, features: torch.Tensor, i: int, j: int
    ) -> torch.Tensor:
        ...

    def get_8_neighbor_coords(
        self, i: int, j: int, height: int, width: int
    ) -> list[tuple[int, int] | None]:
        ...

    def parameters(self, recurse: bool = True) -> Iterator[nn.Parameter]:
        ...

    def train(self, mode: bool = True) -> nn.Module:
        ...

    def to(self, *args: object, **kwargs: object) -> nn.Module:
        ...

    def state_dict(self, *args: object, **kwargs: object) -> dict[str, torch.Tensor]:
        ...

    def load_state_dict(
        self, state_dict: dict[str, torch.Tensor], strict: bool = True
    ) -> _IncompatibleKeys:
        ...
