#!/usr/bin/env python3
"""U-Net training pipeline v13 — INDUSTRY STANDARD ARCHITECTURE.

This script replaces the A3C-LSTM per-cell approach with U-Net, the
industry-standard architecture for the Next Day Wildfire Spread benchmark.

Key differences from run_mega_training.py (v10-v12):
    - Model: WildfireUNet (not A3C_PerCellModel_LSTM)
    - Batch size: 32 (not 1)
    - Loss: Weighted BCE weight=5 (not focal BCE pos_weight=3-8)
    - Patch size: 64x64 (not 30x30)
    - Training: Full-patch supervision (not per-cell iteration)

Expected improvements:
    - IoU: 0.002 → 0.10-0.20
    - Recall: 0.002 → 0.15-0.30
    - Training speed: 10x faster (batch processing)

References:
    - Hu et al., "Next Day Wildfire Spread", NeurIPS 2023
    - docs/INDUSTRY_SOLUTIONS_ANALYSIS.md
    - docs/LOOP_ENGINEERING_PLAN.md
"""

import os
import sys
import subprocess
import json
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader

# --------------------------------------------------------------------------- #
# 1. Clone repository + install deps
# --------------------------------------------------------------------------- #
print("=" * 70)
print("WILDFIRE U-NET TRAINING v13 — INDUSTRY STANDARD")
print("=" * 70)

if not Path("WildfireFrontDynamics").exists():
    print("Cloning repository...")
    subprocess.run(
        ["git", "clone", "--depth", "1",
         "https://github.com/AlonsoAlviraa/WildfireFrontDynamics.git"],
        check=True,
    )

os.chdir("WildfireFrontDynamics")
sys.path.insert(0, os.getcwd())

# --------------------------------------------------------------------------- #
# 2. Preprocess NDWS with 64x64 patches (not 30x30)
# --------------------------------------------------------------------------- #
print("\n=== FASE 1: PREPROCESAMIENTO TFRECORDS (64x64 patches) ===")

# Set patch size to 64 via environment variable
os.environ["PATCH_SIZE"] = "64"

preprocess_script = "kaggle_job/preprocess_ndws.py"
for split in ["train", "val", "test"]:
    print(f"\n--- Preprocessing split: {split} ---")
    subprocess.run([sys.executable, preprocess_script, "--split", split], check=True)

# --------------------------------------------------------------------------- #
# 3. Imports & data loaders
# --------------------------------------------------------------------------- #
from wildfire_front.ml.dataset import NpzWildfireDataset
from wildfire_front.evaluation import compute_segmentation_metrics, aggregate_segmentation_metrics

train_dir = "/tmp/ndws_npz/train"
val_dir = "/tmp/ndws_npz/val"
test_dir = "/tmp/ndws_npz/test"

train_dataset = NpzWildfireDataset(train_dir, augment=True)
val_dataset = NpzWildfireDataset(val_dir, augment=False)
test_dataset = NpzWildfireDataset(test_dir, augment=False)

print(f"\nDataset sizes -> train={len(train_dataset)}  val={len(val_dataset)}  test={len(test_dataset)}")

# CRITICAL DIFFERENCE: batch_size=32 (not 1!)
# U-Net processes full patches, so we can batch them
BATCH_SIZE = int(os.environ.get("WF_BATCH_SIZE", "32"))
print(f"Batch size: {BATCH_SIZE} (U-Net enables full batch processing)")

train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True,
                          num_workers=8, pin_memory=True,
                          persistent_workers=True, prefetch_factor=4)
val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE, shuffle=False,
                        num_workers=4, pin_memory=True,
                        persistent_workers=True, prefetch_factor=4)
test_loader = DataLoader(test_dataset, batch_size=BATCH_SIZE, shuffle=False,
                         num_workers=4, pin_memory=True,
                         persistent_workers=True, prefetch_factor=4)

# --------------------------------------------------------------------------- #
# Device selection
# --------------------------------------------------------------------------- #
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
if torch.cuda.is_available():
    torch.backends.cudnn.benchmark = True
    print(f"GPU: {torch.cuda.get_device_name(0)}")
print(f"Device: {device}")

# --------------------------------------------------------------------------- #
# 4. Model — U-Net (not A3C-LSTM!)
# --------------------------------------------------------------------------- #
from models.unet_model import WildfireUNet, WildfireUNetSmall, weighted_bce_loss, combined_loss

# Determine input channels from data
sample_seq, sample_curr, sample_target = train_dataset[0]
# NDWS provides sequences of shape (3, C, H, W) — we flatten time*channels
in_channels = sample_seq.shape[1] * sample_seq.shape[0]  # time_steps * channels
print(f"Input channels: {in_channels} (time_steps={sample_seq.shape[0]}, channels={sample_seq.shape[1]})")

