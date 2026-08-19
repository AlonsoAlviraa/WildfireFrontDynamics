#!/usr/bin/env python3
"""Same-fire architecture / hyperparameter sweep (additional, in-sample).

Does not overwrite official LATAM complete-proxy JSON, product weights, or
lab_scratch_frozen. Decode-knob rows are eval-only ablations, not MET.

  python scripts/run_same_fire_arch_sweep.py --list-only
  python scripts/run_same_fire_arch_sweep.py
  python scripts/run_same_fire_arch_sweep.py --only standard_abs_lr1e4 --epochs 6
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.run_latam_au_complete_model_iou import OOD_GROWTH_THRESHOLD  # noqa: E402
from scripts.run_latam_au_lab_scratch import frozen_ring_decode_loss  # noqa: E402
from scripts.run_same_fire_scratch import (  # noqa: E402
    INIT,
    PRODUCT,
    _collect_caldor_tiles,
    _collect_cems_tiles,
)
from wildfire_front.ml.feature_schema import schema_channel_count  # noqa: E402
from wildfire_front.ml.unet_train import (  # noqa: E402
    UNetTrainConfig,
    build_model,
    model_forward,
    prepare_input,
)
from wildfire_front.open_if.same_fire_model import (  # noqa: E402
    binary_iou,
    decode_complete_proxy_pred,
)

N_CH = schema_channel_count("legacy17")
DEFAULT_OUT = ROOT / "outputs" / "ml_eval" / "mega_goal_model" / "same_fire_arch_sweep"
OFFICIAL = ROOT / "outputs" / "ml_eval" / "mega_goal_model" / "complete_proxy_model_iou.json"
SCRATCH = (
    ROOT / "outputs" / "ml_eval" / "mega_goal_model" / "same_fire_scratch" / "weights_pretrained_best.pt"
)

EXIT_OK = 0
EXIT_MISSING = 1
EXIT_BAD_DATA = 2
EXIT_USAGE = 3

SWEEP_CONFIGS: tuple[dict[str, Any], ...] = (
    {
        "id": "residual_scratch_ref",
        "architecture": "residual",
        "model": "small",
        "se_attention": False,
        "loss": "frozen_ring",
        "lr": 1e-4,
        "fp_weight": 4.0,
        "epochs": 0,
        "init": "same_fire_scratch",
        "decode": "frozen_ring",
        "train": False,
        "note": "reference: already-trained same-fire residual scratch",
    },
    {
        "id": "residual_fp8_lr1e4",
        "architecture": "residual",
        "model": "small",
        "se_attention": False,
        "loss": "frozen_ring",
        "lr": 1e-4,
        "fp_weight": 8.0,
        "epochs": 6,
        "init": "lab_scratch",
        "decode": "frozen_ring",
        "train": True,
        "note": "stronger false-ring leak penalty",
    },
    {
        "id": "residual_fp4_lr3e4",
        "architecture": "residual",
        "model": "small",
        "se_attention": False,
        "loss": "frozen_ring",
        "lr": 3e-4,
        "fp_weight": 4.0,
        "epochs": 6,
        "init": "lab_scratch",
        "decode": "frozen_ring",
        "train": True,
        "note": "higher lr residual",
    },
    {
        "id": "standard_abs_lr1e4",
        "architecture": "standard",
        "model": "small",
        "se_attention": False,
        "loss": "bce_dice_abs",
        "lr": 1e-4,
        "fp_weight": None,
        "epochs": 8,
        "init": "random",
        "decode": "abs_thr",
        "train": True,
        "note": "standard U-Net predicts P(abs); no residual keep-t0 prior",
    },
    {
        "id": "standard_se_abs_lr1e4",
        "architecture": "standard",
        "model": "small",
        "se_attention": True,
        "loss": "bce_dice_abs",
        "lr": 1e-4,
        "fp_weight": None,
        "epochs": 8,
        "init": "random",
        "decode": "abs_thr",
        "train": True,
        "note": "standard small + squeeze-excitation",
    },
    {
        "id": "standard_abs_lr3e4",
        "architecture": "standard",
        "model": "small",
        "se_attention": False,
        "loss": "bce_dice_abs",
        "lr": 3e-4,
        "fp_weight": None,
        "epochs": 8,
        "init": "random",
        "decode": "abs_thr",
        "train": True,
        "note": "standard U-Net higher lr",
    },
)

DECODE_ABLATIONS: tuple[dict[str, Any], ...] = (
    {
        "id": "residual_eval_keep_t0_norings_g90",
        "decode": "keep_t0_no_ring",
        "growth_threshold": 0.90,
        "source": "residual_scratch_ref",
        "note": "eval-only decode ablation — not frozen MET",
    },
    {
        "id": "residual_eval_keep_t0_norings_g50",
        "decode": "keep_t0_no_ring",
        "growth_threshold": 0.50,
        "source": "residual_scratch_ref",
        "note": "eval-only decode ablation — not frozen MET",
    },
    {
        "id": "standard_abs_eval_keep_t0",
        "decode": "keep_t0_thr",
        "growth_threshold": 0.50,
        "source": "standard_abs_lr1e4",
        "note": "eval-only: OR t0 onto standard P>=0.5",
    },
)

NOT_CLAIMS = (
    "additional same-fire architecture sweep — not official LATAM complete-proxy",
    "in-sample tiles (578/632/Caldor) — not sealed transfer",
    "not GO_Q",
    "not clm_ensemble_v34",
    "not catalog 0.8963",
    "decode-ablation rows are not the frozen MET knobs",
    "lab_ok_conaf remains false",
)


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-root", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--list-only", action="store_true")
    ap.add_argument("--only", action="append", dest="only_ids", default=None)
    ap.add_argument("--epochs", type=int, default=None, help="Override train epochs for all train configs.")
    ap.add_argument("--max-patches", type=int, default=16)
    ap.add_argument("--skip-decode-ablations", action="store_true")
    return ap


def _init_path(kind: str) -> Path | None:
    if kind == "same_fire_scratch":
        return SCRATCH if SCRATCH.is_file() else (INIT if INIT.is_file() else PRODUCT)
    if kind == "lab_scratch":
        return INIT if INIT.is_file() else PRODUCT
    return None


def _bce_dice(logits: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    if logits.ndim == 4:
        logits = logits[:, 0]
    bce = F.binary_cross_entropy_with_logits(logits, target)
    prob = torch.sigmoid(logits)
    inter = (prob * target).sum()
    dice = 1.0 - (2.0 * inter + 1e-6) / (prob.sum() + target.sum() + 1e-6)
    return bce + dice


def decode_mask(
    probability: np.ndarray,
    prev: np.ndarray,
    *,
    architecture: str,
    decode: str,
    growth_threshold: float,
) -> np.ndarray:
    prev_b = prev >= 0.5
    if decode == "frozen_ring":
        return decode_complete_proxy_pred(
            probability,
            prev,
            architecture="residual",
            target_mode="delta",
            threshold=0.5,
            growth_threshold=OOD_GROWTH_THRESHOLD,
            require_growth_ring=True,
        )
    if decode == "keep_t0_no_ring":
        return prev_b | ((~prev_b) & (probability >= float(growth_threshold)))
    if decode == "keep_t0_thr":
        return prev_b | (probability >= float(growth_threshold))
    return probability >= 0.5


def eval_tiles(
    model,
    device,
    tiles: list[dict[str, Any]],
    *,
    architecture: str,
    decode: str,
    growth_threshold: float = OOD_GROWTH_THRESHOLD,
) -> dict[str, Any]:
    if not tiles:
        return {"n_tiles": 0, "model_iou": None, "copy_iou": None, "delta_vs_copy": None}
    model.eval()
    ious: list[float] = []
    copies: list[float] = []
    with torch.no_grad():
        for tile in tiles:
            seq = np.asarray(tile["seq"], dtype=np.float32)
            if seq.ndim == 4:
                seq = seq[np.newaxis, ...]
            prev = np.asarray(tile["prev"], dtype=np.float32)
            tgt = np.asarray(tile["target"], dtype=np.float32)
            seq_t = torch.from_numpy(seq)
            cur_t = torch.from_numpy(prev[np.newaxis, ...])
            x_in = prepare_input(seq_t, cur_t).to(device)
            logits = model_forward(model, x_in, cur_t.to(device), architecture)
            prob = torch.sigmoid(logits)[0, 0].cpu().numpy()
            pred = decode_mask(
                prob,
                prev,
                architecture=architecture,
                decode=decode,
                growth_threshold=growth_threshold,
            )
            ious.append(binary_iou(pred, tgt > 0.5))
            copies.append(binary_iou(prev >= 0.5, tgt > 0.5))
    model.train()
    model_iou = float(np.mean(ious))
    copy_iou = float(np.mean(copies))
    return {
        "n_tiles": len(ious),
        "model_iou": model_iou,
        "copy_iou": copy_iou,
        "delta_vs_copy": float(model_iou - copy_iou),
        "n_tiles_beating_copy": int(sum(m > c for m, c in zip(ious, copies, strict=True))),
    }


def collect_tiles(max_patches: int) -> list[dict[str, Any]]:
    cache: dict[str, Any] = {}
    tiles: list[dict[str, Any]] = []
    tiles.extend(_collect_cems_tiles("EMSR578_AOI01", max_patches, cache))
    tiles.extend(_collect_cems_tiles("EMSR632_AOI01", max_patches, cache))
    tiles.extend(_collect_caldor_tiles(max_patches))
    return tiles


def _stack_tiles(tiles: list[dict[str, Any]]) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    seqs, curs, tgts = [], [], []
    for tile in tiles:
        seq = np.asarray(tile["seq"], dtype=np.float32)
        if seq.ndim == 5:
            seq = seq[0]
        seqs.append(torch.from_numpy(seq))
        curs.append(torch.from_numpy(np.asarray(tile["prev"], dtype=np.float32)))
        tgts.append(torch.from_numpy(np.asarray(tile["target"], dtype=np.float32)))
    return torch.stack(seqs), torch.stack(curs), torch.stack(tgts)


def train_config(
    cfg: dict[str, Any],
    tiles: list[dict[str, Any]],
    *,
    epochs_override: int | None,
    out_dir: Path,
    device: torch.device,
) -> dict[str, Any]:
    arch = str(cfg["architecture"])
    model_cfg = UNetTrainConfig(
        architecture=arch,
        model=str(cfg["model"]),
        se_attention=bool(cfg["se_attention"]),
        target_mode="delta" if arch == "residual" else "absolute",
    )
    model = build_model(model_cfg, in_channels=N_CH + 1)
    init = _init_path(str(cfg["init"]))
    if cfg["init"] != "random":
        if init is None or not init.is_file():
            raise FileNotFoundError(f"missing init weights for {cfg['id']}")
        model.load_state_dict(torch.load(init, map_location=device, weights_only=True), strict=True)
    model.to(device)
    epochs = int(epochs_override if epochs_override is not None else cfg["epochs"])
    if not cfg["train"] or epochs <= 0:
        metrics = eval_tiles(
            model,
            device,
            tiles,
            architecture=arch,
            decode=str(cfg["decode"]),
        )
        return {
            **{k: cfg[k] for k in cfg},
            "trained": False,
            "best_epoch": 0,
            "history": [],
            "metrics": metrics,
            "weights": None,
        }

    opt = torch.optim.AdamW(model.parameters(), lr=float(cfg["lr"]), weight_decay=1e-4)
    seq_all, cur_all, tgt_all = _stack_tiles(tiles)
    n = seq_all.shape[0]
    batch_size = 8
    history: list[dict[str, Any]] = []
    best = -1e9
    best_epoch = -1
    weights_path = out_dir / f"{cfg['id']}.pt"
    model.train()
    for epoch in range(1, epochs + 1):
        order = torch.randperm(n)
        losses: list[float] = []
        for start in range(0, n, batch_size):
            idx = order[start : start + batch_size]
            seq = seq_all[idx].to(device)
            cur = cur_all[idx].to(device)
            tgt = tgt_all[idx].to(device)
            seq_in = seq.unsqueeze(1) if seq.ndim == 4 else seq
            x = prepare_input(seq_in, cur)
            logits = model_forward(model, x, cur, arch)
            if cfg["loss"] == "frozen_ring":
                loss = frozen_ring_decode_loss(
                    logits, cur, tgt, fp_weight=float(cfg["fp_weight"] or 4.0)
                )
            else:
                loss = _bce_dice(logits, tgt)
            opt.zero_grad()
            loss.backward()
            opt.step()
            losses.append(float(loss.item()))
        metrics = eval_tiles(
            model, device, tiles, architecture=arch, decode=str(cfg["decode"])
        )
        delta = float(metrics["delta_vs_copy"] or 0.0)
        row = {
            "epoch": epoch,
            "train_loss": float(sum(losses) / max(len(losses), 1)),
            "tile_delta_vs_copy": delta,
            "model_iou": metrics["model_iou"],
        }
        history.append(row)
        print(
            f"{cfg['id']} epoch {epoch}/{epochs} loss={row['train_loss']:.4f} "
            f"iou={metrics['model_iou']:.4f} delta={delta:+.6f}",
            flush=True,
        )
        if delta > best:
            best = delta
            best_epoch = epoch
            torch.save(model.state_dict(), weights_path)
    if weights_path.is_file():
        model.load_state_dict(torch.load(weights_path, map_location=device, weights_only=True), strict=True)
    metrics = eval_tiles(model, device, tiles, architecture=arch, decode=str(cfg["decode"]))
    return {
        **{k: cfg[k] for k in cfg},
        "trained": True,
        "best_epoch": best_epoch,
        "history": history,
        "metrics": metrics,
        "weights": str(weights_path.relative_to(ROOT)).replace("\\", "/") if weights_path.is_file() else None,
    }


def write_scorecard(doc: dict[str, Any], path: Path) -> None:
    lines = [
        "# SCORECARD — same-fire architecture sweep (additional, in-sample)",
        "",
        "Not a replacement for official LATAM complete-proxy. Not GO_Q / v34.",
        "",
        f"- as_of_utc: `{doc.get('as_of_utc')}`",
        f"- n_tiles: `{doc.get('n_tiles')}`",
        f"- winner_by_delta: `{doc.get('winner_id')}`",
        "",
        "| id | arch | decode | train | model IoU | copy | Δ vs copy | beat tiles | note |",
        "|---|---|---|---|---:|---:|---:|---:|---|",
    ]
    for row in doc.get("rows") or []:
        m = row.get("metrics") or {}
        lines.append(
            "| {id} | {arch} | {dec} | {tr} | {iou} | {copy} | {delta} | {beat} | {note} |".format(
                id=row.get("id"),
                arch=row.get("architecture"),
                dec=row.get("decode"),
                tr="yes" if row.get("trained") else "no",
                iou="" if m.get("model_iou") is None else f"{m['model_iou']:.6f}",
                copy="" if m.get("copy_iou") is None else f"{m['copy_iou']:.6f}",
                delta="" if m.get("delta_vs_copy") is None else f"{m['delta_vs_copy']:+.6f}",
                beat=m.get("n_tiles_beating_copy") if m.get("n_tiles_beating_copy") is not None else "",
                note=str(row.get("note") or "")[:60],
            )
        )
    lines.extend(["", "## not_claims", ""])
    for claim in doc.get("not_claims") or NOT_CLAIMS:
        lines.append(f"- {claim}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.list_only:
        for cfg in SWEEP_CONFIGS:
            print(f"{cfg['id']}\t{cfg['architecture']}\ttrain={cfg['train']}\t{cfg['note']}")
        for cfg in DECODE_ABLATIONS:
            print(f"{cfg['id']}\teval_only\t{cfg['note']}")
        return EXIT_OK

    out = Path(args.out_root)
    if out.resolve() == OFFICIAL.resolve() or out.resolve() == OFFICIAL.parent.resolve():
        print("error: refusing to write over official complete-proxy JSON", file=sys.stderr)
        return EXIT_USAGE

    wanted = set(args.only_ids) if args.only_ids else None
    if wanted:
        known = {c["id"] for c in SWEEP_CONFIGS} | {c["id"] for c in DECODE_ABLATIONS}
        unknown = wanted - known
        if unknown:
            print(f"error: unknown config {sorted(unknown)}", file=sys.stderr)
            return EXIT_USAGE

    official_before = OFFICIAL.read_bytes() if OFFICIAL.is_file() else None
    print("collecting same-fire tiles ...", flush=True)
    tiles = collect_tiles(int(args.max_patches))
    if len(tiles) < 8:
        print(f"error: too few tiles ({len(tiles)})", file=sys.stderr)
        return EXIT_BAD_DATA
    print(f"n_tiles={len(tiles)} fires={sorted({t.get('fire_id') for t in tiles})}", flush=True)

    device = torch.device("cpu")
    out.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    trained_models: dict[str, Any] = {}

    for cfg in SWEEP_CONFIGS:
        if wanted and cfg["id"] not in wanted:
            continue
        print(f"=== {cfg['id']} ===", flush=True)
        try:
            result = train_config(
                cfg,
                tiles,
                epochs_override=args.epochs,
                out_dir=out,
                device=device,
            )
        except FileNotFoundError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return EXIT_MISSING
        rows.append(result)
        # keep last model on disk path; re-load later for ablations
        trained_models[cfg["id"]] = result

    if not args.skip_decode_ablations:
        for abl in DECODE_ABLATIONS:
            if wanted and abl["id"] not in wanted:
                continue
            source_id = str(abl["source"])
            source = next((r for r in rows if r.get("id") == source_id), None)
            if source is None:
                print(f"skip ablation {abl['id']}: missing source {source_id}", flush=True)
                continue
            src_cfg = next(c for c in SWEEP_CONFIGS if c["id"] == source_id)
            model_cfg = UNetTrainConfig(
                architecture=str(src_cfg["architecture"]),
                model=str(src_cfg["model"]),
                se_attention=bool(src_cfg["se_attention"]),
            )
            model = build_model(model_cfg, in_channels=N_CH + 1)
            weights = None
            if source.get("weights"):
                weights = ROOT / str(source["weights"])
            elif src_cfg["init"] != "random":
                weights = _init_path(str(src_cfg["init"]))
            if weights is None or not Path(weights).is_file():
                print(f"skip ablation {abl['id']}: no weights", flush=True)
                continue
            model.load_state_dict(
                torch.load(Path(weights), map_location=device, weights_only=True), strict=True
            )
            model.to(device)
            metrics = eval_tiles(
                model,
                device,
                tiles,
                architecture=str(src_cfg["architecture"]),
                decode=str(abl["decode"]),
                growth_threshold=float(abl.get("growth_threshold") or 0.5),
            )
            rows.append(
                {
                    "id": abl["id"],
                    "architecture": src_cfg["architecture"],
                    "decode": abl["decode"],
                    "trained": False,
                    "eval_only_ablation": True,
                    "source": source_id,
                    "growth_threshold": abl.get("growth_threshold"),
                    "note": abl["note"],
                    "metrics": metrics,
                    "weights": source.get("weights"),
                }
            )
            print(
                f"{abl['id']} iou={metrics['model_iou']} delta={metrics['delta_vs_copy']:+.6f}",
                flush=True,
            )

    scored = [r for r in rows if (r.get("metrics") or {}).get("delta_vs_copy") is not None]
    winner = max(scored, key=lambda r: float(r["metrics"]["delta_vs_copy"])) if scored else None
    doc = {
        "schema": "wfd_same_fire_arch_sweep_v1",
        "as_of_utc": utc_now(),
        "n_tiles": len(tiles),
        "fires": sorted({str(t.get("fire_id")) for t in tiles}),
        "in_sample": True,
        "winner_id": None if winner is None else winner.get("id"),
        "winner_delta_vs_copy": None
        if winner is None
        else winner["metrics"]["delta_vs_copy"],
        "rows": rows,
        "not_claims": list(NOT_CLAIMS),
        "go_q": "partial",
        "lab_ok_conaf": False,
        "sold_as_clm_ensemble_v34": False,
    }
    (out / "arch_sweep.json").write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    write_scorecard(doc, out / "SCORECARD.md")
    if official_before is not None and OFFICIAL.read_bytes() != official_before:
        print("error: official LATAM JSON changed", file=sys.stderr)
        return EXIT_USAGE
    print(f"wrote {out / 'SCORECARD.md'} winner={doc['winner_id']} delta={doc['winner_delta_vs_copy']}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
