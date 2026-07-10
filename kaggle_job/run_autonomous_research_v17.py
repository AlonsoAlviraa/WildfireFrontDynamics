#!/usr/bin/env python3
"""Autonomous Wildfire Segmentation Research Pipeline v17b.

COMPLETELY SELF-CONTAINED: No external imports from wildfire_front package.
All preprocessing, model, dataset, losses, and training logic inlined.

Solves bottlenecks:
  - Extreme imbalance (99% background) → SOTA losses
  - Copy-baseline dominance (IoU=0.79) → Residual Delta learning
  - Noisy channels (14/17 useless) → Feature importance + pruning
  - Data leakage → Content fingerprint anti-leakage checks

Phases (16h budget):
  0: Data + feature analysis (10 min)
  1: Copy baseline (5 min)
  2: Optuna sweep (~14h, ~40 trials)
  3: Full retraining (45 min)
  4: Production export (30 min)
"""

import os
import sys
import subprocess
import json
import time
import random
import hashlib
import argparse
import warnings
import traceback
from pathlib import Path
from datetime import datetime
from collections import defaultdict

warnings.filterwarnings("ignore")

# =================================================================== #
# 0. FIX P100 sm_60 compatibility — MUST happen before importing torch
# =================================================================== #
print("=" * 80)
print("AUTONOMOUS WILDFIRE SEGMENTATION RESEARCH PIPELINE v17b")
print("=" * 80)

def _install_pt_for_p100():
    """Detect P100 GPU (sm_60) and install compatible PyTorch BEFORE import."""
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10
        )
        if r.returncode == 0:
            gpu_name = r.stdout.strip()
            print(f"  GPU detected: {gpu_name}")
            if "P100" in gpu_name or "T4" in gpu_name:
                # Check current PyTorch version
                try:
                    import torch as _t_check
                    _t_ver = _t_check.__version__
                    print(f"  PyTorch installed: {_t_ver}")
                    if int(_t_ver.split(".")[0]) > 2 or (
                        int(_t_ver.split(".")[0]) == 2 and int(_t_ver.split(".")[1]) > 1
                    ):
                        print(f"  Installing PyTorch 2.1.2 (supports sm_60/sm_75)...")
                        subprocess.run(
                            [sys.executable, "-m", "pip", "install", "-q",
                             "torch==2.1.2", "torchvision==0.16.2"],
                            check=True, capture_output=True
                        )
                        print("  PyTorch 2.1.2 installed.")
                        # Force reimport by deleting from sys.modules
                        for mod in list(sys.modules.keys()):
                            if "torch" in mod:
                                del sys.modules[mod]
                except ImportError:
                    print("  PyTorch not found, installing 2.1.2...")
                    subprocess.run(
                        [sys.executable, "-m", "pip", "install", "-q",
                         "torch==2.1.2", "torchvision==0.16.2"],
                        check=True, capture_output=True
                    )
    except Exception as e:
        print(f"  GPU check warning: {e}")

_install_pt_for_p100()

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader

print(f"PyTorch version: {torch.__version__}")
SEED = 42
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)
if torch.cuda.is_available():
    torch.cuda.manual_seed_all(SEED)
    torch.backends.cudnn.benchmark = True

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# PyTorch 2.1.x compatible AMP API
USE_AMP = DEVICE.type == "cuda"
print(f"Device: {DEVICE} | AMP: {USE_AMP}")

if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    cap = torch.cuda.get_device_capability(0)
    print(f"Compute capability: sm_{cap[0]}{cap[1]}")

# =================================================================== #
# Install optuna
# =================================================================== #
try:
    import optuna
