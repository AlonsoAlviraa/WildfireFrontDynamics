import os
import sys
import subprocess
import glob
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, random_split
import numpy as np

# 1. Clone repository
print("Cloning repository...")
subprocess.run(["git", "clone", "https://github.com/AlonsoAlviraa/WildfireFrontDynamics.git"], check=True)

print("Changing directory to WildfireFrontDynamics...")
os.chdir("WildfireFrontDynamics")
sys.path.append(os.getcwd())

# 2. Run Preprocessing as a subprocess for both train and val splits
print("=== FASE 1: PREPROCESAMIENTO DE TFRECORDS (TRAIN & VAL) ===")
preprocess_script = "kaggle_job/preprocess_ndws.py"
subprocess.run([sys.executable, preprocess_script, "--split", "train"], check=True)
subprocess.run([sys.executable, preprocess_script, "--split", "val"], check=True)

# 3. Setup paths and imports
print("=== SETUP ENTORNOS ===")
sys.path.append(os.getcwd())

from models.model import A3C_PerCellModel_LSTM
from wildfire_front.ml.dataset import NpzWildfireDataset, WildfireDataset
from wildfire_front.ml.meta_labeler import WildfireMetaLabeler
from wildfire_front.ml.train import calculate_local_spread_loss

# 3. Load pre-training and validation datasets explicitly (no random_split to avoid leakage)
train_dir = "/tmp/ndws_npz/train"
val_dir = "/tmp/ndws_npz/val"
train_dataset = NpzWildfireDataset(train_dir)
val_dataset = NpzWildfireDataset(val_dir)
print(f"Pre-training samples: {len(train_dataset)}, Meta-Labeler validation samples: {len(val_dataset)}")

train_loader = DataLoader(train_dataset, batch_size=1, shuffle=True)
val_loader = DataLoader(val_dataset, batch_size=1, shuffle=False)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Using device: {device}")

# 4. Initialize model and load initial pre-trained weights
model = A3C_PerCellModel_LSTM(in_channels=16, lstm_hidden=256, sequence_length=3)
pretrained_base = "models/v3.pt"
print(f"Loading initial model weights from {pretrained_base}...")
checkpoint = torch.load(pretrained_base, map_location=device)
state_dict = checkpoint.get("model_state_dict", checkpoint)
model.load_state_dict(state_dict)
model.to(device)

# 5. FASE 2: PRE-ENTRENAMIENTO MASIVO (GOOGLE NDWS)
print("=== FASE 2: PRE-ENTRENAMIENTO MASIVO EN LA NUBE ===")
optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4, weight_decay=1e-4)
from torch.optim.lr_scheduler import CosineAnnealingLR
epochs = 12  # Pre-train for 12 epochs
scheduler = CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-6)
model.train()

for epoch in range(epochs):
    epoch_loss = 0.0
    steps = 0
    for sequence, current_fire, target_fire in train_loader:
        sequence = sequence.to(device)
        current_fire = current_fire.to(device)
        target_fire = target_fire.to(device)

        features, _ = model.forward(sequence, current_fire)
        loss = calculate_local_spread_loss(model, features, current_fire, target_fire)

        if loss is not None:
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=0.5)
            optimizer.step()
            epoch_loss += loss.item()
            steps += 1

    scheduler.step()
    avg_loss = epoch_loss / steps if steps > 0 else 0.0
    current_lr = scheduler.get_last_lr()[0]
    print(f"Pre-training Epoch {epoch+1}/{epochs} - Loss: {avg_loss:.6f} - LR: {current_lr:.8f}")

# Save pre-trained model
pretrained_output = "../weights_pretrained.pt"
torch.save(model.state_dict(), pretrained_output)
print(f"Pre-trained weights saved to {pretrained_output}")

# 6. FASE 3: TRANSFER LEARNING CON DATASET TACTICO LOCAL
print("=== FASE 3: TRANSFER LEARNING CON DATASET LOCAL ===")
local_images = "data/candidates/semireal_controlled_001/images"
local_masks = "data/candidates/semireal_controlled_001/masks"
local_dataset = WildfireDataset(local_images, local_masks, sequence_length=3, patch_size=30)
local_loader = DataLoader(local_dataset, batch_size=1, shuffle=True)

# Reset optimizer with a smaller learning rate for fine-tuning
optimizer = torch.optim.AdamW(model.parameters(), lr=2e-5, weight_decay=1e-4)
model.train()

