"""Consolidated U-Net training for NDWS wildfire spread prediction.

Replaces duplicated logic in run_unet_training_v14–v18 with a single module.
Supports absolute-mask training (v14) and changed-pixel-focused modes (v19+).
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.optim.lr_scheduler import CosineAnnealingLR, LinearLR, SequentialLR
from torch.utils.data import DataLoader, WeightedRandomSampler

from models.unet_model import (
    WildfireUNet,
    WildfireUNetSmall,
    count_parameters,
    make_loss_fn,
    weighted_bce_loss,
)
from wildfire_front.ml.dataset import NpzWildfireDataset
from wildfire_front.ml.ndws_metrics import aggregate_ndws_evaluation, evaluate_sample


@dataclass
class UNetTrainConfig:
    """Training configuration for NDWS U-Net experiments."""

    epochs: int = 50
    batch_size: int = 32
    lr: float = 1e-3
    loss: str = "composite"
    pos_weight: float = 5.0
    model: str = "small"
    architecture: str = "standard"
    se_attention: bool = False
    norm: str = "group"
    grad_accum: int = 1
    ema_decay: float = 0.0
    patience: int = 10
    deterministic: bool = False
    smoke_test: bool = False
    data_dir: str = "/tmp/ndws_npz"
    output_dir: str = "."
    version_tag: str = "v19"
    target_mode: str = "absolute"
    change_loss_weight: float = 5.0
    weighted_sampler: bool = False
    clm_data_dir: str | None = None
    early_stop_metric: str = "improvement_vs_copy_iou"
    eval_thresholds: tuple[float, ...] = (0.3, 0.4, 0.5, 0.6)
    primary_threshold: float = 0.5


def prepare_input(sequence: torch.Tensor, current_fire: torch.Tensor) -> torch.Tensor:
    """Flatten (B,T,C,H,W) sequence and append current_fire channel."""
    b, t, c, h, w = sequence.shape
    flat = sequence.reshape(b, t * c, h, w)
    fire = current_fire.unsqueeze(1)
    return torch.cat([flat, fire], dim=1)


def build_training_target(
    target_fire: torch.Tensor,
    current_fire: torch.Tensor,
    mode: str,
) -> torch.Tensor:
    """Build loss target from absolute mask or delta/growth formulation."""
    target = target_fire.unsqueeze(1).float()
    prev = current_fire.unsqueeze(1).float()

    if mode == "absolute":
        return target

    if mode == "delta":
        tgt_bin = (target >= 0.5).float()
        prev_bin = (prev >= 0.5).float()
        growth = torch.clamp(tgt_bin - prev_bin, 0.0, 1.0)
        return growth

    if mode == "changed_weighted":
        return target

    raise ValueError(f"Unknown target_mode: {mode}")


def change_pixel_weights(
    target_fire: torch.Tensor,
    current_fire: torch.Tensor,
    base_weight: float = 1.0,
    change_weight: float = 5.0,
) -> torch.Tensor:
    """Per-pixel loss weights: higher on pixels where fire mask changes."""
    tgt_bin = (target_fire.unsqueeze(1) >= 0.5).float()
    prev_bin = (current_fire.unsqueeze(1) >= 0.5).float()
    changed = (tgt_bin != prev_bin).float()
    return base_weight + change_weight * changed


def apply_weighted_loss(
    loss_fn: Callable[[torch.Tensor, torch.Tensor], torch.Tensor],
    logits: torch.Tensor,
    targets: torch.Tensor,
    weights: torch.Tensor,
) -> torch.Tensor:
    """Element-wise loss with spatial weights, reduced to scalar mean."""
    logits = torch.clamp(logits, -10.0, 10.0)
    pw = torch.tensor(5.0, device=logits.device, dtype=logits.dtype)
    bce = F.binary_cross_entropy_with_logits(logits, targets, reduction="none", pos_weight=pw)
    return (bce * weights).mean()


class EMA:
    """Exponential moving average of model weights."""

    def __init__(self, model: nn.Module, decay: float = 0.999) -> None:
        self.decay = decay
        self.shadow = {k: v.detach().clone() for k, v in model.state_dict().items()}

    @torch.no_grad()
    def update(self, model: nn.Module) -> None:
        for k, v in model.state_dict().items():
            if v.dtype.is_floating_point:
                self.shadow[k].mul_(self.decay).add_(v.detach(), alpha=1 - self.decay)
            else:
                self.shadow[k] = v.detach().clone()

    @torch.no_grad()
    def apply(self, model: nn.Module) -> None:
        model.load_state_dict(self.shadow)

    @torch.no_grad()
    def restore(self, model: nn.Module, backup: dict[str, torch.Tensor]) -> None:
        model.load_state_dict(backup)


def build_model(config: UNetTrainConfig, in_channels: int) -> nn.Module:
    """Instantiate U-Net variant from config."""
    if config.architecture == "residual":
        from models.unet_model import ResidualWildfireUNetSmall

        return ResidualWildfireUNetSmall(
            in_channels=in_channels,
            bilinear=True,
            norm=config.norm,
            se_attention=config.se_attention,
        )
    if config.model == "full":
        return WildfireUNet(
            in_channels=in_channels,
            out_channels=1,
            bilinear=True,
            norm=config.norm,
            se_attention=config.se_attention,
        )
    return WildfireUNetSmall(
        in_channels=in_channels,
        out_channels=1,
        bilinear=True,
        norm=config.norm,
        se_attention=config.se_attention,
    )


def model_forward(
    model: nn.Module,
    x: torch.Tensor,
    current_fire: torch.Tensor,
    architecture: str,
) -> torch.Tensor:
    if architecture == "residual":
        return model(x, current_fire)
    return model(x)


def select_device() -> tuple[torch.device, bool]:
    """Pick CUDA only if a probe kernel actually runs (P100 + PyTorch 2.10 fails)."""
    if not torch.cuda.is_available():
        print("No CUDA available — using CPU.")
        return torch.device("cpu"), False
    try:
        probe = torch.zeros(2, 2, device="cuda")
        probe = probe @ probe
        torch.cuda.synchronize()
        name = torch.cuda.get_device_name(0)
        cap = torch.cuda.get_device_capability(0)
        print(f"GPU OK: {name} (sm_{cap[0]}{cap[1]})")
        torch.backends.cudnn.benchmark = True
        return torch.device("cuda"), True
    except Exception as exc:
        name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "unknown"
        print(f"[WARN] CUDA probe failed on {name}: {exc}")
        print("[WARN] Falling back to CPU (use T4 GPU on Kaggle for training).")
        return torch.device("cpu"), False


def _sample_change_weight(npz_path: Path) -> float:
    with np.load(npz_path) as data:
        if "change_fraction" in data:
            return float(data["change_fraction"]) + 0.05
        cf = data["current_fire"]
        tf = data["target_fire"]
        cf_bin = (np.asarray(cf) >= 0.5).astype(np.float32)
        tf_bin = (np.asarray(tf) >= 0.5).astype(np.float32)
        return float(np.mean(cf_bin != tf_bin)) + 0.05


def merge_clm_patches(
    ndws_root: Path,
    clm_root: Path,
    *,
    splits: tuple[str, ...] = ("train", "val", "test"),
) -> dict[str, int]:
    """Copy CLM NPZ patches into NDWS split directories for mixed training."""
    import shutil

    clm_root = Path(clm_root)
    ndws_root = Path(ndws_root)
    merged: dict[str, int] = {}

    for split in splits:
        src = clm_root / split
        if not src.exists():
            continue
        dst = ndws_root / split
        dst.mkdir(parents=True, exist_ok=True)
        n = 0
        for npz in src.glob("*.npz"):
            target = dst / npz.name
            if not target.exists():
                shutil.copy2(npz, target)
                n += 1
        merged[split] = n
        if n:
            print(f"[clm] merged {n} patches into {dst}")

    return merged


def build_dataloaders(
    config: UNetTrainConfig,
) -> tuple[
    DataLoader,
    DataLoader,
    DataLoader,
    Path,
    NpzWildfireDataset,
    NpzWildfireDataset,
    NpzWildfireDataset,
]:
    """Create train/val/test loaders from preprocessed NPZ directory."""
    data_root = Path(config.data_dir)

    if config.smoke_test and not (data_root / "train").exists():
        for split_name, n in [("train", 20), ("val", 6), ("test", 6)]:
            d = data_root / split_name
            d.mkdir(parents=True, exist_ok=True)
            for i in range(n):
                seq = np.random.randn(1, 17, 64, 64).astype(np.float32) * 0.5
                cf = np.zeros((64, 64), dtype=np.float32)
                tf_ = np.zeros((64, 64), dtype=np.float32)
                cf[20:40, 20:40] = 1.0
                tf_[18:42, 18:42] = 1.0
                change_fraction = float(np.mean((cf >= 0.5) != (tf_ >= 0.5)))
                np.savez_compressed(
                    d / f"patch_{i:06d}.npz",
                    sequence=seq,
                    current_fire=cf,
                    target_fire=tf_,
                    change_fraction=change_fraction,
                )

    train_ds = NpzWildfireDataset(data_root / "train", augment=True)
    val_ds = NpzWildfireDataset(data_root / "val", augment=False)
    test_ds = NpzWildfireDataset(data_root / "test", augment=False)

    if len(train_ds) == 0 or len(val_ds) == 0 or len(test_ds) == 0:
        raise RuntimeError(
            f"Empty dataset split(s): train={len(train_ds)} val={len(val_ds)} test={len(test_ds)}"
        )

    num_workers = 0 if sys.platform == "win32" else min(4, os.cpu_count() or 2)

    def _loader(
        dataset: NpzWildfireDataset,
        *,
        shuffle: bool,
        sampler: WeightedRandomSampler | None = None,
    ) -> DataLoader:
        persistent = num_workers > 0
        if sampler is not None:
            return DataLoader(
                dataset,
                batch_size=config.batch_size,
                sampler=sampler,
                shuffle=False,
                num_workers=num_workers,
                pin_memory=True,
                persistent_workers=persistent,
            )
        return DataLoader(
            dataset,
            batch_size=config.batch_size,
            shuffle=shuffle,
            num_workers=num_workers,
            pin_memory=True,
            persistent_workers=persistent,
        )

    if config.weighted_sampler:
        weights = [_sample_change_weight(f) for f in train_ds.files]
        sampler = WeightedRandomSampler(weights, num_samples=len(weights), replacement=True)
        train_loader = _loader(train_ds, shuffle=False, sampler=sampler)
    else:
        train_loader = _loader(train_ds, shuffle=True)

    val_loader = _loader(val_ds, shuffle=False)
    test_loader = _loader(test_ds, shuffle=False)
    return train_loader, val_loader, test_loader, data_root, train_ds, val_ds, test_ds


@torch.no_grad()
def evaluate_loader(
    model: nn.Module,
    loader: DataLoader,
    device: torch.device,
    config: UNetTrainConfig,
    *,
    use_amp: bool,
) -> dict:
    """Evaluate model with NDWS copy-baseline and changed-pixel metrics."""
    model.eval()
    total_loss, steps = 0.0, 0
    per_threshold: dict[float, list] = {t: [] for t in config.eval_thresholds}

    for sequence, current_fire, target_fire in loader:
        sequence = sequence.to(device)
        current_fire = current_fire.to(device)
        target_fire = target_fire.to(device)
        x = prepare_input(sequence, current_fire)
        target = build_training_target(target_fire, current_fire, config.target_mode)

        with torch.amp.autocast("cuda", enabled=use_amp):
            logits = model_forward(model, x, current_fire, config.architecture)
        logits = logits.float()
        total_loss += weighted_bce_loss(logits, target, pos_weight=config.pos_weight).item()
        steps += 1

        probs = torch.sigmoid(logits)
        if config.target_mode == "delta":
            prev_bin = (current_fire >= 0.5).float().unsqueeze(1)
            probs = torch.clamp(prev_bin + probs, 0.0, 1.0)

        for i in range(probs.shape[0]):
            pred_np = probs[i, 0].cpu().numpy()
            prev_np = current_fire[i].cpu().numpy()
            tgt_np = target_fire[i].cpu().numpy()
            for t in config.eval_thresholds:
                per_threshold[t].append(evaluate_sample(pred_np, prev_np, tgt_np, threshold=t))

    model.train()
    results: dict = {"loss": total_loss / steps if steps else 0.0}

    for t in config.eval_thresholds:
        agg = aggregate_ndws_evaluation(per_threshold[t])
        results[f"thresh_{t}"] = agg
        results[f"copy_baseline_thresh_{t}"] = agg.get("copy_full", {})
        if t == config.primary_threshold:
            results["improvement_vs_copy_iou"] = agg.get("improvement_vs_copy_iou", 0.0)
            results["improvement_vs_copy_iou_changed"] = agg.get(
                "improvement_vs_copy_iou_changed", 0.0
            )
            results["legacy_improvement_vs_naive_copy_iou_changed"] = agg.get(
                "legacy_improvement_vs_naive_copy_iou_changed", 0.0
            )
            results["copy_baseline_iou"] = agg.get("copy_baseline_iou", 0.0)
            results["dilated_copy_baseline_iou"] = agg.get("dilated_copy_baseline_iou", 0.0)
            results["improvement_vs_dilated_copy_iou"] = agg.get(
                "improvement_vs_dilated_copy_iou", 0.0
            )
            results["model_iou"] = agg.get("model_iou", 0.0)
            results["model_iou_changed"] = agg.get("model_iou_changed", 0.0)
            results["model_iou_growth"] = agg.get("model_iou_growth", 0.0)

    return results


def _early_stop_score(val_results: dict, metric: str) -> float:
    primary = val_results.get("thresh_0.5", val_results)
    if metric == "val_loss":
        return -float(val_results.get("loss", 0.0))
    if metric in primary:
        return float(primary[metric])
    return float(val_results.get(metric, -1e9))


def run_training(config: UNetTrainConfig) -> dict:
    """Full training loop. Returns training_summary dict."""
    if config.deterministic:
        torch.manual_seed(42)
        np.random.seed(42)

    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    log_file = output_dir / "training_log.txt"
    history_file = output_dir / "training_history.json"
    best_weights = output_dir / "weights_pretrained_best.pt"

    def log(msg: str) -> None:
        print(msg)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(msg + "\n")

    data_root = Path(config.data_dir)
    if config.clm_data_dir:
        merge_clm_patches(data_root, Path(config.clm_data_dir))

    train_loader, val_loader, test_loader, _, train_ds, val_ds, test_ds = build_dataloaders(config)
    log(f"Dataset sizes -> train={len(train_ds)} val={len(val_ds)} test={len(test_ds)}")

    device, use_amp = select_device()
    if device.type == "cuda":
        log(f"GPU: {torch.cuda.get_device_name(0)}")
    else:
        log("Device: CPU (reduced epochs recommended on Kaggle P100)")

    sample_seq, sample_curr, _ = train_ds[0]
    in_channels = sample_seq.shape[0] * sample_seq.shape[1] + 1
    model = build_model(config, in_channels).to(device)
    n_params = count_parameters(model)
    log(f"Model: {model.__class__.__name__}, params={n_params:,}, target_mode={config.target_mode}")

    if config.loss == "composite":
        loss_fn = make_loss_fn(
            "composite",
            pos_weight=config.pos_weight,
            dice_weight=0.3,
            tversky_weight=0.3,
        )
    elif config.loss == "combined":
        loss_fn = make_loss_fn("combined", pos_weight=config.pos_weight, dice_weight=0.5)
    elif config.loss == "focal":
        loss_fn = make_loss_fn("focal", pos_weight=config.pos_weight, gamma=2.0)
    elif config.loss == "tversky":
        loss_fn = make_loss_fn("tversky")
    else:
        loss_fn = make_loss_fn("bce", pos_weight=config.pos_weight)

    optimizer = torch.optim.AdamW(model.parameters(), lr=config.lr, weight_decay=1e-4)
    warmup_epochs = min(3, max(1, config.epochs // 10))
    warmup = LinearLR(optimizer, start_factor=0.1, total_iters=warmup_epochs)
    cosine = CosineAnnealingLR(optimizer, T_max=max(1, config.epochs - warmup_epochs), eta_min=1e-6)
    scheduler = SequentialLR(optimizer, schedulers=[warmup, cosine], milestones=[warmup_epochs])

    ema = EMA(model, config.ema_decay) if config.ema_decay > 0 else None
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)

    best_score = -1e18
    best_epoch = -1
    no_improve = 0
    history: list[dict] = []

    log(f"\n--- U-Net {config.version_tag} started ---")
    start_time = time.time()

    for epoch in range(config.epochs):
        model.train()
        epoch_loss, steps = 0.0, 0
        optimizer.zero_grad()
        t0 = time.time()

        for batch_idx, (sequence, current_fire, target_fire) in enumerate(train_loader):
            sequence = sequence.to(device)
            current_fire = current_fire.to(device)
            target_fire = target_fire.to(device)
            x = prepare_input(sequence, current_fire)
            target = build_training_target(target_fire, current_fire, config.target_mode)

            with torch.amp.autocast("cuda", enabled=use_amp):
                logits = model_forward(model, x, current_fire, config.architecture)
            logits = logits.float()

            if config.target_mode == "changed_weighted":
                weights = change_pixel_weights(
                    target_fire, current_fire, change_weight=config.change_loss_weight
                )
                loss = apply_weighted_loss(loss_fn, logits, target, weights) / config.grad_accum
            else:
                loss = loss_fn(logits, target) / config.grad_accum

            scaler.scale(loss).backward()

            if (batch_idx + 1) % config.grad_accum == 0:
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad()
                if ema:
                    ema.update(model)

            epoch_loss += loss.item() * config.grad_accum
            steps += 1

        scheduler.step()
        train_loss = epoch_loss / steps if steps else 0.0

        if ema:
            backup = {k: v.detach().clone() for k, v in model.state_dict().items()}
            ema.apply(model)
        val_results = evaluate_loader(model, val_loader, device, config, use_amp=use_amp)
        if ema:
            ema.restore(model, backup)

        val_loss = val_results["loss"]
        primary = val_results.get(f"thresh_{config.primary_threshold}", {})
        val_iou = float(primary.get("model_iou", 0.0))
        val_recall = float(primary.get("model_full", {}).get("micro_recall", 0.0))
        delta_full = float(primary.get("improvement_vs_copy_iou", 0.0))
        delta_changed = float(primary.get("improvement_vs_copy_iou_changed", 0.0))
        legacy_delta = float(primary.get("legacy_improvement_vs_naive_copy_iou_changed", 0.0))
        copy_iou = float(primary.get("copy_baseline_iou", 0.0))
        score = _early_stop_score(val_results, config.early_stop_metric)

        log(
            f"Epoch {epoch + 1:02d}/{config.epochs}  train={train_loss:.5f}  val={val_loss:.5f}  "
            f"IoU@0.5={val_iou:.4f}  copy={copy_iou:.4f}  delta_full={delta_full:+.4f}  "
            f"delta_changed={delta_changed:+.4f}  legacy={legacy_delta:+.4f}  "
            f"lr={scheduler.get_last_lr()[0]:.2e}  ({time.time() - t0:.0f}s)"
        )

        history.append(
            {
                "epoch": epoch + 1,
                "train_loss": train_loss,
                "val_loss": val_loss,
                "val_iou_0.5": val_iou,
                "val_recall_0.5": val_recall,
                "improvement_vs_copy_iou": delta_full,
                "improvement_vs_copy_iou_changed": delta_changed,
                "legacy_improvement_vs_naive_copy_iou_changed": legacy_delta,
                "copy_baseline_iou": copy_iou,
            }
        )
        history_file.write_text(json.dumps(history, indent=2))

        if score > best_score:
            best_score = score
            best_epoch = epoch + 1
            no_improve = 0
            torch.save(model.state_dict(), best_weights)
            log(f"  -> new best ({config.early_stop_metric}={score:.4f}); checkpoint saved")
        else:
            no_improve += 1
            if no_improve >= config.patience:
                log(f"  -> early stopping at epoch {epoch + 1}")
                break

    total_time = time.time() - start_time
    log(f"\nTraining completed in {total_time:.0f}s")

    model.load_state_dict(torch.load(best_weights, map_location=device))
    test_results = evaluate_loader(model, test_loader, device, config, use_amp=use_amp)

    primary_test = test_results.get(f"thresh_{config.primary_threshold}", {})
    summary = {
        "version": config.version_tag,
        "architecture": model.__class__.__name__,
        "target_mode": config.target_mode,
        "best_epoch": best_epoch,
        "early_stop_metric": config.early_stop_metric,
        "train_samples": len(train_ds),
        "val_samples": len(val_ds),
        "test_samples": len(test_ds),
        "total_train_time_s": total_time,
        "config": asdict(config),
        "test_metrics": test_results,
        "test_iou": float(primary_test.get("model_iou", 0.0)),
        "copy_baseline_iou": float(primary_test.get("copy_baseline_iou", 0.0)),
        "improvement_vs_copy_iou": float(primary_test.get("improvement_vs_copy_iou", 0.0)),
        "improvement_vs_copy_iou_changed": float(
            primary_test.get("improvement_vs_copy_iou_changed", 0.0)
        ),
        "legacy_improvement_vs_naive_copy_iou_changed": float(
            primary_test.get("legacy_improvement_vs_naive_copy_iou_changed", 0.0)
        ),
        "dilated_copy_baseline_iou": float(
            primary_test.get("dilated_copy_baseline_iou", 0.0)
        ),
        "improvement_vs_dilated_copy_iou": float(
            primary_test.get("improvement_vs_dilated_copy_iou", 0.0)
        ),
        "model_iou_growth": float(primary_test.get("model_iou_growth", 0.0)),
    }

    summary_path = output_dir / "training_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, default=str))
    (output_dir / "evaluation_metrics.json").write_text(
        json.dumps(test_results, indent=2, default=str)
    )

    log(f"Copy baseline IoU: {summary['copy_baseline_iou']:.4f}")
    log(f"Model IoU: {summary['test_iou']:.4f}")
    log(
        f"Improvement vs dilated copy (changed): "
        f"{summary['improvement_vs_copy_iou_changed']:+.4f}  "
        f"(legacy naive: {summary['legacy_improvement_vs_naive_copy_iou_changed']:+.4f})"
    )
    return summary


def config_from_namespace(args) -> UNetTrainConfig:
    """Build UNetTrainConfig from argparse Namespace."""
    return UNetTrainConfig(
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        loss=args.loss,
        pos_weight=args.pos_weight,
        model=args.model,
        architecture=getattr(args, "architecture", "standard"),
        se_attention=getattr(args, "se_attention", False),
        norm=args.norm,
        grad_accum=args.grad_accum,
        ema_decay=args.ema_decay,
        patience=args.patience,
        deterministic=args.deterministic,
        smoke_test=args.smoke_test,
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        version_tag=args.version_tag,
        target_mode=getattr(args, "target_mode", "absolute"),
        change_loss_weight=getattr(args, "change_loss_weight", 5.0),
        weighted_sampler=getattr(args, "weighted_sampler", False),
        early_stop_metric=getattr(args, "early_stop_metric", "improvement_vs_copy_iou"),
        clm_data_dir=getattr(args, "clm_data_dir", None),
    )
