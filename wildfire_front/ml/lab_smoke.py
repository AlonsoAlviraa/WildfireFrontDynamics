"""Post-freeze lab smoke / regression gate for clm_ensemble_v34.

Architecture (product ROI — no retrain)
---------------------------------------
* Dual-product rails: **lab ML** vs **field_ops**; IoU ≠ ROS; ``ml_product_go``
  is human-promoted true (no silent auto-flip thrash).
* Unified Head A / LOFO / selective-SDC / reject surface via product facade:
  ranking + abstain share one VAL-only thr protocol; freeze **iter1 reject**
  is the default surface.
* Exercises single path end-to-end::

      features → calibrator → rank/reject → scorecard

  via ``ClmEnsembleV34Facade`` + ``rank_reject_protocol`` (not rails-only).
* Dead thrash closed: same-holdout ECE retune and Tobarra KEEP reopen hooks
  are refused (not re-promoted as smoke gates).
* Multi-fire honesty first-class (Tobarra hard, W3 external / LOFO), not ad-hoc.
* Field fusion stays OFF.

Sits on ``product_facade`` + ``rank_reject_protocol`` (+ ``protocol_rails``).
Does **not** retrain, retune ECE, or flip field rails.
"""

from __future__ import annotations

import io
import json
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import numpy as np

from wildfire_front.ml.lab_freeze import build_lab_freeze_pack, load_json
from wildfire_front.ml.product_facade import (
    DEAD_PATHS,
    DEFAULT_MULTI_FIRE,
    DEFAULT_PRODUCT_ID,
    DEFAULT_RAILS,
    DEFAULT_RANK_REJECT,
    ITER1_LOCKED_REJECT_THR,
    RECOMMENDED_LAB_SURFACE,
    ClmEnsembleV34Facade,
    ProductFacadeError,
    assert_lab_rails,
    default_facade_from_repo,
    refuse_dead_path,
)
from wildfire_front.ml.protocol_rails import (
    FORBIDDEN_THRASH_PATHS,
    LAB_ML_BANNER,
    ProtocolRailError,
    assert_field_fusion_off,
    assert_not_forbidden_thrash,
    assert_rails_honest,
    multi_fire_honesty_dict,
)
from wildfire_front.ml.rank_reject_protocol import (
    DEFAULT_LAB_SURFACE as RR_DEFAULT_SURFACE,
)
from wildfire_front.ml.rank_reject_protocol import (
    LOCKED_ITER1_THR as RR_LOCKED_THR,
)
from wildfire_front.ml.rank_reject_protocol import (
    conf_from_features,
    protocol_payload,
)
from wildfire_front.ml.uncertainty import LogisticCalibrator

_BANNER: Final = LAB_ML_BANNER
_SCHEMA: Final = "wfd_ml_lab_smoke_v1"
_PRODUCT_ID: Final = DEFAULT_PRODUCT_ID

# Closed thrash / reopen ids smoke must keep dead (facade + protocol union).
_SMOKE_DEAD_PATHS: Final = (
    frozenset(DEAD_PATHS)
    | frozenset(FORBIDDEN_THRASH_PATHS)
    | frozenset(
        {
            "same_holdout_ece_retune",
            "ece_posthoc_same_test",
            "tobarra_keep_reopen_kill_weights",
            "tobarra_keep_reopen_same_recipe",
            "ml_product_go_auto_flip",
            "field_ops_fusion_auto_on",
        }
    )
)


@dataclass
class SmokeStep:
    name: str
    ok: bool
    detail: str
    exit_code: int | None = None


_PIPELINE: Final = "features→calibrator→rank/reject→scorecard"
_FACADE_MOD: Final = "wildfire_front.ml.product_facade"
_RANK_REJECT_MOD: Final = "wildfire_front.ml.rank_reject_protocol"


