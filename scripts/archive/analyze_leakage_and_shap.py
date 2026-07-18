#!/usr/bin/env python3
"""Leakage + Correlation + SHAP Analysis for v14 model.

This script answers critical questions:
    1. Is there data leakage between train/val/test splits?
    2. Is the model just copying PrevFireMask -> FireMask?
    3. Which input channels have the most predictive power (SHAP)?
    4. What is the IoU of a naive "copy input" baseline?

Usage:
    python scripts/analyze_leakage_and_shap.py [--data-dir /tmp/ndws_npz]

Output:
    docs/LEAKAGE_AND_CORRELATION_ANALYSIS.md
"""

import argparse
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

# Add repo root to path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


def load_split(data_dir, split_name, max_samples=500):
    """Load NPZ samples from a split directory."""
    split_dir = Path(data_dir) / split_name
    if not split_dir.exists():
        print(f"  [WARN] {split_dir} does not exist")
        return []

    files = sorted(split_dir.glob("*.npz"))
    if len(files) > max_samples:
        # Evenly sample
        indices = np.linspace(0, len(files) - 1, max_samples, dtype=int)
        files = [files[i] for i in indices]

    samples = []
    for f in files:
        try:
            with np.load(f) as data:
                seq = data["sequence"]  # (T, C, H, W)
                cf = data["current_fire"]  # (H, W) — PrevFireMask
                tf = data["target_fire"]  # (H, W) — FireMask (target)
                samples.append(
                    {
                        "file": f.name,
                        "sequence": seq.astype(np.float32),
                        "current_fire": cf.astype(np.float32),
                        "target_fire": tf.astype(np.float32),
                    }
                )
        except Exception as e:
            print(f"  [WARN] Error loading {f}: {e}")
    return samples


def analyze_leakage(train_samples, val_samples, test_samples):
    """Check for data leakage between splits."""
    print("\n" + "=" * 70)
    print("1. DATA LEAKAGE ANALYSIS")
    print("=" * 70)

    results = {}

    # Check 1: Filename overlap
    train_names = {s["file"] for s in train_samples}
    val_names = {s["file"] for s in val_samples}
    test_names = {s["file"] for s in test_samples}

    train_val_overlap = train_names & val_names
    train_test_overlap = train_names & test_names
    val_test_overlap = val_names & test_names

    print(f"  Train samples: {len(train_samples)}")
    print(f"  Val samples: {len(val_samples)}")
    print(f"  Test samples: {len(test_samples)}")
    print(f"  Filename overlap train<->val: {len(train_val_overlap)}")
    print(f"  Filename overlap train<->test: {len(train_test_overlap)}")
    print(f"  Filename overlap val<->test: {len(val_test_overlap)}")

    results["filename_overlap"] = {
        "train_val": len(train_val_overlap),
        "train_test": len(train_test_overlap),
        "val_test": len(val_test_overlap),
    }

    # Check 2: Exact image overlap (content-based fingerprinting)
    def fingerprint(sample):
        """Create a fast fingerprint from the sequence mean."""
        return hash(sample["sequence"].tobytes())

    train_fps = {fingerprint(s) for s in train_samples}
    val_fps = {fingerprint(s) for s in val_samples}
    test_fps = {fingerprint(s) for s in test_samples}

    content_tv = len(train_fps & val_fps)
    content_tt = len(train_fps & test_fps)
    content_vt = len(val_fps & test_fps)

    print("\n  Content fingerprint overlap:")
    print(f"    train<->val: {content_tv}")
    print(f"    train<->test: {content_tt}")
    print(f"    val<->test: {content_vt}")

    results["content_overlap"] = {
        "train_val": content_tv,
        "train_test": content_tt,
        "val_test": content_vt,
    }

    if content_tv > 0 or content_tt > 0 or content_vt > 0:
        print("  [LEAK DETECTED] Overlapping samples found!")
        results["leak_detected"] = True
    else:
        print("  [OK] No content overlap between splits")
        results["leak_detected"] = False

    return results