except ImportError:
    print("Installing optuna...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "optuna"], check=True)
    import optuna
optuna.logging.set_verbosity(optuna.logging.WARNING)

# =================================================================== #
# 1. Clone repo + preprocess NDWS data
# =================================================================== #
if not Path("WildfireFrontDynamics").exists():
    print("Cloning repository...")
    subprocess.run(
        ["git", "clone", "--depth", "1",
         "https://github.com/AlonsoAlviraa/WildfireFrontDynamics.git"],
        check=True
    )

os.chdir("WildfireFrontDynamics")
sys.path.insert(0, os.getcwd())

# =================================================================== #
# NDWS PREPROCESSING (self-contained)
# =================================================================== #
DATA_ROOT = Path("/tmp/ndws_npz")

def preprocess_ndws():
    """Convert NDWS TFRecords to NPZ patches."""
    import struct
    tfrecord_glob = Path("/kaggle/input/next-day-wildfire-spread")

    # Find TFRecord files
    tf_files = sorted(tfrecord_glob.glob("*.tfrecord"))
    if not tf_files:
        tf_files = sorted(tfrecord_glob.glob("*next*day*"))
    if not tf_files:
        # Try subdirectories
        tf_files = sorted(tfrecord_glob.rglob("*.tfrecord"))

    print(f"  Found {len(tf_files)} TFRecord files")

    if not tf_files:
        raise FileNotFoundError(f"No TFRecords found in {tfrecord_glob}")

    # Standard NDWS splits
    splits = {
        "train": list(range(0, 12)),
        "val": list(range(12, 14)),
        "test": list(range(14, 15)),
    }

    # Feature names and shapes from NDWS
    FEATURE_NAMES = [
        "elevation", "pdsi", "NDVI", "precipitation", "downward_shortwave_radiation_flux",
        "energy_release_component", "specific_humidity", "temperature",
        "wind_direction", "wind_speed",
        "previous_day_fire_mask",  # input (prev fire)
        "fire_mask",  # target
    ]

    for split_name, indices in splits.items():
        out_dir = DATA_ROOT / split_name
        out_dir.mkdir(parents=True, exist_ok=True)

        existing = list(out_dir.glob("*.npz"))
        if len(existing) > 10:
            print(f"  {split_name}: {len(existing)} patches already exist, skipping")
            continue

        print(f"  Processing {split_name} (shards {indices})...")
        count = 0

        for idx in indices:
            if idx >= len(tf_files):
                continue
            tf_path = tf_files[idx]
            try:
                patches = parse_tfrecord_simple(str(tf_path))
                for patch in patches:
                    if patch is None:
                        continue
                    np.savez_compressed(
                        out_dir / f"{split_name}_{count:05d}.npz",
                        sequence=patch["sequence"],
                        current_fire=patch["current_fire"],
                        target_fire=patch["target_fire"],
                    )
                    count += 1
            except Exception as e:
                print(f"    Warning: shard {idx} failed: {e}")

        print(f"    {split_name}: {count} patches")

    return splits


def parse_tfrecord_simple(filepath):
    """Parse NDWS TFRecord using raw TF parsing (no TF dependency if possible)."""
    try:
        import tensorflow as tf
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "tensorflow"], check=True)
        import tensorflow as tf

    FEATURE_DESC = {
        "elevation": tf.io.FixedLenFeature([64, 64], tf.float32),
        "pdsi": tf.io.FixedLenFeature([64, 64], tf.float32),
        "NDVI": tf.io.FixedLenFeature([64, 64], tf.float32),
        "precipitation": tf.io.FixedLenFeature([64, 64], tf.float32),
        "downward_shortwave_radiation_flux": tf.io.FixedLenFeature([64, 64], tf.float32),
        "energy_release_component": tf.io.FixedLenFeature([64, 64], tf.float32),
        "specific_humidity": tf.io.FixedLenFeature([64, 64], tf.float32),
        "temperature": tf.io.FixedLenFeature([64, 64], tf.float32),
        "wind_direction": tf.io.FixedLenFeature([64, 64], tf.float32),
        "wind_speed": tf.io.FixedLenFeature([64, 64], tf.float32),
        "previous_day_fire_mask": tf.io.FixedLenFeature([64, 64], tf.float32),
        "fire_mask": tf.io.FixedLenFeature([64, 64], tf.float32),
    }

    patches = []
    dataset = tf.data.TFRecordDataset(filepath)
    for serialized in dataset:
        example = tf.io.parse_single_example(serialized, FEATURE_DESC)

        # Stack features: 10 weather + 1 prev_fire = 11 channels
        channels = [
            example["elevation"].numpy(),
            example["pdsi"].numpy(),
            example["NDVI"].numpy(),
            example["precipitation"].numpy(),
            example["downward_shortwave_radiation_flux"].numpy(),
            example["energy_release_component"].numpy(),
            example["specific_humidity"].numpy(),
            example["temperature"].numpy(),
            example["wind_direction"].numpy(),
            example["wind_speed"].numpy(),
        ]

        prev_fire = example["previous_day_fire_mask"].numpy()
        target_fire = example["fire_mask"].numpy()

        # Normalize
        seq = np.stack(channels, axis=0).astype(np.float32)  # (10, 64, 64)
        seq = np.nan_to_num(seq, nan=0.0, posinf=0.0, neginf=0.0)

        # Normalize each channel
        for c in range(seq.shape[0]):
            std = seq[c].std()
            if std > 1e-6:
                seq[c] = (seq[c] - seq[c].mean()) / std

        # Add temporal dim for compatibility: (T=1, C=10, H, W)
        sequence = seq[np.newaxis, ...]

        prev_fire = (prev_fire > 0).astype(np.float32)
        target_fire = (target_fire > 0).astype(np.float32)

        patches.append({
            "sequence": sequence,
            "current_fire": prev_fire,
            "target_fire": target_fire,
        })

    return patches


# Run preprocessing
if not (DATA_ROOT / "train").exists() or len(list((DATA_ROOT / "train").glob("*.npz"))) < 10:
    print("\n=== PREPROCESSING NDWS TFRecords ===")
    try:
        preprocess_ndws()
    except Exception as e:
        print(f"Preprocessing error: {e}")
        traceback.print_exc()
        # Try using repo's preprocess script
        print("Falling back to repo preprocess script...")
        for split in ["train", "val", "test"]:
            subprocess.run([sys.executable, "kaggle_job/preprocess_ndws.py",
                          "--split", split], check=False)

