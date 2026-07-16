#!/usr/bin/env python3
"""Mega training pipeline — LEAK-FREE edition.

This script runs entirely inside a Kaggle GPU notebook/script. It performs:

1. Clone repo + preprocess NDWS into 3 DISJOINT splits (train/val/test).
2. Pre-train A3C-LSTM on train, validate on val (early stopping + best ckpt).
3. Fine-tune on local tactical dataset (optional).
4. Train meta-labeler on VAL predictions, evaluate on TEST (unseen).
5. Save all artifacts.

Leak guarantees
----------------
- Train / val / test TFRecord shards are DISJOINT (see ``preprocess_ndws.py``).
- The meta-labeler is NEVER evaluated on the same data it was trained on.
- The TEST split is touched exactly once, at the very end, for honest metrics.
"""

import os
import sys
import subprocess
import json
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

# --------------------------------------------------------------------------- #
# 1. Clone repository + install deps
# --------------------------------------------------------------------------- #
print("=" * 70)
print("WILDFIRE MEGA TRAINING — LEAK-FREE EDITION")
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
# 2. Preprocess all three disjoint splits
# --------------------------------------------------------------------------- #
print("\n=== FASE 1: PREPROCESAMIENTO TFRECORDS (train / val / test) ===")
preprocess_script = "kaggle_job/preprocess_ndws.py"
for split in ["train", "val", "test"]:
    print(f"\n--- Preprocessing split: {split} ---")
    subprocess.run([sys.executable, preprocess_script, "--split", split], check=True)

# --------------------------------------------------------------------------- #
# 3. Imports & data loaders
# --------------------------------------------------------------------------- #
from models.model import A3C_PerCellModel_LSTM
from wildfire_front.ml.dataset import NpzWildfireDataset, WildfireDataset
from wildfire_front.ml.meta_labeler import WildfireMetaLabeler
from wildfire_front.ml.train import (
    calculate_local_spread_loss,
    calculate_local_spread_loss_vectorized,
)
from wildfire_front.ml.weights import load_pretrained_weights

train_dir = "/tmp/ndws_npz/train"
val_dir = "/tmp/ndws_npz/val"
test_dir = "/tmp/ndws_npz/test"

train_dataset = NpzWildfireDataset(train_dir, augment=True)  # Sprint 3.2: data augmentation
val_dataset = NpzWildfireDataset(val_dir, augment=False)
test_dataset = NpzWildfireDataset(test_dir, augment=False)

print(f"\nDataset sizes -> train={len(train_dataset)}  val={len(val_dataset)}  test={len(test_dataset)}")
if len(test_dataset) == 0:
    raise SystemExit("TEST split is empty — cannot guarantee leak-free evaluation. Aborting.")

# IMPORTANT: The A3C per-cell model iterates cell-by-cell and asserts batch=1.
# DataParallel/batch>1 are NOT compatible with this architecture.
# Instead, we use AMP (Automatic Mixed Precision) + cudnn.benchmark for speedup.
N_GPUS = torch.cuda.device_count() if torch.cuda.is_available() else 0
BATCH_SIZE = 1  # MUST be 1 — model architecture requires it
print(f"GPU setup: {N_GPUS} GPU(s) detected, batch_size={BATCH_SIZE} (per-cell model requires bs=1)")
print(f"Using AMP mixed precision + cudnn.benchmark for speedup")

# Enable cudnn autotuner — picks fastest conv kernels for fixed input shapes
if torch.cuda.is_available():
    torch.backends.cudnn.benchmark = True

# v7: Increased workers (4->8) + persistent_workers + prefetch_factor
# for maximal GPU feeding throughput with vectorized loss.
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
# Robust device selection: verify GPU compute-capability is supported by PyTorch
# --------------------------------------------------------------------------- #
def _select_device():
    """Pick a usable GPU (checking sm compatibility) or fall back to CPU.

    Kaggle may assign a Tesla P100 (sm_60) which is NOT supported by recent
    PyTorch builds (min sm_70).  We probe with a tiny op and fall back to CPU
    so the job always completes instead of crashing.
    """
    if not torch.cuda.is_available():
        print("CUDA not available — using CPU.")
        return torch.device("cpu")
    cap = torch.cuda.get_device_capability(0)
    name = torch.cuda.get_device_name(0)
    print(f"GPU detected: {name} (compute capability sm_{cap[0]}{cap[1]})")
    # Probe with a tiny operation to confirm kernels actually run.
    try:
        probe = torch.zeros(8, device="cuda")
        _ = (probe @ probe).sum().item()  # forces a real kernel launch
        if cap[0] < 7:
            raise RuntimeError(f"sm_{cap[0]}{cap[1]} < sm_70 — not supported by this PyTorch build")
        print(f"GPU kernel probe OK — using cuda ({name}).")
        return torch.device("cuda")
    except Exception as exc:  # noqa: BLE001
        print(f"WARNING: GPU unusable ({exc}). Falling back to CPU — training will be slow.")
        return torch.device("cpu")