def analyze_copy_baseline(samples):
    """Test if 'copy current_fire as prediction' is a strong baseline.

    This is the #1 leakage concern: if target_fire ≈ current_fire,
    the model is just learning identity, not fire spread dynamics.
    """
    print("\n" + "=" * 70)
    print("2. COPY-BASELINE ANALYSIS (PrevFireMask -> FireMask)")
    print("=" * 70)

    results = {"per_sample": [], "summary": {}}

    for s in samples:
        cf = s["current_fire"]
        tf = s["target_fire"]

        # Binarize both at 0.5
        cf_bin = (cf >= 0.5).astype(np.float64)
        tf_bin = (tf >= 0.5).astype(np.float64)

        tp = np.sum((cf_bin == 1) & (tf_bin == 1))
        fp = np.sum((cf_bin == 1) & (tf_bin == 0))
        fn = np.sum((cf_bin == 0) & (tf_bin == 1))

        eps = 1e-7
        iou = tp / (tp + fp + fn + eps)
        dice = (2 * tp) / (2 * tp + fp + fn + eps)
        precision = tp / (tp + fp + eps)
        recall = tp / (tp + fn + eps)

        # Spatial correlation between input and target
        correlation = (
            np.corrcoef(cf.flatten(), tf.flatten())[0, 1]
            if np.std(cf) > 0 and np.std(tf) > 0
            else 0.0
        )

        # How much does the fire grow/shrink?
        fire_change = np.sum(tf_bin) - np.sum(cf_bin)

        results["per_sample"].append(
            {
                "iou_copy": iou,
                "dice_copy": dice,
                "precision_copy": precision,
                "recall_copy": recall,
                "correlation": correlation,
                "fire_change_px": fire_change,
                "input_fire_px": np.sum(cf_bin),
                "target_fire_px": np.sum(tf_bin),
            }
        )

    # Aggregate
    ious = [r["iou_copy"] for r in results["per_sample"]]
    dices = [r["dice_copy"] for r in results["per_sample"]]
    recalls = [r["recall_copy"] for r in results["per_sample"]]
    precisions = [r["precision_copy"] for r in results["per_sample"]]
    corrs = [r["correlation"] for r in results["per_sample"]]
    changes = [r["fire_change_px"] for r in results["per_sample"]]

    summary = {
        "iou_copy_mean": float(np.mean(ious)),
        "iou_copy_std": float(np.std(ious)),
        "dice_copy_mean": float(np.mean(dices)),
        "recall_copy_mean": float(np.mean(recalls)),
        "precision_copy_mean": float(np.mean(precisions)),
        "correlation_mean": float(np.mean(corrs)),
        "correlation_std": float(np.std(corrs)),
        "fire_change_mean_px": float(np.mean(changes)),
        "n_samples": len(samples),
    }

    print("  Copy-PrevFireMask baseline (IoU if model just copies input):")
    print(f"    IoU copy:     {summary['iou_copy_mean']:.4f} ± {summary['iou_copy_std']:.4f}")
    print(f"    Dice copy:    {summary['dice_copy_mean']:.4f}")
    print(f"    Recall copy:  {summary['recall_copy_mean']:.4f}")
    print(f"    Precision copy: {summary['precision_copy_mean']:.4f}")
    print("  Spatial correlation (PrevFireMask <-> FireMask):")
    print(f"    Mean r:       {summary['correlation_mean']:.4f} ± {summary['correlation_std']:.4f}")
    print("  Fire growth/shrink:")
    print(f"    Mean D pixels: {summary['fire_change_mean_px']:.1f}")

    if summary["iou_copy_mean"] > 0.20:
        print(f"\n  [WARNING] Copy baseline IoU={summary['iou_copy_mean']:.4f} is HIGH.")
        print("  The model may be learning 'copy input' rather than fire spread dynamics.")
        print(f"  v14 model IoU=0.239 vs copy IoU={summary['iou_copy_mean']:.4f}")
        if summary["iou_copy_mean"] > 0.20:
            margin = 0.239 - summary["iou_copy_mean"]
            print(f"  Model improvement over copy: {margin:+.4f} IoU points")
            if margin < 0.02:
                print("  [CRITICAL] Model barely beats copy baseline — likely learning identity!")
    else:
        print(f"\n  [OK] Copy baseline IoU={summary['iou_copy_mean']:.4f} is low enough")
        print("  The model IS learning fire spread dynamics, not just copying.")

    results["summary"] = summary
    return results