ft_epochs = 10
for epoch in range(ft_epochs):
    epoch_loss = 0.0
    steps = 0
    for sequence, current_fire, target_fire in local_loader:
        sequence = sequence.to(device)
        current_fire = current_fire.to(device)
        target_fire = target_fire.to(device)

        features, _ = model.forward(sequence, current_fire)
        loss = calculate_local_spread_loss(model, features, current_fire, target_fire)

        if loss is not None:
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=0.5)
            optimizer.step()
            epoch_loss += loss.item()
            steps += 1

    avg_loss = epoch_loss / steps if steps > 0 else 0.0
    print(f"Fine-tuning Epoch {epoch+1}/{ft_epochs} - Loss: {avg_loss:.6f}")

fine_tuned_output = "../weights_fine_tuned.pt"
torch.save(model.state_dict(), fine_tuned_output)
print(f"Fine-tuned weights saved to {fine_tuned_output}")

# 7. FASE 4: ENTRENAMIENTO DEL META-LABELER
print("=== FASE 4: ENTRENAMIENTO DE LA CAPA DE SEGURIDAD (META-LABELER) ===")
meta_labeler = WildfireMetaLabeler(n_estimators=100, max_depth=10, random_state=42)

# Collect predictions on validation set to train Meta-Labeler
model.eval()
X_meta = []
y_meta = []

with torch.no_grad():
    for sequence, current_fire, target_fire in val_loader:
        sequence = sequence.to(device)
        current_fire = current_fire.to(device)
        target_fire = target_fire.to(device)

        features, _ = model.forward(sequence, current_fire)
        burning_cells = model.get_burning_cells(current_fire)
        if not burning_cells:
            continue

        H, W = current_fire.shape[1], current_fire.shape[2]
        
        # Get slope and aspect arrays from sequence (Channels 0 & 1 at t=-1)
        slope_grid = sequence[0, -1, 0].cpu().numpy()
        aspect_grid = sequence[0, -1, 1].cpu().numpy()
        
        # Get weather variables (temp, humidity, wind_speed) from sequence at t=-1
        temp = float(sequence[0, -1, 2, 0, 0].cpu().item())
        humidity = float(sequence[0, -1, 3, 0, 0].cpu().item())
        wind_speed = float(sequence[0, -1, 4, 0, 0].cpu().item())

        for i, j in burning_cells:
            logits_8d = model.predict_8_neighbors(features, i, j).squeeze(0)
            probs_8d = torch.sigmoid(logits_8d).cpu().numpy()
            
            # Ground truth targets for 8 neighbors
            labels_8d = np.zeros(8, dtype=np.float32)
            neighbors = model.get_8_neighbor_coords(i, j, H, W)
            for n_idx, neighbor in enumerate(neighbors):
                if neighbor is not None:
                    ni, nj = neighbor
                    if target_fire[0, ni, nj] > 0.5 and current_fire[0, ni, nj] <= 0.5:
                        labels_8d[n_idx] = 1.0

            # Build cell features using the class definition
            preds_8d = (probs_8d > 0.5).astype(np.float32)
            correct_8d = (preds_8d == labels_8d).astype(np.float32)
            
            cell_features = meta_labeler.build_features(
                prob=probs_8d,
                slope=np.full(8, slope_grid[i, j]),
                aspect=np.full(8, aspect_grid[i, j]),
                wind_speed=wind_speed,
                humidity=humidity,
                temp=temp
            )
            
            for k in range(8):
                X_meta.append(cell_features[k])
                y_meta.append(correct_8d[k])

X_meta = np.array(X_meta)
y_meta = np.array(y_meta)

print(f"Meta-Labeler dataset shapes: X={X_meta.shape}, y={y_meta.shape}")
print(f"Label distribution: Correct (1) = {np.sum(y_meta == 1)}, Incorrect (0) = {np.sum(y_meta == 0)}")

print("Fitting Random Forest classifier...")
meta_labeler.train(X_meta, y_meta)

# Self-eval metrics
train_preds = meta_labeler.predict_trustworthiness(X_meta)
accuracy = np.mean(train_preds == y_meta)
print(f"Meta-Labeler Self-Training Accuracy: {accuracy:.4f}")

meta_labeler_output = "../meta_labeler.pkl"
meta_labeler.save(meta_labeler_output)
print(f"Meta-Labeler model successfully saved to {meta_labeler_output}")

print("=== ALL STAGES COMPLETED SUCCESSFULLY ===")
