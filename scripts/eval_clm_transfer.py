#!/usr/bin/env python3
"""M2 — Honest CLM transfer evaluation of production / candidate weights.

Loads NPZ patches from a CLM directory (if present), runs a residual U-Net
checkpoint with the same protocol metrics as NDWS, and writes a report.
If weights or data are missing, writes an explicit NO-GO with reasons.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    import torch
    from torch.utils.data import DataLoader

    from wildfire_front.ml.dataset import NpzWildfireDataset
    from wildfire_front.ml.ndws_metrics import aggregate_ndws_evaluation, evaluate_sample
    from wildfire_front.ml.unet_train import UNetTrainConfig, build_model, prepare_input

    weight_candidates = [
        ROOT / "models" / "production" / "weights_v21_best.pt",
        ROOT / "kaggle_outputs_v21" / "weights_pretrained_best.pt",
        ROOT / "kaggle_outputs_v23_clean12" / "weights_pretrained_best.pt",
    ]

    # Prefer held-out splits; fall back to train with explicit protocol label.
    clm_dir = None
    clm_split_label = "unknown"
    base = ROOT / "artifacts" / "clm_ndws_patches"
    for sub in ("test", "val", "train"):
        d = base / sub
        if d.is_dir() and list(d.glob("*.npz")):
            clm_dir = d
            clm_split_label = sub
            break
    if clm_dir is None and base.is_dir() and list(base.glob("*.npz")):
        clm_dir = base
        clm_split_label = "flat"

    weights = next((p for p in weight_candidates if p.is_file()), None)
    out_dir = ROOT / "outputs" / "ml_eval"
    out_dir.mkdir(parents=True, exist_ok=True)

    report: dict = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "leap_id": "M2",
        "hypothesis": "H7 honest CLM transfer",
        "protocol": f"clm_npz_{clm_split_label}_cap400",
    }

    if clm_dir is None or weights is None:
        report.update(
            {
                "status": "NO_GO",
                "go": False,
                "reason": "missing_data_or_weights",
                "clm_dir": str(clm_dir) if clm_dir else None,
                "weights": str(weights) if weights else None,
                "note": "Cannot claim transfer; document absence.",
            }
        )
        path = out_dir / "clm_transfer_report.json"
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 0

    ds = NpzWildfireDataset(clm_dir, augment=False)
    # Cap for local CPU
    n = min(len(ds), 400)
    if n < 10:
        report.update({"status": "NO_GO", "go": False, "reason": "too_few_patches", "n": n})
        (out_dir / "clm_transfer_report.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        print(report)
        return 0

    # Infer channels from first sample
    seq0, cur0, _ = ds[0]
    # sequence shape (T,C,H,W) or (C,H,W)
    if seq0.dim() == 3:
        seq0 = seq0.unsqueeze(0)
    in_ch = seq0.shape[0] * seq0.shape[1] + 1
    cfg = UNetTrainConfig(architecture="residual", model="small", target_mode="delta")
    model = build_model(cfg, in_channels=in_ch)
    state = torch.load(weights, map_location="cpu", weights_only=True)
    # If channel mismatch, NO-GO
    try:
        model.load_state_dict(state, strict=True)
    except Exception as exc:
        report.update(
            {
                "status": "NO_GO",
                "go": False,
                "reason": "weight_shape_mismatch",
                "error": str(exc),
                "in_channels": in_ch,
                "weights": str(weights),
                "clm_dir": str(clm_dir),
                "n_patches": n,
            }
        )
        (out_dir / "clm_transfer_report.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        print(json.dumps(report, indent=2))
        return 0

    model.eval()
    device = torch.device("cpu")
    model.to(device)

    sample_metrics = []
    copy_ious = []
    with torch.no_grad():
        for i in range(n):
            seq, cur, tgt = ds[i]
            if seq.dim() == 3:
                seq = seq.unsqueeze(0)
            seq_b = seq.unsqueeze(0).to(device)
            cur_b = cur.unsqueeze(0).to(device)
            x = prepare_input(seq_b, cur_b)
            # residual models need prev_fire
            try:
                logits = model(x, cur_b)
            except TypeError:
                logits = model(x)
            if cfg.target_mode == "delta":
                # decode absolute = prev + growth
                prob = torch.sigmoid(logits)
                # if delta training, model outputs growth logits
                pred = torch.clamp(cur_b.unsqueeze(1) + prob, 0.0, 1.0)
            else:
                pred = torch.sigmoid(logits)
            pred_np = pred.squeeze().cpu().numpy()
            cur_np = cur.numpy()
            tgt_np = tgt.numpy()
            # API: prediction, prev_fire, target_fire
            m = evaluate_sample(pred_np, cur_np, tgt_np, threshold=0.5)
            sample_metrics.append(m)

    agg = aggregate_ndws_evaluation(sample_metrics)
    model_iou = float(agg.get("model_iou") or agg.get("model_full", {}).get("micro_iou") or 0.0)
    copy_iou = float(agg.get("copy_baseline_iou") or agg.get("copy_full", {}).get("micro_iou") or 0.0)
    delta = float(agg.get("improvement_vs_copy_iou", model_iou - copy_iou))
    go = delta is not None and delta > 0

    report.update(
        {
            "status": "GO" if go else "NO_GO",
            "go": go,
            "weights": str(weights),
            "clm_dir": str(clm_dir),
            "n_patches": n,
            "in_channels": in_ch,
            "model_iou": model_iou,
            "copy_iou": copy_iou,
            "improvement_vs_copy_iou": delta,
            "aggregate": agg if isinstance(agg, dict) else str(agg),
            "clm_split": clm_split_label,
            "verdict_es": (
                f"El modelo supera copy en CLM split={clm_split_label} "
                f"(Δ={delta:.3f}). "
                + (
                    "OJO: split train no es holdout puro."
                    if clm_split_label == "train"
                    else "Split preferente test/val."
                )
                if go
                else "NO transfer defendible: no supera copy o datos incompatibles."
            ),
        }
    )
    path = out_dir / "clm_transfer_report.json"
    path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: report[k] for k in report if k != "aggregate"}, indent=2, default=str))
    print("Wrote", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
