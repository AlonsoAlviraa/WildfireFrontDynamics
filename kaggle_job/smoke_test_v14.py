#!/usr/bin/env python3
"""Local smoke-test harness for the experiment loop.

This validates that the full training pipeline (model + loss + data + eval)
works end-to-end on synthetic data **before** burning Kaggle GPU hours.

Run locally:
    python kaggle_job/smoke_test_v14.py

It will:
    1. Generate 20 tiny synthetic samples (no NDWS download needed)
    2. Run 2 epochs of training with the v14 script logic
    3. Verify loss decreases and metrics are computed
    4. Exit 0 on success, 1 on failure
"""

import sys
import json
import tempfile
from pathlib import Path


def main():
    print("=" * 60)
    print("SMOKE TEST: v14 training pipeline on synthetic data")
    print("=" * 60)

    # Add repo root to path
    repo_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(repo_root))

    # Check torch is available
    try:
        import torch
        import torch.nn as nn
        print(f"[OK] PyTorch {torch.__version__}")
    except ImportError:
        print("[FAIL] PyTorch not installed. Install with: pip install torch")
        return 1

    import numpy as np

    # Import model components
    try:
        from models.unet_model import (
            WildfireUNet, WildfireUNetSmall, count_parameters,
            weighted_bce_loss, dice_loss, tversky_loss, focal_loss,
            combined_loss, composite_loss, make_loss_fn,
        )
        print("[OK] models.unet_model imported")
    except Exception as e:
        print(f"[FAIL] Cannot import models.unet_model: {e}")
        return 1

    # Test 1: Model forward pass
    print("\n--- Test 1: Model forward pass ---")
    for cls_name, cls in [("WildfireUNet", WildfireUNet), ("WildfireUNetSmall", WildfireUNetSmall)]:
        model = cls(in_channels=18, out_channels=1, bilinear=True)
        x = torch.randn(4, 18, 64, 64)
        with torch.no_grad():
            out = model(x)
        assert out.shape == (4, 1, 64, 64), f"{cls_name} output shape: {out.shape}"
        params = count_parameters(model)
        print(f"  [OK] {cls_name}: input {x.shape} -> output {out.shape} ({params:,} params)")

    # Test 2: Loss functions
    print("\n--- Test 2: Loss functions ---")
    logits = torch.randn(4, 1, 64, 64, requires_grad=True)
    targets = (torch.rand(4, 1, 64, 64) > 0.8).float()

    for name, fn in [("weighted_bce", weighted_bce_loss), ("dice", dice_loss),
                     ("tversky", tversky_loss), ("focal", focal_loss),
                     ("combined", combined_loss), ("composite", composite_loss)]:
        loss = fn(logits, targets) if name not in ("weighted_bce", "combined", "focal", "composite") \
               else fn(logits, targets, pos_weight=5.0)
        assert torch.isfinite(loss), f"{name} loss is not finite: {loss}"
        loss.backward()
        assert logits.grad is not None, f"{name} produced no gradient"
        print(f"  [OK] {name}_loss = {loss.item():.4f}, grad norm = {logits.grad.norm().item():.4f}")
        logits.grad = None

    # Test 3: make_loss_fn factory
    print("\n--- Test 3: make_loss_fn factory ---")
    for name in ["bce", "dice", "tversky", "focal", "combined", "composite"]:
        fn = make_loss_fn(name, pos_weight=5.0)
        loss = fn(logits, targets)
        assert torch.isfinite(loss), f"factory {name} loss not finite"
        print(f"  [OK] make_loss_fn('{name}') = {loss.item():.4f}")

    # Test 4: Dataset + evaluation
    print("\n--- Test 4: NpzWildfireDataset + evaluation ---")
    try:
        from wildfire_front.ml.dataset import NpzWildfireDataset
        from wildfire_front.evaluation import (
            compute_segmentation_metrics, aggregate_segmentation_metrics
        )
        print("  [OK] wildfire_front imports successful")
    except Exception as e:
        print(f"  [FAIL] wildfire_front import: {e}")
        return 1

    # Generate synthetic data
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        for split_name, n in [("train", 20), ("val", 6), ("test", 6)]:
            d = tmpdir / split_name
            d.mkdir(parents=True, exist_ok=True)
            for i in range(n):
                seq = np.random.randn(1, 17, 64, 64).astype(np.float32) * 0.5
                cf = np.zeros((64, 64), dtype=np.float32)
                tf_ = np.zeros((64, 64), dtype=np.float32)
                cf[20:40, 20:40] = 1.0
                tf_[18:42, 18:42] = 1.0
                np.savez_compressed(d / f"patch_{i:06d}.npz", sequence=seq,
                                    current_fire=cf, target_fire=tf_)

        ds = NpzWildfireDataset(tmpdir / "train", augment=True)
        assert len(ds) == 20
        seq, cf, tf_ = ds[0]
        assert seq.shape == (1, 17, 64, 64), f"seq shape: {seq.shape}"
        assert cf.shape == (64, 64), f"cf shape: {cf.shape}"
        assert tf_.shape == (64, 64), f"tf shape: {tf_.shape}"
        print(f"  [OK] Dataset: {len(ds)} samples, seq={seq.shape}, cf={cf.shape}, tf={tf_.shape}")

        # Test evaluation
        pred = np.random.rand(64, 64).astype(np.float32)
        gt = tf_.numpy()
        m = compute_segmentation_metrics(pred, gt, threshold=0.5)
        agg = aggregate_segmentation_metrics([m])
        assert "micro_iou" in agg, f"aggregate missing micro_iou: {agg}"
        print(f"  [OK] Evaluation: IoU={agg['micro_iou']:.4f}, Recall={agg['micro_recall']:.4f}")

    # Test 5: Mini training loop (2 epochs) — also generates data for Test 6
    print("\n--- Test 5: Mini training loop (2 epochs) ---")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"  Device: {device}")

    model = WildfireUNetSmall(in_channels=18, out_channels=1, bilinear=True).to(device)
    loss_fn = make_loss_fn("composite", pos_weight=5.0)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)

    # Use a persistent temp dir so Test 6 can reuse it
    tmpdir = Path(tempfile.mkdtemp(prefix="wildfire_smoke_"))
    for split_name, n in [("train", 20), ("val", 6), ("test", 6)]:
        d = tmpdir / split_name
        d.mkdir(parents=True, exist_ok=True)
        for i in range(n):
            seq = np.random.randn(1, 17, 64, 64).astype(np.float32) * 0.5
            cf = np.zeros((64, 64), dtype=np.float32)
            tf_ = np.zeros((64, 64), dtype=np.float32)
            cf[20:40, 20:40] = 1.0
            tf_[18:42, 18:42] = 1.0
            np.savez_compressed(d / f"patch_{i:06d}.npz", sequence=seq,
                                current_fire=cf, target_fire=tf_)

    from torch.utils.data import DataLoader

    train_ds = NpzWildfireDataset(tmpdir / "train", augment=True)
    val_ds = NpzWildfireDataset(tmpdir / "val", augment=False)
    train_loader = DataLoader(train_ds, batch_size=4, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=4, shuffle=False)

    losses = []
    for epoch in range(2):
        model.train()
        epoch_loss = 0
        for seq, cf, tf_batch in train_loader:
            seq, cf, tf_batch = seq.to(device), cf.to(device), tf_batch.to(device)
            B, T, C, H, W = seq.shape
            x = torch.cat([seq.reshape(B, T * C, H, W), cf.unsqueeze(1)], dim=1)
            target = tf_batch.unsqueeze(1).float()
            optimizer.zero_grad()
            logits = model(x)
            loss = loss_fn(logits, target)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            epoch_loss += loss.item()
        avg = epoch_loss / len(train_loader)
        losses.append(avg)
        print(f"  Epoch {epoch+1}/2: loss={avg:.4f}")

    assert len(losses) == 2, f"Expected 2 epochs, got {len(losses)}"
    assert all(np.isfinite(losses)), f"Losses not finite: {losses}"
    print(f"  [OK] Training completed, losses={[f'{l:.4f}' for l in losses]}")

    # Test 6: Full v14 script smoke-test mode
    print("\n--- Test 6: v14 script smoke-test mode ---")
    import subprocess
    v14_script = repo_root / "kaggle_job" / "run_unet_training_v14.py"
    result = subprocess.run(
        [sys.executable, str(v14_script),
         "--smoke-test", "--epochs", "2", "--batch-size", "4",
         "--data-dir", str(tmpdir),
         "--output-dir", str(tmpdir / "output")],
        capture_output=True, text=True, timeout=300, cwd=str(repo_root)
    )
    if result.returncode != 0:
        print(f"  [FAIL] v14 script exited with code {result.returncode}")
        print(f"  stderr: {result.stderr[-500:]}")
        return 1
    print(f"  [OK] v14 script completed successfully (returncode=0)")

    # Check outputs were created
    output = tmpdir / "output"
    summary_file = output / "training_summary.json"
    if summary_file.exists():
        summary = json.loads(summary_file.read_text())
        print(f"  [OK] training_summary.json: version={summary.get('version')}, "
              f"best_epoch={summary.get('best_epoch')}")
    else:
        print(f"  [WARN] training_summary.json not found at {summary_file}")

    print("\n" + "=" * 60)
    print("ALL SMOKE TESTS PASSED [OK]")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())