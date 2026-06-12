"""Cloud Training and Hugging Face Hub Upload Pipeline.

This script executes the spatiotemporal training loop on cloud platforms
(Kaggle / Google Colab) and pushes the optimized weights directly to the
Hugging Face Hub, avoiding local storage.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader

from models.model import A3C_PerCellModel_LSTM
from .dataset import WildfireDataset
from .train import calculate_local_spread_loss


def upload_to_huggingface(
    local_file: Path,
    repo_id: str,
    token: str,
) -> None:
    """Upload a local weights file directly to Hugging Face Hub."""
    try:
        from huggingface_hub import HfApi
    except ImportError:
        print(
            "Error: 'huggingface_hub' is not installed. "
            "Please run 'pip install huggingface_hub' to enable upload.",
            file=sys.stderr,
        )
        return

    print(f"Authenticating and uploading {local_file.name} to Hugging Face repository '{repo_id}'...")
    try:
        api = HfApi()
        # Create repo if it doesn't exist
        api.create_repo(repo_id=repo_id, token=token, private=True, exist_ok=True)
        # Upload the file
        api.upload_file(
            path_or_fileobj=str(local_file),
            path_in_repo=local_file.name,
            repo_id=repo_id,
            token=token,
        )
        print("Upload completed successfully!")
    except Exception as e:
        print(f"Failed to upload to Hugging Face: {e}", file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Cloud training and Hugging Face upload pipeline.")
    parser.add_argument("--images", type=Path, required=True, help="Path to images directory")
    parser.add_argument("--masks", type=Path, required=True, help="Path to masks directory")
    parser.add_argument("--weights", type=Path, required=True, help="Path to pre-trained weights v3.pt")
    parser.add_argument("--output-weights", type=Path, required=True, help="Where to save the fine-tuned weights")
    parser.add_argument("--epochs", type=int, default=5, help="Number of training epochs")
    parser.add_argument("--lr", type=float, default=1e-4, help="Learning rate")
    parser.add_argument("--hf-token", type=str, help="Hugging Face write token")
    parser.add_argument("--hf-repo", type=str, help="Hugging Face repository name (e.g. username/repo-name)")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    # 1. Initialize dataset
    dataset = WildfireDataset(args.images, args.masks, sequence_length=3, patch_size=30)
    dataloader = DataLoader(dataset, batch_size=1, shuffle=True)
    print(f"Dataset loaded. Total spatial sequence patches: {len(dataset)}")

    # 2. Setup model
    model = A3C_PerCellModel_LSTM(in_channels=16, lstm_hidden=256, sequence_length=3)
    print(f"Loading pre-trained weights from {args.weights}...")
    checkpoint = torch.load(args.weights, map_location=device)
    state_dict = checkpoint.get("model_state_dict", checkpoint)
    model.load_state_dict(state_dict)
    model.to(device)

    # 3. Optimize policy weights
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    model.train()

    print("Starting training loop...")
    for epoch in range(args.epochs):
        epoch_loss = 0.0
        steps = 0
        for sequence, current_fire, target_fire in dataloader:
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
        print(f"Epoch {epoch+1}/{args.epochs} - Loss: {avg_loss:.6f}")

    # 4. Save local weights file
    args.output_weights.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "epochs": args.epochs,
            "final_loss": avg_loss,
        },
        args.output_weights,
    )
    print(f"Weights saved locally to {args.output_weights}")

    # 5. Push to Hugging Face Hub if credentials are provided
    if args.hf_token and args.hf_repo:
        upload_to_huggingface(args.output_weights, args.hf_repo, args.hf_token)


if __name__ == "__main__":
    main()
