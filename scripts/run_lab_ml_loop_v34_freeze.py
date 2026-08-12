#!/usr/bin/env python3
"""Lab ML loop iter 7: freeze / handoff pack consolidating core lab evidence.

Architecture (product ROI — no retrain)
---------------------------------------
* Dual-product rails: **lab ML** vs **field_ops**; IoU ≠ ROS;
  ``ml_product_go`` promoted **true** when lab_usable (human promote 2026-08-05);
  silent auto-flip thrash refused; field fusion stays **OFF** (lab GO ≠ field fusion).
* Default lab surface: **iter1 reject only** (VAL-only thr frozen, thr≈0.795).
* Unified path via ``product_facade`` + ``rank_reject_protocol``:
  features→calibrator→rank/reject→scorecard. Sealed by ``lab_freeze``;
  this runner emits the architecture freeze card — it does not reimplement conf logic.
* Dead thrash paths (same-holdout ECE post-hoc / logistic refit, Tobarra KEEP
  reopen of KILL weights, auto_ml_product_go) are **not** required loop evidence
  and never gate freeze; explicit promoted true is allowed.
* Multi-fire honesty first-class (Tobarra hard, W3 external / LOFO).
* Freeze ≠ field fusion ON. Does **not** retrain or retune ECE.

Usage
-----
::

    $env:PYTHONPATH = "."
    python scripts/run_lab_ml_loop_v34_freeze.py
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

from wildfire_front.ml.lab_freeze import build_lab_freeze_pack, load_json  # noqa: E402
from wildfire_front.ml.product_facade import (  # noqa: E402
    DEAD_PATHS,
    DEFAULT_MULTI_FIRE,
    DEFAULT_PRODUCT_ID,
    ITER1_LOCKED_REJECT_THR,
    RECOMMENDED_LAB_SURFACE,
    ProductFacadeError,
    refuse_dead_path,
)
from wildfire_front.ml.protocol_rails import (  # noqa: E402
    FORBIDDEN_THRASH_PATHS,
    rank_abstain_protocol_dict,
)

# Core freeze evidence (promoted lab path). Dead ECE/refit thrash is *not* required.
_CORE_ITER_ARTIFACTS: Final[dict[str, str]] = {
    "1_reject": "lab_loop_v34_reject_latest.json",
    "4_generalization": "lab_loop_v34_generalization_latest.json",
    "5_teach_cases": "lab_loop_v34_teach_cases_latest.json",
    "6_risk_curve": "lab_loop_v34_risk_curve_latest.json",
}

# Historical dead thrash — optional presence only; never required for freeze.
_DEAD_THRASH_ITER_ARTIFACTS: Final[dict[str, str]] = {
    "2_ece_posthoc": "lab_loop_v34_ece_latest.json",
    "3_refit": "lab_loop_v34_refit_latest.json",
}

_PRODUCT_ID: Final = DEFAULT_PRODUCT_ID
_RECOMMENDED_SURFACE: Final = RECOMMENDED_LAB_SURFACE  # iter1_reject_only
_DEAD_PATHS: Final = frozenset(DEAD_PATHS) | frozenset(FORBIDDEN_THRASH_PATHS)
_PIPELINE: Final = "features→calibrator→rank/reject→scorecard"
_FACADE: Final = "wildfire_front.ml.product_facade"
_RANK_REJECT_PROTOCOL: Final = "wildfire_front.ml.rank_reject_protocol"


def _architecture_freeze(pack: dict[str, Any]) -> dict[str, Any]:
    """Emit architecture freeze: product_facade rails, iter1 reject, fusion OFF."""
    rails = pack.get("rails") if isinstance(pack.get("rails"), dict) else {}
    locked_thr = rails.get("locked_reject_thr")
    if locked_thr is None:
        locked_thr = ITER1_LOCKED_REJECT_THR
    multi_fire = pack.get("multi_fire_honesty")
    if not isinstance(multi_fire, dict):
        multi_fire = DEFAULT_MULTI_FIRE.as_dict()
    rank_reject = rank_abstain_protocol_dict(
        locked_reject_thr=float(locked_thr),
        recommended_lab_surface=_RECOMMENDED_SURFACE,
    )
    return {
        "schema": "wfd_ml_architecture_freeze_v1",
        "product_id": _PRODUCT_ID,
        "product_rail": "lab_ml",
        "field_rail": "field_ops",
        "recommended_lab_surface": _RECOMMENDED_SURFACE,
        "freeze_iter1_reject": True,
        "locked_reject_thr": float(locked_thr),
        "val_only_threshold_tune": True,
        # Human promote authorized 2026-08-05 (lab GO ≠ field fusion).
        "ml_product_go": True,
        "field_ops_allow_ml_live_in_fusion": False,
        "field_ops_ml_live_fusion": "OFF",
        "field_fusion_off": True,
        "iou_is_not_ros": True,
        "stop_ece_thrash_on_same_test": True,
        "tobarra_keep_reopen": False,
        "dead_thrash_not_required_for_freeze": True,
        "dead_thrash_closed": True,
        "dead_paths": sorted(_DEAD_PATHS),
        "core_iterations": list(_CORE_ITER_ARTIFACTS.keys()),
        "dead_thrash_iterations": list(_DEAD_THRASH_ITER_ARTIFACTS.keys()),
        "pipeline": _PIPELINE,
        "product_facade": _FACADE,
        "rank_reject_protocol": rank_reject,
        "rank_reject_protocol_mod": _RANK_REJECT_PROTOCOL,
        "multi_fire_honesty": multi_fire,
        "freeze_neq_field_promote": True,
        "note": (
            "Architecture freeze seals iter1 reject as default lab surface via "
            "product_facade + rank_reject_protocol and keeps field_ops fusion OFF. "
            "Same-holdout ECE/refit thrash and Tobarra KEEP reopen are closed — "
            "optional archaeology only, not required freeze gates."
        ),
    }


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

    # Dead thrash must stay sealed (architecture refuse — not optional folklore).
    for dead in (
        "same_holdout_ece_retune",
        "tobarra_keep_reopen_same_recipe",
    ):
        try:
            refuse_dead_path(dead)
        except ProductFacadeError:
            pass  # expected: path is sealed
        else:
            raise ProductFacadeError(f"dead path still open: {dead!r}")

    repo = args.repo.resolve()
    pack = build_lab_freeze_pack(repo)
    created = datetime.now(UTC).isoformat()
    usable = bool((pack.get("verdict") or {}).get("lab_usable_freeze"))
    arch = _architecture_freeze(pack)
    core_iters = list((pack.get("core_iteration_presence") or _CORE_ITER_ARTIFACTS).keys())

    # Prefer pack rails (already product_facade via lab_freeze); stamp facade ids.
    rails = dict(pack.get("rails") or {})
    rails.update(
        {
            # Rails stamp promoted true; verdict below is bool(lab_usable).
            "ml_product_go": True,
            "field_ops_allow_ml_live_in_fusion": False,
            "field_ops_ml_live_fusion": "OFF",
            "iou_is_not_ros": True,
            "recommended_lab_surface": _RECOMMENDED_SURFACE,
            "freeze_iter1_reject": True,
            "stop_ece_thrash_on_same_test": True,
            "tobarra_keep_reopen": False,
            "dead_thrash_closed": True,
            "pipeline": _PIPELINE,
            "product_facade": _FACADE,
            "rank_reject_protocol": _RANK_REJECT_PROTOCOL,
            "dead_paths": sorted(_DEAD_PATHS),
        }
    )
    if rails.get("locked_reject_thr") is None:
        rails["locked_reject_thr"] = float(ITER1_LOCKED_REJECT_THR)

    payload: dict[str, Any] = {
        "schema": "ml_lab_loop_v34_freeze_v1",
        "created_utc": created,
        "iteration": 7,
        "product_id": _PRODUCT_ID,
        "product_facade": _FACADE,
        "pipeline": _PIPELINE,
        "friction": "loop_evidence_not_consolidated_for_handoff",
        "control_question": (
            "¿Se puede congelar un handoff lab usable (CLI+evidencia+rails honestos) "
            "sin promover a campo ni retunear ECE?"
        ),
        "control_answer": "YES" if usable else "NO",
        "architecture_freeze": arch,
        "rails": rails,
        "rank_reject_protocol": arch.get("rank_reject_protocol"),
        "multi_fire_honesty": pack.get("multi_fire_honesty") or arch["multi_fire_honesty"],
        "freeze_pack": pack,
        "verdict": {
            **(pack.get("verdict") or {}),
            "recommended_lab_surface": _RECOMMENDED_SURFACE,
            "architecture_freeze": True,
            "freeze_iter1_reject": True,
            "ece_holdout_still_unfixed": True,
            "stop_ece_thrash_on_same_test": True,
            "tobarra_keep_reopen": False,
            "dead_thrash_not_required": True,
            "dead_thrash_closed": True,
            "field_product": False,
            # Stamp true when lab_usable (human promote authorized; fusion stays OFF).
            "ml_product_go": bool(usable),
            "field_ops_fusion": "OFF",
            "product_facade": _FACADE,
            "pipeline": _PIPELINE,
            "core_iterations_frozen": core_iters,
            "dead_thrash_iterations": list(_DEAD_THRASH_ITER_ARTIFACTS.keys()),
        },
    }

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "lab_loop_v34_freeze_latest.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    prev = load_json(out_dir / "lab_loop_v34_latest.json") or {}
    prev_sum = prev.get("summary") if isinstance(prev.get("summary"), dict) else {}
    prev_iters = prev.get("iterations") if isinstance(prev.get("iterations"), dict) else {}

    # Preserve optional dead-thrash pointers if already present (archaeology only);
    # never re-seed them as required freeze evidence.
    dead_thrash_ptrs = {k: prev_iters[k] for k in _DEAD_THRASH_ITER_ARTIFACTS if k in prev_iters}

    latest = {
        "schema": "ml_lab_loop_v34_latest_v1",
        "updated_utc": created,
        "architecture_freeze": arch,
        "core_iterations": dict(_CORE_ITER_ARTIFACTS),
        "dead_thrash_iterations": {
            "required_for_freeze": False,
            "paths": dict(_DEAD_THRASH_ITER_ARTIFACTS),
            "present_optional": dead_thrash_ptrs,
            "note": (
                "same-holdout ECE post-hoc / refit are closed thrash — "
                "optional archaeology, not freeze gates"
            ),
        },
        "iterations": {
            **prev_iters,
            **_CORE_ITER_ARTIFACTS,
            **dead_thrash_ptrs,
            "7_freeze": "lab_loop_v34_freeze_latest.json",
        },
        "summary": {
            **prev_sum,
            "iter7_lab_freeze": True,
            "lab_usable_freeze": usable,
            "architecture_freeze": True,
            "recommended_lab_surface": _RECOMMENDED_SURFACE,
            "freeze_iter1_reject": True,
            "stop_ece_thrash_on_same_test": True,
            "tobarra_keep_reopen": False,
            "dead_thrash_not_required_for_freeze": True,
            "dead_thrash_iterations_closed": list(_DEAD_THRASH_ITER_ARTIFACTS.keys()),
            "core_iterations": list(_CORE_ITER_ARTIFACTS.keys()),
            "product_facade": _FACADE,
            "pipeline": _PIPELINE,
            "rails": {
                "ml_product_go": True,
                "field_ops_allow_ml_live_in_fusion": False,
                "field_ops_ml_live_fusion": "OFF",
                "iou_is_not_ros": True,
                "label": "lab / research_open only",
                "no_ece_retune_same_holdout": True,
                "recommended_lab_surface": _RECOMMENDED_SURFACE,
                "locked_reject_thr": arch.get("locked_reject_thr"),
                "product_facade": _FACADE,
                "pipeline": _PIPELINE,
            },
            "cli_freeze": "wildfire-front ml freeze",
            "freeze_checks_ok": all((pack.get("checks") or {}).values()),
        },
    }
    (out_dir / "lab_loop_v34_latest.json").write_text(
        json.dumps(latest, indent=2), encoding="utf-8"
    )

    md_path: Path | None = None
    if not args.no_md:
        md_path = args.md_path or (
            ROOT / "docs" / "ML_LOOP_ITERATIONS" / "iter_20260804_lab_freeze.md"
        )
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(_render_md(payload), encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": True,
                "json": str(json_path),
                "md": str(md_path) if md_path else None,
                "lab_usable_freeze": usable,
                "control_answer": payload["control_answer"],
                "architecture_freeze": True,
                "recommended_lab_surface": _RECOMMENDED_SURFACE,
                "freeze_iter1_reject": True,
                "ml_product_go": bool(usable),
                "field_ops_fusion": "OFF",
                "product_facade": _FACADE,
                "pipeline": _PIPELINE,
                "dead_thrash_not_required": True,
                "core_iterations": list(_CORE_ITER_ARTIFACTS.keys()),
                "checks": pack.get("checks"),
            },
            indent=2,
        )
    )
    return 0 if usable else 2


def _render_md(payload: dict[str, Any]) -> str:
    pack = payload.get("freeze_pack") or {}
    v = pack.get("verdict") or {}
    payload_verdict = payload.get("verdict") or {}
    rails = payload.get("rails") or pack.get("rails") or {}
    arch = payload.get("architecture_freeze") or {}
    # Rails stamp promoted true; verdict stamps true when lab_usable.
    ml_go_rails = bool(rails.get("ml_product_go", arch.get("ml_product_go", True)))
    ml_go_verdict = bool(
        payload_verdict.get(
            "ml_product_go",
            v.get("lab_usable_freeze", False),
        )
    )
    ml_go_rails_s = "true" if ml_go_rails else "false"
    ml_go_verdict_s = "true" if ml_go_verdict else "false"
    lines = [
        "# ML lab loop — iter 7 freeze / handoff",
        "",
        f"**UTC:** {payload.get('created_utc')}  ",
        f"**product_facade:** `{_FACADE}`  ",
        f"**pipeline:** `{_PIPELINE}`  ",
        "**Prior:** core iters 1,4–6 (reject YES · LOFO · teach · curve)  ",
        "**Dead thrash (not required):** iters 2–3 ECE post-hoc / refit  ",
        "**Label:** lab / research_open only",
        "",
        "## Architecture freeze",
        "",
        "| Key | Value |",
        "|-----|--------|",
        f"| product_facade | **{_FACADE}** |",
        f"| pipeline | **{_PIPELINE}** |",
        f"| recommended surface | **{arch.get('recommended_lab_surface', _RECOMMENDED_SURFACE)}** |",
        f"| freeze iter1 reject | **{arch.get('freeze_iter1_reject', True)}** |",
        f"| locked thr | **{arch.get('locked_reject_thr', rails.get('locked_reject_thr'))}** |",
        f"| ml_product_go | **{ml_go_rails_s}** |",
        "| field_ops fusion | **OFF** |",
        "| ECE thrash same TEST | **stopped / not required** |",
        "| Tobarra KEEP reopen | **false / sealed** |",
        "| dead thrash required for freeze | **false** |",
        "",
        "## Rails",
        "",
        "| Rail | Value |",
        "|------|--------|",
        f"| product_facade | **{_FACADE}** |",
        f"| ml_product_go | **{ml_go_rails_s}** |",
        "| field_ops fusion | **OFF** |",
        f"| recommended surface | **{_RECOMMENDED_SURFACE}** |",
        f"| locked thr | **{rails.get('locked_reject_thr')}** |",
        "| ECE thrash same TEST | **stopped** |",
        "",
        f"## Control: **{payload.get('control_answer')}**",
        "",
        f"- lab_usable_freeze: **{v.get('lab_usable_freeze')}**",
        f"- ml_product_go (verdict, when lab_usable): **{ml_go_verdict_s}**",
        "- field_product: **false**",
        "- architecture_freeze: **true**",
        f"- product_facade: **{_FACADE}**",
        f"- note: {v.get('note')}",
        "",
        "## Loop board",
        "",
        "| Iter | Name | Lab promote? | Headline |",
        "|-----:|------|:------------:|----------|",
    ]
    for row in pack.get("loop_board") or []:
        flag = "DEAD" if row.get("dead_path") else ("YES" if row.get("promoted_lab") else "NO")
        lines.append(f"| {row.get('iter')} | {row.get('name')} | {flag} | {row.get('headline')} |")
    lines += [
        "",
        "## Checks (core + rails; ece/refit not required)",
        "",
    ]
    for k, ok in (pack.get("checks") or {}).items():
        lines.append(f"- [{'x' if ok else ' '}] `{k}`")
    lines += [
        "",
        "## CLI",
        "",
        "```powershell",
        "python -m wildfire_front ml freeze",
        "python -m wildfire_front ml freeze --json",
        "```",
        "",
        "## Do not",
        "",
    ]
    for d in pack.get("do_not") or []:
        lines.append(f"- {d}")
    lines += [
        "",
        "---",
        "*Iteration 7 — architecture freeze via product_facade: iter1 reject default, "
        "ml_product_go true when lab_usable (human promote), fusion OFF. "
        "Lab GO ≠ field fusion. ECE not fixed. Dead thrash not required.*",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
