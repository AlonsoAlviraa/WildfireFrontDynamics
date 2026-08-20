"""Event-disjoint RCDA/U-Net training with VAL-only selection."""

from __future__ import annotations

import json
import math
import random
import sys
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import scipy
import torch
import torch.nn as nn
import torch.nn.functional as F
from scipy.ndimage import binary_dilation, distance_transform_edt, label
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler

PROTOCOL_SEED = "wfd_rcda_event_split_v1"
THRESHOLDS = tuple(round(value / 20.0, 2) for value in range(1, 20))
EARLY_STOP_THRESHOLDS = tuple(round(value / 10.0, 1) for value in range(1, 10))
DISTANCE_CAP_PX = 32.0
HORIZON_REF_HOURS = 24.0
SEALED_CHANNEL_NAMES = (
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
    "distance_to_front_near",
    "distance_to_front_global",
    "horizon_hours",
)


@dataclass
class SealedTrainConfig:
    dataset_root: str
    protocol_dir: str
    output_dir: str
    model_name: str = "unet"
    run_name: str | None = None
    seed: int = 0
    epochs: int = 20
    batch_size: int = 8
    lr: float = 1e-3
    weight_decay: float = 1e-4
    max_grad_norm: float = 5.0
    patience: int = 6
    num_workers: int = 2
    loss_name: str = "focal_tversky"
    tversky_alpha: float = 0.3
    tversky_beta: float = 0.7
    tversky_gamma: float = 0.75
    target_mode: str = "growth"
    extent_loss_weight: float = 0.35
    growth_loss_weight: float = 0.65
    front_ring_bce_weight: float = 0.0
    front_ring_radius_px: float = 16.0
    background_bce_weight: float = 0.0
    far_background_bce_weight: float = 0.0
    far_background_min_distance_px: float = 12.0
    base_channels: int = 32
    scheduler_name: str = "cosine"
    selection_metric: str = "event_macro_iou"
    evaluate_test: bool = True
    compute_paper_metrics: bool = True
    weighted_sampling: bool = True
    sampling_strategy: str = "size_event_power"
    event_balance_power: float = 0.5
    amp: bool = True
    smoke: bool = False
    max_train_samples: int | None = None
    max_eval_samples: int | None = None


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_protocol(protocol_dir: Path) -> dict[str, Any]:
    manifests = {
        split: load_json(protocol_dir / f"{split}.json") for split in ("train", "val", "test")
    }
    normalization = load_json(protocol_dir / "normalization_train_only.json")
    train_uids = set(manifests["train"]["events"])
    val_uids = set(manifests["val"]["events"])
    test_uids = set(manifests["test"]["events"])
    if train_uids & val_uids or train_uids & test_uids or val_uids & test_uids:
        raise ValueError("sealed protocol events are not disjoint")
    if str(normalization.get("fit_split")) != "train":
        raise ValueError("normalization was not fit on TRAIN")
    return {"manifests": manifests, "normalization": normalization}


def sample_date(name: str) -> datetime:
    return datetime.strptime(name.rsplit("_", 1)[-1].replace(".npy", ""), "%Y-%m-%d")


def sample_uid(name: str) -> str:
    return name.rsplit("_", 1)[0]


def growth_mask(inputs: np.ndarray, label: np.ndarray) -> np.ndarray:
    previous = np.asarray(inputs[0]) > 0.5
    next_extent = np.asarray(label) > 0.5
    return np.logical_and(next_extent, ~previous).astype(np.float32)


def encode_features(
    inputs: np.ndarray,
    *,
    channel_min: np.ndarray,
    channel_max: np.ndarray,
    horizon_hours: float = HORIZON_REF_HOURS,
) -> np.ndarray:
    """TRAIN-only min-max plus sin/cos wind, distance-to-front and horizon."""
    raw = np.asarray(inputs, dtype=np.float32)
    if raw.shape[0] != 12:
        raise ValueError(f"expected 12 RCDA channels, got {raw.shape[0]}")
    span = np.maximum(channel_max - channel_min, 1e-6).astype(np.float32)
    scaled = (raw - channel_min[:, None, None]) / span[:, None, None]
    previous = raw[0] > 0.5
    distance = distance_transform_edt(~previous).astype(np.float32)
    near_distance = np.clip(distance / DISTANCE_CAP_PX, 0.0, 1.0)
    diagonal = max(math.hypot(*raw.shape[1:]), 1.0)
    global_distance = np.clip(distance / diagonal, 0.0, 1.0)
    wind = raw[7]
    encoded = np.concatenate(
        [
            scaled[0:7],
            np.sin(wind)[None],
            np.cos(wind)[None],
            scaled[8:12],
            near_distance[None],
            global_distance[None],
            np.full((1, *raw.shape[1:]), horizon_hours / 48.0, dtype=np.float32),
        ],
        axis=0,
    )
    return encoded.astype(np.float32)


def focal_tversky_loss(
    logits: torch.Tensor,
    targets: torch.Tensor,
    *,
    alpha: float = 0.3,
    beta: float = 0.7,
    gamma: float = 0.75,
    eps: float = 1e-6,
) -> torch.Tensor:
    """Focal-Tversky on logits; beta>alpha emphasizes recall of sparse growth."""
    probs = torch.sigmoid(logits)
    dims = tuple(range(1, probs.ndim))
    true_pos = (probs * targets).sum(dim=dims)
    false_pos = (probs * (1.0 - targets)).sum(dim=dims)
    false_neg = ((1.0 - probs) * targets).sum(dim=dims)
    tversky = (true_pos + eps) / (true_pos + alpha * false_pos + beta * false_neg + eps)
    return torch.pow(1.0 - tversky, gamma).mean()


def front_ring_bce_loss(
    logits: torch.Tensor,
    inputs: torch.Tensor,
    growth_targets: torch.Tensor,
    *,
    radius_px: float,
    max_pos_weight: float = 20.0,
) -> torch.Tensor:
    """Balanced growth BCE only in the observable ring outside the t0 front."""

    if radius_px <= 0.0 or radius_px > DISTANCE_CAP_PX:
        raise ValueError(
            f"front-ring radius must be within (0, {DISTANCE_CAP_PX}] pixels"
        )
    if logits.shape != growth_targets.shape:
        raise ValueError("front-ring logits and growth targets must have equal shape")
    previous = inputs[:, 0:1] > 0.5
    normalized_distance = inputs[:, 13:14]
    ring = (~previous) & (normalized_distance < radius_px / DISTANCE_CAP_PX)
    ring_logits = logits[ring]
    ring_targets = growth_targets[ring]
    if ring_logits.numel() == 0:
        return logits.sum() * 0.0
    positives = ring_targets.sum()
    negatives = ring_targets.numel() - positives
    pos_weight = (negatives / positives.clamp_min(1.0)).clamp(
        min=1.0,
        max=max_pos_weight,
    )
    return F.binary_cross_entropy_with_logits(
        ring_logits,
        ring_targets,
        pos_weight=pos_weight,
    )


def _add_front_ring_objective(
    base_loss: torch.Tensor,
    growth_logits: torch.Tensor,
    inputs: torch.Tensor,
    growth_targets: torch.Tensor,
    config: SealedTrainConfig,
) -> torch.Tensor:
    if config.front_ring_bce_weight <= 0.0:
        return base_loss
    ring_loss = front_ring_bce_loss(
        growth_logits,
        inputs,
        growth_targets,
        radius_px=config.front_ring_radius_px,
    )
    return base_loss + config.front_ring_bce_weight * ring_loss


