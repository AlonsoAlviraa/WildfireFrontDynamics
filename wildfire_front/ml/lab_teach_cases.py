"""Lab teach-cases surface: fail buckets + loop board for teaching (not field product).

Consumes the unified lab product path (architecture only — no retrain)::

    features → calibrator → rank/reject → scorecard
    (``product_facade`` + ``rank_reject_protocol``)

* Dual-product rails via ``product_facade``: lab ML vs field_ops; IoU ≠ ROS;
  ``ml_product_go`` default **True** (human promote 2026-08-05); never auto-flips;
  field fusion OFF (lab GO ≠ field fusion).
* Shared rank / reject / LOFO surface: VAL-only thr; freeze **iter1 reject**
  as default (``DEFAULT_RANK_REJECT`` / ``rank_reject_protocol``).
* Multi-fire honesty first-class (Tobarra hard, W3 external / LOFO) — not ad-hoc.
* Dead thrash closed via ``product_facade.refuse_dead_path``: same-holdout ECE
  retune, Tobarra KEEP reopen of KILL weights.
* Field fusion stays OFF. Teach ≠ field dispatch.

Rails / rank-reject ownership: ``product_facade`` + ``rank_reject_protocol``.
``protocol_rails`` supplies integrity thrash ids / banner only. This module is
the teach pack, not a second conf/rank implementation.
"""

from __future__ import annotations

import json
from collections import Counter
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
_SCHEMA: Final = "wfd_ml_teach_cases_v1"
_PRODUCT_ID: Final = DEFAULT_PRODUCT_ID
_RECOMMENDED_SURFACE: Final = RECOMMENDED_LAB_SURFACE  # iter1_reject_only
_FACADE: Final = "wildfire_front.ml.product_facade"
_FACADE_CLASS: Final = "ClmEnsembleV34Facade"
_PIPELINE: Final = "features→calibrator→rank/reject→scorecard"
_RANK_REJECT_PROTOCOL: Final = "wildfire_front.ml.rank_reject_protocol"

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

