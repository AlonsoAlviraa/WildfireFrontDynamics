"""CLI contract tests for teach / show / demo-third-party / decide --explain."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

from wildfire_front.cli import build_parser, main
from wildfire_front.product import teach_path

ROOT = Path(__file__).resolve().parents[1]


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


def test_teach_exit_0_and_acts(capsys):
    code, out, _err = _run_main(["teach"], capsys)
    assert code == 0
    assert "Acto 1" in out or "acto 1" in out.lower()
    assert "Acto 2" in out
    assert "Acto 3" in out
    assert "Acto 4" in out
    assert "fusion" in out.lower() or "OFF" in out
    assert "field_ops" in out.lower() or "ML fusion=OFF" in out or "fusion=OFF" in out


def test_teach_act_filter(capsys):
    code, out, _err = _run_main(["teach", "--act", "3"], capsys)
    assert code == 0
    assert "decide" in out.lower() or "Decidir" in out
    assert "multi_ccaa" not in out.lower() and "multi-CCAA" not in out
    # Act 1 keywords should be absent
    assert "build_demo_multi_ccaa" not in out


def test_teach_json_schema(capsys):
    code, out, _err = _run_main(["teach", "--json"], capsys)
    assert code == 0
    data = json.loads(out)
    assert data["schema"] == "wfd_teach_path_v1"
    assert len(data["acts"]) == 4
    assert data["rails"]["GO_Q"] != True  # noqa: E712 — never invent complete true claim
    assert data["rails"]["ml_product_go"] is True
    assert data["rails"]["field_ops_ml_live_fusion"] == "OFF"
    assert data["course"].endswith("CURSO_WFD_PARA_DESCONOCIDOS.md")
    assert "CHEATSHEET" in data["cheatsheet"]


def test_show_reads_gates(capsys):
    code, out, _err = _run_main(["show"], capsys)
    assert code == 0
    assert "GO_MES" in out
    assert "true" in out.lower() or "True" in out
    assert "partial" in out.lower()
    assert "OFF" in out
    assert "ml_product_go" in out.lower() or "ml_product_go" in out


def test_show_json_never_go_q_true(capsys):
    code, out, _err = _run_main(["show", "--json"], capsys)
    assert code == 0
    data = json.loads(out)
    assert data["schema"] == "wfd_show_snapshot_v1"
    go_q = data["gates"]["GO_Q"]
    # Must not be boolean True or claim complete
    assert go_q is not True
    assert go_q != "true"
    assert go_q != "complete"
    assert data["gates"]["field_ops_ml_live_fusion"] == "OFF"
    assert data["gates"]["ml_product_go"] is True


def test_show_missing_pack_ok(capsys, monkeypatch, tmp_path: Path):
    """Missing pack is informational — exit 0, presence false (isolated root)."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "config").mkdir()
    (tmp_path / "docs" / "GO_MES_VERDICT.json").write_text(
        json.dumps({"GO_MES": True, "GO_MES_plus": False}), encoding="utf-8"
    )
    (tmp_path / "docs" / "PLAN_1_MES_GRAPH_V6_STATUS.json").write_text(
        json.dumps(
            {
                "rails": {
                    "GO_MES": True,
                    "GO_Q": "partial",
                    "ml_product_go": True,
                    "field_ops_ml_live_fusion": "OFF",
                },
                "gates": {"GO_Q": {"met": False, "status": "partial"}},
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "config" / "decision_policies.json").write_text(
        json.dumps({"policies": {"field_ops": {"allow_ml_live_in_fusion": False}}}),
        encoding="utf-8",
    )

    snap = teach_path.load_gate_snapshot(tmp_path)
    assert snap["repo_root"] == str(tmp_path)
    assert snap["presence"]["demo_third_party"] is False
    assert snap["gates"]["GO_Q"] == "partial"
    assert snap["gates"]["GO_MES"] is True

    text = teach_path.format_show_human(snap)
    assert "MISSING" in text
    assert "partial" in text

    # CLI show with isolated snapshot (monkeypatch) — pack-less root, exit 0
    def _fake_snap():
        return snap

    monkeypatch.setattr("wildfire_front.cli_teach.load_gate_snapshot", _fake_snap)
    code, out, _err = _run_main(["show"], capsys)
    assert code == 0
    assert "MISSING" in out
    assert "partial" in out


def test_demo_third_party_skip_build_missing(capsys, tmp_path: Path):
    empty = tmp_path / "no_such_bundle"
    code, _out, err = _run_main(
        [
            "demo-third-party",
            "--skip-build",
            "--output",
            str(empty),
            "--no-replay",
        ],
        capsys,
    )
    # With --no-replay and skip-build on missing: design says exit 1 for missing bundle
    assert code == 1
    assert "missing" in err.lower() or "error" in err.lower() or code == 1


def test_demo_third_party_replay_ok(tmp_path: Path, capsys):
    """Build pack to tmp via importlib then wrap CLI --skip-build --replay."""
    mod_path = ROOT / "scripts" / "build_demo_third_party_pack.py"
    if not mod_path.is_file():
        pytest.skip("build script missing")
    spec = importlib.util.spec_from_file_location("build_demo_tp", mod_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    # Ensure ROOT on path for script imports
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec.loader.exec_module(mod)
    out = tmp_path / "demo_third_party"
    summary = mod.build_pack(out, make_zip=False)
    assert summary.get("self_replay_ok") is True

    code, stdout, err = _run_main(
        [
            "demo-third-party",
            "--skip-build",
            "--output",
            str(out),
            "--replay",
        ],
        capsys,
    )
    assert code == 0, f"stdout={stdout}\nerr={err}"
    assert "replay_ok" in stdout.lower() or "True" in stdout
    assert "cryptographic" in stdout.lower() or "forensic" in stdout.lower()


def test_demo_third_party_replay_exit_2(tmp_path: Path, capsys, monkeypatch):
    """replay_ok False → exit 2 (design §4.5.4)."""
    out = tmp_path / "bundle"
    out.mkdir()
    (out / "replay_sources.json").write_text("{}", encoding="utf-8")

    def _fake_replay(bundle, base=None):  # noqa: ANN001
        return {
            "replay_ok": False,
            "expected_decision": "GO",
            "got_decision": "ABSTAIN",
            "match_decision": False,
            "match_output_hash": False,
        }

    monkeypatch.setattr(
        "wildfire_front.product.forensics.load_and_replay_bundle",
        _fake_replay,
    )
    code, stdout, _err = _run_main(
        [
            "demo-third-party",
            "--skip-build",
            "--output",
            str(out),
            "--replay",
        ],
        capsys,
    )
    assert code == 2
    assert "replay_ok" in stdout.lower() or "False" in stdout


def test_demo_third_party_build_self_replay_warn_no_replay(tmp_path: Path, capsys, monkeypatch):
    """Build self_replay_ok false + --no-replay → exit 2."""

    class _FakeBuild:
        @staticmethod
        def build_pack(out, *, make_zip=True, dist_dir=None):  # noqa: ANN001
            Path(out).mkdir(parents=True, exist_ok=True)
            return {
                "self_replay_ok": False,
                "decision": "GO",
                "policy_id": "field_ops",
                "zip_path": None,
                "out_dir": str(out),
            }

    monkeypatch.setattr(
        "wildfire_front.cli_teach._load_script_module",
        lambda name, rel, repo: _FakeBuild(),
    )
    code, stdout, _err = _run_main(
        [
            "demo-third-party",
            "--output",
            str(tmp_path / "pack"),
            "--no-replay",
            "--no-zip",
        ],
        capsys,
    )
    assert code == 2
    assert "WARN_REPLAY" in stdout or "build" in stdout.lower()


def test_decide_explain_abstain(capsys):
    code, out, _err = _run_main(
        ["decide", "--policy", "field_ops", "--explain"],
        capsys,
    )
    assert code == 0
    assert "ABSTAIN" in out or "abstain" in out.lower()
    assert "Sources" in out or "sources" in out.lower()
    assert "Reasons" in out or "reasons" in out.lower()
    assert "OFF" in out or "fusion" in out.lower()


def test_decide_explain_with_json_noop(capsys):
    code, out, _err = _run_main(
        ["decide", "--policy", "field_ops", "--json", "--explain"],
        capsys,
    )
    assert code == 0
    data = json.loads(out)
    # Pure card JSON — not dual-format teach wrapper
    assert "decision" in data
    assert data.get("schema") != "wfd_teach_path_v1"
    assert "acts" not in data


def test_parser_help_lists_new_commands():
    parser = build_parser()
    help_text = parser.format_help()
    assert "teach" in help_text
    assert "show" in help_text
    assert "demo-third-party" in help_text

    # Subparser for decide has --explain
    # parse with --explain should not error
    args = parser.parse_args(["decide", "--policy", "field_ops", "--explain"])
    assert getattr(args, "explain", False) is True

    args_t = parser.parse_args(["teach", "--act", "2"])
    assert args_t.command == "teach"
    assert args_t.act == 2

    args_d = parser.parse_args(["demo-third-party", "--no-replay"])
    assert args_d.command == "demo-third-party"
    assert args_d.replay is False


def test_format_decide_explain_shape():
    card: dict[str, Any] = {
        "decision": "ABSTAIN",
        "confidence_pred": 0.0,
        "confidence_pred_label": "NONE",
        "system_reliability_pass": False,
        "latency_ms": 1,
        "policy_id": "field_ops",
        "sources": [],
        "reasons": ["no_actionable_sources"],
        "disclaimers": ["Not a tactical dispatch order."],
        "metrics": {"allow_ml_live_in_fusion": False, "policy_id": "field_ops"},
        "audit": {
            "policy_id": "field_ops",
            "policy_snapshot": {
                "require_ops_for_go": True,
                "allow_ml_live_in_fusion": False,
            },
        },
    }
    text = teach_path.format_decide_explain(card, field_ops_fusion_rail="OFF")
    assert "ABSTAIN" in text
    assert "Sources" in text
    assert "Reasons" in text
    assert "Disclaimers" in text
    assert "field_ops ML live fusion: OFF" in text
    assert "field_ops allow_ml_live_in_fusion: OFF" in text
    assert "IoU" in text


def test_format_decide_explain_research_open_does_not_label_field_ops_on():
    """research_open may enable this_run fusion; field_ops rail must stay OFF."""
    card: dict[str, Any] = {
        "decision": "HOLD",
        "confidence_pred": 0.5,
        "confidence_pred_label": "MEDIUM",
        "system_reliability_pass": False,
        "latency_ms": 2,
        "policy_id": "research_open",
        "sources": [
            {
                "id": "ml_live",
                "available": True,
                "weight": 0.3,
                "confidence": 0.6,
                "actionable": True,
                "role": "live_ml",
            }
        ],
        "reasons": ["policy:research_open", "ml_live:fused"],
        "disclaimers": ["Experimental research_open only."],
        "metrics": {
            "allow_ml_live_in_fusion": True,
            "policy_id": "research_open",
        },
        "audit": {
            "policy_id": "research_open",
            "policy_snapshot": {
                "require_ops_for_go": False,
                "allow_ml_live_in_fusion": True,
            },
        },
    }
    text = teach_path.format_decide_explain(card, field_ops_fusion_rail="OFF")
    assert "this_run policy allow_ml_live: ON" in text
    assert "allow_ml_live_in_fusion (effective): True" in text
    assert "field_ops allow_ml_live_in_fusion: OFF" in text
    assert "field_ops ML live fusion: OFF" in text
    # Must never teach that field_ops fusion is ON when only research_open is hot
    assert "field_ops ML live fusion: ON" not in text
    assert "field_ops allow_ml_live_in_fusion: ON" not in text


def test_resolve_repo_root_honors_explicit_preferred(tmp_path: Path):
    """Explicit preferred root is never replaced by cwd even if docs missing."""
    empty = tmp_path / "empty_root"
    empty.mkdir()
    resolved = teach_path.resolve_repo_root(empty)
    assert resolved == empty
    # cwd would be monorepo under CI; preferred must still win
    assert resolved != Path.cwd() or empty.resolve() == Path.cwd().resolve()


def test_load_gate_snapshot_never_defaults_go_q_true(tmp_path: Path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "config").mkdir()
    # No GO_MES / plan files → GO_Q/GO_MES must be unknown (not invent true)
    snap = teach_path.load_gate_snapshot(tmp_path)
    assert snap["repo_root"] == str(tmp_path)
    assert snap["gates"]["GO_Q"] == "unknown"
    assert snap["gates"]["GO_MES"] == "unknown"
    assert snap["gates"]["GO_Q"] is not True
    assert snap["gates"]["ml_product_go"] is True
    assert snap["gates"]["field_ops_ml_live_fusion"] == "OFF"


def test_cheatsheet_exists_and_has_key_strings():
    path = ROOT / "docs" / "CHEATSHEET_DEMO_12MIN.md"
    if not path.is_file():
        pytest.skip("cheatsheet not yet written")
    text = path.read_text(encoding="utf-8")
    assert "Acto 1" in text or "acto 1" in text.lower()
    assert "demo-third-party" in text
    assert "fusion" in text.lower()
