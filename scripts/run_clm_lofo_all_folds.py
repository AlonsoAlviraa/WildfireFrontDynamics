#!/usr/bin/env python3
"""Run LOFO fine-tune for each held-out source under a LOFO pack root.

Metrics-lift harness (PR3a): configurable data/eval roots, schema summary fields,
optional ``--smoke`` 1-epoch dry path that does not claim KEEP.

Usage::

    $env:PYTHONPATH = "."
    python scripts/run_clm_lofo_all_folds.py
    python scripts/run_clm_lofo_all_folds.py \\
        --lofo-root artifacts/clm_ndws_patches/lofo_v2 \\
        --out-root outputs/ml_eval/lofo_v2 \\
        --feature-schema legacy17 --schema-path-id E3a
    python scripts/run_clm_lofo_all_folds.py --smoke
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.ml.feature_schema import (  # noqa: E402
    NeverChannelTrainError,
    assert_no_never_train_channels,
    channel_stats_from_tensor,
    never_gate_default_for_schema,
    schema_channel_count,
    schema_channel_names,
    spatial_v1_schema_map,
    work_class_for_schema,
)
from wildfire_front.ml.unet_train import UNetTrainConfig, run_training  # noqa: E402

DEFAULT_LOFO_ROOT = ROOT / "artifacts" / "clm_ndws_patches" / "lofo_v1"
DEFAULT_INIT = ROOT / "models" / "production" / "weights_v21_best.pt"
DEFAULT_OUT_ROOT = ROOT / "outputs" / "ml_eval" / "lofo_v1"


def _gate_never_channels_on_train(
    train_dir: Path,
    *,
    feature_schema: str,
    allow_never: bool,
    allowlist: set[str] | None,
    allowlist_honesty: str | None,
    max_files: int = 32,
) -> dict[str, Any]:
    """Sample train NPZ and block if never channels present.

    Samples up to ``max_files`` train NPZ (first sorted names; smoke cost tradeoff —
    not a full-pack audit). Raise ``max_files`` for stricter CI.
    """
    import numpy as np

    files = sorted(train_dir.glob("*.npz"))[:max_files]
    if not files:
        return {"ok": True, "skipped": True, "reason": "no_train_npz"}
    # Aggregate last-frame channels
    frames: list[Any] = []
    for fp in files:
        with np.load(fp) as z:
            seq = z["sequence"]
            frame = seq[-1] if seq.ndim == 4 else seq
            frames.append(np.asarray(frame, dtype=np.float32))
    stack = np.stack(frames, axis=0)  # (N, C, H, W)
    # Flatten N into spatial for stats: treat as (C, N*H, W) via reshape
    n, c, h, w = stack.shape
    flat = stack.transpose(1, 0, 2, 3).reshape(c, n * h, w)
    rows = channel_stats_from_tensor(flat)
    names: tuple[str, ...] | None
    try:
        names = schema_channel_names(feature_schema)
    except ValueError:
        names = None
    if allow_never:
        # Explicit opt-out still stamps honesty
        return {
            "ok": True,
            "skipped": False,
            "allow_never": True,
            "allowlist_honesty": allowlist_honesty,
            "never_channels": [r for r in rows if r.get("label") == "never"],
            "note": "never-channel gate disabled by --allow-never-channels",
            "max_files_sampled": max_files,
            "n_files_sampled": len(files),
        }
    return assert_no_never_train_channels(
        rows,
        channel_names=names,
        allowlist=allowlist,
        allowlist_honesty=allowlist_honesty,
        raise_on_block=True,
    )


def run_fold(
    held: str,
    *,
    lofo_root: Path,
    out_root: Path,
    init_weights: Path | None,
    epochs: int = 12,
    feature_schema: str = "legacy17",
    schema_path_id: str | None = None,
    in_channels: int | None = None,
    batch_size: int = 8,
    smoke: bool = False,
    gate_never_channels: bool = True,
    force_gate_never_channels: bool = False,
    allow_never_channels: bool = False,
    never_allowlist: set[str] | None = None,
    never_allowlist_honesty: str | None = None,
) -> dict[str, Any]:
    data = lofo_root / held
    out = out_root / held
    out.mkdir(parents=True, exist_ok=True)
    if not (data / "train").is_dir():
        return {"held": held, "status": "missing_split"}

    # channel match honesty
    init_path = str(init_weights) if init_weights and init_weights.is_file() else None
    channel_match = True
    if (
        feature_schema
        in (
            "clean12_subset",
            "clean12",
            "spatial_v1",
            "physics14_spatial",
            "physics14",
            "physics15",
        )
        and init_path
    ):
        # sealed v21 is legacy17-width; disclose mismatch for non-legacy schemas
        channel_match = False
        init_path = None

    work_class = work_class_for_schema(feature_schema, schema_path_id=schema_path_id)

    if smoke:
        # Do not train; write stub summary + skip KEEP claim
        stub = {
            "held": held,
            "status": "smoke_skip_train",
            "feature_schema": feature_schema,
            "schema_path_id": schema_path_id,
            "work_class": work_class,
            "in_channels": in_channels,
            "init_weights_path": init_path,
            "init_weights_channel_match": channel_match,
            "test_iou": None,
            "copy_baseline_iou": None,
            "improvement_vs_copy_iou": None,
            "smoke": True,
            "note": "PR3a smoke — no train, no KEEP claim",
        }
        if feature_schema in ("spatial_v1", "physics14_spatial"):
            stub["schema_map"] = spatial_v1_schema_map()
            stub["schema_path_id"] = schema_path_id or "E2-P2"
        (out / "training_summary.json").write_text(json.dumps(stub, indent=2), encoding="utf-8")
        return stub

    # Never-channel gate: ON by default only for schemas that claim spatial/physics
    # variance (spatial_v1, physics14/15). Sealed legacy17 / clean12_subset keep
    # intentional constants — gate OFF unless --force-gate-never-channels (BUG-1).
    apply_gate = bool(gate_never_channels) and (
        never_gate_default_for_schema(feature_schema) or bool(force_gate_never_channels)
    )
    train_gate: dict[str, Any] | None = None
    if apply_gate:
        try:
            train_gate = _gate_never_channels_on_train(
                data / "train",
                feature_schema=feature_schema,
                allow_never=allow_never_channels,
                allowlist=never_allowlist,
                allowlist_honesty=never_allowlist_honesty,
            )
        except NeverChannelTrainError as exc:
            blocked = {
                "held": held,
                "status": "blocked_never_channels",
                "feature_schema": feature_schema,
                "schema_path_id": schema_path_id,
                "work_class": work_class,
                "error": str(exc),
                "keep_claim": False,
            }
            (out / "training_summary.json").write_text(
                json.dumps(blocked, indent=2), encoding="utf-8"
            )
            return blocked
    elif gate_never_channels:
        train_gate = {
            "ok": True,
            "skipped": True,
            "reason": (
                f"never-gate default off for schema={feature_schema} "
                f"(sealed/recipe path); use --force-gate-never-channels to enable"
            ),
            "schema_default_gate": never_gate_default_for_schema(feature_schema),
        }

    cfg = UNetTrainConfig(
        epochs=epochs,
        batch_size=batch_size,
        lr=3e-4,
        loss="composite",
        pos_weight=5.0,
        model="small",
        architecture="residual",
        target_mode="delta",
        change_loss_weight=5.0,
        weighted_sampler=True,
        patience=6 if epochs > 2 else max(1, epochs),
        data_dir=str(data),
        output_dir=str(out),
        version_tag=f"lofo_{held}",
        early_stop_metric="improvement_vs_copy_iou",
        init_weights_path=init_path or "",
    )
    print(f"\n=== LOFO fold held={held} schema={feature_schema} ===", flush=True)
    s = run_training(cfg)
    # Enrich training_summary on disk if present
    ts_path = out / "training_summary.json"
    summary_extra = {
        "feature_schema": feature_schema,
        "schema_path_id": schema_path_id,
        "work_class": work_class,
        "in_channels": in_channels,
        "init_weights_path": init_path,
        "init_weights_channel_match": channel_match,
        "held_out": held,
        "lofo_root": str(lofo_root.as_posix()),
        "train_gate": train_gate,
        "never_gate_applied": apply_gate,
    }
    if feature_schema in ("spatial_v1", "physics14_spatial"):
        summary_extra["schema_map"] = spatial_v1_schema_map()
        summary_extra["schema_path_id"] = schema_path_id or "E2-P2"
    if ts_path.is_file():
        try:
            prev = json.loads(ts_path.read_text(encoding="utf-8"))
            if isinstance(prev, dict):
                prev.update(summary_extra)
                ts_path.write_text(json.dumps(prev, indent=2), encoding="utf-8")
        except (OSError, json.JSONDecodeError):
            pass
    else:
        ts_path.write_text(json.dumps({**s, **summary_extra}, indent=2), encoding="utf-8")

    row = {
        "held": held,
        "status": "ok",
        "test_iou": s.get("test_iou"),
        "copy_baseline_iou": s.get("copy_baseline_iou"),
        "improvement_vs_copy_iou": s.get("improvement_vs_copy_iou"),
        "best_epoch": s.get("best_epoch"),
        "test_samples": s.get("test_samples"),
        **summary_extra,
    }
    print(json.dumps(row, indent=2), flush=True)
    return row


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--lofo-root", type=Path, default=DEFAULT_LOFO_ROOT)
    p.add_argument("--out-root", type=Path, default=DEFAULT_OUT_ROOT)
    p.add_argument("--init-weights", type=Path, default=DEFAULT_INIT)
    p.add_argument("--epochs", type=int, default=12)
    p.add_argument("--batch-size", type=int, default=8)
    p.add_argument(
        "--feature-schema",
        type=str,
        default="legacy17",
        help=(
            "Recorded in training_summary "
            "(legacy17|clean12_subset|physics14|spatial_v1|physics14_spatial)"
        ),
    )
    p.add_argument("--schema-path-id", type=str, default=None)
    p.add_argument(
        "--in-channels",
        type=int,
        default=None,
        help="Feature+prev_fire channel count for summary honesty",
    )
    p.add_argument("--folds", type=str, default=None, help="Comma-separated fold filter")
    p.add_argument(
        "--all",
        action="store_true",
        help="Include tobarra fold (default skips when cached verdict exists)",
    )
    p.add_argument(
        "--smoke",
        action="store_true",
        help="PR3a CI smoke: no real train; write stubs; exit 0; never KEEP",
    )
    p.add_argument(
        "--no-gate-never-channels",
        action="store_true",
        help="Disable never-channel train block even for spatial_v1 / physics schemas",
    )
    p.add_argument(
        "--force-gate-never-channels",
        action="store_true",
        help=(
            "Force never-gate even for sealed legacy17 / clean12_subset "
            "(default: gate only spatial_v1 / physics14/15)"
        ),
    )
    p.add_argument(
        "--allow-never-channels",
        action="store_true",
        help="Allow train despite never channels (requires --never-allowlist-honesty)",
    )
    p.add_argument(
        "--never-allowlist",
        type=str,
        default="",
        help="Comma-separated channel names / ch{i} allowed despite never",
    )
    p.add_argument(
        "--never-allowlist-honesty",
        type=str,
        default=None,
        help="Honesty stamp required when allowlisting never channels",
    )
    p.add_argument(
        "--report-out",
        type=Path,
        default=None,
    )
    args = p.parse_args(argv)

    lofo_root = args.lofo_root.resolve()
    out_root = args.out_root.resolve()
    init = args.init_weights.resolve() if args.init_weights else None

    if not args.smoke and init is not None and not init.is_file():
        print("missing init weights", init, file=sys.stderr)
        # allow continue without init for clean12_subset
        if args.feature_schema == "legacy17":
            return 1

    if not lofo_root.is_dir() and not args.smoke:
        print("missing lofo-root", lofo_root, file=sys.stderr)
        return 1

    if args.smoke and not lofo_root.is_dir():
        # synthetic smoke without pack
        report = {
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "protocol": "clm_lofo_metrics_lift_smoke",
            "smoke": True,
            "folds": [],
            "summary": {
                "n_folds": 0,
                "mean_delta": None,
                "keep_claim": False,
                "note": "smoke without pack — no KEEP",
            },
            "feature_schema": args.feature_schema,
            "schema_path_id": args.schema_path_id,
        }
        out = args.report_out or (ROOT / "docs" / "CLM_LOFO_ALL_FOLDS_REPORT.json")
        # don't overwrite production report on smoke without pack — write lab_loop
        out = args.report_out or (
            ROOT / "outputs" / "ml_eval" / "lab_loop" / "lofo_train_smoke_report.json"
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(
            json.dumps({"ok": True, "smoke": True, "out": str(out), "keep_claim": False}, indent=2)
        )
        return 0

    folds = sorted(p.name for p in lofo_root.iterdir() if p.is_dir() and (p / "train").is_dir())
    if args.folds:
        want = {x.strip() for x in args.folds.split(",") if x.strip()}
        folds = [f for f in folds if f in want]

    in_ch = args.in_channels
    if in_ch is None:
        if args.feature_schema in ("clean12", "clean12_subset"):
            in_ch = 13  # 12 + prev_fire
        elif args.feature_schema in ("physics14", "spatial_v1", "physics14_spatial"):
            in_ch = 15  # 14 + prev_fire
        elif args.feature_schema == "physics15":
            in_ch = 16
        else:
            in_ch = 18  # 17 + prev_fire typical
        # Cross-check registered counts when known
        try:
            feat_n = schema_channel_count(args.feature_schema)
            in_ch = feat_n + 1
        except ValueError:
            pass

    if args.feature_schema in ("spatial_v1", "physics14_spatial") and not args.schema_path_id:
        args.schema_path_id = "E2-P2"

    never_allow = {x.strip() for x in (args.never_allowlist or "").split(",") if x.strip()}
    if args.allow_never_channels and not (args.never_allowlist_honesty or "").strip():
        # SUGGESTION-4: hard-require operator honesty stamp (no silent auto-fill)
        print(
            "refuse: --allow-never-channels requires non-empty --never-allowlist-honesty",
            file=sys.stderr,
        )
        return 2

    rows: list[dict[str, Any]] = []
    for held in folds:
        if held == "tobarra_20240802" and not args.all and not args.smoke:
            prev = ROOT / "docs" / "V29_LOFO_TOBARRA_VERDICT.json"
            if prev.is_file():
                d = json.loads(prev.read_text(encoding="utf-8"))
                rows.append(
                    {
                        "held": held,
                        "status": "cached",
                        "test_iou": d.get("test_iou"),
                        "copy_baseline_iou": d.get("copy_baseline_iou"),
                        "improvement_vs_copy_iou": d.get("improvement_vs_copy_iou")
                        or d.get("delta"),
                        "best_epoch": d.get("best_epoch"),
                    }
                )
                print("skip tobarra (cached)", flush=True)
                continue
        rows.append(
            run_fold(
                held,
                lofo_root=lofo_root,
                out_root=out_root,
                init_weights=init,
                epochs=1 if args.smoke else args.epochs,
                feature_schema=args.feature_schema,
                schema_path_id=args.schema_path_id,
                in_channels=in_ch,
                batch_size=args.batch_size,
                smoke=bool(args.smoke),
                gate_never_channels=not bool(args.no_gate_never_channels),
                force_gate_never_channels=bool(args.force_gate_never_channels),
                allow_never_channels=bool(args.allow_never_channels),
                never_allowlist=never_allow or None,
                never_allowlist_honesty=args.never_allowlist_honesty,
            )
        )

    deltas = [
        float(r["improvement_vs_copy_iou"])
        for r in rows
        if r.get("improvement_vs_copy_iou") is not None
    ]
    report = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "protocol": "clm_lofo_metrics_lift_v1" if args.schema_path_id else "clm_lofo_v1_all_folds",
        "lofo_root": str(lofo_root.as_posix()),
        "out_root": str(out_root.as_posix()),
        "feature_schema": args.feature_schema,
        "schema_path_id": args.schema_path_id,
        "work_class": work_class_for_schema(
            args.feature_schema, schema_path_id=args.schema_path_id
        ),
        "in_channels": in_ch,
        "smoke": bool(args.smoke),
        "folds": rows,
        "summary": {
            "n_folds": len(rows),
            "mean_delta": sum(deltas) / len(deltas) if deltas else None,
            "min_delta": min(deltas) if deltas else None,
            "all_positive": all(d > 0 for d in deltas) if deltas else False,
            "keep_claim": False if args.smoke else None,
        },
        "honesty": [
            "IoU ≠ ROS",
            "field fusion OFF",
            "VAL-only early stop on improvement_vs_copy_iou",
            "smoke never claims KEEP",
        ],
    }
    if args.smoke:
        out = args.report_out or (
            ROOT / "outputs" / "ml_eval" / "lab_loop" / "lofo_train_smoke_report.json"
        )
    else:
        out = args.report_out or (ROOT / "docs" / "CLM_LOFO_ALL_FOLDS_REPORT.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print("Wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
