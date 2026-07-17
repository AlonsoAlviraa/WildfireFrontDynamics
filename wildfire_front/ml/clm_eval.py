"""Shared CLM holdout evaluation (single model or ensemble soft-vote)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

import numpy as np
import torch

from wildfire_front.ml.dataset import NpzWildfireDataset
from wildfire_front.ml.ndws_metrics import aggregate_ndws_evaluation, evaluate_sample
from wildfire_front.ml.unet_train import UNetTrainConfig, build_model, prepare_input


def _load_model(weights: Path, in_channels: int, device: torch.device) -> torch.nn.Module:
    cfg = UNetTrainConfig(architecture="residual", model="small", target_mode="delta")
    model = build_model(cfg, in_channels=in_channels)
    state = torch.load(weights, map_location=device, weights_only=True)
    model.load_state_dict(state, strict=True)
    model.to(device)
    model.eval()
    return model


def _decode_delta(logits: torch.Tensor, prev: torch.Tensor) -> torch.Tensor:
    """prev + sigmoid(growth logits), clamped to [0, 1]."""
    prob = torch.sigmoid(logits)
    prev_b = prev if prev.dim() == 4 else prev.unsqueeze(1)
    return torch.clamp(prev_b + prob, 0.0, 1.0)


@torch.no_grad()
def evaluate_clm_weights(
    weights: Path | Sequence[Path],
    data_dir: Path,
    *,
    max_patches: int = 400,
    threshold: float = 0.5,
    device: torch.device | str | None = None,
    ensemble_mode: str = "mean_prob",
) -> dict[str, Any]:
    """Evaluate one checkpoint or soft-vote ensemble on a CLM NPZ split dir.

    Parameters
    ----------
    weights:
        Single path or list of checkpoint paths (ensemble).
    data_dir:
        Directory of ``*.npz`` patches (e.g. holdout_v1/test).
    ensemble_mode:
        ``mean_prob`` — average growth probabilities before decode (recommended).
        ``mean_abs`` — average absolute fire probabilities after decode.
    """
    weight_list = [Path(weights)] if isinstance(weights, (str, Path)) else [Path(w) for w in weights]
    for w in weight_list:
        if not w.is_file():
            raise FileNotFoundError(f"missing weights: {w}")

    if device is None:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(device)

    ds = NpzWildfireDataset(data_dir, augment=False)
    n = min(len(ds), max_patches)
    if n < 1:
        raise ValueError(f"no patches in {data_dir}")

    seq0, cur0, _ = ds[0]
    if seq0.dim() == 3:
        seq0 = seq0.unsqueeze(0)
    in_ch = seq0.shape[0] * seq0.shape[1] + 1

    models = [_load_model(w, in_ch, device) for w in weight_list]
    sample_metrics: list[dict] = []

    for i in range(n):
        seq, cur, tgt = ds[i]
        if seq.dim() == 3:
            seq = seq.unsqueeze(0)
        seq_b = seq.unsqueeze(0).to(device)
        cur_b = cur.unsqueeze(0).to(device)
        x = prepare_input(seq_b, cur_b)

        growth_probs: list[torch.Tensor] = []
        abs_probs: list[torch.Tensor] = []
        for model in models:
            try:
                logits = model(x, cur_b)
            except TypeError:
                logits = model(x)
            g = torch.sigmoid(logits)
            growth_probs.append(g)
            abs_probs.append(_decode_delta(logits, cur_b))

        if len(models) == 1:
            pred = abs_probs[0]
        elif ensemble_mode == "mean_abs":
            pred = torch.stack(abs_probs, dim=0).mean(dim=0)
        else:
            # mean growth probability then decode (single-change D2)
            mean_g = torch.stack(growth_probs, dim=0).mean(dim=0)
            prev_b = cur_b.unsqueeze(1)
            pred = torch.clamp(prev_b + mean_g, 0.0, 1.0)

        pred_np = pred.squeeze().cpu().numpy()
        m = evaluate_sample(pred_np, cur.numpy(), tgt.numpy(), threshold=threshold)
        sample_metrics.append(m)

    agg = aggregate_ndws_evaluation(sample_metrics)
    model_iou = float(agg.get("model_iou") or 0.0)
    copy_iou = float(agg.get("copy_baseline_iou") or 0.0)
    delta = float(agg.get("improvement_vs_copy_iou", model_iou - copy_iou))
    return {
        "n_patches": n,
        "n_members": len(models),
        "weights": [str(w) for w in weight_list],
        "ensemble_mode": ensemble_mode if len(models) > 1 else "single",
        "in_channels": in_ch,
        "threshold": threshold,
        "device": str(device),
        "model_iou": model_iou,
        "copy_baseline_iou": copy_iou,
        "improvement_vs_copy_iou": delta,
        "model_iou_growth": float(agg.get("model_iou_growth") or 0.0),
        "improvement_vs_dilated_copy_iou_growth": float(
            agg.get("improvement_vs_dilated_copy_iou_growth") or 0.0
        ),
        "improvement_vs_copy_iou_changed": float(
            agg.get("improvement_vs_copy_iou_changed") or 0.0
        ),
        "model_iou_changed": float(agg.get("model_iou_changed") or 0.0),
        "aggregate": agg,
    }


def default_lofo_weight_paths(root: Path) -> list[Path]:
    """Canonical LOFO + Tobarra checkpoint paths if present."""
    candidates = [
        root / "outputs" / "ml_eval" / "lofo_v1" / "CARDOSO" / "weights_pretrained_best.pt",
        root
        / "outputs"
        / "ml_eval"
        / "lofo_v1"
        / "LA_ESTRELLA_ACOM1"
        / "weights_pretrained_best.pt",
        root
        / "outputs"
        / "ml_eval"
        / "lofo_v1"
        / "LA_ESTRELLA_ACOM2"
        / "weights_pretrained_best.pt",
        root / "outputs" / "ml_eval" / "v29_lofo_tobarra" / "weights_pretrained_best.pt",
    ]
    return [p for p in candidates if p.is_file()]
