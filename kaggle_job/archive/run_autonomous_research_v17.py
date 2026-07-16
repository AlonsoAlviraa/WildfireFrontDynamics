#!/usr/bin/env python3
"""Autonomous Wildfire Segmentation Research Pipeline v17c — MEGA NIGHT EDITION.

BULLETPROOF version: Every step has fallbacks, error handling, and logging.
Uses repo's proven preprocess_ndws.py instead of inlined parser.

Pipeline:
  0: Data preprocessing (repo script) + feature analysis
  1: Copy baseline
  2: Optuna sweep (~14h, 40 trials)
  3: Full retraining
  4: Production export
"""

import os
import sys
import subprocess
import json
import time
import random
import hashlib
import warnings
import traceback
from pathlib import Path
from datetime import datetime
from collections import defaultdict

warnings.filterwarnings("ignore")

# =================================================================== #
# CONFIG — all paths and constants up front
# =================================================================== #
KAGGLE_WORK = Path("/kaggle/working")
DATA_ROOT = Path("/tmp/ndws_npz")
OUT_DIR = KAGGLE_WORK  # Write outputs directly to /kaggle/working/
MAX_HOURS = 16.0
SEED = 42
START_TIME = time.time()

# =================================================================== #
# LOGGING — write to /kaggle/working/ immediately
# =================================================================== #
LOG_FILE = OUT_DIR / "research_log.txt"

def log(msg):
    """Log message to both stdout and file."""
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

log("=" * 80)
log("AUTONOMOUS WILDFIRE RESEARCH PIPELINE v17d — MEGA NIGHT")
log("=" * 80)
log(f"Start time: {datetime.now().isoformat()}")
log(f"Max hours: {MAX_HOURS}")
log(f"Output dir: {OUT_DIR}")

# =================================================================== #
# 0. GPU CHECK + PyTorch COMPATIBILITY FIX (before import torch)
# =================================================================== #
sys.path.insert(0, str(Path(__file__).resolve().parent))
from kaggle_common import (  # noqa: E402
    install_pytorch_p100_compat,
    run_preprocess_ndws,
    validate_dataset_sizes,
)

install_pytorch_p100_compat()

# =================================================================== #
# IMPORTS — after PyTorch fix
# =================================================================== #
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader

log(f"PyTorch version: {torch.__version__}")

random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)
if torch.cuda.is_available():
    torch.cuda.manual_seed_all(SEED)
    torch.backends.cudnn.benchmark = True

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
USE_AMP = DEVICE.type == "cuda"

if torch.cuda.is_available():
    log(f"GPU: {torch.cuda.get_device_name(0)}")
    cap = torch.cuda.get_device_capability(0)
    log(f"Compute capability: sm_{cap[0]}{cap[1]}")
else:
    log("WARNING: No GPU available! Running on CPU.")
log(f"Device: {DEVICE} | AMP: {USE_AMP}")

# Install optuna
try:
    import optuna
except ImportError:
    log("Installing optuna...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "optuna"],
                   check=True, timeout=120)
    import optuna
optuna.logging.set_verbosity(optuna.logging.WARNING)

# =================================================================== #
# 1. CLONE REPO + PREPROCESS DATA
# =================================================================== #
REPO_DIR = Path("WildfireFrontDynamics")

if not REPO_DIR.exists():
    log("Cloning repository...")
    subprocess.run(
        ["git", "clone", "--depth", "1",
         "https://github.com/AlonsoAlviraa/WildfireFrontDynamics.git"],
        check=True, timeout=120
    )

os.chdir(str(REPO_DIR))
sys.path.insert(0, os.getcwd())
log(f"Working directory: {os.getcwd()}")

# =================================================================== #
# 1b. PREPROCESS DATA (repo preprocess_ndws.py — proven in v14-v16)
# =================================================================== #
try:
    total_patches = run_preprocess_ndws(DATA_ROOT, min_total=100, log=log)
    log(f"Data ready: {total_patches} patches total")
except Exception as e:
    log(f"FATAL: Data preprocessing failed: {e}")
    log(traceback.format_exc())
    sys.exit(1)