def background_bce_loss(
    logits: torch.Tensor,
    growth_targets: torch.Tensor,
) -> torch.Tensor:
    """BCE on observed non-growth pixels, separated from the overlap loss.

    Focal-Tversky is intentionally recall-oriented in the sealed recipe.  This
    auxiliary term is opt-in and lets a preregistered DEV experiment test
    whether the WFIGS domain shift is producing too many low-area false
    positives without changing the frozen default recipe.
    """

    if logits.shape != growth_targets.shape:
        raise ValueError("background BCE logits and targets must have equal shape")
    negative = growth_targets < 0.5
    if not bool(negative.any()):
        return logits.sum() * 0.0
    return F.binary_cross_entropy_with_logits(
        logits[negative],
        torch.zeros_like(logits[negative]),
    )


def _add_background_objective(
    base_loss: torch.Tensor,
    growth_logits: torch.Tensor,
    growth_targets: torch.Tensor,
    config: SealedTrainConfig,
) -> torch.Tensor:
    if config.background_bce_weight <= 0.0:
        return base_loss
    return base_loss + config.background_bce_weight * background_bce_loss(
        growth_logits,
        growth_targets,
    )


def far_background_bce_loss(
    logits: torch.Tensor,
    inputs: torch.Tensor,
    growth_targets: torch.Tensor,
    *,
    min_distance_px: float,
) -> torch.Tensor:
    """BCE on non-growth pixels outside a fixed t0-front distance band."""

    if min_distance_px <= 0.0 or min_distance_px > DISTANCE_CAP_PX:
        raise ValueError(
            f"far-background distance must be within (0, {DISTANCE_CAP_PX}] pixels"
        )
    if logits.shape != growth_targets.shape:
        raise ValueError("far-background BCE logits and targets must have equal shape")
    if inputs.ndim != 4 or inputs.shape[1] <= 13 or inputs.shape[0] != logits.shape[0]:
        raise ValueError("far-background BCE requires encoded distance channel 13")
    far_negative = (inputs[:, 13:14] >= min_distance_px / DISTANCE_CAP_PX) & (
        growth_targets < 0.5
    )
    if not bool(far_negative.any()):
        return logits.sum() * 0.0
    return F.binary_cross_entropy_with_logits(
        logits[far_negative],
        torch.zeros_like(logits[far_negative]),
    )


def _add_far_background_objective(
    base_loss: torch.Tensor,
    growth_logits: torch.Tensor,
    inputs: torch.Tensor,
    growth_targets: torch.Tensor,
    config: SealedTrainConfig,
) -> torch.Tensor:
    if config.far_background_bce_weight <= 0.0:
        return base_loss
    return base_loss + config.far_background_bce_weight * far_background_bce_loss(
        growth_logits,
        inputs,
        growth_targets,
        min_distance_px=config.far_background_min_distance_px,
    )


def confusion(prediction: np.ndarray, target: np.ndarray) -> np.ndarray:
    pred = prediction.astype(bool)
    truth = target.astype(bool)
    return np.array(
        [
            np.logical_and(pred, truth).sum(),
            np.logical_and(~pred, ~truth).sum(),
            np.logical_and(pred, ~truth).sum(),
            np.logical_and(~pred, truth).sum(),
        ],
        dtype=np.int64,
    )


def metrics_from_confusion(row: np.ndarray) -> dict[str, float | int]:
    tp, tn, fp, fn = (int(value) for value in row)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    iou = tp / (tp + fp + fn) if tp + fp + fn else 0.0
    return {
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "iou": iou,
    }


def objective_loss(
    logits: torch.Tensor,
    inputs: torch.Tensor,
    growth_targets: torch.Tensor,
    extent_targets: torch.Tensor,
    config: SealedTrainConfig,
) -> torch.Tensor:
    """Compute the registered objective without using validation or test labels."""

    if not math.isfinite(config.background_bce_weight) or config.background_bce_weight < 0.0:
        raise ValueError("background_bce_weight must be finite and non-negative")
    if not math.isfinite(config.far_background_bce_weight) or config.far_background_bce_weight < 0.0:
        raise ValueError("far_background_bce_weight must be finite and non-negative")

    if config.target_mode == "multitask":
        if logits.ndim != 4 or logits.shape[1] != 2:
            raise ValueError("multitask mode requires [N, 2, H, W] logits")
        growth_logits = logits[:, 0:1]
        extent_logits = logits[:, 1:2]
        growth_loss = focal_tversky_loss(
            growth_logits,
            growth_targets,
            alpha=config.tversky_alpha,
            beta=config.tversky_beta,
            gamma=config.tversky_gamma,
        )
        extent_loss = focal_tversky_loss(
            extent_logits,
            extent_targets,
            alpha=config.tversky_alpha,
            beta=config.tversky_beta,
            gamma=config.tversky_gamma,
        )
        base_loss = (
            config.extent_loss_weight * extent_loss
            + config.growth_loss_weight * growth_loss
        )
        base_loss = _add_background_objective(
            base_loss,
            growth_logits,
            growth_targets,
            config,
        )
        base_loss = _add_far_background_objective(
            base_loss,
            growth_logits,
            inputs,
            growth_targets,
            config,
        )
        return _add_front_ring_objective(
            base_loss,
            growth_logits,
            inputs,
            growth_targets,
            config,
        )
    if config.target_mode == "growth":
        base_loss = focal_tversky_loss(
            logits,
            growth_targets,
            alpha=config.tversky_alpha,
            beta=config.tversky_beta,
            gamma=config.tversky_gamma,
        )
        base_loss = _add_background_objective(
            base_loss,
            logits,
            growth_targets,
            config,
        )
        base_loss = _add_far_background_objective(
            base_loss,
            logits,
            inputs,
            growth_targets,
            config,
        )
        return _add_front_ring_objective(
            base_loss,
            logits,
            inputs,
            growth_targets,
            config,
        )
    extent_loss = focal_tversky_loss(
        logits,
        extent_targets,
        alpha=config.tversky_alpha,
        beta=config.tversky_beta,
        gamma=config.tversky_gamma,
    )
    if config.target_mode == "extent":
        return extent_loss
    if config.target_mode == "hybrid":
        previous = inputs[:, 0:1] > 0.5
        growth_logits = logits.masked_fill(previous, -20.0)
        growth_loss = focal_tversky_loss(
            growth_logits,
            growth_targets,
            alpha=config.tversky_alpha,
            beta=config.tversky_beta,
            gamma=config.tversky_gamma,
        )
        base_loss = (
            config.extent_loss_weight * extent_loss
            + config.growth_loss_weight * growth_loss
        )
        base_loss = _add_background_objective(
            base_loss,
            growth_logits,
            growth_targets,
            config,
        )
        base_loss = _add_far_background_objective(
            base_loss,
            growth_logits,
            inputs,
            growth_targets,
            config,
        )
        return _add_front_ring_objective(
            base_loss,
            growth_logits,
            inputs,
            growth_targets,
            config,
        )
    raise ValueError(f"unknown target_mode {config.target_mode!r}")


