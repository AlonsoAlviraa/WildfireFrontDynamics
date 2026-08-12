"""ML lab product CLI: list/show/predict/card/doctor/cases/curve/freeze/smoke/lofo.

Architecture (product ROI — no retrain)
---------------------------------------
* Dual rails: **lab ML** vs **field_ops**; IoU ≠ ROS; ``ml_product_go`` true
  (human promote 2026-08-05) — never silent auto-flip.
* Scorecard / rails / rank-reject come from ``product_facade`` + ``protocol_rails``
  (features → calibrator → rank/reject → scorecard). CLI does **not** reimplement
  conf math or ECE thrash aggregation.
* Freeze **iter1 reject** (VAL-only thr) as default lab surface.
* Multi-fire honesty first-class (Tobarra hard, W3 external).
* Field fusion stays OFF. Lab GO ≠ field fusion.

Registered from ``wildfire_front.cli.build_parser`` via ``register_ml_commands``.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .cli_report import print_json
from .ml.product_facade import (
    DEAD_PATHS,
    DEFAULT_MULTI_FIRE,
    DEFAULT_PRODUCT_ID,
    DEFAULT_RAILS,
    DEFAULT_RANK_REJECT,
    ITER1_LOCKED_REJECT_THR,
    ML_PRODUCT_GO_DEFAULT,
    OPS_PRODUCT_ID,
    RECOMMENDED_LAB_SURFACE,
    ProductFacadeError,
    assert_lab_rails,
    default_facade_from_repo,
    refuse_dead_path,
)
from .ml.protocol_rails import (
    FORBIDDEN_THRASH_PATHS,
    LAB_ML_BANNER,
    assert_field_fusion_off,
    assert_rails_honest,
    multi_fire_honesty_dict,
    rank_abstain_protocol_dict,
)
from .product.teach_path import resolve_repo_root

AddGlobalFlags = Callable[[argparse.ArgumentParser], None]

_ML_BANNER = LAB_ML_BANNER

_ML_EPILOG = f"""
honesty:
  · {_ML_BANNER}
  · Default product: clm_ensemble_v34 via product_facade (fallback clm_v28; research ndws_v21)
  · Catalog holdout IoU 0.8963 = provenance only — not live certainty
  · Freeze iter1 reject thr (VAL-only); ranking + abstain share one protocol
  · ml_product_go true (human promote 2026-08-05); field_ops fusion OFF
  · Dead thrash closed: same-holdout ECE retune; Tobarra KEEP reopen; no auto_ml_product_go

examples:
  wildfire-front ml list
  wildfire-front ml show
  wildfire-front ml show --json
  wildfire-front ml doctor
  wildfire-front ml cases
  wildfire-front ml cases --bucket accepted_low_iou
  wildfire-front ml curve
  wildfire-front ml freeze
  wildfire-front ml smoke
  wildfire-front ml lofo
  wildfire-front ml next
  wildfire-front ml card --mode offline --scenario hold
  wildfire-front ml predict --list-products
  wildfire-front ml predict --product clm_ensemble_v34 --npz path/patch.npz

docs:
  docs/ML_PRODUCT_START_HERE.md · docs/PLAN_ML_PRODUCT_USABLE.md
  docs/ML_PRODUCT_SCORECARD.json · docs/METRICS_HONESTY_IOU_NE_ROS.md