# =================================================================== #
# 2. DATASET
# =================================================================== #
class WildfireDataset(Dataset):
    def __init__(self, directory, augment=False, selected_channels=None):
        self.directory = Path(directory)
        self.files = sorted(self.directory.glob("*.npz"))
        if len(self.files) == 0:
            raise RuntimeError(f"No .npz files in {directory}")
        self.augment = augment
        self.selected_channels = selected_channels
        self._fps = self._fingerprints()

    def _fingerprints(self):
        fps = []
        for f in self.files:
            try:
                with np.load(f) as d:
                    fps.append(hashlib.md5(d["current_fire"].tobytes()).hexdigest()[:8])
            except Exception:
                fps.append("err")
        return fps

    def __len__(self):
        return len(self.files)

    def __getitem__(self, idx):
        with np.load(self.files[idx]) as d:
            seq = np.where(np.isfinite(d["sequence"]),
                          d["sequence"].astype(np.float32), 0.0)
            cf = d["current_fire"].astype(np.float32)
            tf_mask = d["target_fire"].astype(np.float32)

        if self.selected_channels is not None:
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
    """(B,T,C,H,W) -> (B,T*C+1,H,W)"""
    B, T, C, H, W = seq.shape
    flat = seq.reshape(B, T * C, H, W)
    fire = cf.unsqueeze(1)
    return torch.cat([flat, fire], dim=1)


# =================================================================== #
# 3. LOSS FUNCTIONS
# =================================================================== #
class FocalLoss(nn.Module):
    def __init__(self, alpha=0.75, gamma=2.0, pos_weight=5.0):
        super().__init__()
        self.alpha, self.gamma, self.pos_weight = alpha, gamma, pos_weight

    def forward(self, logits, targets):
        logits = torch.clamp(logits, -10, 10)
        pw = torch.tensor(self.pos_weight, device=logits.device)
        bce = F.binary_cross_entropy_with_logits(
            logits, targets, reduction="none", pos_weight=pw)
        p = torch.sigmoid(logits)
        p_t = p * targets + (1 - p) * (1 - targets)
        return (self.alpha * ((1 - p_t) ** self.gamma) * bce).mean()


class TverskyLoss(nn.Module):
    def __init__(self, alpha=0.3, beta=0.7, smooth=1e-7):
        super().__init__()
        self.alpha, self.beta, self.smooth = alpha, beta, smooth

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
        inter = (probs * targets).sum(dim=[1, 2, 3])
        union = probs.sum(dim=[1, 2, 3]) + targets.sum(dim=[1, 2, 3])
        return (1 - (2 * inter + self.smooth) / (union + self.smooth)).mean()


class CompositeLoss(nn.Module):
    def __init__(self, w_focal=1.0, w_tversky=0.5, w_dice=0.5, w_bce=0.5,
                 pos_weight=5.0, gamma=2.0):
        super().__init__()
        self.focal = FocalLoss(0.75, gamma, pos_weight)
        self.tversky = TverskyLoss()
        self.dice = DiceLoss()
        self.w_focal, self.w_tversky = w_focal, w_tversky
        self.w_dice, self.w_bce = w_dice, w_bce
        self.pos_weight = pos_weight

    def forward(self, logits, targets):
        pw = torch.tensor(self.pos_weight, device=logits.device)
        bce = F.binary_cross_entropy_with_logits(logits, targets, pos_weight=pw)
        return (self.w_focal * self.focal(logits, targets)
                + self.w_tversky * self.tversky(logits, targets)
                + self.w_dice * self.dice(logits, targets)
                + self.w_bce * bce)


