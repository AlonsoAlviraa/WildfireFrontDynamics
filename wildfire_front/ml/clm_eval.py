"""Shared CLM holdout evaluation (single model or ensemble soft-vote).

Architecture (lab ML rail — product ROI; no retrain)
----------------------------------------------------
Sits on ``product_facade`` + ``rank_reject_protocol`` (single product path)::

    features → calibrator → rank/reject (VAL thr freeze) → scorecard

* Dual rails: lab ML eval vs field_ops; IoU ≠ ROS; ``ml_product_go`` never auto-flips.
* Mix / temperature selection: VAL-only via ``SplitContext`` (protocol_rails).
  Conf reject thr is separate (VAL freeze **iter1 reject**); mask thr ≠ conf thr.
* Multi-fire honesty first-class: LOFO in-pack folds vs Tobarra **hard** fold
  under ``lofo_v1/tobarra_20240802`` — not ad-hoc ``v29_lofo_tobarra`` promote paths.
* Dead thrash closed: same-holdout ECE retune; Tobarra KEEP reopen of KILL weights.
* Field fusion stays OFF. LOFO / hard-fold eval is report/scorecard only.
"""

from __future__ import annotations

import contextlib
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Final

import numpy as np
import torch

from wildfire_front.ml.dataset import NpzWildfireDataset
from wildfire_front.ml.ndws_metrics import aggregate_ndws_evaluation, evaluate_sample
from wildfire_front.ml.product_facade import (
    DEAD_PATHS,
    DEFAULT_MULTI_FIRE,
    DEFAULT_PRODUCT_ID,
    DEFAULT_RAILS,
    DEFAULT_RANK_REJECT,
    ITER1_LOCKED_REJECT_THR,
    RECOMMENDED_LAB_SURFACE,
    TOBARRA_FIRE_ID,
    ProductFacadeError,
    assert_lab_rails,
    fire_honesty_tag,
    refuse_dead_path,
)
from wildfire_front.ml.protocol_rails import (
    LAB_ML_BANNER,
    SplitContext,
    assert_split_context,
    multi_fire_honesty_dict,
)
from wildfire_front.ml.rank_reject_protocol import (
    DEAD_PROTOCOL_PATHS,
    protocol_payload,
    refuse_dead_protocol_path,
)
from wildfire_front.ml.rank_reject_protocol import (
    lab_rails as rank_reject_lab_rails,
)
from wildfire_front.ml.rank_reject_protocol import (
    multi_fire_honesty as rank_reject_multi_fire,
)
from wildfire_front.ml.unet_train import UNetTrainConfig, build_model, prepare_input

# ── Product path identity (facade + rank/reject; no second conf path) ────────
_PIPELINE: Final = "features→calibrator→rank/reject→scorecard"
_FACADE: Final = "wildfire_front.ml.product_facade"
_RANK_REJECT: Final = "wildfire_front.ml.rank_reject_protocol"
_DEAD: Final = frozenset(DEAD_PATHS) | frozenset(DEAD_PROTOCOL_PATHS)

# ── Multi-fire honesty: first-class LOFO / Tobarra weight layout ─────────────
# In-pack LOFO folds (mask IoU stress) vs Tobarra hard transfer fold.
LOFO_IN_PACK_FOLDS: Final[tuple[str, ...]] = (
    "CARDOSO",
    "LA_ESTRELLA_ACOM1",
    "LA_ESTRELLA_ACOM2",
)
TOBARRA_HARD_FOLD: Final[str] = TOBARRA_FIRE_ID  # tobarra_20240802
# Legacy KEEP-or-KILL experiment dir (verdict KILL; not a product re-promote path).
LEGACY_TOBARRA_KILL_DIR: Final[str] = "v29_lofo_tobarra"
_WEIGHTS_NAME: Final[str] = "weights_pretrained_best.pt"


