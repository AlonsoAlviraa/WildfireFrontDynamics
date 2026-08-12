"""Tests for H3 dry-run path + H1 acta record (mocks / temp files)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_script(name: str, rel: str):
    path = ROOT / rel
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    # Ensure scripts can import each other
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def h3_mod():
    return _load_script("wfd_run_h3_dry_run_path", "scripts/run_h3_dry_run_path.py")


@pytest.fixture(scope="module")
def record_mod():
    return _load_script("wfd_record_h1", "scripts/record_h1_demo_complete.py")


@pytest.fixture(scope="module")
def prep_mod():
    return _load_script("wfd_prepare_h1", "scripts/prepare_h1_acta_draft.py")


def test_aggregate_report_schema_and_honesty(h3_mod):
    steps = [
        {"id": "teach", "ok": True, "rc": 0, "detail": "ok"},
        {
            "id": "show",
            "ok": True,
            "rc": 0,
            "detail": {},
            "gates": {"GO_Q": "partial", "field_ops_ml_live_fusion": "OFF", "GO_MES": True},
        },
        {"id": "cheatsheet", "ok": True, "rc": 0, "detail": "docs/CHEATSHEET_DEMO_12MIN.md"},
        {"id": "demo_third_party", "ok": True, "rc": 0, "detail": {"replay_ok": True}},
    ]
    report = h3_mod.aggregate_report(
        steps,
        human_attestation_pending=True,
        h1_status="NOT_STARTED",
        utc="2026-08-04T00:00:00+00:00",
    )
    assert report["schema"] == "wfd_h3_dry_run_v1"
    assert report["h3_eng_path_ok"] is True
    assert report["h3_human_attestation_pending"] is True
    assert report["go_q_met"] is False
    assert report["gates"]["GO_Q"] == "partial"
    assert report["gates"]["field_ops_ml_live_fusion"] == "OFF"
    assert len(report["steps"]) == 4


def test_aggregate_report_fails_if_step_fails(h3_mod):
    steps = [
        {"id": "teach", "ok": True, "rc": 0},
        {"id": "show", "ok": False, "rc": 1},
        {"id": "cheatsheet", "ok": True, "rc": 0},
        {"id": "demo_third_party", "ok": True, "rc": 0},
    ]
    report = h3_mod.aggregate_report(steps, human_attestation_pending=True)
    assert report["h3_eng_path_ok"] is False
    assert report["go_q_met"] is False
    assert report["h3_human_attestation_pending"] is True


def test_run_path_with_mocked_runners(h3_mod, tmp_path: Path):
    """Full run_path aggregation with pure mocks (no real pack build)."""
    cheat = ROOT / "docs" / "CHEATSHEET_DEMO_12MIN.md"
    assert cheat.is_file(), "cheatsheet must exist in repo for this test"

    def teach_runner():
        return 0, "=== Acto 1 — Ver ===\nActo 2\nActo 3\nActo 4\n"

    def show_runner():
        data = {
            "schema": "wfd_show_snapshot_v1",
            "gates": {
                "GO_MES": True,
                "GO_Q": "partial",
                "field_ops_ml_live_fusion": "OFF",
                "ml_product_go": True,
            },
        }
        return 0, data, json.dumps(data)

    def demo_runner():
        return 0, {
            "build": "OK",
            "replay_ok": True,
            "decision": "HOLD",
            "out": str(tmp_path),
        }

    out_dir = tmp_path / "demo_third_party"
    report, code = h3_mod.run_path(
        no_zip=True,
        out_dir=out_dir,
        teach_runner=teach_runner,
        show_runner=show_runner,
        demo_runner=demo_runner,
    )
    assert code == 0
    assert report["h3_eng_path_ok"] is True
    assert report["h3_human_attestation_pending"] is True
    assert report["go_q_met"] is False
    assert (out_dir / "H3_DRY_RUN_REPORT.json").is_file()
    assert (out_dir / "H3_DRY_RUN_REPORT.md").is_file()
    data = json.loads((out_dir / "H3_DRY_RUN_REPORT.json").read_text(encoding="utf-8"))
    assert data["schema"] == "wfd_h3_dry_run_v1"


def test_show_step_rejects_go_q_true(h3_mod):
    def bad_show():
        data = {
            "gates": {
                "GO_Q": True,
                "field_ops_ml_live_fusion": "OFF",
            }
        }
        return 0, data, json.dumps(data)

    step = h3_mod.run_show_step(runner=bad_show)
    assert step["ok"] is False
    assert step["detail"]["go_q_not_true"] is False


def test_show_step_rejects_fusion_on(h3_mod):
    def bad_show():
        data = {
            "gates": {
                "GO_Q": "partial",
                "field_ops_ml_live_fusion": "ON",
            }
        }
        return 0, data, json.dumps(data)

    step = h3_mod.run_show_step(runner=bad_show)
    assert step["ok"] is False


def test_validate_acta_empty_fails(h3_mod):
    text = """
| **Fecha** | YYYY-MM-DD |
| **Presentador** | | | |
| **Tercero (externo)** | | | |
"""
    v = h3_mod.validate_acta_fields(text)
    assert v["ok"] is False
    assert any("fecha" in p for p in v["problems"])


def test_validate_acta_filled_ok(h3_mod):
    text = """
