"""Shared CLM holdout evaluation (single model or ensemble soft-vote)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import torch

from wildfire_front.ml.dataset import NpzWildfireDataset
from wildfire_front.ml.ndws_metrics import aggregate_ndws_evaluation, evaluate_sample
from wildfire_front.ml.protocol_rails import SplitContext, assert_split_context
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


def _agg_float(agg: dict[str, Any], key: str, default: float = 0.0) -> float:
    """Extract a numeric field from aggregate_ndws_evaluation output."""
    v = agg.get(key, default)
    if isinstance(v, (int, float)):
        return float(v)
    return default


def _normalize_member_weights(n: int, member_weights: Sequence[float] | None) -> list[float] | None:
    if member_weights is None:
        return None
    if len(member_weights) != n:
        raise ValueError(f"member_weights length {len(member_weights)} != n_models {n}")
    w = np.asarray([float(x) for x in member_weights], dtype=np.float64)
    if np.any(w < 0) or float(w.sum()) <= 0:
        raise ValueError("member_weights must be non-negative with positive sum")
    w = w / w.sum()
    return [float(x) for x in w.tolist()]


@torch.no_grad()
def evaluate_clm_weights(
    weights: Path | Sequence[Path],
    data_dir: Path,
    *,
    max_patches: int = 400,
    threshold: float = 0.5,
    device: torch.device | str | None = None,
    ensemble_mode: str = "mean_prob",
    member_weights: Sequence[float] | None = None,
    temperatures: Sequence[float] | None = None,
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
    member_weights:
        Optional non-negative mix weights (normalized). Length = n members.
    temperatures:
        Optional per-member temperature scales (logit / T before soft-vote).
    """
    weight_list = (
        [Path(weights)] if isinstance(weights, (str, Path)) else [Path(w) for w in weights]
    )
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
    mix = _normalize_member_weights(len(models), member_weights)
    if temperatures is not None and len(temperatures) != len(models):
        raise ValueError(f"temperatures length {len(temperatures)} != n_models {len(models)}")
    temps = [float(t) for t in temperatures] if temperatures is not None else [1.0] * len(models)
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
        for mi, model in enumerate(models):
            try:
                logits = model(x, cur_b)
            except TypeError:
                logits = model(x)
            t = temps[mi]
            g = torch.sigmoid(logits / t) if abs(t - 1.0) > 1e-09 else torch.sigmoid(logits)
            growth_probs.append(g)
            abs_probs.append(torch.clamp(cur_b.unsqueeze(1) + g, 0.0, 1.0))

        if len(models) == 1:
            pred = abs_probs[0]
        elif ensemble_mode == "mean_abs":
            stacked = torch.stack(abs_probs, dim=0)
            if mix is None:
                pred = stacked.mean(dim=0)
            else:
                w_t = torch.tensor(mix, device=device, dtype=stacked.dtype).view(-1, 1, 1, 1, 1)
                pred = (stacked * w_t).sum(dim=0)
        else:
            stacked = torch.stack(growth_probs, dim=0)
            if mix is None:
                mean_g = stacked.mean(dim=0)
            else:
                w_t = torch.tensor(mix, device=device, dtype=stacked.dtype).view(-1, 1, 1, 1, 1)
                mean_g = (stacked * w_t).sum(dim=0)
            prev_b = cur_b.unsqueeze(1)
            pred = torch.clamp(prev_b + mean_g, 0.0, 1.0)

        pred_np = pred.squeeze().cpu().numpy()
        m = evaluate_sample(pred_np, cur.numpy(), tgt.numpy(), threshold=threshold)
        sample_metrics.append(m)

    agg = aggregate_ndws_evaluation(sample_metrics)
    model_iou = _agg_float(agg, "model_iou")
    copy_iou = _agg_float(agg, "copy_baseline_iou")
    delta = _agg_float(agg, "improvement_vs_copy_iou", model_iou - copy_iou)
    return {
        "n_patches": n,
        "n_members": len(models),
        "weights": [str(w) for w in weight_list],
        "member_weights": mix,
        "temperatures": temps,
        "ensemble_mode": ensemble_mode if len(models) > 1 else "single",
        "in_channels": in_ch,
        "threshold": threshold,
        "device": str(device),
        "model_iou": model_iou,
        "copy_baseline_iou": copy_iou,
        "improvement_vs_copy_iou": delta,
        "model_iou_growth": _agg_float(agg, "model_iou_growth"),
        "improvement_vs_dilated_copy_iou_growth": _agg_float(
            agg, "improvement_vs_dilated_copy_iou_growth"
        ),
        "improvement_vs_copy_iou_changed": _agg_float(agg, "improvement_vs_copy_iou_changed"),
        "model_iou_changed": _agg_float(agg, "model_iou_changed"),
        "aggregate": agg,
    }