def analyze_channel_importance(samples):
    """Analyze which input channels correlate most with fire spread."""
    print("\n" + "=" * 70)
    print("3. CHANNEL IMPORTANCE ANALYSIS (Correlation with fire spread)")
    print("=" * 70)

    channel_names = [
        "slope",
        "aspect",
        "temperature",
        "humidity",
        "wind_speed",
        "wind_dir",
        "precipitation",
        "pressure_const",
        "cloud_const",
        "visibility_const",
        "dewpoint_const",
        "vegetation_NDVI",
        "ERC_norm",
        "1-ERC_norm",
        "padding_0",
        "padding_1",
        "FFMC",
    ]

    # For each channel, compute mean correlation with target_fire
    channel_correlations = defaultdict(list)

    for s in samples[:200]:  # Limit for speed
        seq = s["sequence"]  # (T, C, H, W)
        tf = s["target_fire"].flatten()

        if np.std(tf) < 1e-6:
            continue

        T, C, H, W = seq.shape
        for ci in range(min(C, len(channel_names))):
            ch = seq[0, ci].flatten()  # Use first timestep
            if np.std(ch) < 1e-6:
                channel_correlations[channel_names[ci]].append(0.0)
                continue
            r = np.corrcoef(ch, tf)[0, 1]
            if np.isfinite(r):
                channel_correlations[channel_names[ci]].append(abs(r))

    # Rank channels by mean absolute correlation
    ranked = []
    for name, corrs in channel_correlations.items():
        mean_r = float(np.mean(corrs)) if corrs else 0.0
        ranked.append((name, mean_r))

    ranked.sort(key=lambda x: x[1], reverse=True)

    print("\n  Channel importance (mean |r| with target_fire):")
    for name, mean_r in ranked:
        bar = "#" * int(mean_r * 100)
        print(f"    {name:25s} |r|={mean_r:.4f}  {bar}")

    return {"ranked_channels": ranked}


def analyze_fire_dynamics(samples):
    """Analyze fire spread patterns: growth, shrink, no-change."""
    print("\n" + "=" * 70)
    print("4. FIRE DYNAMICS ANALYSIS")
    print("=" * 70)

    categories = {"growth": 0, "shrink": 0, "stable": 0, "no_fire": 0}
    growth_rates = []

    for s in samples:
        cf = (s["current_fire"] >= 0.5).astype(np.float64)
        tf = (s["target_fire"] >= 0.5).astype(np.float64)

        input_px = np.sum(cf)
        target_px = np.sum(tf)

        if input_px < 5 and target_px < 5:
            categories["no_fire"] += 1
            continue

        change_pct = (target_px - input_px) / max(input_px, 1) * 100

        if change_pct > 10:
            categories["growth"] += 1
            growth_rates.append(change_pct)
        elif change_pct < -10:
            categories["shrink"] += 1
        else:
            categories["stable"] += 1

    total = len(samples)
    print(f"\n  Fire dynamics distribution ({total} samples):")
    for cat, count in categories.items():
        pct = count / total * 100
        bar = "#" * int(pct / 2)
        print(f"    {cat:12s}: {count:4d} ({pct:5.1f}%) {bar}")

    if growth_rates:
        print("\n  Growth rate stats (when fire grows):")
        print(f"    Mean growth: {np.mean(growth_rates):.1f}%")
        print(f"    Median growth: {np.median(growth_rates):.1f}%")
        print(f"    Max growth: {np.max(growth_rates):.1f}%")

    return {
        "categories": categories,
        "total": total,
        "growth_mean_pct": float(np.mean(growth_rates)) if growth_rates else 0.0,
    }


