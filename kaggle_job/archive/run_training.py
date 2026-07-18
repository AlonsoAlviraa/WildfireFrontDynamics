import os
import sys
import subprocess

print("=== Starting Wildfire Front Dynamics Training Job on Kaggle ===")

print("Cloning repository...")
subprocess.run(["git", "clone", "https://github.com/AlonsoAlviraa/WildfireFrontDynamics.git"], check=True)

print("Changing directory to WildfireFrontDynamics...")
os.chdir("WildfireFrontDynamics")
sys.path.append(os.getcwd())

print("Installing required dependencies (rasterio)...")
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "rasterio"], check=True)

print("Verifying PyTorch CUDA support...")
import torch
print("CUDA Available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("Device Name:", torch.cuda.get_device_name(0))

print("Launching training pipeline...")
# Run training with 15 epochs on the candidate dataset
cmd = [
    sys.executable, "-m", "wildfire_front.ml.cloud_train",
    "--images", "data/candidates/semireal_controlled_001/images",
    "--masks", "data/candidates/semireal_controlled_001/masks",
    "--weights", "models/v3.pt",
    "--output-weights", "../fine_tuned_weights.pt",
    "--epochs", "15",
    "--lr", "1e-4"
]

print("Executing command:", " ".join(cmd))
subprocess.run(cmd, check=True)

print("Training finished successfully!")
print("Checking output files:")
if os.path.exists("../fine_tuned_weights.pt"):
    print("Output weights successfully saved to outputs folder!")
else:
    print("Warning: output weights not found at ../fine_tuned_weights.pt")
