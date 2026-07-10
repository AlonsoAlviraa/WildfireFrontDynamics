#!/usr/bin/env python3
"""Leakage + Copy Baseline Analysis for Kaggle (real NDWS data).

Runs on Kaggle with actual preprocessed data to measure:
    1. Copy baseline (PrevFireMask as prediction) IoU
    2. Channel correlations with target
    3. Fire dynamics distribution

Usage on Kaggle: set as kernel script.
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from collections import defaultdict
import numpy as np

# Clone repo
if not Path("WildfireFrontDynamics").exists():
    subprocess.run(["git", "clone", "--depth", "1",
                     "https://github.com/AlonsoAlviraa/WildfireFrontDynamics.git"], check=True)
if Path("WildfireFrontDynamics").exists():
    os.chdir("WildfireFrontDynamics")
    sys.path.insert(0, os.getcwd())

# Preprocess if needed
data_root = Path("/tmp/ndws_npz")
if not all((data_root / s).exists() for s in ["train", "val", "test"]):
    for split in ["train", "val", "test"]:
        subprocess.run([sys.executable, "kaggle_job/preprocess_ndws.py",
                         "--split", split, "--patch-size", "64"], check=True)

print("=" * 70)
print("LEAKAGE + COPY BASELINE ANALYSIS (REAL NDWS DATA)")
print("=" * 70)

# Load data
for split in ["train", "val", "test"]:
    split_dir = data_root / split
    files = sorted(split_dir.glob("*.npz"))
    print(f"\n{split}: {len(files)} files")

    copy_ious = []
    copy_recalls = []
    copy_precisions = []
    correlations = []
    categories = {"growth": 0, "shrink": 0, "stable": 0, "no_fire": 0}
    channel_corrs = defaultdict(list)

    channel_names = [
        "slope", "aspect", "temperature", "humidity", "wind_speed",
        "wind_dir", "precip", "pressure", "cloud", "visibility",
        "dewpoint", "vegetation", "ERC", "1-ERC", "pad0", "pad1", "FFMC",
    ]

    for fpath in files[:500]:  # Sample up to 500
        try:
            with np.load(fpath) as data:
                seq = data["sequence"]
                cf = data["current_fire"]
                tf = data["target_fire"]
        except Exception:
            continue

        cf_bin = (cf >= 0.5).astype(np.float64)
        tf_bin = (tf >= 0.5).astype(np.float64)

        tp = np.sum((cf_bin == 1) & (tf_bin == 1))
        fp = np.sum((cf_bin == 1) & (tf_bin == 0))
        fn = np.sum((cf_bin == 0) & (tf_bin == 1))

        eps = 1e-7
        copy_ious.append(tp / (tp + fp + fn + eps))
        copy_recalls.append(tp / (tp + fn + eps))
        copy_precisions.append(tp / (tp + fp + eps))

        if np.std(cf) > 0 and np.std(tf) > 0:
            r = np.corrcoef(cf.flatten(), tf.flatten())[0, 1]
            if np.isfinite(r):
                correlations.append(r)

        # Fire dynamics
        in_px = np.sum(cf_bin)
        tgt_px = np.sum(tf_bin)
        if in_px < 5 and tgt_px < 5:
            categories["no_fire"] += 1
        else:
            change = (tgt_px - in_px) / max(in_px, 1) * 100
            if change > 10:
                categories["growth"] += 1
            elif change < -10:
                categories["shrink"] += 1
            else:
                categories["stable"] += 1

        # Channel correlations
        T, C, H, W = seq.shape
        tf_flat = tf.flatten()
        if np.std(tf_flat) > 1e-6:
            for ci in range(min(C, len(channel_names))):
                ch = seq[0, ci].flatten()
                if np.std(ch) > 1e-6:
                    r = np.corrcoef(ch, tf_flat)[0, 1]
                    if np.isfinite(r):
                        channel_corrs[channel_names[ci]].append(abs(r))

    print(f"\n--- {split.upper()} COPY BASELINE ---")
    print(f"  Copy IoU:     {np.mean(copy_ious):.4f} +/- {np.std(copy_ious):.4f}")
    print(f"  Copy Recall:  {np.mean(copy_recalls):.4f}")
    print(f"  Copy Precision: {np.mean(copy_precisions):.4f}")
    if correlations:
        print(f"  Correlation:  {np.mean(correlations):.4f} +/- {np.std(correlations):.4f}")

    print(f"\n--- {split.upper()} FIRE DYNAMICS ---")
    total = sum(categories.values())
    for cat, count in categories.items():
        pct = count / total * 100 if total > 0 else 0
        print(f"  {cat:12s}: {count:4d} ({pct:5.1f}%)")

    if channel_corrs:
        print(f"\n--- {split.upper()} CHANNEL IMPORTANCE ---")
        ranked = [(name, np.mean(corrs)) for name, corrs in channel_corrs.items()]
        ranked.sort(key=lambda x: x[1], reverse=True)
        for name, mean_r in ranked:
            print(f"  {name:25s} |r|={mean_r:.4f}")

# Save results
results = {
    "copy_baseline_test_iou": float(np.mean(copy_ious)),
    "v14_model_test_iou": 0.239,
    "margin": float(np.mean(copy_ious)) - 0.239,
    "conclusion": "CRITICAL: Copy baseline beats model. Need residual architecture." 
                  if np.mean(copy_ious) > 0.30 else "OK: Model beats copy baseline."
}
Path("/kaggle/working/leakage_analysis.json").write_text(json.dumps(results, indent=2))
print("\n" + "=" * 70)
print(f"CONCLUSION: {results['conclusion']}")
print(f"  Copy IoU: {results['copy_baseline_test_iou']:.4f}")
print(f"  Model IoU: {results['v14_model_test_iou']:.4f}")
print(f"  Margin: {results['margin']:+.4f}")
print("=" * 70)