# Use the smaller U-Net for faster training (can switch to full if needed)
USE_SMALL_UNET = os.environ.get("WF_SMALL_UNET", "1") == "1"
if USE_SMALL_UNET:
    model = WildfireUNetSmall(in_channels=in_channels, out_channels=1, bilinear=True)
    print("Using WildfireUNetSmall (32-64-128-256-512 channels)")
else:
    model = WildfireUNet(in_channels=in_channels, out_channels=1, bilinear=True)
    print("Using WildfireUNet (64-128-256-512-1024 channels)")

model.to(device)

n_params = sum(p.numel() for p in model.parameters())
print(f"Model parameters: {n_params:,}")

# AMP
USE_AMP = device.type == "cuda"
scaler = torch.amp.GradScaler('cuda', enabled=USE_AMP)

# --------------------------------------------------------------------------- #
# 5. Training loop
# --------------------------------------------------------------------------- #
print("\n=== FASE 2: U-NET TRAINING ===")

EPOCHS = int(os.environ.get("WF_EPOCHS", "50"))
PEAK_LR = float(os.environ.get("WF_PEAK_LR", "1e-3"))  # Higher LR for U-Net
WARMUP_EPOCHS = 3
WEIGHT_DECAY = 1e-4
patience = 10

optimizer = torch.optim.AdamW(model.parameters(), lr=PEAK_LR, weight_decay=WEIGHT_DECAY)

from torch.optim.lr_scheduler import CosineAnnealingLR, LinearLR, SequentialLR

warmup_scheduler = LinearLR(optimizer, start_factor=0.1, total_iters=WARMUP_EPOCHS)
cosine_scheduler = CosineAnnealingLR(optimizer, T_max=EPOCHS - WARMUP_EPOCHS, eta_min=1e-6)
scheduler = SequentialLR(
    optimizer,
    schedulers=[warmup_scheduler, cosine_scheduler],
    milestones=[WARMUP_EPOCHS],
)

best_val_loss = float("inf")
best_epoch = -1
no_improve = 0
history = []

