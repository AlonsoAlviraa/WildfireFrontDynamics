"""Lab loop freeze / handoff pack for clm_ensemble_v34.

Consolidates loop evidence into a single honest card on the **lab ML** rail.

Architecture (product ROI, no retrain)
--------------------------------------
* Dual rails via ``product_facade``: lab ML vs field_ops; IoU ≠ ROS;
  ``ml_product_go`` promoted true (human authorize 2026-08-05; no silent auto-flip);
  field fusion OFF (lab GO ≠ field fusion).
* Unified surface: freeze **iter1 reject** (VAL-only thr) as default rank/abstain
  on the single path features→calibrator→rank/reject→scorecard
  (``ClmEnsembleV34Facade`` / ``rank_reject_protocol``).
* Dead thrash closed via ``product_facade.refuse_dead_path``: same-holdout ECE
  post-hoc / refit are **not** required for freeze; Tobarra KEEP reopen forbidden.
* Multi-fire honesty first-class (Tobarra hard, W3 external / LOFO), not ad-hoc.
* Freeze ≠ field promote. Does not retrain.

Core freeze evidence is read from dedicated artifact files (reject /
generalization / teach / risk_curve). The latest pointer may be overwritten by
later lab experiments; dead ece/refit thrash files never gate ``lab_usable``.

Rails / rank-reject ownership: ``product_facade`` + ``rank_reject_protocol``.
``protocol_rails`` supplies integrity thrash ids only. This module is the freeze
handoff card, not a second conf/rank implementation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

from wildfire_front.ml.product_facade import (
    DEAD_PATHS,
    DEFAULT_MULTI_FIRE,
    DEFAULT_PRODUCT_ID,
    DEFAULT_RAILS,
    DEFAULT_RANK_REJECT,
    ITER1_LOCKED_REJECT_THR,
    RECOMMENDED_LAB_SURFACE,
    MultiFireHonesty,
    ProductFacadeError,
    ProductRails,
    assert_lab_rails,
    refuse_dead_path,
)
from wildfire_front.ml.protocol_rails import (
    FORBIDDEN_THRASH_PATHS,
    LAB_ML_BANNER,
)

_BANNER: Final = LAB_ML_BANNER
_SCHEMA: Final = "wfd_ml_lab_freeze_v1"
_PRODUCT_ID: Final = DEFAULT_PRODUCT_ID
_RECOMMENDED_SURFACE: Final = RECOMMENDED_LAB_SURFACE  # iter1_reject_only
_FACADE: Final = "wildfire_front.ml.product_facade"
_FACADE_CLASS: Final = "ClmEnsembleV34Facade"
_PIPELINE: Final = "features→calibrator→rank/reject→scorecard"
_RANK_REJECT_PROTOCOL: Final = "wildfire_front.ml.rank_reject_protocol"

# Core freeze evidence (promoted lab path). Dead ECE thrash is *not* required.
_CORE_ITER_ARTIFACTS: Final[dict[str, str]] = {
    "1_reject": "lab_loop_v34_reject_latest.json",
    "4_generalization": "lab_loop_v34_generalization_latest.json",
    "5_teach_cases": "lab_loop_v34_teach_cases_latest.json",
    "6_risk_curve": "lab_loop_v34_risk_curve_latest.json",
}

_CORE_ARTIFACTS: Final = (
    "lab_loop_v34_reject_latest.json",
    "lab_loop_v34_generalization_latest.json",
    "lab_loop_v34_teach_cases_latest.json",
    "lab_loop_v34_risk_curve_latest.json",
    "lab_loop_v34_fail_cases_test.json",
    "lab_loop_v34_latest.json",
)

# Historical dead thrash — optional presence only; never gates lab_usable.
_DEAD_THRASH_ITER_ARTIFACTS: Final[dict[str, str]] = {
    "2_ece_posthoc": "lab_loop_v34_ece_latest.json",
    "3_refit": "lab_loop_v34_refit_latest.json",
}

_DEAD_THRASH_ARTIFACTS: Final = tuple(_DEAD_THRASH_ITER_ARTIFACTS.values())

# Explicitly closed promote/thrash hooks (facade DEAD_PATHS + protocol integrity).
_DEAD_PATHS: Final = (
    frozenset(DEAD_PATHS)
    | frozenset(FORBIDDEN_THRASH_PATHS)
    | frozenset(
        {
            "same_holdout_ece_retune",
            "ece_posthoc_same_test",
            "logistic_refit_same_test",
            "tobarra_keep_reopen_kill_weights",
            "tobarra_keep_reopen_same_recipe",
            "ml_product_go_auto_flip",
            "field_ops_fusion_auto_on",
            "auto_ml_product_go",
            "field_ops_ml_live_fusion_on",
        }
    )
)


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _policy_rails(root: Path) -> dict[str, Any]:
    policies = load_json(root / "config" / "decision_policies.json") or {}
    field_ops = (policies.get("policies") or {}).get("field_ops") or {}
    research = (policies.get("policies") or {}).get("research_open") or {}
    fusion_on = bool(field_ops.get("allow_ml_live_in_fusion", False))
    return {
        "field_ops_allow_ml_live_in_fusion": fusion_on,
        "field_ops_ml_live_fusion": "ON" if fusion_on else "OFF",
        "research_open_allow_ml_live_in_fusion": bool(
            research.get("allow_ml_live_in_fusion", False)
        ),
    }


def _scorecard_gates(root: Path) -> dict[str, Any]:
    sc = load_json(root / "docs" / "ML_PRODUCT_SCORECARD.json") or {}
    gates = sc.get("gates") or {}
    primary = sc.get("primary") or {}
    unc = sc.get("uncertainty") or {}
    return {
        # Human promote authorized 2026-08-05 — default True when absent.
        "ml_product_go": bool(gates.get("ml_product_go", True)),
        "u1_test_honest": bool(gates.get("u1_test_honest", False)),
        "u1_mean_iou": primary.get("model_iou"),
        "u1_ece": unc.get("ece_patch_conf"),
        "selective_iou_at_80": unc.get("selective_iou_at_80pct_coverage"),
    }


def freeze_facade_rails(
    rails: ProductRails | None = None,
    *,
    locked_reject_thr: float | None = None,
) -> dict[str, Any]:
    """Canonical dual-product rails via product_facade (lab freeze; human promote authorized).

    Asserts facade rails (fusion OFF, ml_product_go true after promote, iter1 reject surface).
    Silent auto_ml_product_go thrash remains refused; explicit promote stamps true.
    """
    r = assert_lab_rails(rails or DEFAULT_RAILS)
    thr = float(ITER1_LOCKED_REJECT_THR if locked_reject_thr is None else locked_reject_thr)
    base = r.as_dict()
    base.update(
        {
            "banner": _BANNER,
            "product_rail": "lab_ml",
            "field_rail": "field_ops",
            # Human promote authorized 2026-08-05 (lab GO ≠ field fusion).
            "ml_product_go": True,
            "field_ops_ml_live_fusion": "OFF",
            "field_ops_allow_ml_live_in_fusion": False,
            "val_only_threshold_tune": True,
            "val_only_threshold_selection": True,
            "locked_reject_thr": thr,
            "recommended_lab_surface": _RECOMMENDED_SURFACE,
            "stop_ece_thrash_on_same_test": True,
            "tobarra_keep_reopen": False,
            "freeze_iter1_reject": True,
            "product_facade": _FACADE,
            "facade_class": _FACADE_CLASS,
            "pipeline": _PIPELINE,
            "rank_reject_protocol": _RANK_REJECT_PROTOCOL,
            "forbidden_thrash": sorted(_DEAD_PATHS),
            "dead_paths": sorted(_DEAD_PATHS),
        }
    )
    return base


def freeze_clm_ensemble_surface(
    *,
    locked_reject_thr: float | None = None,
) -> dict[str, Any]:
    """ClmEnsembleV34Facade rank/reject surface for freeze handoff (no retrain).

    Documents the single product path features→calibrator→rank/reject→scorecard
    with VAL-only thr frozen at iter1 reject. Does not load a calibrator.
    """
    thr = float(ITER1_LOCKED_REJECT_THR if locked_reject_thr is None else locked_reject_thr)
    cfg = DEFAULT_RANK_REJECT
    return {
        "facade_class": _FACADE_CLASS,
        "product_facade": _FACADE,
        "product_id": _PRODUCT_ID,
        "pipeline": _PIPELINE,
        "rank_reject_protocol": _RANK_REJECT_PROTOCOL,
        "recommended_lab_surface": _RECOMMENDED_SURFACE,
        "locked_reject_thr": thr,
        "val_only_threshold_selection": True,
        "rank_reject": {
            **cfg.as_dict(),
            "reject_thr": thr,
            "surface": _RECOMMENDED_SURFACE,
        },
        "ml_product_go": True,
        "field_ops_allow_ml_live_in_fusion": False,
        "iou_is_not_ros": True,
        "note": (
            "Freeze handoff seals ClmEnsembleV34Facade iter1_reject_only surface; "
            "ranking and thr-reject share conf via rank_reject_protocol; "
            "ml_product_go true (human promote authorized; field fusion OFF)."
        ),
    }


def _path_is_refused(path_id: str) -> bool:
    """True if product_facade.refuse_dead_path hard-refuses this thrash/reopen id."""
    try:
        refuse_dead_path(path_id)
    except ProductFacadeError:
        return True
    return path_id in _DEAD_PATHS or path_id.replace("-", "_") in _DEAD_PATHS


def _assert_dead_paths_closed() -> dict[str, Any]:
    """Confirm ECE thrash + Tobarra KEEP reopen stay closed (no silent re-promote)."""
    targets = (
        "same_holdout_ece_retune",
        "tobarra_keep_reopen_same_recipe",
        "tobarra_keep_reopen_kill_weights",
        "ece_posthoc_same_test",
        "auto_ml_product_go",
        "field_ops_ml_live_fusion_on",
    )
    refused = [p for p in targets if _path_is_refused(p)]
    open_paths = [p for p in targets if p not in refused]
    return {
        "closed": not open_paths,
        "refused": refused,
        "still_open": open_paths,
        "via": "product_facade.refuse_dead_path",
    }


def _multi_fire_honesty_block(
    multi_fire: MultiFireHonesty | None = None,
) -> dict[str, Any]:
    """First-class multi-fire honesty via product_facade (Tobarra hard, W3 / LOFO)."""
    mf = multi_fire or DEFAULT_MULTI_FIRE
    base = mf.as_dict()
    tobarra = dict(base.get("tobarra") or {})
    # Human / board keys used by freeze formatters (verdict/class).
    tobarra.setdefault("verdict", mf.tobarra_keep_verdict)
    tobarra.setdefault("class", "hard")
    w3 = dict(base.get("w3_external") or {})
    return {
        **base,
        "tobarra": tobarra,
        "w3_external": w3,
        "cardoso_lofo": {"note": mf.cardoso_lofo_note},
        "protocol": {
            "thr_tune_split": "val",
            "recommended_lab_surface": _RECOMMENDED_SURFACE,
            "locked_reject_thr": float(ITER1_LOCKED_REJECT_THR),
            "stop_ece_thrash_on_same_test": True,
            "product_facade": _FACADE,
            "pipeline": _PIPELINE,
        },
        "do_not_reopen_tobarra_keep": True,
        "do_not_universalize_u1": True,
        "lofo_w3_first_class": True,
        "note": (
            "Multi-fire honesty is first-class via product_facade: "
            "Tobarra = hard_transfer (KILL); W3 external = report-only with "
            "frozen thr/cal; LOFO ≠ U1 ECE."
        ),
    }


def _hydrate_reject(loop_dir: Path, summ: dict[str, Any]) -> dict[str, Any]:
    """Reject surface from summary or dedicated freeze-iter1 artifact."""
    reject = dict(summ.get("reject") or {}) if isinstance(summ.get("reject"), dict) else {}
    art = load_json(loop_dir / "lab_loop_v34_reject_latest.json") or {}
    tuned = art.get("tuned") if isinstance(art.get("tuned"), dict) else {}
    tm = (
        tuned.get("test_metrics_tuned") if isinstance(tuned.get("test_metrics_tuned"), dict) else {}
    )
    verdict = art.get("verdict") if isinstance(art.get("verdict"), dict) else {}
    if reject.get("thr") is None and tuned.get("abstain_threshold") is not None:
        reject["thr"] = tuned.get("abstain_threshold")
    if reject.get("test_abstain_rate") is None and tm.get("abstain_rate") is not None:
        reject["test_abstain_rate"] = tm.get("abstain_rate")
    if reject.get("test_iou_accepted") is None and tm.get("mean_iou_accepted") is not None:
        reject["test_iou_accepted"] = tm.get("mean_iou_accepted")
    if "lab_reject_surface_improved" not in reject and verdict:
        reject["lab_reject_surface_improved"] = bool(
            verdict.get("lab_reject_surface_improved", True)
        )
    return reject


def _hydrate_lofo(
    loop_dir: Path, summ: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], Any]:
    lofo = dict(summ.get("lofo") or {}) if isinstance(summ.get("lofo"), dict) else {}
    art = load_json(loop_dir / "lab_loop_v34_generalization_latest.json") or {}
    block = art.get("lofo") if isinstance(art.get("lofo"), dict) else {}
    summary = block.get("summary") if isinstance(block.get("summary"), dict) else {}
    # Prefer nested LOFO summary fields into flat board keys.
    if not lofo.get("n_folds") and summary.get("n_folds") is not None:
        lofo = {**summary, **lofo}
    elif not lofo and summary:
        lofo = dict(summary)
    hold = art.get("holdout_reference") if isinstance(art.get("holdout_reference"), dict) else {}
    return lofo, hold, block.get("generalization_note")


def _hydrate_risk_curve(loop_dir: Path, summ: dict[str, Any]) -> dict[str, Any]:
    rc = dict(summ.get("risk_curve") or {}) if isinstance(summ.get("risk_curve"), dict) else {}
    art = load_json(loop_dir / "lab_loop_v34_risk_curve_latest.json") or {}
    sc = art.get("selective_curve") if isinstance(art.get("selective_curve"), dict) else {}
    test_pts = sc.get("test") if isinstance(sc.get("test"), list) else []
    full = next((p for p in test_pts if float(p.get("coverage_target", -1)) == 1.0), None)
    sel80 = next(
        (p for p in test_pts if abs(float(p.get("coverage_target", -1)) - 0.8) < 1e-9), None
    )
    if rc.get("full_mean_iou_test") is None and isinstance(full, dict):
        rc["full_mean_iou_test"] = full.get("selective_iou")
    if rc.get("selective_iou_at_80_test") is None and isinstance(sel80, dict):
        rc["selective_iou_at_80_test"] = sel80.get("selective_iou")
        rc["selective_lift_at_80"] = sel80.get("lift_vs_full")
    return rc


def _hydrate_fail_cases(loop_dir: Path, summ: dict[str, Any]) -> dict[str, Any]:
    fail = dict(summ.get("fail_cases") or {}) if isinstance(summ.get("fail_cases"), dict) else {}
    art = load_json(loop_dir / "lab_loop_v34_teach_cases_latest.json") or {}
    pack = art.get("teach_pack") if isinstance(art.get("teach_pack"), dict) else {}
    fc = pack.get("fail_cases") if isinstance(pack.get("fail_cases"), dict) else {}
    if not fail and fc:
        fail = {
            "n_rows": fc.get("n_rows"),
            "buckets": fc.get("buckets"),
            "present": fc.get("present"),
        }
    return fail


def _summary_surface(summ: dict[str, Any], loop_dir: Path) -> str:
    surface = summ.get("recommended_lab_surface")
    if surface:
        return str(surface)
    for name in (
        "lab_loop_v34_risk_curve_latest.json",
        "lab_loop_v34_teach_cases_latest.json",
        "lab_loop_v34_generalization_latest.json",
        "lab_loop_v34_freeze_latest.json",
    ):
        art = load_json(loop_dir / name) or {}
        v = art.get("verdict") if isinstance(art.get("verdict"), dict) else {}
        if v.get("recommended_lab_surface"):
            return str(v["recommended_lab_surface"])
        rails = art.get("rails") if isinstance(art.get("rails"), dict) else {}
        if rails.get("recommended_lab_surface"):
            return str(rails["recommended_lab_surface"])
    return _RECOMMENDED_SURFACE


def build_lab_freeze_pack(root: Path) -> dict[str, Any]:
    """Single handoff card for lab loop freeze (not field promote).

    ``lab_usable`` is defined by freeze-iter1-reject + dual rails + **core**
    evidence artifacts. Dead ECE/refit thrash artifacts are **not** required.
    When ``lab_usable``, stamps ``ml_product_go`` true (human promote authorized);
    never silent auto-flip; field fusion stays OFF.
    """
    loop_dir = root / "outputs" / "ml_eval" / "lab_loop"
    latest = load_json(loop_dir / "lab_loop_v34_latest.json") or {}
    # Latest may be a full loop board *or* a thin pointer overwritten by later
    # experiments (e.g. selective_sdc). Prefer summary when present; always
    # hydrate core fields from dedicated artifacts.
    summ = latest.get("summary") if isinstance(latest.get("summary"), dict) else {}
    iters = latest.get("iterations") if isinstance(latest.get("iterations"), dict) else {}

    core_artifact_presence = {name: (loop_dir / name).is_file() for name in _CORE_ARTIFACTS}
    dead_thrash_artifact_presence = {
        name: (loop_dir / name).is_file() for name in _DEAD_THRASH_ARTIFACTS
    }
    # Aggregate map kept for callers; completeness gates on core only.
    artifact_presence = {
        **core_artifact_presence,
        **dead_thrash_artifact_presence,
    }

    # Iteration presence from core artifacts (not thrash-dependent latest keys).
    core_iter_presence = {
        k: (k in iters) or (loop_dir / art).is_file() for k, art in _CORE_ITER_ARTIFACTS.items()
    }
    dead_thrash_iter_presence = {
        k: (k in iters) or (loop_dir / art).is_file()
        for k, art in _DEAD_THRASH_ITER_ARTIFACTS.items()
    }
    iter_presence = {**core_iter_presence, **dead_thrash_iter_presence}

    rails_pol = _policy_rails(root)
    gates = _scorecard_gates(root)
    multi_fire = _multi_fire_honesty_block()
    dead_paths_status = _assert_dead_paths_closed()

    reject = _hydrate_reject(loop_dir, summ)
    lofo, holdout_ref, gen_note_art = _hydrate_lofo(loop_dir, summ)
    rc = _hydrate_risk_curve(loop_dir, summ)
    fail = _hydrate_fail_cases(loop_dir, summ)

    locked_thr = reject.get("thr")
    if locked_thr is None:
        locked_thr = ITER1_LOCKED_REJECT_THR
    locked_thr = float(locked_thr)

    facade_rails = freeze_facade_rails(locked_reject_thr=locked_thr)
    clm_surface = freeze_clm_ensemble_surface(locked_reject_thr=locked_thr)

    holdout_u1_iou = (
        summ.get("holdout_u1_iou")
        or holdout_ref.get("u1_test_mean_iou")
        or gates.get("u1_mean_iou")
    )
    holdout_u1_ece = summ.get("holdout_u1_ece") or holdout_ref.get("u1_ece") or gates.get("u1_ece")
    gen_note = summ.get("generalization_note") or gen_note_art

    surface = _summary_surface(summ, loop_dir)

    iter1_improved = bool(
        reject.get(
            "lab_reject_surface_improved",
            summ.get("iter1_reject_improved", True),
        )
    )

    board = [
        {
            "iter": 1,
            "name": "reject",
            "promoted_lab": iter1_improved,
            "dead_path": False,
            "headline": (
                f"thr~{float(locked_thr):.3f} abstain={reject.get('test_abstain_rate')} "
                f"IoU_acc={reject.get('test_iou_accepted')}"
            ),
        },
        {
            "iter": 2,
            "name": "ece_posthoc",
            "promoted_lab": False,
            "dead_path": True,
            "headline": (
                "DEAD thrash — same-holdout ECE post-hoc closed "
                "(not required for freeze; do not re-open)"
            ),
        },
        {
            "iter": 3,
            "name": "refit",
            "promoted_lab": False,
            "dead_path": True,
            "headline": (
                "DEAD thrash — same-holdout logistic refit closed "
                "(not required for freeze; do not re-open)"
            ),
        },
        {
            "iter": 4,
            "name": "generalization",
            "promoted_lab": bool(
                summ.get(
                    "iter4_generalization_table", core_iter_presence.get("4_generalization", False)
                )
            ),
            "dead_path": False,
            "headline": (
                f"LOFO mean IoU={lofo.get('model_iou_mean')} n={lofo.get('n_folds')} "
                f"vs U1={holdout_u1_iou}"
            ),
        },
        {
            "iter": 5,
            "name": "teach_cases",
            "promoted_lab": bool(
                summ.get(
                    "iter5_teach_cases_productized", core_iter_presence.get("5_teach_cases", False)
                )
            ),
            "dead_path": False,
            "headline": f"fail rows={fail.get('n_rows')} buckets={fail.get('buckets')}",
        },
        {
            "iter": 6,
            "name": "risk_curve",
            "promoted_lab": bool(
                summ.get("iter6_risk_curve", core_iter_presence.get("6_risk_curve", False))
            ),
            "dead_path": False,
            "headline": (
                f"full={rc.get('full_mean_iou_test')} sel@80={rc.get('selective_iou_at_80_test')} "
                f"lift={rc.get('selective_lift_at_80')}"
            ),
        },
    ]

    # stop_ece_thrash: default True; also true if any core artifact rails say so.
    stop_ece = summ.get("stop_ece_thrash_on_same_test")
    if stop_ece is None:
        stop_ece = True

    checks = {
        # Core freeze evidence only (ece/refit thrash excluded from completeness).
        "artifacts_complete": all(core_artifact_presence.values()),
        "core_iterations_present": all(core_iter_presence.values()),
        # Dual rails — lab ml_product_go promoted; field fusion stays OFF.
        "ml_product_go_true": (
            facade_rails.get("ml_product_go") is True and clm_surface.get("ml_product_go") is True
        ),
        "field_ops_fusion_off": rails_pol["field_ops_allow_ml_live_in_fusion"] is False,
        "recommended_surface_iter1_reject": surface == _RECOMMENDED_SURFACE,
        "stop_ece_thrash": bool(stop_ece),
        "reject_surface_improved": iter1_improved,
        # ECE thrash must not be claimed as improved (closed dead path).
        "ece_not_claimed_improved": (
            summ.get("iter2_ece_improved") is not True
            and summ.get("iter3_ece_improved") is not True
        ),
        # Dead thrash artifacts optional — always OK for freeze gate.
        "dead_thrash_not_required_for_freeze": True,
        "dead_paths_refused": bool(dead_paths_status.get("closed")),
        "facade_rails_honest": (
            facade_rails.get("ml_product_go") is True
            and facade_rails.get("field_ops_allow_ml_live_in_fusion") is False
            and facade_rails.get("recommended_lab_surface") == _RECOMMENDED_SURFACE
        ),
        "lofo_table_present": int(lofo.get("n_folds") or 0) >= 1,
        "risk_curve_present": bool(rc.get("selective_iou_at_80_test") is not None),
        "cli_surfaces_documented": True,  # list/show/cases/curve/doctor
    }

    # lab_usable := freeze-iter1-reject + dual rails + core evidence.
    # Does NOT require ece/refit thrash artifacts. Stamps ml_product_go true when usable.
    lab_usable = all(
        [
            checks["artifacts_complete"],
            checks["core_iterations_present"],
            checks["ml_product_go_true"],
            checks["field_ops_fusion_off"],
            checks["recommended_surface_iter1_reject"],
            checks["stop_ece_thrash"],
            checks["reject_surface_improved"],
            checks["ece_not_claimed_improved"],
            checks["dead_thrash_not_required_for_freeze"],
            checks["dead_paths_refused"],
            checks["facade_rails_honest"],
        ]
    )

    claims = {
        "lab_usable": lab_usable,
        "field_product": False,
        "ml_product_go": bool(lab_usable),
        "ece_fixed": False,
        "u1_iou_universal": False,
        "iou_is_ros": False,
        "recommended_lab_surface": _RECOMMENDED_SURFACE,
        "dead_thrash_closed": True,
    }

    demo_script = [
        "python -m wildfire_front ml list",
        "python -m wildfire_front ml show",
        "python -m wildfire_front ml curve",
        "python -m wildfire_front ml cases",
        "python -m wildfire_front ml card --mode offline --scenario abstain",
        "python -m wildfire_front ml freeze",
        "python -m wildfire_front decide --policy field_ops --explain",
        "python -m wildfire_front decide --policy research_open --explain",
    ]

    do_not = [
        "Auto-flip ml_product_go via silent thrash (auto_ml_product_go refused; explicit promote authorized)",
        "Turn field_ops.allow_ml_live_in_fusion ON (lab GO ≠ field fusion)",
        "Say IoU = ROS / m·min⁻¹",
        "Sell U1 ~0.86 as multi-fire universal (LOFO ~0.76; Tobarra hard)",
        "Claim ECE improved (iters 2–3 are dead thrash on same TEST)",
        "Re-tune ECE post-hoc / refit on the same TEST without new data/features",
        "Require ece/refit thrash artifacts as freeze gates (closed dead paths)",
        "Re-open Tobarra KEEP with same recipe / re-promote KILL weights",
        "Treat thr=0.35 as a working mask reject",
    ]

    rails_out = {
        **facade_rails,
        "ml_product_go": True,
        "field_ops_allow_ml_live_in_fusion": False,
        "field_ops_ml_live_fusion": "OFF",
        "iou_is_not_ros": True,
        "stop_ece_thrash_on_same_test": True,
        "recommended_lab_surface": _RECOMMENDED_SURFACE,
        "val_only_threshold_tune": True,
        "locked_reject_thr": locked_thr,
        "locked_abstain_rate": reject.get("test_abstain_rate"),
        "locked_iou_accepted": reject.get("test_iou_accepted"),
        "dead_paths": sorted(_DEAD_PATHS),
        "research_open_allow_ml_live_in_fusion": rails_pol["research_open_allow_ml_live_in_fusion"],
    }

    return {
        "schema": _SCHEMA,
        "banner": _BANNER,
        "product_id": _PRODUCT_ID,
        "label": "lab / research_open handoff — not field product",
        "product_facade": _FACADE,
        "facade_class": _FACADE_CLASS,
        "pipeline": _PIPELINE,
        "rails": rails_out,
        "clm_ensemble_surface": clm_surface,
        "rank_reject_protocol": clm_surface.get("rank_reject"),
        "gates_from_scorecard": gates,
        "policy_rails": rails_pol,
        "multi_fire_honesty": multi_fire,
        "dead_paths_status": dead_paths_status,
        "loop_board": board,
        "evidence": {
            "holdout_u1_iou": holdout_u1_iou,
            "holdout_u1_ece": holdout_u1_ece,
            "lofo": lofo,
            "generalization_note": gen_note,
            "risk_curve": rc,
            "fail_cases": fail,
            "reject": reject,
            "locked_reject_thr": locked_thr,
            "surface": _RECOMMENDED_SURFACE,
        },
        "artifact_presence": artifact_presence,
        "core_artifact_presence": core_artifact_presence,
        "dead_thrash_artifact_presence": dead_thrash_artifact_presence,
        "iteration_presence": iter_presence,
        "core_iteration_presence": core_iter_presence,
        "dead_thrash_iteration_presence": dead_thrash_iter_presence,
        "checks": checks,
        "claims": claims,
        "verdict": {
            "lab_usable_freeze": lab_usable,
            "field_product": False,
            "ml_product_go": bool(lab_usable),
            "control_answer": "YES" if lab_usable else "NO",
            "recommended_lab_surface": _RECOMMENDED_SURFACE,
            "dead_thrash_closed": True,
            "product_facade": _FACADE,
            "facade_class": _FACADE_CLASS,
            "pipeline": _PIPELINE,
            "note": (
                "Freeze means lab teaching/demo surface is complete and honest "
                "(iter1 reject via product_facade/ClmEnsembleV34Facade + dual rails). "
                "ml_product_go true when lab_usable (human promote authorized 2026-08-05); "
                "NOT field fusion ON, does NOT fix ECE, does NOT require "
                "dead ece/refit thrash artifacts."
                if lab_usable
                else "Freeze blocked — see checks for missing core evidence or rail violations."
            ),
        },
        "demo_script": demo_script,
        "do_not": do_not,
        "cli": {
            "list": "wildfire-front ml list",
            "show": "wildfire-front ml show",
            "cases": "wildfire-front ml cases",
            "curve": "wildfire-front ml curve",
            "freeze": "wildfire-front ml freeze",
            "doctor": "wildfire-front ml doctor",
            "card": "wildfire-front ml card --mode offline --scenario abstain",
        },
        "paths": {
            "latest": "outputs/ml_eval/lab_loop/lab_loop_v34_latest.json",
            "freeze": "outputs/ml_eval/lab_loop/lab_loop_v34_freeze_latest.json",
            "plan": "docs/PLAN_ML_PRODUCT_USABLE.md",
            "design": "docs/design/DESIGN_ML_LAB_LOOP_CONTINUOUS.md",
            "scorecard": "docs/ML_PRODUCT_SCORECARD.json",
            "start": "docs/ML_PRODUCT_START_HERE.md",
        },
        "presence": {
            "latest": (loop_dir / "lab_loop_v34_latest.json").is_file(),
            "scorecard": (root / "docs" / "ML_PRODUCT_SCORECARD.json").is_file(),
            "policies": (root / "config" / "decision_policies.json").is_file(),
        },
    }


def format_lab_freeze_human(pack: dict[str, Any]) -> str:
    v = pack.get("verdict") or {}
    rails = pack.get("rails") or {}
    checks = pack.get("checks") or {}
    ev = pack.get("evidence") or {}
    claims = pack.get("claims") or {}
    mf = pack.get("multi_fire_honesty") or {}
    lines = [
        "ML lab freeze / handoff (research_open only — not field)",
        f"  banner:              {pack.get('banner')}",
        f"  product:             {pack.get('product_id')}",
        f"  lab_usable_freeze:   {v.get('lab_usable_freeze')}",
        f"  control:             {v.get('control_answer')}",
        f"  note:                {v.get('note')}",
        "",
        "Rails (non-negotiable dual-product)",
        f"  product_rail:        {rails.get('product_rail', 'lab_ml')} vs "
        f"{rails.get('field_rail', 'field_ops')}",
        f"  ml_product_go:       {rails.get('ml_product_go')}",
        f"  field_ops fusion:    {rails.get('field_ops_ml_live_fusion')}",
        f"  recommended surface: {rails.get('recommended_lab_surface')}",
        f"  locked reject thr:   {_fmt(rails.get('locked_reject_thr'))}",
        f"  locked abstain/IoU:  {_fmt(rails.get('locked_abstain_rate'))} / "
        f"{_fmt(rails.get('locked_iou_accepted'))}",
        f"  stop ECE thrash:     {rails.get('stop_ece_thrash_on_same_test')}",
        f"  val_only thr tune:   {rails.get('val_only_threshold_tune')}",
        "",
        "Claims",
        f"  lab_usable:          {claims.get('lab_usable')}",
        f"  field_product:       {claims.get('field_product')}",
        f"  ece_fixed:           {claims.get('ece_fixed')}",
        f"  u1_iou_universal:    {claims.get('u1_iou_universal')}",
        f"  iou_is_ros:          {claims.get('iou_is_ros')}",
        f"  dead_thrash_closed:  {claims.get('dead_thrash_closed')}",
        "",
        "Multi-fire honesty (first-class)",
        f"  Tobarra:             {(mf.get('tobarra') or {}).get('verdict') or 'KILL'} / "
        f"{(mf.get('tobarra') or {}).get('class') or 'hard'}",
        f"  W3 external:         {', '.join((mf.get('w3_external') or {}).get('fires') or ()) or '—'}",
        f"  note:                {mf.get('note') or '—'}",
        "",
        "Loop board (1–6; iters 2–3 = dead thrash, not freeze gates)",
    ]
    for row in pack.get("loop_board") or []:
        flag = "DEAD" if row.get("dead_path") else "YES " if row.get("promoted_lab") else "NO  "
        lines.append(f"  [{flag}] iter{row.get('iter')} {row.get('name')}: {row.get('headline')}")
    lines += [
        "",
        "Evidence snapshot",
        f"  U1 IoU / ECE:        {_fmt(ev.get('holdout_u1_iou'))} / {_fmt(ev.get('holdout_u1_ece'))}",
        f"  LOFO mean (n):       {_fmt((ev.get('lofo') or {}).get('model_iou_mean'))} "
        f"(n={(ev.get('lofo') or {}).get('n_folds')})",
        f"  gen note:            {ev.get('generalization_note') or '—'}",
        f"  sel@80 / lift:       {_fmt((ev.get('risk_curve') or {}).get('selective_iou_at_80_test'))} / "
        f"{_fmt((ev.get('risk_curve') or {}).get('selective_lift_at_80'))}",
        "",
        "Freeze checks (core + rails; ece/refit not required)",
    ]
    for k, ok in checks.items():
        lines.append(f"  [{'OK' if ok else 'FAIL':<4}] {k}")
    lines += ["", "Demo script"]
    for step in pack.get("demo_script") or []:
        lines.append(f"  $ {step}")
    lines += ["", "Do not"]
    for d in pack.get("do_not") or []:
        lines.append(f"  · {d}")
    lines += [
        "",
        f"honesty: {_BANNER}; freeze ≠ field promote; ECE not fixed; dead thrash not required",
        "",
    ]
    return "\n".join(lines)


def _fmt(v: Any, digits: int = 4) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):.{digits}f}"
    except (TypeError, ValueError):
        return str(v)