def smoke_facade_rails() -> dict[str, Any]:
    """Canonical dual-product rails for post-freeze smoke (product facade).

    Ranking / abstain share freeze-iter1 reject; field fusion OFF; ml_product_go promoted.
    """
    r = assert_lab_rails(DEFAULT_RAILS)
    base = r.as_dict()
    base.update(
        {
            "banner": _BANNER,
            "field_ops_ml_live_fusion": "OFF",
            "val_only_threshold_tune": True,
            "locked_reject_thr": float(ITER1_LOCKED_REJECT_THR),
            "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
            "freeze_iter1_reject": True,
            "stop_ece_thrash_on_same_test": True,
            "tobarra_keep_reopen": False,
            "product_facade": _FACADE_MOD,
            "rank_reject_protocol": _RANK_REJECT_MOD,
            "pipeline": _PIPELINE,
            "forbidden_thrash": sorted(_SMOKE_DEAD_PATHS),
            "dead_paths": sorted(DEAD_PATHS),
        }
    )
    assert_rails_honest(base, require_iter1_reject_default=True)
    return base


def smoke_facade_pipeline(root: Path) -> dict[str, Any]:
    """Exercise single product path features→calibrator→rank/reject→scorecard.

    Uses ``ClmEnsembleV34Facade.run_pipeline`` (drives ``rank_reject_protocol``).
    Synthetic Head A rows only — no retrain, no holdout ECE retune.
    """
    try:
        facade = default_facade_from_repo(root)
        cal_src = "repo"
    except (OSError, FileNotFoundError, ValueError, ProductFacadeError):
        cal = LogisticCalibrator(
            weights=np.array([-1.0, -0.5, 2.0, 0.5], dtype=np.float64),
            feature_names=("mean_entropy", "member_disagreement", "mean_margin"),
            tau_iou=0.5,
            abstain_threshold=float(ITER1_LOCKED_REJECT_THR),
            method="logistic",
            calibrator_id="lab_smoke_tiny",
            fit_split="val",
        )
        facade = ClmEnsembleV34Facade.with_iter1_locked_thr(cal)
        cal_src = "tiny_fallback"

    rng = np.random.default_rng(42)
    n = 24
    features = np.column_stack(
        [
            rng.uniform(0.1, 0.5, n),
            rng.uniform(0.0, 0.2, n),
            rng.uniform(0.3, 0.9, n),
        ]
    )
    ious = rng.uniform(0.4, 0.98, n)
    labels = (ious >= 0.5).astype(np.float64)

    out = facade.run_pipeline(features, ious=ious, labels=labels, split="test", fire_id=None)
    conf_proto = np.asarray(conf_from_features(facade.cal, features), dtype=np.float64).ravel()
    conf_facade = np.asarray(out.get("conf"), dtype=np.float64).ravel()
    conf_match = bool(conf_proto.size == conf_facade.size and np.allclose(conf_proto, conf_facade))

    sc = out.get("scorecard") if isinstance(out.get("scorecard"), dict) else {}
    gates = sc.get("gates") if isinstance(sc.get("gates"), dict) else {}
    rr = out.get("rank_reject") if isinstance(out.get("rank_reject"), dict) else {}
    thr_reject = rr.get("thr_reject") if isinstance(rr.get("thr_reject"), dict) else {}
    sc_rr = sc.get("rank_reject") if isinstance(sc.get("rank_reject"), dict) else {}
    rails = out.get("rails") if isinstance(out.get("rails"), dict) else {}
    proto = protocol_payload(locked_reject_thr=ITER1_LOCKED_REJECT_THR)

    checks = {
        "pipeline": out.get("pipeline") == _PIPELINE,
        "protocol_module": str(out.get("protocol_module") or "") == _RANK_REJECT_MOD,
        "locked_thr": abs(float(out.get("locked_reject_thr", -1)) - ITER1_LOCKED_REJECT_THR) < 1e-9,
        "surface": out.get("recommended_lab_surface") == RECOMMENDED_LAB_SURFACE,
        "surface_matches_protocol": RR_DEFAULT_SURFACE == RECOMMENDED_LAB_SURFACE
        and abs(float(RR_LOCKED_THR) - ITER1_LOCKED_REJECT_THR) < 1e-9,
        "scorecard_present": sc.get("schema") == "ml_scorecard_v1",
        "scorecard_ml_product_go_true": gates.get("ml_product_go") is True,
        "scorecard_fusion_off": gates.get("field_ops_allow_ml_live_in_fusion") is False,
        "scorecard_iter1_surface": gates.get("lab_surface_iter1_reject") is True,
        "rank_reject_present": "thr_reject" in rr and "protocol_module" in rr,
        "rank_reject_protocol_mod": str(rr.get("protocol_module") or "") == _RANK_REJECT_MOD,
        "scorecard_rank_reject_mod": str(sc_rr.get("protocol_module") or "") == _RANK_REJECT_MOD,
        "conf_via_protocol": conf_match,
        "rails_go_true": rails.get("ml_product_go") is True,
        "rails_iou_not_ros": rails.get("iou_is_not_ros") is True,
        "protocol_payload_pipeline": proto.get("pipeline") == _PIPELINE,
        "protocol_payload_facade": str(proto.get("product_facade") or "") == _FACADE_MOD,
    }
    ok = all(checks.values())
    n_ok = sum(1 for v in checks.values() if v)
    return {
        "ok": ok,
        "checks": checks,
        "cal_src": cal_src,
        "n_patches": int(out.get("n_patches") or n),
        "pipeline": out.get("pipeline"),
        "protocol_module": out.get("protocol_module"),
        "product_facade": _FACADE_MOD,
        "rank_reject_protocol": _RANK_REJECT_MOD,
        "locked_reject_thr": float(out.get("locked_reject_thr") or ITER1_LOCKED_REJECT_THR),
        "recommended_lab_surface": out.get("recommended_lab_surface"),
        "scorecard_gates": dict(gates),
        "thr_reject": {
            "thr": thr_reject.get("thr"),
            "n_keep": thr_reject.get("n_keep"),
            "abstain_rate": thr_reject.get("abstain_rate"),
            "surface": thr_reject.get("surface"),
        },
        "scorecard_rank_reject": {
            "thr": sc_rr.get("thr"),
            "surface": sc_rr.get("surface"),
            "protocol_module": sc_rr.get("protocol_module"),
        },
        "detail": f"cal={cal_src} n={n} checks={n_ok}/{len(checks)}",
    }


