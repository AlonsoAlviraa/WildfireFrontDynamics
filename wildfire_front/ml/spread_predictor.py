"""Production inference for NDWS wildfire spread models (v21+)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch

from wildfire_front.ml.unet_train import build_model, model_forward, prepare_input


@dataclass(frozen=True)
class SpreadModelManifest:
    """Frozen production contract for a trained spread model."""

    version: str
    architecture: str
    target_mode: str
    in_channels: int
    sequence_timesteps: int
    sequence_channels: int
    patch_size: int
    threshold: float
    filter_mode: str
    metrics: dict[str, float]
    weights_file: str
    repo_commit: str | None = None

    @classmethod
    def from_json(cls, path: Path | str) -> SpreadModelManifest:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            version=str(data["version"]),
            architecture=str(data["architecture"]),
            target_mode=str(data["target_mode"]),
            in_channels=int(data["in_channels"]),
            sequence_timesteps=int(data.get("sequence_timesteps", 1)),
            sequence_channels=int(data.get("sequence_channels", 17)),
            patch_size=int(data.get("patch_size", 64)),
            threshold=float(data.get("threshold", 0.5)),
            filter_mode=str(data.get("filter_mode", "any_fire")),
            metrics={k: float(v) for k, v in dict(data.get("metrics", {})).items()},
            weights_file=str(data["weights_file"]),
            repo_commit=data.get("repo_commit"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "architecture": self.architecture,
            "target_mode": self.target_mode,
            "in_channels": self.in_channels,
            "sequence_timesteps": self.sequence_timesteps,
            "sequence_channels": self.sequence_channels,
            "patch_size": self.patch_size,
            "threshold": self.threshold,
            "filter_mode": self.filter_mode,
            "metrics": self.metrics,
            "weights_file": self.weights_file,
            "repo_commit": self.repo_commit,
        }


class SpreadPredictor:
    """Load a v21-style checkpoint and predict next-day fire masks."""

    def __init__(
        self,
        manifest: SpreadModelManifest,
        weights_path: Path | str,
        *,
        device: torch.device | str | None = None,
    ) -> None:
        self.manifest = manifest
        self.weights_path = Path(weights_path)
        if not self.weights_path.is_file():
            raise FileNotFoundError(f"Weights not found: {self.weights_path}")

        if device is None:
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.device = torch.device(device)

        from wildfire_front.ml.unet_train import UNetTrainConfig

        config = UNetTrainConfig(
            architecture=manifest.architecture,
            target_mode=manifest.target_mode,
            version_tag=manifest.version,
        )
        self._config = config
        self.model = build_model(config, manifest.in_channels).to(self.device)
        state = torch.load(self.weights_path, map_location=self.device, weights_only=True)
        self.model.load_state_dict(state, strict=True)
        self.model.eval()

    @classmethod
    def from_manifest(
        cls,
        manifest_path: Path | str,
        *,
        weights_path: Path | str | None = None,
        device: torch.device | str | None = None,
    ) -> SpreadPredictor:
        manifest = SpreadModelManifest.from_json(manifest_path)
        root = Path(manifest_path).resolve().parent
        resolved = Path(weights_path) if weights_path else root / manifest.weights_file
        return cls(manifest, resolved, device=device)

    def _decode_probs(self, logits: torch.Tensor, current_fire: torch.Tensor) -> torch.Tensor:
        probs = torch.sigmoid(logits)
        if self.manifest.target_mode == "delta":
            prev_bin = (current_fire >= self.manifest.threshold).float().unsqueeze(1)
            probs = torch.clamp(prev_bin + probs, 0.0, 1.0)
        return probs

    @torch.no_grad()
    def predict(
        self,
        sequence: np.ndarray | torch.Tensor,
        current_fire: np.ndarray | torch.Tensor,
    ) -> np.ndarray:
        """Predict next-day fire probability map for one 64×64 patch."""
        seq_t = self._as_sequence_tensor(sequence)
        fire_t = self._as_fire_tensor(current_fire)
        x = prepare_input(seq_t, fire_t)
        logits = model_forward(self.model, x, fire_t, self.manifest.architecture)
        probs = self._decode_probs(logits, fire_t)
        return probs[0, 0].detach().cpu().numpy()

    @torch.no_grad()
    def predict_binary(
        self,
        sequence: np.ndarray | torch.Tensor,
        current_fire: np.ndarray | torch.Tensor,
        *,
        threshold: float | None = None,
    ) -> np.ndarray:
        thr = self.manifest.threshold if threshold is None else threshold
        return (self.predict(sequence, current_fire) >= thr).astype(np.float32)

    def _as_sequence_tensor(self, sequence: np.ndarray | torch.Tensor) -> torch.Tensor:
        if isinstance(sequence, torch.Tensor):
            seq = sequence.float()
        else:
            seq = torch.from_numpy(np.asarray(sequence, dtype=np.float32))
        if seq.dim() == 4:
            seq = seq.unsqueeze(0)
        if seq.dim() != 5:
            raise ValueError(f"sequence must be (T,C,H,W), got {tuple(seq.shape)}")
        return seq.to(self.device)

    def _as_fire_tensor(self, current_fire: np.ndarray | torch.Tensor) -> torch.Tensor:
        if isinstance(current_fire, torch.Tensor):
            fire = current_fire.float()
        else:
            fire = torch.from_numpy(np.asarray(current_fire, dtype=np.float32))
        if fire.dim() == 2:
            fire = fire.unsqueeze(0)
        return fire.to(self.device)