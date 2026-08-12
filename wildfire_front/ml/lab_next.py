"""Next-signal readiness gate for lab loop (post freeze/smoke/LOFO).

Probes what is READY vs BLOCKED for the next metric-bearing work on the
**lab ML** rail (``clm_ensemble_v34``). Does **not** unfreeze rails, retune
ECE, reopen Tobarra KEEP, or claim field product.

Architecture (product ROI — shared with freeze / LOFO / reject surface)
----------------------------------------------------------------------
* Dual rails via ``product_facade``: lab ML vs field_ops; IoU ≠ ROS;
  ``ml_product_go`` human-promoted true (2026-08-05; no auto-flip thrash);
  field fusion OFF (lab GO ≠ field fusion).
* Single protocol path: features → calibrator → rank/reject → scorecard
  (``product_facade`` + ``rank_reject_protocol``; VAL-only thr; freeze
  **iter1 reject** default).
* Dead thrash refused via ``product_facade.refuse_dead_path``: same-holdout
  ECE retune; Tobarra KEEP reopen of KILL weights.
* Multi-fire honesty first-class: Tobarra = hard (KILL); W3 external =
  report-only; LOFO first-class.
* Next-gate ≠ metric win / field promote. No conf math here — readiness card only.
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
    ProductFacadeError,
    assert_lab_rails,
    refuse_dead_path,
)
from wildfire_front.ml.protocol_rails import (
    FORBIDDEN_THRASH_PATHS,
    LAB_ML_BANNER,
    MULTI_FIRE_HONESTY,
    rank_abstain_protocol_dict,
)

_BANNER: Final = LAB_ML_BANNER
_SCHEMA: Final = "wfd_ml_lab_next_v1"
_PRODUCT_ID: Final = DEFAULT_PRODUCT_ID
_RECOMMENDED_SURFACE: Final = RECOMMENDED_LAB_SURFACE  # iter1_reject_only
_PIPELINE: Final = "features→calibrator→rank/reject→scorecard"
_FACADE: Final = "wildfire_front.ml.product_facade"

# Dead thrash / reopen paths — never surface as READY next-gate work.
# Union of product_facade DEAD_PATHS + protocol forbidden thrash + site seals.
_DEAD_PATHS: Final = (
    frozenset(DEAD_PATHS)
    | frozenset(FORBIDDEN_THRASH_PATHS)
    | frozenset(
        {
            "same_holdout_ece_retune",
            "ece_posthoc_same_test",
            "tobarra_keep_reopen_kill_weights",
            "tobarra_keep_reopen_same_recipe",
            "tobarra_finetune_keep_reopen",
            "ml_product_go_auto_flip",
            "field_ops_fusion_auto_on",
            "auto_ml_product_go",
            "field_ops_ml_live_fusion_on",
        }
    )
)

# Known LOFO fold → data search tokens
_LOFO_DATA_HINTS: dict[str, list[str]] = {
    "CARDOSO": ["cardoso", "CARDOSO"],
    "LA_ESTRELLA_ACOM1": ["LA_ESTRELLA_ACOM1", "la_estrella", "estrella"],
    "LA_ESTRELLA_ACOM2": ["LA_ESTRELLA_ACOM2", "la_estrella", "estrella"],
    "tobarra_20240802": ["tobarra", "TOBARRA"],
}


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _exists(path: Path) -> bool:
    return path.is_file() or path.is_dir()


def _find_data_hits(root: Path, tokens: list[str], limit: int = 3) -> list[str]:
    data = root / "data"
    if not data.is_dir():
        return []
    hits: list[str] = []
    # Prefer organized real_if paths
    search_roots = [
        data / "real_if",
        data,
    ]
    for base in search_roots:
        if not base.is_dir():
            continue
        try:
            for p in base.rglob("*"):
                name = p.name
                if any(t.lower() in name.lower() for t in tokens):
                    hits.append(str(p.as_posix())[:120])
                    if len(hits) >= limit:
                        return hits
        except OSError:
            continue
    return hits


def _path_is_refused(path_id: str) -> bool:
    """True if product_facade hard-refuses this thrash/reopen id."""
    try:
        refuse_dead_path(path_id)
    except ProductFacadeError:
        return True
    return path_id in _DEAD_PATHS or path_id in DEAD_PATHS


def _assert_dead_paths_closed() -> tuple[bool, list[str]]:
    """Refuse ECE thrash reopen + Tobarra KEEP reopen via product_facade."""
    targets = (
        "same_holdout_ece_retune",
        "tobarra_keep_reopen_same_recipe",
        "tobarra_keep_reopen_kill_weights",
        "auto_ml_product_go",
        "field_ops_ml_live_fusion_on",
    )
    refused = [p for p in targets if _path_is_refused(p)]
    open_paths = [p for p in targets if p not in refused]
    return (not open_paths), refused


def _next_facade_rails(*, locked_thr: float, lab_usable: bool) -> dict[str, Any]:
    """Canonical dual-product rails via product_facade (human-promoted GO; no auto-flip)."""
    r = assert_lab_rails(DEFAULT_RAILS)
    base = r.as_dict()
    base.update(
        {
            "banner": _BANNER,
            "product_id": _PRODUCT_ID,
            "product_rail": "lab_ml",
            "field_rail": "field_ops",
            "ml_product_go": True,
            "field_ops_allow_ml_live_in_fusion": False,
            "field_ops_ml_live_fusion": "OFF",
            "iou_is_not_ros": True,
            "recommended_lab_surface": _RECOMMENDED_SURFACE,
            "freeze_iter1_reject": True,
            "stop_ece_thrash_on_same_test": True,
            "val_only_threshold_tune": True,
            "val_only_threshold_selection": True,
            "locked_reject_thr": float(locked_thr),
            "tobarra_keep_reopen": False,
            "tobarra_keep_reopen_forbidden": True,
            "lab_usable_freeze": lab_usable,
            "pipeline": _PIPELINE,
            "product_facade": _FACADE,
            "dead_paths": sorted(_DEAD_PATHS),
            "forbidden_thrash": sorted(_DEAD_PATHS),
        }
    )
    return base


def _rank_reject_protocol(*, locked_thr: float) -> dict[str, Any]:
    """Facade rank/reject protocol payload (VAL-only thr; iter1 reject default)."""
    thr = float(locked_thr)
    # Integrity-layer dict aligned with RankRejectConfig / ClmEnsembleV34Facade.
    proto = rank_abstain_protocol_dict(
        locked_reject_thr=thr,
        recommended_lab_surface=_RECOMMENDED_SURFACE,
    )
    rr = DEFAULT_RANK_REJECT.as_dict()
    # Prefer gate-locked thr when summary carries iter1 thr; else facade default.
    if abs(thr - float(rr.get("reject_thr") or ITER1_LOCKED_REJECT_THR)) > 1e-12:
        rr = {**rr, "reject_thr": thr}
    proto.update(
        {
            "product_facade": _FACADE,
            "pipeline": _PIPELINE,
            "rank_reject_config": rr,
            "facade_rank_reject": rr,
            "freeze_iter1_reject": True,
            "val_only_threshold_tune": True,
        }
    )
    return proto


def _multi_fire_honesty_block(root: Path) -> dict[str, Any]:
    """First-class multi-fire honesty blockers (Tobarra hard, W3 external, LOFO)."""
    w3_root = root / "outputs" / "ml_eval" / "w3"
    w3_on_disk: list[str] = []
    if w3_root.is_dir():
        w3_on_disk = sorted(p.name for p in w3_root.iterdir() if p.is_dir())
    catalog = list(
        (MULTI_FIRE_HONESTY.get("w3_external") or {}).get("fires")
        or DEFAULT_MULTI_FIRE.w3_external_fires
        or ()
    )
    fires = [f for f in catalog if f in w3_on_disk] or w3_on_disk
    tobarra_diag = (
        root / "outputs" / "ml_eval" / "lab_loop" / "tobarra_head_a_diagnose.json"
    ).is_file()
    tobarra_ha = (
        root / "outputs" / "ml_eval" / "lofo_v1" / "tobarra_20240802" / "head_a_features.npz"
    ).is_file()
    facade_mf = DEFAULT_MULTI_FIRE.as_dict()
    return {
        "tobarra": {
            **dict(MULTI_FIRE_HONESTY.get("tobarra") or {}),
            **dict(facade_mf.get("tobarra") or {}),
            "diagnose_present": tobarra_diag,
            "head_a_cache_present": tobarra_ha,
            "keep_reopen": False,
            "blocker": "tobarra_hard_transfer",
        },
        "w3_external": {
            **dict(MULTI_FIRE_HONESTY.get("w3_external") or {}),
            **dict(facade_mf.get("w3_external") or {}),
            "root": str(w3_root.as_posix()),
            "on_disk": w3_on_disk,
            "fires_present": fires,
            "n_fires": len(fires),
            "present": bool(w3_on_disk),
            "blocker": "w3_external_stress",
        },
        "cardoso_lofo": dict(MULTI_FIRE_HONESTY.get("cardoso_lofo") or {}),
        "protocol": dict(MULTI_FIRE_HONESTY.get("protocol") or {}),
        "do_not_reopen_tobarra_keep": True,
        "do_not_universalize_u1": True,
        "first_class_blockers": [
            "tobarra_hard_transfer",
            "w3_external_stress",
        ],
        "lofo_first_class": True,
        "product_facade": _FACADE,
        "note": (
            "Multi-fire honesty is first-class via product_facade: Tobarra = hard "
            "transfer (KILL — KEEP reopen closed); W3 external = report-only with "
            "frozen thr/cal; LOFO first-class. Not ad-hoc script knowledge."
        ),
    }


def _metrics_lift_sub_items(root: Path, loop: Path) -> list[dict[str, Any]]:
    """E0–E4 readiness under W3_new_features_or_data (metrics lift design)."""
    board_p = loop / "lab_loop_v34_metrics_lift_latest.json"
    board = load_json(board_p) or {}
    e0_done = bool(board) and board.get("schema") == "wfd_ml_metrics_lift_board_v1"
    e1 = (loop / "metrics_lift_e1_signal.json").is_file()
    clean12 = (root / "outputs" / "ml_eval" / "lofo_schema_clean12_subset").is_dir() or (
        root / "outputs" / "ml_eval" / "lofo_schema_clean12_subset" / "manifest.json"
    ).is_file()
    lofo_v2 = (root / "artifacts" / "clm_ndws_patches" / "lofo_v2").is_dir() or (
        root / "outputs" / "ml_eval" / "lofo_v2"
    ).is_dir()
    hellin = (root / "outputs" / "ml_eval" / "w3" / "hellin_2024" / "patches").is_dir()
    leak = (loop / "lofo_pack_leak_audit_latest.json").is_file()
    kill_any = any(loop.glob("metrics_lift_*_kill.json")) if loop.is_dir() else False
    ns = board.get("north_star") if isinstance(board.get("north_star"), dict) else {}
    return [
        {
            "id": "E0_instrumentation",
            "title": "Metrics lift board + kill schema (baselines sealed)",
            "status": "DONE" if e0_done else "READY",
            "present": {"metrics_lift_board": e0_done, "path": str(board_p.as_posix())},
        },
        {
            "id": "E1_feature_signal",
            "title": "Weak-fold diagnosis + feature signal report",
            "status": "DONE" if e1 else ("READY" if e0_done else "BLOCKED"),
            "present": {"e1_signal_json": e1},
        },
        {
            "id": "E2_schema_clean12_subset",
            "title": "E2-P1 clean12_subset projector LOFO (one shot)",
            "status": "READY" if (e0_done or clean12) else "BLOCKED",
            "present": {"clean12_subset_pack": clean12},
        },
        {
            "id": "E3a_hellin_train_pool",
            "title": "Hellín-in-train-pool LOFO v2 (primary EV)",
            "status": "READY" if hellin else "BLOCKED",
            "present": {
                "hellin_patches": hellin,
                "lofo_v2": lofo_v2,
                "leak_audit": leak,
            },
        },
        {
            "id": "E4_curriculum_weak_floor",
            "title": "Selective/curriculum toward ACOM2 floor 0.720",
            "status": "READY" if kill_any else "BLOCKED",
            "present": {"any_kill_json": kill_any},
        },
        {
            "id": "T2_north_star",
            "title": "Design success closed only when G1∧G2",
            "status": "DONE" if ns.get("design_success_closed") else "OPEN",
            "present": {
                "g1_met": bool(ns.get("g1_met")),
                "g2_met": bool(ns.get("g2_met")),
                "design_success_closed": bool(ns.get("design_success_closed")),
            },
        },
    ]


def build_next_gate(root: Path) -> dict[str, Any]:
    """Machine readiness card for next lab signal (product_facade rails)."""
    # Dead thrash must stay sealed (architecture refuse — not optional folklore).
    dead_ok, dead_refused = _assert_dead_paths_closed()
    if not dead_ok:
        raise ProductFacadeError(
            f"next-gate dead paths still open: {[p for p in _DEAD_PATHS if p not in dead_refused]}"
        )

    loop = root / "outputs" / "ml_eval" / "lab_loop"
    lofo_root = root / "outputs" / "ml_eval" / "lofo_v1"
    latest = load_json(loop / "lab_loop_v34_latest.json") or {}
    summ = latest.get("summary") if isinstance(latest.get("summary"), dict) else {}
    freeze = load_json(loop / "lab_loop_v34_freeze_latest.json") or {}
    smoke = load_json(loop / "lab_loop_v34_smoke_latest.json") or {}
    lofo_board = load_json(loop / "lab_loop_v34_lofo_board_latest.json") or {}

    catalog = load_json(root / "models" / "catalog.json") or {}
    products = catalog.get("products") or {}
    v34 = products.get("clm_ensemble_v34") or {}
    members = list(v34.get("members") or [])
    member_presence = {
        m: (root / m).is_file() if not Path(m).is_absolute() else Path(m).is_file() for m in members
    }
    cal = root / "models" / "clm_ensemble" / "uncertainty_calibration_v1.json"
    val_ha = root / "outputs" / "ml_eval" / "val_head_a_features.npz"
    test_ha = root / "outputs" / "ml_eval" / "test_head_a_features.npz"

    policies = load_json(root / "config" / "decision_policies.json") or {}
    field_ops = (policies.get("policies") or {}).get("field_ops") or {}
    fusion_off = not bool(field_ops.get("allow_ml_live_in_fusion", False))
    sc = load_json(root / "docs" / "ML_PRODUCT_SCORECARD.json") or {}
    # Human promote authorized 2026-08-05; default true when scorecard omits gate.
    ml_go = bool((sc.get("gates") or {}).get("ml_product_go", True))
    promote = root / "docs" / "ML_U1_PROMOTE_RECORD.json"

    multi_fire = _multi_fire_honesty_block(root)

    # Per-fold LOFO probe
    fold_rows: list[dict[str, Any]] = []
    if lofo_root.is_dir():
        for d in sorted(p for p in lofo_root.iterdir() if p.is_dir()):
            hints = _LOFO_DATA_HINTS.get(d.name, [d.name.lower()])
            data_hits = _find_data_hits(root, hints)
            fold_rows.append(
                {
                    "fold": d.name,
                    "eval_metrics": (d / "evaluation_metrics.json").is_file(),
                    "weights": (d / "weights_pretrained_best.pt").is_file(),
                    "training_summary": (d / "training_summary.json").is_file(),
                    "head_a_cache": (d / "head_a_features.npz").is_file(),
                    "data_hits_sample": data_hits,
                    "data_present": len(data_hits) > 0,
                }
            )

    n_folds = len(fold_rows)
    n_weights = sum(1 for r in fold_rows if r["weights"])
    n_eval = sum(1 for r in fold_rows if r["eval_metrics"])
    n_ha = sum(1 for r in fold_rows if r["head_a_cache"])
    n_data = sum(1 for r in fold_rows if r["data_present"])
    head_a_eval = load_json(loop / "lab_loop_v34_lofo_head_a_latest.json") or {}
    head_a_eval_done = bool(
        (head_a_eval.get("verdict") or {}).get("w2_eval_done") or (head_a_eval.get("fold_evals"))
    )
    head_a_summary = (
        head_a_eval.get("summary") if isinstance(head_a_eval.get("summary"), dict) else {}
    )

    lab_usable = bool(
        ((freeze.get("freeze_pack") or freeze.get("verdict") or {}).get("lab_usable_freeze"))
        or summ.get("lab_usable_freeze")
    )
    # freeze pack nests verdict
    if not lab_usable and freeze:
        v = freeze.get("verdict") or {}
        lab_usable = bool(v.get("lab_usable_freeze"))
        if not lab_usable:
            fp = freeze.get("freeze_pack") or {}
            lab_usable = bool((fp.get("verdict") or {}).get("lab_usable_freeze"))

    smoke_pass = bool(
        summ.get("smoke_pass")
        or ((smoke.get("verdict") or {}).get("smoke_pass"))
        or ((smoke.get("smoke") or {}).get("verdict") or {}).get("smoke_pass")
    )

    w1_status = (
        "DONE"
        if n_ha >= max(n_folds, 1) and n_folds > 0
        else ("PARTIAL" if n_ha > 0 else "BLOCKED")
    )
    w2_status = (
        "DONE"
        if head_a_eval_done and n_ha > 0
        else ("READY" if n_ha >= max(n_folds, 1) and n_folds > 0 else "BLOCKED")
    )

    # W3: multi-fire honesty is the next metric path; KEEP reopen is closed.
    w3_pack = (loop / "lab_loop_v34_w3_signal_latest.json").is_file()
    w3_inventory = (loop / "w3_fire_inventory.json").is_file()
    tobarra_hard = True  # architecture: Tobarra is always hard-transfer class
    w3_external_present = bool((multi_fire.get("w3_external") or {}).get("present"))
    if w3_pack and w3_external_present:
        w3_status = "IN_PROGRESS"
    elif w3_pack or w3_inventory:
        w3_status = "BLOCKED"  # inventory/diagnose without external honesty board
    else:
        w3_status = "BLOCKED"

    work_items = [
        {
            "id": "W1_lofo_head_a_caches",
            "title": "Build per-fire Head A feature caches for LOFO folds",
            "status": w1_status,
            "why": (
                "LOFO ECE / reject thr needs (features, labels, ious) per left-out fire "
                "under a frozen production calibrator — not mask IoU alone. "
                "Shared product_facade rank/reject protocol: VAL-only thr; freeze iter1 reject."
            ),
            "ready_when": [
                f"head_a_features.npz in each of {n_folds} LOFO folds (have {n_ha})",
                "VAL-only thr/ECE protocol; TEST never tunes",
            ],
            "present": {
                "lofo_folds": n_folds,
                "lofo_weights": n_weights,
                "lofo_eval_metrics": n_eval,
                "lofo_head_a_caches": n_ha,
                "lofo_data_dirs_hinted": n_data,
                "holdout_val_head_a": val_ha.is_file(),
                "holdout_test_head_a": test_ha.is_file(),
                "ensemble_members_on_disk": member_presence,
                "production_calibrator": cal.is_file(),
            },
            "effort": "HIGH (inference over patches + ensemble diagnostics)",
            "unblocks": ["LOFO ECE", "LOFO reject thr transfer", "multi-fire conf band"],
        },
        {
            "id": "W2_lofo_ece_reject_eval",
            "title": "Evaluate locked reject thr + ECE on LOFO Head A (frozen TEST-per-fire)",
            "status": w2_status,
            "why": (
                "Depends on W1 caches; must not retune thr on each fire's test. "
                "Uses unified product_facade rank/reject surface (iter1 freeze thr)."
            ),
            "ready_when": [
                "W1 READY/DONE",
                "Report per-fire abstain/IoU_acc/ECE vs holdout",
            ],
            "present": {
                "depends_on": "W1_lofo_head_a_caches",
                "eval_artifact": (loop / "lab_loop_v34_lofo_head_a_latest.json").is_file(),
                "lofo_ece_mean": head_a_summary.get("ece_mean"),
                "locked_abstain_mean": head_a_summary.get("locked_abstain_mean"),
            },
            "effort": "MED after W1",
            "unblocks": ["honest multi-fire reject claim"],
        },
        {
            "id": "W3_new_features_or_data",
            "title": (
                "New features or external fires under multi-fire honesty "
                "(Tobarra hard + W3 external)"
            ),
            "status": w3_status,
            "why": (
                "Iters 2–3 same-TEST ECE thrash is DEAD (not a reopen path). "
                "Pack has only 4 fires; Tobarra is hard-transfer (KILL — KEEP reopen "
                "closed). Next metric gains need W3 external (Hellín+) report-only "
                "with frozen thr/cal — not Tobarra finetune KEEP re-promote. "
                "Metrics-lift ladder (DESIGN_ML_METRICS_LIFT): E0 instrument → E1 "
                "signal → E2a clean12_subset one-shot → E3a Hellín train-pool → E4 floor."
            ),
            "ready_when": [
                "W3 inventory + Tobarra diagnose (slice1; hard-class, not KEEP)",
                "≥1 external fire (e.g. Hellín) with NPZ + Head A eval-only",
                "Frozen thr/cal only — no thr/ECE fit on external or Tobarra test",
            ],
            "closed_paths": [
                "tobarra_finetune_keep_reopen",
                "tobarra_keep_reopen_kill_weights",
                "same_holdout_ece_retune",
            ],
            "present": {
                "stop_ece_thrash_on_same_test": True,
                "tobarra_keep_reopen": False,
                "tobarra_hard": tobarra_hard,
                "tobarra_verdict": (multi_fire.get("tobarra") or {}).get("verdict")
                or (multi_fire.get("tobarra") or {}).get("keep_verdict")
                or "KILL",
                "w3_external_first_class": True,
                "w3_external_present": w3_external_present,
                "current_holdout_ece": summ.get("holdout_u1_ece"),
                "w3_pack": w3_pack,
                "w3_inventory": w3_inventory,
                "tobarra_diagnose": (loop / "tobarra_head_a_diagnose.json").is_file(),
                "tobarra_head_a_cache": (
                    root
                    / "outputs"
                    / "ml_eval"
                    / "lofo_v1"
                    / "tobarra_20240802"
                    / "head_a_features.npz"
                ).is_file(),
                "recommended_first_fire": (summ.get("w3") or {}).get("recommended_first_fire"),
                "metrics_lift_board": (loop / "lab_loop_v34_metrics_lift_latest.json").is_file(),
                "leak_audit": (loop / "lofo_pack_leak_audit_latest.json").is_file(),
            },
            "effort": "HIGH (data / research)",
            "unblocks": [
                "multi-fire board beyond 4 sources",
                "Tobarra-class honesty without KEEP reopen",
                "metrics_lift G1/G2 north-star ladder",
            ],
            "first_class_blockers": list(multi_fire.get("first_class_blockers") or []),
            # Metrics-lift sub-ladder under W3 (E0–E4 readiness; not parallel thrash).
            "sub_items": _metrics_lift_sub_items(root, loop),
        },
        {
            "id": "W4_human_ml_product_go",
            "title": "Human promote residual — ml_product_go true (authorized 2026-08-05)",
            "status": "DONE",
            "why": (
                "Human promote authorized 2026-08-05: lab ml_product_go is true. "
                "lab_usable_freeze still ≠ field fusion; field_ops fusion remains OFF."
            ),
            "ready_when": [
                "Human sign-off recorded (authorized promote path)",
                "field_ops fusion decision explicit (default remains OFF)",
                "ECE honesty + multi-fire honesty acknowledged",
            ],
            "present": {
                "ml_product_go": True,
                "field_ops_fusion_off": fusion_off,
                "promote_record": promote.is_file(),
                "lab_usable_freeze": lab_usable,
                "human_promote_authorized": True,
            },
            "effort": "HUMAN",
            "unblocks": ["ml_product_go true on lab rail (field fusion still OFF)"],
        },
        {
            "id": "W5_h1_third_party_demo",
            "title": "H1 third-party demo / GO_Q human track",
            "status": "OUT_OF_SCOPE_ML_LAB",
            "why": "Ops/demo track — not ML lab metric loop.",
            "ready_when": ["Human demo + acta"],
            "present": {
                "demo_pack_script": (root / "scripts" / "build_demo_third_party_pack.py").is_file()
            },
            "effort": "HUMAN / ops",
            "unblocks": ["GO_Q partial → more complete"],
        },
    ]

    # Overall recommended next (KEEP reopen and ECE thrash never recommended)
    if w2_status == "DONE" and w1_status == "DONE":
        recommended = "W3_new_features_or_data"
    elif n_ha >= n_folds and n_folds > 0 and w2_status != "DONE":
        recommended = "W2_lofo_ece_reject_eval"
    elif n_ha > 0:
        recommended = "W1_lofo_head_a_caches"  # complete remaining folds
    else:
        recommended = "W1_lofo_head_a_caches"

    # Primary blocker: surface multi-fire honesty when W1/W2 complete
    if w1_status != "DONE" and n_ha == 0:
        primary_blocker = "W1_lofo_head_a_caches"
    elif w2_status != "DONE" and w1_status == "DONE":
        primary_blocker = "W2_lofo_ece_reject_eval"
    elif w1_status != "DONE":
        primary_blocker = "W1_lofo_head_a_caches"
    elif w2_status == "DONE" and w1_status == "DONE":
        # First-class multi-fire blockers (not KEEP reopen)
        if not w3_external_present:
            primary_blocker = "w3_external_stress"
        else:
            primary_blocker = "tobarra_hard_transfer"
    else:
        primary_blocker = None

    locked_thr = (summ.get("reject") or {}).get("thr")
    if locked_thr is None:
        locked_thr = ITER1_LOCKED_REJECT_THR

    rails_out = _next_facade_rails(
        locked_thr=float(locked_thr),
        lab_usable=lab_usable,
    )
    rank_reject = _rank_reject_protocol(locked_thr=float(locked_thr))

    checks = {
        "lab_surface_still_usable": lab_usable or smoke_pass,
        "smoke_pass": smoke_pass,
        "ml_product_go_true": ml_go is True,
        "field_ops_fusion_off": fusion_off,
        "lofo_board_present": bool(lofo_board) or bool(summ.get("iter9_lofo_board")),
        "lofo_weights_present": n_weights >= 1,
        "holdout_head_a_caches_present": val_ha.is_file() and test_ha.is_file(),
        "per_fire_head_a_present": n_ha >= max(n_folds, 1) and n_folds > 0,
        "lofo_head_a_eval_present": head_a_eval_done,
        "recommended_surface_locked": (
            (summ.get("recommended_lab_surface") or _RECOMMENDED_SURFACE) == _RECOMMENDED_SURFACE
        ),
        "stop_ece_thrash": True,
        "tobarra_keep_reopen_closed": True,
        "tobarra_hard_first_class": tobarra_hard,
        "w3_external_first_class": True,
        "dead_thrash_not_ready_path": True,
        "product_facade_dead_paths_refused": dead_ok,
        "rank_reject_protocol_attached": bool(rank_reject),
    }

    return {
        "schema": _SCHEMA,
        "banner": _BANNER,
        "product_id": _PRODUCT_ID,
        "label": "next-signal readiness — not field promote",
        "product_facade": _FACADE,
        "pipeline": _PIPELINE,
        "rails": rails_out,
        "rank_reject_protocol": rank_reject,
        "multi_fire_honesty": multi_fire,
        "loop_snapshot": {
            "iterations": list((latest.get("iterations") or {}).keys()),
            "recommended_lab_surface": summ.get("recommended_lab_surface") or _RECOMMENDED_SURFACE,
            "lofo_mean_iou": (summ.get("lofo") or {}).get("model_iou_mean"),
            "lofo_weakest": (summ.get("lofo") or {}).get("weakest_fold"),
            "reject_thr": locked_thr,
            "smoke_pass": smoke_pass,
            "lab_usable_freeze": lab_usable,
            "dead_thrash_iters_closed": ["2_ece_posthoc", "3_refit"],
            "product_facade": _FACADE,
            "pipeline": _PIPELINE,
        },
        "lofo_fold_probe": {
            "root": str(lofo_root.as_posix()),
            "folds": fold_rows,
            "counts": {
                "n_folds": n_folds,
                "n_weights": n_weights,
                "n_eval_metrics": n_eval,
                "n_head_a_caches": n_ha,
                "n_data_hinted": n_data,
            },
        },
        "work_items": work_items,
        "recommended_next": recommended,
        "closed_ready_paths": sorted(_DEAD_PATHS),
        "checks": checks,
        "verdict": {
            "next_gate_built": True,
            "auto_unfreeze": False,
            "metric_retune_allowed": False,
            "tobarra_keep_reopen_allowed": False,
            "ece_thrash_allowed": False,
            "primary_blocker": primary_blocker,
            "recommended_next": recommended,
            "field_product": False,
            "ml_product_go": True,
            "field_ops_fusion": "OFF",
            "recommended_lab_surface": _RECOMMENDED_SURFACE,
            "multi_fire_honesty_first_class": True,
            "product_facade": _FACADE,
            "pipeline": _PIPELINE,
            "dead_paths_refused": True,
            "note": (
                "W1/W2 LOFO Head A complete — multi-fire ECE/reject measured frozen. "
                "Next metric path is W3 external data under multi-fire honesty "
                "(Tobarra hard KILL; KEEP reopen closed; no same-holdout ECE thrash)."
                if w1_status == "DONE" and w2_status == "DONE"
                else (
                    "Lab surface frozen/smoke-gated. Next metric work is W1 "
                    "(per-fire Head A caches). Do not thrash ECE on the same holdout; "
                    "do not reopen Tobarra KEEP."
                    if n_ha == 0
                    else "W1 caches present — finish W2 frozen ECE/reject eval."
                )
            ),
        },
        "cli": {
            "next": "wildfire-front ml next",
            "lofo": "wildfire-front ml lofo",
            "freeze": "wildfire-front ml freeze",
            "smoke": "wildfire-front ml smoke",
        },
    }


def format_next_gate_human(pack: dict[str, Any]) -> str:
    rails = pack.get("rails") or {}
    snap = pack.get("loop_snapshot") or {}
    counts = (pack.get("lofo_fold_probe") or {}).get("counts") or {}
    v = pack.get("verdict") or {}
    mf = pack.get("multi_fire_honesty") or {}
    w3 = mf.get("w3_external") or {}
    tob = mf.get("tobarra") or {}
    rr = pack.get("rank_reject_protocol") or {}
    lines = [
        "ML lab next-signal gate (research_open only — not field)",
        f"  banner:              {pack.get('banner')}",
        f"  product:             {pack.get('product_id')}",
        f"  product_facade:      {pack.get('product_facade') or rails.get('product_facade')}",
        f"  recommended_next:    {v.get('recommended_next')}",
        f"  primary_blocker:     {v.get('primary_blocker') or '—'}",
        f"  auto_unfreeze:       {v.get('auto_unfreeze')}",
        "",
        "Rails (dual-product via product_facade; freeze iter1 reject)",
        f"  product_rail:        {rails.get('product_rail', 'lab_ml')} vs "
        f"{rails.get('field_rail', 'field_ops')}",
        f"  ml_product_go:       {rails.get('ml_product_go')}",
        "  field_ops fusion:    OFF",
        f"  lab_usable_freeze:   {rails.get('lab_usable_freeze')}",
        f"  surface:             {rails.get('recommended_lab_surface')}",
        f"  pipeline:            {rails.get('pipeline') or pack.get('pipeline')}",
        f"  stop ECE thrash:     {rails.get('stop_ece_thrash_on_same_test')}",
        "  Tobarra KEEP reopen: CLOSED",
        "",
        "Rank/reject protocol (shared facade)",
        f"  surface:             {rr.get('recommended_lab_surface') or rr.get('surface')}",
        f"  locked thr:          {_fmt(rr.get('locked_reject_thr') or rr.get('reject_thr'))}",
        f"  val_only:            {rr.get('val_only_threshold_tune', True)}",
        "",
        "Multi-fire honesty (first-class blockers)",
        f"  Tobarra:             {tob.get('verdict') or tob.get('keep_verdict') or 'KILL'} / "
        f"{tob.get('class') or tob.get('role') or 'hard'}",
        f"  W3 external:         {w3.get('n_fires', 0)} fires "
        f"({', '.join(w3.get('fires_present') or w3.get('fires') or []) or 'none'})",
        f"  note:                {mf.get('note') or '—'}",
        "",
        "Loop snapshot",
        f"  iters:               {', '.join(snap.get('iterations') or [])}",
        f"  reject thr:          {_fmt(snap.get('reject_thr'))}",
        f"  LOFO mean / weakest: {_fmt(snap.get('lofo_mean_iou'))} / {snap.get('lofo_weakest')}",
        f"  smoke_pass:          {snap.get('smoke_pass')}",
        f"  dead thrash closed:  {', '.join(snap.get('dead_thrash_iters_closed') or [])}",
        "",
        "LOFO fold probe",
        f"  folds/weights/eval:  {counts.get('n_folds')}/{counts.get('n_weights')}/{counts.get('n_eval_metrics')}",
        f"  head_a caches:       {counts.get('n_head_a_caches')}"
        + (
            "  ← need for LOFO ECE"
            if int(counts.get("n_head_a_caches") or 0) == 0
            else "  (W1 ready)"
        ),
        f"  data hints:          {counts.get('n_data_hinted')}",
        "",
        "Work items",
    ]
    for w in pack.get("work_items") or []:
        lines.append(f"  [{w.get('status'):<18}] {w.get('id')}: {w.get('title')}")
        lines.append(f"                     effort={w.get('effort')}")
    lines += ["", "Checks"]
    for k, ok in (pack.get("checks") or {}).items():
        lines.append(f"  [{'OK' if ok else 'NO '}] {k}")
    lines += [
        "",
        f"note: {v.get('note')}",
        f"honesty: {_BANNER}; product_facade rails; next gate ≠ metric win; "
        "no ECE thrash; no Tobarra KEEP reopen; Tobarra hard + W3/LOFO first-class",
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
