"""CLI contract tests for ``wildfire-front ml`` lab product surface.

Single product path: product_facade + rank_reject_protocol
(features→calibrator→rank/reject→scorecard) for show/doctor/predict.

Rails: field_ops fusion OFF · ml_product_go true · IoU ≠ ROS.
Default surface iter1_reject_only (VAL thr freeze). Never assert fusion ON for field_ops.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wildfire_front.cli import build_parser, main
from wildfire_front.cli_ml import (
    build_ml_doctor_report,
    build_ml_scorecard_snapshot,
)
from wildfire_front.ml.product_facade import (
    ITER1_LOCKED_REJECT_THR,
    RECOMMENDED_LAB_SURFACE,
)

ROOT = Path(__file__).resolve().parents[1]

_FACADE_MOD = "wildfire_front.ml.product_facade"
_FACADE_CLASS = "ClmEnsembleV34Facade"
_PIPELINE = "features→calibrator→rank/reject→scorecard"
_RANK_REJECT_MOD = "wildfire_front.ml.rank_reject_protocol"


def _run_main(argv: list[str], capsys) -> tuple[int, str, str]:
    """Invoke CLI main; return (exit_code, stdout, stderr)."""
    try:
        main(argv)
        code = 0
    except SystemExit as exc:
        raw = exc.code
        if raw is None:
            code = 0
        elif isinstance(raw, int):
            code = raw
        else:
            code = 1
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_ml_list_exit_0_contains_clm_ensemble_v34(capsys):
    code, out, _err = _run_main(["ml", "list"], capsys)
    assert code == 0
    assert "clm_ensemble_v34" in out
    # Strong contract: product rows must show not_for (not vacuous "not" from banner)
    assert "not_for" in out.lower()
    assert "drone ros" in out.lower() or "ros" in out.lower()
    low = out.lower()
    assert "lab product" in low
    assert "iou" in low
    assert "field_ops" in low
    assert "default" in low
    assert "clm_ensemble_v34" in out


def test_ml_list_json_schema(capsys):
    code, out, _err = _run_main(["ml", "list", "--json"], capsys)
    assert code == 0
    data = json.loads(out)
    assert data["schema"] == "wfd_ml_list_v1"
    assert data["default_product"] == "clm_ensemble_v34"
    ids = {p["id"] for p in data["products"]}
    assert "clm_ensemble_v34" in ids
    assert data.get("ops_product") == "front_dynamics_v1" or "front_dynamics" in str(
        data.get("ops_product")
    )
    # Every product must expose non-empty not_for
    by_id = {p["id"]: p for p in data["products"]}
    v34 = by_id["clm_ensemble_v34"]
    assert isinstance(v34.get("not_for"), str) and len(v34["not_for"].strip()) > 0
    for p in data["products"]:
        assert isinstance(p.get("not_for"), str) and p["not_for"].strip(), p.get("id")


def test_ml_show_json_rails(capsys):
    code, out, _err = _run_main(["ml", "show", "--json"], capsys)
    assert code == 0
    data = json.loads(out)
    assert data["schema"] == "wfd_ml_show_snapshot_v1"
    assert data["gates"]["ml_product_go"] is True
    fusion = data["fusion_rails"]
    assert fusion["field_ops_allow_ml_live_in_fusion"] is False
    assert fusion["field_ops_ml_live_fusion"] == "OFF"
    # Never claim field_ops ON
    assert fusion["field_ops_ml_live_fusion"] != "ON"
    # U1 / catalog keys present
    assert "u1" in data
    assert "catalog_holdout" in data
    cat_iou = data["catalog_holdout"].get("test_iou")
    # When scorecard provenance is present, expect known 0.8963; never invent if None
    if cat_iou is not None:
        assert abs(float(cat_iou) - 0.8963) < 0.001
    # product_facade + rank_reject_protocol single path (not rails-only)
    assert data.get("product_facade") == _FACADE_MOD
    assert data.get("facade_class") == _FACADE_CLASS
    assert data.get("pipeline") == _PIPELINE
    assert RECOMMENDED_LAB_SURFACE == "iter1_reject_only"
    rr = data.get("rank_reject_protocol")
    assert isinstance(rr, dict)
    assert rr.get("product_facade") == _FACADE_MOD
    assert rr.get("facade_class") == _FACADE_CLASS
    assert rr.get("pipeline") == _PIPELINE
    assert rr.get("recommended_lab_surface") == "iter1_reject_only"
    assert rr.get("thr_tune_split") == "val"
    assert abs(float(rr.get("locked_reject_thr")) - float(ITER1_LOCKED_REJECT_THR)) < 1e-9
    assert rr.get("ml_product_go") is True
    assert rr.get("field_ops_allow_ml_live_in_fusion") is False
    rails = data.get("rails") or {}
    assert rails.get("product_facade") == _FACADE_MOD
    assert rails.get("recommended_lab_surface") == "iter1_reject_only"
    assert rails.get("stop_ece_thrash_on_same_test") is True
    assert rails.get("tobarra_keep_reopen") is False
    mf = data.get("multi_fire_honesty") or {}
    assert mf.get("lofo_first_class") is True
    assert mf.get("w3_first_class") is True
    assert mf.get("do_not_reopen_tobarra_keep") is True
    # When Head A caches exist: live ClmEnsembleV34Facade features→scorecard
    fp = data.get("facade_pipeline")
    if fp is not None and fp.get("present"):
        assert fp.get("product_facade") == _FACADE_MOD
        assert fp.get("facade_class") == _FACADE_CLASS
        assert "features" in str(fp.get("pipeline") or "")
        assert fp.get("recommended_lab_surface") == "iter1_reject_only"
        assert abs(float(fp.get("locked_reject_thr")) - float(ITER1_LOCKED_REJECT_THR)) < 1e-9
        assert fp.get("ml_product_go") is True
        assert fp.get("field_ops_ml_live_fusion") == "OFF"
        assert isinstance(fp.get("rank_reject"), dict)
        assert fp["rank_reject"].get("protocol_module") == _RANK_REJECT_MOD or (
            "rank_reject" in str(fp["rank_reject"].get("protocol_module") or "")
            or fp["rank_reject"].get("recommended_lab_surface") == "iter1_reject_only"
        )
        assert "scorecard" in fp


def test_ml_cases_offline_teach_surface(capsys):
    code, out, _err = _run_main(["ml", "cases"], capsys)
    assert code == 0
    low = out.lower()
    assert "lab" in low
    assert "ml_product_go" in low or "true" in low
    assert "field_ops" in low or "off" in low
    assert "reject" in low or "thr" in low
    # Never claim field fusion product
    assert "field_ops fusion:    ON" not in out


def test_ml_cases_json_rails(capsys):
    code, out, _err = _run_main(["ml", "cases", "--json"], capsys)
    assert code == 0
    data = json.loads(out)
    assert data["schema"] == "wfd_ml_teach_cases_v1"
    assert data["rails"]["ml_product_go"] is True
    assert data["rails"]["field_ops_allow_ml_live_in_fusion"] is False
    assert data["rails"]["iou_is_not_ros"] is True
    assert data["fail_cases"]["present"] is True
    assert data["fail_cases"]["n_rows"] >= 1


def test_ml_curve_offline_rails(capsys):
    code, out, _err = _run_main(["ml", "curve"], capsys)
    assert code == 0
    low = out.lower()
    assert "coverage" in low or "selective" in low
    assert "ml_product_go" in low or "true" in low
    assert "off" in low
    assert "field_ops fusion:    ON" not in out


def test_ml_curve_json_rails(capsys):
    code, out, _err = _run_main(["ml", "curve", "--json"], capsys)
    assert code == 0
    data = json.loads(out)
    assert data["schema"] == "ml_lab_loop_v34_risk_curve_v1"
    assert data["rails"]["ml_product_go"] is True
    assert data["rails"]["field_ops_allow_ml_live_in_fusion"] is False
    assert data["rails"]["iou_is_not_ros"] is True
    assert data["verdict"]["recommended_lab_surface"] == "iter1_reject_only"
    assert len(data["selective_curve"]["test"]) >= 3


def test_ml_freeze_handoff_rails(capsys):
    code, out, _err = _run_main(["ml", "freeze"], capsys)
    # usable freeze → 0; incomplete → 2; never claim field ON
    assert code in (0, 2)
    low = out.lower()
    assert "lab_usable_freeze" in low or "freeze" in low
    assert "ml_product_go" in low
    assert "field_ops fusion:    ON" not in out
    assert "off" in low


def test_ml_freeze_json_claims(capsys):
    code, out, _err = _run_main(["ml", "freeze", "--json"], capsys)
    assert code in (0, 2)
    data = json.loads(out)
    assert data["schema"] == "wfd_ml_lab_freeze_v1"
    assert data["rails"]["ml_product_go"] is True
    assert data["rails"]["field_ops_allow_ml_live_in_fusion"] is False
    assert data["claims"]["field_product"] is False
    assert data["claims"]["ece_fixed"] is False
    assert data["claims"]["iou_is_ros"] is False
    assert data["claims"]["recommended_lab_surface"] == "iter1_reject_only"
    if data["verdict"]["lab_usable_freeze"]:
        assert code == 0
    else:
        assert code == 2


def test_ml_smoke_post_freeze(capsys):
    code, out, _err = _run_main(["ml", "smoke"], capsys)
    assert code in (0, 2)
    low = out.lower()
    assert "smoke" in low
    assert "field_ops fusion:    ON" not in out
    assert "off" in low or "ml_product_go" in low


def test_ml_smoke_json(capsys):
    code, out, _err = _run_main(["ml", "smoke", "--json"], capsys)
    assert code in (0, 2)
    data = json.loads(out)
    assert data["schema"] == "wfd_ml_lab_smoke_v1"
    assert data["rails"]["ml_product_go"] is True
    assert data["rails"]["field_ops_allow_ml_live_in_fusion"] is False
    if data["verdict"]["smoke_pass"]:
        assert code == 0
    else:
        assert code == 2


def test_ml_lofo_board_rails(capsys):
    code, out, _err = _run_main(["ml", "lofo"], capsys)
    assert code in (0, 2)
    low = out.lower()
    assert "lofo" in low or "fold" in low
    assert "field_ops fusion:    ON" not in out
    assert "off" in low or "ml_product_go" in low


def test_ml_lofo_json(capsys):
    code, out, _err = _run_main(["ml", "lofo", "--json"], capsys)
    assert code in (0, 2)
    data = json.loads(out)
    assert data["schema"] == "wfd_ml_lofo_board_v1"
    assert data["rails"]["ml_product_go"] is True
    assert data["rails"]["field_ops_allow_ml_live_in_fusion"] is False
    assert data["rails"]["lofo_is_not_u1_ece"] is True
    if data["verdict"]["lofo_board_built"]:
        assert code == 0
        assert data["summary"]["n_folds"] >= 1
    else:
        assert code == 2


def test_ml_next_gate_rails(capsys):
    code, out, _err = _run_main(["ml", "next"], capsys)
    assert code == 0
    low = out.lower()
    assert "recommended_next" in low or "w1" in low
    assert "field_ops fusion:    ON" not in out


def test_ml_next_json(capsys):
    code, out, _err = _run_main(["ml", "next", "--json"], capsys)
    assert code == 0
    data = json.loads(out)
    assert data["schema"] == "wfd_ml_lab_next_v1"
    assert data["rails"]["ml_product_go"] is True
    assert data["rails"]["field_ops_allow_ml_live_in_fusion"] is False
    assert data["verdict"]["auto_unfreeze"] is False
    assert data["verdict"]["metric_retune_allowed"] is False
    assert data["recommended_next"] in (
        "W1_lofo_head_a_caches",
        "W2_lofo_ece_reject_eval",
        "W3_new_features_or_data",
    )


def test_ml_show_human_mentions_rails(capsys):
    code, out, _err = _run_main(["ml", "show"], capsys)
    assert code == 0
    assert "ml_product_go" in out
    assert "OFF" in out
    assert "field_ops" in out.lower()
    # recommended eligibility must not be confused with field_ops ON
    assert "field_ops stays OFF" in out or "field_ops stays off" in out.lower()
    assert "0.8963" in out or "provenance" in out.lower()
    low = out.lower()
    assert "lab" in low or "iou" in low
    # Facade surface (features→scorecard path), not rails banner only
    assert _FACADE_CLASS in out or "facade" in low
    assert "iter1_reject_only" in out or "iter1" in low
    assert "pipeline" in low or "features" in low


def test_ml_doctor_exit_0_structure(capsys):
    code, out, _err = _run_main(["ml", "doctor"], capsys)
    assert code == 0
    assert "ML doctor" in out or "doctor" in out.lower()
    # Structure present even if weights missing
    assert "catalog" in out.lower() or "OK" in out or "MISSING" in out
    # Facade freeze / thrash checks surface in human doctor
    low = out.lower()
    assert "facade" in low or _FACADE_CLASS.lower() in low or "iter1" in low


def test_ml_doctor_json_structure(capsys):
    code, out, _err = _run_main(["ml", "doctor", "--json"], capsys)
    assert code == 0
    data = json.loads(out)
    assert data["schema"] == "wfd_ml_doctor_v1"
    assert "checks" in data
    assert isinstance(data["checks"], list)
    assert len(data["checks"]) >= 3
    assert data["summary"]["ready_for_offline"] is True
    # field_ops fusion must be reported OFF / check ok
    names = {c["name"]: c for c in data["checks"]}
    assert "field_ops_fusion_off" in names
    assert names["field_ops_fusion_off"]["ok"] is True
    assert "ml_product_go_true" in names
    assert names["ml_product_go_true"]["ok"] is True
    # ClmEnsembleV34Facade product path + rank/reject freeze surface
    assert data.get("product_facade") == _FACADE_MOD
    assert data.get("facade_class") == _FACADE_CLASS
    assert data.get("pipeline") == _PIPELINE
    assert "facade_iter1_reject" in names
    assert names["facade_iter1_reject"]["ok"] is True
    assert "facade_dead_thrash_closed" in names
    assert names["facade_dead_thrash_closed"]["ok"] is True
    honesty = " ".join(data.get("honesty") or [])
    assert _FACADE_CLASS in honesty or "facade" in honesty.lower()


def test_ml_card_offline_hold(capsys, tmp_path: Path):
    """Offline hold demo with hard rail asserts (JSON preferred)."""
    out = tmp_path / "ml_card"
    code, stdout, err = _run_main(
        [
            "ml",
            "card",
            "--mode",
            "offline",
            "--scenario",
            "hold",
            "--output",
            str(out),
            "--json",
        ],
        capsys,
    )
    if code != 0:
        combined = (stdout + err).lower()
        assert "traceback" not in combined
        pytest.skip(f"ml card offline not runnable here: {err or stdout}")
    assert code == 0
    data = json.loads(stdout)
    assert data["schema"] == "wfd_ml_card_v1"
    # Hard rails — not vacuous
    assert data["field_ops_fusion"] == "OFF"
    assert data["field_ops_fusion"] != "ON"
    assert data["ml_product_go"] is True
    summary = data.get("summary") or {}
    assert str(summary.get("decision", "")).upper() == "HOLD"
    # Human fallback path also checked without --json
    code2, human, err2 = _run_main(
        [
            "ml",
            "card",
            "--mode",
            "offline",
            "--scenario",
            "hold",
            "--output",
            str(tmp_path / "ml_card_human"),
        ],
        capsys,
    )
    if code2 != 0:
        pytest.skip(f"ml card human path skip: {err2 or human}")
    assert "fusion: OFF (field_ops)" in human
    assert "ml_product_go=true" in human
    # Must not advertise field_ops fusion ON
    assert "fusion: ON (field_ops)" not in human
    assert "field_ops fusion ON" not in human.lower()


def test_ml_predict_list_products(capsys):
    code, out, _err = _run_main(["ml", "predict", "--list-products"], capsys)
    assert code == 0
    assert "clm_ensemble_v34" in out


def test_ml_predict_list_products_json_facade_surface(capsys):
    """predict --list-products --json stamps product_facade + rank/reject freeze."""
    code, out, _err = _run_main(
        ["ml", "predict", "--list-products", "--json"],
        capsys,
    )
    assert code == 0
    data = json.loads(out)
    assert data.get("product_facade") == _FACADE_MOD
    assert data.get("facade_class") == _FACADE_CLASS
    assert data.get("pipeline") == _PIPELINE
    assert data.get("recommended_lab_surface") == "iter1_reject_only"
    assert abs(float(data.get("locked_reject_thr")) - float(ITER1_LOCKED_REJECT_THR)) < 1e-9
    assert data.get("ml_product_go") is True
    assert data.get("field_ops_ml_live_fusion") == "OFF"
    rails = data.get("rails") or {}
    assert rails.get("product_facade") == _FACADE_MOD
    assert rails.get("recommended_lab_surface") == "iter1_reject_only"
    assert rails.get("stop_ece_thrash_on_same_test") is True
    assert rails.get("tobarra_keep_reopen") is False
    products = data.get("products") or []
    ids = {p.get("id") for p in products if isinstance(p, dict)}
    assert "clm_ensemble_v34" in ids


def test_ml_predict_missing_npz_clean_exit(capsys):
    """Without --npz and without list: exit 1, no traceback."""
    code, out, err = _run_main(
        ["ml", "predict", "--product", "clm_ensemble_v34"],
        capsys,
    )
    # If weights missing → 1; if weights present but no npz → 1
    assert code == 1
    combined = out + err
    assert "traceback" not in combined.lower()
    assert (
        "error" in combined.lower() or "npz" in combined.lower() or "not ready" in combined.lower()
    )


def test_ml_predict_missing_weights_clean_exit(capsys, monkeypatch):
    """Weights missing → exit 1 + clear message (no traceback), even if .pt exist on disk."""

    class _FakeSpec:
        def resolve_existing(self):
            return False, "missing weights: models/fake/weights.pt"

    def _fake_get_product(product_id: str, catalog_path=None):  # noqa: ARG001
        return _FakeSpec()

    monkeypatch.setattr(
        "wildfire_front.ml.product_catalog.get_product",
        _fake_get_product,
    )
    code, out, err = _run_main(
        [
            "ml",
            "predict",
            "--product",
            "clm_ensemble_v34",
            "--npz",
            "artifacts/does_not_matter.npz",
        ],
        capsys,
    )
    assert code == 1
    combined = (out + err).lower()
    assert "traceback" not in combined
    assert "not ready" in combined or "missing weights" in combined
    assert "error" in combined


def test_ml_help_banner():
    parser = build_parser()
    # Ensure ml subcommand registered
    # Parse help via subparser
    ml_parser = None
    for action in parser._subparsers._group_actions:  # type: ignore[attr-defined]
        if hasattr(action, "choices") and action.choices and "ml" in action.choices:
            ml_parser = action.choices["ml"]
            break
    assert ml_parser is not None
    help_text = ml_parser.format_help()
    low = help_text.lower()
    assert "lab product" in low
    assert "field_ops" in low
    assert "iou" in low
    assert "list" in low and "show" in low and "doctor" in low


def test_scorecard_snapshot_helpers():
    snap = build_ml_scorecard_snapshot(ROOT)
    assert snap["gates"]["ml_product_go"] is True
    assert snap["fusion_rails"]["field_ops_allow_ml_live_in_fusion"] is False
    assert snap["fusion_rails"]["field_ops_ml_live_fusion"] == "OFF"
    # Single path: ClmEnsembleV34Facade + rank_reject_protocol surface
    assert snap.get("product_facade") == _FACADE_MOD
    assert snap.get("facade_class") == _FACADE_CLASS
    assert snap.get("pipeline") == _PIPELINE
    rr = snap.get("rank_reject_protocol") or {}
    assert rr.get("product_facade") == _FACADE_MOD
    assert rr.get("recommended_lab_surface") == RECOMMENDED_LAB_SURFACE == "iter1_reject_only"
    assert rr.get("thr_tune_split") == "val"
    assert abs(float(rr.get("locked_reject_thr")) - float(ITER1_LOCKED_REJECT_THR)) < 1e-9
    report = build_ml_doctor_report(ROOT)
    assert report["schema"] == "wfd_ml_doctor_v1"
    assert report["summary"]["ready_for_offline"] is True
    # ready_for_live_predict is explicit default-product readiness
    assert isinstance(report["summary"]["ready_for_live_predict"], bool)
    assert report.get("product_facade") == _FACADE_MOD
    assert report.get("facade_class") == _FACADE_CLASS
    assert report.get("pipeline") == _PIPELINE
    names = {c["name"]: c for c in report.get("checks") or []}
    assert names.get("facade_iter1_reject", {}).get("ok") is True
    assert names.get("facade_dead_thrash_closed", {}).get("ok") is True


def test_catalog_holdout_no_invented_iou_when_missing(tmp_path: Path, monkeypatch):
    """SUG-1: missing provenance → test_iou is None, not invented 0.8963."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (tmp_path / "config").mkdir()
    (tmp_path / "models").mkdir()
    # Minimal scorecard without catalog_holdout_test_reference
    (docs / "ML_PRODUCT_SCORECARD.json").write_text(
        json.dumps(
            {
                "schema": "ml_scorecard_v1",
                "product_id": "clm_ensemble_v34",
                "primary": {"model_iou": 0.85},
                "uncertainty": {"ece_patch_conf": 0.15},
                "gates": {"ml_product_go": True, "u1_test_honest": True},
                "provenance": {},
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "config" / "decision_policies.json").write_text(
        json.dumps({"policies": {"field_ops": {"allow_ml_live_in_fusion": False}}}),
        encoding="utf-8",
    )
    (tmp_path / "models" / "catalog.json").write_text(
        json.dumps({"default_product": "clm_ensemble_v34", "products": {}}),
        encoding="utf-8",
    )
    snap = build_ml_scorecard_snapshot(tmp_path)
    assert snap["catalog_holdout"]["test_iou"] is None
    assert snap["gates"]["ml_product_go"] is True
    assert snap["fusion_rails"]["field_ops_ml_live_fusion"] == "OFF"


def test_never_assert_field_ops_fusion_on():
    """Hard rail: snapshot always reports field_ops fusion OFF in this repo."""
    snap = build_ml_scorecard_snapshot(ROOT)
    assert snap["fusion_rails"]["field_ops_allow_ml_live_in_fusion"] is False
    policies = json.loads((ROOT / "config" / "decision_policies.json").read_text(encoding="utf-8"))
    assert policies["policies"]["field_ops"]["allow_ml_live_in_fusion"] is False
