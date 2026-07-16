#!/usr/bin/env python3
"""U-Net training pipeline v13 — INDUSTRY STANDARD ARCHITECTURE.

Self-contained: U-Net model inlined to avoid import issues.

Key differences from run_mega_training.py (v10-v12):
    - Model: WildfireUNet (not A3C_PerCellModel_LSTM)
    - Batch size: 32 (not 1)
    - Loss: Weighted BCE weight=5 + Dice
    - Full-patch supervision (not per-cell iteration)
"""

import os
import sys
import subprocess
import json
import time
from pathlib import Path

import numpy as np

# --------------------------------------------------------------------------- #
# 0. FIX P100 sm_60 compatibility — MUST happen before `import torch`
# --------------------------------------------------------------------------- #
print("=" * 70)
print("WILDFIRE U-NET TRAINING v13 — INDUSTRY STANDARD")
print("=" * 70)

# Kaggle's P100 GPU (sm_60) needs PyTorch <= 2.1.x.
# Current Kaggle PyTorch (2.3+) only supports sm_70+ → CUDA kernel errors.
# We detect P100 via nvidia-smi BEFORE importing torch, install compatible
# version, then import. This avoids "no kernel image" runtime crashes.
def _check_gpu_compat():
    """Check if GPU needs older PyTorch. Returns True if P100 (sm_60) detected."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,compute_cap", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and "P100" in result.stdout:
            print(f"  P100 GPU detected: {result.stdout.strip()}")
            return True
    except Exception:
        pass
    return False

if _check_gpu_compat():
    print("  Installing PyTorch 2.1.2 (supports P100 sm_60)...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q",
                    "torch==2.1.2", "torchvision==0.16.2"],
                   check=True, capture_output=True)
    print("  PyTorch 2.1.2 installed successfully.")

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader

print(f"PyTorch version: {torch.__version__}")

# --------------------------------------------------------------------------- #
# 1. Clone repository
# --------------------------------------------------------------------------- #
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
# 2. Preprocess NDWS
# --------------------------------------------------------------------------- #
print("\n=== FASE 1: PREPROCESAMIENTO TFRECORDS ===")

preprocess_script = "kaggle_job/preprocess_ndws.py"
for split in ["train", "val", "test"]:
    print(f"\n--- Preprocessing split: {split} ---")
    subprocess.run([sys.executable, preprocess_script, "--split", split], check=True)

# --------------------------------------------------------------------------- #
# 3. U-NET MODEL (inlined — no external imports)
# --------------------------------------------------------------------------- #

class DoubleConv(nn.Module):
    """(Conv2d -> GroupNorm -> ReLU) x 2"""
    def __init__(self, in_ch, out_ch, mid_ch=None):
        super().__init__()
        mid = mid_ch if mid_ch is not None else out_ch
        self.double_conv = nn.Sequential(
            nn.Conv2d(in_ch, mid, 3, padding=1, bias=False),
            nn.GroupNorm(8, mid),
            nn.ReLU(inplace=True),
            nn.Conv2d(mid, out_ch, 3, padding=1, bias=False),
            nn.GroupNorm(8, out_ch),
            nn.ReLU(inplace=True),
        )
    def forward(self, x):
        return self.double_conv(x)


class DownBlock(nn.Module):
    """MaxPool -> DoubleConv"""
    def __init__(self, in_ch, out_ch):
        super().__init__()
        self.maxpool_conv = nn.Sequential(nn.MaxPool2d(2), DoubleConv(in_ch, out_ch))
    def forward(self, x):
        return self.maxpool_conv(x)


class UpBlock(nn.Module):
    """Upsample -> Concat skip -> DoubleConv"""
    def __init__(self, in_ch, out_ch, bilinear=True):
        super().__init__()
        if bilinear:
            self.up = nn.Upsample(scale_factor=2, mode="bilinear", align_corners=True)
            self.conv = DoubleConv(in_ch, out_ch, mid_ch=in_ch // 2)
        else:
            self.up = nn.ConvTranspose2d(in_ch, in_ch // 2, 2, 2)
            self.conv = DoubleConv(in_ch, out_ch)
    def forward(self, x1, x2):
        x1 = self.up(x1)
        diffY = x2.size()[2] - x1.size()[2]
        diffX = x2.size()[3] - x1.size()[3]
        x1 = F.pad(x1, [diffX // 2, diffX - diffX // 2, diffY // 2, diffY - diffY // 2])
        x = torch.cat([x2, x1], dim=1)
        return self.conv(x)


class WildfireUNetSmall(nn.Module):
    """U-Net Small: 32-64-128-256-512 channels. Input: (B, C, H, W). Output: (B, 1, H, W)."""
    def __init__(self, in_channels=12, out_channels=1, bilinear=True):
        super().__init__()
        self.bilinear = bilinear
        self.inc = DoubleConv(in_channels, 32)
        self.down1 = DownBlock(32, 64)
        self.down2 = DownBlock(64, 128)
        self.down3 = DownBlock(128, 256)
        factor = 2 if bilinear else 1
        self.down4 = DownBlock(256, 512 // factor)
        self.up1 = UpBlock(512, 256 // factor, bilinear)
        self.up2 = UpBlock(256, 128 // factor, bilinear)
        self.up3 = UpBlock(128, 64 // factor, bilinear)
        self.up4 = UpBlock(64, 32, bilinear)
        self.outc = nn.Conv2d(32, out_channels, 1)
    def forward(self, x):
        x1 = self.inc(x)
        x2 = self.down1(x1)
        x3 = self.down2(x2)
        x4 = self.down3(x3)
        x5 = self.down4(x4)
        x = self.up1(x5, x4)
        x = self.up2(x, x3)
        x = self.up3(x, x2)
        x = self.up4(x, x1)
        return self.outc(x)


# --- Loss functions (inlined) ---

def weighted_bce_loss(logits, targets, pos_weight=5.0):
    return F.binary_cross_entropy_with_logits(
        logits, targets, reduction="mean",
        pos_weight=torch.tensor(pos_weight, device=logits.device))

def dice_loss(logits, targets, eps=1e-7):
    probs = torch.sigmoid(logits)
    intersection = (probs * targets).sum(dim=[1,2,3])
    union = probs.sum(dim=[1,2,3]) + targets.sum(dim=[1,2,3])
    dice = (2 * intersection + eps) / (union + eps)
    return (1 - dice).mean()

def combined_loss(logits, targets, pos_weight=5.0, dice_weight=0.5):
    return weighted_bce_loss(logits, targets, pos_weight) + dice_weight * dice_loss(logits, targets)


# --------------------------------------------------------------------------- #
# 4. Data loaders
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

BATCH_SIZE = 32
print(f"Batch size: {BATCH_SIZE}")

train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True,
                          num_workers=4, pin_memory=True, persistent_workers=True)
val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE, shuffle=False,
                        num_workers=4, pin_memory=True, persistent_workers=True)
test_loader = DataLoader(test_dataset, batch_size=BATCH_SIZE, shuffle=False,
                         num_workers=4, pin_memory=True, persistent_workers=True)

# --------------------------------------------------------------------------- #
# Device
# --------------------------------------------------------------------------- #
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
if torch.cuda.is_available():
    torch.backends.cudnn.benchmark = True
    print(f"GPU: {torch.cuda.get_device_name(0)}")
print(f"Device: {device}")

# --------------------------------------------------------------------------- #
# 5. Model
# --------------------------------------------------------------------------- #
sample_seq, sample_curr, sample_target = train_dataset[0]
in_channels = sample_seq.shape[1] * sample_seq.shape[0] + 1  # time*channels + fire mask
print(f"Input channels: {in_channels}")

model = WildfireUNetSmall(in_channels=in_channels, out_channels=1, bilinear=True)
model.to(device)

n_params = sum(p.numel() for p in model.parameters())
print(f"WildfireUNetSmall parameters: {n_params:,}")

USE_AMP = device.type == "cuda"
scaler = torch.amp.GradScaler('cuda', enabled=USE_AMP)

# --------------------------------------------------------------------------- #
# 6. Training
# --------------------------------------------------------------------------- #
EPOCHS = 50
PEAK_LR = 1e-3
WARMUP_EPOCHS = 3
patience = 10

optimizer = torch.optim.AdamW(model.parameters(), lr=PEAK_LR, weight_decay=1e-4)

from torch.optim.lr_scheduler import CosineAnnealingLR, LinearLR, SequentialLR

warmup_scheduler = LinearLR(optimizer, start_factor=0.1, total_iters=WARMUP_EPOCHS)
cosine_scheduler = CosineAnnealingLR(optimizer, T_max=EPOCHS - WARMUP_EPOCHS, eta_min=1e-6)
scheduler = SequentialLR(optimizer, schedulers=[warmup_scheduler, cosine_scheduler], milestones=[WARMUP_EPOCHS])

best_val_loss = float("inf")
best_epoch = -1
no_improve = 0
history = []

LOG_FILE = Path("../training_log.txt")
def log_msg(msg):
    print(msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

log_msg(f"\n--- U-Net v13 started at {time.strftime('%Y-%m-%d %H:%M:%S')} ---")
log_msg(f"Config: EPOCHS={EPOCHS}, BATCH_SIZE={BATCH_SIZE}, LR={PEAK_LR}, params={n_params:,}")


def prepare_input(sequence, current_fire):
    """Flatten temporal dim into channels: (B,T,C,H,W) -> (B,T*C+1,H,W)"""
    B, T, C, H, W = sequence.shape
    flat = sequence.reshape(B, T * C, H, W)
    fire = current_fire.unsqueeze(1)
    return torch.cat([flat, fire], dim=1)


@torch.no_grad()
def evaluate_model(model, loader, device):
    model.eval()
    total_loss, steps = 0.0, 0
    all_metrics = []
    for sequence, current_fire, target_fire in loader:
        sequence = sequence.to(device)
        current_fire = current_fire.to(device)
        target_fire = target_fire.to(device)
        x = prepare_input(sequence, current_fire)
        target = target_fire.unsqueeze(1).float()
        with torch.amp.autocast('cuda', enabled=USE_AMP):
            logits = model(x)
        logits = logits.float()
        loss = weighted_bce_loss(logits, target, pos_weight=5.0)
        total_loss += loss.item()
        steps += 1
        probs = torch.sigmoid(logits)
        for i in range(probs.shape[0]):
            m = compute_segmentation_metrics(probs[i,0].cpu().numpy(), target[i,0].cpu().numpy(), threshold=0.5)
            all_metrics.append(m)
    model.train()
    avg_loss = total_loss / steps if steps else 0.0
    seg = aggregate_segmentation_metrics(all_metrics) if all_metrics else {}
    return avg_loss, seg


for epoch in range(EPOCHS):
    model.train()
    epoch_loss, steps = 0.0, 0
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
    history.append({"epoch": epoch+1, "train_loss": train_loss, "val_loss": val_loss,
                    "val_iou": val_iou, "val_recall": val_recall})
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
    Path("../training_history.json").write_text(json.dumps(history, indent=2))

# --------------------------------------------------------------------------- #
# 7. Final evaluation
# --------------------------------------------------------------------------- #
print(f"\nLoading best checkpoint from epoch {best_epoch}")
model.load_state_dict(torch.load("../weights_pretrained_best.pt", map_location=device))
print("\n=== TEST SET EVALUATION ===")
test_loss, test_seg = evaluate_model(model, test_loader, device)
print(f"  TEST loss: {test_loss:.5f}")
print(f"    IoU:       {test_seg.get('micro_iou', 0.0):.4f}")
print(f"    Dice/F1:   {test_seg.get('micro_dice', 0.0):.4f}")
print(f"    Precision: {test_seg.get('micro_precision', 0.0):.4f}")
print(f"    Recall:    {test_seg.get('micro_recall', 0.0):.4f}")
Path("../evaluation_metrics.json").write_text(json.dumps(test_seg, indent=2, default=str))
summary = {
    "version": "v13",
    "architecture": "WildfireUNetSmall",
    "best_pretrain_epoch": best_epoch,
    "best_val_loss": best_val_loss,
    "test_loss": test_loss,
    "train_samples": len(train_dataset),
    "val_samples": len(val_dataset),
    "test_samples": len(test_dataset),
    "v13_config": {"model": "U-Net", "batch_size": BATCH_SIZE, "peak_lr": PEAK_LR, "n_params": n_params},
    "seg_metrics": test_seg,
}
Path("../training_summary.json").write_text(json.dumps(summary, indent=2, default=str))
print(json.dumps(summary, indent=2, default=str))
print("\n=== U-NET v13 COMPLETED ===")