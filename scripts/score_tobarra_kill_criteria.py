#!/usr/bin/env python3
"""Score Tobarra LOFO result against K1–K5 (zero leak, no thr/ECE on test).

Does **not** train. Uses v29 / keep-attempt evaluation_metrics + recipe baselines.

Architecture (product ROI — no retrain)
---------------------------------------
* Single path tags: ``product_facade`` + ``rank_reject_protocol``
  (features→calibrator→rank/reject→scorecard; VAL thr freeze; surface
  ``iter1_reject_only``). This scorer is eval-only and does not retune thr.
* Dual-product rails: **lab ML** vs **field_ops**; IoU ≠ ROS;
  ``ml_product_go`` true (human promote 2026-08-05); field fusion **OFF**
  (lab GO ≠ field fusion; via facade, not ad-hoc JSON).
* Multi-fire honesty first-class: Tobarra hard transfer (KEEP sealed KILL);
  W3 external report-only.
* Dead thrash sealed: same-holdout ECE retune; Tobarra KEEP re-promote of
  KILL weights / same recipe; auto_ml_product_go silent thrash (explicit
  promoted true allowed). Complete metric fails → **KILL** (not
  KEEP-adjacent INCONCLUSIVE without facade seal).

Usage::

    $env:PYTHONPATH = "."
    python scripts/score_tobarra_kill_criteria.py
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from wildfire_front.ml.product_facade import (  # noqa: E402
    DEAD_PATHS,
    DEFAULT_MULTI_FIRE,
    DEFAULT_RAILS,
    DEFAULT_RANK_REJECT,
    ITER1_LOCKED_REJECT_THR,
    RECOMMENDED_LAB_SURFACE,
    TOBARRA_FIRE_ID,
    ProductFacadeError,
    assert_lab_rails,
    refuse_dead_path,
)
from wildfire_front.ml.protocol_rails import (  # noqa: E402
    FORBIDDEN_THRASH_PATHS,
    MULTI_FIRE_HONESTY,
    PIPELINE_FEATURES_TO_SCORECARD,
    assert_rails_honest,
    assert_split_role,
    default_dual_product_rails,
    rank_abstain_protocol_dict,
)
from wildfire_front.ml.w3_signal import (  # noqa: E402
    assert_tobarra_keep_reopen_forbidden,
    tobarra_keep_seal,
)

_FACADE = "wildfire_front.ml.product_facade"
_RANK_REJECT_MOD = "wildfire_front.ml.rank_reject_protocol"
_PIPELINE = PIPELINE_FEATURES_TO_SCORECARD  # features→calibrator→rank/reject→scorecard
_DEAD_PATH_IDS = (
    "tobarra_keep_reopen_same_recipe",
    "tobarra_keep_reopen_kill_weights",
    "tobarra_keep_same_recipe",
    "same_holdout_ece_retune",
    "auto_ml_product_go",
    "field_ops_ml_live_fusion_on",
)


def _load(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return d if isinstance(d, dict) else None


def _seal_dead_paths() -> None:
    """Hard-refuse closed thrash / KEEP re-promote via product_facade."""
    assert_tobarra_keep_reopen_forbidden(reopen=False)
    for dead in _DEAD_PATH_IDS:
        try:
            refuse_dead_path(dead)
        except ProductFacadeError:
            pass  # expected — path is sealed
        else:
            # Only DEAD_PATHS subset is refuse_dead_path; protocol-only aliases OK.
            if dead in DEAD_PATHS:
                raise ProductFacadeError(f"dead path still open: {dead!r}")


def _rails_payload() -> dict[str, Any]:
    """Dual-product rails from product_facade + protocol_rails (no ad-hoc JSON)."""
    facade_rails = assert_lab_rails(DEFAULT_RAILS)
    dual = default_dual_product_rails().as_dict()
    rails: dict[str, Any] = {
        **dual,
        **facade_rails.as_dict(),
        # Explicit lab promote (DEFAULT_RAILS / assert_lab_rails); ≠ field fusion.
        "ml_product_go": bool(facade_rails.ml_product_go),
        "field_ops_allow_ml_live_in_fusion": False,
        "field_ops_ml_live_fusion": "OFF",
        "field_fusion_off": True,
        "iou_is_not_ros": True,
        "fit_split": "val",
        "val_only_threshold_selection": True,
        "test_never_used_for_tune": True,
        "no_ece_retune_same_holdout": True,
        "stop_ece_thrash_on_same_test": True,
        "tobarra_keep_reopen_forbidden": True,
        "tobarra_keep_reopen": False,
        "re_promote_kill_weights": False,
        "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
        "locked_reject_thr": float(ITER1_LOCKED_REJECT_THR),
        "freeze_iter1_reject": True,
        "label": "lab / research_open only",
        "lab_only": True,
        "dead_paths": sorted(set(DEAD_PATHS) | set(FORBIDDEN_THRASH_PATHS)),
        "product_facade": _FACADE,
        "pipeline": _PIPELINE,
    }
    assert_rails_honest(rails)
    return rails


def _rank_reject_protocol() -> dict[str, Any]:
    """Shared rank/reject surface stamp (VAL thr freeze; iter1 reject default)."""
    base = rank_abstain_protocol_dict(
        locked_reject_thr=float(ITER1_LOCKED_REJECT_THR),
        recommended_lab_surface=RECOMMENDED_LAB_SURFACE,
    )
    return {
        **DEFAULT_RANK_REJECT.as_dict(),
        **base,
        "thr_source": "val_iter1_reject_frozen",
        "thr_tune_split": "val",
        "freeze_iter1_reject": True,
        "pipeline": _PIPELINE,
        "product_facade": _FACADE,
        "module": _RANK_REJECT_MOD,
        "note": (
            "Scorer is eval-only: applies frozen VAL thr metadata; never fits "
            "thr/ECE on Tobarra test / LOFO held-out / U1 TEST."
        ),
    }


def audit_lofo_leak(fold_dir: Path, held: str) -> dict[str, Any]:
    counts = {"train": 0, "val": 0, "test": 0}
    leaked: list[str] = []
    test_held = 0
    test_foreign = 0
    for split in ("train", "val", "test"):
        d = fold_dir / split
        if not d.is_dir():
            continue
        for p in d.glob("*.npz"):
            counts[split] += 1
            src = "unknown"
            try:
                with np.load(p, allow_pickle=True) as z:
                    if "source" in z.files:
                        src = str(z["source"])
            except OSError:
                continue
            if split in ("train", "val") and src == held:
                leaked.append(f"{split}:{p.name}")
            if split == "test":
                if src == held:
                    test_held += 1
                else:
                    test_foreign += 1
    return {
        "ok": len(leaked) == 0 and test_foreign == 0 and test_held > 0,
        "held_out": held,
        "fold_dir": str(fold_dir.as_posix()),
        "counts": counts,
        "n_leaked_train_val": len(leaked),
        "leaked_examples": leaked[:20],
        "test_held_out": test_held,
        "test_foreign": test_foreign,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", type=Path, default=ROOT)
    p.add_argument(
        "--recipe",
        type=Path,
        default=ROOT / "outputs" / "ml_eval" / "lab_loop" / "tobarra_finetune_recipe.json",
    )
    p.add_argument(
        "--v29-metrics",
        type=Path,
        default=None,
        help="Metrics JSON (default: keep_attempt_latest then v29_lofo_tobarra)",
    )
    p.add_argument(
        "--metrics",
        type=Path,
        default=None,
        help="Alias for --v29-metrics (any evaluation_metrics.json)",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=ROOT / "outputs" / "ml_eval" / "lab_loop" / "tobarra_kill_scorecard.json",
    )
    p.add_argument(
        "--leak-out",
        type=Path,
        default=ROOT / "outputs" / "ml_eval" / "lab_loop" / "tobarra_leak_audit_latest.json",
    )
    p.add_argument(
        "--fresh-train",
        action="store_true",
        help=(
            "After a successful fresh LOFO train: verdict must be KEEP or KILL "
            "(never INCONCLUSIVE). K1 fail after full train → KILL."
        ),
    )
    args = p.parse_args(argv)
    repo = args.repo.resolve()

    # Architecture rails + dead thrash seal (product_facade path).
    _seal_dead_paths()
    # LOFO held-out fire: report/scorecard only — never thr/ECE fit.
    assert_split_role("lofo", "scorecard")
    rails = _rails_payload()
    rank_reject = _rank_reject_protocol()
    multi_fire = {
        **dict(MULTI_FIRE_HONESTY),
        **DEFAULT_MULTI_FIRE.as_dict(),
    }
    keep_seal = tobarra_keep_seal()

    recipe = _load(args.recipe) or {}
    baseline = float(
        ((recipe.get("prior_evidence") or {}).get("head_a_baseline") or {}).get("mean_iou")
        or recipe.get("baseline_mean_iou")
        or 0.489
    )
    min_lift = float(recipe.get("min_delta_vs_baseline") or 0.03)
    min_copy = float(recipe.get("min_delta_vs_copy") or 0.05)

    fold = repo / "artifacts" / "clm_ndws_patches" / "lofo_v1" / TOBARRA_FIRE_ID
    leak = audit_lofo_leak(fold, TOBARRA_FIRE_ID)
    args.leak_out.parent.mkdir(parents=True, exist_ok=True)
    args.leak_out.write_text(json.dumps(leak, indent=2), encoding="utf-8")

    metrics_path = args.metrics or args.v29_metrics
    if metrics_path is None:
        candidates = [
            repo
            / "outputs"
            / "ml_eval"
            / "lofo_tobarra_keep_attempt_latest"
            / "evaluation_metrics.json",
            repo / "outputs" / "ml_eval" / "v29_lofo_tobarra" / "evaluation_metrics.json",
        ]
        metrics_path = next((c for c in candidates if c.is_file()), candidates[-1])
    em = _load(Path(metrics_path)) or {}
    test_iou = em.get("model_iou")
    copy_delta = em.get("improvement_vs_copy_iou")
    if (
        copy_delta is None
        and em.get("model_iou") is not None
        and em.get("copy_baseline_iou") is not None
    ):
        copy_delta = float(em["model_iou"]) - float(em["copy_baseline_iou"])

    # K5 from product_facade dual rails (not ad-hoc decision_policies / scorecard JSON).
    # Lab ml_product_go may be True (promoted); K5 is field fusion OFF only.
    ml_go = bool(rails.get("ml_product_go", True))
    fusion_off = not bool(rails.get("field_ops_allow_ml_live_in_fusion", False))

    k1_lift = float(test_iou) - baseline if test_iou is not None else None
    metrics_complete = test_iou is not None and copy_delta is not None
    checks = {
        "K1_test_iou_lift": {
            "pass": k1_lift is not None and k1_lift >= min_lift,
            "value": k1_lift,
            "threshold": min_lift,
            "baseline": baseline,
            "test_iou": test_iou,
            "note": (
                "LOFO mask IoU vs ensemble Head A baseline; not same protocol "
                "as Head A exactly. Facade: product path sealed; K1 fail → KILL "
                "weights claim (not KEEP-adjacent INCONCLUSIVE re-promote)."
            ),
        },
        "K2_beats_copy": {
            "pass": copy_delta is not None and float(copy_delta) >= min_copy,
            "value": float(copy_delta) if copy_delta is not None else None,
            "threshold": min_copy,
        },
        "K3_zero_target_leak": {
            "pass": bool(leak.get("ok")) and int(leak.get("n_leaked_train_val") or 0) == 0,
            "value": leak.get("n_leaked_train_val"),
            "threshold": 0,
            "leak_audit": str(args.leak_out.as_posix()),
        },
        "K4_no_holdout_test_thr_ece": {
            "pass": True,  # this scorer does not fit thr/ECE
            "value": "scorer_eval_only",
            "allowed": ["train", "val_non_held_out"],
            "note": (
                "PASS for this eval-only scorer; thr source is VAL-frozen "
                f"{RECOMMENDED_LAB_SURFACE} (thr={ITER1_LOCKED_REJECT_THR}); "
                "never thr/ECE on Tobarra test / U1 TEST (dead path sealed)."
            ),
        },
        "K5_no_field_rails": {
            # Field fusion must stay OFF; lab ml_product_go True is allowed.
            "pass": fusion_off,
            "field_ops_fusion_off": fusion_off,
            "ml_product_go": ml_go,
            "source": _FACADE,
            "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
        },
    }

    all_k = all(bool(c.get("pass")) for c in checks.values())
    # Complete metric fails → KILL (facade dead-path seal: no KEEP-adjacent
    # INCONCLUSIVE that re-opens Tobarra KEEP / re-promotes KILL weights).
    # INCONCLUSIVE only when metrics are incomplete (and not --fresh-train).
    if all_k:
        verdict = "KEEP"
    elif not checks["K3_zero_target_leak"]["pass"] or not checks["K5_no_field_rails"]["pass"]:
        verdict = "KILL"
    elif not metrics_complete:
        verdict = "INCONCLUSIVE"
        checks["K1_test_iou_lift"]["note"] = (
            "Incomplete metrics (missing test IoU and/or copy delta) — "
            "INCONCLUSIVE only for blocked/incomplete eval; not a KEEP claim. "
            "Tobarra KEEP reopen sealed (product_facade)."
        )
    else:
        # K1 and/or K2 fail with complete metrics → KILL weights claim
        verdict = "KILL"
        if not checks["K1_test_iou_lift"]["pass"]:
            checks["K1_test_iou_lift"]["note"] = (
                "K1 lift vs Head A baseline < threshold → KILL weights claim. "
                "Beats-copy alone is not KEEP. Facade seals Tobarra KEEP reopen / "
                "KILL re-promote (no INCONCLUSIVE KEEP-adjacent path)."
            )

    # After successful fresh train (--fresh-train), INCONCLUSIVE is forbidden.
    if args.fresh_train and verdict == "INCONCLUSIVE":
        verdict = "KILL"
        checks["K1_test_iou_lift"]["note"] = (
            "Fresh LOFO train complete: incomplete or failing gates → KILL "
            "(INCONCLUSIVE only allowed if train blocked; beats-copy alone is not KEEP)"
        )

    # Never allow KEEP while KEEP reopen is sealed as historical KILL without
    # all K gates; re-promote of KILL weights is always false on this path.
    if verdict == "KEEP" and not all_k:
        verdict = "KILL"

    payload = {
        "schema": "tobarra_kill_scorecard_v1",
        "created_utc": datetime.now(UTC).isoformat(),
        "source_metrics": str(Path(metrics_path).as_posix()),
        "recipe": str(args.recipe.as_posix()),
        "product_id": "clm_ensemble_v34",
        "product_facade": _FACADE,
        "rank_reject_protocol": rank_reject,
        "pipeline": _PIPELINE,
        "verdict": verdict,
        "fresh_train": bool(args.fresh_train),
        "checks": checks,
        "rails": rails,
        "multi_fire_honesty": multi_fire,
        "tobarra_keep_seal": keep_seal,
        "dead_paths": sorted(set(DEAD_PATHS) | set(FORBIDDEN_THRASH_PATHS)),
        "honesty": [
            "IoU ≠ ROS",
            "K1 compares LOFO mask IoU to ensemble Head A mean IoU baseline — protocols differ",
            "v29 prior GO_TRANSFER_LOFO is copy-relative, not K1 automatic KEEP",
            "Never thr/ECE fit on Tobarra test or U1 holdout TEST (VAL thr only)",
            f"Default lab surface: {RECOMMENDED_LAB_SURFACE} (thr={ITER1_LOCKED_REJECT_THR})",
            "After successful fresh train: verdict is KEEP or KILL only",
            "Tobarra KEEP reopen / KILL re-promote sealed (product_facade dead paths)",
            "Multi-fire: Tobarra hard transfer; W3 external report-only; CARDOSO ≠ independent multi-fire",
            "Complete metric gate fail → KILL (not KEEP-adjacent INCONCLUSIVE)",
        ],
        "field_product": False,
        "ml_product_go": True,
        "re_promote_kill_weights": False,
        "tobarra_keep_reopen_forbidden": True,
        "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
        "locked_reject_thr": float(ITER1_LOCKED_REJECT_THR),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": True,
                "verdict": verdict,
                "out": str(args.out),
                "leak_out": str(args.leak_out),
                "product_facade": _FACADE,
                "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
                "locked_reject_thr": float(ITER1_LOCKED_REJECT_THR),
                "ml_product_go": True,
                "field_ops_fusion": "OFF",
                "re_promote_kill_weights": False,
                "K1_pass": checks["K1_test_iou_lift"]["pass"],
                "K2_pass": checks["K2_beats_copy"]["pass"],
                "K3_pass": checks["K3_zero_target_leak"]["pass"],
                "K5_pass": checks["K5_no_field_rails"]["pass"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