@torch.no_grad()
def collect_member_growth_cache(
    weights: Sequence[Path],
    data_dir: Path,
    *,
    max_patches: int = 400,
    device: torch.device | str | None = None,
) -> dict[str, Any]:
    """Run each member once and cache per-patch growth probs + masks.

    Enables cheap offline mix / threshold sweeps without reloading models.
    """
    weight_list = [Path(w) for w in weights]
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

    growth: list[list[np.ndarray]] = [[] for _ in models]
    prevs: list[np.ndarray] = []
    tgts: list[np.ndarray] = []

    for i in range(n):
        seq, cur, tgt = ds[i]
        if seq.dim() == 3:
            seq = seq.unsqueeze(0)
        seq_b = seq.unsqueeze(0).to(device)
        cur_b = cur.unsqueeze(0).to(device)
        x = prepare_input(seq_b, cur_b)
        prevs.append(cur.numpy())
        tgts.append(tgt.numpy())
        for mi, model in enumerate(models):
            try:
                logits = model(x, cur_b)
            except TypeError:
                logits = model(x)
            growth[mi].append(torch.sigmoid(logits).squeeze().cpu().numpy())

    # free GPU/CPU model refs
    del models
    # str() works when torch is untyped (CI mypy --ignore-missing-imports)
    if "cuda" in str(device):
        torch.cuda.empty_cache()

    return {
        "n_patches": n,
        "n_members": len(weight_list),
        "weights": [str(w) for w in weight_list],
        "growth": growth,  # [member][patch] -> HxW float
        "prev": prevs,
        "target": tgts,
        "device": str(device),
    }


def _apply_temperature_to_prob(prob: np.ndarray, temperature: float) -> np.ndarray:
    """Rescale Bernoulli probs via logit / T (temperature scaling)."""
    t = float(temperature)
    if abs(t - 1.0) < 1e-9:
        return prob
    if t <= 0:
        raise ValueError(f"temperature must be > 0, got {t}")
    eps = 1e-6
    p = np.clip(prob, eps, 1.0 - eps)
    logit = np.log(p / (1.0 - p))
    return 1.0 / (1.0 + np.exp(-logit / t))