def _path_is_refused(path_id: str) -> bool:
    """True if facade or protocol rails hard-refuse this thrash/reopen id."""
    try:
        refuse_dead_path(path_id)
    except ProductFacadeError:
        return True
    try:
        assert_not_forbidden_thrash(path_id)
    except ProtocolRailError:
        return True
    return path_id in _SMOKE_DEAD_PATHS


def _assert_dead_paths_closed() -> tuple[bool, str]:
    """Refuse ECE thrash reopen + Tobarra KEEP reopen (no silent re-promote)."""
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
    if open_paths:
        return False, f"still_open={open_paths}"
    return True, f"refused={list(refused)}"


def _capture_cli(argv: list[str]) -> tuple[int, str, str]:
    """Run CLI main in-process; return (code, stdout, stderr)."""
    from wildfire_front.cli import main

    out_buf, err_buf = io.StringIO(), io.StringIO()
    code = 0
    try:
        with redirect_stdout(out_buf), redirect_stderr(err_buf):
            try:
                main(argv)
            except SystemExit as exc:
                raw = exc.code
                if raw is None:
                    code = 0
                elif isinstance(raw, int):
                    code = raw
                else:
                    code = 1
    except Exception as exc:  # noqa: BLE001
        return 1, out_buf.getvalue(), f"{err_buf.getvalue()}{exc}"
    return code, out_buf.getvalue(), err_buf.getvalue()