def clm_eval_lab_rails() -> dict[str, Any]:
    """Dual-product rails for CLM mask IoU eval (product_facade + rank_reject).

    ``ml_product_go`` promoted true (human authorize 2026-08-05); never *auto*-flip;
    field fusion OFF; freeze iter1 reject surface.
    """
    r = assert_lab_rails(DEFAULT_RAILS)
    base = r.as_dict()
    base.update(rank_reject_lab_rails())
    base.update(
        {
            "banner": LAB_ML_BANNER,
            "product_facade": _FACADE,
            "rank_reject_protocol": _RANK_REJECT,
            "pipeline": _PIPELINE,
            "tobarra_keep_reopen": False,
            "field_ops_ml_live_fusion": "OFF",
            "freeze_iter1_reject": True,
            "val_only_threshold_tune": True,
            "val_only_threshold_selection": True,
            "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
            "locked_reject_thr": float(ITER1_LOCKED_REJECT_THR),
            "dead_paths": sorted(_DEAD),
            "forbidden_thrash": sorted(_DEAD),
        }
    )
    return base


def clm_eval_rank_reject_surface() -> dict[str, Any]:
    """Shared facade rank/reject surface metadata (VAL thr freeze; no LOFO fit).

    Mask IoU thr used by ``evaluate_clm_weights`` is **not** conf reject thr;
    conf rank/reject stays on product_facade iter1_reject_only.
    """
    thr = float(ITER1_LOCKED_REJECT_THR)
    cfg = DEFAULT_RANK_REJECT
    return {
        "facade_class": "ClmEnsembleV34Facade",
        "product_facade": _FACADE,
        "product_id": DEFAULT_PRODUCT_ID,
        "pipeline": _PIPELINE,
        "rank_reject_protocol": _RANK_REJECT,
        "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
        "locked_reject_thr": thr,
        "thr_source": "val_iter1_reject_frozen",
        "val_only_threshold_selection": True,
        "fit_on_lofo": False,
        "rank_reject": {**cfg.as_dict(), "reject_thr": thr},
        "protocol": protocol_payload(locked_reject_thr=thr),
        "ml_product_go": True,
        "field_ops_allow_ml_live_in_fusion": False,
        "iou_is_not_ros": True,
        "note": (
            "CLM mask IoU eval reports under product_facade rails; "
            "conf rank/reject thr is VAL-only freeze iter1 reject. "
            "Mask thr for IoU is separate from conf reject thr."
        ),
    }


def _assert_dead_paths_closed() -> None:
    """Hard-seal ECE thrash + Tobarra KEEP reopen (architecture refuse)."""
    for dead in (
        "same_holdout_ece_retune",
        "tobarra_keep_reopen_same_recipe",
    ):
        try:
            refuse_dead_path(dead)
        except ProductFacadeError:
            pass  # expected: sealed
        else:
            raise ProductFacadeError(f"dead path still open: {dead!r}")
        # expected: sealed
        with contextlib.suppress(ValueError):
            refuse_dead_protocol_path(dead)


