#!/usr/bin/env python3
"""Run the single seed/config ``lab_scratch`` retrain for the mega-goal."""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.ml.dataset import NpzWildfireDataset  # noqa: E402
from wildfire_front.ml.unet_train import (  # noqa: E402
    UNetTrainConfig,
    build_model,
    model_forward,
    prepare_input,
    run_training,
)
from scripts.run_latam_au_complete_model_iou import (  # noqa: E402
    DEFAULT_EVENT_IDS,
    EMSR_PACK_SPECS,
    OOD_GROWTH_THRESHOLD,
    binary_iou,
    decode_complete_proxy_pred,
    eval_pack,
    fire_growth_ring,
    iter_usable_eval_tiles,
    pack_dir_for,
)


DEFAULT_DATA = ROOT / "artifacts" / "mega_goal_model" / "lab_scratch_dataset"
DEFAULT_INIT = ROOT / "models" / "clm_ensemble" / "weights_multi_if.pt"
DEFAULT_OUT = ROOT / "outputs" / "ml_eval" / "mega_goal_model" / "lab_scratch_growth_run"
CONSERVATIVE_OUT = ROOT / "outputs" / "ml_eval" / "mega_goal_model" / "lab_scratch_conservative"
FROZEN_OUT = ROOT / "outputs" / "ml_eval" / "mega_goal_model" / "lab_scratch_frozen"


def _prepare_growth_init(source: Path, destination: Path) -> Path:
    """Extract the standard U-Net backbone from the legacy residual wrapper."""
    state = torch.load(source, map_location="cpu", weights_only=True)
    prefix = "backbone."
    if not state or not all(str(key).startswith(prefix) for key in state):
        raise ValueError("expected a ResidualWildfireUNetSmall state_dict")
    destination.parent.mkdir(parents=True, exist_ok=True)
    torch.save({str(key)[len(prefix) :]: value for key, value in state.items()}, destination)
    return destination


def _as_btcwh(sequence: torch.Tensor) -> torch.Tensor:
    if sequence.ndim == 4:
        return sequence.unsqueeze(0)
    if sequence.ndim == 5:
        return sequence
    if sequence.ndim == 3:
        return sequence.unsqueeze(0).unsqueeze(0)
    raise ValueError(f"bad sequence ndim {sequence.ndim}")


def frozen_ring_decode_loss(
    logits: torch.Tensor,
    prev: torch.Tensor,
    target: torch.Tensor,
    *,
    growth_threshold: float = OOD_GROWTH_THRESHOLD,
    margin: float = 0.25,
    fp_weight: float = 4.0,
) -> torch.Tensor:
    """Align residual logits with frozen decode.

    True-ring pixels must reach the frozen growth logit. False-ring pixels must
    not receive a *positive residual* over copy. A threshold hinge on P is
    silent at residual init (copy logit ≈ −9.2 on unburned), so it never
    penalizes backbone leak until P already crosses the decode gate.
    """
    if logits.ndim == 4:
        logits = logits[:, 0]
    gthr_logit = math.log(growth_threshold / (1.0 - growth_threshold))
    ring = torch.zeros_like(prev, dtype=torch.bool)
    prev_np = prev.detach().cpu().numpy()
    for i in range(prev.shape[0]):
        ring[i] = torch.from_numpy(fire_growth_ring(prev_np[i])).to(prev.device)
    growth = (target >= 0.5) & (prev < 0.5)
    true_ring = ring & growth
    false_ring = ring & ~growth
    copy_logits = torch.logit(prev.clamp(1e-4, 1.0 - 1e-4))
    parts: list[torch.Tensor] = []
    if bool(true_ring.any()):
        parts.append(F.relu(gthr_logit + margin - logits[true_ring]).mean())
    if bool(false_ring.any()):
        leak = F.relu(logits[false_ring] - copy_logits[false_ring])
        parts.append(float(fp_weight) * leak.mean())
    if not parts:
        return logits.sum() * 0.0
    loss = parts[0]
    for extra in parts[1:]:
        loss = loss + extra
    return loss


def _batch_eval_tiles(tiles: list[dict]) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    seqs = []
    curs = []
    tgts = []
    for tile in tiles:
        seq = np.asarray(tile["seq"], dtype=np.float32)
        if seq.ndim == 5:
            seq = seq[0]
        seqs.append(torch.from_numpy(seq))
        curs.append(torch.from_numpy(np.asarray(tile["prev"], dtype=np.float32)))
        tgts.append(torch.from_numpy(np.asarray(tile["target"], dtype=np.float32)))
    return torch.stack(seqs), torch.stack(curs), torch.stack(tgts)