device = _select_device()
print(f"Using device: {device}")

# --------------------------------------------------------------------------- #
# 4. Model + backward-compatible weight loading
# --------------------------------------------------------------------------- #
model = A3C_PerCellModel_LSTM(in_channels=17, lstm_hidden=256, sequence_length=3)
pretrained_base = Path("models/v3.pt")
if pretrained_base.exists():
    print(f"\nLoading base weights from {pretrained_base} (non-strict, v1->v2 remap)...")
    load_pretrained_weights(model, pretrained_base)
else:
    print(f"\nWARNING: {pretrained_base} not found (likely .gitignored). Training from scratch.")
    print("  Pre-trained conv/LSTM weights will be initialized randomly.")
model.to(device)

# AMP (Automatic Mixed Precision) — runs conv/linear ops in fp16/tf16 where safe,
# giving ~40-50% speedup on T4 GPUs without changing model semantics.
USE_AMP = device.type == "cuda"
scaler = torch.amp.GradScaler('cuda', enabled=USE_AMP)
if USE_AMP:
    print("AMP (Automatic Mixed Precision) ENABLED — fp16/tf16 on T4")

# --------------------------------------------------------------------------- #
# 5. FASE 2: Pre-training on NDWS train split with validation-based selection
# --------------------------------------------------------------------------- #
print("\n=== FASE 2: PRE-ENTRENAMIENTO MASIVO (NDWS train) ===")
# Focal loss + pos_weight is now built into calculate_local_spread_loss (train.py).
# This penalizes false negatives 3x more than false positives → higher recall.
# v11: LR peak reducido a 5e-5 (la mitad) para evitar oscilaciones post-warmup
#      que causaban early stopping prematuro en epoch 3.
PEAK_LR = float(os.environ.get("WF_PEAK_LR", "5e-5"))
optimizer = torch.optim.AdamW(model.parameters(), lr=PEAK_LR, weight_decay=3e-4)

from torch.optim.lr_scheduler import CosineAnnealingLR, LinearLR, SequentialLR

EPOCHS = int(os.environ.get("WF_EPOCHS", "50"))  # nocturno: 50 epochs
WARMUP_EPOCHS = 5  # v11: warmup más largo (3→5) para estabilizar gradientes
GRAD_ACCUM_STEPS = 4  # simulate batch_size=4 via gradient accumulation
patience = 12  # v11: más paciencia (8→12) para dar tiempo al cosine decay

# v12: Warmup start más bajo (0.01 en lugar de 0.1) para proteger pesos v3.pt
warmup_scheduler = LinearLR(optimizer, start_factor=0.01, total_iters=WARMUP_EPOCHS)
cosine_scheduler = CosineAnnealingLR(optimizer, T_max=EPOCHS - WARMUP_EPOCHS, eta_min=1e-6)
scheduler = SequentialLR(
    optimizer,
    schedulers=[warmup_scheduler, cosine_scheduler],
    milestones=[WARMUP_EPOCHS],
)

# --- AUTO-RESUME from last checkpoint (nocturno: survives interruptions) ---
RESUME_CKPT = Path("../weights_pretrained_best.pt")
RESUME_META = Path("../training_state.json")
start_epoch = 0
best_val_loss = float("inf")
best_epoch = -1
no_improve = 0
history = []

# v12: FREEZE conv layers during warmup to protect pre-trained v3.pt features
# Solo entrenar LSTM + policy head durante las primeras WARMUP_EPOCHS
FREEZE_CONV_EPOCHS = WARMUP_EPOCHS  # Congelar conv durante todo el warmup
conv_frozen = False


