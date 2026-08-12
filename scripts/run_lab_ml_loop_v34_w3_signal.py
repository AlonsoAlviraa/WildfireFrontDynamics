#!/usr/bin/env python3
"""Lab ML loop iter 13: W3 multi-fire honesty pack (architectural artifact).

Architecture (product ROI — no retrain)
---------------------------------------
* Dual-product rails: **lab ML** vs **field_ops**; IoU ≠ ROS;
  ``ml_product_go`` **true** (human promote 2026-08-05; no silent auto-flip);
  field fusion stays **OFF** (lab GO ≠ field fusion).
* Ranking / abstain share one protocol via ``product_facade`` +
  ``rank_reject_protocol``: VAL-only thr; freeze **iter1 reject** default
  (via ``w3_signal`` pack — no conf math here).
* Thr metrics authority: pack Tobarra diagnose **facade.scorecard only**
  (no parallel ``reject_locked`` thr copy in this runner).
* Multi-fire honesty first-class: Tobarra hard + W3 external fires
  (not a one-off inventory folklore script).
* Dead thrash closed: same-holdout ECE retune, Tobarra KEEP reopen of KILL weights;
  silent ``auto_ml_product_go`` refused (explicit promoted true allowed).
* Pipeline: features → calibrator → rank/reject → scorecard (lab rail only).

Does **not** retrain. Does **not** retune ECE/thr on holdout TEST or external.
Uses ``wildfire_front.ml.w3_signal.build_w3_signal_pack`` (inventory + Tobarra diagnose).

Usage
-----
::

    $env:PYTHONPATH = "."
    python scripts/run_lab_ml_loop_v34_w3_signal.py
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.ml.product_facade import (  # noqa: E402
    DEAD_PATHS,
    DEFAULT_PRODUCT_ID,
    DEFAULT_RAILS,
    ITER1_LOCKED_REJECT_THR,
    RECOMMENDED_LAB_SURFACE,
    TOBARRA_FIRE_ID,
    W3_EXTERNAL_FIRES,
    ProductFacadeError,
    assert_lab_rails,
    refuse_dead_path,
)
from wildfire_front.ml.protocol_rails import (  # noqa: E402
    FORBIDDEN_THRASH_PATHS,
    LAB_ML_BANNER,
    assert_rails_honest,
    assert_split_role,
)
from wildfire_front.ml.rank_reject_protocol import (  # noqa: E402
    DEAD_PROTOCOL_PATHS,
    protocol_payload,
    refuse_dead_protocol_path,
)
from wildfire_front.ml.w3_signal import (  # noqa: E402
    build_w3_signal_pack,
    load_json,
    tobarra_keep_seal,
    w3_lab_rails,
    w3_multi_fire_honesty,
)

_PRODUCT_ID: Final = DEFAULT_PRODUCT_ID
_RECOMMENDED_SURFACE: Final = RECOMMENDED_LAB_SURFACE  # iter1_reject_only
_DEAD_PATHS: Final = (
    frozenset(DEAD_PATHS) | frozenset(FORBIDDEN_THRASH_PATHS) | frozenset(DEAD_PROTOCOL_PATHS)
)
_PIPELINE: Final = "features→calibrator→rank/reject→scorecard"
_FACADE: Final = "wildfire_front.ml.product_facade"
_FACADE_CLASS: Final = "ClmEnsembleV34Facade"
_RANK_REJECT_PROTOCOL: Final = "wildfire_front.ml.rank_reject_protocol"
_SCORECARD_API: Final = "ClmEnsembleV34Facade.scorecard"
_BANNER: Final = LAB_ML_BANNER
_TOBARRA: Final = TOBARRA_FIRE_ID
_LOCKED_THR: Final = float(ITER1_LOCKED_REJECT_THR)
_THR_SOURCE: Final = "val_iter1_reject_frozen"


def _facade_scorecard_from_diag(diag: dict[str, Any]) -> dict[str, Any] | None:
    """Thr metrics authority: pack diagnose ``scorecard`` only (no reject_locked thr copy)."""
    sc = diag.get("scorecard")
    return sc if isinstance(sc, dict) else None


def _scorecard_thr_view(scorecard: dict[str, Any] | None, *, locked_thr: float) -> dict[str, Any]:
    """Surface frozen thr + abstain from facade.scorecard (single path)."""
    if not scorecard:
        return {
            "thr": float(locked_thr),
            "surface": _RECOMMENDED_SURFACE,
            "scorecard_api": _SCORECARD_API,
            "present": False,
        }
    unc = scorecard.get("uncertainty") if isinstance(scorecard.get("uncertainty"), dict) else {}
    rr = scorecard.get("rank_reject") if isinstance(scorecard.get("rank_reject"), dict) else {}
    primary = scorecard.get("primary") if isinstance(scorecard.get("primary"), dict) else {}
    thr = rr.get("thr", locked_thr)
    return {
        "thr": float(thr) if thr is not None else float(locked_thr),
        "surface": rr.get("surface") or _RECOMMENDED_SURFACE,
        "abstain_rate": unc.get("abstain_rate"),
        "coverage": unc.get("coverage"),
        "mean_confidence": unc.get("mean_confidence"),
        "selective_iou_at_80pct_coverage": unc.get("selective_iou_at_80pct_coverage"),
        "mean_iou": primary.get("mean_iou") or primary.get("iou_mean"),
        "scorecard_api": _SCORECARD_API,
        "schema": scorecard.get("schema"),
        "split": scorecard.get("split"),
        "present": True,
    }


def _architecture_w3_multi_fire(pack: dict[str, Any]) -> dict[str, Any]:
    """First-class architecture card: W3 multi-fire honesty (Tobarra hard + external)."""
    rails = pack.get("rails") if isinstance(pack.get("rails"), dict) else {}
    mf = pack.get("multi_fire_honesty") if isinstance(pack.get("multi_fire_honesty"), dict) else {}
    inv = pack.get("inventory") if isinstance(pack.get("inventory"), dict) else {}
    diag = pack.get("tobarra_diagnose") if isinstance(pack.get("tobarra_diagnose"), dict) else {}
    sm = inv.get("summary") if isinstance(inv.get("summary"), dict) else {}
    keep = pack.get("tobarra_keep_seal") if isinstance(pack.get("tobarra_keep_seal"), dict) else {}

    locked_thr = rails.get("locked_reject_thr")
    if locked_thr is None:
        locked_thr = _LOCKED_THR
    locked_thr = float(locked_thr)

    # Single protocol path: rank_reject_protocol.protocol_payload (VAL thr freeze).
    rank_reject = {
        **protocol_payload(locked_reject_thr=locked_thr),
        "product_facade": _FACADE,
        "module": _RANK_REJECT_PROTOCOL,
        "pipeline": _PIPELINE,
        "thr_source": _THR_SOURCE,
        "recommended_lab_surface": _RECOMMENDED_SURFACE,
        "locked_reject_thr": locked_thr,
        "freeze_iter1_reject": True,
        "scorecard_api": _SCORECARD_API,
        "scorecard_only": True,
        "no_parallel_thr_copy": True,
    }
    # Pack diagnose thr metrics: facade.scorecard only (no parallel reject_locked thr).
    scorecard = _facade_scorecard_from_diag(diag)
    thr_view = _scorecard_thr_view(scorecard, locked_thr=locked_thr)

    w3_catalog = list(mf.get("w3_external_catalog") or W3_EXTERNAL_FIRES)
    if not w3_catalog and isinstance(mf.get("w3_external"), dict):
        w3_catalog = list((mf.get("w3_external") or {}).get("fires") or [])

    return {
        "schema": "wfd_ml_architecture_w3_multi_fire_honesty_v1",
        "product_id": _PRODUCT_ID,
        "product_rail": "lab_ml",
        "field_rail": "field_ops",
        "banner": _BANNER,
        "recommended_lab_surface": _RECOMMENDED_SURFACE,
        "freeze_iter1_reject": True,
        "locked_reject_thr": locked_thr,
        "val_only_threshold_tune": True,
        "thr_source": _THR_SOURCE,
        "ml_product_go": True,
        "field_ops_allow_ml_live_in_fusion": False,
        "field_ops_ml_live_fusion": "OFF",
        "field_fusion_off": True,
        "iou_is_not_ros": True,
        "stop_ece_thrash_on_same_test": True,
        "tobarra_keep_reopen": False,
        "tobarra_hard": True,
        "tobarra_fire_id": _TOBARRA,
        "tobarra_mean_iou": diag.get("mean_iou"),
        "tobarra_bimodal": diag.get("bimodal_hint"),
        "tobarra_keep_seal": keep or tobarra_keep_seal(),
        "tobarra_scorecard": scorecard,
        "tobarra_scorecard_thr": thr_view,
        "w3_external_catalog": w3_catalog,
        "w3_role": mf.get("w3_role") or "external_probe",
        "n_external_ready": sm.get("n_external_ready"),
        "recommended_first_fire": sm.get("recommended_first_fire"),
        "hard_fire_in_pack": sm.get("hard_fire_in_pack") or _TOBARRA,
        "dead_thrash_closed": True,
        "dead_paths": sorted(_DEAD_PATHS),
        "pipeline": _PIPELINE,
        "product_facade": _FACADE,
        "facade_class": _FACADE_CLASS,
        "rank_reject_protocol": rank_reject,
        "rank_reject_protocol_mod": _RANK_REJECT_PROTOCOL,
        "scorecard_api": _SCORECARD_API,
        "scorecard_only": True,
        "no_parallel_thr_copy": True,
        "multi_fire_honesty": mf or w3_multi_fire_honesty(),
        "w3_instrumented": bool(sm) and bool(diag.get("ok")),
        "note": (
            "W3 multi-fire honesty pack is first-class architecture output under "
            "shared product_facade + rank_reject_protocol. "
            "Tobarra thr metrics via ClmEnsembleV34Facade.scorecard only "
            "(no reject_locked thr copy). "
            "Tobarra = hard transfer (KEEP reopen sealed); W3 external = frozen "
            "thr/cal eval-only probes. IoU ≠ ROS; fusion OFF; "
            "ml_product_go true (human promote; no silent auto-flip)."
        ),
    }


def _site_rails() -> dict[str, Any]:
    """Dual-product rails from facade + W3 multi-fire honesty flags."""
    r = assert_lab_rails(DEFAULT_RAILS)
    base = w3_lab_rails()
    # Prefer facade snapshot; keep W3-specific honesty flags from w3_lab_rails.
    facade = r.as_dict()
    base = {**facade, **base}
    base.update(
        {
            "label": "lab / research_open only",
            "no_ece_retune_same_holdout": True,
            "freeze_iter1_reject": True,
            "pipeline": _PIPELINE,
            "product_facade": _FACADE,
            "facade_class": _FACADE_CLASS,
            "rank_reject_protocol": _RANK_REJECT_PROTOCOL,
            "scorecard_api": _SCORECARD_API,
            "scorecard_only": True,
            "no_parallel_thr_copy": True,
            "forbidden_thrash": sorted(_DEAD_PATHS),
            "ml_product_go": True,
            "field_ops_allow_ml_live_in_fusion": False,
            "field_ops_ml_live_fusion": "OFF",
        }
    )
    assert_rails_honest(base, require_iter1_reject_default=True)
    return base


def _seal_dead_paths() -> None:
    """Architecture refuse: dead thrash must stay closed (not optional folklore)."""
    for dead in ("same_holdout_ece_retune", "tobarra_keep_reopen_same_recipe"):
        try:
            refuse_dead_path(dead)
        except ProductFacadeError:
            pass  # expected: path is sealed
        else:
            raise ProductFacadeError(f"dead path still open: {dead!r}")
        try:
            refuse_dead_protocol_path(dead)
        except ValueError:
            pass  # expected: protocol path is sealed
        else:
            raise ProductFacadeError(f"protocol dead path still open: {dead!r}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", type=Path, default=ROOT)
    p.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "outputs" / "ml_eval" / "lab_loop",
    )
    p.add_argument("--md-path", type=Path, default=None)
    p.add_argument("--no-md", action="store_true")
    args = p.parse_args(argv)

    # Protocol integrity: W3 external / Tobarra LOFO are scorecard/report only.
    assert_split_role("external", "scorecard")
    assert_split_role("lofo", "scorecard")
    _seal_dead_paths()

    repo = args.repo.resolve()
    pack = build_w3_signal_pack(repo)
    created = datetime.now(UTC).isoformat()
    inv = pack.get("inventory") or {}
    diag = pack.get("tobarra_diagnose") if isinstance(pack.get("tobarra_diagnose"), dict) else {}
    ok = bool(inv.get("summary")) and bool(diag.get("ok"))

    # Single thr metrics path: pack diagnose facade.scorecard (no reject_locked thr copy).
    scorecard = _facade_scorecard_from_diag(diag)

    rails = _site_rails()
    pack_rails = pack.get("rails") if isinstance(pack.get("rails"), dict) else {}
    rails = {**pack_rails, **rails}
    rails["scorecard_api"] = _SCORECARD_API
    rails["facade_class"] = _FACADE_CLASS
    rails["rank_reject_protocol"] = _RANK_REJECT_PROTOCOL
    rails["scorecard_only"] = True
    rails["no_parallel_thr_copy"] = True

    multi_fire = pack.get("multi_fire_honesty") or w3_multi_fire_honesty()
    keep_seal = pack.get("tobarra_keep_seal") or tobarra_keep_seal()
    arch = _architecture_w3_multi_fire(
        {
            **pack,
            "rails": rails,
            "multi_fire_honesty": multi_fire,
            "tobarra_keep_seal": keep_seal,
        }
    )
    rank_reject = arch.get("rank_reject_protocol") or {
        **protocol_payload(locked_reject_thr=float(_LOCKED_THR)),
        "product_facade": _FACADE,
        "module": _RANK_REJECT_PROTOCOL,
        "pipeline": _PIPELINE,
        "thr_source": _THR_SOURCE,
        "scorecard_api": _SCORECARD_API,
        "scorecard_only": True,
        "no_parallel_thr_copy": True,
    }
    locked_thr = float(arch.get("locked_reject_thr") or _LOCKED_THR)
    # Thr metrics: facade.scorecard only (never diag reject_locked thr copy).
    thr_view = arch.get("tobarra_scorecard_thr") or _scorecard_thr_view(
        scorecard, locked_thr=locked_thr
    )

    sm = inv.get("summary") or {}
    payload: dict[str, Any] = {
        "schema": "ml_lab_loop_v34_w3_signal_v1",
        "created_utc": created,
        "iteration": 13,
        "product_id": _PRODUCT_ID,
        "banner": _BANNER,
        "product_facade": _FACADE,
        "facade_class": _FACADE_CLASS,
        "pipeline": _PIPELINE,
        "rank_reject_protocol_mod": _RANK_REJECT_PROTOCOL,
        "scorecard_api": _SCORECARD_API,
        "scorecard_only": True,
        "no_parallel_thr_copy": True,
        "friction": "new_signal_needed_tobarra_hard_and_pack_closed",
        "control_question": (
            "¿Podemos instrumentar W3 (inventario fuegos externos + diagnóstico Tobarra) "
            "como paquete de honestidad multi-fuego de arquitectura, sin retunear ECE "
            "en holdout TEST ni reabrir Tobarra KEEP / field_ops?"
        ),
        "control_answer": "YES" if ok else "NO",
        "architecture_w3_multi_fire_honesty": arch,
        "rails": rails,
        "rank_reject_protocol": rank_reject,
        "multi_fire_honesty": multi_fire,
        "tobarra_keep_seal": keep_seal,
        "tobarra_scorecard": scorecard,
        "tobarra_scorecard_thr": thr_view,
        "pack": pack,
        "verdict": {
            "w3_instrumented": ok,
            "architecture_w3_multi_fire_honesty": True,
            "recommended_first_fire": sm.get("recommended_first_fire"),
            "tobarra_bimodal": diag.get("bimodal_hint"),
            "tobarra_mean_iou": diag.get("mean_iou"),
            "tobarra_hard": True,
            "tobarra_reject_helps": (diag.get("teaching") or {}).get("reject_helps"),
            "tobarra_scorecard_present": bool(scorecard),
            "tobarra_scorecard_abstain": thr_view.get("abstain_rate"),
            "n_external_ready": sm.get("n_external_ready"),
            "w3_external_catalog": list(W3_EXTERNAL_FIRES),
            "forbidden_ece_same_holdout": True,
            "ece_thrash_reopen": False,
            "tobarra_keep_reopen": False,
            "dead_thrash_closed": True,
            "field_product": False,
            "ml_product_go": True,
            "field_ops_fusion": "OFF",
            "recommended_lab_surface": _RECOMMENDED_SURFACE,
            "freeze_iter1_reject": True,
            "locked_reject_thr": locked_thr,
            "thr_source": _THR_SOURCE,
            "product_facade": _FACADE,
            "facade_class": _FACADE_CLASS,
            "rank_reject_protocol_mod": _RANK_REJECT_PROTOCOL,
            "scorecard_api": _SCORECARD_API,
            "scorecard_only": True,
            "no_parallel_thr_copy": True,
            "pipeline": _PIPELINE,
            "note": (
                "W3 multi-fire honesty pack (architecture): inventory + Tobarra diagnose "
                "via product_facade + rank_reject_protocol; thr via facade.scorecard only "
                "(no reject_locked thr copy). "
                "ml_product_go true (lab promote); field fusion OFF. "
                "Next: Hellín patch intake or Tobarra finetune with kill criteria "
                "(KEEP reopen sealed)."
            ),
        },
    }

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    # dedicated artifacts (inventory + diagnose remain machine-readable slices)
    (out_dir / "w3_fire_inventory.json").write_text(json.dumps(inv, indent=2), encoding="utf-8")
    (out_dir / "tobarra_head_a_diagnose.json").write_text(
        json.dumps(diag, indent=2), encoding="utf-8"
    )
    (out_dir / "w3_multi_fire_honesty_architecture.json").write_text(
        json.dumps(arch, indent=2), encoding="utf-8"
    )
    json_path = out_dir / "lab_loop_v34_w3_signal_latest.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    prev = load_json(out_dir / "lab_loop_v34_latest.json") or {}
    prev_sum = prev.get("summary") if isinstance(prev.get("summary"), dict) else {}
    prev_iters = prev.get("iterations") if isinstance(prev.get("iterations"), dict) else {}
    latest = {
        "schema": "ml_lab_loop_v34_latest_v1",
        "updated_utc": created,
        "iterations": {
            **prev_iters,
            "13_w3_signal": "lab_loop_v34_w3_signal_latest.json",
        },
        "summary": {
            **prev_sum,
            "iter13_w3_signal": True,
            "architecture_w3_multi_fire_honesty": True,
            "w3": {
                "recommended_first_fire": payload["verdict"]["recommended_first_fire"],
                "n_external_ready": payload["verdict"]["n_external_ready"],
                "tobarra_mean_iou": payload["verdict"]["tobarra_mean_iou"],
                "tobarra_bimodal": payload["verdict"]["tobarra_bimodal"],
                "tobarra_hard": True,
                "tobarra_scorecard_present": bool(scorecard),
                "w3_external_catalog": list(W3_EXTERNAL_FIRES),
                "architecture_artifact": "w3_multi_fire_honesty_architecture.json",
                "scorecard_api": _SCORECARD_API,
            },
            "multi_fire_honesty": {
                "tobarra_hard": True,
                "tobarra_fire_id": _TOBARRA,
                "tobarra_keep_reopen": False,
                "w3_external_catalog": list(W3_EXTERNAL_FIRES),
                "n_external_ready": sm.get("n_external_ready"),
                "recommended_first_fire": sm.get("recommended_first_fire"),
                "frozen_thr_and_cal": True,
                "do_not_reopen_tobarra_keep": True,
            },
            "recommended_next": "W3_hellin_patch_intake",
            "recommended_lab_surface": _RECOMMENDED_SURFACE,
            "freeze_iter1_reject": True,
            "stop_ece_thrash_on_same_test": True,
            "ece_thrash_reopen": False,
            "tobarra_keep_reopen": False,
            "dead_thrash_closed": True,
            "rank_reject_protocol": rank_reject,
            "rank_reject_protocol_mod": _RANK_REJECT_PROTOCOL,
            "scorecard_api": _SCORECARD_API,
            "scorecard_only": True,
            "no_parallel_thr_copy": True,
            "rails": {
                "ml_product_go": True,
                "field_ops_allow_ml_live_in_fusion": False,
                "field_ops_ml_live_fusion": "OFF",
                "iou_is_not_ros": True,
                "label": "lab / research_open only",
                "no_ece_retune_same_holdout": True,
                "recommended_lab_surface": _RECOMMENDED_SURFACE,
                "locked_reject_thr": locked_thr,
                "freeze_iter1_reject": True,
                "product_facade": _FACADE,
                "facade_class": _FACADE_CLASS,
                "rank_reject_protocol": _RANK_REJECT_PROTOCOL,
                "scorecard_api": _SCORECARD_API,
                "scorecard_only": True,
                "no_parallel_thr_copy": True,
                "pipeline": _PIPELINE,
            },
        },
    }
    (out_dir / "lab_loop_v34_latest.json").write_text(
        json.dumps(latest, indent=2), encoding="utf-8"
    )

    md_path: Path | None = None
    if not args.no_md:
        md_path = args.md_path or (
            ROOT / "docs" / "ML_LOOP_ITERATIONS" / "iter_20260805_w3_signal.md"
        )
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(_render_md(payload), encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": ok,
                "json": str(json_path),
                "md": str(md_path) if md_path else None,
                "architecture_w3_multi_fire_honesty": True,
                "recommended_first_fire": payload["verdict"]["recommended_first_fire"],
                "n_external_ready": payload["verdict"]["n_external_ready"],
                "tobarra_mean_iou": payload["verdict"]["tobarra_mean_iou"],
                "tobarra_bimodal": payload["verdict"]["tobarra_bimodal"],
                "tobarra_hard": True,
                "tobarra_scorecard_present": bool(scorecard),
                "w3_external_catalog": list(W3_EXTERNAL_FIRES),
                "recommended_lab_surface": _RECOMMENDED_SURFACE,
                "freeze_iter1_reject": True,
                "ml_product_go": True,
                "field_ops_fusion": "OFF",
                "ece_thrash_reopen": False,
                "tobarra_keep_reopen": False,
                "product_facade": _FACADE,
                "rank_reject_protocol": _RANK_REJECT_PROTOCOL,
                "scorecard_api": _SCORECARD_API,
                "scorecard_only": True,
                "no_parallel_thr_copy": True,
            },
            indent=2,
        )
    )
    return 0 if ok else 2


def _render_md(payload: dict[str, Any]) -> str:
    pack = payload.get("pack") or {}
    inv = pack.get("inventory") or {}
    diag = pack.get("tobarra_diagnose") or {}
    sm = inv.get("summary") or {}
    arch = payload.get("architecture_w3_multi_fire_honesty") or {}
    mf = payload.get("multi_fire_honesty") or {}
    keep = payload.get("tobarra_keep_seal") or {}
    # Thr metrics: facade.scorecard only (no reject_locked thr copy).
    thr_view = payload.get("tobarra_scorecard_thr") or arch.get("tobarra_scorecard_thr") or {}
    w3_cat = list(arch.get("w3_external_catalog") or W3_EXTERNAL_FIRES)
    lines = [
        "# ML lab loop — iter 13 W3 multi-fire honesty pack",
        "",
        f"**UTC:** {payload.get('created_utc')}  ",
        f"**Banner:** {payload.get('banner') or _BANNER}  ",
        "**Label:** lab only · architecture artifact · no ECE thrash same-holdout",
        "",
        "## Architecture (shared rails / protocol)",
        "",
        "| Gate | Value |",
        "|------|--------|",
        f"| product_facade | **{_FACADE}** |",
        f"| rank_reject_protocol | **{_RANK_REJECT_PROTOCOL}** |",
        f"| scorecard_api | **{_SCORECARD_API}** |",
        "| scorecard only | **true** (no parallel thr copy) |",
        f"| pipeline | **{_PIPELINE}** |",
        f"| recommended surface | **{_RECOMMENDED_SURFACE}** |",
        f"| locked reject thr | **{arch.get('locked_reject_thr')}** |",
        "| freeze iter1 reject | **true** |",
        f"| Tobarra hard | **{arch.get('tobarra_hard')}** |",
        "| Tobarra KEEP reopen | **sealed** |",
        f"| W3 external catalog | **{', '.join(w3_cat)}** |",
        f"| n external READY | **{arch.get('n_external_ready')}** |",
        "| dead thrash closed | **true** |",
        "| field fusion | **OFF** |",
        "| ml_product_go | **true** |",
        "| IoU ≠ ROS | **true** |",
        "",
        f"## Control: **{payload.get('control_answer')}**",
        "",
        "### Multi-fire honesty (first-class)",
        "",
        f"- hard fire in pack: **{sm.get('hard_fire_in_pack') or _TOBARRA}**",
        f"- Tobarra KEEP seal: **{keep.get('sealed', True)}** (re-promote KILL weights: **false**)",
        f"- W3 external role: **{mf.get('w3_role') or arch.get('w3_role') or 'external_probe'}**",
        "- frozen thr/cal on external: **true**",
        "",
        "### In-pack sources (closed)",
        "",
        f"- n_sources: **{sm.get('n_in_pack_sources')}**",
        f"- hard fire: **{sm.get('hard_fire_in_pack')}**",
        "",
        "### External candidates",
        "",
        f"- READY: **{sm.get('n_external_ready')}** · first: **{sm.get('recommended_first_fire')}**",
        "",
        "| id | priority | status | n_lwir | n_mask | honesty catalog |",
        "|----|----------|--------|-------:|-------:|:---------------:|",
    ]
    for e in inv.get("external_candidates") or []:
        lines.append(
            f"| {e.get('id')} | {e.get('priority')} | {e.get('status')} | "
            f"{e.get('n_lwir_tif')} | {e.get('n_mask_tif')} | "
            f"{'yes' if e.get('in_w3_honesty_catalog') else 'no'} |"
        )
    iq = diag.get("iou_quantiles") or {}
    lines += [
        "",
        "### Tobarra diagnose (hard transfer · facade.scorecard thr)",
        "",
        f"- mean IoU: **{diag.get('mean_iou')}** · bimodal: **{diag.get('bimodal_hint')}**",
        f"- frac IoU&lt;0.1: **{diag.get('frac_iou_lt_0_1')}** · q25/q75: "
        f"**{iq.get('q25')}** / **{iq.get('q75')}**",
        f"- conf band: mean **{(diag.get('conf') or {}).get('mean')}** "
        f"[{(diag.get('conf') or {}).get('min')}–{(diag.get('conf') or {}).get('max')}]",
        f"- corr(conf, IoU): **{diag.get('corr_conf_iou')}**",
        f"- scorecard thr: **{thr_view.get('thr')}** · surface: **{thr_view.get('surface')}**",
        f"- scorecard abstain: **{thr_view.get('abstain_rate')}** · coverage: **{thr_view.get('coverage')}**",
        f"- scorecard present: **{thr_view.get('present')}**",
        f"- reject helps: **{(diag.get('teaching') or {}).get('reject_helps')}**",
        f"- thr source: **{diag.get('thr_source') or _THR_SOURCE}**",
        f"- thr metrics API: **{_SCORECARD_API}** (no reject_locked thr copy)",
        "",
        "## Rails",
        "",
        "| Rail | Value |",
        "|------|--------|",
        "| ml_product_go | **true** |",
        "| field_ops fusion | **OFF** |",
        "| ECE thrash same TEST | **stopped** |",
        "| Tobarra KEEP reopen | **closed** |",
        f"| surface | **{_RECOMMENDED_SURFACE}** |",
        f"| product_facade | **{_FACADE}** |",
        f"| rank_reject_protocol | **{_RANK_REJECT_PROTOCOL}** |",
        f"| scorecard_api | **{_SCORECARD_API}** |",
        "",
        "## Next",
        "",
        "1. Hellín `geotiff_to_training_patches` + Head A eval-only (frozen thr/cal)",
        "2. Tobarra finetune only with kill criteria (no U1 ECE thrash; KEEP reopen sealed)",
        "3. `ml_product_go` **true** (human promote 2026-08-05); field fusion remains "
        "**OFF** (lab GO ≠ field fusion)",
        "",
        "```powershell",
        "python scripts/run_lab_ml_loop_v34_w3_signal.py",
        "```",
        "",
        "---",
        "*Iteration 13 — W3 multi-fire honesty as architecture artifact on product_facade "
        "+ rank_reject_protocol; thr via facade.scorecard only; ml_product_go true "
        "(lab ≠ field fusion); thrash closed.*",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
