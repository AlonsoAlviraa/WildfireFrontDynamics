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
from typing import cast

import torch

from .types import LocalSpreadModel


def _smart_init_fusion_layers(model: torch.nn.Module) -> list[str]:
    """Initialize new v2 fusion layers so they DON'T destroy pre-trained features.

    When loading v1 weights into a v2 model, three layer groups are new:
    - ``fusion_gate``: 1×1 conv + sigmoid. We init bias to a large negative
      value so ``sigmoid(bias) ≈ 0``, meaning the gate passes through the
      spatial features (from pre-trained encoder) and ignores the randomly-
      initialized temporal projection. As training proceeds, the gate opens.
    - ``refine``: 3×3 conv + GroupNorm + ReLU. We init the conv as identity
      (center kernel = 1, rest = 0) and GroupNorm to affine identity so the
      refinement stage starts as a no-op.
    - ``temporal_projection``: Linear(256→256) + ReLU + Unflatten. We init
      the last linear row to near-zero so the temporal context has minimal
      initial influence, letting the gate control the blend.

    Returns the list of layer names that were smart-initialized.
    """
    import torch.nn as nn

    initialized: list[str] = []

    for name, module in model.named_modules():
        # fusion_gate: Conv2d(512, 256, 1) → make output ≈ 0 (sigmoid→0→spatial passthrough)
        if name == "fusion_gate":
            for sub_name, param in module.named_parameters():
                if "weight" in sub_name:
                    nn.init.normal_(param, mean=0.0, std=0.01)
                elif "bias" in sub_name:
                    # Large negative bias → sigmoid ≈ 0 → gate passes spatial features
                    nn.init.constant_(param, -4.0)
            initialized.append(name)

        # refine: Conv2d(256, 256, 3, pad=1) → identity-like initialization
        elif name == "refine":
            for _sub_name, sub_module in module.named_modules():
                if isinstance(sub_module, nn.Conv2d):
                    # Identity initialization: center weight = 1, rest = 0
                    nn.init.zeros_(sub_module.weight)
                    with torch.no_grad():
                        center = sub_module.kernel_size[0] // 2
                        out_c, in_c = sub_module.out_channels, sub_module.in_channels
                        for c in range(min(out_c, in_c)):
                            sub_module.weight[c, c, center, center] = 1.0
                    if sub_module.bias is not None:
                        nn.init.zeros_(sub_module.bias)
                elif isinstance(sub_module, nn.GroupNorm):
                    # Identity GroupNorm: weight=1, bias=0
                    nn.init.ones_(sub_module.weight)
                    nn.init.zeros_(sub_module.bias)
            initialized.append(name)

        # temporal_projection: Linear(256→256) → scale down so temporal noise is small initially
        elif name == "temporal_projection":
            for _sub_name, sub_module in module.named_modules():
                if isinstance(sub_module, nn.Linear):
                    nn.init.xavier_uniform_(sub_module.weight, gain=0.1)
                    if sub_module.bias is not None:
                        nn.init.zeros_(sub_module.bias)
            initialized.append(name)

    return initialized


def load_pretrained_weights(
    model: LocalSpreadModel | torch.nn.Module, weights_path: Path
) -> dict[str, object]:
    """Load weights into ``model`` with backward-compatible key remapping.

    After loading, any newly-introduced v2 layers (fusion_gate, refine,
    temporal_projection) are **smart-initialized** so they don't destroy the
    pre-trained features. The fusion gate starts closed (spatial passthrough)
    and the refinement layer acts as identity.

    Returns a dict with ``"missing"``, ``"unexpected"``, ``"shape_mismatch"``,
    ``"skipped_legacy"``, and ``"smart_init"`` key lists.
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
    unexpected = list(result.unexpected_keys)

    # Smart-initialize new v2 layers so pre-trained features are preserved.
    # This runs BEFORE computing the warning lists so we can filter out keys
    # that are intentionally handled by smart-init (fusion_gate, refine,
    # temporal_projection).  Without this filter the caller sees spurious
    # "missing keys" / "shape mismatch" warnings for layers that are actually
    # being deliberately initialized.
    # model is always an nn.Module at runtime; cast satisfies mypy's union narrowing.
    smart_init = _smart_init_fusion_layers(cast(torch.nn.Module, model))
    smart_init_prefixes = tuple(name + "." for name in smart_init)

    def _is_smart_init_key(key: str) -> bool:
        return any(key.startswith(prefix) for prefix in smart_init_prefixes)

    missing = [
        k for k in result.missing_keys if k not in shape_mismatch and not _is_smart_init_key(k)
    ]
    shape_mismatch = [k for k in shape_mismatch if not _is_smart_init_key(k)]

    if smart_init:
        print(f"  Smart-initialized v2 fusion layers (identity/passthrough): {smart_init}")
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
        "smart_init": smart_init,
    }