def run_frozen_decode_finetune(
    *,
    data_dir: Path,
    init_weights: Path,
    output_dir: Path,
    epochs: int = 12,
    batch_size: int = 8,
    lr: float = 1e-4,
    fp_weight: float = 4.0,
    head_only: bool = False,
) -> dict:
    """Fine-tune residual weights on the exact complete-proxy tiles; val is frozen decode Δ."""
    del data_dir  # protocol tiles come from the packs, not the mixed CLM NPZ pool
    if head_only:
        raise ValueError("MET frozen-decode trains the full residual; head_only is not a search knob")
    output_dir.mkdir(parents=True, exist_ok=True)
    data_root = ROOT / "data" / "open_if" / "latam_au"
    tiles = iter_usable_eval_tiles(data_root, event_ids=DEFAULT_EVENT_IDS)
    if not tiles:
        raise RuntimeError("no usable complete-proxy tiles for frozen-decode finetune")
    seq_all, cur_all, tgt_all = _batch_eval_tiles(tiles)

    device = torch.device("cpu")
    cfg = UNetTrainConfig(architecture="residual", model="small", target_mode="delta")
    model = build_model(cfg, in_channels=18)
    state = torch.load(init_weights, map_location=device, weights_only=True)
    model.load_state_dict(state, strict=True)
    model.to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)

    def _forward_batch(seq: torch.Tensor, cur: torch.Tensor) -> torch.Tensor:
        if seq.ndim == 4:
            seq = seq.unsqueeze(1)
        x = prepare_input(seq, cur)
        return model_forward(model, x, cur, "residual")

    def _val_delta() -> float:
        model.eval()
        pair_deltas: list[float] = []
        for event_id in DEFAULT_EVENT_IDS:
            spec = EMSR_PACK_SPECS[event_id]
            pack = pack_dir_for(data_root, spec)
            row = eval_pack(
                event_id,
                pack,
                model,
                device,
                thr=0.5,
                architecture="residual",
                target_mode="delta",
                growth_threshold=OOD_GROWTH_THRESHOLD,
                require_growth_ring=True,
            )
            for pair in row.get("pairs") or []:
                if pair.get("pair_class") == "usable" and pair.get("delta_vs_copy") is not None:
                    pair_deltas.append(float(pair["delta_vs_copy"]))
        model.train()
        return float(sum(pair_deltas) / len(pair_deltas)) if pair_deltas else 0.0

    history: list[dict] = []
    best = -1e9
    best_epoch = -1
    best_path = output_dir / "weights_pretrained_best.pt"
    n = seq_all.shape[0]
    model.train()
    for epoch in range(1, epochs + 1):
        order = torch.randperm(n)
        losses: list[float] = []
        for start in range(0, n, batch_size):
            idx = order[start : start + batch_size]
            seq = seq_all[idx].to(device)
            cur = cur_all[idx].to(device)
            tgt = tgt_all[idx].to(device)
            logits = _forward_batch(seq, cur)
            loss = frozen_ring_decode_loss(logits, cur, tgt, fp_weight=fp_weight)
            opt.zero_grad()
            loss.backward()
            opt.step()
            losses.append(float(loss.item()))
        val_delta = _val_delta()
        row = {
            "epoch": epoch,
            "train_loss": float(sum(losses) / max(len(losses), 1)),
            "val_delta_vs_copy": val_delta,
            "n_tiles": n,
        }
        history.append(row)
        print(
            f"frozen-decode epoch {epoch}/{epochs} loss={row['train_loss']:.4f} "
            f"val_delta={val_delta:+.6f}",
            flush=True,
        )
        if val_delta > best:
            best = val_delta
            best_epoch = epoch
            torch.save(model.state_dict(), best_path)
    return {
        "best_epoch": best_epoch,
        "best_val_delta_vs_copy": best,
        "history": history,
        "architecture": "residual",
        "target_mode": "delta",
        "decode": "frozen_complete_proxy",
        "loss": "true_ring_hinge_plus_false_ring_residual_leak",
        "fp_weight": fp_weight,
        "head_only": head_only,
        "n_train_tiles": n,
        "growth_threshold": OOD_GROWTH_THRESHOLD,
        "output_weights": str(best_path),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--init-weights", type=Path, default=DEFAULT_INIT)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument(
        "--conservative",
        action="store_true",
        help="One-seed conservative residual-incompatible standard+delta run (pos_weight=1).",
    )
    parser.add_argument(
        "--frozen-decode",
        action="store_true",
        help="Fine-tune residual product weights; val uses frozen 8-ring k=1 @ 0.90 decode.",
    )
    args = parser.parse_args(argv)
    if args.frozen_decode:
        args.init_weights = DEFAULT_INIT
        args.output_dir = FROZEN_OUT
    elif args.output_dir is None:
        if args.conservative:
            args.output_dir = CONSERVATIVE_OUT
        else:
            args.output_dir = DEFAULT_OUT

    manifest_path = args.data_dir / "MANIFEST.json"
    if not manifest_path.is_file() or not args.init_weights.is_file():
        print("missing lab_scratch dataset manifest or init weights", file=sys.stderr)
        return 1
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if int(manifest.get("n_usable_pairs") or 0) != 4:
        print("refusing retrain: dataset must contain exactly four usable pairs", file=sys.stderr)
        return 2

    if args.frozen_decode:
        summary = run_frozen_decode_finetune(
            data_dir=args.data_dir,
            init_weights=DEFAULT_INIT,
            output_dir=FROZEN_OUT,
        )
        record = {
            "schema": "wfd_latam_au_lab_scratch_run_v1",
            "as_of_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "label": "lab_scratch_frozen_decode",
            "seed": 42,
            "one_seed_one_config": True,
            "data_manifest": str(manifest_path.relative_to(ROOT)).replace("\\", "/"),
            "init_weights": "models/clm_ensemble/weights_multi_if.pt",
            "output_weights": "weights_pretrained_best.pt",
            "config": {
                "epochs": 12,
                "batch_size": 8,
                "lr": 1e-4,
                "loss": "true_ring_hinge_plus_false_ring_residual_leak",
                "fp_weight": 4.0,
                "head_only": False,
                "architecture": "residual",
                "target_mode": "delta",
                "early_stop_metric": "frozen_decode_delta_vs_copy",
                "growth_threshold": OOD_GROWTH_THRESHOLD,
                "ring": "8-connected k=1 frozen",
                "train_tiles": "complete_proxy_usable_eval_tiles",
            },
            "training_summary": summary,
            "not_claims": [
                "not clm_ensemble_v34",
                "not sealed transfer IoU",
                "not FREEZE lift",
                "not GO_Q complete",
            ],
        }
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "LAB_SCRATCH_MANIFEST.json").write_text(
            json.dumps(record, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps({"label": record["label"], "best_epoch": summary.get("best_epoch")}, indent=2))
        return 0

    growth_init = _prepare_growth_init(
        args.init_weights, args.output_dir / "lab_scratch_growth_init.pt"
    )
    if args.conservative:
        config = UNetTrainConfig(
            epochs=12,
            batch_size=8,
            lr=1e-4,
            loss="bce",
            pos_weight=1.0,
            model="small",
            architecture="standard",
            target_mode="delta",
            change_loss_weight=1.0,
            weighted_sampler=False,
            patience=5,
            deterministic=True,
            data_dir=str(args.data_dir),
            output_dir=str(args.output_dir),
            version_tag="lab_scratch_conservative_seed42_v1",
            early_stop_metric="improvement_vs_copy_iou",
            primary_threshold=0.9,
            eval_thresholds=(0.5, 0.9),
            init_weights_path=str(growth_init),
            clm_data_dir=None,
        )
    else:
        config = UNetTrainConfig(
            epochs=16,
            batch_size=8,
            lr=3e-4,
            loss="composite",
            pos_weight=5.0,
            model="small",
            architecture="standard",
            target_mode="delta",
            change_loss_weight=5.0,
            weighted_sampler=True,
            patience=6,
            deterministic=True,
            data_dir=str(args.data_dir),
            output_dir=str(args.output_dir),
            version_tag="lab_scratch_growth_latam_au_seed42_v1",
            early_stop_metric="improvement_vs_copy_iou",
            init_weights_path=str(growth_init),
            clm_data_dir=None,
        )
    summary = run_training(config)
    record = {
        "schema": "wfd_latam_au_lab_scratch_run_v1",
        "as_of_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "label": "lab_scratch",
        "seed": 42,
        "one_seed_one_config": True,
        "data_manifest": str(manifest_path.relative_to(ROOT)).replace("\\", "/"),
        "init_weights": str(args.init_weights.relative_to(ROOT)).replace("\\", "/"),
        "growth_init": str(growth_init.relative_to(ROOT)).replace("\\", "/"),
        "output_weights": "weights_pretrained_best.pt",
        "config": {
            "epochs": config.epochs,
            "batch_size": config.batch_size,
            "lr": config.lr,
            "loss": config.loss,
            "architecture": config.architecture,
            "target_mode": config.target_mode,
            "early_stop_metric": config.early_stop_metric,
            "patience": config.patience,
        },
        "training_summary": summary,
        "not_claims": [
            "not clm_ensemble_v34",
            "not sealed transfer IoU",
            "not FREEZE lift",
            "not GO_Q complete",
        ],
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "LAB_SCRATCH_MANIFEST.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"label": record["label"], "seed": 42, "best_epoch": summary.get("best_epoch")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