class SealedRCDADataset(Dataset):
    def __init__(
        self,
        dataset_root: Path,
        manifest: dict[str, Any],
        normalization: dict[str, Any],
        *,
        augment: bool = False,
        max_samples: int | None = None,
    ) -> None:
        self.dataset_root = Path(dataset_root)
        self.samples = list(manifest["samples"])
        if max_samples is not None:
            self.samples = self.samples[:max_samples]
        self.channel_min = np.asarray(normalization["channel_min"], dtype=np.float32)
        self.channel_max = np.asarray(normalization["channel_max"], dtype=np.float32)
        self.augment = augment
        self._event_counts = {
            uid: sum(1 for row in self.samples if row["uid"] == uid)
            for uid in {str(row["uid"]) for row in self.samples}
        }
        self._horizon_cache = self._infer_horizons()

    def _infer_horizons(self) -> dict[str, float]:
        by_uid: dict[str, list[tuple[datetime, str]]] = defaultdict(list)
        for row in self.samples:
            by_uid[row["uid"]].append((sample_date(row["name"]), row["name"]))
        horizons: dict[str, float] = {}
        for _uid, items in by_uid.items():
            ordered = sorted(items, key=lambda item: item[0])
            gaps = [
                max((later[0] - earlier[0]).total_seconds() / 3600.0, 1.0)
                for earlier, later in zip(ordered, ordered[1:], strict=False)
            ]
            typical = float(np.median(gaps)) if gaps else HORIZON_REF_HOURS
            for _date, name in ordered:
                horizons[name] = typical
        return horizons

    def __len__(self) -> int:
        return len(self.samples)

    def sample_weight(
        self,
        index: int,
        *,
        event_balance_power: float = 0.5,
        sampling_strategy: str = "size_event_power",
    ) -> float:
        row = self.samples[index]
        event_days = max(1, self._event_counts[str(row["uid"])])
        if sampling_strategy == "uniform_events":
            return 1.0 / event_days
        if sampling_strategy != "size_event_power":
            raise ValueError(f"unknown sampling_strategy {sampling_strategy!r}")
        label = np.load(self.dataset_root / row["label"], mmap_mode="r")
        inputs = np.load(self.dataset_root / row["input"], mmap_mode="r")
        support = int(growth_mask(inputs, label).sum())
        if support == 0:
            size_w = 4.0
        elif support < 100:
            size_w = 3.0
        elif support < 500:
            size_w = 1.5
        elif support < 2000:
            size_w = 1.0
        else:
            size_w = 2.0
        if not 0.0 <= event_balance_power <= 1.0:
            raise ValueError("event_balance_power must be within [0, 1]")
        return size_w / (event_days**event_balance_power)

    def __getitem__(self, index: int) -> dict[str, Any]:
        row = self.samples[index]
        inputs = np.load(self.dataset_root / row["input"], allow_pickle=False)
        label = np.load(self.dataset_root / row["label"], allow_pickle=False)
        target = growth_mask(inputs, label)
        extent_target = (np.asarray(label) > 0.5).astype(np.float32)
        horizon = self._horizon_cache.get(row["name"], HORIZON_REF_HOURS)
        features = encode_features(
            inputs,
            channel_min=self.channel_min,
            channel_max=self.channel_max,
            horizon_hours=horizon,
        )
        if self.augment:
            features, targets = _augment(features, np.stack([target, extent_target]))
            target, extent_target = targets[0], targets[1]
        return {
            "input": torch.from_numpy(np.ascontiguousarray(features)),
            "target": torch.from_numpy(target[None].copy()),
            "extent_target": torch.from_numpy(extent_target[None].copy()),
            "name": row["name"],
            "uid": row["uid"],
            "horizon_hours": horizon,
        }


def _augment(features: np.ndarray, target: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    horizontal_axis = target.ndim - 1
    vertical_axis = target.ndim - 2
    if random.random() < 0.5:
        features = np.flip(features, axis=2).copy()
        target = np.flip(target, axis=horizontal_axis).copy()
        features[7] = -features[7]
    if random.random() < 0.5:
        features = np.flip(features, axis=1).copy()
        target = np.flip(target, axis=vertical_axis).copy()
        # Wind is encoded as (east=sin(direction), north=cos(direction)).
        # A vertical image reflection reverses north/south, not east/west.
        features[8] = -features[8]
    k = random.choice([0, 1, 2, 3])
    if k:
        features = np.rot90(features, k=k, axes=(1, 2)).copy()
        target = np.rot90(target, k=k, axes=(vertical_axis, horizontal_axis)).copy()
        sin_c, cos_c = features[7].copy(), features[8].copy()
        angle = -k * (math.pi / 2)
        features[7] = sin_c * math.cos(angle) + cos_c * math.sin(angle)
        features[8] = cos_c * math.cos(angle) - sin_c * math.sin(angle)
    return features, target


class ConvBlock(nn.Module):
    def __init__(self, in_ch: int, out_ch: int) -> None:
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(in_ch, out_ch, 3, padding=1, bias=False),
            nn.GroupNorm(8, out_ch),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_ch, out_ch, 3, padding=1, bias=False),
            nn.GroupNorm(8, out_ch),
            nn.ReLU(inplace=True),
        )

    def forward(self, tensor: torch.Tensor) -> torch.Tensor:
        return self.block(tensor)


class ResidualBlock(nn.Module):
    def __init__(self, in_ch: int, out_ch: int) -> None:
        super().__init__()
        self.body = nn.Sequential(
            nn.Conv2d(in_ch, out_ch, 3, padding=1, bias=False),
            nn.GroupNorm(8, out_ch),
            nn.SiLU(inplace=True),
            nn.Conv2d(out_ch, out_ch, 3, padding=1, bias=False),
            nn.GroupNorm(8, out_ch),
        )
        self.skip = (
            nn.Identity()
            if in_ch == out_ch
            else nn.Conv2d(in_ch, out_ch, kernel_size=1, bias=False)
        )
        self.activation = nn.SiLU(inplace=True)

    def forward(self, tensor: torch.Tensor) -> torch.Tensor:
        return self.activation(self.body(tensor) + self.skip(tensor))