| **Fecha** | 2026-08-10 |
| Rol | Nombre | Org |
| **Presentador** | Ana Pérez | WFD |
| **Tercero (externo)** | Dr. Luis Gómez | INFOCAM |
"""
    v = h3_mod.validate_acta_fields(text)
    assert v["ok"] is True
    assert v["fecha"] == "2026-08-10"
    assert "Ana" in (v["presentador"] or "")
    assert "Luis" in (v["tercero"] or "")


def test_record_h1_empty_acta_exit_2(record_mod, tmp_path: Path):
    acta = tmp_path / "ACTA_DEMO_empty.md"
    acta.write_text(
        """# Acta
| **Fecha** | YYYY-MM-DD |
| **Presentador** | |
| **Tercero (externo)** | |
""",
        encoding="utf-8",
    )
    status = tmp_path / "status.json"
    status.write_text(
        json.dumps(
            {
                "rails": {"GO_Q": "partial"},
                "gates": {
                    "M3.2": {"met": False, "status": "PENDING"},
                    "GO_Q": {"met": False, "status": "partial"},
                },
                "tracks": {"H": {"items": {"H1_demo_acta": "TODO"}}},
            }
        ),
        encoding="utf-8",
    )
    code, payload = record_mod.record(acta_path=acta, status_path=status)
    assert code == 2
    assert payload["ok"] is False
    # status must not be mutated
    st = json.loads(status.read_text(encoding="utf-8"))
    assert st["rails"]["GO_Q"] == "partial"
    assert st["tracks"]["H"]["items"]["H1_demo_acta"] == "TODO"


def test_record_h1_pending_human_name_refused(record_mod, tmp_path: Path):
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
    status.write_text(
        json.dumps(
            {
                "rails": {"GO_Q": "partial"},
                "gates": {"M3.2": {"met": False}, "GO_Q": {"met": False}},
                "tracks": {"H": {"items": {"H1_demo_acta": "TODO"}}},
            }
        ),
        encoding="utf-8",
    )
    code, payload = record_mod.record(acta_path=acta, status_path=status)
    assert code == 2
    assert "PENDING_HUMAN" in (payload.get("error") or "")


def test_record_h1_filled_updates_status(record_mod, tmp_path: Path):
    acta = tmp_path / "ACTA_DEMO_20260810_infocam.md"
    acta.write_text(
        """# Acta demo
| **Fecha** | 2026-08-10 |
| Rol | Nombre | Org |
| **Presentador** | Ana Pérez | WFD |
| **Tercero (externo)** | Dr. Luis Gómez | INFOCAM |
""",
        encoding="utf-8",
    )
    status = tmp_path / "status.json"
    status.write_text(
        json.dumps(
            {
                "schema": "plan_1_mes_graph_v6_status",
                "rails": {"GO_Q": "partial", "GO_MES": True},
                "gates": {
                    "M3.2": {"met": False, "status": "PENDING", "templates_ready": True},
                    "GO_Q": {"met": False, "status": "partial"},
                },
                "tracks": {"H": {"items": {"H1_demo_acta": "TODO"}, "evidence": {}}},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    code, payload = record_mod.record(acta_path=acta, status_path=status)
    assert code == 0
    assert payload["ok"] is True
    st = json.loads(status.read_text(encoding="utf-8"))
    assert st["gates"]["M3.2"]["met"] is True
    assert st["gates"]["M3.2"]["status"] == "DONE"
    assert st["tracks"]["H"]["items"]["H1_demo_acta"] == "DONE"
    assert st["rails"]["GO_Q"] is True
    assert st["gates"]["GO_Q"]["met"] is True


def test_record_h1_dry_run_no_write(record_mod, tmp_path: Path):
    acta = tmp_path / "ACTA_DEMO_20260810_x.md"
    acta.write_text(
        """
| **Fecha** | 2026-08-10 |
| **Presentador** | Ana Pérez | WFD |
| **Tercero (externo)** | Luis Gómez | Org |
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
        "tracks": {"H": {"items": {"H1_demo_acta": "TODO"}, "evidence": {}}},
    }
    status.write_text(json.dumps(original), encoding="utf-8")
    code, payload = record_mod.record(acta_path=acta, status_path=status, dry_run=True)
    assert code == 0
    assert payload.get("dry_run") is True
    st = json.loads(status.read_text(encoding="utf-8"))
    assert st["rails"]["GO_Q"] == "partial"


def test_prepare_h1_draft(prep_mod, tmp_path: Path):
    template = ROOT / "docs" / "ACTA_DEMO_TERCERO_TEMPLATE.md"
    out = tmp_path / "ACTA_DEMO_PENDING_HUMAN.md"
    path = prep_mod.prepare(template=template, out=out, force=True)
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "BORRADOR" in text or "NO firmado" in text
    assert "NO cierra GO_Q" in text or "GO_Q" in text
    assert "Presentador" in text


def test_cli_dry_run_h3_registered():
    from wildfire_front.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["dry-run-h3", "--no-zip"])
    assert args.command == "dry-run-h3"
    assert args.no_zip is True
