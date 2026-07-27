"""PR3/PR4: pilot honesty card offline orchestrator + pure report (no weights)."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_pilot_honesty_card.py"
DEMO_SCRIPT = ROOT / "scripts" / "run_ml_live_card_demo.py"
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "pilot"
GEN_AT = "2026-07-24T00:00:00+00:00"


def _load_pilot_mod():
    spec = importlib.util.spec_from_file_location("run_pilot_honesty_card", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_demo_mod():
    spec = importlib.util.spec_from_file_location("run_ml_live_card_demo", DEMO_SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_bare_fixture_root_loads_pilot_sites_json(tmp_path: Path):
    """T4b/T6: --fixture-root alone auto-loads DIR/pilot_sites.json."""
    mod = _load_pilot_mod()
    out = tmp_path / "pilot_out"
    summary = mod.run_pilot(
        mode="offline",
        fixture_root=FIXTURE_ROOT,
        out_dir=out,
        generated_at=GEN_AT,
        write_docs_report=False,
    )
    assert summary.get("n_failed", 0) == 0
    assert summary.get("n_ok") == 3
    assert (out / "pilot_manifest.json").is_file()
    assert (out / "facts_table.json").is_file()
    assert (out / "report" / "PILOT_HONESTY_CARD.md").is_file()
    assert (out / "index.html").is_file()
    portal = (out / "index.html").read_text(encoding="utf-8")
    assert 'lang="es"' in portal
    assert "Tobarra" in portal and "Níjar" in portal and "Caminomorisco" in portal
    assert "No es orden táctica" in portal
    assert "Not a tactical dispatch" not in portal
    assert "field_ops" in portal and "OFF" in portal
    assert "provenance only" in portal
    assert "confianza" in portal
    assert "sitios OK" in portal
    assert "Saltar al contenido" in portal
    assert "Sitios" in portal and "Contraste" in portal
    assert "se calla" in portal  # Tobarra research GO → field_ops ABSTAIN
    assert ">sí<" in portal or ">no<" in portal  # ML live bools Spanish
    report = (out / "report" / "PILOT_HONESTY_CARD.md").read_text(encoding="utf-8")
    assert "sí" in report or "no" in report  # no raw True/False in table
    assert "True" not in report and "False" not in report
    for sid in ("tobarra", "nijar", "caminomorisco"):
        site_dir = out / "sites" / sid
        assert (site_dir / "decision_card.json").is_file()
        assert (site_dir / "decision_card_field_ops.json").is_file()
        assert (site_dir / "site_summary.json").is_file()
        assert (site_dir / "sources.json").is_file()
    # must not require production packs
    man = json.loads((out / "pilot_manifest.json").read_text(encoding="utf-8"))
    assert "fixture_root" in (man.get("catalog_source") or "")
    assert "outputs/open_if" not in json.dumps(man)


def test_tobarra_ops_on_card(tmp_path: Path):
    mod = _load_pilot_mod()
    out = tmp_path / "pilot_ops"
    mod.run_pilot(
        mode="offline",
        fixture_root=FIXTURE_ROOT,
        out_dir=out,
        generated_at=GEN_AT,
        sites_filter=["tobarra"],
    )
    card = json.loads(
        (out / "sites" / "tobarra" / "decision_card.json").read_text(encoding="utf-8")
    )
    ops_src = None
    for s in card.get("sources") or []:
        if s.get("id") in {"ops_thermal_front", "ops"}:
            ops_src = s
            break
    assert ops_src is not None
    assert ops_src.get("available") is True
    ros = (ops_src.get("metrics") or {}).get("primary_ros_m_min")
    assert ros is not None
    summary = json.loads(
        (out / "sites" / "tobarra" / "site_summary.json").read_text(encoding="utf-8")
    )
    assert summary["sources_resolved"]["ops"] is True
    assert summary["ops_primary_ros_m_min"] is not None


def test_open_metrics_never_contain_ros_keys(tmp_path: Path):
    mod = _load_pilot_mod()
    out = tmp_path / "pilot_open"
    mod.run_pilot(
        mode="offline",
        fixture_root=FIXTURE_ROOT,
        out_dir=out,
        generated_at=GEN_AT,
    )
    banned = ("primary_ros_m_min", "vp_m_min", "vp_tactical", "ros_m_min")
    for sid in ("nijar", "caminomorisco"):
        sources = json.loads((out / "sites" / sid / "sources.json").read_text(encoding="utf-8"))
        open_m = sources.get("open") or {}
        blob = json.dumps(open_m)
        for k in banned:
            assert k not in open_m
            assert f'"{k}"' not in blob


def test_field_ops_fusion_false_and_hold_or_abstain(tmp_path: Path):
    mod = _load_pilot_mod()
    out = tmp_path / "pilot_field"
    summary = mod.run_pilot(
        mode="offline",
        fixture_root=FIXTURE_ROOT,
        out_dir=out,
        generated_at=GEN_AT,
    )
    assert summary.get("field_ops_allow_ml_live_in_fusion") is False
    for s in summary.get("sites") or []:
        assert s.get("field_ops_allow_ml_live_in_fusion") is False
        contrast = s.get("contrast_field_ops") or {}
        dec = contrast.get("decision")
        assert dec in {"HOLD", "ABSTAIN"}
        card_fo = json.loads(
            (out / "sites" / s["site_id"] / "decision_card_field_ops.json").read_text(
                encoding="utf-8"
            )
        )
        snap = (card_fo.get("audit") or {}).get("policy_snapshot") or {}
        assert snap.get("allow_ml_live_in_fusion") is False
        metrics = card_fo.get("metrics") or {}
        assert metrics.get("allow_ml_live_in_fusion") is False
        # T8b: research GO → field ABSTAIN must cite a documented non-GO path
        # (fail-closed reliability, action threshold, or require_ops) — not any "ops" substring.
        if s.get("decision") == "GO" and dec == "ABSTAIN":
            reasons = " ".join(str(r) for r in (card_fo.get("reasons") or []))
            reasons_l = reasons.lower()
            assert (
                "field_ops_fail_closed_reliability_unverified" in reasons
                or "below_action_threshold" in reasons_l
                or "require_ops_for_go" in reasons_l
                or "ops required" in reasons_l
                or "missing:ops" in reasons_l
                or "missing ops" in reasons_l
            ), f"unexpected field_ops ABSTAIN reasons: {reasons}"


def test_live_path_catalog_iou_honesty(tmp_path: Path):
    """T9: confidence_pred is not catalog holdout 0.8963; provenance flag true."""
    mod = _load_pilot_mod()
    out = tmp_path / "pilot_t9"
    summary = mod.run_pilot(
        mode="offline",
        fixture_root=FIXTURE_ROOT,
        out_dir=out,
        generated_at=GEN_AT,
        sites_filter=["nijar", "tobarra"],
    )
    for s in summary.get("sites") or []:
        conf = s.get("confidence_pred")
        if conf is not None:
            assert abs(float(conf) - 0.8963) > 1e-9
        flags = s.get("honesty_flags") or {}
        assert flags.get("catalog_iou_is_provenance_only") is True
        card = json.loads(
            (out / "sites" / s["site_id"] / "decision_card.json").read_text(encoding="utf-8")
        )
        live_ids = {src.get("id") for src in (card.get("sources") or []) if isinstance(src, dict)}
        assert "ml_live_reliability" in live_ids or "ml_live" in live_ids
    report = (out / "report" / "PILOT_HONESTY_CARD.md").read_text(encoding="utf-8")
    assert "provenance only" in report
    assert "Catalog holdout" in report


def test_report_pure_render_budget_and_substrings():
    mod = _load_pilot_mod()
    demo = _load_demo_mod()
    u1 = demo.load_u1_honesty_snapshot()
    facts = {
        "schema": "pilot_honesty_facts_table_v1",
        "rows": [
            {
                "site_id": "tobarra",
                "display_name": "Tobarra",
                "track": "OPS",
                "sources": "ops+ml_live",
                "decision_research_open": "HOLD",
                "confidence_pred": 0.6,
                "live_ok": True,
                "live_available": True,
                "live_abstained": False,
                "allow_ml_live_in_fusion": True,
                "decision_field_ops": "ABSTAIN",
                "key_number_label": "primary_ros_m_min",
                "key_number_value": 6.752,
                "key_number_source": "operational_metrics.speed_median_m_min",
                "pack_verdict": None,
                "honesty_note": "Sin Vp táctica",
            },
            {
                "site_id": "nijar",
                "display_name": "Níjar",
                "track": "OPEN_AND",
                "sources": "open+ml_live",
                "decision_research_open": "HOLD",
                "confidence_pred": 0.55,
                "live_ok": True,
                "live_available": True,
                "live_abstained": False,
                "allow_ml_live_in_fusion": True,
                "decision_field_ops": "HOLD",
                "key_number_label": "area_ha",
                "key_number_value": 2169.34,
                "key_number_source": "metrics_o2.area_rediam_ha",
                "pack_verdict": "GO_OPEN_AND_O2",
                "honesty_note": "Sin Vp táctica; open HOLD",
            },
            {
                "site_id": "caminomorisco",
                "display_name": "Caminomorisco",
                "track": "OPEN_EXT",
                "sources": "open+ml_live",
                "decision_research_open": "HOLD",
                "confidence_pred": 0.4,
                "live_ok": False,
                "live_available": True,
                "live_abstained": True,
                "allow_ml_live_in_fusion": True,
                "decision_field_ops": "HOLD",
                "key_number_label": "area_ha",
                "key_number_value": 2679.14,
                "key_number_source": "metrics_o2.area_rai_ha",
                "pack_verdict": "PARTIAL",
                "honesty_note": "Sin Vp táctica; open HOLD",
            },
        ],
    }
    site_summaries = [
        {
            "site_id": r["site_id"],
            "decision": r["decision_research_open"],
            "confidence_pred": r["confidence_pred"],
            "live_ok": r["live_ok"],
            "honesty_flags": {
                "vp_invented": False,
                "sources_incomplete": False,
            },
            "contrast_field_ops": {"decision": r["decision_field_ops"]},
        }
        for r in facts["rows"]
    ]
    body = mod.render_report(
        facts,
        site_summaries,
        u1,
        generated_at=GEN_AT,
        pilot_manifest={
            "policy_id": "research_open",
            "product_id": "clm_ensemble_v34",
            "out_dir": "outputs/pilot_honesty_card",
        },
    )
    nonempty = [ln for ln in body.splitlines() if ln.strip()]
    words = body.split()
    assert len(nonempty) <= 90
    assert len(words) <= 1200
    assert GEN_AT in body
    assert "field_ops" in body and "OFF" in body
    assert "provenance only" in body
    assert "No es orden táctica" in body
    assert "Not a tactical dispatch" not in body
    assert "Ops" in body and "ML" in body
    assert "Tobarra" in body and "Níjar" in body and "Caminomorisco" in body
    assert (
        "field_ops_fail_closed_reliability_unverified" in body
        or "sin R1–R4 inventados" in body
        or "No inventa R1–R4" in body
    )
    # Spanish UI labels (human-facing); no Python bools
    assert "Generado:" in body
    assert "Tabla de hechos" in body or "Cifra clave" in body
    assert "Modo presentación" in body
    assert "Contraste de políticas" in body or "Contraste field_ops" in body
    assert "confianza" in body
    assert "True" not in body and "False" not in body
    assert "sí" in body or "no" in body
    assert "se calla" in body
    # u1_source labeling
    assert "U1 TEST honest" in body
    assert u1.get("u1_source") in body
    # numbers come from facts (interpolated), not silent invent
    assert "2169.34" in body or "2169.340" in body
    assert "6.752" in body

    portal = mod.render_pilot_portal_html(
        facts,
        site_summaries,
        u1,
        generated_at=GEN_AT,
        pilot_manifest={
            "policy_id": "research_open",
            "product_id": "clm_ensemble_v34",
            "out_dir": "outputs/pilot_honesty_card",
        },
    )
    assert 'lang="es"' in portal
    assert "pill go" in portal or "pill hold" in portal or "pill abstain" in portal
    assert "research_open" in portal and "field_ops" in portal
    assert "No es orden táctica" in portal
    assert "Not a tactical dispatch" not in portal
    assert "provenance only" in portal
    assert "se calla" in portal  # field_ops ABSTAIN on Tobarra unit fixture
    assert "sitios OK" in portal
    assert "confianza" in portal
    assert "Saltar al contenido" in portal
    assert ">sí<" in portal or ">no<" in portal
    assert portal.count("se calla") >= 1
    # Single silence chip next to pill (not duplicated in chips row)
    assert "contraste: se calla" not in portal


def test_cli_bare_fixture_root(tmp_path: Path):
    out = tmp_path / "cli_pilot"
    r = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--mode",
            "offline",
            "--fixture-root",
            str(FIXTURE_ROOT),
            "--out-dir",
            str(out),
            "--generated-at",
            GEN_AT,
            "--json",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )
    assert r.returncode == 0, r.stderr
    payload = json.loads(r.stdout)
    assert payload["n_ok"] == 3
    assert (out / "report" / "PILOT_HONESTY_CARD.md").is_file()
    assert (out / "index.html").is_file()
    assert "No es orden táctica" in (out / "index.html").read_text(encoding="utf-8")


def test_load_catalog_fixture_root_total():
    mod = _load_pilot_mod()
    catalog, source = mod.load_catalog(sites_config=None, fixture_root=FIXTURE_ROOT)
    assert catalog.get("schema") == "pilot_sites_catalog_v1"
    assert len(catalog.get("sites") or []) == 3
    assert "fixture_root" in source


def test_fixture_root_without_pilot_sites_json_falls_through(tmp_path: Path):
    """Empty fixture-root (no pilot_sites.json) → warn + builtin production catalog."""
    import warnings

    mod = _load_pilot_mod()
    empty_root = tmp_path / "empty_fixture_root"
    empty_root.mkdir()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        catalog, source = mod.load_catalog(sites_config=None, fixture_root=empty_root)
    assert source == "builtin_production"
    assert catalog.get("schema") == "pilot_sites_catalog_v1"
    assert any(
        getattr(w, "message", None) is not None
        and "fixture_root_without_pilot_sites_json" in str(w.message)
        for w in caught
    )


def test_allow_missing_pack_skips_without_fake_card(tmp_path: Path):
    """--allow-missing-pack → SKIP summary, no decision_card pretend-success."""
    mod = _load_pilot_mod()
    empty_root = tmp_path / "missing_packs"
    empty_root.mkdir()
    catalog = {
        "schema": "pilot_sites_catalog_v1",
        "sites": [
            {
                "site_id": "ghost",
                "display_name": "Ghost",
                "track": "OPEN_AND",
                "event_id": "pilot_ghost",
                "work_dir": None,
                "open_pack": "does_not_exist_pack",
                "anchor_key": None,
                "anchors_path": None,
                "ml_scenario": "hold",
                "ml_prediction": None,
            }
        ],
    }
    cat_path = empty_root / "pilot_sites.json"
    cat_path.write_text(json.dumps(catalog), encoding="utf-8")
    out = tmp_path / "skip_out"
    summary = mod.run_pilot(
        mode="offline",
        fixture_root=empty_root,
        out_dir=out,
        generated_at=GEN_AT,
        allow_missing_pack=True,
    )
    assert summary.get("n_skipped") == 1
    assert summary.get("n_ok") == 0
    site = (summary.get("sites") or [])[0]
    assert site.get("skipped") is True
    assert site.get("honesty_flags", {}).get("sources_incomplete") is True
    assert not (out / "sites" / "ghost" / "decision_card.json").is_file()
    assert (out / "sites" / "ghost" / "site_summary.json").is_file()