def freeze_conv_layers(model, freeze: bool):
    """Freeze/unfreeze conv1/conv2/conv3 to protect pre-trained features."""
    global conv_frozen
    for name in ["conv1", "conv2", "conv3"]:
        if hasattr(model, name):
            layer = getattr(model, name)
            for param in layer.parameters():
                param.requires_grad = not freeze
    conv_frozen = freeze
    n_trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    status = "FROZEN" if freeze else "UNFROZEN"
    print(f"  Conv layers {status} — {n_trainable:,} trainable params")


# v12: Freeze conv layers at start to protect v3.pt features
freeze_conv_layers(model, freeze=True)

if RESUME_CKPT.exists() and RESUME_META.exists():
    try:
        state = json.loads(RESUME_META.read_text())
        start_epoch = state.get("epoch", 0)
        best_val_loss = state.get("best_val_loss", float("inf"))
        best_epoch = state.get("best_epoch", -1)
        no_improve = state.get("no_improve", 0)
        history = state.get("history", [])
        model.load_state_dict(torch.load(RESUME_CKPT, map_location=device))
        # Advance scheduler to the right epoch
        for _ in range(start_epoch):
            scheduler.step()
        print(f"AUTO-RESUME: starting at epoch {start_epoch+1}/{EPOCHS}, "
              f"best_val_loss={best_val_loss:.5f} (epoch {best_epoch})")
    except Exception as exc:
        print(f"AUTO-RESUME: failed to load state ({exc}), starting from scratch")
        start_epoch = 0
else:
    print("No previous checkpoint found — starting training from scratch")


@torch.no_grad()
def evaluate_loss(model, loader, device):
    model.eval()
    total, steps = 0.0, 0
    for sequence, current_fire, target_fire in loader:
        sequence = sequence.to(device)
        current_fire = current_fire.to(device)
        target_fire = target_fire.to(device)
        # Forward in AMP (fp16), loss computed in fp32 to avoid NaN
        with torch.amp.autocast('cuda', enabled=USE_AMP):
            features, _ = model.forward(sequence, current_fire)
        features = features.float()  # cast back to fp32 for stable loss
        loss = calculate_local_spread_loss_vectorized(model, features, current_fire, target_fire, sequence=sequence)
        if loss is not None:
            total += loss.item()
            steps += 1
    model.train()
    return total / steps if steps else 0.0


# --- NaN DETECTION COUNTERS (v8 NaN-fix) ---
nan_skipped_batches = 0
total_batches_seen = 0