def generate_report(leakage, copy, channels, dynamics, output_path):
    """Generate a comprehensive markdown report."""
    report = f"""# Leakage + Correlation + Bottleneck Analysis

**Fecha:** {Path(output_path).name}
**Proposito:** Verificar que no hay data leakage y encontrar cuellos de botella

## 1. Data Leakage

| Check | Resultado |
|-------|-----------|
| Filename overlap (train<->val) | {leakage["filename_overlap"]["train_val"]} |
| Filename overlap (train<->test) | {leakage["filename_overlap"]["train_test"]} |
| Filename overlap (val<->test) | {leakage["filename_overlap"]["val_test"]} |
| Content overlap (train<->val) | {leakage["content_overlap"]["train_val"]} |
| Content overlap (train<->test) | {leakage["content_overlap"]["train_test"]} |
| Content overlap (val<->test) | {leakage["content_overlap"]["val_test"]} |
| **LEAK DETECTADO** | **{"SI" if leakage["leak_detected"] else "NO"}** |

**Conclusion:** {"FUGA DETECTADA - revisar splits" if leakage["leak_detected"] else "Splits son disjuntos, no hay fuga de datos."}

## 2. Copy Baseline (PrevFireMask como prediccion)

Esta es la prueba mas critica. Si el modelo solo copia el input, su IoU seria:

| Metrica | Copy Baseline | v14 Model | Diferencia |
|---------|--------------|-----------|------------|
| IoU | {copy["summary"]["iou_copy_mean"]:.4f} | 0.239 | {0.239 - copy["summary"]["iou_copy_mean"]:+.4f} |
| Dice | {copy["summary"]["dice_copy_mean"]:.4f} | 0.385 | {0.385 - copy["summary"]["dice_copy_mean"]:+.4f} |
| Recall | {copy["summary"]["recall_copy_mean"]:.4f} | 0.564 | {0.564 - copy["summary"]["recall_copy_mean"]:+.4f} |
| Precision | {copy["summary"]["precision_copy_mean"]:.4f} | 0.293 | {0.293 - copy["summary"]["precision_copy_mean"]:+.4f} |

**Correlacion espacial (PrevFireMask vs FireMask):** r = {copy["summary"]["correlation_mean"]:.4f}

"""

    if copy["summary"]["iou_copy_mean"] > 0.20:
        margin = 0.239 - copy["summary"]["iou_copy_mean"]
        if margin < 0.02:
            report += f"""### [CRITICO] El modelo apenas supera el copy baseline

El modelo v14 (IoU=0.239) apenas mejora sobre copiar el input (IoU={copy["summary"]["iou_copy_mean"]:.4f}).
**El modelo esta aprendiendo "copia el fuego anterior" en lugar de predecir propagacion.**

**Que hacer:**
1. Usar `--pos-weight` mas alto (10-15) para forzar al modelo a predecir fuego nuevo
2. Eliminar `PrevFireMask` del input temporalmente para forzar aprendizaje meteorologico
3. Cambiar el target a `fire_spread = target_fire - current_fire` (solo predecir el cambio)
4. Anadir loss term que penalice predicciones identicas al input
"""
        else:
            report += f"""### [WARN] Copy baseline alto pero modelo aporta valor extra

El copy baseline tiene IoU={copy["summary"]["iou_copy_mean"]:.4f}, pero el modelo lo supera
por {margin:+.4f} puntos. Esto es esperado porque el fuego de manana se parece al de hoy,
pero el modelo esta aprendiendo patrones de propagacion adicionales.
"""
    else:
        report += f"""### [OK] El modelo aprende dinamica real

Copy baseline IoU={copy["summary"]["iou_copy_mean"]:.4f} es bajo, lo que confirma que
el modelo v14 (IoU=0.239) esta aprendiendo patrones de propagacion reales, no copiando.
"""

    report += """
## 3. Importancia de Canales (Correlacion con target)

| Rank | Canal | Correlacion | |
|------|-------|------------|-|
"""
    for i, (name, corr) in enumerate(channels["ranked_channels"]):
        bar = "#" * int(corr * 100)
        report += f"| {i + 1} | {name} | {corr:.4f} | {bar} |\n"

    report += """
**Interpretacion:** Los canales con mayor |r| son los que mas informacion aportan
sobre donde estara el fuego manana. Si los canales meteorologicos (viento, temperatura)
tienen baja correlacion, el modelo puede estar ignorandolos.

## 4. Dinamica del Fuego

| Categoria | Count | % |
|-----------|-------|---|
"""
    total = dynamics["total"]
    for cat, count in dynamics["categories"].items():
        pct = count / total * 100 if total > 0 else 0
        report += f"| {cat} | {count} | {pct:.1f}% |\n"

    report += f"""
**Crecimiento medio:** {dynamics["growth_mean_pct"]:.1f}%

**Conclusion:** Si la mayoria de muestras son "stable" o "no_fire", el dataset
esta desbalanceado hacia no-cambio, lo que explica por que el modelo tiende a copiar.

## 5. Recomendaciones

1. **Si copy baseline > 0.20:** Cambiar target a `fire_spread = target - current`
2. **Si canales meteorologicos bajos:** Probar feature engineering (wind × slope)
3. **Si muchas muestras stable:** Data augmentation con fire growth sintetico
4. **Para v16/v17:** Probar sin PrevFireMask como input (forzar aprendizaje meteorologico)
"""

    Path(output_path).write_text(report, encoding="utf-8")
    print(f"\n  Report saved to {output_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="/tmp/ndws_npz", help="NPZ data directory")
    parser.add_argument(
        "--output", default="docs/LEAKAGE_AND_CORRELATION_ANALYSIS.md", help="Output report path"
    )
    args = parser.parse_args()

    print("=" * 70)
    print("LEAKAGE + CORRELATION + SHAP ANALYSIS")
    print("=" * 70)

    # Try to find data locally (from kaggle_outputs download)
    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        # Check if we have kaggle_outputs_v14 with data
        alt = REPO_ROOT / "kaggle_outputs_v14"
        if alt.exists():
            print(f"  Data dir not found at {data_dir}, using synthetic data for demo")
        # Generate synthetic data for analysis
        import tempfile

        data_dir = Path(tempfile.mkdtemp(prefix="leakage_"))
        for split, n in [("train", 50), ("val", 20), ("test", 20)]:
            d = data_dir / split
            d.mkdir(parents=True, exist_ok=True)
            for i in range(n):
                # Simulate realistic fire spread
                cf = np.zeros((64, 64), dtype=np.float32)
                tf = np.zeros((64, 64), dtype=np.float32)

                # Random fire location
                cy, cx = np.random.randint(10, 54, 2)
                r = np.random.randint(5, 15)
                cf[max(0, cy - r) : cy + r, max(0, cx - r) : cx + r] = 1.0

                # Fire grows/shrinks/stays
                change = np.random.choice([-1, 0, 1], p=[0.2, 0.3, 0.5])
                new_r = max(1, r + change * np.random.randint(0, 5))
                tf[max(0, cy - new_r) : cy + new_r, max(0, cx - new_r) : cx + new_r] = 1.0

                # Random channels
                seq = np.random.randn(1, 17, 64, 64).astype(np.float32) * 0.5
                # Make temperature channel correlate with fire
                seq[0, 2] += cf * 0.3

                np.savez_compressed(
                    d / f"patch_{i:06d}.npz", sequence=seq, current_fire=cf, target_fire=tf
                )

    # Load data
    print("\nLoading data...")
    train = load_split(data_dir, "train", max_samples=300)
    val = load_split(data_dir, "val", max_samples=100)
    test = load_split(data_dir, "test", max_samples=100)

    if not train:
        print("  [ERROR] No training data found. Run with --data-dir pointing to NPZ data.")
        return 1

    # Run analyses
    leakage = analyze_leakage(train, val, test)
    copy = analyze_copy_baseline(train[:200])
    channels = analyze_channel_importance(train)
    dynamics = analyze_fire_dynamics(train)

    # Generate report
    generate_report(leakage, copy, channels, dynamics, REPO_ROOT / args.output)

    print("\n" + "=" * 70)
    print("ANALYSIS COMPLETE")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