LOG_FILE = Path("../training_log.txt")
def log_msg(msg):
    print(msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

log_msg(f"\n--- U-Net v13 training started at {time.strftime('%Y-%m-%d %H:%M:%S')} ---")
log_msg(f"Config: EPOCHS={EPOCHS}, BATCH_SIZE={BATCH_SIZE}, LR={PEAK_LR}, WARMUP={WARMUP_EPOCHS}")
log_msg(f"Model: {'Small' if USE_SMALL_UNET else 'Full'} U-Net ({n_params:,} params)")


def prepare_input(sequence, current_fire):
    """Flatten temporal dimension into channels for U-Net.

    sequence: (B, T, C, H, W) → (B, T*C + 1, H, W)
    current_fire: (B, H, W) → appended as extra channel
    """
    B, T, C, H, W = sequence.shape
    # Flatten time: (B, T*C, H, W)
    flat = sequence.reshape(B, T * C, H, W)
    # Append current fire mask as extra channel: (B, T*C+1, H, W)
    fire_expanded = current_fire.unsqueeze(1)  # (B, 1, H, W)
    return torch.cat([flat, fire_expanded], dim=1)


@torch.no_grad()
def evaluate_model(model, loader, device):
    """Compute loss + segmentation metrics on val/test."""
    model.eval()
    total_loss = 0.0
    steps = 0
    all_metrics = []

    for sequence, current_fire, target_fire in loader:
        sequence = sequence.to(device)
        current_fire = current_fire.to(device)
        target_fire = target_fire.to(device)

        x = prepare_input(sequence, current_fire)
        target = target_fire.unsqueeze(1)  # (B, 1, H, W)

        with torch.amp.autocast('cuda', enabled=USE_AMP):
            logits = model(x)
        logits = logits.float()
        target = target.float()

        loss = weighted_bce_loss(logits, target, pos_weight=5.0)
        total_loss += loss.item()
        steps += 1

        # Segmentation metrics
        probs = torch.sigmoid(logits)
        for i in range(probs.shape[0]):
            pred_np = probs[i, 0].cpu().numpy()
            gt_np = target[i, 0].cpu().numpy()
            m = compute_segmentation_metrics(pred_np, gt_np, threshold=0.5)
            all_metrics.append(m)

    model.train()
    avg_loss = total_loss / steps if steps else 0.0
    seg = aggregate_segmentation_metrics(all_metrics) if all_metrics else {}
    return avg_loss, seg


# --- Training loop ---
for epoch in range(EPOCHS):
    model.train()
    epoch_loss = 0.0
    steps = 0
    t0 = time.time()

    for sequence, current_fire, target_fire in train_loader:
        sequence = sequence.to(device)
        current_fire = current_fire.to(device)
        target_fire = target_fire.to(device)

        x = prepare_input(sequence, current_fire)
        target = target_fire.unsqueeze(1).float()

        optimizer.zero_grad()

        with torch.amp.autocast('cuda', enabled=USE_AMP):
            logits = model(x)
        logits = logits.float()

        loss = combined_loss(logits, target, pos_weight=5.0, dice_weight=0.5)

        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        scaler.step(optimizer)
        scaler.update()

        epoch_loss += loss.item()
        steps += 1

    scheduler.step()
    train_loss = epoch_loss / steps if steps else 0.0
    val_loss, val_seg = evaluate_model(model, val_loader, device)

    lr_now = scheduler.get_last_lr()[0]
    elapsed = time.time() - t0

    val_iou = val_seg.get("micro_iou", 0.0)
    val_recall = val_seg.get("micro_recall", 0.0)

    log_msg(f"Epoch {epoch+1:02d}/{EPOCHS}  train={train_loss:.5f}  val={val_loss:.5f}  "
            f"IoU={val_iou:.4f}  Recall={val_recall:.4f}  lr={lr_now:.2e}  ({elapsed:.0f}s)")

    history.append({
        "epoch": epoch + 1,
        "train_loss": train_loss,
        "val_loss": val_loss,
        "val_iou": val_iou,
        "val_recall": val_recall,
    })

    # Model selection on VAL loss
    if val_loss < best_val_loss:
        best_val_loss = val_loss
        best_epoch = epoch + 1
        no_improve = 0
        torch.save(model.state_dict(), "../weights_pretrained_best.pt")
        log_msg(f"  -> new best val_loss; checkpoint saved")
    else:
        no_improve += 1
        if no_improve >= patience:
            log_msg(f"  -> early stopping at epoch {epoch+1}")
            break

    # Save training state
    Path("../training_history.json").write_text(json.dumps(history, indent=2))

# --------------------------------------------------------------------------- #
# 6. Final evaluation on TEST set
# --------------------------------------------------------------------------- #
print(f"\nLoading best checkpoint from epoch {best_epoch} (val_loss={best_val_loss:.5f})")
model.load_state_dict(torch.load("../weights_pretrained_best.pt", map_location=device))

print("\n=== FASE 3: TEST SET EVALUATION ===")
test_loss, test_seg = evaluate_model(model, test_loader, device)

print(f"  Neural model TEST loss: {test_loss:.5f}")
print(f"  Segmentation metrics (TEST):")
print(f"    IoU (micro):       {test_seg.get('micro_iou', 0.0):.4f}")
print(f"    Dice/F1 (micro):   {test_seg.get('micro_dice', 0.0):.4f}")
print(f"    Precision (micro): {test_seg.get('micro_precision', 0.0):.4f}")
print(f"    Recall (micro):    {test_seg.get('micro_recall', 0.0):.4f}")

Path("../evaluation_metrics.json").write_text(json.dumps(test_seg, indent=2, default=str))

summary = {
    "version": "v13",
    "architecture": "WildfireUNetSmall" if USE_SMALL_UNET else "WildfireUNet",
    "best_pretrain_epoch": best_epoch,
    "best_val_loss": best_val_loss,
    "test_loss": test_loss,
    "train_samples": len(train_dataset),
    "val_samples": len(val_dataset),
    "test_samples": len(test_dataset),
    "v13_config": {
        "model": "U-Net",
        "batch_size": BATCH_SIZE,
        "peak_lr": PEAK_LR,
        "warmup_epochs": WARMUP_EPOCHS,
        "patience": patience,
        "loss": "Weighted BCE (w=5) + Dice (w=0.5)",
        "patch_size": 64,
        "n_params": n_params,
    },
    "seg_metrics": test_seg,
    "comparison": {
        "v12_iou": 0.002,
        "v13_iou": test_seg.get("micro_iou", 0.0),
        "improvement_factor": test_seg.get("micro_iou", 0.0) / 0.002 if test_seg.get("micro_iou", 0) > 0 else 0,
    }
}
Path("../training_summary.json").write_text(json.dumps(summary, indent=2, default=str))
print("\nSummary written to ../training_summary.json")
print(json.dumps(summary, indent=2, default=str))

print("\n=== U-NET v13 TRAINING COMPLETED ===")