# --- Logging setup (nocturno: append to file for long runs) ---
LOG_FILE = Path("../training_log.txt")
def log_msg(msg):
    print(msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

log_msg(f"\n--- Training run started at {time.strftime('%Y-%m-%d %H:%M:%S')} ---")
log_msg(f"Config: EPOCHS={EPOCHS}, WARMUP={WARMUP_EPOCHS}, GRAD_ACCUM={GRAD_ACCUM_STEPS}, "
        f"patience={patience}, AMP={USE_AMP}")

for epoch in range(start_epoch, EPOCHS):
    # v12: Unfreeze conv layers after warmup
    if conv_frozen and epoch >= FREEZE_CONV_EPOCHS:
        freeze_conv_layers(model, freeze=False)
    model.train()
    epoch_loss, steps = 0.0, 0
    accum_count = 0
    optimizer.zero_grad()
    t0 = time.time()
    for sequence, current_fire, target_fire in train_loader:
        total_batches_seen += 1
        sequence = sequence.to(device)
        current_fire = current_fire.to(device)
        target_fire = target_fire.to(device)

        # --- INPUT NaN GUARD: skip batches with corrupted data ---
        if torch.isnan(sequence).any() or torch.isinf(sequence).any():
            nan_skipped_batches += 1
            continue

        # Forward in AMP (fp16) for speed, loss in fp32 for stability
        with torch.amp.autocast('cuda', enabled=USE_AMP):
            features, _ = model.forward(sequence, current_fire)
        features = features.float()  # CRITICAL: cast to fp32 before loss

        # --- FEATURES NaN GUARD: skip if forward pass produced NaN ---
        if torch.isnan(features).any() or torch.isinf(features).any():
            nan_skipped_batches += 1
            if nan_skipped_batches <= 5:
                log_msg(f"  WARNING: NaN/Inf in features at batch {total_batches_seen}, skipping")
            continue

        loss = calculate_local_spread_loss_vectorized(model, features, current_fire, target_fire, sequence=sequence)

        if loss is not None and not torch.isnan(loss) and not torch.isinf(loss):
            # --- GRADIENT ACCUMULATION (simulate batch_size=4) ---
            # Divide loss by accum steps, backward without zeroing grad
            scaler.scale(loss / GRAD_ACCUM_STEPS).backward()
            accum_count += 1
            epoch_loss += loss.item()
            steps += 1

            # Every GRAD_ACCUM_STEPS: step optimizer + zero grad
            if accum_count >= GRAD_ACCUM_STEPS:
                scaler.unscale_(optimizer)
                # v12: gradient clipping más agresivo (0.5 → 0.3)
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=0.3)
                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad()
                accum_count = 0
        elif loss is not None:
            nan_skipped_batches += 1

    # Flush remaining accumulated gradients at epoch end
    if accum_count > 0:
        scaler.unscale_(optimizer)
        # v12: gradient clipping más agresivo (0.5 → 0.3)
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=0.3)
        scaler.step(optimizer)
        scaler.update()
        optimizer.zero_grad()

    scheduler.step()
    train_loss = epoch_loss / steps if steps else 0.0
    if nan_skipped_batches > 0:
        log_msg(f"  [v8 NaN-guard] Skipped {nan_skipped_batches}/{total_batches_seen} batches due to NaN/Inf")
    val_loss = evaluate_loss(model, val_loader, device)
    lr_now = scheduler.get_last_lr()[0]
    elapsed = time.time() - t0
    log_msg(f"Epoch {epoch+1:02d}/{EPOCHS}  train={train_loss:.5f}  val={val_loss:.5f}  "
            f"lr={lr_now:.2e}  ({elapsed:.0f}s)")
    history.append({"epoch": epoch + 1, "train_loss": train_loss, "val_loss": val_loss})

    # Model selection on VAL (never on test) + SAVE FULL STATE for auto-resume
    if val_loss < best_val_loss:
        best_val_loss = val_loss
        best_epoch = epoch + 1
        no_improve = 0
        torch.save(model.state_dict(), "../weights_pretrained_best.pt")
        log_msg(f"  -> new best val_loss; checkpoint saved")
    else:
        no_improve += 1
        if no_improve >= patience:
            log_msg(f"  -> early stopping at epoch {epoch+1} (no improvement {no_improve} epochs)")
            break

    # --- SAVE TRAINING STATE (auto-resume checkpoint, every epoch) ---
    # This survives Kaggle session disconnects — training can resume exactly
    # where it left off without losing progress.
    training_state = {
        "epoch": epoch + 1,
        "best_val_loss": best_val_loss,
        "best_epoch": best_epoch,
        "no_improve": no_improve,
        "history": history,
    }
    Path("../training_state.json").write_text(json.dumps(training_state, indent=2))
    Path("../training_history.json").write_text(json.dumps(history, indent=2))

# Load best checkpoint
print(f"\nLoading best checkpoint from epoch {best_epoch} (val_loss={best_val_loss:.5f})")
model.load_state_dict(torch.load("../weights_pretrained_best.pt", map_location=device))
torch.save(model.state_dict(), "../weights_pretrained.pt")
print("Pre-trained weights saved to ../weights_pretrained.pt")

# Save training history for offline analysis
Path("../training_history.json").write_text(json.dumps(history, indent=2))

# --------------------------------------------------------------------------- #
# 6. FASE 3: Transfer learning on local tactical dataset (optional)
# --------------------------------------------------------------------------- #
local_images = Path("data/candidates/semireal_controlled_001/images")
local_masks = Path("data/candidates/semireal_controlled_001/masks")
if local_images.is_dir() and local_masks.is_dir():
    print("\n=== FASE 3: TRANSFER LEARNING (dataset local) ===")
    local_dataset = WildfireDataset(local_images, local_masks, sequence_length=3, patch_size=30)
    local_loader = DataLoader(local_dataset, batch_size=1, shuffle=True)

    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-5, weight_decay=1e-4)
    model.train()
    FT_EPOCHS = 10
    for epoch in range(FT_EPOCHS):
        epoch_loss, steps = 0.0, 0
        for sequence, current_fire, target_fire in local_loader:
            sequence = sequence.to(device)
            current_fire = current_fire.to(device)
            target_fire = target_fire.to(device)
            with torch.amp.autocast('cuda', enabled=USE_AMP):
                features, _ = model.forward(sequence, current_fire)
            features = features.float()
            loss = calculate_local_spread_loss_vectorized(model, features, current_fire, target_fire, sequence=sequence)
            if loss is not None:
                optimizer.zero_grad()
                scaler.scale(loss).backward()
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=0.5)
                scaler.step(optimizer)
                scaler.update()
                epoch_loss += loss.item()
                steps += 1
        print(f"Fine-tune {epoch+1:02d}/{FT_EPOCHS}  loss={epoch_loss/steps if steps else 0:.5f}")

    torch.save(model.state_dict(), "../weights_fine_tuned.pt")
    print("Fine-tuned weights saved to ../weights_fine_tuned.pt")