# Verify data exists
for split in ["train", "val", "test"]:
    n = len(list((DATA_ROOT / split).glob("*.npz")))
    print(f"  {split}: {n} patches")


# =================================================================== #
# 2. DATASET
# =================================================================== #
class WildfireDataset(Dataset):
    def __init__(self, directory, augment=False, selected_channels=None):
        self.directory = Path(directory)
        self.files = sorted(self.directory.glob("*.npz"))
        self.augment = augment
        self.selected_channels = selected_channels  # list of channel indices or None
        self._fps = self._fingerprints()

    def _fingerprints(self):
        fps = []
        for f in self.files:
            try:
                with np.load(f) as d:
                    fps.append(hashlib.md5(d["current_fire"].tobytes()).hexdigest()[:8])
            except:
                fps.append("err")
        return fps

    def __len__(self):
        return len(self.files)

    def __getitem__(self, idx):
        with np.load(self.files[idx]) as d:
            seq = np.where(np.isfinite(d["sequence"]), d["sequence"].astype(np.float32), 0.0)
            cf = d["current_fire"].astype(np.float32)
            tf_mask = d["target_fire"].astype(np.float32)

        # Channel pruning
        if self.selected_channels is not None:
            # seq shape: (T, C, H, W) — select from C dimension
            seq = seq[:, self.selected_channels, :, :]

        seq = torch.from_numpy(seq)
        cf = torch.from_numpy(cf)
        tf_mask = torch.from_numpy(tf_mask)

        if self.augment:
            if random.random() < 0.5:
                seq = torch.flip(seq, dims=[-1])
                cf = torch.flip(cf, dims=[-1])
                tf_mask = torch.flip(tf_mask, dims=[-1])
            if random.random() < 0.5:
                seq = torch.flip(seq, dims=[-2])
                cf = torch.flip(cf, dims=[-2])
                tf_mask = torch.flip(tf_mask, dims=[-2])

        return seq, cf, tf_mask


def prepare_input(seq, cf):
    """Flatten temporal dim into channels: (B,T,C,H,W) -> (B,T*C+1,H,W)"""
    B, T, C, H, W = seq.shape
    flat = seq.reshape(B, T * C, H, W)
    fire = cf.unsqueeze(1)  # (B,1,H,W)
    return torch.cat([flat, fire], dim=1)


# =================================================================== #
# 3. SOTA LOSS FUNCTIONS
# =================================================================== #
class FocalLoss(nn.Module):
    def __init__(self, alpha=0.75, gamma=2.0, pos_weight=5.0):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma
        self.pos_weight = pos_weight

    def forward(self, logits, targets):
        logits = torch.clamp(logits, -10, 10)
        pw = torch.tensor(self.pos_weight, device=logits.device)
        bce = F.binary_cross_entropy_with_logits(logits, targets, reduction="none", pos_weight=pw)
        p = torch.sigmoid(logits)
        p_t = p * targets + (1 - p) * (1 - targets)
        return (self.alpha * ((1 - p_t) ** self.gamma) * bce).mean()


class TverskyLoss(nn.Module):
    def __init__(self, alpha=0.3, beta=0.7, smooth=1e-7):
        super().__init__()
        self.alpha = alpha
        self.beta = beta
        self.smooth = smooth

    def forward(self, logits, targets):
        probs = torch.sigmoid(logits)
        tp = (probs * targets).sum(dim=[1, 2, 3])
        fp = ((1 - targets) * probs).sum(dim=[1, 2, 3])
        fn = (targets * (1 - probs)).sum(dim=[1, 2, 3])
        tv = (tp + self.smooth) / (tp + self.alpha * fp + self.beta * fn + self.smooth)
        return (1 - tv).mean()


class DiceLoss(nn.Module):
    def __init__(self, smooth=1e-7):
        super().__init__()
        self.smooth = smooth

    def forward(self, logits, targets):
        probs = torch.sigmoid(logits)
        intersection = (probs * targets).sum(dim=[1, 2, 3])
        union = probs.sum(dim=[1, 2, 3]) + targets.sum(dim=[1, 2, 3])
        dice = (2 * intersection + self.smooth) / (union + self.smooth)
        return (1 - dice).mean()


class CompositeSOTALLoss(nn.Module):
    """Weighted combination of Focal + Tversky + Dice + Weighted BCE."""
    def __init__(self, w_focal=1.0, w_tversky=0.5, w_dice=0.5, w_bce=0.5,
                 pos_weight=5.0, gamma=2.0):
        super().__init__()
        self.focal = FocalLoss(0.75, gamma, pos_weight)
        self.tversky = TverskyLoss()
        self.dice = DiceLoss()
        self.w_focal = w_focal
        self.w_tversky = w_tversky
        self.w_dice = w_dice
        self.w_bce = w_bce
        self.pos_weight = pos_weight

    def forward(self, logits, targets):
        pw = torch.tensor(self.pos_weight, device=logits.device)
        bce = F.binary_cross_entropy_with_logits(logits, targets, pos_weight=pw)
        return (self.w_focal * self.focal(logits, targets)
                + self.w_tversky * self.tversky(logits, targets)
                + self.w_dice * self.dice(logits, targets)
                + self.w_bce * bce)