_BUCKET_TEACH = {
    "accepted_low_iou": (
        "High conf accepted the patch but IoU is weak — overconfidence risk "
        "(why thr alone is not enough; ECE residual ~0.15)."
    ),
    "rejected_high_iou": (
        "Rejected (conf below thr) despite high IoU — conservative false reject "
        "trade-off of thr~0.80 reject surface."
    ),
}


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def summarize_fail_cases(fail: dict[str, Any] | None) -> dict[str, Any]:
    if not fail:
        return {"present": False, "n_rows": 0, "buckets": {}, "examples": []}
    rows = fail.get("rows") or []
    if not isinstance(rows, list):
        rows = []
    counts = Counter(str(r.get("bucket") or "unknown") for r in rows if isinstance(r, dict))
    examples: list[dict[str, Any]] = []
    seen: set[str] = set()
    for r in rows:
        if not isinstance(r, dict):
            continue
        b = str(r.get("bucket") or "unknown")
        if b in seen:
            continue
        seen.add(b)
        examples.append(
            {
                "bucket": b,
                "index": r.get("index"),
                "conf": r.get("conf"),
                "iou": r.get("iou"),
                "teach": _BUCKET_TEACH.get(
                    b, "Edge case for lab teaching — not a field dispatch rule."
                ),
            }
        )
    return {
        "present": True,
        "n_rows": len(rows),
        "threshold": fail.get("threshold"),
        "label": fail.get("label") or "lab teaching only",
        "buckets": dict(sorted(counts.items())),
        "examples": examples,
        "bucket_teach": {k: _BUCKET_TEACH[k] for k in _BUCKET_TEACH if k in counts},
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
            "rank_reject_protocol": _RANK_REJECT_PROTOCOL,
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


def teach_facade_rails(
    rails: ProductRails | None = None,
    *,
    locked_reject_thr: float | None = None,
    recommended_surface: str | None = None,
    stop_ece_thrash: bool = True,
) -> dict[str, Any]:
    """Canonical dual-product rails via product_facade (teach pack; no auto-flip).

    Asserts facade rails (fusion OFF, ml_product_go true after human promote
    2026-08-05, iter1 reject surface). Lab GO ≠ field fusion.
    """
    r = assert_lab_rails(rails or DEFAULT_RAILS)
    thr = float(ITER1_LOCKED_REJECT_THR if locked_reject_thr is None else locked_reject_thr)
    surface = str(recommended_surface or _RECOMMENDED_SURFACE)
    base = r.as_dict()
    base.update(
        {
            "banner": _BANNER,
            "product_rail": "lab_ml",
            "field_rail": "field_ops",
            "field_ops_ml_live_fusion": "OFF",
            "ml_product_go": True,
            "val_only_threshold_tune": True,
            "val_only_threshold_selection": True,
            "locked_reject_thr": thr,
            "recommended_lab_surface": surface,
            "stop_ece_thrash_on_same_test": bool(stop_ece_thrash),
            "tobarra_keep_reopen": False,
            "tobarra_keep_reopen_forbidden": True,
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


def teach_rank_reject_surface(
    *,
    locked_reject_thr: float | None = None,
    recommended_surface: str | None = None,
) -> dict[str, Any]:
    """ClmEnsembleV34Facade rank/reject surface for teach pack (no retrain).

    Documents the single product path features→calibrator→rank/reject→scorecard
    with VAL-only thr frozen at iter1 reject. Does not load a calibrator.
    """
    thr = float(ITER1_LOCKED_REJECT_THR if locked_reject_thr is None else locked_reject_thr)
    surface = str(recommended_surface or _RECOMMENDED_SURFACE)
    cfg = DEFAULT_RANK_REJECT
    return {
        "facade_class": _FACADE_CLASS,
        "product_facade": _FACADE,
        "product_id": _PRODUCT_ID,
        "pipeline": _PIPELINE,
        "rank_reject_protocol": _RANK_REJECT_PROTOCOL,
        "protocol_module": _RANK_REJECT_PROTOCOL,
        "recommended_lab_surface": surface,
        "locked_reject_thr": thr,
        "reject_thr": thr,
        "surface": surface,
        "thr_tune_split": "val",
        "val_only_threshold_selection": True,
        "freeze_iter1_reject": True,
        "rank_score_name": cfg.rank_score_name,
        "selective_coverage": float(cfg.selective_coverage),
        "rank_reject": {
            **cfg.as_dict(),
            "reject_thr": thr,
            "surface": surface,
        },
        "ml_product_go": True,
        "field_ops_allow_ml_live_in_fusion": False,
        "iou_is_not_ros": True,
        "note": (
            "Teach pack seals ClmEnsembleV34Facade iter1_reject_only surface; "
            "ranking and thr-reject share conf via rank_reject_protocol "
            "(features→calibrator→rank/reject→scorecard)."
        ),
    }


def build_teach_cases_pack(root: Path) -> dict[str, Any]:
    """Offline pack for ``ml cases`` and loop iter5.

    Consumes unified product_facade + rank_reject_protocol path (iter1 freeze,
    VAL-only thr, multi-fire honesty). Does not retune ECE or flip field rails.
    """
    loop_dir = root / "outputs" / "ml_eval" / "lab_loop"
    fail_path = loop_dir / "lab_loop_v34_fail_cases_test.json"
    latest_path = loop_dir / "lab_loop_v34_latest.json"
    gen_path = loop_dir / "lab_loop_v34_generalization_latest.json"
    reject_path = loop_dir / "lab_loop_v34_reject_latest.json"

    fail = load_json(fail_path)
    latest = load_json(latest_path) or {}
    gen = load_json(gen_path) or {}
    reject = load_json(reject_path) or {}
    summ = latest.get("summary") if isinstance(latest.get("summary"), dict) else {}
    rej_lock = summ.get("reject") or {}
    if not rej_lock and reject:
        tuned = reject.get("tuned") or {}
        tm = tuned.get("test_metrics_tuned") or {}
        rej_lock = {
            "thr": tuned.get("abstain_threshold"),
            "test_abstain_rate": tm.get("abstain_rate"),
            "test_iou_accepted": tm.get("mean_iou_accepted"),
        }
    locked_thr = rej_lock.get("thr")
    if locked_thr is None:
        locked_thr = ITER1_LOCKED_REJECT_THR
    locked_thr = float(locked_thr)
    surface = summ.get("recommended_lab_surface") or _RECOMMENDED_SURFACE
    stop_ece = bool(summ.get("stop_ece_thrash_on_same_test", True))
    lofo = summ.get("lofo") or (gen.get("lofo") or {}).get("summary") or {}
    fail_sum = summarize_fail_cases(fail)

    # Single product path: product_facade rails + rank_reject_protocol surface.
    rank_reject = teach_rank_reject_surface(
        locked_reject_thr=locked_thr,
        recommended_surface=str(surface),
    )
    rails = teach_facade_rails(
        locked_reject_thr=locked_thr,
        recommended_surface=str(surface),
        stop_ece_thrash=stop_ece,
    )
    multi_fire = _multi_fire_honesty_block()
    dead_paths_status = _assert_dead_paths_closed()

    talking_points = [
        "Default thr=0.35 never rejects — conf lives ~0.74–0.81; lab thr~0.80 enables ABSTAIN.",
        "Accepted low-IoU patches show overconfidence; rejected high-IoU is the thr cost.",
        f"LOFO mean IoU ~{lofo.get('model_iou_mean', '—')} (n={lofo.get('n_folds', '—')}) "
        f"vs U1 holdout ~{summ.get('holdout_u1_iou', '—')} — do not universalize one holdout.",
        "ECE post-hoc/refit did not improve TEST (iter2/3) — stop thrashing same holdout.",
        "IoU is mask overlap lab metric — never ROS / m·min⁻¹.",
        "ml_product_go true (human promote 2026-08-05) · field_ops fusion OFF "
        "— lab GO ≠ field fusion.",
        "Rank + reject share one VAL-only thr protocol via product_facade "
        "(features→calibrator→rank/reject→scorecard); freeze iter1 reject as default.",
        "Tobarra = hard transfer (KILL); W3 external = frozen thr/cal report only.",
    ]

    script = [
        "python -m wildfire_front ml list",
        "python -m wildfire_front ml show",
        "python -m wildfire_front ml cases",
        "python -m wildfire_front ml cases --bucket accepted_low_iou",
        "python -m wildfire_front ml card --mode offline --scenario abstain",
        "Explain thr~0.80 vs 0.35 using fail buckets",
        "Explain LOFO vs U1 without collapsing protocols",
        "Explain Tobarra hard / W3 external without reopening KEEP or ECE thrash",
    ]

    return {
        "schema": _SCHEMA,
        "banner": _BANNER,
        "label": "lab / research_open only — not field product",
        "product_id": _PRODUCT_ID,
        "product_facade": _FACADE,
        "facade_class": _FACADE_CLASS,
        "pipeline": _PIPELINE,
        "rails": rails,
        "rank_reject_protocol": rank_reject,
        "multi_fire_honesty": multi_fire,
        "dead_paths_status": dead_paths_status,
        "locked_reject": {
            "thr": locked_thr,
            "thr_value": locked_thr,
            "test_abstain_rate": rej_lock.get("test_abstain_rate") or rej_lock.get("abstain_rate"),
            "test_iou_accepted": rej_lock.get("test_iou_accepted") or rej_lock.get("iou_accepted"),
            "surface": surface,
            "val_only_threshold_tune": True,
            "freeze_iter1_reject": True,
            "product_facade": _FACADE,
            "pipeline": _PIPELINE,
        },
        "lofo": {
            "n_folds": lofo.get("n_folds"),
            "model_iou_mean": lofo.get("model_iou_mean"),
            "model_iou_std": lofo.get("model_iou_std"),
            "spread_max_minus_min": lofo.get("spread_max_minus_min"),
            "generalization_note": summ.get("generalization_note")
            or (gen.get("lofo") or {}).get("generalization_note"),
            "honesty": ("LOFO mask IoU ≠ U1 Head A ECE protocol — never mix as one number."),
            "lofo_is_not_u1_ece": True,
            "lofo_w3_first_class": True,
        },
        "holdout": {
            "u1_mean_iou": summ.get("holdout_u1_iou"),
            "u1_ece": summ.get("holdout_u1_ece"),
        },
        "fail_cases": fail_sum,
        "paths": {
            "fail_cases": "outputs/ml_eval/lab_loop/lab_loop_v34_fail_cases_test.json",
            "latest": "outputs/ml_eval/lab_loop/lab_loop_v34_latest.json",
            "generalization": "outputs/ml_eval/lab_loop/lab_loop_v34_generalization_latest.json",
            "course": "docs/CURSO_WFD_PARA_DESCONOCIDOS.md",
            "cheatsheet": "docs/CHEATSHEET_ML_LAB.md",
            "product_facade": _FACADE,
            "rank_reject_protocol": _RANK_REJECT_PROTOCOL,
        },
        "talking_points": talking_points,
        "demo_script": script,
        "do_not": [
            "Auto-flip ml_product_go (silent thrash; explicit promote allowed)",
            "Turn field_ops.allow_ml_live_in_fusion ON",
            "Say IoU = ROS / m·min⁻¹",
            "Universalize U1 holdout IoU across fires (LOFO / Tobarra hard)",
            "Re-tune ECE post-hoc on the same TEST holdout",
            "Re-open Tobarra KEEP with same recipe / re-promote KILL weights",
            "Treat thr=0.35 as a working mask reject",
            "Collapse LOFO mask IoU with U1 Head A ECE into one number",
            "Bypass product_facade / rank_reject_protocol for conf or thr",
        ],
        "iterations": latest.get("iterations") or {},
        "presence": {
            "fail_cases": fail_path.is_file(),
            "latest": latest_path.is_file(),
            "generalization": gen_path.is_file(),
        },
    }


def format_teach_cases_human(
    pack: dict[str, Any],
    *,
    bucket: str | None = None,
    limit: int = 5,
) -> str:
    """Human table for ``ml cases``."""
    fc = pack.get("fail_cases") or {}
    rej = pack.get("locked_reject") or {}
    lofo = pack.get("lofo") or {}
    hold = pack.get("holdout") or {}
    rails = pack.get("rails") or {}
    mf = pack.get("multi_fire_honesty") or {}
    rr = pack.get("rank_reject_protocol") or {}
    lines = [
        "ML lab teach cases (research_open / lab only — not field)",
        f"  banner:              {pack.get('banner')}",
        f"  product:             {pack.get('product_id')}",
        f"  pipeline:            {pack.get('pipeline') or _PIPELINE}",
        f"  product_facade:      {pack.get('product_facade') or rails.get('product_facade') or _FACADE}",
        f"  product_rail:        {rails.get('product_rail', 'lab_ml')} vs "
        f"{rails.get('field_rail', 'field_ops')}",
        f"  recommended surface: {rails.get('recommended_lab_surface')}",
        f"  ml_product_go:       {rails.get('ml_product_go')}",
        "  field_ops fusion:    OFF (rail)",
        f"  rank/reject thr:     {_fmt(rr.get('locked_reject_thr') or rr.get('reject_thr') or rej.get('thr'))} "
        f"(VAL-only; freeze iter1)",
        "",
        "Locked reject (iter1)",
        f"  thr:                 {_fmt(rej.get('thr_value') or rej.get('thr'))}",
        f"  abstain_rate:        {_fmt(rej.get('test_abstain_rate'))}",
        f"  IoU accepted:        {_fmt(rej.get('test_iou_accepted'))}",
        "",
        "Holdout vs LOFO (different protocols)",
        f"  U1 mean IoU:         {_fmt(hold.get('u1_mean_iou'))}",
        f"  U1 ECE:              {_fmt(hold.get('u1_ece'))}",
        f"  LOFO n_folds:        {lofo.get('n_folds') if lofo.get('n_folds') is not None else '—'}",
        f"  LOFO mean IoU:       {_fmt(lofo.get('model_iou_mean'))}",
        f"  LOFO spread:         {_fmt(lofo.get('spread_max_minus_min'))}",
        f"  note:                {lofo.get('generalization_note') or '—'}",
        "",
        "Multi-fire honesty (first-class)",
        f"  Tobarra:             {(mf.get('tobarra') or {}).get('verdict') or (mf.get('tobarra') or {}).get('keep_verdict') or 'hard/KILL'}",
        f"  W3 external:         {(mf.get('w3_external') or {}).get('role') or 'external_stress'}",
        f"  note:                {mf.get('note') or '—'}",
        "",
        "Fail-case buckets (TEST indices into Head A feature order)",
        f"  present:             {fc.get('present')}",
        f"  n_rows:              {fc.get('n_rows')}",
        f"  thr used in export:  {_fmt(fc.get('threshold'))}",
        f"  buckets:             {fc.get('buckets') or {}}",
        "",
    ]
    bt = fc.get("bucket_teach") or {}
    for b, text in bt.items():
        lines.append(f"  [{b}] {text}")
    lines.append("")

    examples = list(fc.get("examples") or [])
    # Optional: expand from full fail file is not in pack examples only one per bucket.
    # If bucket filter, show talking for that bucket only.
    if bucket:
        lines.append(f"Focus bucket: {bucket}")
        teach = _BUCKET_TEACH.get(bucket, "See fail_cases JSON for rows.")
        lines.append(f"  teach: {teach}")
        lines.append("")

    lines.append("Example row per bucket (first seen)")
    for ex in examples[: max(1, limit)]:
        if bucket and ex.get("bucket") != bucket:
            continue
        lines.append(
            f"  · {ex.get('bucket')}: idx={ex.get('index')} "
            f"conf={_fmt(ex.get('conf'))} iou={_fmt(ex.get('iou'))}"
        )
    lines.append("")
    lines.append("Talking points")
    for i, tp in enumerate(pack.get("talking_points") or [], 1):
        lines.append(f"  {i}. {tp}")
    lines.append("")
    lines.append("Demo script")
    for step in pack.get("demo_script") or []:
        lines.append(f"  $ {step}" if step.startswith("python") else f"  · {step}")
    lines.append("")
    do_not = pack.get("do_not") or []
    if do_not:
        lines.append("Do not")
        for d in do_not:
            lines.append(f"  · {d}")
        lines.append("")
    lines.append(
        f"honesty: {_BANNER}; fail cases are teaching indices only; "
        "LOFO ≠ U1 ECE; Tobarra hard; fusion OFF; "
        f"pipeline {_PIPELINE}"
    )
    lines.append("")
    return "\n".join(lines)


def filter_fail_rows(
    fail: dict[str, Any] | None,
    *,
    bucket: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    if not fail:
        return []
    rows = [r for r in (fail.get("rows") or []) if isinstance(r, dict)]
    if bucket:
        rows = [r for r in rows if str(r.get("bucket")) == bucket]
    return rows[: max(0, limit)]


def _fmt(v: Any, digits: int = 4) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):.{digits}f}"
    except (TypeError, ValueError):
        return str(v)