else:
    print("\n=== FASE 3: SKIPPED (no local tactical dataset found) ===")

# --------------------------------------------------------------------------- #
# 7. FASE 4: Meta-labeler — train on VAL, evaluate on TEST (leak-free)
# --------------------------------------------------------------------------- #
print("\n=== FASE 4: META-LABELER (train=VAL, eval=TEST) ===")
meta_labeler = WildfireMetaLabeler(n_estimators=100, max_depth=10, random_state=42)


def collect_meta_features(model, loader, device):
    """Return (X, y) for every neighbor of every burning cell.

    v11 (Sprint 2): Uses :meth:`build_enhanced_features` with 12 features
    (base 7 + 5 spatial: prob_mean, prob_std, burning_density, prob_gradient).
    """
    model.eval()
    X_all, y_all = [], []
    with torch.no_grad():
        for sequence, current_fire, target_fire in loader:
            sequence = sequence.to(device)
            current_fire = current_fire.to(device)
            target_fire = target_fire.to(device)
            with torch.amp.autocast('cuda', enabled=USE_AMP):
                features, _ = model.forward(sequence, current_fire)
            burning_cells = model.get_burning_cells(current_fire)
            if not burning_cells:
                continue
            H, W = current_fire.shape[1], current_fire.shape[2]
            slope_grid = sequence[0, -1, 0].cpu().numpy()
            aspect_grid = sequence[0, -1, 1].cpu().numpy()
            temp = float(sequence[0, -1, 2, 0, 0].cpu().item())
            humidity = float(sequence[0, -1, 3, 0, 0].cpu().item())
            wind_speed = float(sequence[0, -1, 4, 0, 0].cpu().item())
            for i, j in burning_cells:
                logits_8d = model.predict_8_neighbors(features, i, j).squeeze(0)
                probs_8d = torch.sigmoid(logits_8d).cpu().numpy()
                labels_8d = np.zeros(8, dtype=np.float32)
                neighbors = model.get_8_neighbor_coords(i, j, H, W)
                burning_flags = np.zeros(8, dtype=np.float32)
                for n_idx, neighbor in enumerate(neighbors):
                    if neighbor is not None:
                        ni, nj = neighbor
                        if target_fire[0, ni, nj] > 0.5 and current_fire[0, ni, nj] <= 0.5:
                            labels_8d[n_idx] = 1.0
                        if current_fire[0, ni, nj] > 0.5:
                            burning_flags[n_idx] = 1.0
                preds_8d = (probs_8d > 0.5).astype(np.float32)
                correct_8d = (preds_8d == labels_8d).astype(np.float32)
                # Sprint 2: enhanced features (12 columns)
                cell_features = meta_labeler.build_enhanced_features(
                    prob=probs_8d,
                    slope=np.full(8, slope_grid[i, j]),
                    aspect=np.full(8, aspect_grid[i, j]),
                    wind_speed=wind_speed,
                    humidity=humidity,
                    temp=temp,
                    burning_neighbors=burning_flags,
                )
                for k in range(8):
                    X_all.append(cell_features[k])
                    y_all.append(correct_8d[k])
    return np.array(X_all), np.array(y_all)


# Train meta-labeler on VAL predictions
print("Collecting meta features on VAL split (for training)...")
X_meta_train, y_meta_train = collect_meta_features(model, val_loader, device)
print(f"  VAL meta shapes: X={X_meta_train.shape}  pos={int(np.sum(y_meta_train==1))}  neg={int(np.sum(y_meta_train==0))}")

if len(X_meta_train) == 0:
    print("WARNING: no burning cells found in VAL — meta-labeler will be skipped.")
