"""Backward-compatible weight loading for the A3C-LSTM model.

The v2 architecture renamed/restructured the fusion layers:

    v1 (legacy checkpoints)  ->  v2 (current ``A3C_PerCellModel_LSTM``)
    ------------------------------------------------------------
    ``upsample.0.*``         ->  ``temporal_projection.0.*``
                               + new ``fusion_gate.*`` and ``refine.*`` layers

This helper remaps legacy keys and falls back to non-strict loading so that
pre-trained convolutional / LSTM / policy / value weights are preserved while
the newly introduced fusion/refinement layers are initialized from scratch.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import torch

from .types import LocalSpreadModel


def load_pretrained_weights(
    model: LocalSpreadModel | torch.nn.Module, weights_path: Path
) -> dict[str, object]:
    """Load weights into ``model`` with backward-compatible key remapping.

    Returns a dict with ``"missing"``, ``"unexpected"``, and ``"shape_mismatch"``
    key lists so callers can log or assert on the compatibility outcome.
    """

    checkpoint = torch.load(weights_path, map_location="cpu", weights_only=False)
    state_dict = checkpoint.get("model_state_dict", checkpoint)

    model_state = model.state_dict()

    # Remap legacy v1 keys and drop shape-incompatible tensors.
    remapped: dict[str, torch.Tensor] = {}
    shape_mismatch: list[str] = []
    skipped_legacy: list[str] = []

    for key, value in state_dict.items():
        new_key = key
        if key.startswith("upsample."):
            new_key = "temporal_projection." + key[len("upsample.") :]

        if new_key in model_state:
            if model_state[new_key].shape != value.shape:
                # Shape changed between v1 and v2 — skip and let it initialize.
                shape_mismatch.append(new_key)
                continue
            remapped[new_key] = value
        else:
            skipped_legacy.append(key)

    result = model.load_state_dict(remapped, strict=False)
    missing = [k for k in result.missing_keys if k not in shape_mismatch]
    unexpected = list(result.unexpected_keys)

    if missing:
        warnings.warn(
            f"Pre-trained weights missing keys (initialized randomly): {missing}",
            stacklevel=2,
        )
    if shape_mismatch:
        warnings.warn(
            f"Pre-trained weights had shape-mismatched keys (reinitialized): {shape_mismatch}",
            stacklevel=2,
        )
    if skipped_legacy:
        warnings.warn(
            f"Pre-trained weights contained unmapped legacy keys (ignored): {skipped_legacy}",
            stacklevel=2,
        )

    return {
        "missing": missing,
        "unexpected": unexpected,
        "shape_mismatch": shape_mismatch,
        "skipped_legacy": skipped_legacy,
    }