# =================================================================== #
# 4. ATTENTION + MODEL
# =================================================================== #
class SEBlock(nn.Module):
    def __init__(self, ch, r=8):
        super().__init__()
        self.sq = nn.AdaptiveAvgPool2d(1)
        self.ex = nn.Sequential(
            nn.Linear(ch, max(ch // r, 4), bias=False), nn.ReLU(inplace=True),
            nn.Linear(max(ch // r, 4), ch, bias=False), nn.Sigmoid())
    def forward(self, x):
        b, c = x.shape[:2]
        return x * self.ex(self.sq(x).view(b, c)).view(b, c, 1, 1)


class CBAM(nn.Module):
    def __init__(self, ch, r=8):
        super().__init__()
        self.avg, self.maxp = nn.AdaptiveAvgPool2d(1), nn.AdaptiveMaxPool2d(1)
        self.mlp = nn.Sequential(
            nn.Conv2d(ch, max(ch // r, 4), 1, bias=False), nn.ReLU(inplace=True),
            nn.Conv2d(max(ch // r, 4), ch, 1, bias=False))
        self.spatial = nn.Conv2d(2, 1, 7, padding=3, bias=False)
    def forward(self, x):
        ca = torch.sigmoid(self.mlp(self.avg(x)) + self.mlp(self.maxp(x)))
        x = x * ca
        sa = torch.sigmoid(self.spatial(
            torch.cat([x.mean(1, keepdim=True), x.max(1, keepdim=True)[0]], dim=1)))
        return x * sa


class DoubleConv(nn.Module):
    def __init__(self, in_ch, out_ch, mid_ch=None, norm="group", attention=None):
        super().__init__()
        mid = mid_ch if mid_ch is not None else out_ch
        nf = lambda c: nn.GroupNorm(8, c) if norm == "group" else nn.BatchNorm2d(c)
        self.body = nn.Sequential(
            nn.Conv2d(in_ch, mid, 3, padding=1, bias=False), nf(mid), nn.ReLU(inplace=True),
            nn.Conv2d(mid, out_ch, 3, padding=1, bias=False), nf(out_ch), nn.ReLU(inplace=True))
        if attention == "cbam": self.att = CBAM(out_ch)
        elif attention == "se": self.att = SEBlock(out_ch)
        else: self.att = nn.Identity()
    def forward(self, x): return self.att(self.body(x))


class DownBlock(nn.Module):
    def __init__(self, i, o, **kw):
        super().__init__()
        self.p = nn.Sequential(nn.MaxPool2d(2), DoubleConv(i, o, **kw))
    def forward(self, x): return self.p(x)


class UpBlock(nn.Module):
    def __init__(self, i, o, bil=True, **kw):
        super().__init__()
        if bil:
            self.up = nn.Upsample(scale_factor=2, mode="bilinear", align_corners=True)
            self.conv = DoubleConv(i, o, mid_ch=i // 2, **kw)
        else:
            self.up = nn.ConvTranspose2d(i, i // 2, 2, 2)
            self.conv = DoubleConv(i, o, **kw)
    def forward(self, x1, x2):
        x1 = self.up(x1)
        dy, dx = x2.size(2) - x1.size(2), x2.size(3) - x1.size(3)
        x1 = F.pad(x1, [dx // 2, dx - dx // 2, dy // 2, dy - dy // 2])
        return self.conv(torch.cat([x2, x1], dim=1))


class ResidualWildfireUNet(nn.Module):
    """U-Net that predicts DELTA over copy baseline."""
    def __init__(self, in_channels=12, base_ch=32, depth=3, bilinear=True,
                 norm="group", attention="cbam", dropout=0.1):
        super().__init__()
        kw = dict(norm=norm, attention=attention)
        self.inc = DoubleConv(in_channels, base_ch, **kw)
        self.downs, self.ups = nn.ModuleList(), nn.ModuleList()
        ch = base_ch
        for _ in range(depth):
            nc = min(ch * 2, 512)
            self.downs.append(DownBlock(ch, nc, **kw))
            ch = nc
        for i in range(depth):
            oc = max(base_ch * (2 ** (depth - i - 1)), base_ch)
            self.ups.append(UpBlock(ch, oc, bilinear, **kw))
            ch = oc
        self.drop = nn.Dropout2d(dropout) if dropout > 0 else nn.Identity()
        self.outc = nn.Conv2d(ch, 1, 1)
        self.delta_scale = nn.Parameter(torch.tensor(1.0))
        self.copy_bias = nn.Parameter(torch.tensor(2.0))

    def forward(self, x, prev_fire):
        x1 = self.inc(x)
        skips = [x1]
        for d in self.downs:
            x1 = d(x1)
            skips.append(x1)
        for u, s in zip(self.ups, reversed(skips[:-1])):
            x1 = u(x1, s)
        delta = self.outc(self.drop(x1))
        return self.delta_scale * delta + self.copy_bias * (prev_fire * 2 - 1)


# =================================================================== #
# 5. EVALUATION
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
    all_preds, all_targets, copy_ious = [], [], []
    for seq, cf, tf_mask in loader:
        seq, cf, tf_mask = seq.to(device), cf.to(device), tf_mask.to(device)
        x = prepare_input(seq, cf)
        tgt = tf_mask.unsqueeze(1).float()
        logits = model(x, cf.unsqueeze(1))
        probs = torch.sigmoid(logits)
        all_preds.append(probs.cpu().numpy())
        all_targets.append(tgt.cpu().numpy())
        cf_np, tf_np = cf.unsqueeze(1).cpu().numpy(), tgt.cpu().numpy()
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
# 6. FEATURE ANALYSIS
# =================================================================== #
def analyze_features(ds, max_n=500):
    log("\n=== FEATURE IMPORTANCE ANALYSIS ===")
    scores = defaultdict(list)
    for i in range(min(len(ds), max_n)):
        seq, cf, tf_mask = ds[i]
        T, C, H, W = seq.shape
        tf_flat = (tf_mask >= 0.5).numpy().flatten().astype(int)
        for ci in range(C):
            ch = seq[0, ci].numpy().flatten()
            if np.std(ch) < 1e-6 or np.std(tf_flat) < 1e-6:
                scores[ci].append(0.0)
                continue
            r = np.corrcoef(ch, tf_flat)[0, 1]
            scores[ci].append(abs(r) if np.isfinite(r) else 0.0)

    names = [f"ch{ci}" for ci in range(max(C, 20) if 'C' in dir() else 20)]
    ranked = sorted([(ci, float(np.mean(s))) for ci, s in scores.items()],
                    key=lambda x: x[1], reverse=True)
    for ci, score in ranked:
        log(f"  ch{ci:2d}: {score:.4f} {'#' * int(score * 200)}")

    total = sum(r[1] for r in ranked) + 1e-7
    cumulative, selected = 0, []
    for ci, score in ranked:
        cumulative += score
        selected.append(ci)
        if cumulative / total > 0.95:
            break
    log(f"  Selected {len(selected)}/{len(ranked)} channels")
    return selected


# =================================================================== #
# 7. AMP HELPERS (PyTorch 2.1.x compatible)
# =================================================================== #
def make_scaler():
    if USE_AMP:
        return torch.cuda.amp.GradScaler()
    return torch.cuda.amp.GradScaler(enabled=False)

def autocast_ctx():
    if USE_AMP:
        return torch.cuda.amp.autocast()
    return torch.cuda.amp.autocast(enabled=False)


# =================================================================== #
# 8. OPTUNA OBJECTIVE
# =================================================================== #
def create_objective(train_ds, val_ds, device, in_channels):
    def objective(trial):
        if time.time() - START_TIME > MAX_HOURS * 3600 - 1800:
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
            in_channels=in_channels, base_ch=cfg["base_ch"], depth=cfg["depth"],
            norm=cfg["norm"], attention=att, dropout=cfg["dropout"]
        ).to(device)
        trial.set_user_attr("n_params", sum(p.numel() for p in model.parameters()))

        criterion = CompositeLoss(
            cfg["w_focal"], cfg["w_tversky"], cfg["w_dice"], cfg["w_bce"],
            cfg["pos_weight"], cfg["focal_gamma"]
        ).to(device)

        opt = torch.optim.AdamW(model.parameters(), lr=cfg["lr"], weight_decay=1e-4)
        sch = torch.optim.lr_scheduler.CosineAnnealingWarmRestarts(opt, T_0=5, T_mult=2, eta_min=1e-6)
        scaler = make_scaler()

        tl = DataLoader(train_ds, batch_size=cfg["batch_size"], shuffle=True,
                       num_workers=2, pin_memory=True, drop_last=True)
        vl = DataLoader(val_ds, batch_size=cfg["batch_size"], shuffle=False,
                       num_workers=2, pin_memory=True)

        best_iou, no_imp = 0.0, 0
        for ep in range(cfg["epochs"]):
            if time.time() - START_TIME > MAX_HOURS * 3600 - 1800:
                break
            model.train()
            for seq, cf, tf_mask in tl:
                seq, cf, tf_mask = seq.to(device), cf.to(device), tf_mask.to(device)
                x = prepare_input(seq, cf)
                tgt = tf_mask.unsqueeze(1).float()
                opt.zero_grad()
                with autocast_ctx():
                    logits = model(x, cf.unsqueeze(1))
                    loss = criterion(logits, tgt)
                scaler.scale(loss).backward()
                scaler.unscale_(opt)
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                scaler.step(opt)
                scaler.update()
            sch.step()

            vr = evaluate_model(model, vl, device)
            vi = vr.get("iou@0.5", 0.0)
            trial.report(vi, ep)
            if trial.should_prune():
                raise optuna.TrialPruned()
            if vi > best_iou:
                best_iou = vi
                no_imp = 0
            else:
                no_imp += 1
                if no_imp >= 5:
                    break

        trial.set_user_attr("copy_baseline_iou", vr.get("copy_baseline_iou", 0.0))
        return best_iou
    return objective


# =================================================================== #
# 9. MAIN PIPELINE
# =================================================================== #
def main():
    # ---- PHASE 0 ----
    log("\n=== PHASE 0: Data + Feature Analysis ===")
    for split in ("train", "val", "test"):
        n = len(list((DATA_ROOT / split).glob("*.npz")))
        if n == 0:
            raise RuntimeError(f"Empty split '{split}' — preprocessing failed")
    train_ds = WildfireDataset(DATA_ROOT / "train", augment=True)
    val_ds = WildfireDataset(DATA_ROOT / "val", augment=False)
    test_ds = WildfireDataset(DATA_ROOT / "test", augment=False)
    log(f"Dataset: train={len(train_ds)} val={len(val_ds)} test={len(test_ds)}")

    tv_ov = len(set(train_ds._fps) & set(val_ds._fps))
    tt_ov = len(set(train_ds._fps) & set(test_ds._fps))
    log(f"Anti-leakage: train-val={tv_ov}, train-test={tt_ov}")

    selected_ch = analyze_features(train_ds)

    train_ds_p = WildfireDataset(DATA_ROOT / "train", augment=True, selected_channels=selected_ch)
    val_ds_p = WildfireDataset(DATA_ROOT / "val", augment=False, selected_channels=selected_ch)
    test_ds_p = WildfireDataset(DATA_ROOT / "test", augment=False, selected_channels=selected_ch)

    sample_seq, _, _ = train_ds_p[0]
    in_ch = sample_seq.shape[0] * sample_seq.shape[1] + 1
    log(f"Input channels (pruned): {in_ch}")

    # ---- PHASE 1: Copy Baseline ----
    log("\n=== PHASE 1: Copy Baseline ===")
    test_loader = DataLoader(test_ds_p, batch_size=32, shuffle=False, num_workers=2)
    copy_ious = []
    for _, cf, tf_mask in test_loader:
        cf_np, tf_np = cf.unsqueeze(1).numpy(), tf_mask.unsqueeze(1).numpy()
        for i in range(cf_np.shape[0]):
            copy_ious.append(compute_iou(cf_np[i, 0:1], tf_np[i], 0.5))
    copy_iou = float(np.mean(copy_ious))
    log(f"Copy baseline IoU@0.5: {copy_iou:.4f}")

    # ---- PHASE 2: Optuna Sweep ----
    sweep_budget = MAX_HOURS * 3600 - (time.time() - START_TIME) - 2.0 * 3600
    log(f"\n=== PHASE 2: Optuna Sweep ({sweep_budget/3600:.1f}h) ===")
    study = optuna.create_study(
        direction="maximize",
        pruner=optuna.pruners.MedianPruner(n_startup_trials=3, n_warmup_steps=5),
        sampler=optuna.samplers.TPESampler(seed=SEED))
    try:
        study.optimize(
            create_objective(train_ds_p, val_ds_p, DEVICE, in_ch),
            n_trials=40, timeout=sweep_budget, catch=(Exception,))
    except Exception as e:
        log(f"Sweep error: {e}")

    log(f"Sweep: {len(study.trials)} trials")
    if study.best_trial:
        log(f"Best sweep IoU: {study.best_value:.4f}")
        bp = study.best_params
        bp["n_params"] = study.best_trial.user_attrs.get("n_params", 0)
        (OUT_DIR / "best_params.json").write_text(json.dumps(bp, indent=2, default=str))
    else:
        log("No valid trials — using defaults")
        bp = {"base_ch": 32, "depth": 3, "attention": "cbam", "norm": "group",
              "dropout": 0.1, "lr": 1e-3, "batch_size": 32,
              "w_focal": 1.0, "w_tversky": 0.5, "w_dice": 0.5, "w_bce": 0.5,
              "pos_weight": 5.0, "focal_gamma": 2.0, "epochs": 30}

    # ---- PHASE 3: Full Retraining ----
    log("\n=== PHASE 3: Full Retraining ===")
    att = None if bp.get("attention") == "none" else bp.get("attention")
    bm = ResidualWildfireUNet(
        in_channels=in_ch, base_ch=bp["base_ch"], depth=bp["depth"],
        norm=bp["norm"], attention=att, dropout=bp["dropout"]
    ).to(DEVICE)
    crit = CompositeLoss(bp["w_focal"], bp["w_tversky"], bp["w_dice"], bp["w_bce"],
                         bp["pos_weight"], bp["focal_gamma"]).to(DEVICE)
    opt = torch.optim.AdamW(bm.parameters(), lr=bp["lr"], weight_decay=1e-4)
    sch = torch.optim.lr_scheduler.CosineAnnealingWarmRestarts(opt, T_0=5, T_mult=2, eta_min=1e-6)
    scaler = make_scaler()
    tl = DataLoader(train_ds_p, batch_size=bp["batch_size"], shuffle=True,
                   num_workers=4, pin_memory=True, drop_last=True)
    vl = DataLoader(val_ds_p, batch_size=bp["batch_size"], shuffle=False,
                   num_workers=4, pin_memory=True)

    best_val, hist = 0.0, []
    for ep in range(50):
        if time.time() - START_TIME > MAX_HOURS * 3600 - 1800:
            log(f"Time budget at epoch {ep+1}")
            break
        bm.train()
        el, st, t0 = 0.0, 0, time.time()
        for seq, cf, tf_mask in tl:
            seq, cf, tf_mask = seq.to(DEVICE), cf.to(DEVICE), tf_mask.to(DEVICE)
            x = prepare_input(seq, cf)
            tgt = tf_mask.unsqueeze(1).float()
            opt.zero_grad()
            with autocast_ctx():
                logits = bm(x, cf.unsqueeze(1))
                loss = crit(logits, tgt)
            scaler.scale(loss).backward()
            scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(bm.parameters(), 1.0)
            scaler.step(opt)
            scaler.update()
            el += loss.item()
            st += 1
        sch.step()
        vr = evaluate_model(bm, vl, DEVICE)
        vi = vr.get("iou@0.5", 0.0)
        log(f"  Ep {ep+1}: loss={el/st:.4f} val_iou={vi:.4f} copy={vr.get('copy_baseline_iou',0):.4f} ({time.time()-t0:.0f}s)")
        hist.append({"epoch": ep+1, "train_loss": el/st, "val_iou": vi})
        if vi > best_val:
            best_val = vi
            torch.save(bm.state_dict(), OUT_DIR / "best_model.pt")
            log(f"    -> new best!")

    (OUT_DIR / "retrain_history.json").write_text(json.dumps(hist, indent=2))

    # ---- PHASE 4: Export ----
    log("\n=== PHASE 4: Production Export ===")
    if (OUT_DIR / "best_model.pt").exists():
        bm.load_state_dict(torch.load(OUT_DIR / "best_model.pt", map_location=DEVICE))
    tr = evaluate_model(bm, test_loader, DEVICE)
    miou = tr.get("iou@0.5", 0.0)
    log(f"\n{'='*50}")
    log(f"FINAL: Model IoU={miou:.4f} | Copy={copy_iou:.4f} | Margin={miou-copy_iou:+.4f}")
    log(f"Beats copy: {'YES' if miou > copy_iou else 'NO'}")
    log(f"{'='*50}")

    try:
        bm.eval()
        scripted = torch.jit.script(bm)
        scripted.save(str(OUT_DIR / "wildfire_model_production.pt"))
        log("TorchScript exported")
    except Exception as e:
        log(f"TorchScript failed ({e})")
        torch.save(bm.state_dict(), OUT_DIR / "wildfire_model_production.pt")

    summary = {
        "version": "v17c", "pipeline": "autonomous_research_mega_night",
        "timestamp": datetime.now().isoformat(),
        "runtime_s": time.time() - START_TIME,
        "n_trials": len(study.trials),
        "best_sweep_iou": float(study.best_value) if study.best_trial else 0.0,
        "copy_baseline_iou": copy_iou,
        "final_model_iou": miou,
        "margin_over_copy": miou - copy_iou,
        "beats_copy": miou > copy_iou,
        "best_params": bp,
        "test_metrics": tr,
        "selected_channels": selected_ch,
    }
    (OUT_DIR / "final_report.json").write_text(json.dumps(summary, indent=2, default=str))
    log(f"\nPipeline complete in {(time.time()-START_TIME)/3600:.1f}h")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"\nFATAL ERROR: {e}")
        log(traceback.format_exc())
        sys.exit(1)