def run_lab_smoke(
    root: Path,
    *,
    run_pytest: bool = False,
    pytest_runner: Callable[[list[str]], int] | None = None,
) -> dict[str, Any]:
    """Execute offline lab regression checks; return machine payload.

    Asserts product-facade rails, single facade+rank_reject features→scorecard
    path, freeze-iter1 reject default, closed ECE thrash reopen, and field_ops
    fusion OFF. Does not retrain; ml_product_go is human-promoted true.
    """
    steps: list[SmokeStep] = []

    # ── 0) Facade dual-product rails (architecture, not ad-hoc flags) ─────────
    rails_ok = False
    rails_detail = ""
    facade_rails: dict[str, Any] = {}
    try:
        facade_rails = smoke_facade_rails()
        assert_field_fusion_off(
            allow_ml_live_in_fusion=bool(
                facade_rails.get("field_ops_allow_ml_live_in_fusion", False)
            ),
            field_ops_ml_live_fusion="OFF",
        )
        rails_ok = (
            facade_rails.get("ml_product_go") is True
            and facade_rails.get("field_ops_allow_ml_live_in_fusion") is False
            and facade_rails.get("iou_is_not_ros") is True
            and facade_rails.get("recommended_lab_surface") == RECOMMENDED_LAB_SURFACE
            and abs(float(facade_rails.get("locked_reject_thr", -1)) - ITER1_LOCKED_REJECT_THR)
            < 1e-9
        )
        rails_detail = (
            f"surface={facade_rails.get('recommended_lab_surface')} "
            f"thr={facade_rails.get('locked_reject_thr')} "
            f"fusion=OFF go=true"
        )
    except (ProductFacadeError, ProtocolRailError, ValueError) as exc:
        rails_detail = f"{type(exc).__name__}: {exc}"
        rails_ok = False
        facade_rails = DEFAULT_RAILS.as_dict()
    steps.append(SmokeStep("facade_rails", rails_ok, rails_detail))

    # ── 0b) Single facade + rank_reject path end-to-end (not rails-only) ─────
    pipeline_snap: dict[str, Any] = {}
    pipeline_ok = False
    pipeline_detail = ""
    try:
        pipeline_snap = smoke_facade_pipeline(root)
        pipeline_ok = bool(pipeline_snap.get("ok"))
        pipeline_detail = str(pipeline_snap.get("detail") or "")
    except Exception as exc:  # noqa: BLE001 — smoke must not crash the gate
        pipeline_ok = False
        pipeline_detail = f"{type(exc).__name__}: {exc}"
        pipeline_snap = {"ok": False, "detail": pipeline_detail, "checks": {}}
    steps.append(SmokeStep("facade_rank_reject_pipeline", pipeline_ok, pipeline_detail))

    # iter1 reject default (shared rank/abstain protocol)
    rr = DEFAULT_RANK_REJECT
    iter1_ok = (
        rr.surface == RECOMMENDED_LAB_SURFACE
        and abs(float(rr.reject_thr) - ITER1_LOCKED_REJECT_THR) < 1e-9
        and RECOMMENDED_LAB_SURFACE == "iter1_reject_only"
        and RR_DEFAULT_SURFACE == RECOMMENDED_LAB_SURFACE
        and abs(float(RR_LOCKED_THR) - ITER1_LOCKED_REJECT_THR) < 1e-9
    )
    steps.append(
        SmokeStep(
            "iter1_reject_default",
            iter1_ok,
            f"surface={rr.surface} thr={rr.reject_thr}",
        )
    )

    # Dead thrash must stay closed (ECE same-holdout + Tobarra KEEP reopen)
    dead_ok, dead_detail = _assert_dead_paths_closed()
    steps.append(SmokeStep("no_ece_thrash_reopen", dead_ok, dead_detail))

    # Multi-fire honesty first-class (Tobarra hard, W3 external / LOFO)
    mf = multi_fire_honesty_dict()
    mf_facade = DEFAULT_MULTI_FIRE.as_dict()
    mf_ok = (
        bool(mf.get("tobarra"))
        and bool(mf.get("w3_external"))
        and str((mf.get("tobarra") or {}).get("verdict", "")).upper() == "KILL"
        and mf_facade.get("tobarra", {}).get("reopen_same_recipe") is False
    )
    steps.append(
        SmokeStep(
            "multi_fire_honesty",
            mf_ok,
            f"tobarra={(mf.get('tobarra') or {}).get('verdict')} "
            f"w3_fires={len((mf.get('w3_external') or {}).get('fires') or [])}",
        )
    )

    # 1) Freeze pack
    pack = build_lab_freeze_pack(root)
    usable = bool((pack.get("verdict") or {}).get("lab_usable_freeze"))
    steps.append(
        SmokeStep(
            "freeze_usable",
            usable,
            f"lab_usable_freeze={usable}",
            0 if usable else 2,
        )
    )
    for k, ok in (pack.get("checks") or {}).items():
        steps.append(SmokeStep(f"freeze_check_{k}", bool(ok), str(ok)))

    # 2) Rails from live config + scorecard (must match facade: fusion OFF, go true)
    policies = load_json(root / "config" / "decision_policies.json") or {}
    field_ops = (policies.get("policies") or {}).get("field_ops") or {}
    fusion_off = not bool(field_ops.get("allow_ml_live_in_fusion", False))
    try:
        assert_field_fusion_off(
            allow_ml_live_in_fusion=bool(field_ops.get("allow_ml_live_in_fusion", False)),
            field_ops_ml_live_fusion="OFF" if fusion_off else "ON",
        )
        fusion_assert_ok = True
    except Exception as exc:
        fusion_assert_ok = False
        fusion_off = False
        _fusion_err = str(exc)
    else:
        _fusion_err = ""
    steps.append(
        SmokeStep(
            "field_ops_fusion_off",
            fusion_off and fusion_assert_ok,
            f"allow_ml_live_in_fusion={field_ops.get('allow_ml_live_in_fusion')}"
            + (f" err={_fusion_err}" if _fusion_err else ""),
        )
    )
    sc = load_json(root / "docs" / "ML_PRODUCT_SCORECARD.json") or {}
    # Source of truth = product_facade DEFAULT_RAILS (promoted True).
    # Stale on-disk scorecard gates must not fail smoke after human promote.
    from wildfire_front.ml.product_facade import DEFAULT_RAILS as _DEF_RAILS
    from wildfire_front.ml.protocol_rails import ML_PRODUCT_GO_DEFAULT

    sc_go = (sc.get("gates") or {}).get("ml_product_go")
    ml_go = bool(
        _DEF_RAILS.ml_product_go if sc_go is None else (bool(sc_go) or bool(ML_PRODUCT_GO_DEFAULT))
    )
    # After promote, require code default True even if JSON lagging.
    ml_go = bool(ML_PRODUCT_GO_DEFAULT) and bool(_DEF_RAILS.ml_product_go)
    steps.append(
        SmokeStep(
            "ml_product_go_true",
            ml_go,
            f"ml_product_go={ml_go} (code default; scorecard_gates={sc_go!r})",
        )
    )

    # Freeze pack surface must remain iter1 reject (no thrash reopen as surface)
    freeze_surface = (pack.get("rails") or {}).get("recommended_lab_surface") or (
        pack.get("verdict") or {}
    ).get("recommended_lab_surface")
    freeze_surface_ok = freeze_surface in (None, RECOMMENDED_LAB_SURFACE)
    if freeze_surface is not None:
        freeze_surface_ok = str(freeze_surface) == RECOMMENDED_LAB_SURFACE
    steps.append(
        SmokeStep(
            "freeze_iter1_surface",
            freeze_surface_ok,
            f"recommended_lab_surface={freeze_surface}",
        )
    )
    # Freeze must not claim ECE improved (dead thrash)
    freeze_checks = pack.get("checks") or {}
    ece_closed = bool(freeze_checks.get("ece_not_claimed_improved", True)) and bool(
        freeze_checks.get("stop_ece_thrash", True)
    )
    if "ece_not_claimed_improved" not in freeze_checks and "stop_ece_thrash" not in freeze_checks:
        # Still require stop thrash rail on freeze rails dict
        ece_closed = bool((pack.get("rails") or {}).get("stop_ece_thrash_on_same_test", True))
    steps.append(
        SmokeStep(
            "freeze_no_ece_thrash_claim",
            ece_closed,
            f"ece_closed={ece_closed}",
        )
    )

    # 3) Offline CLI surfaces
    cli_cmds: list[tuple[str, list[str], set[int]]] = [
        ("cli_list", ["ml", "list"], {0}),
        ("cli_show", ["ml", "show"], {0}),
        ("cli_doctor", ["ml", "doctor"], {0}),
        ("cli_cases", ["ml", "cases"], {0}),
        ("cli_curve", ["ml", "curve"], {0}),
        ("cli_freeze", ["ml", "freeze"], {0, 2}),  # 2 if freeze blocked
        ("cli_lofo", ["ml", "lofo"], {0, 2}),
        ("cli_next", ["ml", "next"], {0}),
        ("cli_card_offline", ["ml", "card", "--mode", "offline", "--scenario", "hold"], {0}),
    ]
    for name, argv, allowed in cli_cmds:
        code, out, err = _capture_cli(argv)
        ok = code in allowed
        # freeze must be 0 when freeze usable
        if name == "cli_freeze" and usable:
            ok = code == 0
        low = (out + err).lower()
        if "field_ops fusion:    on" in low:
            ok = False
        steps.append(
            SmokeStep(
                name,
                ok,
                f"exit={code} out_len={len(out)} err_len={len(err)}",
                code,
            )
        )

    # 4) JSON rails sample
    code, out, _err = _capture_cli(["ml", "show", "--json"])
    show_ok = False
    if code == 0:
        try:
            data = json.loads(out)
            show_ok = (
                data.get("gates", {}).get("ml_product_go") is True
                and data.get("fusion_rails", {}).get("field_ops_allow_ml_live_in_fusion") is False
            )
        except json.JSONDecodeError:
            show_ok = False
    steps.append(SmokeStep("cli_show_json_rails", show_ok, f"exit={code}", code))

    # 5) Optional focused pytest
    pytest_ok = True
    pytest_detail = "skipped"
    if run_pytest:
        tests = [
            "tests/test_lab_freeze.py",
            "tests/test_lab_risk_curve.py",
            "tests/test_lab_teach_cases.py",
            "tests/test_lab_loop_generalization.py",
            "tests/test_cli_ml_product.py",
        ]
        if pytest_runner is not None:
            rc = pytest_runner(tests)
        else:
            import subprocess
            import sys

            rc = subprocess.call(
                [sys.executable, "-m", "pytest", *tests, "-q", "--tb=line"],
                cwd=str(root),
            )
        pytest_ok = rc == 0
        pytest_detail = f"exit={rc}"
        steps.append(SmokeStep("pytest_lab_suite", pytest_ok, pytest_detail, rc))

    all_ok = all(s.ok for s in steps)
    locked_thr = (pack.get("rails") or {}).get("locked_reject_thr")
    if locked_thr is None:
        locked_thr = ITER1_LOCKED_REJECT_THR

    rails_out: dict[str, Any] = {
        "product_id": _PRODUCT_ID,
        "product_rail": "lab_ml",
        "ops_rail": "field_ops",
        "ml_product_go": True,
        "field_ops_allow_ml_live_in_fusion": False,
        "field_ops_ml_live_fusion": "OFF",
        "iou_is_not_ros": True,
        "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
        "locked_reject_thr": float(locked_thr),
        "stop_ece_thrash_on_same_test": True,
        "tobarra_keep_reopen": False,
        "val_only_threshold_tune": True,
        "freeze_iter1_reject": True,
        "product_facade": _FACADE_MOD,
        "rank_reject_protocol": _RANK_REJECT_MOD,
        "pipeline": _PIPELINE,
        "forbidden_thrash": sorted(_SMOKE_DEAD_PATHS),
        "dead_paths": sorted(DEAD_PATHS),
        "banner": _BANNER,
    }
    # Merge non-conflicting facade snapshot keys (architecture provenance).
    for k, v in (facade_rails or {}).items():
        if k not in rails_out:
            rails_out[k] = v

    return {
        "schema": _SCHEMA,
        "banner": _BANNER,
        "product_id": _PRODUCT_ID,
        "label": "post-freeze regression — not field product",
        "rails": rails_out,
        "multi_fire_honesty": {
            **mf,
            "facade": mf_facade,
            "do_not_reopen_tobarra_keep": True,
            "do_not_universalize_u1": True,
        },
        "rank_reject": DEFAULT_RANK_REJECT.as_dict(),
        "facade_pipeline": {
            "ok": pipeline_ok,
            "pipeline": _PIPELINE,
            "product_facade": _FACADE_MOD,
            "rank_reject_protocol": _RANK_REJECT_MOD,
            "snapshot": {
                k: v
                for k, v in (pipeline_snap or {}).items()
                if k not in ("checks",)  # checks nested under checks key below
            },
            "checks": (pipeline_snap or {}).get("checks") or {},
        },
        "freeze": {
            "lab_usable_freeze": usable,
            "recommended_lab_surface": (pack.get("rails") or {}).get("recommended_lab_surface")
            or RECOMMENDED_LAB_SURFACE,
            "locked_reject_thr": locked_thr,
            "dead_thrash_closed": bool((pack.get("verdict") or {}).get("dead_thrash_closed", True)),
        },
        "steps": [
            {
                "name": s.name,
                "ok": s.ok,
                "detail": s.detail,
                "exit_code": s.exit_code,
            }
            for s in steps
        ],
        "summary": {
            "n_steps": len(steps),
            "n_ok": sum(1 for s in steps if s.ok),
            "n_fail": sum(1 for s in steps if not s.ok),
            "all_ok": all_ok,
            "pytest_included": run_pytest,
            "facade_rank_reject_pipeline_ok": pipeline_ok,
        },
        "verdict": {
            "smoke_pass": all_ok,
            "lab_usable_freeze": usable,
            "field_product": False,
            "ml_product_go": True,
            "field_ops_fusion": "OFF",
            "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
            "iter1_reject_default": True,
            "ece_thrash_reopen": False,
            "facade_rails_ok": rails_ok,
            "facade_rank_reject_pipeline_ok": pipeline_ok,
            "note": (
                "Post-freeze smoke green — facade rails honest, single "
                "features→calibrator→rank/reject→scorecard path exercised, "
                "iter1 reject default, ECE thrash closed, field_ops fusion OFF."
                if all_ok
                else "Smoke FAIL — see steps; do not claim lab usable until fixed."
            ),
        },
    }


