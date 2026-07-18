"""Production inference for NDWS / CLM single and ensemble spread models."""

from __future__ import annotations

import json
from collections.abc import Sequence
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
    product_type: str = "single"
    ensemble_mode: str = "mean_prob"
    members: tuple[str, ...] = ()
    member_weights: tuple[float, ...] = ()
    member_temperatures: tuple[float, ...] = ()

    @classmethod
    def from_json(cls, path: Path | str) -> SpreadModelManifest:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        metrics_raw = dict(data.get("metrics", {}))
        metrics: dict[str, float] = {}
        for k, v in metrics_raw.items():
            try:
                metrics[k] = float(v)
            except (TypeError, ValueError):
                continue
        members = tuple(str(m) for m in (data.get("members") or []))
        mw_raw = data.get("member_weights") or []
        member_weights = tuple(float(x) for x in mw_raw) if mw_raw else ()
        mt_raw = data.get("member_temperatures") or data.get("temperatures") or []
        member_temperatures = tuple(float(x) for x in mt_raw) if mt_raw else ()
        product_type = str(data.get("product_type") or ("ensemble" if members else "single"))
        return cls(
            version=str(data.get("version") or data.get("id") or "unknown"),
            architecture=str(data.get("architecture", "residual")),
            target_mode=str(data.get("target_mode", "delta")),
            in_channels=int(data.get("in_channels", 18)),
            sequence_timesteps=int(data.get("sequence_timesteps", 1)),
            sequence_channels=int(data.get("sequence_channels", 17)),
            patch_size=int(data.get("patch_size", 64)),
            threshold=float(data.get("threshold", 0.5)),
            filter_mode=str(data.get("filter_mode", "any_fire")),
            metrics=metrics,
            weights_file=str(data.get("weights_file") or ""),
            repo_commit=data.get("repo_commit"),
            product_type=product_type,
            ensemble_mode=str(data.get("ensemble_mode") or "mean_prob"),
            members=members,
            member_weights=member_weights,
            member_temperatures=member_temperatures,
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
            "product_type": self.product_type,
            "ensemble_mode": self.ensemble_mode,
            "members": list(self.members),
            "member_weights": list(self.member_weights),
            "member_temperatures": list(self.member_temperatures),
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


class EnsembleSpreadPredictor:
    """Soft-vote ensemble of residual delta models (CLM v30).

    ``mean_prob`` (default): average **growth** sigmoid across members, then
    decode absolute fire as ``clamp(prev + mean_growth, 0, 1)``.
    """

    def __init__(
        self,
        manifest: SpreadModelManifest,
        member_weights: Sequence[Path | str],
        *,
        ensemble_mode: str = "mean_prob",
        mix_weights: Sequence[float] | None = None,
        device: torch.device | str | None = None,
    ) -> None:
        paths = [Path(p) for p in member_weights]
        if len(paths) < 2:
            raise ValueError("ensemble requires >= 2 member weight files")
        missing = [str(p) for p in paths if not p.is_file()]
        if missing:
            raise FileNotFoundError(f"missing ensemble members: {missing}")

        self.manifest = manifest
        self.member_paths = paths
        self.ensemble_mode = ensemble_mode or manifest.ensemble_mode or "mean_prob"
        # Prefer explicit mix, then manifest.member_weights, else equal
        raw_mix = (
            mix_weights
            if mix_weights is not None
            else (list(manifest.member_weights) if manifest.member_weights else None)
        )
        mix: list[float] | None
        if raw_mix is not None:
            if len(raw_mix) != len(paths):
                raise ValueError("mix_weights length must match members")
            s = float(sum(float(x) for x in raw_mix))
            if s <= 0:
                raise ValueError("mix_weights sum must be positive")
            mix = [float(x) / s for x in raw_mix]
        else:
            mix = None
        self.mix_weights: list[float] | None = mix
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
        self.models: list[torch.nn.Module] = []
        for wpath in paths:
            model = build_model(config, manifest.in_channels).to(self.device)
            state = torch.load(wpath, map_location=self.device, weights_only=True)
            model.load_state_dict(state, strict=True)
            model.eval()
            self.models.append(model)

    @classmethod
    def from_manifest(
        cls,
        manifest_path: Path | str,
        *,
        member_weights: Sequence[Path | str] | None = None,
        repo_root: Path | str | None = None,
        device: torch.device | str | None = None,
    ) -> EnsembleSpreadPredictor:
        manifest_path = Path(manifest_path)
        manifest = SpreadModelManifest.from_json(manifest_path)
        root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[2]
        if member_weights is not None:
            members = list(member_weights)
        else:
            members = []
            for rel in manifest.members:
                p = Path(rel)
                members.append(p if p.is_absolute() else (root / p).resolve())
        return cls(
            manifest,
            members,
            ensemble_mode=manifest.ensemble_mode,
            device=device,
        )

    @classmethod
    def from_product_spec(
        cls, spec: Any, *, device: torch.device | str | None = None
    ) -> EnsembleSpreadPredictor:
        """Build from ``ProductSpec`` (catalog)."""
        manifest = SpreadModelManifest.from_json(spec.manifest_path)
        return cls(
            manifest,
            list(spec.member_paths),
            ensemble_mode=getattr(spec, "ensemble_mode", None) or manifest.ensemble_mode,
            device=device,
        )

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

    @torch.no_grad()
    def predict(
        self,
        sequence: np.ndarray | torch.Tensor,
        current_fire: np.ndarray | torch.Tensor,
    ) -> np.ndarray:
        seq_t = self._as_sequence_tensor(sequence)
        fire_t = self._as_fire_tensor(current_fire)
        x = prepare_input(seq_t, fire_t)

        growth_list: list[torch.Tensor] = []
        abs_list: list[torch.Tensor] = []
        temps = list(self.manifest.member_temperatures) if self.manifest.member_temperatures else []
        if temps and len(temps) != len(self.models):
            temps = []
        for mi, model in enumerate(self.models):
            logits = model_forward(model, x, fire_t, self.manifest.architecture)
            t = float(temps[mi]) if temps else 1.0
            growth = torch.sigmoid(logits / t) if abs(t - 1.0) > 1e-9 else torch.sigmoid(logits)
            growth_list.append(growth)
            if self.manifest.target_mode == "delta":
                prev_bin = (fire_t >= self.manifest.threshold).float().unsqueeze(1)
                abs_list.append(torch.clamp(prev_bin + growth, 0.0, 1.0))
            else:
                abs_list.append(growth)

        def _mix(stacked: torch.Tensor) -> torch.Tensor:
            if self.mix_weights is None:
                return stacked.mean(dim=0)
            w = torch.tensor(self.mix_weights, device=stacked.device, dtype=stacked.dtype).view(
                -1, *([1] * (stacked.dim() - 1))
            )
            return (stacked * w).sum(dim=0)

        if self.ensemble_mode == "mean_abs":
            probs = _mix(torch.stack(abs_list, dim=0))
        else:
            mean_g = _mix(torch.stack(growth_list, dim=0))
            if self.manifest.target_mode == "delta":
                prev_bin = (fire_t >= self.manifest.threshold).float().unsqueeze(1)
                probs = torch.clamp(prev_bin + mean_g, 0.0, 1.0)
            else:
                probs = mean_g
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

    @property
    def n_members(self) -> int:
        return len(self.models)