"""


def register_ml_commands(
    commands: argparse._SubParsersAction,
    *,
    add_global_flags: AddGlobalFlags,
) -> argparse.ArgumentParser:
    """Attach ``ml`` command group and subcommands to the root CLI."""
    ml = commands.add_parser(
        "ml",
        help="ML lab product (list/show/.../lofo/next; bare → hub)",
        description=(
            "ML lab product CLI for next-day mask products (clm_ensemble_v34 default). "
            f"{_ML_BANNER}. Offline list/show/doctor/cases/curve/freeze/smoke/lofo/next work "
            "without weights (curve needs Head A caches if regenerating; reads loop JSON "
            "offline); predict/card need weights for live inference (offline card does not). "
            "Bare `ml` (no SUBCOMMAND) prints a lab hub (exit 0) — not an error."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=_ML_EPILOG,
    )
    # Parent flags so `ml --json` works without a subcommand (hub path).
    add_global_flags(ml)
    # Bare `ml` → hub (required=False); ML product gates frozen — hub is discoverability only.
    ml_subs = ml.add_subparsers(dest="ml_command", required=False, metavar="SUBCOMMAND")

    # ── list ──────────────────────────────────────────────────────────────
    lst = ml_subs.add_parser(
        "list",
        help="List catalog products + default + not_for (offline OK)",
        description=(
            f"List ML products from models/catalog.json. {_ML_BANNER}. "
            "Does not require .pt weights (ready flag reports presence)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="example:\n  wildfire-front ml list\n  wildfire-front ml list --json",
    )
    add_global_flags(lst)

    # ── show ──────────────────────────────────────────────────────────────
    show = ml_subs.add_parser(
        "show",
        help="Scorecard snapshot: U1 IoU, ECE, catalog, facade pipeline, fusion rails",
        description=(
            "Honest ML scorecard from docs JSON + product_facade rails; when Head A "
            "caches exist, also runs ClmEnsembleV34Facade features→conf→rank/reject→scorecard. "
            f"{_ML_BANNER}. Offline — no .pt weights required."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="example:\n  wildfire-front ml show\n  wildfire-front ml show --json",
    )
    add_global_flags(show)

    # ── predict ───────────────────────────────────────────────────────────
    pred = ml_subs.add_parser(
        "predict",
        help=(
            "Product facade path: features→calibrator→rank/reject "
            f"(default {DEFAULT_PRODUCT_ID}; needs weights for inference)"
        ),
        description=(
            "In-process product path via product_catalog + spread_predictor "
            "(conf/abstain through ClmEnsembleV34Facade rank/reject; freeze iter1 thr). "
            f"Use --list-products without weights. Missing .pt → exit 1 (no traceback). {_ML_BANNER}."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  wildfire-front ml predict --list-products\n"
            "  wildfire-front ml predict --product clm_ensemble_v34 --npz path/patch.npz\n"
            "  wildfire-front ml predict --product clm_v28 --npz path/patch.npz --eval\n"
        ),
    )
    pred.add_argument(
        "--product",
        default=None,
        help=f"Catalog product id (default: {DEFAULT_PRODUCT_ID} via product_facade)",
    )
    pred.add_argument(
        "--list-products",
        action="store_true",
        help="List products via product_catalog (same catalog loader as facade path)",
    )
    pred.add_argument("--npz", type=str, default=None, help="Input patch NPZ or directory")
    pred.add_argument("--output", type=str, default=None, help="Write prediction NPZ")
    pred.add_argument("--eval", action="store_true", help="Metrics if target_fire present")
    pred.add_argument("--max-patches", type=int, default=0, help="0 = all")
    pred.add_argument("--with-uncertainty", action="store_true")
    pred.add_argument("--ml-live-json", type=str, default=None)
    pred.add_argument("--calibrator", type=str, default=None)
    pred.add_argument("--manifest", type=str, default=None)
    pred.add_argument("--weights", type=str, default=None)
    pred.add_argument(
        "--abstain-below",
        type=float,
        default=None,
        help=(
            f"Confidence thr for abstain (default: freeze iter1 reject "
            f"{ITER1_LOCKED_REJECT_THR}; VAL-only product surface)"
        ),
    )
    add_global_flags(pred)

    # ── card ──────────────────────────────────────────────────────────────
    card = ml_subs.add_parser(
        "card",
        help="ML live → Decision Card demo (offline default; discoverable wrapper)",
        description=(
            "Wrapper for scripts/run_ml_live_card_demo.py. "
            "Offline mode needs no weights. Live mode needs ensemble weights. "
            f"{_ML_BANNER}."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  wildfire-front ml card --mode offline --scenario hold\n"
            "  wildfire-front ml card --mode offline --scenario abstain\n"
            "  wildfire-front ml card --mode offline --scenario go\n"
        ),
    )
    card.add_argument(
        "--mode",
        choices=("offline", "live", "from-json"),
        default="offline",
        help="Demo mode (default: offline — no weights)",
    )
    card.add_argument(
        "--scenario",
        choices=("hold", "abstain", "identity", "go"),
        default="hold",
        help="Offline scenario (default: hold). 'go' maps to hold under research_open lab demo.",
    )
    card.add_argument(
        "--policy",
        default="research_open",
        help="Decision policy (default: research_open). field_ops never gets fusion ON from this demo.",
    )
    card.add_argument(
        "--output",
        type=Path,
        default=None,
        metavar="DIR",
        help="Output directory (default: outputs/ml_live_card_demo)",
    )
    card.add_argument("--event-id", default="ml_live_card_demo")
    card.add_argument("--npz", type=str, default=None, help="For --mode live")
    card.add_argument("--ml-prediction", type=str, default=None, help="For --mode from-json")
    card.add_argument("--max-patches", type=int, default=1)
    add_global_flags(card)

    # ── doctor ────────────────────────────────────────────────────────────
    doc = ml_subs.add_parser(
        "doctor",
        help="Check weights, catalog, calibrator JSON, PYTHONPATH (offline OK)",
        description=(
            "Pre-flight for ML lab path. Missing weights are reported honestly "
            f"(exit 0 with structure). {_ML_BANNER}."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="example:\n  wildfire-front ml doctor\n  wildfire-front ml doctor --json",
    )
    add_global_flags(doc)

    # ── cases (teach fail buckets + LOFO board) ───────────────────────────
    cases = ml_subs.add_parser(
        "cases",
        help="Teach fail-case buckets + LOFO/reject board (offline, lab only)",
        description=(
            "Productized teaching surface from lab loop fail_cases + LOFO + locked reject. "
            f"No weights. Not field_ops. {_ML_BANNER}."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  wildfire-front ml cases\n"
            "  wildfire-front ml cases --json\n"
            "  wildfire-front ml cases --bucket accepted_low_iou\n"
            "  wildfire-front ml cases --bucket rejected_high_iou --limit 5\n"
        ),
    )
    cases.add_argument(
        "--bucket",
        default=None,
        choices=("accepted_low_iou", "rejected_high_iou"),
        help="Focus one fail-case bucket",
    )
    cases.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Max detailed rows when --bucket set (default 5)",
    )
    cases.add_argument(
        "--rows",
        action="store_true",
        help="Include raw fail-case rows (respects --bucket/--limit)",
    )
    add_global_flags(cases)

    # ── curve (risk–coverage) ─────────────────────────────────────────────
    curve = ml_subs.add_parser(
        "curve",
        help="Risk–coverage curve + thr operating points (lab only, offline)",
        description=(
            "Show selective coverage→IoU curve and thr operating points from lab loop "
            f"artifacts (or build on the fly from Head A caches). {_ML_BANNER}."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  wildfire-front ml curve\n"
            "  wildfire-front ml curve --json\n"
            "  wildfire-front ml curve --rebuild\n"
        ),
    )
    curve.add_argument(
        "--rebuild",
        action="store_true",
        help="Recompute from Head A caches + production calibrator (writes lab_loop JSON)",
    )
    add_global_flags(curve)

    # ── freeze (handoff card) ─────────────────────────────────────────────
    frz = ml_subs.add_parser(
        "freeze",
        help="Lab freeze / handoff card (iters 1–6 consolidated; not field promote)",
        description=(
            "Consolidate lab loop evidence into a single honest freeze card. "
            f"lab_usable stamps ml_product_go true (human promote); field fusion OFF. "
            f"{_ML_BANNER}."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  wildfire-front ml freeze\n"
            "  wildfire-front ml freeze --json\n"
            "  wildfire-front ml freeze --write\n"
        ),
    )
    frz.add_argument(
        "--write",
        action="store_true",
        help="Re-run freeze script (writes lab_loop_v34_freeze_latest.json + latest pointer)",
    )
    add_global_flags(frz)

    # ── smoke (post-freeze regression) ────────────────────────────────────
    sm = ml_subs.add_parser(
        "smoke",
        help="Post-freeze smoke: freeze + offline CLI + rails (lab only)",
        description=(
            "Regression gate after lab freeze. Exit 0 if all steps pass. "
            f"Does not flip field rails. {_ML_BANNER}."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  wildfire-front ml smoke\n"
            "  wildfire-front ml smoke --json\n"
            "  wildfire-front ml smoke --write\n"
            "  wildfire-front ml smoke --pytest\n"
        ),
    )
    sm.add_argument(
        "--write",
        action="store_true",
        help="Write smoke JSON + update lab_loop_v34_latest.json",
    )
    sm.add_argument(
        "--pytest",
        action="store_true",
        help="Also run focused lab pytest suite (slower)",
    )
    add_global_flags(sm)

    # ── lofo (multi-fire board) ───────────────────────────────────────────
    lofo = ml_subs.add_parser(
        "lofo",
        help="Multi-fire LOFO mask IoU scoreboard (not U1 ECE; lab only)",
        description=(
            "Leave-one-fire-out scoreboard from outputs/ml_eval/lofo_v1. "
            f"Protocol ≠ U1 Head A ECE. {_ML_BANNER}."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  wildfire-front ml lofo\n"
            "  wildfire-front ml lofo --json\n"
            "  wildfire-front ml lofo --write\n"
        ),
    )
    lofo.add_argument(
        "--write",
        action="store_true",
        help="Write lab_loop_v34_lofo_board_latest.json + update latest pointer",
    )
    add_global_flags(lofo)

    # ── lift (metrics lift board) ─────────────────────────────────────────
    lift = ml_subs.add_parser(
        "lift",
        help="Metrics lift board (LOFO G1/G2 baselines + candidate; lab only)",
        description=(
            "Seal LOFO mean/min + U1 baselines and optional candidate root into "
            "lab_loop_v34_metrics_lift_latest.json. Does not retrain or claim KEEP. "
            f"{_ML_BANNER}."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  wildfire-front ml lift --baselines-only\n"
            "  wildfire-front ml lift --candidate-root outputs/ml_eval/lofo_v1\n"
            "  wildfire-front ml lift --json\n"
        ),
    )
    lift.add_argument(
        "--baselines-only",
        action="store_true",
        help="Seal baselines; no candidate metrics",
    )
    lift.add_argument(
        "--candidate-root",
        type=str,
        default=None,
        help="Root with {FOLD}/evaluation_metrics.json children",
    )
    lift.add_argument(
        "--candidate-board",
        type=str,
        default=None,
        help="Optional pre-built LOFO board JSON",
    )
    lift.add_argument("--experiment-id", type=str, default=None)
    lift.add_argument(
        "--write",
        action="store_true",
        default=True,
        help="Write lab_loop_v34_metrics_lift_latest.json (default true)",
    )
    lift.add_argument(
        "--no-write",
        action="store_true",
        help="Do not write board JSON",
    )
    add_global_flags(lift)

    # ── next (readiness gate) ─────────────────────────────────────────────
    nxt = ml_subs.add_parser(
        "next",
        help="Next-signal readiness (W1 Head A LOFO path; not metric retune)",
        description=(
            "Probe READY/BLOCKED work items after lab freeze. "
            f"Does not unfreeze field rails. {_ML_BANNER}."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  wildfire-front ml next\n"
            "  wildfire-front ml next --json\n"
            "  wildfire-front ml next --write\n"
        ),
    )
    nxt.add_argument(
        "--write",
        action="store_true",
        help="Write lab_loop_v34_next_gate_latest.json + update latest pointer",
    )
    add_global_flags(nxt)

    return ml


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _repo(preferred: Path | None = None) -> Path:
    return resolve_repo_root(preferred)


def _facade_cli_rails() -> dict[str, Any]:
    """Dual-product rails from product facade (never auto-promote / fusion ON)."""
    # Seal dead thrash / KEEP reopen (architecture refuse — not optional folklore).
    for dead in (
        "same_holdout_ece_retune",
        "tobarra_keep_reopen_same_recipe",
        "auto_ml_product_go",
        "field_ops_ml_live_fusion_on",
    ):
        try:
            refuse_dead_path(dead)
        except ProductFacadeError:
            pass
        else:
            raise ProductFacadeError(f"dead path not sealed: {dead}")

    r = assert_lab_rails(DEFAULT_RAILS)
    base = r.as_dict()
    base.update(
        {
            "banner": _ML_BANNER,
            "field_ops_ml_live_fusion": "OFF",
            "val_only_threshold_tune": True,
            "locked_reject_thr": float(ITER1_LOCKED_REJECT_THR),
            "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
            "freeze_iter1_reject": True,
            "stop_ece_thrash_on_same_test": True,
            "tobarra_keep_reopen": False,
            "product_facade": "wildfire_front.ml.product_facade",
            "facade_class": "ClmEnsembleV34Facade",
            "pipeline": "features→calibrator→rank/reject→scorecard",
            "dead_paths": sorted(DEAD_PATHS | FORBIDDEN_THRASH_PATHS),
        }
    )
    assert_rails_honest(base, require_iter1_reject_default=True)
    assert_field_fusion_off(
        allow_ml_live_in_fusion=False,
        field_ops_ml_live_fusion="OFF",
    )
    return base


def _jsonable_rank_reject_surface(surface: dict[str, Any]) -> dict[str, Any]:
    """Drop large arrays from a facade rank_reject / pipeline surface for CLI JSON."""
    skip = {"keep_mask", "conf", "keep"}
    out: dict[str, Any] = {}
    for k, v in surface.items():
        if k in skip:
            continue
        if hasattr(v, "tolist") and not isinstance(v, (str, bytes, dict, list)):
            continue  # numpy arrays
        out[k] = v
    return out


def _run_facade_pipeline_from_caches(root: Path) -> dict[str, Any] | None:
    """Offline ClmEnsembleV34Facade path: Head A features → conf → rank/reject → scorecard.

    Uses production calibrator + freeze **iter1 reject** thr (VAL-only surface).
    Returns None when caches / calibrator are missing (show stays docs-only).
    """
    test_ha = root / "outputs" / "ml_eval" / "test_head_a_features.npz"
    if not test_ha.is_file():
        return None
    try:
        facade = default_facade_from_repo(root)
    except (OSError, FileNotFoundError, ProductFacadeError, ValueError):
        return None

    try:
        import numpy as np

        with np.load(test_ha) as data:
            features = np.asarray(data["features"], dtype=np.float64)
            labels = (
                np.asarray(data["labels"], dtype=np.float64) if "labels" in data.files else None
            )
            ious = np.asarray(data["ious"], dtype=np.float64) if "ious" in data.files else None
        pipe = facade.run_pipeline(features, ious=ious, labels=labels, split="test")
    except Exception:  # noqa: BLE001 — show path must stay offline-resilient
        return None

    conf = pipe.get("conf")
    conf_summary: dict[str, Any] | None = None
    if conf is not None:
        import numpy as np

        c = np.asarray(conf, dtype=np.float64).ravel()
        conf_summary = {
            "n": int(c.size),
            "mean": float(np.mean(c)) if c.size else None,
            "p50": float(np.median(c)) if c.size else None,
        }

    return {
        "present": True,
        "source": "outputs/ml_eval/test_head_a_features.npz",
        "product_id": pipe.get("product_id") or DEFAULT_PRODUCT_ID,
        "pipeline": pipe.get("pipeline") or "features→calibrator→rank/reject→scorecard",
        "facade_class": "ClmEnsembleV34Facade",
        "product_facade": "wildfire_front.ml.product_facade",
        "calibrator_id": pipe.get("calibrator_id"),
        "locked_reject_thr": pipe.get("locked_reject_thr") or float(ITER1_LOCKED_REJECT_THR),
        "recommended_lab_surface": pipe.get("recommended_lab_surface") or RECOMMENDED_LAB_SURFACE,
        "n_patches": pipe.get("n_patches"),
        "conf_summary": conf_summary,
        "rank_reject": _jsonable_rank_reject_surface(
            pipe.get("rank_reject") if isinstance(pipe.get("rank_reject"), dict) else {}
        ),
        "scorecard": pipe.get("scorecard"),
        "rails": pipe.get("rails") or facade.rails_snapshot(),
        "multi_fire": pipe.get("multi_fire") or DEFAULT_MULTI_FIRE.as_dict(),
        "ml_product_go": bool(
            (pipe.get("rails") or {}).get("ml_product_go", ML_PRODUCT_GO_DEFAULT)
            if isinstance(pipe.get("rails"), dict)
            else ML_PRODUCT_GO_DEFAULT
        ),
        "field_ops_ml_live_fusion": "OFF",
        "note": (
            "Live facade pipeline on holdout Head A caches (VAL thr freeze; "
            "ml_product_go true human promote; not same-holdout ECE retune; "
            "not field fusion)."
        ),
    }


def build_ml_scorecard_snapshot(repo: Path | None = None) -> dict[str, Any]:
    """Scorecard snapshot via product facade path + docs metrics (honest dual rails).

    Does **not** reimplement conf/rank math or ECE thrash aggregation. U1 numbers
    are read from docs scorecard JSON; rails / surface / multi-fire come from
    ``product_facade`` + ``protocol_rails``. When Head A caches exist, also runs
    ``ClmEnsembleV34Facade.run_pipeline`` (features→conf→rank/reject→scorecard).
    """
    root = _repo(repo)
    scorecard_path = root / "docs" / "ML_PRODUCT_SCORECARD.json"
    promote_path = root / "docs" / "ML_U1_PROMOTE_RECORD.json"
    catalog_path = root / "models" / "catalog.json"
    policies_path = root / "config" / "decision_policies.json"

    sc = _load_json(scorecard_path) or {}
    prom = _load_json(promote_path) or {}
    catalog = _load_json(catalog_path) or {}
    policies = _load_json(policies_path) or {}

    primary = sc.get("primary") or prom.get("primary_eval") or {}
    unc = sc.get("uncertainty") or prom.get("uncertainty") or {}
    gates = sc.get("gates") or prom.get("gates_snapshot") or {}
    prov = sc.get("provenance") or {}
    cat_ref = prov.get("catalog_holdout_test_reference") or {}

    # Live config check (must match facade: fusion OFF). CLI never flips ON.
    field_ops = (policies.get("policies") or {}).get("field_ops") or {}
    research_open = (policies.get("policies") or {}).get("research_open") or {}
    field_ops_fusion = bool(field_ops.get("allow_ml_live_in_fusion", False))
    research_fusion = bool(research_open.get("allow_ml_live_in_fusion", False))
    assert_field_fusion_off(
        allow_ml_live_in_fusion=field_ops_fusion,
        field_ops_ml_live_fusion="ON" if field_ops_fusion else "OFF",
    )

    facade_rails = _facade_cli_rails()
    # Human promote 2026-08-05: ml_product_go true; refuse silent auto_ml_product_go.
    rank_reject = rank_abstain_protocol_dict(
        locked_reject_thr=float(ITER1_LOCKED_REJECT_THR),
        recommended_lab_surface=RECOMMENDED_LAB_SURFACE,
    )
    rank_reject = {
        **rank_reject,
        "product_facade": "wildfire_front.ml.product_facade",
        "facade_class": "ClmEnsembleV34Facade",
        "pipeline": "features→calibrator→rank/reject→scorecard",
        "rank_reject_config": DEFAULT_RANK_REJECT.as_dict(),
    }
    multi_fire = {
        **multi_fire_honesty_dict(),
        "facade": DEFAULT_MULTI_FIRE.as_dict(),
        "lofo_first_class": True,
        "w3_first_class": True,
        "do_not_reopen_tobarra_keep": True,
        "do_not_universalize_u1": True,
        "note": (
            "Multi-fire honesty is first-class: Tobarra = hard transfer (KILL); "
            "W3 external = report-only with frozen thr/cal; LOFO ≠ U1 ECE."
        ),
    }

    # Single product path when caches present (not docs re-aggregation).
    facade_pipeline = _run_facade_pipeline_from_caches(root)

    product_id = (
        sc.get("product_id")
        or prom.get("product_id")
        or catalog.get("default_product")
        or DEFAULT_PRODUCT_ID
    )

    return {
        "schema": "wfd_ml_show_snapshot_v1",
        "banner": _ML_BANNER,
        "product_id": product_id,
        "default_product": catalog.get("default_product") or DEFAULT_PRODUCT_ID,
        "fallback_product": catalog.get("fallback_ml_product"),
        "research_product": catalog.get("research_ml_product"),
        "ops_product_separate": catalog.get("ops_product") or OPS_PRODUCT_ID,
        "product_facade": "wildfire_front.ml.product_facade",
        "facade_class": "ClmEnsembleV34Facade",
        "pipeline": "features→calibrator→rank/reject→scorecard",
        "u1": {
            "mean_iou": primary.get("model_iou"),
            "n_patches": primary.get("n_patches"),
            "split": primary.get("model_iou_split") or sc.get("u1_eval_split") or "test",
            "ece_patch_conf": unc.get("ece_patch_conf"),
            "selective_iou_at_80": unc.get("selective_iou_at_80pct_coverage"),
            "u1_test_honest": bool(gates.get("u1_test_honest", False)),
        },
        "catalog_holdout": {
            # Never invent metrics: only surface catalog IoU when provenance JSON has it
            "test_iou": cat_ref.get("test_iou"),  # None if missing (not default 0.8963)
            "note": cat_ref.get("note")
            or (
                "Provenance only — not live certainty, not U1 eval mean, not ROS"
                if cat_ref.get("test_iou") is not None
                else "Catalog holdout IoU unknown (no provenance reference in scorecard)"
            ),
        },
        "gates": {
            # Human promote 2026-08-05: stamp true; no silent auto-flip; fusion OFF.
            "ml_product_go": bool(facade_rails.get("ml_product_go", ML_PRODUCT_GO_DEFAULT)),
            "u1_test_honest": bool(gates.get("u1_test_honest", False)),
            "allow_ml_live_in_fusion_recommended": bool(
                gates.get("allow_ml_live_in_fusion_recommended", False)
                or sc.get("allow_ml_live_in_fusion_recommended", False)
            ),
            "promote_eligible": bool(gates.get("promote_eligible", False)),
            "lab_surface_iter1_reject": True,
        },
        "fusion_rails": {
            "field_ops_allow_ml_live_in_fusion": False,
            "field_ops_ml_live_fusion": "OFF",
            "research_open_allow_ml_live_in_fusion": research_fusion,
            "research_open_note": "experimental lab only — not tactical"
            if research_fusion
            else "off",
            "config_field_ops_allow_ml_live_in_fusion": field_ops_fusion,
        },
        "rails": facade_rails,
        "rank_reject_protocol": rank_reject,
        "rank_reject": DEFAULT_RANK_REJECT.as_dict(),
        "multi_fire_honesty": multi_fire,
        "facade_pipeline": facade_pipeline,
        "paths": {
            "scorecard": str(scorecard_path.relative_to(root))
            if scorecard_path.is_file()
            else str(scorecard_path),
            "promote_record": str(promote_path.relative_to(root))
            if promote_path.is_file()
            else str(promote_path),
            "catalog": str(catalog_path.relative_to(root))
            if catalog_path.is_file()
            else str(catalog_path),
            "policies": str(policies_path.relative_to(root))
            if policies_path.is_file()
            else str(policies_path),
        },
        "presence": {
            "scorecard": scorecard_path.is_file(),
            "promote_record": promote_path.is_file(),
            "catalog": catalog_path.is_file(),
            "policies": policies_path.is_file(),
            "facade_pipeline": bool(facade_pipeline and facade_pipeline.get("present")),
        },
        "honesty": [
            _ML_BANNER,
            (
                "Catalog holdout IoU is provenance only (not live certainty)"
                if cat_ref.get("test_iou") is not None
                else "Catalog holdout IoU not present in scorecard provenance"
            ),
            "ml_product_go true (human promote 2026-08-05; no silent auto-flip)",
            "field_ops fusion must stay OFF (lab GO ≠ field fusion)",
            f"freeze lab surface {RECOMMENDED_LAB_SURFACE} thr≈{ITER1_LOCKED_REJECT_THR}",
            "same-holdout ECE thrash closed; Tobarra KEEP reopen closed",
            "pipeline: features→calibrator→rank/reject→scorecard (ClmEnsembleV34Facade)",
        ],
        "lab_loop_reject": _load_lab_loop_reject(root),
        "repo_root": str(root),
    }


def _load_lab_loop_reject(root: Path) -> dict[str, Any] | None:
    """Lab loop **iter1 reject** surface only (research_open).

    Dead thrash paths (same-holdout ECE retune / combined_reject_after_ece) are
    **not** re-aggregated as promote hooks. Freeze surface is always
    ``iter1_reject_only`` at the VAL-locked thr.
    """
    latest = _load_json(root / "outputs" / "ml_eval" / "lab_loop" / "lab_loop_v34_latest.json")
    path_reject = root / "outputs" / "ml_eval" / "lab_loop" / "lab_loop_v34_reject_latest.json"
    data = _load_json(path_reject)
    if not data and not latest:
        return None

    tuned = (data or {}).get("tuned") or {}
    base = tuned.get("test_metrics_baseline") or {}
    t = tuned.get("test_metrics_tuned") or {}
    verdict = (data or {}).get("verdict") or {}

    thr = tuned.get("abstain_threshold")
    abstain_tuned = t.get("abstain_rate")
    iou_tuned = t.get("mean_iou_accepted")
    reject_improved = bool(verdict.get("lab_reject_surface_improved", True))
    lofo: dict[str, Any] = {}
    holdout_u1_iou = None
    holdout_u1_ece = None
    gen_note = None
    iter4 = False
    path = "outputs/ml_eval/lab_loop/lab_loop_v34_reject_latest.json"
    iterations: list[str] = ["reject"] if data else []

    if latest and isinstance(latest.get("summary"), dict):
        summ = latest["summary"]
        c = summ.get("reject") or summ.get("combined") or {}
        i1 = summ.get("iter1") or {}
        lofo = summ.get("lofo") or {}
        thr = thr if thr is not None else (c.get("thr") or i1.get("abstain_threshold"))
        abstain_tuned = (
            abstain_tuned
            if abstain_tuned is not None
            else (
                c.get("abstain_rate") or c.get("test_abstain_rate") or i1.get("test_abstain_rate")
            )
        )
        iou_tuned = (
            iou_tuned
            if iou_tuned is not None
            else (
                c.get("iou_accepted") or c.get("test_iou_accepted") or i1.get("test_iou_accepted")
            )
        )
        reject_improved = bool(summ.get("iter1_reject_improved", reject_improved))
        holdout_u1_iou = summ.get("holdout_u1_iou")
        holdout_u1_ece = summ.get("holdout_u1_ece")
        gen_note = summ.get("generalization_note")
        iter4 = bool(summ.get("iter4_generalization_table", False))
        path = "outputs/ml_eval/lab_loop/lab_loop_v34_latest.json"
        iterations = list((latest.get("iterations") or {}).keys()) or ["reject"]

    if thr is None:
        thr = float(ITER1_LOCKED_REJECT_THR)

    return {
        "present": True,
        "path": path,
        "label": "lab / research_open only — not field product",
        "abstain_threshold": thr,
        "confidence_temperature": tuned.get("confidence_temperature") or 1.0,
        "test_abstain_rate_baseline": base.get("abstain_rate"),
        "test_abstain_rate_tuned": abstain_tuned,
        "test_mean_iou_accepted_baseline": base.get("mean_iou_accepted"),
        "test_mean_iou_accepted_tuned": iou_tuned,
        # Holdout U1 ECE is report-only residual — not a same-holdout retune claim.
        "test_ece_full_baseline": holdout_u1_ece or t.get("ece_full") or base.get("ece_full"),
        "test_ece_full_tuned": None,  # dead thrash: no ECE retune surface
        "ece_method": None,
        "ece_improved": False,  # iters 2–3 same-holdout ECE thrash closed
        "lab_reject_surface_improved": reject_improved,
        "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
        "freeze_iter1_reject": True,
        "locked_reject_thr": float(ITER1_LOCKED_REJECT_THR),
        "field_product": False,
        "ml_product_go": bool(ML_PRODUCT_GO_DEFAULT),
        "iterations": iterations,
        "lofo_n_folds": lofo.get("n_folds"),
        "lofo_iou_mean": lofo.get("model_iou_mean"),
        "lofo_iou_std": lofo.get("model_iou_std"),
        "lofo_spread": lofo.get("spread_max_minus_min"),
        "holdout_u1_iou": holdout_u1_iou,
        "generalization_note": gen_note,
        "stop_ece_thrash_on_same_test": True,
        "tobarra_keep_reopen": False,
        "iter4_generalization_table": iter4,
        "dead_thrash_closed": True,
        "dead_paths": sorted(DEAD_PATHS | FORBIDDEN_THRASH_PATHS),
        "product_facade": "wildfire_front.ml.product_facade",
    }


def format_ml_show_human(snap: dict[str, Any]) -> str:
    """Human table for ``ml show``."""
    u1 = snap.get("u1") or {}
    cat = snap.get("catalog_holdout") or {}
    gates = snap.get("gates") or {}
    fusion = snap.get("fusion_rails") or {}
    rails = snap.get("rails") or {}
    mf = snap.get("multi_fire_honesty") or {}
    rr = snap.get("rank_reject_protocol") or snap.get("rank_reject") or {}
    lines = [
        "ML product scorecard (lab)",
        f"  banner:           {snap.get('banner')}",
        f"  product:          {snap.get('product_id')}",
        f"  default:          {snap.get('default_product')}",
        f"  fallback:         {snap.get('fallback_product')}",
        f"  research:         {snap.get('research_product')}",
        f"  ops (separate):   {snap.get('ops_product_separate')}",
        f"  pipeline:         {rails.get('pipeline') or 'features→calibrator→rank/reject→scorecard'}",
        "",
        "U1 TEST honest (lab eval)",
        f"  mean IoU:         {_fmt_num(u1.get('mean_iou'))}",
        f"  selective@80:     {_fmt_num(u1.get('selective_iou_at_80'))}",
        f"  ECE:              {_fmt_num(u1.get('ece_patch_conf'))}",
        f"  n_patches:        {u1.get('n_patches') if u1.get('n_patches') is not None else '—'}",
        f"  split:            {u1.get('split') or '—'}",
        f"  u1_test_honest:   {u1.get('u1_test_honest')}",
        "",
        "Catalog holdout (provenance only)",
        f"  test_iou:         {_fmt_num(cat.get('test_iou'))}",
        f"  note:             {cat.get('note')}",
        "",
        "Gates / rails (lab eligibility ≠ field_ops ON)",
        f"  product_rail:                     {rails.get('product_rail', 'lab_ml')} vs "
        f"{rails.get('ops_rail') or rails.get('field_rail') or 'field_ops'}",
        f"  ml_product_go:                    {gates.get('ml_product_go')}",
        f"  allow_ml_live_in_fusion_recommended: "
        f"{gates.get('allow_ml_live_in_fusion_recommended')} "
        f"(research/lab eligibility — field_ops stays OFF)",
        f"  promote_eligible:                 {gates.get('promote_eligible')}",
        f"  field_ops ML live fusion:         {fusion.get('field_ops_ml_live_fusion')}  "
        f"(config rail — never auto-ON from recommended)",
        f"  research_open live fusion:        "
        f"{'experimental ON' if fusion.get('research_open_allow_ml_live_in_fusion') else 'OFF'}"
        f"  (lab demos only; not tactical)",
        f"  freeze surface:                   {rails.get('recommended_lab_surface') or RECOMMENDED_LAB_SURFACE}",
        f"  locked reject thr:                {_fmt_num(rr.get('locked_reject_thr') or rails.get('locked_reject_thr') or ITER1_LOCKED_REJECT_THR)}",
        f"  stop ECE thrash:                  {rails.get('stop_ece_thrash_on_same_test', True)}",
        f"  facade class:                     {snap.get('facade_class') or rails.get('facade_class') or 'ClmEnsembleV34Facade'}",
        "",
        "Multi-fire honesty (first-class)",
        f"  Tobarra:          {(mf.get('tobarra') or {}).get('verdict') or (mf.get('tobarra') or {}).get('class') or 'hard/KILL'}",
        f"  W3 external:      {(mf.get('w3_external') or {}).get('role') or 'external_stress'}",
        f"  note:             {mf.get('note') or '—'}",
        "",
    ]
    fp = snap.get("facade_pipeline")
    if fp and fp.get("present"):
        sc_live = fp.get("scorecard") or {}
        unc_live = sc_live.get("uncertainty") or {}
        thr_m = (fp.get("rank_reject") or {}).get("thr_reject_metrics") or {}
        lines.extend(
            [
                "Facade pipeline (ClmEnsembleV34Facade — features→conf→rank/reject→scorecard)",
                f"  source:               {fp.get('source')}",
                f"  n_patches:            {fp.get('n_patches') if fp.get('n_patches') is not None else '—'}",
                f"  locked reject thr:    {_fmt_num(fp.get('locked_reject_thr'))}",
                f"  surface:              {fp.get('recommended_lab_surface') or RECOMMENDED_LAB_SURFACE}",
                f"  conf mean/p50:        {_fmt_num((fp.get('conf_summary') or {}).get('mean'))} / "
                f"{_fmt_num((fp.get('conf_summary') or {}).get('p50'))}",
                f"  thr abstain_rate:     {_fmt_num(thr_m.get('abstain_rate') or unc_live.get('abstain_rate'))}",
                f"  thr IoU accepted:     {_fmt_num(thr_m.get('mean_iou_accepted') or unc_live.get('mean_iou_accepted'))}",
                f"  ECE (report only):    {_fmt_num(unc_live.get('ece_patch_conf'))}",
                f"  ml_product_go:        {fp.get('ml_product_go', ML_PRODUCT_GO_DEFAULT)}",
                f"  field fusion:         {fp.get('field_ops_ml_live_fusion', 'OFF')}",
                "",
            ]
        )
    lab = snap.get("lab_loop_reject")
    if lab and lab.get("present"):
        lines.extend(
            [
                "Lab loop reject surface (iter1 freeze — research_open only; not field)",
                f"  label:                 {lab.get('label')}",
                f"  reject thr:            {_fmt_num(lab.get('abstain_threshold'))}",
                f"  abstain_rate baseline: {_fmt_num(lab.get('test_abstain_rate_baseline'))}",
                f"  abstain_rate tuned:    {_fmt_num(lab.get('test_abstain_rate_tuned'))}",
                f"  IoU accepted baseline: {_fmt_num(lab.get('test_mean_iou_accepted_baseline'))}",
                f"  IoU accepted tuned:    {_fmt_num(lab.get('test_mean_iou_accepted_tuned'))}",
                f"  holdout U1 ECE:        {_fmt_num(lab.get('test_ece_full_baseline') or lab.get('test_ece_full'))}",
                f"  ECE retune (dead):     closed (ece_improved={lab.get('ece_improved')})",
                f"  reject improved:       {lab.get('lab_reject_surface_improved')}",
                f"  recommended surface:   {lab.get('recommended_lab_surface') or RECOMMENDED_LAB_SURFACE}",
                f"  stop ECE thrash:       {lab.get('stop_ece_thrash_on_same_test')}",
                f"  report:                {lab.get('path')}",
                "",
            ]
        )
        if lab.get("iter4_generalization_table") or lab.get("lofo_n_folds"):
            lines.extend(
                [
                    "Lab loop LOFO generalization (mask IoU — not U1 ECE protocol)",
                    f"  n_folds:               {lab.get('lofo_n_folds') if lab.get('lofo_n_folds') is not None else '—'}",
                    f"  LOFO mean IoU:         {_fmt_num(lab.get('lofo_iou_mean'))}",
                    f"  LOFO IoU std:          {_fmt_num(lab.get('lofo_iou_std'))}",
                    f"  LOFO spread (max-min): {_fmt_num(lab.get('lofo_spread'))}",
                    f"  holdout U1 mean IoU:   {_fmt_num(lab.get('holdout_u1_iou'))}",
                    f"  note:                  {lab.get('generalization_note') or '—'}",
                    "  Tobarra KEEP reopen:   CLOSED",
                    "",
                ]
            )
    lines.append("Paths")
    for k, v in (snap.get("paths") or {}).items():
        present = (snap.get("presence") or {}).get(k, None)
        if k == "promote_record":
            present = (snap.get("presence") or {}).get("promote_record")
        flag = ""
        if present is True:
            flag = "  [ok]"
        elif present is False:
            flag = "  [MISSING]"
        lines.append(f"  {k}: {v}{flag}")
    lines.append("")
    lines.append("honesty: " + "; ".join(snap.get("honesty") or [_ML_BANNER]))
    lines.append("")
    return "\n".join(lines)


def _fmt_num(v: Any, digits: int = 4) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):.{digits}f}"
    except (TypeError, ValueError):
        return str(v)


def build_ml_doctor_report(repo: Path | None = None) -> dict[str, Any]:
    """Structure for ``ml doctor`` — missing weights OK as report (exit 0)."""
    root = _repo(repo)
    checks: list[dict[str, Any]] = []

    def _check(name: str, ok: bool, detail: str, *, severity: str = "info") -> None:
        checks.append(
            {
                "name": name,
                "ok": ok,
                "status": "OK" if ok else "MISSING",
                "detail": detail,
                "severity": severity if not ok else "info",
            }
        )

    # PYTHONPATH / importability
    try:
        import wildfire_front  # noqa: F401

        _check(
            "pythonpath_wildfire_front",
            True,
            f"importable from {getattr(wildfire_front, '__file__', '?')}",
        )
    except ImportError as exc:
        _check(
            "pythonpath_wildfire_front",
            False,
            f"cannot import wildfire_front: {exc} (set PYTHONPATH=.)",
            severity="warn",
        )

    catalog_path = root / "models" / "catalog.json"
    if catalog_path.is_file():
        _check("catalog_json", True, str(catalog_path))
        try:
            from wildfire_front.ml.product_catalog import list_products, load_catalog

            cat = load_catalog(catalog_path)
            products = list_products(catalog_path)
            default = cat.get("default_product")
            _check(
                "catalog_default",
                default == "clm_ensemble_v34" or bool(default),
                f"default_product={default}",
            )
            for row in products:
                pid = row["id"]
                ready = bool(row.get("ready"))
                _check(
                    f"weights_{pid}",
                    ready,
                    str(row.get("status") or ("ok" if ready else "missing")),
                    severity="warn" if not ready else "info",
                )
        except Exception as exc:  # noqa: BLE001
            _check("catalog_load", False, str(exc), severity="warn")
    else:
        _check("catalog_json", False, f"missing {catalog_path}", severity="error")

    cal_candidates = [
        root / "models" / "clm_ensemble" / "uncertainty_calibration_v1.json",
        root / "models" / "clm_ensemble" / "uncertainty_calibrator_v1.json",
    ]
    cal_found = next((p for p in cal_candidates if p.is_file()), None)
    _check(
        "calibrator_json",
        cal_found is not None,
        str(cal_found) if cal_found else "missing product calibrator (identity → force abstain)",
        severity="warn",
    )

    for rel in (
        "docs/ML_PRODUCT_SCORECARD.json",
        "docs/ML_U1_PROMOTE_RECORD.json",
        "config/decision_policies.json",
        "scripts/predict_spread.py",
        "scripts/run_ml_live_card_demo.py",
    ):
        p = root / rel
        _check(rel.replace("/", "_").replace(".", "_"), p.is_file(), str(p))

    # field_ops fusion rail (product facade: must stay OFF)
    policies = _load_json(root / "config" / "decision_policies.json") or {}
    field_ops = (policies.get("policies") or {}).get("field_ops") or {}
    fusion_off = not bool(field_ops.get("allow_ml_live_in_fusion", False))
    try:
        assert_field_fusion_off(
            allow_ml_live_in_fusion=bool(field_ops.get("allow_ml_live_in_fusion", False)),
            field_ops_ml_live_fusion="OFF" if fusion_off else "ON",
        )
        fusion_assert_ok = True
    except Exception as exc:  # noqa: BLE001
        fusion_assert_ok = False
        fusion_off = False
        _fusion_err = str(exc)
    else:
        _fusion_err = ""
    _check(
        "field_ops_fusion_off",
        fusion_off and fusion_assert_ok,
        (
            "field_ops.allow_ml_live_in_fusion=false (product_facade)"
            if fusion_off and fusion_assert_ok
            else f"UNEXPECTED: field_ops fusion ON {_fusion_err}".strip()
        ),
        severity="error" if not (fusion_off and fusion_assert_ok) else "info",
    )

    # Facade freeze surface (iter1 reject; dead thrash closed; ml_product_go promoted)
    try:
        facade_rails = _facade_cli_rails()
        ml_go = bool(facade_rails.get("ml_product_go", ML_PRODUCT_GO_DEFAULT))
        _check(
            "ml_product_go_true",
            ml_go is True,
            f"ml_product_go={ml_go} (human promote 2026-08-05; no silent auto-flip)",
            severity="error" if not ml_go else "info",
        )
        _check(
            "facade_iter1_reject",
            facade_rails.get("recommended_lab_surface") == RECOMMENDED_LAB_SURFACE
            and abs(float(facade_rails.get("locked_reject_thr", -1)) - ITER1_LOCKED_REJECT_THR)
            < 1e-9,
            f"surface={facade_rails.get('recommended_lab_surface')} "
            f"thr={facade_rails.get('locked_reject_thr')}",
        )
        _check(
            "facade_dead_thrash_closed",
            bool(facade_rails.get("stop_ece_thrash_on_same_test"))
            and facade_rails.get("tobarra_keep_reopen") is False,
            "same-holdout ECE thrash closed; Tobarra KEEP reopen closed",
        )
    except Exception as exc:  # noqa: BLE001
        _check(
            "ml_product_go_true",
            False,
            f"facade rails failed: {exc}",
            severity="error",
        )
        _check("facade_iter1_reject", False, str(exc), severity="error")

    # Lab loop artifacts (teaching surface; warn if incomplete)
    loop_dir = root / "outputs" / "ml_eval" / "lab_loop"
    latest_loop = _load_json(loop_dir / "lab_loop_v34_latest.json") or {}
    _check(
        "lab_loop_latest",
        bool(latest_loop),
        str(loop_dir / "lab_loop_v34_latest.json"),
        severity="warn",
    )
    for rel_name in (
        "lab_loop_v34_reject_latest.json",
        "lab_loop_v34_fail_cases_test.json",
        "lab_loop_v34_risk_curve_latest.json",
        "lab_loop_v34_freeze_latest.json",
    ):
        p = loop_dir / rel_name
        _check(
            f"lab_loop_{rel_name.replace('.', '_')}",
            p.is_file(),
            str(p),
            severity="warn",
        )
    for rel in (
        "outputs/ml_eval/val_head_a_features.npz",
        "outputs/ml_eval/test_head_a_features.npz",
    ):
        p = root / rel
        _check(
            rel.replace("/", "_").replace(".", "_"),
            p.is_file(),
            str(p),
            severity="warn",
        )

    n_ok = sum(1 for c in checks if c["ok"])
    n_missing = sum(1 for c in checks if not c["ok"])
    weights_missing = [
        c["name"] for c in checks if c["name"].startswith("weights_") and not c["ok"]
    ]

    return {
        "schema": "wfd_ml_doctor_v1",
        "banner": _ML_BANNER,
        "repo_root": str(root),
        "summary": {
            "ok_count": n_ok,
            "missing_count": n_missing,
            "weights_missing": weights_missing,
            "ready_for_offline": True,  # list/show/card offline always
            # Default product ready ⇒ live predict path usable (explicit parens)
            "ready_for_live_predict": (
                any(c["name"] == "weights_clm_ensemble_v34" and c["ok"] for c in checks)
            ),
        },
        "checks": checks,
        "product_facade": "wildfire_front.ml.product_facade",
        "facade_class": "ClmEnsembleV34Facade",
        "pipeline": "features→calibrator→rank/reject→scorecard",
        "honesty": [
            _ML_BANNER,
            "MISSING weights is a report, not a crash",
            "exit 0 even when weights missing (structure OK)",
            "predict/show/card use ClmEnsembleV34Facade product path",
        ],
    }


def format_ml_doctor_human(report: dict[str, Any]) -> str:
    lines = [
        "ML doctor (lab product)",
        f"  banner: {_ML_BANNER}",
        f"  repo:   {report.get('repo_root')}",
        "",
    ]
    for c in report.get("checks") or []:
        flag = "OK" if c.get("ok") else "MISSING"
        lines.append(f"  [{flag:<7}] {c.get('name')}: {c.get('detail')}")
    summary = report.get("summary") or {}
    lines.extend(
        [
            "",
            f"  summary: {summary.get('ok_count')} ok / {summary.get('missing_count')} missing",
            f"  offline path: ready={summary.get('ready_for_offline')}",
            f"  live predict: ready={summary.get('ready_for_live_predict')}",
            f"  weights_missing: {summary.get('weights_missing') or []}",
            "",
            "honesty: " + "; ".join(report.get("honesty") or [_ML_BANNER]),
            "",
        ]
    )
    return "\n".join(lines)


def run_ml_list(args: argparse.Namespace) -> int:
    """List catalog products; exit 0 offline."""
    try:
        from wildfire_front.ml.product_catalog import list_products, load_catalog

        as_json = bool(getattr(args, "json", False))
        catalog = load_catalog()
        rows = list_products()
        payload = {
            "schema": "wfd_ml_list_v1",
            "banner": _ML_BANNER,
            "default_product": catalog.get("default_product"),
            "fallback_ml_product": catalog.get("fallback_ml_product"),
            "research_ml_product": catalog.get("research_ml_product"),
            "emergency_ml_product": catalog.get("emergency_ml_product"),
            "ops_product": catalog.get("ops_product"),
            "ops_note": catalog.get("ops_note"),
            "products": rows,
        }
        if as_json:
            print_json(payload)
        else:
            print(f"ML products  [{_ML_BANNER}]")
            print(f"  default:   {payload['default_product']}")
            print(f"  fallback:  {payload['fallback_ml_product']}")
            print(f"  research:  {payload['research_ml_product']}")
            print(f"  ops (≠ML): {payload['ops_product']}")
            print("")
            for r in rows:
                ready = "ready" if r.get("ready") else "MISSING weights"
                print(f"  {r['id']:<20} [{ready}]  {r.get('label', '')}")
                print(f"    domain:   {r.get('domain')}")
                print(f"    use_when: {r.get('use_when')}")
                print(f"    not_for:  {r.get('not_for')}")
                print("")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1


def run_ml_show(args: argparse.Namespace) -> int:
    """Scorecard snapshot; offline."""
    try:
        as_json = bool(getattr(args, "json", False))
        snap = build_ml_scorecard_snapshot()
        if as_json:
            # drop absolute repo_root noise optional — keep for debug
            print_json(snap)
        else:
            sys.stdout.write(format_ml_show_human(snap))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1


def run_ml_doctor(args: argparse.Namespace) -> int:
    """Doctor report; exit 0 even if weights missing."""
    try:
        as_json = bool(getattr(args, "json", False))
        report = build_ml_doctor_report()
        if as_json:
            print_json(report)
        else:
            sys.stdout.write(format_ml_doctor_human(report))
        # Structure always OK; hard fail only if catalog completely broken is still 0
        # per acceptance ("missing weights OK as report")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _resolve_predict_calibrator(root: Path, calibrator_path: str | None):
    """Load Head A calibrator for the live product path (facade / identity).

    Explicit ``--calibrator`` must exist. Default: product artifact under
    ``models/clm_ensemble/`` only (never CI fixtures). Missing → identity.
    """
    from wildfire_front.ml.uncertainty import LogisticCalibrator, load_calibrator

    if calibrator_path:
        p = Path(calibrator_path)
        if not p.is_file():
            raise FileNotFoundError(
                f"--calibrator path not found: {p} "
                "(refusing silent identity when path was explicitly set)"
            )
        return load_calibrator(p)
    candidates = [
        root / "models" / "clm_ensemble" / "uncertainty_calibration_v1.json",
        root / "models" / "clm_ensemble" / "uncertainty_calibrator_v1.json",
    ]
    for c in candidates:
        if c.is_file():
            return load_calibrator(c)
    return LogisticCalibrator.identity()


def run_ml_predict(args: argparse.Namespace) -> int:
    """In-process product path: catalog → predictor → ClmEnsembleV34Facade conf/reject.

    Default product = ``clm_ensemble_v34``; default abstain thr = freeze **iter1
    reject** (VAL-locked). ``ml_product_go`` true (human promote); fusion stays OFF.
    Not a thin subprocess wrapper around ``predict_spread`` — conf/abstain go through
    ``product_facade`` (same path as scorecard / rank-reject).
    """
    root = _repo()

    # Facade rails: dual-product freeze (promoted go; no silent auto-flip / fusion ON).
    try:
        facade_rails = _facade_cli_rails()
    except Exception as exc:  # noqa: BLE001
        print(f"error: product facade rails failed: {exc}", file=sys.stderr)
        return 1
    ml_go = bool(facade_rails.get("ml_product_go", ML_PRODUCT_GO_DEFAULT))

    # Fast path: --list-products without invoking full inference setup
    if getattr(args, "list_products", False) and not getattr(args, "npz", None):
        try:
            from wildfire_front.ml.product_catalog import list_products

            rows = list_products()
            if getattr(args, "json", False):
                print_json(
                    {
                        "products": rows,
                        "banner": _ML_BANNER,
                        "default_product": DEFAULT_PRODUCT_ID,
                        "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
                        "locked_reject_thr": float(ITER1_LOCKED_REJECT_THR),
                        "ml_product_go": ml_go,
                        "field_ops_ml_live_fusion": "OFF",
                        "product_facade": "wildfire_front.ml.product_facade",
                        "facade_class": "ClmEnsembleV34Facade",
                        "pipeline": "features→calibrator→rank/reject→scorecard",
                        "rails": facade_rails,
                    }
                )
            else:
                print(json.dumps(rows, indent=2))
            return 0
        except Exception as exc:  # noqa: BLE001
            print(f"error: {exc}", file=sys.stderr)
            return 1

    product = getattr(args, "product", None) or DEFAULT_PRODUCT_ID
    if product and not getattr(args, "list_products", False):
        try:
            from wildfire_front.ml.product_catalog import get_product

            spec = get_product(product)
            ok, msg = spec.resolve_existing()
            if not ok:
                print(
                    f"error: product {product} not ready: {msg}\n"
                    f"  hint: place .pt weights under models/ or use --list-products\n"
                    f"  note: {_ML_BANNER}; freeze thr={ITER1_LOCKED_REJECT_THR}",
                    file=sys.stderr,
                )
                return 1
        except KeyError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        except Exception as exc:  # noqa: BLE001
            print(f"error: product check failed: {exc}", file=sys.stderr)
            return 1

    if not getattr(args, "list_products", False) and not getattr(args, "npz", None):
        try:
            from wildfire_front.ml.product_catalog import get_product

            pid = product or DEFAULT_PRODUCT_ID
            spec = get_product(pid)
            ok, msg = spec.resolve_existing()
            if not ok:
                print(
                    f"error: product {pid} not ready: {msg}\n"
                    f"  --npz required for inference; weights missing → cannot predict\n"
                    f"  note: {_ML_BANNER}",
                    file=sys.stderr,
                )
                return 1
        except Exception:
            pass
        print(
            f"error: --npz required unless --list-products\n  note: {_ML_BANNER}",
            file=sys.stderr,
        )
        return 1

    # ── In-process facade product path ────────────────────────────────────
    try:
        import numpy as np

        from wildfire_front.ml.ndws_metrics import (
            aggregate_ndws_evaluation,
            evaluate_sample,
        )
        from wildfire_front.ml.product_catalog import (
            get_product,
            load_predictor_for_product,
        )
        from wildfire_front.ml.product_facade import ClmEnsembleV34Facade
        from wildfire_front.ml.spread_predictor import (
            EnsembleSpreadPredictor,
            SpreadPredictor,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"error: predict imports failed: {exc}\n  note: {_ML_BANNER}", file=sys.stderr)
        return 1

    as_json = bool(getattr(args, "json", False))
    try:
        if getattr(args, "manifest", None):
            manifest_path = Path(args.manifest)
            mdata = json.loads(manifest_path.read_text(encoding="utf-8"))
            is_ens = bool(mdata.get("members") or mdata.get("product_type") == "ensemble")
            if is_ens:
                members = mdata.get("members") or []
                member_paths = []
                for rel in members:
                    p = Path(rel)
                    member_paths.append(p if p.is_absolute() else (root / p).resolve())
                predictor: SpreadPredictor | EnsembleSpreadPredictor = (
                    EnsembleSpreadPredictor.from_manifest(
                        manifest_path, member_weights=member_paths
                    )
                )
                product_id = str(mdata.get("id") or mdata.get("version") or "ensemble")
                product_label = product_id
                domain = str(mdata.get("domain") or "ensemble")
            else:
                predictor = SpreadPredictor.from_manifest(
                    manifest_path, weights_path=getattr(args, "weights", None)
                )
                product_id = str(mdata.get("version") or "custom")
                product_label = product_id
                domain = "custom"
        else:
            spec = get_product(product)
            ok, msg = spec.resolve_existing()
            if not ok:
                print(
                    f"error: product {product} not ready: {msg}\n  note: {_ML_BANNER}",
                    file=sys.stderr,
                )
                return 1
            if not as_json:
                print(f"Product: {spec.id} ({spec.domain}) type={spec.product_type}")
                print(f"  use_when: {spec.use_when}")
                print(f"  not_for:  {spec.not_for}")
                print(
                    f"  facade:   ClmEnsembleV34Facade  surface={RECOMMENDED_LAB_SURFACE} "
                    f"thr={ITER1_LOCKED_REJECT_THR}"
                )
            predictor = load_predictor_for_product(product)
            product_id = spec.id
            product_label = spec.label
            domain = spec.domain

        npz_path = Path(args.npz)
        paths = sorted(npz_path.glob("*.npz")) if npz_path.is_dir() else [npz_path]
        max_patches = int(getattr(args, "max_patches", 0) or 0)
        if max_patches > 0:
            paths = paths[:max_patches]
        if not paths:
            print(f"error: no NPZ under {npz_path}\n  note: {_ML_BANNER}", file=sys.stderr)
            return 1

        # Freeze iter1 reject thr as default product abstain (facade rank/reject).
        abstain = getattr(args, "abstain_below", None)
        abstain = float(ITER1_LOCKED_REJECT_THR) if abstain is None else float(abstain)

        use_unc = bool(
            getattr(args, "with_uncertainty", False)
            or getattr(args, "ml_live_json", None)
            or product_id == DEFAULT_PRODUCT_ID
        )
        calibrator = None
        facade: ClmEnsembleV34Facade | None = None
        if use_unc:
            try:
                calibrator = _resolve_predict_calibrator(root, getattr(args, "calibrator", None))
            except FileNotFoundError as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 1
            facade = ClmEnsembleV34Facade.with_iter1_locked_thr(calibrator)
            if getattr(calibrator, "is_identity", False) and not as_json:
                print(
                    "NOTE: no product calibrator under models/clm_ensemble/ — "
                    "using identity (live confidence forces abstain). "
                    f"{_ML_BANNER}",
                    flush=True,
                )

        sample_metrics: list[dict] = []
        metrics_rows: list[dict] = []
        last_live_doc: dict | None = None
        n_abstain = 0
        n_keep = 0

        for path in paths:
            with np.load(path) as data:
                seq = data["sequence"]
                current_fire = data["current_fire"]
                target_fire = data.get("target_fire", None)

            thr = predictor.manifest.threshold
            if use_unc and hasattr(predictor, "predict_with_uncertainty"):
                from wildfire_front.ml.uncertainty import build_ml_prediction_document

                unc = predictor.predict_with_uncertainty(
                    seq,
                    current_fire,
                    threshold=thr,
                    calibrator=calibrator,
                    product_id=product_id,
                    abstain_below=float(abstain),
                )
                pred_prob = unc.prob
                pred_bin = unc.binary
                mask_summary = {
                    "mean_prob": float(np.mean(pred_prob)),
                    "fire_frac": float(np.mean(pred_bin)),
                    "shape": list(pred_prob.shape),
                }
                last_live_doc = build_ml_prediction_document(unc, mask_summary=mask_summary)
                # Tag facade ownership on live doc (rails never auto-flip).
                if isinstance(last_live_doc, dict):
                    last_live_doc.setdefault("product_facade", "wildfire_front.ml.product_facade")
                    last_live_doc.setdefault("facade_class", "ClmEnsembleV34Facade")
                    last_live_doc.setdefault(
                        "pipeline", "features→calibrator→rank/reject→scorecard"
                    )
                    last_live_doc.setdefault("ml_product_go", ml_go)
                    last_live_doc.setdefault("field_ops_ml_live_fusion", "OFF")
                    last_live_doc.setdefault("recommended_lab_surface", RECOMMENDED_LAB_SURFACE)
                    last_live_doc.setdefault("locked_reject_thr", float(abstain))
                if bool(getattr(unc, "abstain", False)):
                    n_abstain += 1
                else:
                    n_keep += 1
                if (
                    getattr(args, "with_uncertainty", False)
                    and (as_json or len(paths) == 1)
                    and (not getattr(args, "ml_live_json", None) or len(paths) == 1)
                ):
                    print(json.dumps(last_live_doc, indent=2))
            else:
                pred_prob = predictor.predict(seq, current_fire)
                pred_bin = (pred_prob >= thr).astype(np.float32)

            if getattr(args, "eval", False) and target_fire is not None:
                sample = evaluate_sample(pred_prob, current_fire, target_fire)
                sample_metrics.append(sample)
                metrics_rows.append(
                    {
                        "file": path.name,
                        "iou": float(sample["model_full"].iou),
                        "copy_iou": float(sample["copy_full"].iou),
                    }
                )

            if getattr(args, "output", None) and len(paths) == 1:
                out = Path(args.output)
                out.parent.mkdir(parents=True, exist_ok=True)
                n_mem = getattr(predictor, "n_members", 1)
                np.savez_compressed(
                    out,
                    prediction=pred_prob,
                    prediction_binary=pred_bin,
                    current_fire=current_fire,
                    target_fire=target_fire if target_fire is not None else np.array([]),
                    product=product_id,
                    model_version=predictor.manifest.version,
                    n_members=np.int32(n_mem),
                )
                if not as_json:
                    print(f"Wrote {out}")

        if getattr(args, "ml_live_json", None) and last_live_doc is not None:
            live_path = Path(args.ml_live_json)
            live_path.parent.mkdir(parents=True, exist_ok=True)
            live_path.write_text(json.dumps(last_live_doc, indent=2), encoding="utf-8")
            if not as_json:
                print(f"Wrote {live_path}")

        if metrics_rows:
            ious = np.asarray([r["iou"] for r in metrics_rows], dtype=float)
            copy_ious = np.asarray([r["copy_iou"] for r in metrics_rows], dtype=float)
            agg = aggregate_ndws_evaluation(sample_metrics) if sample_metrics else {}
            report = {
                "product": product_id,
                "label": product_label,
                "domain": domain,
                "model_version": predictor.manifest.version,
                "product_type": getattr(predictor.manifest, "product_type", "single"),
                "n_members": getattr(predictor, "n_members", 1),
                "n_patches": len(metrics_rows),
                "mean_iou": float(ious.mean()),
                "mean_copy_iou": float(copy_ious.mean()),
                "mean_delta_vs_copy": float((ious - copy_ious).mean()),
                "micro_iou": float(agg.get("model_iou") or ious.mean()),
                "micro_delta": float(
                    agg.get("improvement_vs_copy_iou") or (ious - copy_ious).mean()
                ),
                "model_iou_growth": float(agg.get("model_iou_growth") or 0.0),
                # Facade ownership (single product path; not field promote)
                "product_facade": "wildfire_front.ml.product_facade",
                "facade_class": "ClmEnsembleV34Facade",
                "pipeline": "features→calibrator→rank/reject→scorecard",
                "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
                "locked_reject_thr": float(abstain),
                "ml_product_go": ml_go,
                "field_ops_ml_live_fusion": "OFF",
                "n_keep": n_keep,
                "n_abstain": n_abstain,
            }
            print(json.dumps(report, indent=2))
        elif use_unc and last_live_doc is not None and not getattr(args, "with_uncertainty", False):
            # Single-patch default product path: surface facade live doc when
            # neither --eval nor --with-uncertainty was requested.
            if len(paths) == 1 and as_json:
                print(json.dumps(last_live_doc, indent=2))
            elif len(paths) == 1 and not as_json and facade is not None:
                conf = last_live_doc.get("confidence_pred")
                if conf is None:
                    conf = (last_live_doc.get("uncertainty") or {}).get("confidence_pred")
                print(
                    f"ml predict  [{_ML_BANNER}]\n"
                    f"  product:   {product_id}\n"
                    f"  facade:    ClmEnsembleV34Facade\n"
                    f"  thr:       {abstain}\n"
                    f"  surface:   {RECOMMENDED_LAB_SURFACE}\n"
                    f"  conf:      {_fmt_num(conf)}\n"
                    f"  ml_product_go={str(ml_go).lower()}  field_ops fusion=OFF"
                )
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"error: predict failed: {exc}\n  note: {_ML_BANNER}", file=sys.stderr)
        return 1


def _load_script_module(name: str, rel: str, repo: Path) -> Any:
    path = repo / rel
    if not path.is_file():
        raise FileNotFoundError(f"script not found: {path}")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_ml_card(args: argparse.Namespace) -> int:
    """Decision Card demo under product_facade rails (offline works without weights).

    Demo script produces the card; CLI owns dual-product rails
    (``ml_product_go`` true human promote, field fusion OFF, freeze iter1 reject) and
    attaches facade pipeline metadata. Never silent auto-promotes.
    """
    root = _repo()
    as_json = bool(getattr(args, "json", False))
    mode = str(getattr(args, "mode", "offline") or "offline")
    scenario = str(getattr(args, "scenario", "hold") or "hold")
    # Map 'go' → hold for offline demo (research_open ML-only does not produce tactical GO)
    if scenario == "go":
        scenario = "hold"
        if not getattr(args, "quiet", False):
            print(
                "note: --scenario go maps to offline hold (lab ML-only; not tactical GO); "
                f"{_ML_BANNER}",
                file=sys.stderr,
            )

    out = getattr(args, "output", None)
    out = root / "outputs" / "ml_live_card_demo" if out is None else Path(out)

    # Facade rails first (dead thrash sealed; fusion OFF; go promoted).
    try:
        facade_rails = _facade_cli_rails()
    except Exception as exc:  # noqa: BLE001
        print(f"error: product facade rails failed: {exc}", file=sys.stderr)
        return 1
    rank_reject = rank_abstain_protocol_dict(
        locked_reject_thr=float(ITER1_LOCKED_REJECT_THR),
        recommended_lab_surface=RECOMMENDED_LAB_SURFACE,
    )
    ml_go = bool(facade_rails.get("ml_product_go", ML_PRODUCT_GO_DEFAULT))

    if mode == "live":
        # Preflight weights
        try:
            from wildfire_front.ml.product_catalog import get_product, load_catalog

            pid = load_catalog().get("default_product") or DEFAULT_PRODUCT_ID
            spec = get_product(pid)
            ok, msg = spec.resolve_existing()
            if not ok:
                print(
                    f"error: live card needs weights for {pid}: {msg}\n"
                    f"  use: wildfire-front ml card --mode offline --scenario hold\n"
                    f"  note: {_ML_BANNER}",
                    file=sys.stderr,
                )
                return 1
        except Exception as exc:  # noqa: BLE001
            print(
                f"error: live preflight failed: {exc}\n  note: {_ML_BANNER}",
                file=sys.stderr,
            )
            return 1

    try:
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        mod = _load_script_module(
            "wfd_run_ml_live_card_demo",
            "scripts/run_ml_live_card_demo.py",
            root,
        )
        # Prefer run_demo API if present
        if hasattr(mod, "run_demo"):
            kwargs: dict[str, Any] = {
                "mode": mode,
                "scenario": scenario,
                "out_dir": out,
                "event_id": getattr(args, "event_id", "ml_live_card_demo"),
                "policy_id": getattr(args, "policy", "research_open"),
            }
            if getattr(args, "npz", None):
                kwargs["npz"] = Path(args.npz)
            if getattr(args, "ml_prediction", None):
                kwargs["ml_prediction_path"] = Path(args.ml_prediction)
            if getattr(args, "max_patches", None) is not None:
                kwargs["max_patches"] = int(args.max_patches)
            # Filter kwargs to what run_demo accepts
            import inspect

            sig = inspect.signature(mod.run_demo)
            kwargs = {k: v for k, v in kwargs.items() if k in sig.parameters}
            summary = mod.run_demo(**kwargs)
            # CLI facade owns rails — promoted go; fusion stays OFF (no silent thrash).
            field_ops_fusion = "OFF"
            if as_json:
                print_json(
                    {
                        "schema": "wfd_ml_card_v1",
                        "banner": _ML_BANNER,
                        "mode": mode,
                        "scenario": scenario,
                        "summary": summary,
                        "out": str(out),
                        "field_ops_fusion": field_ops_fusion,
                        "ml_product_go": ml_go,
                        "product_facade": "wildfire_front.ml.product_facade",
                        "facade_class": "ClmEnsembleV34Facade",
                        "pipeline": "features→calibrator→rank/reject→scorecard",
                        "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
                        "locked_reject_thr": float(ITER1_LOCKED_REJECT_THR),
                        "rails": facade_rails,
                        "rank_reject_protocol": rank_reject,
                        "multi_fire_honesty": DEFAULT_MULTI_FIRE.as_dict(),
                    }
                )
            else:
                print(f"ml card  [{_ML_BANNER}]")
                print(f"  mode:     {mode}")
                print(f"  scenario: {scenario}")
                print(f"  out:      {out}")
                print(f"  facade:   ClmEnsembleV34Facade / {RECOMMENDED_LAB_SURFACE}")
                if isinstance(summary, dict):
                    print(f"  decision: {summary.get('decision')}")
                    print(f"  policy:   {summary.get('policy_id') or kwargs.get('policy_id')}")
                    conf = summary.get("confidence_pred")
                    if conf is not None:
                        print(f"  confidence_pred: {conf}")
                print(
                    f"  fusion: {field_ops_fusion} (field_ops)  ml_product_go={str(ml_go).lower()}"
                )
            return 0

        # Fallback: subprocess main
        cmd = [
            sys.executable,
            str(root / "scripts" / "run_ml_live_card_demo.py"),
            "--mode",
            mode,
            "--scenario",
            scenario,
            "--out-dir",
            str(out),
        ]
        env = os.environ.copy()
        pp = env.get("PYTHONPATH", "")
        if str(root) not in pp.split(os.pathsep):
            env["PYTHONPATH"] = str(root) + (os.pathsep + pp if pp else "")
        proc = subprocess.run(cmd, cwd=str(root), env=env, check=False)
        return int(proc.returncode)

    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except TypeError as exc:
        # Signature mismatch — try minimal offline
        if mode == "offline" and hasattr(mod, "run_demo"):
            try:
                summary = mod.run_demo(
                    mode="offline",
                    scenario=scenario,
                    out_dir=out,
                )
                if as_json:
                    print_json(
                        {
                            "summary": summary,
                            "banner": _ML_BANNER,
                            "ml_product_go": ml_go,
                            "field_ops_fusion": "OFF",
                            "product_facade": "wildfire_front.ml.product_facade",
                        }
                    )
                else:
                    print(f"ml card offline ok decision={summary.get('decision')}")
                return 0
            except Exception as exc2:  # noqa: BLE001
                print(
                    f"error: card demo failed: {exc2}\n  note: {_ML_BANNER}",
                    file=sys.stderr,
                )
                return 1
        print(f"error: card demo failed: {exc}\n  note: {_ML_BANNER}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"error: card demo failed: {exc}\n  note: {_ML_BANNER}", file=sys.stderr)
        return 1


def run_ml_cases(args: argparse.Namespace) -> int:
    """Teach fail-cases + LOFO board (offline)."""
    from .ml.lab_teach_cases import (
        build_teach_cases_pack,
        filter_fail_rows,
        format_teach_cases_human,
        load_json,
    )

    root = _repo(getattr(args, "repo", None))
    pack = build_teach_cases_pack(root)
    bucket = getattr(args, "bucket", None)
    limit = int(getattr(args, "limit", 5) or 5)
    if getattr(args, "rows", False):
        fail = load_json(
            root / "outputs" / "ml_eval" / "lab_loop" / "lab_loop_v34_fail_cases_test.json"
        )
        pack = dict(pack)
        pack["rows"] = filter_fail_rows(fail, bucket=bucket, limit=limit)
    if getattr(args, "json", False):
        print_json(pack)
        return 0
    print(format_teach_cases_human(pack, bucket=bucket, limit=limit))
    if getattr(args, "rows", False) and pack.get("rows"):
        print("Rows (teaching indices only)")
        for r in pack["rows"]:
            print(
                f"  idx={r.get('index')} bucket={r.get('bucket')} "
                f"conf={_fmt_num(r.get('conf'))} iou={_fmt_num(r.get('iou'))}"
            )
        print()
    return 0


def _format_ml_curve_human(payload: dict[str, Any]) -> str:
    h = payload.get("highlights_test") or {}
    curve = (payload.get("selective_curve") or {}).get("test") or []
    thr = (payload.get("thr_operating_points") or {}).get("test") or []
    band = (payload.get("conf_band") or {}).get("test") or {}
    rails = payload.get("rails") or {}
    lines = [
        "ML lab risk–coverage curve (research_open / lab only — not field)",
        f"  banner:              {_ML_BANNER}",
        f"  product:             {payload.get('product_id')}",
        f"  ml_product_go:       {rails.get('ml_product_go', ML_PRODUCT_GO_DEFAULT)}",
        "  field_ops fusion:    OFF (rail)",
        f"  recommended surface: {(payload.get('verdict') or {}).get('recommended_lab_surface', 'iter1_reject_only')}",
        "",
        "Conf band TEST",
        f"  mean/p05/p50/p95:    {_fmt_num(band.get('mean'))} / "
        f"{_fmt_num(band.get('p05'))} / {_fmt_num(band.get('p50'))} / {_fmt_num(band.get('p95'))}",
        f"  note:                {(payload.get('conf_band') or {}).get('note') or '—'}",
        "",
        "Selective curve TEST (rank by conf — not thr reject)",
        "  coverage  n_keep  sel_IoU  lift_vs_full",
    ]
    for r in curve:
        lines.append(
            f"  {_fmt_num(r.get('coverage_target')):>8}  "
            f"{int(r.get('n_keep') or 0):>6}  "
            f"{_fmt_num(r.get('selective_iou')):>7}  "
            f"{_fmt_num(r.get('lift_vs_full')):>12}"
        )
    lines += [
        "",
        f"  full IoU:            {_fmt_num(h.get('full_mean_iou'))}",
        f"  selective@80:        {_fmt_num(h.get('selective_iou_at_80'))}",
        f"  lift@80:             {_fmt_num(h.get('selective_lift_at_80'))}",
        f"  ranking useful@80:   {h.get('ranking_useful_at_80')}",
        "",
        "Thr operating points TEST (frozen)",
        "  thr      keep    abstain  IoU_acc  ECE_full",
    ]
    for r in thr:
        lines.append(
            f"  {_fmt_num(r.get('threshold')):>7}  "
            f"{_fmt_num(r.get('keep_rate')):>6}  "
            f"{_fmt_num(r.get('abstain_rate')):>7}  "
            f"{_fmt_num(r.get('mean_iou_accepted')):>7}  "
            f"{_fmt_num(r.get('ece_full')):>8}"
        )
    lines += [
        "",
        "honesty: ranking curve ≠ thr reject; IoU ≠ ROS; ECE not claimed fixed",
        "",
    ]
    return "\n".join(lines)


def run_ml_freeze(args: argparse.Namespace) -> int:
    """Lab freeze handoff card (offline). Exit 0 if usable, 2 if freeze blocked."""
    from .ml.lab_freeze import build_lab_freeze_pack, format_lab_freeze_human

    root = _repo()
    if getattr(args, "write", False):
        try:
            from scripts.run_lab_ml_loop_v34_freeze import main as freeze_main

            freeze_main([])
        except Exception as exc:  # noqa: BLE001
            print(f"error: freeze write failed: {exc}", file=sys.stderr)
            return 1
    pack = build_lab_freeze_pack(root)
    if getattr(args, "json", False):
        print_json(pack)
    else:
        sys.stdout.write(format_lab_freeze_human(pack))
    usable = bool((pack.get("verdict") or {}).get("lab_usable_freeze"))
    return 0 if usable else 2


def run_ml_smoke(args: argparse.Namespace) -> int:
    """Post-freeze smoke. Exit 0 if pass, 2 if fail."""
    from .ml.lab_smoke import format_lab_smoke_human, run_lab_smoke

    root = _repo()
    if getattr(args, "write", False):
        try:
            from scripts.run_lab_ml_loop_v34_smoke import main as smoke_main

            sm_argv: list[str] = []
            if getattr(args, "pytest", False):
                sm_argv.append("--pytest")
            return int(smoke_main(sm_argv))
        except Exception as exc:  # noqa: BLE001
            print(f"error: smoke write failed: {exc}", file=sys.stderr)
            return 1
    payload = run_lab_smoke(root, run_pytest=bool(getattr(args, "pytest", False)))
    if getattr(args, "json", False):
        print_json(payload)
    else:
        sys.stdout.write(format_lab_smoke_human(payload))
    return 0 if (payload.get("verdict") or {}).get("smoke_pass") else 2


def run_ml_lofo(args: argparse.Namespace) -> int:
    """Multi-fire LOFO scoreboard (offline)."""
    from .ml.lab_lofo_board import build_lofo_scoreboard, format_lofo_board_human

    root = _repo()
    if getattr(args, "write", False):
        try:
            from scripts.run_lab_ml_loop_v34_lofo_board import main as lofo_main

            rc = lofo_main([])
            if rc != 0:
                return int(rc)
        except Exception as exc:  # noqa: BLE001
            print(f"error: lofo write failed: {exc}", file=sys.stderr)
            return 1
    pack = build_lofo_scoreboard(root)
    if getattr(args, "json", False):
        print_json(pack)
    else:
        sys.stdout.write(format_lofo_board_human(pack))
    return 0 if (pack.get("verdict") or {}).get("lofo_board_built") else 2


def run_ml_lift(args: argparse.Namespace) -> int:
    """Metrics lift board (offline; no retrain; no KEEP without scoring)."""
    from scripts.run_lab_ml_loop_v34_metrics_lift import main as lift_main

    argv: list[str] = []
    if getattr(args, "baselines_only", False):
        argv.append("--baselines-only")
    cr = getattr(args, "candidate_root", None)
    if cr:
        argv.extend(["--candidate-root", str(cr)])
    cb = getattr(args, "candidate_board", None)
    if cb:
        argv.extend(["--candidate-board", str(cb)])
    exp = getattr(args, "experiment_id", None)
    if exp:
        argv.extend(["--experiment-id", str(exp)])
    if getattr(args, "no_write", False):
        argv.append("--no-write")
    if getattr(args, "json", False):
        argv.append("--json")
    # default write via script unless --no-write
    if not cr and not cb and not getattr(args, "baselines_only", False):
        argv.append("--baselines-only")
    try:
        return int(lift_main(argv))
    except Exception as exc:  # noqa: BLE001
        print(f"error: metrics lift failed: {exc}", file=sys.stderr)
        return 1


def run_ml_next(args: argparse.Namespace) -> int:
    """Next-signal readiness gate (offline)."""
    from .ml.lab_next import build_next_gate, format_next_gate_human

    root = _repo()
    if getattr(args, "write", False):
        try:
            from scripts.run_lab_ml_loop_v34_next_gate import main as next_main

            rc = next_main([])
            if rc != 0:
                return int(rc)
        except Exception as exc:  # noqa: BLE001
            print(f"error: next gate write failed: {exc}", file=sys.stderr)
            return 1
    pack = build_next_gate(root)
    if getattr(args, "json", False):
        print_json(pack)
    else:
        sys.stdout.write(format_next_gate_human(pack))
    return 0 if (pack.get("verdict") or {}).get("next_gate_built") else 2


def run_ml_curve(args: argparse.Namespace) -> int:
    """Risk–coverage curve from loop JSON or rebuild from caches."""
    root = _repo()
    curve_path = root / "outputs" / "ml_eval" / "lab_loop" / "lab_loop_v34_risk_curve_latest.json"
    need_build = bool(getattr(args, "rebuild", False)) or not curve_path.is_file()
    if need_build:
        try:
            from scripts.run_lab_ml_loop_v34_risk_curve import main as curve_main

            rc = curve_main([])
            if rc != 0 and not curve_path.is_file():
                return int(rc)
        except Exception as exc:  # noqa: BLE001
            if not curve_path.is_file():
                print(f"error: cannot build curve: {exc}", file=sys.stderr)
                return 1
    payload = _load_json(curve_path)
    if not payload:
        print(
            "error: risk curve artifact missing — run "
            "python scripts/run_lab_ml_loop_v34_risk_curve.py",
            file=sys.stderr,
        )
        return 1
    if getattr(args, "json", False):
        print_json(payload)
        return 0
    sys.stdout.write(_format_ml_curve_human(payload))
    return 0


_ML_SUBCOMMANDS: tuple[str, ...] = (
    "list",
    "show",
    "predict",
    "card",
    "doctor",
    "cases",
    "curve",
    "freeze",
    "smoke",
    "lofo",
    "lift",
    "next",
)


def build_ml_hub() -> dict[str, Any]:
    """Discoverability hub for bare ``ml`` — does **not** change product gates."""
    return {
        "schema": "wfd_ml_hub_v1",
        "banner": _ML_BANNER,
        "default_product": DEFAULT_PRODUCT_ID,
        "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
        "iter1_reject_thr": ITER1_LOCKED_REJECT_THR,
        # Frozen product rails (hub must not imply field promote or fusion ON)
        "gates": {
            "ml_product_go": bool(ML_PRODUCT_GO_DEFAULT),
            "field_ops_ml_live_fusion": "OFF",
            "note": (
                "lab usable ≠ field_ops fusion; IoU ≠ ROS; "
                "no silent auto-flip of ml_product_go"
            ),
        },
        "subcommands": list(_ML_SUBCOMMANDS),
        "start_here": [
            {"cmd": "wildfire-front ml list", "why": "catálogo + default + not_for"},
            {"cmd": "wildfire-front ml show", "why": "scorecard + rails (offline)"},
            {"cmd": "wildfire-front ml doctor", "why": "weights / catalog / rails pre-flight"},
            {"cmd": "wildfire-front ml freeze", "why": "lab freeze card (not field promote)"},
            {"cmd": "wildfire-front ml next", "why": "next-signal readiness (lab only)"},
        ],
        "docs": [
            "docs/ML_PRODUCT_START_HERE.md",
            "docs/PLAN_ML_PRODUCT_USABLE.md",
            "docs/METRICS_HONESTY_IOU_NE_ROS.md",
        ],
    }


def format_ml_hub_human(payload: dict[str, Any] | None = None) -> str:
    data = payload or build_ml_hub()
    gates = data.get("gates") or {}
    lines = [
        "╔══════════════════════════════════════════════════════════╗",
        "║  WFD · ML lab hub  (not field fusion · IoU ≠ ROS)        ║",
        "╚══════════════════════════════════════════════════════════╝",
        "",
        f"  banner:   {data.get('banner')}",
        f"  product:  {data.get('default_product')}  · surface={data.get('recommended_lab_surface')}"
        f"  thr={data.get('iter1_reject_thr')}",
        f"  rails:    ml_product_go={gates.get('ml_product_go')}  ·  "
        f"field_ops fusion={gates.get('field_ops_ml_live_fusion')}",
        f"  note:     {gates.get('note')}",
        "",
        "── Empieza aquí (offline OK) ──",
    ]
    for row in data.get("start_here") or []:
        lines.append(f"  {row.get('cmd')}")
        if row.get("why"):
            lines.append(f"      → {row['why']}")
    lines.append("")
    lines.append(f"  SUBCOMMANDS: {' '.join(data.get('subcommands') or [])}")
    lines.append("  Más: wildfire-front ml --help · wildfire-front ml SUB --help")
    docs = data.get("docs") or []
    if docs:
        lines.append(f"  Docs: {' · '.join(docs)}")
    lines.append("")
    return "\n".join(lines)


def run_ml_hub(args: argparse.Namespace) -> int:
    """Bare ``ml`` — exit 0 hub (discoverability only; gates frozen)."""
    payload = build_ml_hub()
    if bool(getattr(args, "json", False)):
        print_json(payload)
    else:
        sys.stdout.write(format_ml_hub_human(payload))
    return 0


def run_ml(args: argparse.Namespace) -> int:
    """Dispatch ``ml`` subcommands. Bare ``ml`` → hub (exit 0)."""
    cmd = getattr(args, "ml_command", None)
    if cmd is None:
        return run_ml_hub(args)
    if cmd == "list":
        return run_ml_list(args)
    if cmd == "show":
        return run_ml_show(args)
    if cmd == "doctor":
        return run_ml_doctor(args)
    if cmd == "predict":
        return run_ml_predict(args)
    if cmd == "card":
        return run_ml_card(args)
    if cmd == "cases":
        return run_ml_cases(args)
    if cmd == "curve":
        return run_ml_curve(args)
    if cmd == "freeze":
        return run_ml_freeze(args)
    if cmd == "smoke":
        return run_ml_smoke(args)
    if cmd == "lofo":
        return run_ml_lofo(args)
    if cmd == "lift":
        return run_ml_lift(args)
    if cmd == "next":
        return run_ml_next(args)
    print(f"error: unknown ml subcommand: {cmd}", file=sys.stderr)
    return 2