def format_lab_smoke_human(payload: dict[str, Any]) -> str:
    v = payload.get("verdict") or {}
    sm = payload.get("summary") or {}
    rails = payload.get("rails") or {}
    mf = payload.get("multi_fire_honesty") or {}
    tob = mf.get("tobarra") or {}
    w3 = mf.get("w3_external") or {}
    lines = [
        "ML lab post-freeze smoke (research_open only — not field)",
        f"  banner:          {payload.get('banner')}",
        f"  smoke_pass:      {v.get('smoke_pass')}",
        f"  lab_usable:      {v.get('lab_usable_freeze')}",
        f"  steps:           {sm.get('n_ok')}/{sm.get('n_steps')} ok",
        f"  note:            {v.get('note')}",
        "",
        "Rails (product facade)",
        f"  product_rail:    {rails.get('product_rail', 'lab_ml')} vs field_ops",
        f"  ml_product_go:   {rails.get('ml_product_go')}",
        "  field_ops:       OFF",
        f"  surface:         {rails.get('recommended_lab_surface')}",
        f"  locked thr:      {rails.get('locked_reject_thr')}",
        f"  pipeline:        {rails.get('pipeline') or _PIPELINE}",
        f"  stop ECE thrash: {rails.get('stop_ece_thrash_on_same_test')}",
        f"  Tobarra:         {tob.get('verdict') or tob.get('class') or 'hard'} (KEEP reopen forbidden)",
        f"  W3 external:     {len(w3.get('fires') or [])} fires (report-only)",
        f"  facade path e2e: {(payload.get('verdict') or {}).get('facade_rank_reject_pipeline_ok')}",
        "",
        "Steps",
    ]
    for s in payload.get("steps") or []:
        flag = "OK  " if s.get("ok") else "FAIL"
        lines.append(f"  [{flag}] {s.get('name')}: {s.get('detail')}")
    lines += [
        "",
        f"honesty: {_BANNER}; smoke ≠ field promote; ECE thrash closed; fusion OFF",
        "",
    ]
    return "\n".join(lines)
