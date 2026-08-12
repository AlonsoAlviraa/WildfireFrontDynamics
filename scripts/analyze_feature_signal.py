#!/usr/bin/env python3
"""Growth-aware feature signal analysis on NPZ patches (R1/R2 + E2-P2).

Reports per-channel std, fraction constant, Pearson corr vs:
  target absolute, growth (target-prev)+, change |target-prev|

Labels each channel ``always`` / ``maybe`` / ``never`` (historical ``must``
is emitted as ``always`` with ``label_legacy=must`` for compatibility).

Train gate: by default **blocks** if any channel is ``never`` unless
``--allow-never-channels`` + ``--allowlist-honesty`` are provided.

Usage:
  python scripts/analyze_feature_signal.py --data-dir artifacts/clm_ndws_patches/train --max-patches 400
  python scripts/analyze_feature_signal.py --data-dir ... --gate-train --schema spatial_v1
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.ml.feature_schema import (  # noqa: E402
    NeverChannelTrainError,
    assert_no_never_train_channels,
    label_channel_signal,
    schema_channel_names,
)


def _pearson(a: np.ndarray, b: np.ndarray) -> float:
    a = a.ravel().astype(np.float64)
    b = b.ravel().astype(np.float64)
    if a.size < 2 or np.std(a) < 1e-12 or np.std(b) < 1e-12:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def analyze_dir(
    data_dir: Path,
    max_patches: int,
    *,
    channel_names: tuple[str, ...] | list[str] | None = None,
) -> dict:
    files = sorted(data_dir.glob("*.npz"))[:max_patches]
    if not files:
        return {"error": f"no npz in {data_dir}", "n": 0}

    # Peek shape
    with np.load(files[0]) as z:
        seq = z["sequence"]
        # (T,C,H,W) or (C,H,W)
        if seq.ndim == 4:
            t0, c, _, _ = seq.shape
        else:
            t0, c = 1, seq.shape[0]

    sums = np.zeros(c, dtype=np.float64)
    sumsq = np.zeros(c, dtype=np.float64)
    n_pix = 0
    # reservoir for correlation (subsample pixels)
    max_pix = 200_000
    ch_store = [[] for _ in range(c)]
    tgt_store: list[np.ndarray] = []
    growth_store: list[np.ndarray] = []
    change_store: list[np.ndarray] = []

    for fp in files:
        with np.load(fp) as z:
            seq = z["sequence"].astype(np.float32)
            prev = z["current_fire"].astype(np.float32)
            tgt = z["target_fire"].astype(np.float32)
        frame = seq[-1] if seq.ndim == 4 else seq  # last timestep channels
        c = frame.shape[0]
        prev_b = (prev >= 0.5).astype(np.float32)
        tgt_b = (tgt >= 0.5).astype(np.float32)
        growth = np.clip(tgt_b - prev_b, 0, 1)
        change = (tgt_b != prev_b).astype(np.float32)

        flat_n = prev.size
        n_pix += flat_n
        for i in range(c):
            sums[i] += float(frame[i].sum())
            sumsq[i] += float((frame[i].astype(np.float64) ** 2).sum())

        # subsample
        idx = np.random.default_rng(0).choice(flat_n, size=min(512, flat_n), replace=False)
        for i in range(c):
            ch_store[i].append(frame[i].ravel()[idx])
        tgt_store.append(tgt_b.ravel()[idx])
        growth_store.append(growth.ravel()[idx])
        change_store.append(change.ravel()[idx])

    tgt_cat = np.concatenate(tgt_store)[:max_pix]
    growth_cat = np.concatenate(growth_store)[:max_pix]
    change_cat = np.concatenate(change_store)[:max_pix]

    channels = []
    never_idx: list[int] = []
    always_idx: list[int] = []
    maybe_idx: list[int] = []
    for i in range(c):
        mean = sums[i] / max(n_pix, 1)
        var = sumsq[i] / max(n_pix, 1) - mean**2
        std = float(np.sqrt(max(var, 0.0)))
        sample = np.concatenate(ch_store[i])[:max_pix]
        frac_const = float(np.mean(np.abs(sample - sample.mean()) < 1e-6)) if sample.size else 1.0
        corr_t = _pearson(sample, tgt_cat[: sample.size])
        corr_g = _pearson(sample, growth_cat[: sample.size])
        corr_c = _pearson(sample, change_cat[: sample.size])
        label = label_channel_signal(
            std=std, frac_const=frac_const, corr_growth=corr_g, corr_change=corr_c
        )
        # Back-compat: historical report used "must" for strong growth corr
        label_legacy = "must" if label == "always" else label
        name = None
        if channel_names is not None and i < len(channel_names):
            name = str(channel_names[i])
        row = {
            "index": i,
            "name": name,
            "mean": mean,
            "std": std,
            "frac_near_constant": frac_const,
            "corr_target": corr_t,
            "corr_growth": corr_g,
            "corr_change": corr_c,
            "label": label,
            "label_legacy": label_legacy,
        }
        channels.append(row)
        if label == "never":
            never_idx.append(i)
        elif label == "always":
            always_idx.append(i)
        else:
            maybe_idx.append(i)

    ranked_growth = sorted(channels, key=lambda x: abs(x["corr_growth"]), reverse=True)
    return {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "data_dir": str(data_dir),
        "n_patches": len(files),
        "n_channels": c,
        "sequence_timesteps_sample": t0,
        "channels": channels,
        "label_counts": {
            "always": len(always_idx),
            "maybe": len(maybe_idx),
            "never": len(never_idx),
        },
        "never_channel_indices": never_idx,
        "always_channel_indices": always_idx,
        "maybe_channel_indices": maybe_idx,
        "ranked_by_abs_corr_growth": [
            {
                "index": x["index"],
                "name": x.get("name"),
                "corr_growth": x["corr_growth"],
                "label": x["label"],
            }
            for x in ranked_growth
        ],
        "notes": (
            "corr vs growth is primary signal metric (not absolute fire persistence); "
            "labels: always|maybe|never (legacy must→always)"
        ),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", type=Path, required=True)
    p.add_argument("--max-patches", type=int, default=400)
    p.add_argument(
        "--output",
        type=Path,
        default=ROOT / "outputs" / "ml_eval" / "feature_signal_report.json",
    )
    p.add_argument(
        "--schema",
        type=str,
        default=None,
        help="Optional schema id to attach channel names (spatial_v1, physics14, …)",
    )
    p.add_argument(
        "--gate-train",
        action="store_true",
        help="Exit non-zero if any never channel blocks train (default policy)",
    )
    p.add_argument(
        "--allow-never-channels",
        type=str,
        default="",
        help="Comma-separated channel names or ch{i} allowlisted despite never",
    )
    p.add_argument(
        "--allowlist-honesty",
        type=str,
        default=None,
        help="Required honesty stamp when allowlist is non-empty",
    )
    args = p.parse_args()

    names = None
    if args.schema:
        try:
            names = schema_channel_names(args.schema)
        except ValueError:
            names = None

    report = analyze_dir(args.data_dir, args.max_patches, channel_names=names)
    if args.schema:
        report["feature_schema"] = args.schema

    gate_result = None
    if args.gate_train and "error" not in report:
        allow = {x.strip() for x in args.allow_never_channels.split(",") if x.strip()}
        try:
            gate_result = assert_no_never_train_channels(
                report.get("channels") or [],
                channel_names=names,
                allowlist=allow or None,
                allowlist_honesty=args.allowlist_honesty,
                raise_on_block=True,
            )
            report["train_gate"] = gate_result
        except NeverChannelTrainError as exc:
            gate_result = {
                "ok": False,
                "blocked": True,
                "error": str(exc),
                "never_channel_indices": report.get("never_channel_indices"),
            }
            report["train_gate"] = gate_result

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}")
    if report.get("ranked_by_abs_corr_growth"):
        print("Top growth correlations:")
        for row in report["ranked_by_abs_corr_growth"][:8]:
            print(f"  ch{row['index']}: corr_growth={row['corr_growth']:.4f} ({row['label']})")
    if report.get("never_channel_indices"):
        print(
            f"NEVER channels ({len(report['never_channel_indices'])}): "
            f"{report['never_channel_indices']}"
        )
    if args.gate_train and gate_result is not None and not gate_result.get("ok", False):
        print("TRAIN GATE BLOCKED:", gate_result.get("error"), file=sys.stderr)
        return 2
    return 0 if "error" not in report else 1


if __name__ == "__main__":
    raise SystemExit(main())
