"""Event-disjoint RCDA/U-Net training with VAL-only selection."""

from __future__ import annotations

import json
import math
import random
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn as nn
from scipy.ndimage import distance_transform_edt
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler

PROTOCOL_SEED = "wfd_rcda_event_split_v1"
THRESHOLDS = (0.2, 0.3, 0.4, 0.5, 0.6)
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
    "distance_to_front",
    "horizon_hours",
)


@dataclass
class SealedTrainConfig:
    dataset_root: str
    protocol_dir: str
    output_dir: str
    model_name: str = "unet"
    seed: int = 0
    epochs: int = 20
    batch_size: int = 8
    lr: float = 1e-3
    patience: int = 6
    num_workers: int = 2
    loss_name: str = "focal_tversky"
    tversky_alpha: float = 0.3
    tversky_beta: float = 0.7
    tversky_gamma: float = 0.75
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
        split: load_json(protocol_dir / f"{split}.json")
        for split in ("train", "val", "test")
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
    distance = np.clip(distance / DISTANCE_CAP_PX, 0.0, 1.0)
    wind = raw[7]
    encoded = np.concatenate(
        [
            scaled[0:7],
            np.sin(wind)[None],
            np.cos(wind)[None],
            scaled[8:12],
            distance[None],
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
    tversky = (true_pos + eps) / (
        true_pos + alpha * false_pos + beta * false_neg + eps
    )
    return torch.pow(1.0 - tversky, gamma).mean()


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
    f1 = (
        2 * precision * recall / (precision + recall) if precision + recall else 0.0
    )
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
            self.samples = self.samples[: max_samples]
        self.channel_min = np.asarray(normalization["channel_min"], dtype=np.float32)
        self.channel_max = np.asarray(normalization["channel_max"], dtype=np.float32)
        self.augment = augment
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

    def sample_weight(self, index: int) -> float:
        row = self.samples[index]
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
        event_days = max(1, sum(1 for item in self.samples if item["uid"] == row["uid"]))
        return size_w / math.sqrt(event_days)

    def __getitem__(self, index: int) -> dict[str, Any]:
        row = self.samples[index]
        inputs = np.load(self.dataset_root / row["input"], allow_pickle=False)
        label = np.load(self.dataset_root / row["label"], allow_pickle=False)
        target = growth_mask(inputs, label)
        horizon = self._horizon_cache.get(row["name"], HORIZON_REF_HOURS)
        features = encode_features(
            inputs,
            channel_min=self.channel_min,
            channel_max=self.channel_max,
            horizon_hours=horizon,
        )
        if self.augment:
            features, target = _augment(features, target)
        return {
            "input": torch.from_numpy(np.ascontiguousarray(features)),
            "target": torch.from_numpy(target[None].copy()),
            "name": row["name"],
            "uid": row["uid"],
            "horizon_hours": horizon,
        }


def _augment(features: np.ndarray, target: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if random.random() < 0.5:
        features = np.flip(features, axis=2).copy()
        target = np.flip(target, axis=1).copy()
        features[7] = -features[7]
    if random.random() < 0.5:
        features = np.flip(features, axis=1).copy()
        target = np.flip(target, axis=0).copy()
        features[7] = -features[7]
    k = random.choice([0, 1, 2, 3])
    if k:
        features = np.rot90(features, k=k, axes=(1, 2)).copy()
        target = np.rot90(target, k=k, axes=(0, 1)).copy()
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


def build_model(name: str, in_channels: int = 15) -> nn.Module:
    if name == "unet":
        return SealedUNet(in_channels=in_channels)
    if name == "rcda":
        return SealedRCDA(in_channels=in_channels)
    raise ValueError(f"unknown model {name}")


@torch.no_grad()
def evaluate_split(
    model: nn.Module,
    loader: DataLoader,
    device: torch.device,
    threshold: float,
) -> dict[str, Any]:
    model.eval()
    total = np.zeros(4, dtype=np.int64)
    far = np.zeros(4, dtype=np.int64)
    event_rows: dict[str, np.ndarray] = defaultdict(lambda: np.zeros(4, dtype=np.int64))
    for batch in loader:
        inputs = batch["input"]
        logits = model(inputs.to(device))
        probs = torch.sigmoid(logits).cpu().numpy()
        targets = batch["target"].numpy()
        preds = probs >= threshold
        distance = inputs[:, 13].numpy() * DISTANCE_CAP_PX
        for index, uid in enumerate(batch["uid"]):
            row = confusion(preds[index, 0], targets[index, 0])
            total += row
            event_rows[uid] += row
            far_mask = distance[index] > 10.5
            far += confusion(preds[index, 0][far_mask], targets[index, 0][far_mask])
    event_ious = [float(metrics_from_confusion(row)["iou"]) for row in event_rows.values()]
    result = metrics_from_confusion(total)
    far_metrics = metrics_from_confusion(far)
    result["event_macro_iou"] = float(np.mean(event_ious)) if event_ious else 0.0
    result["n_events"] = len(event_ious)
    result["n_samples"] = int(loader.dataset.__len__())
    result["threshold"] = threshold
    result["far_gt_10_5px_recall"] = far_metrics["recall"]
    result["far_gt_10_5px_iou"] = far_metrics["iou"]
    return result


@torch.no_grad()
def select_threshold_on_val(
    model: nn.Module,
    loader: DataLoader,
    device: torch.device,
    thresholds: tuple[float, ...] = THRESHOLDS,
) -> tuple[float, dict[str, Any]]:
    best_threshold = thresholds[0]
    best: dict[str, Any] | None = None
    all_rows: dict[str, Any] = {}
    for threshold in thresholds:
        row = evaluate_split(model, loader, device, threshold)
        all_rows[str(threshold)] = row
        if best is None or float(row["f1"]) > float(best["f1"]):
            best = row
            best_threshold = threshold
    assert best is not None
    return best_threshold, {"selected": best, "all": all_rows}


def make_loader(
    dataset: SealedRCDADataset,
    *,
    batch_size: int,
    shuffle: bool,
    weighted: bool,
    num_workers: int,
) -> DataLoader:
    sampler = None
    if weighted:
        weights = [dataset.sample_weight(index) for index in range(len(dataset))]
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
    test_set = SealedRCDADataset(
        dataset_root,
        protocol["manifests"]["test"],
        protocol["normalization"],
        augment=False,
        max_samples=config.max_eval_samples,
    )
    train_loader = make_loader(
        train_set,
        batch_size=config.batch_size,
        shuffle=True,
        weighted=not config.smoke,
        num_workers=config.num_workers if not config.smoke else 0,
    )
    val_loader = make_loader(
        val_set,
        batch_size=config.batch_size,
        shuffle=False,
        weighted=False,
        num_workers=config.num_workers if not config.smoke else 0,
    )
    test_loader = make_loader(
        test_set,
        batch_size=config.batch_size,
        shuffle=False,
        weighted=False,
        num_workers=config.num_workers if not config.smoke else 0,
    )
    model = build_model(config.model_name, in_channels=len(SEALED_CHANNEL_NAMES)).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=config.lr)
    scaler = torch.amp.GradScaler("cuda", enabled=config.amp and device.type == "cuda")
    best_val_f1 = -1.0
    best_epoch = -1
    patience = 0
    history: list[dict[str, Any]] = []
    checkpoint_path = output_dir / f"{config.model_name}_seed{config.seed}_best.pt"
    for epoch in range(1, config.epochs + 1):
        model.train()
        running = 0.0
        for batch in train_loader:
            inputs = batch["input"].to(device)
            targets = batch["target"].to(device)
            optimizer.zero_grad(set_to_none=True)
            with torch.amp.autocast("cuda", enabled=config.amp and device.type == "cuda"):
                logits = model(inputs)
                loss = focal_tversky_loss(
                    logits,
                    targets,
                    alpha=config.tversky_alpha,
                    beta=config.tversky_beta,
                    gamma=config.tversky_gamma,
                )
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            running += float(loss.item())
        val_at_half = evaluate_split(model, val_loader, device, 0.5)
        history.append(
            {
                "epoch": epoch,
                "train_loss": running / max(len(train_loader), 1),
                "val_f1@0.5": val_at_half["f1"],
                "val_iou@0.5": val_at_half["iou"],
            }
        )
        print(
            f"[{config.model_name} seed={config.seed}] epoch {epoch} "
            f"loss={history[-1]['train_loss']:.4f} val_f1={val_at_half['f1']:.4f}",
            flush=True,
        )
        if float(val_at_half["f1"]) >= best_val_f1:
            best_val_f1 = float(val_at_half["f1"])
            best_epoch = epoch
            patience = 0
            torch.save(
                {
                    "model_name": config.model_name,
                    "state_dict": model.state_dict(),
                    "in_channels": len(SEALED_CHANNEL_NAMES),
                    "channel_names": list(SEALED_CHANNEL_NAMES),
                    "seed": config.seed,
                    "epoch": epoch,
                    "protocol_seed": PROTOCOL_SEED,
                    "normalization": protocol["normalization"],
                    "selection_split": "val",
                },
                checkpoint_path,
            )
        else:
            patience += 1
            if patience > config.patience:
                break
    payload = torch.load(checkpoint_path, map_location=device, weights_only=False)
    model.load_state_dict(payload["state_dict"])
    threshold, val_search = select_threshold_on_val(model, val_loader, device)
    test_metrics = evaluate_split(model, test_loader, device, threshold)
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
        "test_once": test_metrics,
        "history": history,
        "test_used_for_selection": False,
        "normalization_fit_split": "train",
    }
    (output_dir / f"{config.model_name}_seed{config.seed}_report.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )
    return report