# =================================================================== #
# 4. ATTENTION MODULES
# =================================================================== #
class SEBlock(nn.Module):
    def __init__(self, ch, r=8):
        super().__init__()
        self.sq = nn.AdaptiveAvgPool2d(1)
        self.ex = nn.Sequential(
            nn.Linear(ch, max(ch // r, 4), bias=False),
            nn.ReLU(inplace=True),
            nn.Linear(max(ch // r, 4), ch, bias=False),
            nn.Sigmoid()
        )

    def forward(self, x):
        b, c = x.shape[:2]
        s = self.ex(self.sq(x).view(b, c)).view(b, c, 1, 1)
        return x * s


class CBAM(nn.Module):
    def __init__(self, ch, r=8):
        super().__init__()
        self.avg = nn.AdaptiveAvgPool2d(1)
        self.maxp = nn.AdaptiveMaxPool2d(1)
        self.mlp = nn.Sequential(
            nn.Conv2d(ch, max(ch // r, 4), 1, bias=False),
            nn.ReLU(inplace=True),
            nn.Conv2d(max(ch // r, 4), ch, 1, bias=False)
        )
        self.spatial = nn.Conv2d(2, 1, 7, padding=3, bias=False)

    def forward(self, x):
        ca = torch.sigmoid(self.mlp(self.avg(x)) + self.mlp(self.maxp(x)))
        x = x * ca
        sa = torch.sigmoid(self.spatial(
            torch.cat([x.mean(1, keepdim=True), x.max(1, keepdim=True)[0]], dim=1)
        ))
        return x * sa


# =================================================================== #
# 5. RESIDUAL DELTA U-NET
# =================================================================== #
class DoubleConv(nn.Module):
    def __init__(self, in_ch, out_ch, mid_ch=None, norm="group", attention=None):
        super().__init__()
        mid = mid_ch if mid_ch is not None else out_ch
        norm_fn = lambda c: nn.GroupNorm(8, c) if norm == "group" else nn.BatchNorm2d(c)
        self.body = nn.Sequential(
            nn.Conv2d(in_ch, mid, 3, padding=1, bias=False),
            norm_fn(mid),
            nn.ReLU(inplace=True),
            nn.Conv2d(mid, out_ch, 3, padding=1, bias=False),
            norm_fn(out_ch),
            nn.ReLU(inplace=True),
        )
        if attention == "cbam":
            self.att = CBAM(out_ch)
        elif attention == "se":
            self.att = SEBlock(out_ch)
        else:
            self.att = nn.Identity()

    def forward(self, x):
        return self.att(self.body(x))


class DownBlock(nn.Module):
    def __init__(self, in_ch, out_ch, **kw):
        super().__init__()
        self.pool_conv = nn.Sequential(nn.MaxPool2d(2), DoubleConv(in_ch, out_ch, **kw))

    def forward(self, x):
        return self.pool_conv(x)


class UpBlock(nn.Module):
    def __init__(self, in_ch, out_ch, bilinear=True, **kw):
        super().__init__()
        if bilinear:
            self.up = nn.Upsample(scale_factor=2, mode="bilinear", align_corners=True)
            self.conv = DoubleConv(in_ch, out_ch, mid_ch=in_ch // 2, **kw)
        else:
            self.up = nn.ConvTranspose2d(in_ch, in_ch // 2, 2, 2)
            self.conv = DoubleConv(in_ch, out_ch, **kw)

    def forward(self, x1, x2):
        x1 = self.up(x1)
        diffY = x2.size()[2] - x1.size()[2]
        diffX = x2.size()[3] - x1.size()[3]
        x1 = F.pad(x1, [diffX // 2, diffX - diffX // 2, diffY // 2, diffY - diffY // 2])
        x = torch.cat([x2, x1], dim=1)
        return self.conv(x)


class ResidualWildfireUNet(nn.Module):
    """U-Net that predicts DELTA over copy baseline.

    output = delta_scale * delta + copy_bias * (prev_fire * 2 - 1)
    """
    def __init__(self, in_channels=12, base_ch=32, depth=3, bilinear=True,
                 norm="group", attention="cbam", dropout=0.1):
        super().__init__()
        kw = dict(norm=norm, attention=attention)
        self.inc = DoubleConv(in_channels, base_ch, **kw)
        self.downs = nn.ModuleList()
        ch = base_ch
        for _ in range(depth):
            next_ch = min(ch * 2, 512)
            self.downs.append(DownBlock(ch, next_ch, **kw))
            ch = next_ch

        self.ups = nn.ModuleList()
        for i in range(depth):
            out_ch = max(base_ch * (2 ** (depth - i - 1)), base_ch)
            self.ups.append(UpBlock(ch, out_ch, bilinear, **kw))
            ch = out_ch

        self.drop = nn.Dropout2d(dropout) if dropout > 0 else nn.Identity()
        self.outc = nn.Conv2d(ch, 1, 1)

        # Residual delta parameters
        self.delta_scale = nn.Parameter(torch.tensor(1.0))
        self.copy_bias = nn.Parameter(torch.tensor(2.0))

    def forward(self, x, prev_fire):
        x1 = self.inc(x)
        skips = [x1]
        for d in self.downs:
            x1 = d(x1)
            skips.append(x1)
        skips = skips[:-1][::-1]
        for u, s in zip(self.ups, skips):
            x1 = u(x1, s)
        delta = self.outc(self.drop(x1))
        return self.delta_scale * delta + self.copy_bias * (prev_fire * 2 - 1)

    def predict_proba(self, x, prev_fire):
        return torch.sigmoid(self.forward(x, prev_fire))


# =================================================================== #
# 6. EVALUATION
# =================================================================== #
def compute_iou(pred, target, thresh=0.5, eps=1e-7):
    pb = (pred >= thresh).astype(np.float64)
    tb = (target >= thresh).astype(np.float64)
    tp = np.sum((pb == 1) & (tb == 1))
    fp = np.sum((pb == 1) & (tb == 0))
    fn = np.sum((pb == 0) & (tb == 1))
    return tp / (tp + fp + fn + eps)


@torch.no_grad()
def evaluate_model(model, loader, device):
    model.eval()
    all_preds = []
    all_targets = []
    copy_ious = []

    for seq, cf, tf_mask in loader:
        seq = seq.to(device)
        cf = cf.to(device)
        tf_mask = tf_mask.to(device)
        x = prepare_input(seq, cf)
        tgt = tf_mask.unsqueeze(1).float()

        logits = model(x, cf.unsqueeze(1))
        probs = torch.sigmoid(logits)

        all_preds.append(probs.cpu().numpy())
        all_targets.append(tgt.cpu().numpy())

        # Copy baseline IoU for this batch
        cf_np = cf.unsqueeze(1).cpu().numpy()
        tf_np = tgt.cpu().numpy()
        for i in range(cf_np.shape[0]):
            copy_ious.append(compute_iou(cf_np[i, 0:1], tf_np[i], 0.5))

    preds = np.concatenate(all_preds)
    tgts = np.concatenate(all_targets)

    return {
        "iou@0.5": float(compute_iou(preds, tgts, 0.5)),
        "iou@0.3": float(compute_iou(preds, tgts, 0.3)),
        "iou@0.4": float(compute_iou(preds, tgts, 0.4)),
        "iou@0.6": float(compute_iou(preds, tgts, 0.6)),
        "copy_baseline_iou": float(np.mean(copy_ious)),
    }


# =================================================================== #
# 7. FEATURE ANALYSIS
# =================================================================== #
def analyze_features(ds, max_n=500):
    print("\n=== FEATURE IMPORTANCE ANALYSIS ===")
    scores = defaultdict(list)
    channel_names = [
        "elevation", "pdsi", "NDVI", "precip", "radiation",
        "ERC", "humidity", "temperature", "wind_dir", "wind_speed",
        "prev_fire", "pad1", "pad2", "pad3", "pad4", "pad5", "pad6"
    ]

    for i in range(min(len(ds), max_n)):
        seq, cf, tf_mask = ds[i]
        T, C, H, W = seq.shape
        tf_flat = (tf_mask >= 0.5).numpy().flatten().astype(int)

        for ci in range(C):
            ch = seq[0, ci].numpy().flatten()
            if np.std(ch) < 1e-6:
                scores[ci].append(0.0)
                continue
            if np.std(tf_flat) < 1e-6:
                scores[ci].append(0.0)
                continue
            r = np.corrcoef(ch, tf_flat)[0, 1]
            scores[ci].append(abs(r) if np.isfinite(r) else 0.0)

    ranked = sorted(
        [(ci, channel_names[ci] if ci < len(channel_names) else f"ch{ci}",
          float(np.mean(s))) for ci, s in scores.items()],
        key=lambda x: x[2], reverse=True
    )

    print("  Channel importance ranking:")
    for ci, name, score in ranked:
        bar = "#" * int(score * 200)
        print(f"    {name:15s} score={score:.4f} {bar}")

    # Select channels cumulatively reaching 95% importance
    total = sum(r[2] for r in ranked) + 1e-7
    cumulative = 0
    selected = []
    for ci, name, score in ranked:
        cumulative += score
        selected.append(ci)
        if cumulative / total > 0.95:
            break

    print(f"\n  Selected {len(selected)}/{len(ranked)} channels (95% importance)")
    return selected


# =================================================================== #
# 8. OPTUNA OBJECTIVE
# =================================================================== #
def make_scaler():
    """Create AMP scaler compatible with PyTorch 2.1.x."""
    if USE_AMP:
        return torch.cuda.amp.GradScaler()
    return torch.cuda.amp.GradScaler(enabled=False)


def autocast_context():
    """AMP autocast context compatible with PyTorch 2.1.x."""
    if USE_AMP:
        return torch.cuda.amp.autocast()
    return torch.cuda.amp.autocast(enabled=False)


def create_objective(train_ds, val_ds, device, in_channels):
    def objective(trial):
        # Time check
        elapsed = time.time() - START_TIME
        if elapsed > MAX_HOURS * 3600 - 1800:
            raise optuna.TrialPruned()

        cfg = {
            "base_ch": trial.suggest_categorical("base_ch", [16, 32, 48]),
            "depth": trial.suggest_int("depth", 2, 4),
            "attention": trial.suggest_categorical("attention", ["cbam", "se", "none"]),
            "norm": trial.suggest_categorical("norm", ["group", "batch"]),
            "dropout": trial.suggest_float("dropout", 0.0, 0.3),
            "lr": trial.suggest_float("lr", 1e-4, 5e-3, log=True),
            "batch_size": trial.suggest_categorical("batch_size", [16, 32, 64]),
            "w_focal": trial.suggest_float("w_focal", 0.5, 2.0),
            "w_tversky": trial.suggest_float("w_tversky", 0.1, 1.0),
            "w_dice": trial.suggest_float("w_dice", 0.1, 1.0),
            "w_bce": trial.suggest_float("w_bce", 0.1, 1.0),
            "pos_weight": trial.suggest_float("pos_weight", 3.0, 15.0),
            "focal_gamma": trial.suggest_float("focal_gamma", 1.5, 3.0),
            "epochs": trial.suggest_int("epochs", 15, 40),
        }

        att = None if cfg["attention"] == "none" else cfg["attention"]

        model = ResidualWildfireUNet(
            in_channels=in_channels,
            base_ch=cfg["base_ch"],
            depth=cfg["depth"],
            norm=cfg["norm"],
            attention=att,
            dropout=cfg["dropout"]
        ).to(device)

        trial.set_user_attr("n_params", sum(p.numel() for p in model.parameters()))

        criterion = CompositeSOTALLoss(
            w_focal=cfg["w_focal"],
            w_tversky=cfg["w_tversky"],
            w_dice=cfg["w_dice"],
            w_bce=cfg["w_bce"],
            pos_weight=cfg["pos_weight"],
            gamma=cfg["focal_gamma"]
        ).to(device)

        optimizer = torch.optim.AdamW(model.parameters(), lr=cfg["lr"], weight_decay=1e-4)
        scheduler = torch.optim.lr_scheduler.CosineAnnealingWarmRestarts(
            optimizer, T_0=5, T_mult=2, eta_min=1e-6
        )
        scaler = make_scaler()

        train_loader = DataLoader(
            train_ds, batch_size=cfg["batch_size"], shuffle=True,
            num_workers=2, pin_memory=True, drop_last=True
        )
        val_loader = DataLoader(
            val_ds, batch_size=cfg["batch_size"], shuffle=False,
            num_workers=2, pin_memory=True
        )

        best_iou = 0.0
        no_improve = 0

        for epoch in range(cfg["epochs"]):
            # Time budget check
            elapsed = time.time() - START_TIME
            if elapsed > MAX_HOURS * 3600 - 1800:
                break

            model.train()
            for seq, cf, tf_mask in train_loader:
                seq = seq.to(device)
                cf = cf.to(device)
                tf_mask = tf_mask.to(device)
                x = prepare_input(seq, cf)
                tgt = tf_mask.unsqueeze(1).float()

                optimizer.zero_grad()
                with autocast_context():
                    logits = model(x, cf.unsqueeze(1))
                    loss = criterion(logits, tgt)

                scaler.scale(loss).backward()
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                scaler.step(optimizer)
                scaler.update()

            scheduler.step()

            val_results = evaluate_model(model, val_loader, device)
            val_iou = val_results.get("iou@0.5", 0.0)

            trial.report(val_iou, epoch)
            if trial.should_prune():
                raise optuna.TrialPruned()

            if val_iou > best_iou:
                best_iou = val_iou
                no_improve = 0
            else:
                no_improve += 1
                if no_improve >= 5:
                    break

        trial.set_user_attr("copy_baseline_iou", val_results.get("copy_baseline_iou", 0.0))
        trial.set_user_attr("margin_over_copy", best_iou - val_results.get("copy_baseline_iou", 0.0))
        return best_iou

    return objective


# =================================================================== #
# 9. MAIN PIPELINE
# =================================================================== #
MAX_HOURS = 16.0
START_TIME = time.time()
OUT_DIR = Path("../")

def log_msg(msg, log_file=None):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    if log_file:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def main():
    log_path = OUT_DIR / "research_log.txt"
    log_msg("=" * 70, log_path)
    log_msg("AUTONOMOUS WILDFIRE RESEARCH PIPELINE v17b", log_path)
    log_msg("=" * 70, log_path)

    # ---- PHASE 0: Data + Feature Analysis ----
    log_msg("\n=== PHASE 0: Data + Feature Analysis ===", log_path)

    train_ds = WildfireDataset(DATA_ROOT / "train", augment=True)
    val_ds = WildfireDataset(DATA_ROOT / "val", augment=False)
    test_ds = WildfireDataset(DATA_ROOT / "test", augment=False)
    log_msg(f"Dataset sizes: train={len(train_ds)} val={len(val_ds)} test={len(test_ds)}", log_path)

    # Anti-leakage check
    tv_overlap = len(set(train_ds._fps) & set(val_ds._fps))
    tt_overlap = len(set(train_ds._fps) & set(test_ds._fps))
    log_msg(f"Anti-leakage: train-val overlap={tv_overlap}, train-test overlap={tt_overlap}", log_path)
    if tv_overlap > 0 or tt_overlap > 0:
        log_msg("WARNING: Potential data leakage detected!", log_path)

    # Feature analysis
    selected_channels = analyze_features(train_ds)

    # Create datasets with channel pruning
    train_ds_pruned = WildfireDataset(DATA_ROOT / "train", augment=True, selected_channels=selected_channels)
    val_ds_pruned = WildfireDataset(DATA_ROOT / "val", augment=False, selected_channels=selected_channels)
    test_ds_pruned = WildfireDataset(DATA_ROOT / "test", augment=False, selected_channels=selected_channels)

    # Determine input channels
    sample_seq, _, _ = train_ds_pruned[0]
    in_channels = sample_seq.shape[0] * sample_seq.shape[1] + 1  # T*C + fire mask
    log_msg(f"Input channels (after pruning): {in_channels}", log_path)

    # ---- PHASE 1: Copy Baseline ----
    log_msg("\n=== PHASE 1: Copy Baseline ===", log_path)
    test_loader = DataLoader(test_ds_pruned, batch_size=32, shuffle=False, num_workers=2)
    copy_ious = []
    for _, cf, tf_mask in test_loader:
        cf_np = cf.unsqueeze(1).numpy()
        tf_np = tf_mask.unsqueeze(1).numpy()
        for i in range(cf_np.shape[0]):
            copy_ious.append(compute_iou(cf_np[i, 0:1], tf_np[i], 0.5))
    copy_baseline_iou = float(np.mean(copy_ious))
    log_msg(f"Copy baseline IoU@0.5: {copy_baseline_iou:.4f}", log_path)

    # ---- PHASE 2: Optuna Sweep ----
    sweep_budget = MAX_HOURS * 3600 - (time.time() - START_TIME) - 2.0 * 3600  # leave 2h for retrain + export
    log_msg(f"\n=== PHASE 2: Optuna Sweep ({sweep_budget/3600:.1f}h budget) ===", log_path)

    study = optuna.create_study(
        direction="maximize",
        pruner=optuna.pruners.MedianPruner(n_startup_trials=3, n_warmup_steps=5),
        sampler=optuna.samplers.TPESampler(seed=SEED)
    )

    try:
        study.optimize(
            create_objective(train_ds_pruned, val_ds_pruned, DEVICE, in_channels),
            n_trials=40,
            timeout=sweep_budget,
            catch=(Exception,)
        )
    except Exception as e:
        log_msg(f"Sweep interrupted: {e}", log_path)

    log_msg(f"Sweep completed: {len(study.trials)} trials", log_path)
    if study.best_trial is not None:
        log_msg(f"Best sweep IoU: {study.best_value:.4f}", log_path)
        best_params = study.best_params
        best_params["n_params"] = study.best_trial.user_attrs.get("n_params", 0)
        best_params["copy_baseline_iou"] = study.best_trial.user_attrs.get("copy_baseline_iou", 0)
        (OUT_DIR / "best_params.json").write_text(
            json.dumps(best_params, indent=2, default=str)
        )
    else:
        log_msg("No valid trials! Using default params.", log_path)
        best_params = {
            "base_ch": 32, "depth": 3, "attention": "cbam", "norm": "group",
            "dropout": 0.1, "lr": 1e-3, "batch_size": 32,
            "w_focal": 1.0, "w_tversky": 0.5, "w_dice": 0.5, "w_bce": 0.5,
            "pos_weight": 5.0, "focal_gamma": 2.0, "epochs": 30
        }

    # ---- PHASE 3: Full Retraining ----
    log_msg("\n=== PHASE 3: Full Retraining (best config) ===", log_path)
    att = None if best_params.get("attention", "none") == "none" else best_params.get("attention")

    best_model = ResidualWildfireUNet(
        in_channels=in_channels,
        base_ch=best_params["base_ch"],
        depth=best_params["depth"],
        norm=best_params["norm"],
        attention=att,
        dropout=best_params["dropout"]
    ).to(DEVICE)

    criterion = CompositeSOTALLoss(
        w_focal=best_params["w_focal"],
        w_tversky=best_params["w_tversky"],
        w_dice=best_params["w_dice"],
        w_bce=best_params["w_bce"],
        pos_weight=best_params["pos_weight"],
        gamma=best_params["focal_gamma"]
    ).to(DEVICE)

    optimizer = torch.optim.AdamW(best_model.parameters(), lr=best_params["lr"], weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingWarmRestarts(
        optimizer, T_0=5, T_mult=2, eta_min=1e-6
    )
    scaler = make_scaler()

    train_loader = DataLoader(
        train_ds_pruned, batch_size=best_params["batch_size"], shuffle=True,
        num_workers=4, pin_memory=True, drop_last=True
    )
    val_loader = DataLoader(
        val_ds_pruned, batch_size=best_params["batch_size"], shuffle=False,
        num_workers=4, pin_memory=True
    )

    best_val_iou = 0.0
    retrain_history = []

    for epoch in range(50):
        elapsed = time.time() - START_TIME
        if elapsed > MAX_HOURS * 3600 - 1800:
            log_msg(f"Time budget reached at epoch {epoch+1}", log_path)
            break

        best_model.train()
        epoch_loss = 0.0
        steps = 0
        t0 = time.time()

        for seq, cf, tf_mask in train_loader:
            seq = seq.to(DEVICE)
            cf = cf.to(DEVICE)
            tf_mask = tf_mask.to(DEVICE)
            x = prepare_input(seq, cf)
            tgt = tf_mask.unsqueeze(1).float()

            optimizer.zero_grad()
            with autocast_context():
                logits = best_model(x, cf.unsqueeze(1))
                loss = criterion(logits, tgt)

            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(best_model.parameters(), 1.0)
            scaler.step(optimizer)
            scaler.update()

            epoch_loss += loss.item()
            steps += 1

        scheduler.step()
        val_results = evaluate_model(best_model, val_loader, DEVICE)
        val_iou = val_results.get("iou@0.5", 0.0)
        elapsed_ep = time.time() - t0

        log_msg(
            f"  Epoch {epoch+1}/50: train_loss={epoch_loss/steps:.4f} "
            f"val_iou={val_iou:.4f} copy_iou={val_results.get('copy_baseline_iou', 0):.4f} "
            f"({elapsed_ep:.0f}s)",
            log_path
        )
        retrain_history.append({
            "epoch": epoch + 1,
            "train_loss": epoch_loss / steps,
            "val_iou": val_iou,
        })

        if val_iou > best_val_iou:
            best_val_iou = val_iou
            torch.save(best_model.state_dict(), OUT_DIR / "best_model.pt")
            log_msg(f"    -> new best val_iou, checkpoint saved", log_path)

    (OUT_DIR / "retrain_history.json").write_text(json.dumps(retrain_history, indent=2))

    # ---- PHASE 4: Production Export ----
    log_msg("\n=== PHASE 4: Production Export ===", log_path)

    best_model.load_state_dict(torch.load(OUT_DIR / "best_model.pt", map_location=DEVICE))
    test_results = evaluate_model(best_model, test_loader, DEVICE)
    model_iou = test_results.get("iou@0.5", 0.0)

    log_msg(f"\n{'='*50}", log_path)
    log_msg(f"FINAL RESULTS:", log_path)
    log_msg(f"  Model IoU@0.5:     {model_iou:.4f}", log_path)
    log_msg(f"  Copy baseline IoU: {copy_baseline_iou:.4f}", log_path)
    log_msg(f"  Margin over copy:  {model_iou - copy_baseline_iou:+.4f}", log_path)
    log_msg(f"  Best sweep IoU:    {study.best_value:.4f}", log_path)
    log_msg(f"  Beats copy:        {'YES' if model_iou > copy_baseline_iou else 'NO'}", log_path)
    log_msg(f"{'='*50}", log_path)

    # Export TorchScript
    try:
        best_model.eval()
        scripted = torch.jit.script(best_model)
        scripted.save(str(OUT_DIR / "wildfire_model_production.pt"))
        log_msg("TorchScript model exported", log_path)
    except Exception as e:
        log_msg(f"TorchScript failed ({e}), saving state_dict", log_path)
        torch.save(best_model.state_dict(), OUT_DIR / "wildfire_model_production.pt")

    # Final report
    summary = {
        "version": "v17b",
        "pipeline": "autonomous_research",
        "timestamp": datetime.now().isoformat(),
        "total_runtime_s": time.time() - START_TIME,
        "n_trials": len(study.trials),
        "best_sweep_iou": float(study.best_value) if study.best_trial else 0.0,
        "copy_baseline_iou": copy_baseline_iou,
        "final_model_iou": model_iou,
        "margin_over_copy": model_iou - copy_baseline_iou,
        "beats_copy_baseline": model_iou > copy_baseline_iou,
        "best_params": best_params,
        "test_metrics": test_results,
        "selected_channels": selected_channels,
        "retrain_epochs": len(retrain_history),
    }
    (OUT_DIR / "final_report.json").write_text(json.dumps(summary, indent=2, default=str))

    log_msg(f"\nPipeline complete in {(time.time()-START_TIME)/3600:.1f}h", log_path)
    return summary


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        traceback.print_exc()
        with open("../research_log.txt", "a") as f:
            f.write(f"\nFATAL ERROR: {e}\n{traceback.format_exc()}\n")