else:
    print("Fitting Random Forest on VAL predictions...")
    meta_labeler.train(X_meta_train, y_meta_train)

    # Evaluate on TEST (unseen) — honest generalization estimate
    print("Collecting meta features on TEST split (for evaluation, unseen)...")
    X_meta_test, y_meta_test = collect_meta_features(model, test_loader, device)
    print(f"  TEST meta shapes: X={X_meta_test.shape}  pos={int(np.sum(y_meta_test==1))}  neg={int(np.sum(y_meta_test==0))}")

    test_preds = meta_labeler.predict_trustworthiness(X_meta_test)
    test_acc = float(np.mean(test_preds == y_meta_test))
    print(f"\n  >>> Meta-Labeler HELD-OUT TEST accuracy: {test_acc:.4f}  (LEAK-FREE)")

    meta_labeler.save("../meta_labeler.pkl")
    print("  Meta-Labeler saved to ../meta_labeler.pkl")

# --------------------------------------------------------------------------- #
# 8. Final test-set evaluation of the neural model itself
# --------------------------------------------------------------------------- #
print("\n=== FASE 5: EVALUACIÓN FINAL EN TEST (unseen) ===")
test_loss = evaluate_loss(model, test_loader, device)
print(f"  Neural model TEST loss: {test_loss:.5f}")

# --- Sprint 3: Interpretable segmentation metrics (IoU/Recall/Precision) ---
from wildfire_front.evaluation import (
    compute_segmentation_metrics,
    aggregate_segmentation_metrics,
)

@torch.no_grad()
def evaluate_segmentation(model, loader, device):
    """Compute per-sample IoU/Recall/Precision over test set."""
    model.eval()
    all_metrics = []
    for sequence, current_fire, target_fire in loader:
        sequence = sequence.to(device)
        current_fire = current_fire.to(device)
        target_fire = target_fire.to(device)
        with torch.amp.autocast('cuda', enabled=USE_AMP):
            features, _ = model.forward(sequence, current_fire)
        # Build predicted spread mask
        H, W = current_fire.shape[1], current_fire.shape[2]
        pred_spread = torch.zeros_like(target_fire)
        burning_cells = model.get_burning_cells(current_fire)
        for i, j in burning_cells:
            logits_8d = model.predict_8_neighbors(features, i, j).squeeze(0)
            probs_8d = torch.sigmoid(logits_8d)
            neighbors = model.get_8_neighbor_coords(i, j, H, W)
            for n_idx, neighbor in enumerate(neighbors):
                if neighbor is not None:
                    ni, nj = neighbor
                    if current_fire[0, ni, nj] <= 0.5:
                        pred_spread[0, ni, nj] = probs_8d[n_idx]
        gt_np = target_fire[0].cpu().numpy()
        pred_np = pred_spread[0].cpu().numpy()
        m = compute_segmentation_metrics(pred_np, gt_np, threshold=0.5)
        all_metrics.append(m)
    return aggregate_segmentation_metrics(all_metrics)

seg_metrics = evaluate_segmentation(model, test_loader, device)
print(f"  Segmentation metrics (TEST):")
print(f"    IoU (micro):       {seg_metrics.get('micro_iou', 0.0):.4f}")
print(f"    Dice/F1 (micro):   {seg_metrics.get('micro_dice', 0.0):.4f}")
print(f"    Precision (micro): {seg_metrics.get('micro_precision', 0.0):.4f}")
print(f"    Recall (micro):    {seg_metrics.get('micro_recall', 0.0):.4f}")

# Save evaluation_metrics.json alongside training_summary.json
Path("../evaluation_metrics.json").write_text(json.dumps(seg_metrics, indent=2, default=str))
print("  Evaluation metrics saved to ../evaluation_metrics.json")

summary = {
    "best_pretrain_epoch": best_epoch,
    "best_val_loss": best_val_loss,
    "test_loss": test_loss,
    "meta_labeler_test_acc": test_acc if len(X_meta_train) else None,
    "train_samples": len(train_dataset),
    "val_samples": len(val_dataset),
    "test_samples": len(test_dataset),
    "v11_config": {
        "peak_lr": PEAK_LR,
        "warmup_epochs": WARMUP_EPOCHS,
        "patience": patience,
        "meta_labeler_features": 12,
    },
    "seg_metrics": seg_metrics,
}
Path("../training_summary.json").write_text(json.dumps(summary, indent=2, default=str))
print("\nSummary written to ../training_summary.json")
print(json.dumps(summary, indent=2))

print("\n=== ALL STAGES COMPLETED — LEAK-FREE ===")