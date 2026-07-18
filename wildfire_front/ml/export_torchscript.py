"""TorchScript export for production spread models."""

from __future__ import annotations

import json
from pathlib import Path

import torch
import torch.nn as nn

from wildfire_front.ml.spread_predictor import SpreadPredictor
from wildfire_front.ml.unet_train import model_forward, prepare_input


class DeployableSpreadModel(nn.Module):
    """Trace-friendly wrapper: sequence + current_fire -> fire probabilities."""

    def __init__(
        self,
        model: nn.Module,
        *,
        architecture: str,
        target_mode: str,
        threshold: float,
    ) -> None:
        super().__init__()
        self.model = model
        self.architecture = architecture
        self.target_mode = target_mode
        self.threshold = threshold

    def forward(self, sequence: torch.Tensor, current_fire: torch.Tensor) -> torch.Tensor:
        if sequence.dim() == 4:
            sequence = sequence.unsqueeze(0)
        if current_fire.dim() == 2:
            current_fire = current_fire.unsqueeze(0)
        x = prepare_input(sequence, current_fire)
        logits = model_forward(self.model, x, current_fire, self.architecture)
        probs = torch.sigmoid(logits)
        if self.target_mode == "delta":
            prev_bin = (current_fire >= self.threshold).float().unsqueeze(1)
            probs = torch.clamp(prev_bin + probs, 0.0, 1.0)
        return probs


def export_torchscript(
    manifest_path: Path | str,
    output_path: Path | str,
    *,
    weights_path: Path | str | None = None,
    patch_size: int = 64,
) -> Path:
    """Export traced TorchScript model and sidecar metadata JSON."""
    manifest_path = Path(manifest_path)
    output_path = Path(output_path)
    predictor = SpreadPredictor.from_manifest(manifest_path, weights_path=weights_path)
    deployable = DeployableSpreadModel(
        predictor.model,
        architecture=predictor.manifest.architecture,
        target_mode=predictor.manifest.target_mode,
        threshold=predictor.manifest.threshold,
    ).eval()

    t = predictor.manifest.sequence_timesteps
    c = predictor.manifest.sequence_channels
    h = w = patch_size
    example_seq = torch.randn(1, t, c, h, w)
    example_fire = (torch.rand(1, h, w) > 0.6).float()

    with torch.no_grad():
        traced = torch.jit.trace(deployable, (example_seq, example_fire), strict=False)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    traced.save(str(output_path))

    meta = {
        "format": "torchscript",
        "inputs": ["sequence", "current_fire"],
        "sequence_shape": [1, t, c, h, w],
        "current_fire_shape": [1, h, w],
        "output_shape": [1, 1, h, w],
        "manifest": predictor.manifest.to_dict(),
    }
    meta_path = output_path.with_suffix(".json")
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return output_path