def score_mix_from_cache(
    cache: dict[str, Any],
    member_weights: Sequence[float] | None = None,
    *,
    split_context: SplitContext,
    threshold: float = 0.5,
    temperatures: Sequence[float] | None = None,
) -> dict[str, Any]:
    """Soft-vote growth probs from cache and score NDWS metrics.

    Optional per-member ``temperatures`` apply logit/T rescaling before the mix.

    ``split_context`` is **required** (protocol rails): tune_mix / temperatures
    only on VAL; test/lofo may report only.
    """
    if not isinstance(split_context, SplitContext):
        raise TypeError("split_context must be a SplitContext instance")
    assert_split_context(split_context)
    n_m = int(cache["n_members"])
    mix = _normalize_member_weights(n_m, member_weights)
    if mix is None:
        mix = [1.0 / n_m] * n_m
    if temperatures is not None and len(temperatures) != n_m:
        raise ValueError(f"temperatures length {len(temperatures)} != n_models {n_m}")
    temps = [float(t) for t in temperatures] if temperatures is not None else [1.0] * n_m
    growth = cache["growth"]
    prevs = cache["prev"]
    tgts = cache["target"]
    sample_metrics: list[dict] = []
    w = np.asarray(mix, dtype=np.float64)
    for i in range(int(cache["n_patches"])):
        layers = []
        for m in range(n_m):
            g = growth[m][i]
            if abs(temps[m] - 1.0) > 1e-9:
                g = _apply_temperature_to_prob(g, temps[m])
            layers.append(g)
        stacked = np.stack(layers, axis=0)
        mean_g = (stacked * w.reshape(-1, 1, 1)).sum(axis=0)
        prev = np.asarray(prevs[i], dtype=np.float64)
        pred = np.clip(prev + mean_g, 0.0, 1.0)
        sample_metrics.append(evaluate_sample(pred, prevs[i], tgts[i], threshold=threshold))
    agg = aggregate_ndws_evaluation(sample_metrics)
    model_iou = _agg_float(agg, "model_iou")
    copy_iou = _agg_float(agg, "copy_baseline_iou")
    delta = _agg_float(agg, "improvement_vs_copy_iou", model_iou - copy_iou)
    return {
        "n_patches": int(cache["n_patches"]),
        "n_members": n_m,
        "weights": list(cache["weights"]),
        "member_weights": list(mix),
        "temperatures": list(temps),
        "ensemble_mode": "mean_prob",
        "threshold": float(threshold),
        "model_iou": model_iou,
        "copy_baseline_iou": copy_iou,
        "improvement_vs_copy_iou": delta,
        "model_iou_growth": _agg_float(agg, "model_iou_growth"),
        "improvement_vs_dilated_copy_iou_growth": _agg_float(
            agg, "improvement_vs_dilated_copy_iou_growth"
        ),
        "improvement_vs_copy_iou_changed": _agg_float(agg, "improvement_vs_copy_iou_changed"),
        "model_iou_changed": _agg_float(agg, "model_iou_changed"),
        "aggregate": agg,
    }


def sweep_mix_threshold_from_cache(
    cache: dict[str, Any],
    mixes: Sequence[Sequence[float]],
    thresholds: Sequence[float] = (0.4, 0.45, 0.5, 0.55, 0.6),
    *,
    split_context: SplitContext,
) -> dict[str, Any]:
    """Exhaustive mix × threshold sweep on a growth cache; returns best by Δ then IoU.

    ``split_context`` is **required** (no silent VAL default on a test cache).
    Typical selection: ``SplitContext(split="val", action="tune_mix")``.
    """
    if not isinstance(split_context, SplitContext):
        raise TypeError("split_context must be a SplitContext instance")
    assert_split_context(split_context)
    ctx = split_context
    best: dict[str, Any] | None = None
    rows: list[dict[str, Any]] = []
    for mix in mixes:
        for thr in thresholds:
            m = score_mix_from_cache(cache, mix, split_context=ctx, threshold=float(thr))
            row = {
                "mix": list(m["member_weights"]),
                "threshold": float(thr),
                "model_iou": m["model_iou"],
                "improvement_vs_copy_iou": m["improvement_vs_copy_iou"],
                "model_iou_growth": m["model_iou_growth"],
            }
            rows.append(row)
            key = (row["improvement_vs_copy_iou"], row["model_iou"])
            if best is None or key > (
                best["improvement_vs_copy_iou"],
                best["model_iou"],
            ):
                best = row
    return {
        "best": best,
        "n_grid": len(rows),
        "rows_top": sorted(
            rows,
            key=lambda r: (r["improvement_vs_copy_iou"], r["model_iou"]),
            reverse=True,
        )[:8],
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
