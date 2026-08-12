"""H1 prep rails (SPA C2 pointers, go_q_met false) + ML closeout claim pack markers."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    path = ROOT / rel
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def prepare_mod():
    return _load("wfd_prepare_h1_session", "scripts/prepare_h1_demo_session.py")


@pytest.fixture(scope="module")
def record_mod():
    return _load("wfd_record_h1_prep", "scripts/record_h1_demo_complete.py")


@pytest.fixture(scope="module")
def ml_verify_mod():
    return _load("wfd_verify_ml_closeout", "scripts/verify_ml_closeout_claims.py")


def test_prepare_h1_session_rails_and_spa_entry(prepare_mod, tmp_path: Path, monkeypatch):
    """Real prepare_h1_demo_session.main builds session JSON with go_q_met false + SPA C2."""
    # Point artifacts into tmp by monkeypatching module paths
    out_json = tmp_path / "H1_DEMO_SESSION_READY.json"
    invite = tmp_path / "H1_CALENDAR_INVITE.md"
    draft = tmp_path / "ACTA_DEMO_PENDING_HUMAN.md"
    draft.write_text("# PENDING draft\n| **Fecha** | |\n", encoding="utf-8")
    cheatsheet = ROOT / "docs" / "CHEATSHEET_DEMO_12MIN.md"
    runbook = ROOT / "docs" / "H1_GO_Q_RUNBOOK.md"

    monkeypatch.setattr(prepare_mod, "OUT_JSON", out_json)
    monkeypatch.setattr(prepare_mod, "INVITE_MD", invite)
    monkeypatch.setattr(prepare_mod, "DRAFT", draft)
    monkeypatch.setattr(prepare_mod, "CHEATSHEET", cheatsheet)
    monkeypatch.setattr(prepare_mod, "RUNBOOK", runbook)
    monkeypatch.setattr(prepare_mod, "ROOT", ROOT)

    def fake_run(cmd: list[str]):
        # prepare_acta: ok; dry_run: ok; record pending: must be exit 2; flags: 0
        joined = " ".join(cmd)
        if "record_h1_demo_complete" in joined:
            return 2, "refusing PENDING"
        if "check_release_flags" in joined:
            return 0, "PASS"
        if "prepare_h1_acta_draft" in joined:
            return 0, "draft ok"
        if "dry_run_demo_third_party" in joined:
            return 0, '{"ok": true}'
        return 0, ""

    monkeypatch.setattr(prepare_mod, "_run", fake_run)

    code = prepare_mod.main(["--skip-dry-run"])
    assert code == 0
    assert out_json.is_file()
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["go_q_met"] is False
    assert payload.get("go_q_invent_forbidden") is True
    rails = payload["rails"]
    assert rails["GO_Q"] == "partial"
    assert rails["field_ops_fusion"] == "OFF"
    assert rails.get("go_q_met") is False
    demo = payload["demo_entry"]
    assert "app" in demo["primary"]
    assert "wildfire_front app" in demo["primary"]
    assert demo["surface"] == "industrial_spa_c2"
    assert "Estado" in demo["primary_acts"]
    assert "CHEATSHEET_DEMO_12MIN" in demo["cheatsheet"].replace("\\", "/")
    assert "H1_GO_Q_RUNBOOK" in demo["runbook"].replace("\\", "/")
    arts = payload["artifacts"]
    assert "spa_app" in arts or "outputs/app" in json.dumps(arts)
    invite_txt = invite.read_text(encoding="utf-8")
    assert "wildfire_front app" in invite_txt
    assert "fusion" in invite_txt.lower() and "OFF" in invite_txt


def test_record_h1_pending_does_not_mutate_status(record_mod, tmp_path: Path):
    """Real record() on PENDING_HUMAN path → exit 2, status file byte-stable."""
    acta = tmp_path / "ACTA_DEMO_PENDING_HUMAN.md"
    acta.write_text(
        """