class ASPP(nn.Module):
    """Compact atrous context block for long-range spread patterns."""

    def __init__(self, channels: int) -> None:
        super().__init__()
        branch = max(channels // 4, 16)
        self.branches = nn.ModuleList(
            [
                nn.Sequential(
                    nn.Conv2d(
                        channels,
                        branch,
                        1 if dilation == 1 else 3,
                        padding=0 if dilation == 1 else dilation,
                        dilation=dilation,
                        bias=False,
                    ),
                    nn.GroupNorm(8, branch),
                    nn.SiLU(inplace=True),
                )
                for dilation in (1, 2, 4, 8)
            ]
        )
        self.project = nn.Sequential(
            nn.Conv2d(branch * 4, channels, 1, bias=False),
            nn.GroupNorm(8, channels),
            nn.SiLU(inplace=True),
        )

    def forward(self, tensor: torch.Tensor) -> torch.Tensor:
        return self.project(torch.cat([branch(tensor) for branch in self.branches], dim=1))


class DualAttention(nn.Module):
    def __init__(self, channels: int) -> None:
        super().__init__()
        hidden = max(channels // 8, 8)
        self.channel = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Conv2d(channels, hidden, 1),
            nn.ReLU(inplace=True),
            nn.Conv2d(hidden, channels, 1),
            nn.Sigmoid(),
        )
        self.spatial = nn.Sequential(
            nn.Conv2d(channels, 1, kernel_size=7, padding=3),
            nn.Sigmoid(),
        )

    def forward(self, skip: torch.Tensor, up: torch.Tensor) -> torch.Tensor:
        fused = skip + up
        return skip * self.channel(fused) * self.spatial(fused) + skip


class SealedUNet(nn.Module):
    def __init__(self, in_channels: int = 15, base: int = 32) -> None:
        super().__init__()
        self.enc1 = ConvBlock(in_channels, base)
        self.enc2 = ConvBlock(base, base * 2)
        self.enc3 = ConvBlock(base * 2, base * 4)
        self.enc4 = ConvBlock(base * 4, base * 8)
        self.pool = nn.MaxPool2d(2)
        self.up3 = nn.ConvTranspose2d(base * 8, base * 4, 2, stride=2)
        self.up2 = nn.ConvTranspose2d(base * 4, base * 2, 2, stride=2)
        self.up1 = nn.ConvTranspose2d(base * 2, base, 2, stride=2)
        self.dec3 = ConvBlock(base * 8, base * 4)
        self.dec2 = ConvBlock(base * 4, base * 2)
        self.dec1 = ConvBlock(base * 2, base)
        self.out = nn.Conv2d(base, 1, 1)

    def forward(self, tensor: torch.Tensor) -> torch.Tensor:
        e1 = self.enc1(tensor)
        e2 = self.enc2(self.pool(e1))
        e3 = self.enc3(self.pool(e2))
        e4 = self.enc4(self.pool(e3))
        d3 = self.dec3(torch.cat([self.up3(e4), e3], dim=1))
        d2 = self.dec2(torch.cat([self.up2(d3), e2], dim=1))
        d1 = self.dec1(torch.cat([self.up1(d2), e1], dim=1))
        return self.out(d1)


class SealedRCDA(nn.Module):
    def __init__(self, in_channels: int = 15, base: int = 32) -> None:
        super().__init__()
        self.enc1 = ConvBlock(in_channels, base)
        self.enc2 = ConvBlock(base, base * 2)
        self.enc3 = ConvBlock(base * 2, base * 4)
        self.enc4 = ConvBlock(base * 4, base * 8)
        self.pool = nn.MaxPool2d(2)
        self.up3 = nn.ConvTranspose2d(base * 8, base * 4, 2, stride=2)
        self.up2 = nn.ConvTranspose2d(base * 4, base * 2, 2, stride=2)
        self.up1 = nn.ConvTranspose2d(base * 2, base, 2, stride=2)
        self.attn3 = DualAttention(base * 4)
        self.attn2 = DualAttention(base * 2)
        self.attn1 = DualAttention(base)
        self.dec3 = ConvBlock(base * 8, base * 4)
        self.dec2 = ConvBlock(base * 4, base * 2)
        self.dec1 = ConvBlock(base * 2, base)
        self.out = nn.Conv2d(base, 1, 1)

    def forward(self, tensor: torch.Tensor) -> torch.Tensor:
        e1 = self.enc1(tensor)
        e2 = self.enc2(self.pool(e1))
        e3 = self.enc3(self.pool(e2))
        e4 = self.enc4(self.pool(e3))
        u3 = self.up3(e4)
        d3 = self.dec3(torch.cat([self.attn3(e3, u3), u3], dim=1))
        u2 = self.up2(d3)
        d2 = self.dec2(torch.cat([self.attn2(e2, u2), u2], dim=1))
        u1 = self.up1(d2)
        d1 = self.dec1(torch.cat([self.attn1(e1, u1), u1], dim=1))
        return self.out(d1)


class SealedASPPUNet(nn.Module):
    def __init__(self, in_channels: int = 16, base: int = 32) -> None:
        super().__init__()
        self.enc1 = ConvBlock(in_channels, base)
        self.enc2 = ConvBlock(base, base * 2)
        self.enc3 = ConvBlock(base * 2, base * 4)
        self.enc4 = ConvBlock(base * 4, base * 8)
        self.context = ASPP(base * 8)
        self.pool = nn.MaxPool2d(2)
        self.up3 = nn.ConvTranspose2d(base * 8, base * 4, 2, stride=2)
        self.up2 = nn.ConvTranspose2d(base * 4, base * 2, 2, stride=2)
        self.up1 = nn.ConvTranspose2d(base * 2, base, 2, stride=2)
        self.dec3 = ConvBlock(base * 8, base * 4)
        self.dec2 = ConvBlock(base * 4, base * 2)
        self.dec1 = ConvBlock(base * 2, base)
        self.out = nn.Conv2d(base, 1, 1)

    def forward(self, tensor: torch.Tensor) -> torch.Tensor:
        e1 = self.enc1(tensor)
        e2 = self.enc2(self.pool(e1))
        e3 = self.enc3(self.pool(e2))
        e4 = self.context(self.enc4(self.pool(e3)))
        d3 = self.dec3(torch.cat([self.up3(e4), e3], dim=1))
        d2 = self.dec2(torch.cat([self.up2(d3), e2], dim=1))
        d1 = self.dec1(torch.cat([self.up1(d2), e1], dim=1))
        return self.out(d1)


class SealedResidualUNet(nn.Module):
    def __init__(
        self,
        in_channels: int = 16,
        base: int = 32,
        *,
        out_channels: int = 1,
    ) -> None:
        super().__init__()
        if out_channels < 1:
            raise ValueError("out_channels must be positive")
        self.enc1 = ResidualBlock(in_channels, base)
        self.enc2 = ResidualBlock(base, base * 2)
        self.enc3 = ResidualBlock(base * 2, base * 4)
        self.enc4 = ResidualBlock(base * 4, base * 8)
        self.context = ASPP(base * 8)
        self.pool = nn.MaxPool2d(2)
        self.up3 = nn.ConvTranspose2d(base * 8, base * 4, 2, stride=2)
        self.up2 = nn.ConvTranspose2d(base * 4, base * 2, 2, stride=2)
        self.up1 = nn.ConvTranspose2d(base * 2, base, 2, stride=2)
        self.dec3 = ResidualBlock(base * 8, base * 4)
        self.dec2 = ResidualBlock(base * 4, base * 2)
        self.dec1 = ResidualBlock(base * 2, base)
        self.out = nn.Conv2d(base, out_channels, 1)

    def forward(self, tensor: torch.Tensor) -> torch.Tensor:
        e1 = self.enc1(tensor)
        e2 = self.enc2(self.pool(e1))
        e3 = self.enc3(self.pool(e2))
        e4 = self.context(self.enc4(self.pool(e3)))
        d3 = self.dec3(torch.cat([self.up3(e4), e3], dim=1))
        d2 = self.dec2(torch.cat([self.up2(d3), e2], dim=1))
        d1 = self.dec1(torch.cat([self.up1(d2), e1], dim=1))
        return self.out(d1)


class SealedFiLMUNet(nn.Module):
    """Context U-Net with explicit conditioning on scalar weather and horizon."""

    CONDITION_CHANNELS = (6, 7, 8, 9, 10, 11, 12, 15)
    PRIOR_CHANNELS = (6, 7, 8, 9, 10, 11, 12, 13, 14, 15)

    def __init__(self, in_channels: int = 16, base: int = 32) -> None:
        super().__init__()
        self.enc1 = ResidualBlock(in_channels, base)
        self.enc2 = ResidualBlock(base, base * 2)
        self.enc3 = ResidualBlock(base * 2, base * 4)
        self.enc4 = ResidualBlock(base * 4, base * 8)
        self.context = ASPP(base * 8)
        self.pool = nn.MaxPool2d(2)
        self.condition = nn.Sequential(
            nn.Linear(len(self.CONDITION_CHANNELS), base * 2),
            nn.SiLU(inplace=True),
            nn.Linear(base * 2, base * 16),
        )
        self.up3 = nn.ConvTranspose2d(base * 8, base * 4, 2, stride=2)
        self.up2 = nn.ConvTranspose2d(base * 4, base * 2, 2, stride=2)
        self.up1 = nn.ConvTranspose2d(base * 2, base, 2, stride=2)
        self.dec3 = ResidualBlock(base * 8, base * 4)
        self.dec2 = ResidualBlock(base * 4, base * 2)
        self.dec1 = ResidualBlock(base * 2, base)
        self.out = nn.Conv2d(base, 1, 1)
        # A shallow physical prior can learn a weather/horizon-dependent radial
        # growth law.  The deep path then only needs to learn spatial residuals.
        prior_hidden = max(base // 2, 8)
        self.prior = nn.Sequential(
            nn.Conv2d(len(self.PRIOR_CHANNELS), prior_hidden, 1),
            nn.SiLU(inplace=True),
            nn.Conv2d(prior_hidden, 1, 1),
        )

    def forward(self, tensor: torch.Tensor) -> torch.Tensor:
        scalars = tensor[:, self.CONDITION_CHANNELS].mean(dim=(-2, -1))
        e1 = self.enc1(tensor)
        e2 = self.enc2(self.pool(e1))
        e3 = self.enc3(self.pool(e2))
        e4 = self.context(self.enc4(self.pool(e3)))
        gamma, beta = self.condition(scalars).chunk(2, dim=1)
        gamma = 0.25 * torch.tanh(gamma)[:, :, None, None]
        beta = 0.25 * torch.tanh(beta)[:, :, None, None]
        e4 = e4 * (1.0 + gamma) + beta
        d3 = self.dec3(torch.cat([self.up3(e4), e3], dim=1))
        d2 = self.dec2(torch.cat([self.up2(d3), e2], dim=1))
        d1 = self.dec1(torch.cat([self.up1(d2), e1], dim=1))
        return self.out(d1) + self.prior(tensor[:, self.PRIOR_CHANNELS])


class ProbabilityAveragingEnsemble(nn.Module):
    """Average seed probabilities while preserving the evaluator's logit API."""

    def __init__(self, models: list[nn.Module]) -> None:
        super().__init__()
        if len(models) < 2:
            raise ValueError("probability ensemble requires at least two models")
        self.models = nn.ModuleList(models)

    def forward(self, tensor: torch.Tensor) -> torch.Tensor:
        probabilities = torch.stack(
            [torch.sigmoid(model(tensor)) for model in self.models],
            dim=0,
        ).mean(dim=0)
        return torch.logit(probabilities.clamp(1e-6, 1.0 - 1e-6))


class HeterogeneousGrowthProbabilityEnsemble(nn.Module):
    """Average growth heads from models with different output contracts."""

    def __init__(self, models: list[nn.Module], target_modes: list[str]) -> None:
        super().__init__()
        if len(models) < 2 or len(models) != len(target_modes):
            raise ValueError("heterogeneous ensemble requires aligned models and modes")
        self.models = nn.ModuleList(models)
        self.target_modes = tuple(target_modes)

    def forward(self, tensor: torch.Tensor) -> torch.Tensor:
        probabilities = torch.stack(
            [
                torch.sigmoid(prediction_logits(model(tensor), mode))
                for model, mode in zip(self.models, self.target_modes, strict=True)
            ],
            dim=0,
        ).mean(dim=0)
        return torch.logit(probabilities.clamp(1e-6, 1.0 - 1e-6))


def build_model(name: str, in_channels: int = 16, *, base: int = 32) -> nn.Module:
    if name == "unet":
        return SealedUNet(in_channels=in_channels, base=base)
    if name == "rcda":
        return SealedRCDA(in_channels=in_channels, base=base)
    if name == "aspp_unet":
        return SealedASPPUNet(in_channels=in_channels, base=base)
    if name == "resunet":
        return SealedResidualUNet(in_channels=in_channels, base=base)
    if name == "resunet_multitask":
        return SealedResidualUNet(
            in_channels=in_channels,
            base=base,
            out_channels=2,
        )
    if name == "film_unet":
        return SealedFiLMUNet(in_channels=in_channels, base=base)
    raise ValueError(f"unknown model {name}")


def prediction_logits(logits: torch.Tensor, prediction_mode: str) -> torch.Tensor:
    """Select the growth logit while keeping auxiliary heads train-only."""

    if logits.ndim != 4:
        raise ValueError("model output must have shape [N, C, H, W]")
    if prediction_mode == "multitask":
        if logits.shape[1] != 2:
            raise ValueError("multitask inference requires two output channels")
        return logits[:, 0:1]
    if logits.shape[1] != 1:
        raise ValueError(
            f"prediction mode {prediction_mode!r} requires one output channel"
        )
    return logits


def prepare_model_for_device(model: nn.Module, device: torch.device) -> nn.Module:
    """Use oneDNN-friendly NHWC storage on CPU without changing model semantics."""

    model = model.to(device)
    if device.type == "cpu":
        model = model.to(memory_format=torch.channels_last)
    return model


def prepare_inputs_for_device(inputs: torch.Tensor, device: torch.device) -> torch.Tensor:
    moved = inputs.to(device)
    if device.type == "cpu" and moved.ndim == 4:
        moved = moved.contiguous(memory_format=torch.channels_last)
    return moved


def postprocess_growth(
    prediction: np.ndarray,
    previous: np.ndarray,
    *,
    dilation_radius: int,
    require_t0_connection: bool,
) -> np.ndarray:
    """Apply the preregistrable spatial decoder to a binary growth mask."""

    if dilation_radius < 0:
        raise ValueError("dilation_radius must be non-negative")
    growth = np.asarray(prediction, dtype=bool) & ~np.asarray(previous, dtype=bool)
    previous_bool = np.asarray(previous, dtype=bool)
    structure = np.ones((3, 3), dtype=bool)
    if dilation_radius > 0:
        growth = binary_dilation(
            growth,
            structure=structure,
            iterations=int(dilation_radius),
        )
        growth &= ~previous_bool
    if require_t0_connection and previous_bool.any() and growth.any():
        components, _count = label(previous_bool | growth, structure=structure)
        touching = np.unique(components[previous_bool])
        touching = touching[touching != 0]
        growth = np.isin(components, touching) & ~previous_bool
    return growth


def restrict_growth_to_distance(
    prediction: np.ndarray,
    previous: np.ndarray,
    distance_to_front_px: np.ndarray,
    *,
    max_distance_px: float,
) -> np.ndarray:
    """Keep predicted growth inside a fixed distance from the observed front."""

    if not np.isfinite(max_distance_px) or max_distance_px <= 0.0:
        raise ValueError("max_distance_px must be finite and positive")
    prediction_array = np.asarray(prediction, dtype=bool)
    previous_array = np.asarray(previous, dtype=bool)
    distance_array = np.asarray(distance_to_front_px, dtype=np.float32)
    if prediction_array.shape != previous_array.shape or prediction_array.shape != distance_array.shape:
        raise ValueError("prediction, previous, and distance arrays must have equal shapes")
    growth = prediction_array & ~previous_array
    return growth & np.isfinite(distance_array) & (distance_array <= max_distance_px)


@torch.no_grad()
def evaluate_split_postprocessed(
    model: nn.Module,
    loader: DataLoader,
    device: torch.device,
    threshold: float,
    *,
    prediction_mode: str = "growth",
    dilation_radius: int,
    require_t0_connection: bool,
    max_distance_px: float | None = None,
) -> dict[str, Any]:
    """Evaluate a fixed VAL-selected spatial decoder without retuning it."""

    model.eval()
    total = np.zeros(4, dtype=np.int64)
    far = np.zeros(4, dtype=np.int64)
    event_rows: dict[str, np.ndarray] = defaultdict(lambda: np.zeros(4, dtype=np.int64))
    n_samples = 0
    for batch in loader:
        inputs = batch["input"]
        logits = model(prepare_inputs_for_device(inputs, device))
        probs = torch.sigmoid(prediction_logits(logits, prediction_mode)).cpu().numpy()
        targets = batch["target"].numpy()
        previous = inputs[:, 0:1].numpy() > 0.5
        distance = inputs[:, 13].numpy() * DISTANCE_CAP_PX
        thresholded = probs >= threshold
        if prediction_mode in {"extent", "hybrid", "multitask"}:
            thresholded = np.logical_and(thresholded, ~previous)
        n_samples += len(batch["uid"])
        for index, uid in enumerate(batch["uid"]):
            prediction = postprocess_growth(
                thresholded[index, 0],
                previous[index, 0],
                dilation_radius=dilation_radius,
                require_t0_connection=require_t0_connection,
            )
            if max_distance_px is not None:
                prediction = restrict_growth_to_distance(
                    prediction,
                    previous[index, 0],
                    distance[index],
                    max_distance_px=max_distance_px,
                )
            truth = targets[index, 0]
            row = confusion(prediction, truth)
            total += row
            event_rows[uid] += row
            far_mask = distance[index] > 10.5
            far += confusion(prediction[far_mask], truth[far_mask])
    per_event = {
        uid: metrics_from_confusion(row) for uid, row in sorted(event_rows.items())
    }
    event_ious = [float(row["iou"]) for row in per_event.values()]
    result = metrics_from_confusion(total)
    far_metrics = metrics_from_confusion(far)
    result.update(
        {
            "event_macro_iou": float(np.mean(event_ious)) if event_ious else 0.0,
            "n_events": len(event_ious),
            "n_samples": n_samples,
            "threshold": threshold,
            "dilation_radius_px": int(dilation_radius),
            "require_t0_connection": bool(require_t0_connection),
            "max_distance_px": max_distance_px,
            "far_gt_10_5px_recall": far_metrics["recall"],
            "far_gt_10_5px_iou": far_metrics["iou"],
            "per_event": per_event,
        }
    )
    return result


@torch.no_grad()
def evaluate_split(
    model: nn.Module,
    loader: DataLoader,
    device: torch.device,
    threshold: float,
    *,
    prediction_mode: str = "growth",
    paper_metrics: bool = False,
) -> dict[str, Any]:
    if paper_metrics:
        from wildfire_front.ml.ndws_metrics import (
            aggregate_ndws_evaluation,
            evaluate_sample,
        )

    model.eval()
    total = np.zeros(4, dtype=np.int64)
    far = np.zeros(4, dtype=np.int64)
    event_rows: dict[str, np.ndarray] = defaultdict(lambda: np.zeros(4, dtype=np.int64))
    n_samples = 0
    sample_metrics: list[dict[str, Any]] = []
    for batch in loader:
        inputs = batch["input"]
        logits = model(prepare_inputs_for_device(inputs, device))
        probs = torch.sigmoid(prediction_logits(logits, prediction_mode)).cpu().numpy()
        targets = batch["target"].numpy()
        extent_targets = batch["extent_target"].numpy()
        preds = probs >= threshold
        if prediction_mode in {"extent", "hybrid", "multitask"}:
            previous = inputs[:, 0:1].numpy() > 0.5
            preds = np.logical_and(preds, ~previous)
        distance = inputs[:, 13].numpy() * DISTANCE_CAP_PX
        n_samples += len(batch["uid"])
        for index, uid in enumerate(batch["uid"]):
            row = confusion(preds[index, 0], targets[index, 0])
            total += row
            event_rows[uid] += row
            far_mask = distance[index] > 10.5
            far += confusion(preds[index, 0][far_mask], targets[index, 0][far_mask])
            if paper_metrics:
                previous = inputs[index, 0].numpy() > 0.5
                growth_probability = probs[index, 0].copy()
                if prediction_mode in {"extent", "hybrid", "multitask"}:
                    growth_probability[previous] = 0.0
                predicted_next = np.where(previous, 1.0, growth_probability)
                sample_metrics.append(
                    evaluate_sample(
                        predicted_next,
                        previous,
                        extent_targets[index, 0],
                        threshold,
                    )
                )
    per_event = {uid: metrics_from_confusion(row) for uid, row in sorted(event_rows.items())}
    event_ious = [float(row["iou"]) for row in per_event.values()]
    result = metrics_from_confusion(total)
    far_metrics = metrics_from_confusion(far)
    result["event_macro_iou"] = float(np.mean(event_ious)) if event_ious else 0.0
    result["n_events"] = len(event_ious)
    result["n_samples"] = n_samples
    result["threshold"] = threshold
    result["far_gt_10_5px_recall"] = far_metrics["recall"]
    result["far_gt_10_5px_iou"] = far_metrics["iou"]
    result["per_event"] = per_event
    if paper_metrics:
        result["paper_metrics"] = aggregate_ndws_evaluation(sample_metrics)
    return result


@torch.no_grad()
def select_threshold_on_val(
    model: nn.Module,
    loader: DataLoader,
    device: torch.device,
    thresholds: tuple[float, ...] = THRESHOLDS,
    *,
    prediction_mode: str = "growth",
    selection_metric: str = "event_macro_iou",
) -> tuple[float, dict[str, Any]]:
    all_rows = evaluate_threshold_grid(
        model,
        loader,
        device,
        thresholds,
        prediction_mode=prediction_mode,
    )
    best_threshold = thresholds[0]
    best: dict[str, Any] | None = None
    for threshold in thresholds:
        row = all_rows[str(threshold)]
        if selection_metric not in row:
            raise ValueError(f"unknown validation selection metric {selection_metric!r}")
        if best is None or float(row[selection_metric]) > float(best[selection_metric]):
            best = row
            best_threshold = threshold
    assert best is not None
    return best_threshold, {
        "selection_metric": selection_metric,
        "selected": best,
        "all": all_rows,
    }


@torch.no_grad()
def evaluate_threshold_grid(
    model: nn.Module,
    loader: DataLoader,
    device: torch.device,
    thresholds: tuple[float, ...],
    *,
    prediction_mode: str = "growth",
) -> dict[str, dict[str, Any]]:
    """Evaluate every VAL threshold in one inference pass."""

    if not thresholds:
        raise ValueError("threshold grid cannot be empty")
    model.eval()
    thresholds_array = np.asarray(thresholds, dtype=np.float32)
    totals = {threshold: np.zeros(4, dtype=np.int64) for threshold in thresholds}
    fars = {threshold: np.zeros(4, dtype=np.int64) for threshold in thresholds}
    event_rows: dict[float, dict[str, np.ndarray]] = {
        threshold: defaultdict(lambda: np.zeros(4, dtype=np.int64)) for threshold in thresholds
    }
    n_samples = 0
    for batch in loader:
        inputs = batch["input"]
        logits = model(prepare_inputs_for_device(inputs, device))
        probs = torch.sigmoid(prediction_logits(logits, prediction_mode)).cpu().numpy()
        targets = batch["target"].numpy()
        previous = inputs[:, 0:1].numpy() > 0.5
        distance = inputs[:, 13].numpy() * DISTANCE_CAP_PX
        n_samples += len(batch["uid"])
        predictions = probs[:, None] >= thresholds_array[None, :, None, None, None]
        if prediction_mode in {"extent", "hybrid", "multitask"}:
            predictions = np.logical_and(predictions, ~previous[:, None])
        for index, uid in enumerate(batch["uid"]):
            pred = predictions[index, :, 0]
            truth = targets[index, 0].astype(bool)
            rows = _threshold_confusions(pred, truth)
            far_mask = distance[index] > 10.5
            far_rows = _threshold_confusions(pred[:, far_mask], truth[far_mask])
            for threshold_index, threshold in enumerate(thresholds):
                totals[threshold] += rows[threshold_index]
                event_rows[threshold][uid] += rows[threshold_index]
                fars[threshold] += far_rows[threshold_index]
    output: dict[str, dict[str, Any]] = {}
    for threshold in thresholds:
        per_event = {
            uid: metrics_from_confusion(row) for uid, row in sorted(event_rows[threshold].items())
        }
        row = metrics_from_confusion(totals[threshold])
        far_metrics = metrics_from_confusion(fars[threshold])
        row.update(
            {
                "event_macro_iou": float(
                    np.mean([float(item["iou"]) for item in per_event.values()])
                )
                if per_event
                else 0.0,
                "n_events": len(per_event),
                "n_samples": n_samples,
                "threshold": threshold,
                "far_gt_10_5px_recall": far_metrics["recall"],
                "far_gt_10_5px_iou": far_metrics["iou"],
                "per_event": per_event,
            }
        )
        output[str(threshold)] = row
    return output


def _threshold_confusions(predictions: np.ndarray, target: np.ndarray) -> np.ndarray:
    """Vectorized [threshold, TP/TN/FP/FN] confusion rows."""

    pred = np.asarray(predictions, dtype=bool)
    truth = np.asarray(target, dtype=bool)
    if pred.ndim < 2:
        raise ValueError("predictions need a leading threshold dimension")
    if pred.shape[1:] != truth.shape:
        raise ValueError("prediction/target shapes do not match")
    axes = tuple(range(1, pred.ndim))
    return np.stack(
        (
            np.logical_and(pred, truth).sum(axis=axes),
            np.logical_and(~pred, ~truth).sum(axis=axes),
            np.logical_and(pred, ~truth).sum(axis=axes),
            np.logical_and(~pred, truth).sum(axis=axes),
        ),
        axis=1,
    ).astype(np.int64, copy=False)


def make_loader(
    dataset: SealedRCDADataset,
    *,
    batch_size: int,
    shuffle: bool,
    weighted: bool,
    num_workers: int,
    event_balance_power: float = 0.5,
    sampling_strategy: str = "size_event_power",
) -> DataLoader:
    sampler = None
    if weighted:
        weights = [
            dataset.sample_weight(
                index,
                event_balance_power=event_balance_power,
                sampling_strategy=sampling_strategy,
            )
            for index in range(len(dataset))
        ]
        sampler = WeightedRandomSampler(weights, num_samples=len(weights), replacement=True)
        shuffle = False
    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        sampler=sampler,
        num_workers=num_workers,
        pin_memory=torch.cuda.is_available(),
    )


def train_sealed(config: SealedTrainConfig) -> dict[str, Any]:
    train_started = time.perf_counter()
    set_seed(config.seed)
    dataset_root = Path(config.dataset_root)
    protocol = load_protocol(Path(config.protocol_dir))
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    train_set = SealedRCDADataset(
        dataset_root,
        protocol["manifests"]["train"],
        protocol["normalization"],
        augment=not config.smoke,
        max_samples=config.max_train_samples,
    )
    val_set = SealedRCDADataset(
        dataset_root,
        protocol["manifests"]["val"],
        protocol["normalization"],
        augment=False,
        max_samples=config.max_eval_samples,
    )
    train_loader = make_loader(
        train_set,
        batch_size=config.batch_size,
        shuffle=True,
        weighted=config.weighted_sampling and not config.smoke,
        num_workers=config.num_workers if not config.smoke else 0,
        event_balance_power=config.event_balance_power,
        sampling_strategy=config.sampling_strategy,
    )
    val_loader = make_loader(
        val_set,
        batch_size=config.batch_size,
        shuffle=False,
        weighted=False,
        num_workers=config.num_workers if not config.smoke else 0,
    )
    test_loader = None
    if config.evaluate_test:
        test_set = SealedRCDADataset(
            dataset_root,
            protocol["manifests"]["test"],
            protocol["normalization"],
            augment=False,
            max_samples=config.max_eval_samples,
        )
        test_loader = make_loader(
            test_set,
            batch_size=config.batch_size,
            shuffle=False,
            weighted=False,
            num_workers=config.num_workers if not config.smoke else 0,
        )
    model = prepare_model_for_device(
        build_model(
            config.model_name,
            in_channels=len(SEALED_CHANNEL_NAMES),
            base=config.base_channels,
        ),
        device,
    )
    parameter_count = sum(parameter.numel() for parameter in model.parameters())
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=config.lr, weight_decay=config.weight_decay
    )
    if config.scheduler_name == "cosine":
        scheduler: torch.optim.lr_scheduler.LRScheduler | None = (
            torch.optim.lr_scheduler.CosineAnnealingLR(
                optimizer, T_max=max(config.epochs, 1), eta_min=config.lr * 0.02
            )
        )
    elif config.scheduler_name == "none":
        scheduler = None
    else:
        raise ValueError(f"unknown scheduler_name {config.scheduler_name!r}")
    scaler = torch.amp.GradScaler("cuda", enabled=config.amp and device.type == "cuda")
    best_val_score = -1.0
    best_epoch = -1
    patience = 0
    history: list[dict[str, Any]] = []
    run_name = config.run_name or f"{config.model_name}_{config.target_mode}"
    artifact_name = "".join(
        character if character.isalnum() or character in "-_" else "_" for character in run_name
    )
    checkpoint_path = output_dir / f"{artifact_name}_seed{config.seed}_best.pt"
    numeric_failure: dict[str, Any] | None = None
    for epoch in range(1, config.epochs + 1):
        epoch_started = time.perf_counter()
        model.train()
        running = 0.0
        for batch_index, batch in enumerate(train_loader):
            inputs = prepare_inputs_for_device(batch["input"], device)
            targets = batch["target"].to(device)
            extent_targets = batch["extent_target"].to(device)
            optimizer.zero_grad(set_to_none=True)
            with torch.amp.autocast("cuda", enabled=config.amp and device.type == "cuda"):
                logits = model(inputs)
                loss = objective_loss(
                    logits,
                    inputs,
                    targets,
                    extent_targets,
                    config,
                )
            if not bool(torch.isfinite(loss).item()):
                numeric_failure = {
                    "status": "truncated_after_nonfinite_optimization",
                    "failed_epoch": epoch,
                    "failed_batch": batch_index,
                    "observed_train_loss": str(float(loss.detach().cpu().item())),
                    "test_evaluated": False,
                }
                print(
                    f"[{config.model_name} seed={config.seed}] non-finite loss at "
                    f"epoch={epoch} batch={batch_index}; optimization stopped and "
                    "the last finite VAL-selected checkpoint will be retained",
                    flush=True,
                )
                break
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(
                model.parameters(),
                max_norm=config.max_grad_norm,
                # AMP overflows are expected during scale discovery. GradScaler
                # records them in unscale_(), skips optimizer.step(), and lowers
                # the scale. On CPU/no-AMP a non-finite gradient remains fatal.
                error_if_nonfinite=not scaler.is_enabled(),
            )
            scaler.step(optimizer)
            scaler.update()
            running += float(loss.item())
        if numeric_failure is not None:
            break
        if scheduler is not None:
            scheduler.step()
        epoch_val_grid = evaluate_threshold_grid(
            model,
            val_loader,
            device,
            EARLY_STOP_THRESHOLDS,
            prediction_mode=config.target_mode,
        )
        val_at_half = epoch_val_grid["0.5"]
        epoch_selected = max(
            epoch_val_grid.values(),
            key=lambda row: float(row[config.selection_metric]),
        )
        history.append(
            {
                "epoch": epoch,
                "train_loss": running / max(len(train_loader), 1),
                "val_f1@0.5": val_at_half["f1"],
                "val_iou@0.5": val_at_half["iou"],
                "val_event_macro_iou@0.5": val_at_half["event_macro_iou"],
                "val_selection_metric": config.selection_metric,
                "val_selection_score": epoch_selected[config.selection_metric],
                "val_selection_threshold": epoch_selected["threshold"],
                "lr": optimizer.param_groups[0]["lr"],
                "epoch_seconds": time.perf_counter() - epoch_started,
            }
        )
        print(
            f"[{config.model_name} seed={config.seed}] epoch {epoch} "
            f"loss={history[-1]['train_loss']:.4f} val_f1={val_at_half['f1']:.4f} "
            f"val_event_macro={epoch_selected[config.selection_metric]:.4f} "
            f"val_thr={epoch_selected['threshold']:.2f}",
            flush=True,
        )
        selection_value = float(epoch_selected[config.selection_metric])
        if selection_value >= best_val_score:
            best_val_score = selection_value
            best_epoch = epoch
            patience = 0
            torch.save(
                {
                    "model_name": config.model_name,
                    "run_name": run_name,
                    "target_mode": config.target_mode,
                    "base_channels": config.base_channels,
                    "state_dict": model.state_dict(),
                    "in_channels": len(SEALED_CHANNEL_NAMES),
                    "channel_names": list(SEALED_CHANNEL_NAMES),
                    "seed": config.seed,
                    "epoch": epoch,
                    "protocol_seed": PROTOCOL_SEED,
                    "normalization": protocol["normalization"],
                    "selection_split": "val",
                    "epoch_selection_threshold": epoch_selected["threshold"],
                    "epoch_selection_score": selection_value,
                },
                checkpoint_path,
            )
        else:
            patience += 1
            if patience > config.patience:
                break
    if not checkpoint_path.is_file():
        detail = numeric_failure or {"status": "no_checkpoint"}
        raise FloatingPointError(
            f"non-finite loss at epoch={detail.get('failed_epoch')} "
            f"batch={detail.get('failed_batch')}; no finite validation checkpoint exists"
        )
    payload = torch.load(checkpoint_path, map_location=device, weights_only=False)
    if not all(
        bool(torch.isfinite(value).all().item())
        for value in payload["state_dict"].values()
    ):
        raise FloatingPointError("refusing to load a non-finite validation checkpoint")
    model.load_state_dict(payload["state_dict"])
    threshold, val_search = select_threshold_on_val(
        model,
        val_loader,
        device,
        prediction_mode=config.target_mode,
        selection_metric=config.selection_metric,
    )
    if config.compute_paper_metrics:
        val_search["paper_metrics_at_selected_threshold"] = evaluate_split(
            model,
            val_loader,
            device,
            threshold,
            prediction_mode=config.target_mode,
            paper_metrics=True,
        )["paper_metrics"]
    report = {
        "schema": "wfd_rcda_sealed_train_v1",
        "config": asdict(config),
        "protocol_seed": PROTOCOL_SEED,
        "channel_names": list(SEALED_CHANNEL_NAMES),
        "best_epoch": best_epoch,
        "checkpoint": str(checkpoint_path),
        "threshold_selected_on": "val",
        "selected_threshold": threshold,
        "val": val_search,
        "history": history,
        "test_used_for_selection": False,
        "test_evaluated": config.evaluate_test,
        "normalization_fit_split": "train",
        "parameter_count": parameter_count,
        "device": str(device),
        "device_name": (torch.cuda.get_device_name(device) if device.type == "cuda" else "cpu"),
        "software_versions": {
            "python": sys.version.split()[0],
            "torch": torch.__version__,
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "cuda_runtime": torch.version.cuda,
            "cudnn": torch.backends.cudnn.version(),
        },
        "determinism": {
            "cudnn_deterministic": bool(torch.backends.cudnn.deterministic),
            "cudnn_benchmark": bool(torch.backends.cudnn.benchmark),
        },
        "torch_num_threads": torch.get_num_threads(),
        "cpu_channels_last": device.type == "cpu",
        "train_and_validation_seconds": time.perf_counter() - train_started,
    }
    if numeric_failure is not None:
        numeric_failure.update(
            {
                "checkpoint_finite": True,
                "checkpoint_epoch": int(payload["epoch"]),
                "checkpoint_selection_score": float(
                    payload["epoch_selection_score"]
                ),
                "checkpoint_selection_threshold": float(
                    payload["epoch_selection_threshold"]
                ),
            }
        )
        report["training_termination"] = numeric_failure
    if test_loader is not None:
        report["test_once"] = evaluate_split(
            model,
            test_loader,
            device,
            threshold,
            prediction_mode=config.target_mode,
            paper_metrics=config.compute_paper_metrics,
        )
    report["total_seconds"] = time.perf_counter() - train_started
    (output_dir / f"{artifact_name}_seed{config.seed}_report.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )
    return report