def _multi_fire_honesty_block(fold: str | None = None) -> dict[str, Any]:
    """First-class multi-fire honesty (facade + protocol; optional fold tag)."""
    out: dict[str, Any] = {
        **multi_fire_honesty_dict(),
        **rank_reject_multi_fire(),
        "facade": DEFAULT_MULTI_FIRE.as_dict(),
        "do_not_reopen_tobarra_keep": True,
        "lofo_first_class": True,
        "w3_external_first_class": True,
        "product_facade": _FACADE,
    }
    if fold is not None:
        out["fold"] = fire_honesty_tag(str(fold))
    return out


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
    fold: str | None = None,
    split_context: SplitContext | None = None,
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
    fold:
        Optional LOFO / multi-fire fold id (e.g. ``tobarra_20240802``). When set,
        attaches first-class multi-fire honesty tags (Tobarra hard, in-pack, …).
    split_context:
        Optional protocol rails context. Report/scorecard only on test/lofo/external;
        never used here to retune thr/mix (mix tune uses ``score_mix_from_cache``).
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

    if split_context is not None:
        if not isinstance(split_context, SplitContext):
            raise TypeError("split_context must be a SplitContext instance")
        assert_split_context(split_context)

    # Product path: dual rails + frozen rank/reject surface (no thrash reopen).
    _assert_dead_paths_closed()
    rails = clm_eval_lab_rails()
    rr_surface = clm_eval_rank_reject_surface()

    agg = aggregate_ndws_evaluation(sample_metrics)
    model_iou = _agg_float(agg, "model_iou")
    copy_iou = _agg_float(agg, "copy_baseline_iou")
    delta = _agg_float(agg, "improvement_vs_copy_iou", model_iou - copy_iou)
    out: dict[str, Any] = {
        "n_patches": n,
        "n_members": len(models),
        "weights": [str(w) for w in weight_list],
        "member_weights": mix,
        "temperatures": temps,
        "ensemble_mode": ensemble_mode if len(models) > 1 else "single",
        "in_channels": in_ch,
        "threshold": threshold,  # mask IoU thr — not conf reject thr
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
        # Dual-product rails + shared facade rank/reject (scorecard path).
        "product_id": DEFAULT_PRODUCT_ID,
        "product_facade": _FACADE,
        "pipeline": _PIPELINE,
        "rails": rails,
        "rank_reject_protocol": rr_surface,
        "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
        "locked_reject_thr": float(ITER1_LOCKED_REJECT_THR),
        "multi_fire_honesty": _multi_fire_honesty_block(fold),
    }
    if fold is not None:
        out["fold"] = str(fold)
        out["fire"] = fire_honesty_tag(str(fold))
    if split_context is not None:
        out["split_context"] = {
            "split": split_context.split,
            "action": split_context.action,
            "protocol": split_context.protocol,
        }
    return out


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
    # Shared product path: rails + rank/reject surface (VAL-only mix/thr already asserted).
    return {
        "n_patches": int(cache["n_patches"]),
        "n_members": n_m,
        "weights": list(cache["weights"]),
        "member_weights": list(mix),
        "temperatures": list(temps),
        "ensemble_mode": "mean_prob",
        "threshold": float(threshold),  # mask IoU thr — not conf reject thr
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
        "product_id": DEFAULT_PRODUCT_ID,
        "product_facade": _FACADE,
        "pipeline": _PIPELINE,
        "rails": clm_eval_lab_rails(),
        "rank_reject_protocol": clm_eval_rank_reject_surface(),
        "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
        "locked_reject_thr": float(ITER1_LOCKED_REJECT_THR),
        "split_context": {
            "split": split_context.split,
            "action": split_context.action,
            "protocol": split_context.protocol,
        },
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
    # VAL-only mix×mask-thr sweep; conf reject thr remains facade iter1 freeze.
    return {
        "best": best,
        "n_grid": len(rows),
        "rows_top": sorted(
            rows,
            key=lambda r: (r["improvement_vs_copy_iou"], r["model_iou"]),
            reverse=True,
        )[:8],
        "product_facade": _FACADE,
        "pipeline": _PIPELINE,
        "rails": clm_eval_lab_rails(),
        "rank_reject_protocol": clm_eval_rank_reject_surface(),
        "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
        "locked_reject_thr": float(ITER1_LOCKED_REJECT_THR),
        "split_context": {
            "split": ctx.split,
            "action": ctx.action,
            "protocol": ctx.protocol,
        },
        "note": (
            "Mix × mask-thr selection is VAL-only; conf reject thr is "
            "product_facade iter1_reject_only freeze (not retuned here)."
        ),
    }


def lofo_v1_root(root: Path) -> Path:
    """Canonical LOFO outputs root (first-class multi-fire layout)."""
    return Path(root) / "outputs" / "ml_eval" / "lofo_v1"


def lofo_fold_weight_path(root: Path, fold: str) -> Path:
    """Canonical LOFO fold checkpoint path under ``lofo_v1/<fold>/``."""
    return lofo_v1_root(root) / str(fold) / _WEIGHTS_NAME


def tobarra_hard_weight_path(root: Path) -> Path | None:
    """Resolve Tobarra hard-fold weights (first-class, not ad-hoc).

    Prefer ``lofo_v1/tobarra_20240802``; fall back to legacy ``v29_lofo_tobarra``
    only as KILL evidence — callers must not re-promote KEEP thrash.
    """
    primary = lofo_fold_weight_path(root, TOBARRA_HARD_FOLD)
    if primary.is_file():
        return primary
    legacy = Path(root) / "outputs" / "ml_eval" / LEGACY_TOBARRA_KILL_DIR / _WEIGHTS_NAME
    if legacy.is_file():
        return legacy
    return None


def default_lofo_weight_paths(
    root: Path,
    *,
    include_tobarra_hard: bool = True,
) -> list[Path]:
    """Canonical LOFO (+ optional Tobarra hard fold) checkpoint paths if present.

    Multi-fire honesty (architecture, not ad-hoc paths):
    * In-pack LOFO: CARDOSO, LA_ESTRELLA_ACOM1, LA_ESTRELLA_ACOM2.
    * Tobarra hard fold: first-class under ``lofo_v1/tobarra_20240802``;
      legacy ``v29_lofo_tobarra`` only if hard-fold weights are missing (KILL).
    * Does not open Tobarra KEEP re-promote hooks; field fusion stays OFF.
    """
    candidates: list[Path] = [lofo_fold_weight_path(root, fold) for fold in LOFO_IN_PACK_FOLDS]
    if include_tobarra_hard:
        hard = tobarra_hard_weight_path(root)
        if hard is not None:
            candidates.append(hard)
    seen: set[str] = set()
    out: list[Path] = []
    for p in candidates:
        if not p.is_file():
            continue
        key = str(p.resolve())
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def lofo_weight_multi_fire_catalog(root: Path) -> dict[str, Any]:
    """First-class multi-fire honesty inventory of LOFO / Tobarra weight paths.

    Surfaces Tobarra as a hard fold (not an ad-hoc ``v29`` script path) and
    tags in-pack LOFO folds. Sits on product_facade + rank_reject_protocol
    (report/scorecard only). Stamps ``ml_product_go`` true (promoted; no auto-flip);
    field fusion OFF; never re-opens Tobarra KEEP thrash of KILL weights.
    """
    _assert_dead_paths_closed()
    folds: list[dict[str, Any]] = []
    for fold in LOFO_IN_PACK_FOLDS:
        p = lofo_fold_weight_path(root, fold)
        tag = fire_honesty_tag(fold)
        folds.append(
            {
                "fold": fold,
                "path": str(p.as_posix()),
                "present": p.is_file(),
                "role": tag.get("role"),
                "hard": False,
                "honesty": tag,
                "board": "lofo_in_pack",
            }
        )

    hard_primary = lofo_fold_weight_path(root, TOBARRA_HARD_FOLD)
    legacy = Path(root) / "outputs" / "ml_eval" / LEGACY_TOBARRA_KILL_DIR / _WEIGHTS_NAME
    resolved = tobarra_hard_weight_path(root)
    hard_tag = fire_honesty_tag(TOBARRA_HARD_FOLD)
    uses_legacy = False
    if resolved is not None and resolved.is_file() and legacy.is_file():
        uses_legacy = resolved.resolve() == legacy.resolve()
    folds.append(
        {
            "fold": TOBARRA_HARD_FOLD,
            "path": str((resolved or hard_primary).as_posix()),
            "present": resolved is not None and resolved.is_file(),
            "role": hard_tag.get("role"),
            "hard": True,
            "honesty": hard_tag,
            "board": "lofo_in_pack",
            "canonical_path": str(hard_primary.as_posix()),
            "legacy_kill_path": str(legacy.as_posix()),
            "uses_legacy_kill_weights": uses_legacy,
            "tobarra_keep_reopen": False,
            "note": (
                "Tobarra = hard multi-fire honesty fold. Prefer lofo_v1 hard fold; "
                "v29 is legacy KILL evidence — do not re-promote KEEP thrash."
            ),
        }
    )
    # W3 external as first-class board section (report-only; no weight path here).
    w3_block = {
        "fires": list(DEFAULT_MULTI_FIRE.w3_external_fires),
        "role": DEFAULT_MULTI_FIRE.w3_role,
        "frozen_thr_and_cal": True,
        "board": "w3_external",
        "note": "W3 external multi-fire honesty — frozen thr/cal; not U1 ECE thrash.",
    }
    return {
        "lofo_root": str(lofo_v1_root(root).as_posix()),
        "in_pack_folds": list(LOFO_IN_PACK_FOLDS),
        "tobarra_hard_fold": TOBARRA_HARD_FOLD,
        "folds": folds,
        "default_weight_paths": [str(p.as_posix()) for p in default_lofo_weight_paths(root)],
        "w3_external": w3_block,
        "multi_fire_honesty": _multi_fire_honesty_block(),
        "product_id": DEFAULT_PRODUCT_ID,
        "product_facade": _FACADE,
        "pipeline": _PIPELINE,
        "rails": clm_eval_lab_rails(),
        "rank_reject_protocol": clm_eval_rank_reject_surface(),
        "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
        "locked_reject_thr": float(ITER1_LOCKED_REJECT_THR),
    }