| **Fecha** | 2026-08-10 |
| **Presentador** | Ana |
| **Tercero (externo)** | Luis |
""",
        encoding="utf-8",
    )
    status = tmp_path / "status.json"
    original = {
        "rails": {"GO_Q": "partial"},
        "gates": {
            "M3.2": {"met": False, "status": "PENDING"},
            "GO_Q": {"met": False, "status": "partial"},
        },
        "tracks": {"H": {"items": {"H1_demo_acta": "TODO"}}},
    }
    raw_before = json.dumps(original, sort_keys=True)
    status.write_text(json.dumps(original, indent=2), encoding="utf-8")
    before_mtime = status.read_text(encoding="utf-8")

    code, payload = record_mod.record(acta_path=acta, status_path=status)
    assert code == 2
    assert payload["ok"] is False
    after = status.read_text(encoding="utf-8")
    assert after == before_mtime
    st = json.loads(after)
    assert st["rails"]["GO_Q"] == "partial"
    assert st["gates"]["GO_Q"]["met"] is False
    assert st["tracks"]["H"]["items"]["H1_demo_acta"] == "TODO"
    # ensure we didn't flip GO_Q via accidental rewrite
    assert json.dumps(
        {
            "rails": st["rails"],
            "gates": st["gates"],
            "tracks": st["tracks"],
        },
        sort_keys=True,
    ) == json.dumps(
        {
            "rails": original["rails"],
            "gates": original["gates"],
            "tracks": original["tracks"],
        },
        sort_keys=True,
    )
    _ = raw_before


def test_ml_closeout_claim_pack_and_verify(ml_verify_mod, tmp_path: Path):
    """Real verify_ml_closeout_claims against in-repo stamps; pack markers present."""
    pack = ROOT / "docs" / "VERIFY_PACK_ML_CLOSEOUT.md"
    assert pack.is_file()
    text = pack.read_text(encoding="utf-8")
    for marker in (
        "FREEZE_ML",
        "field_ops_allow_ml_live_in_fusion",
        "iou_is_not_ros",
        "tobarra_keep",
        "ml_product_go",
        "ML_CLOSEOUT_DECISION",
    ):
        assert marker.lower() in text.lower() or marker in text

    report_json = tmp_path / "ml_report.json"
    report_md = tmp_path / "ml_report.md"
    code = ml_verify_mod.main(
        ["--report-json", str(report_json), "--report-md", str(report_md)]
    )
    assert code == 0
    rep = json.loads(report_json.read_text(encoding="utf-8"))
    assert rep["total"] >= 10
    assert rep["contradicted"] == 0
    assert rep["supported"] == rep["total"]
    assert rep.get("field_ops_fusion") == "OFF"
    assert rep.get("go_q_invent") is False
    assert rep.get("decision") == "FREEZE_ML_AND_REQUEST_DATA"
    rails = rep.get("rails_snapshot") or {}
    assert rails.get("field_ops_allow_ml_live_in_fusion") is False
    assert rails.get("iou_is_not_ros") is True
    md = report_md.read_text(encoding="utf-8")
    assert "supported" in md.lower()
    assert "FREEZE_ML_AND_REQUEST_DATA" in md


def test_ml_closeout_stamp_on_disk_rails():
    """Direct stamp path — no reimplemented oracle for fusion/KILL."""
    stamp = ROOT / "outputs" / "ml_eval" / "lab_loop" / "ML_CLOSEOUT_DECISION.json"
    if not stamp.is_file():
        pytest.skip("ML closeout stamp not present in workspace")
    data = json.loads(stamp.read_text(encoding="utf-8"))
    assert data["decision"] == "FREEZE_ML_AND_REQUEST_DATA"
    rails = data["rails"]
    assert rails["field_ops_allow_ml_live_in_fusion"] is False
    assert rails["iou_is_not_ros"] is True
    assert rails.get("tobarra_keep_reopen") is False
    sealed = data["champions_freeze"]["sealed_product_lofo"]
    assert sealed["config_id"] == "exact_force_ema_long"
    assert sealed["field_ops_allow_ml_live_in_fusion"] is False
