#!/usr/bin/env python3
"""Análisis científico comparativo de curvas de entrenamiento v10 vs v11.

Genera gráficas:
1. Curvas de loss (train + val) superpuestas v10 vs v11
2. Learning rate schedule overlay con marcador de best epoch
3. Gap analysis (val_loss - train_loss) a lo largo del entrenamiento
4. Métricas de segmentación (IoU/Recall/Precision) si están disponibles

Uso:
    python scripts/analyze_training_curves.py
    python scripts/analyze_training_curves.py --v10 kaggle_outputs_v10/training_history.json --v11 kaggle_outputs_v11/training_history.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # no GUI
import matplotlib.pyplot as plt
import numpy as np

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "docs" / "analysis_plots"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

V10_HISTORY = PROJECT_ROOT / "kaggle_outputs_v10" / "training_history.json"
V10_SUMMARY = PROJECT_ROOT / "kaggle_outputs_v10" / "training_summary.json"
V11_HISTORY = PROJECT_ROOT / "kaggle_outputs_v11" / "training_history.json"
V11_SUMMARY = PROJECT_ROOT / "kaggle_outputs_v11" / "training_summary.json"
V11_EVAL = PROJECT_ROOT / "kaggle_outputs_v11" / "evaluation_metrics.json"


def load_history(path: Path) -> list[dict] | None:
    if not path.exists():
        print(f"  WARNING: {path} not found")
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_summary(path: Path) -> dict | None:
    if not path.exists():
        print(f"  WARNING: {path} not found")
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def extract_arrays(history: list[dict]) -> tuple[np.ndarray, ...]:
    """Returns (epochs, train_loss, val_loss, gap)."""
    epochs = np.array([h["epoch"] for h in history])
    train = np.array([h["train_loss"] for h in history])
    val = np.array([h["val_loss"] for h in history])
    gap = val - train
    return epochs, train, val, gap


# ---------------------------------------------------------------------------
# Plot 1: Loss curves comparison
# ---------------------------------------------------------------------------
def plot_loss_curves(h10, h11, outdir: Path):
    fig, ax = plt.subplots(figsize=(12, 7))

    if h10:
        e10, tr10, vl10, _ = extract_arrays(h10)
        ax.plot(e10, tr10, "o--", color="#2196F3", alpha=0.7, label="v10 Train Loss")
        ax.plot(e10, vl10, "s-", color="#2196F3", linewidth=2.5, label="v10 Val Loss")
        best10 = np.argmin(vl10)
        ax.axvline(e10[best10], color="#2196F3", linestyle=":", alpha=0.5)
        ax.annotate(f"v10 best (epoch {e10[best10]})",
                    xy=(e10[best10], vl10[best10]),
                    xytext=(e10[best10] + 1.5, vl10[best10] + 0.02),
                    fontsize=9, color="#2196F3",
                    arrowprops=dict(arrowstyle="->", color="#2196F3"))

    if h11:
        e11, tr11, vl11, _ = extract_arrays(h11)
        ax.plot(e11, tr11, "o--", color="#F44336", alpha=0.7, label="v11 Train Loss")
        ax.plot(e11, vl11, "s-", color="#F44336", linewidth=2.5, label="v11 Val Loss")
        best11 = np.argmin(vl11)
        ax.axvline(e11[best11], color="#F44336", linestyle=":", alpha=0.5)
        ax.annotate(f"v11 best (epoch {e11[best11]})",
                    xy=(e11[best11], vl11[best11]),
                    xytext=(e11[best11] + 1.5, vl11[best11] - 0.03),
                    fontsize=9, color="#F44336",
                    arrowprops=dict(arrowstyle="->", color="#F44336"))

    ax.set_xlabel("Epoch", fontsize=13)
    ax.set_ylabel("Loss (Focal BCE + Physics)", fontsize=13)
    ax.set_title("Curvas de Entrenamiento: v10 (LR=1e-4) vs v11 (LR=5e-5)", fontsize=14, fontweight="bold")
    ax.legend(fontsize=11, loc="upper right")
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0.20, 0.50)

    fig.tight_layout()
    path = outdir / "01_loss_curves_v10_vs_v11.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✓ Saved {path}")


# ---------------------------------------------------------------------------
# Plot 2: Gap analysis (val - train)
# ---------------------------------------------------------------------------
def plot_gap_analysis(h10, h11, outdir: Path):
    fig, ax = plt.subplots(figsize=(12, 6))

    if h10:
        e10, _, _, g10 = extract_arrays(h10)
        ax.plot(e10, g10, "s-", color="#2196F3", linewidth=2, markersize=8, label="v10 Gap (val−train)")
        ax.axhline(0, color="gray", linestyle="--", alpha=0.3)

    if h11:
        e11, _, _, g11 = extract_arrays(h11)
        ax.plot(e11, g11, "s-", color="#F44336", linewidth=2, markersize=8, label="v11 Gap (val−train)")

    ax.axhspan(-0.02, 0.02, alpha=0.1, color="green", label="Zona ideal (|gap|<0.02)")
    ax.set_xlabel("Epoch", fontsize=13)
    ax.set_ylabel("Gap = val_loss − train_loss", fontsize=13)
    ax.set_title("Análisis de Gap: ¿Overfitting o Underfitting?", fontsize=14, fontweight="bold")
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)

    # Add interpretation zones
    ax.axhspan(0.05, 0.5, alpha=0.05, color="red")
    ax.text(1, 0.06, "Overfitting zone", fontsize=9, color="red", alpha=0.7)

    fig.tight_layout()
    path = outdir / "02_gap_analysis.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✓ Saved {path}")


# ---------------------------------------------------------------------------
# Plot 3: LR schedule overlay
# ---------------------------------------------------------------------------
def plot_lr_schedule(h10, h11, s10, s11, outdir: Path):
    fig, ax = plt.subplots(figsize=(12, 6))

    def reconstruct_lr(history, peak_lr, warmup, total_epochs=50):
        """Reconstruct LR schedule from config."""
        epochs = np.array([h["epoch"] for h in history])
        lrs = []
        for e in epochs:
            if e <= warmup:
                lr = peak_lr * 0.1 + (peak_lr * 0.9) * (e / warmup)
            else:
                progress = (e - warmup) / max(1, total_epochs - warmup)
                lr = 1e-6 + 0.5 * (peak_lr - 1e-6) * (1 + np.cos(np.pi * progress))
            lrs.append(lr)
        return epochs, np.array(lrs)

    if h10:
        e10, lr10 = reconstruct_lr(h10, peak_lr=1e-4, warmup=3)
        ax.plot(e10, lr10, "o-", color="#2196F3", linewidth=2, markersize=6, label="v10 LR (peak=1e-4, warmup=3)")
        best10 = np.argmin([h["val_loss"] for h in h10])
        ax.axvline(e10[best10], color="#2196F3", linestyle=":", alpha=0.5)

    if h11:
        peak = s11.get("v11_config", {}).get("peak_lr", 5e-5) if s11 else 5e-5
        warmup = s11.get("v11_config", {}).get("warmup_epochs", 5) if s11 else 5
        e11, lr11 = reconstruct_lr(h11, peak_lr=peak, warmup=warmup)
        ax.plot(e11, lr11, "s-", color="#F44336", linewidth=2, markersize=6, label=f"v11 LR (peak={peak:.0e}, warmup={warmup})")
        best11 = np.argmin([h["val_loss"] for h in h11])
        ax.axvline(e11[best11], color="#F44336", linestyle=":", alpha=0.5)

    ax.set_xlabel("Epoch", fontsize=13)
    ax.set_ylabel("Learning Rate", fontsize=13)
    ax.set_title("Learning Rate Schedule: v10 vs v11", fontsize=14, fontweight="bold")
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)
    ax.set_yscale("log")

    fig.tight_layout()
    path = outdir / "03_lr_schedule.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✓ Saved {path}")


# ---------------------------------------------------------------------------
# Plot 4: Segmentation metrics (v11 only, new feature)
# ---------------------------------------------------------------------------
def plot_segmentation_metrics(eval_path: Path, outdir: Path):
    if not eval_path.exists():
        print(f"  SKIP: {eval_path} not found (v11 may not have completed seg eval)")
        return

    with open(eval_path, encoding="utf-8") as f:
        metrics = json.load(f)

    # Extract micro metrics
    labels = []
    values = []
    for key in ["micro_iou", "micro_dice", "micro_precision", "micro_recall"]:
        if key in metrics:
            labels.append(key.replace("micro_", "").upper())
            values.append(metrics[key])

    if not labels:
        print("  SKIP: no micro metrics found in evaluation_metrics.json")
        return

    fig, ax = plt.subplots(figsize=(8, 6))
    colors = ["#4CAF50", "#2196F3", "#FF9800", "#F44336"]
    bars = ax.bar(labels, values, color=colors[:len(labels)], edgecolor="black", linewidth=0.5)

    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                f"{val:.3f}", ha="center", va="bottom", fontsize=12, fontweight="bold")

    ax.set_ylim(0, 1.0)
    ax.set_ylabel("Score", fontsize=13)
    ax.set_title("Métricas de Segmentación v11 (TEST set, leak-free)", fontsize=14, fontweight="bold")
    ax.axhline(0.5, color="gray", linestyle="--", alpha=0.3, label="Random baseline")
    ax.axhline(0.7, color="green", linestyle="--", alpha=0.3, label="Buen nivel (>0.7)")
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3, axis="y")

    fig.tight_layout()
    path = outdir / "04_segmentation_metrics_v11.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✓ Saved {path}")


# ---------------------------------------------------------------------------
# Plot 5: Summary comparison bar chart
# ---------------------------------------------------------------------------
def plot_summary_comparison(s10, s11, outdir: Path):
    if not s10 or not s11:
        print("  SKIP: missing summary files for comparison")
        return

    metrics = {
        "Best Val Loss": (s10.get("best_val_loss"), s11.get("best_val_loss")),
        "Test Loss": (s10.get("test_loss"), s11.get("test_loss")),
    }
    if s10.get("meta_labeler_test_acc") and s11.get("meta_labeler_test_acc"):
        metrics["Meta-Labeler Acc"] = (s10["meta_labeler_test_acc"], s11["meta_labeler_test_acc"])

    labels = list(metrics.keys())
    v10_vals = [m[0] for m in metrics.values()]
    v11_vals = [m[1] for m in metrics.values()]

    x = np.arange(len(labels))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 6))
    bars1 = ax.bar(x - width / 2, v10_vals, width, label="v10", color="#2196F3", edgecolor="black", linewidth=0.5)
    bars2 = ax.bar(x + width / 2, v11_vals, width, label="v11", color="#F44336", edgecolor="black", linewidth=0.5)

    for bars in [bars1, bars2]:
        for bar in bars:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.005,
                    f"{bar.get_height():.4f}", ha="center", va="bottom", fontsize=10)

    ax.set_ylabel("Valor", fontsize=13)
    ax.set_title("Comparativa de Métricas Clave: v10 vs v11", fontsize=14, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=11)
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3, axis="y")

    fig.tight_layout()
    path = outdir / "05_summary_comparison.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✓ Saved {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Análisis comparativo v10 vs v11")
    parser.add_argument("--v10", type=Path, default=V10_HISTORY, help="Path to v10 training_history.json")
    parser.add_argument("--v11", type=Path, default=V11_HISTORY, help="Path to v11 training_history.json")
    parser.add_argument("--outdir", type=Path, default=OUTPUT_DIR, help="Output directory for plots")
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("ANÁLISIS COMPARATIVO v10 vs v11")
    print("=" * 60)

    print("\nCargando datos...")
    h10 = load_history(args.v10)
    h11 = load_history(args.v11)
    s10 = load_summary(V10_SUMMARY)
    s11 = load_summary(V11_SUMMARY)

    print("\nGenerando graficas...")
    if h10 or h11:
        plot_loss_curves(h10, h11, args.outdir)
        plot_gap_analysis(h10, h11, args.outdir)
        plot_lr_schedule(h10, h11, s10, s11, args.outdir)
    else:
        print("  SKIP: no history data available")

    plot_segmentation_metrics(V11_EVAL, args.outdir)
    plot_summary_comparison(s10, s11, args.outdir)

    # Print text summary
    print("\n" + "=" * 60)
    print("RESUMEN COMPARATIVO")
    print("=" * 60)
    if s10 and s11:
        print(f"\n{'Métrica':<30} {'v10':>10} {'v11':>10} {'Δ':>10}")
        print("-" * 62)
        for key in ["best_val_loss", "test_loss", "meta_labeler_test_acc", "best_pretrain_epoch"]:
            v10v = s10.get(key, "N/A")
            v11v = s11.get(key, "N/A")
            if isinstance(v10v, (int, float)) and isinstance(v11v, (int, float)):
                delta = v11v - v10v
                delta_str = f"{delta:+.4f}" if abs(delta) > 0.0001 else f"{delta:+.1f}"
            else:
                delta_str = "—"
            print(f"  {key:<28} {str(v10v):>10} {str(v11v):>10} {delta_str:>10}")

    if h10 and h11:
        best10_epoch = min(h10, key=lambda x: x["val_loss"])
        best11_epoch = min(h11, key=lambda x: x["val_loss"])
        print(f"\nBest epoch v10: {best10_epoch['epoch']} (val_loss={best10_epoch['val_loss']:.5f})")
        print(f"Best epoch v11: {best11_epoch['epoch']} (val_loss={best11_epoch['val_loss']:.5f})")
        print(f"Total epochs v10: {len(h10)}")
        print(f"Total epochs v11: {len(h11)}")

    print(f"\n✅ Gráficas guardadas en: {args.outdir}")
    print("\n=== ANÁLISIS COMPLETADO ===")


if __name__ == "__main__":
    main()