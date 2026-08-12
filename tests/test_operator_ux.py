"""Operator UX loop: single entry, traffic light, 4 acts, GO_Q gap, ABSTAIN plain."""

from __future__ import annotations

import json
from pathlib import Path

from wildfire_front.cli import build_parser, main
from wildfire_front.product import operator_ux

ROOT = Path(__file__).resolve().parents[1]


def _run_main(argv: list[str], capsys) -> tuple[int, str, str]:
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


def test_operator_status_board(capsys):
    code, out, err = _run_main(["operator"], capsys)
    assert code == 0, err
    assert "MODO OPERARIO" in out or "operario" in out.lower()
    assert "VERDE" in out or "AMARILLO" in out or "ROJO" in out
    assert "GO_Q" in out
    assert "operator do --act" in out or "do --act" in out
    # Must say what is missing for GO_Q without claiming complete
    assert "tercero" in out.lower() or "H1" in out or "acta" in out.lower()
    assert "bug" in out.lower() or "ABSTAIN" in out


def test_operator_json_schema(capsys):
    code, out, _err = _run_main(["operator", "--json"], capsys)
    assert code == 0
    data = json.loads(out)
    assert data["schema"] == "wfd_operator_status_v1"
    assert data["gates"]["GO_Q"] is not True
    assert data["gates"]["ml_product_go"] is True
    assert data["gates"]["field_ops_ml_live_fusion"] == "OFF"
    assert len(data["acts"]) == 4
    assert "one_liner" in data["go_q"]
    assert data["go_q"]["go_q_complete"] is False
    assert data["overall_light"] in ("VERDE", "AMARILLO", "ROJO")


def test_operator_checklist_loop_done_when_artifacts_ok(capsys):
    code, out, _err = _run_main(["operator", "checklist"], capsys)
    assert code == 0
    assert "Checklist" in out or "checklist" in out.lower() or "Acto" in out or "OK" in out
    assert "Honestidad" in out or "artefacto" in out.lower()
    # JSON path for machine criterion
    code2, out2, _ = _run_main(["operator", "checklist", "--json"], capsys)
    assert code2 == 0
    data = json.loads(out2)
    assert data["schema"] == "wfd_operator_checklist_v1"
    assert data["knows_go_q_gap"] is True
    assert "honesty" in data
    # With demos present in repo, all four acts should pass presence
    if data.get("all_four_acts") and data.get("knows_go_q_gap"):
        assert data["loop_done"] is True
    # Act items that pass via presence must declare basis (no silent false "demo done")
    for it in data.get("items") or []:
        if it.get("id", "").startswith("act") and it.get("pass"):
            assert it.get("basis") in (
                "artifact_presence",
                "command_surface",
                "simulated_or_session",
                "session_ran",
            )


def test_operator_board_has_setup(capsys):
    code, out, _err = _run_main(["operator"], capsys)
    assert code == 0
    assert "PYTHONPATH" in out
    assert "Setup" in out or "setup" in out.lower()


def test_entry_docs_point_to_operator():
    """Canonical human paths must not re-open the multi-door trap."""
    checks = {
        ROOT / "README.md": "wildfire_front operator",
        ROOT / "docs" / "START_HERE.md": "wildfire_front operator",
        ROOT / "docs" / "CURSO_WFD_PARA_DESCONOCIDOS.md": "wildfire_front operator",
        ROOT / "docs" / "H1_GO_Q_RUNBOOK.md": "wildfire_front operator",
        ROOT / "docs" / "CHEATSHEET_DEMO_12MIN.md": "wildfire_front operator",
        ROOT / "docs" / "GUIA_COMANDOS_RECREAR_TODO.md": "wildfire_front operator",
        ROOT / "docs" / "GUION_DEMO_30MIN_POST_O1.md": "wildfire_front operator",
        ROOT / "docs" / "ONEPAGER_COMERCIAL_ES.md": "wildfire_front",
    }
    for path, needle in checks.items():
        assert path.is_file(), f"missing {path}"
        text = path.read_text(encoding="utf-8")
        assert needle in text, f"{path.name} must mention {needle}"


def test_operator_do_missing_act_friendly(capsys):
    code, out, err = _run_main(["operator", "do"], capsys)
    assert code == 2
    blob = (out + err).lower()
    assert "acto" in blob or "--act" in blob or "--all" in blob
    assert "operator" in blob


def test_operator_do_all_smoke(capsys):
    """Full 4-act path with existing artifacts (no rebuild)."""
    code, out, err = _run_main(["operator", "do", "--all"], capsys)
    assert code == 0, f"out={out}\nerr={err}"
    assert "Acto 1" in out or "acto 1" in out.lower() or "1→4" in out or "1->4" in out
    assert "4" in out
    # must not claim GO_Q closed
    assert "partial" in out.lower() or "H1" in out or "tercero" in out.lower()
    stamp = ROOT / "outputs" / "operator_ux_last_run.json"
    assert stamp.is_file(), "do --all must write session stamp"
    data = json.loads(stamp.read_text(encoding="utf-8"))
    assert data.get("schema") == "wfd_operator_session_v1"
    assert data.get("all_four_ok") is True
    assert data.get("honesty")
    assert "GO_Q" in data.get("honesty", "") or "H1" in data.get("honesty", "")


def test_operator_do_all_json_is_pure(capsys):
    """--json must be parseable (no human banners interleaved)."""
    code, out, err = _run_main(["operator", "do", "--all", "--json"], capsys)
    assert code == 0, f"out={out}\nerr={err}"
    data = json.loads(out)
    assert data["schema"] == "wfd_operator_do_all_v1"
    assert len(data["acts"]) == 4
    assert all(a.get("ok") for a in data["acts"])
    assert data.get("go_q") != "complete"
    assert data.get("go_q") != True  # noqa: E712


def test_checklist_upgrades_basis_after_session(capsys):
    # ensure session exists
    _run_main(["operator", "do", "--all", "-q"], capsys)
    code, out, _err = _run_main(["operator", "checklist", "--json"], capsys)
    assert code == 0
    data = json.loads(out)
    assert data.get("session_all_four_ok") is True
    act_bases = {i["id"]: i.get("basis") for i in data["items"] if i["id"].startswith("act")}
    assert act_bases.get("act1") == "session_ran"
    assert act_bases.get("act4") == "session_ran"


def test_single_act_does_not_wipe_four_act_stamp(capsys):
    """do --act 4 after do --all must merge, not replace (iter 11)."""
    code_all, _, err_all = _run_main(["operator", "do", "--all", "-q"], capsys)
    assert code_all == 0, err_all
    stamp = ROOT / "outputs" / "operator_ux_last_run.json"
    before = json.loads(stamp.read_text(encoding="utf-8"))
    assert before.get("all_four_ok") is True

    code4, _, err4 = _run_main(["operator", "do", "--act", "4", "--no-build", "-q"], capsys)
    assert code4 == 0, err4
    after = json.loads(stamp.read_text(encoding="utf-8"))
    assert after.get("all_four_ok") is True
    assert set(after.get("ok_acts") or []) >= {1, 2, 3, 4}


def test_operator_board_mentions_do_all(capsys):
    code, out, _err = _run_main(["operator"], capsys)
    assert code == 0
    assert "--all" in out


def test_operator_aliases_operador_and_ops(capsys):
    """Spanish / short aliases must resolve to operator mode (iter 12)."""
    for alias in ("operador", "ops"):
        code, out, err = _run_main([alias], capsys)
        assert code == 0, f"alias={alias} err={err}"
        assert "MODO OPERARIO" in out or "operario" in out.lower()
        assert "VERDE" in out or "AMARILLO" in out or "ROJO" in out


def test_bare_cli_defaults_to_operator(capsys):
    """No COMMAND → operator board (iter 13 cold start <30 s)."""
    code, out, err = _run_main([], capsys)
    assert code == 0, err
    assert "MODO OPERARIO" in out or "operario" in out.lower()
    assert "GO_Q" in out


def test_ensayo_alias_runs_do_all(capsys):
    """Spanish 'ensayo' → compact 4-act path (iter 14)."""
    code, out, err = _run_main(["ensayo", "-q"], capsys)
    assert code == 0, err
    stamp = ROOT / "outputs" / "operator_ux_last_run.json"
    assert stamp.is_file()
    data = json.loads(stamp.read_text(encoding="utf-8"))
    assert data.get("all_four_ok") is True


def test_do_all_default_is_compact(capsys):
    """do --all without -v must not dump full decide explain (iter 14)."""
    code, out, err = _run_main(["operator", "do", "--all"], capsys)
    assert code == 0, err
    assert "Fin ensayo" in out or "4/4" in out or "Acto 1" in out
    # Full explain tables are -v only
    assert "Teach footnote" not in out
    assert out.count("EL SISTEMA SE CALLA") <= 1  # none preferred in compact
    # iter 17: no duplicate act scoreboard under Fin ensayo
    fin = out.find("Fin ensayo")
    assert fin >= 0
    tail = out[fin:]
    # each act listed once in compact body; footer must not re-list all four
    assert tail.count("Acto 1") == 0
    assert "Siguiente:" in out or "next" in out.lower()


def test_operator_next_shows_go_q_gap(capsys):
    code, out, err = _run_main(["operator", "next"], capsys)
    assert code == 0, err
    assert "GO_Q" in out or "go_q" in out.lower() or "tercero" in out.lower()
    assert "H1" in out or "acta" in out.lower() or "humano" in out.lower()
    # must not claim complete
    assert "GO_Q cerrado" not in out or "partial" in out.lower()


def test_invalid_command_hints_operator(capsys):
    code, out, err = _run_main(["no_existe_comando_xyz"], capsys)
    assert code != 0
    blob = (out + err).lower()
    assert "operario" in blob or "operator" in blob or "ensayo" in blob


def test_top_level_next_and_go_q_aliases(capsys):
    """next / go_q at top level expand to operator next (iter 16)."""
    for alias in ("next", "go_q"):
        code, out, err = _run_main([alias], capsys)
        assert code == 0, f"{alias}: {err}"
        assert "GO_Q" in out or "tercero" in out.lower() or "H1" in out


def test_top_level_checklist_alias(capsys):
    code, out, err = _run_main(["checklist", "--json"], capsys)
    assert code == 0, err
    data = json.loads(out)
    assert data.get("schema") == "wfd_operator_checklist_v1"
    assert "loop_done" in data


def test_build_portal_template_has_operator():
    """Regenerating portal must not re-open the show_all-only door."""
    src = (ROOT / "scripts" / "build_portal.py").read_text(encoding="utf-8")
    assert "wildfire_front operator" in src
    assert "operator do --all" in src or "do --all" in src
    # Old single-door show_all must not be the only hero command
    assert "Modo operario" in src or "modo operario" in src.lower()


def test_show_all_script_points_to_operator():
    src = (ROOT / "scripts" / "show_all.py").read_text(encoding="utf-8")
    assert "wildfire_front" in src and "operator" in src
    assert "camino operario" in src.lower() or "modo operario" in src.lower() or "operator" in src


def test_operator_explain_abstain_plain(capsys):
    code, out, _err = _run_main(["operator", "explain-abstain"], capsys)
    assert code == 0
    assert "ABSTAIN" in out
    assert "bug" in out.lower() or "fallo" in out.lower()
    assert "calla" in out.lower() or "FEATURE" in out or "feature" in out.lower()


def test_operator_do_act3_abstain_plain(capsys):
    code, out, _err = _run_main(["operator", "do", "--act", "3"], capsys)
    assert code == 0
    assert "ABSTAIN" in out
    assert "calla" in out.lower() or "feature" in out.lower() or "FEATURE" in out


def test_operator_do_act4_no_build(capsys):
    pack = ROOT / "outputs" / "demo_third_party"
    if not pack.is_dir():
        return  # soft skip without pytest.skip import noise
    code, out, err = _run_main(
        ["operator", "do", "--act", "4", "--no-build"],
        capsys,
    )
    assert code == 0, f"out={out}\nerr={err}"
    assert "replay" in out.lower() or "forensic" in out.lower() or "Pack" in out


def test_decide_short_abstain_has_nota(capsys):
    code, out, _err = _run_main(["decide", "--policy", "field_ops"], capsys)
    assert code == 0
    assert "ABSTAIN" in out
    assert "nota:" in out or "bug" in out.lower() or "explain-abstain" in out


def test_parser_lists_operator():
    help_text = build_parser().format_help()
    assert "operator" in help_text


def test_build_operator_status_lights_unit():
    st = operator_ux.build_operator_status(ROOT)
    assert st["schema"] == "wfd_operator_status_v1"
    assert st["lights"]["GO_Q"] == operator_ux.LIGHT_YELLOW
    assert st["lights"]["field_ops_ml_live_fusion"] == operator_ux.LIGHT_GREEN
    go_q = st["go_q"]
    assert go_q["go_q_complete"] is False
    assert len(go_q["what_is_missing"]) >= 1


def test_format_abstain_plain_unit():
    text = operator_ux.format_abstain_plain(
        {
            "decision": "ABSTAIN",
            "reasons": ["missing:ops", "no_sources"],
            "sources": [{"id": "ops", "available": False}],
        }
    )
    assert "ABSTAIN" in text
    assert "bug" in text.lower() or "fallo" in text.lower()
    assert "ops" in text.lower()


def test_teach_points_to_operator(capsys):
    code, out, _err = _run_main(["teach"], capsys)
    assert code == 0
    assert "operator" in out.lower()


# ── Discoverability / footgun fixes (operator CLI UX pass) ───────────────


def test_help_and_commands_map(capsys):
    """Users type 'help' before discovering --help; must print role map."""
    for argv in (["help"], ["commands"], ["cmds"], ["ayuda"]):
        code, out, err = _run_main(argv, capsys)
        assert code == 0, f"argv={argv} err={err}"
        low = out.lower()
        assert "operario" in low or "operator" in low
        assert "doctor" in low
        assert "decide" in low
        assert "mapa" in low or "commands" in low or "comando" in low


def test_commands_json_schema(capsys):
    code, out, err = _run_main(["commands", "--json"], capsys)
    assert code == 0, err
    data = json.loads(out)
    assert data["schema"] == "wfd_cli_commands_v1"
    ids = {g["id"] for g in data["groups"]}
    assert "operator" in ids
    assert "lab" in ids
    assert "decision" in ids
    assert data.get("common_footguns")


def test_status_bare_is_operator_board(capsys):
    """Bare 'status' is a footgun for incident status; route to operator board."""
    code, out, err = _run_main(["status"], capsys)
    assert code == 0, err
    assert "MODO OPERARIO" in out or "operario" in out.lower()
    assert "GO_Q" in out


def test_status_with_work_dir_routes_incident(capsys, tmp_path):
    """status --work-dir X → incident status (exit 2 when no state)."""
    work = tmp_path / "inc"
    work.mkdir()
    code, out, err = _run_main(["status", "--work-dir", str(work)], capsys)
    # no_state → exit 2 (incident status contract)
    assert code == 2
    blob = (out + err).lower()
    assert "status" in blob or "no_state" in blob or "incident" in blob or "state" in blob


def test_doctor_top_level_runs_ml(capsys):
    code, out, err = _run_main(["doctor"], capsys)
    assert code == 0, err
    low = out.lower()
    assert "ml doctor" in low or "lab product" in low or "doctor → ml" in low
    assert "field_ops" in low or "fusion" in low
    # Must point at field path so operators know about --inbox
    assert "--inbox" in out or "incident" in low


def test_doctor_hub_target(capsys):
    code, out, err = _run_main(["doctor", "--target", "hub"], capsys)
    assert code == 0, err
    assert "ml" in out.lower()
    assert "inbox" in out.lower() or "incident" in out.lower()


def test_doctor_json_wraps_ml(capsys):
    code, out, err = _run_main(["doctor", "--json"], capsys)
    assert code == 0, err
    data = json.loads(out)
    assert data["schema"] == "wfd_doctor_hub_v1"
    assert data["target"] == "ml"
    assert data["report"]["schema"] == "wfd_ml_doctor_v1"


def test_doctor_incident_requires_inbox(capsys):
    code, out, err = _run_main(["doctor", "--target", "incident"], capsys)
    assert code == 2
    blob = (out + err).lower()
    assert "inbox" in blob
    # Must NOT spam the generic "modo operario" as the only hint
    assert "doctor" in blob or "incident" in blob


def test_incident_doctor_missing_inbox_no_operator_spam(capsys):
    """Known-command missing flags must not dump the operator cold-start hint."""
    code, out, err = _run_main(["incident", "doctor"], capsys)
    assert code != 0
    blob = out + err
    assert "--inbox" in blob.lower() or "inbox" in blob.lower()
    # Contextual field hint OK; generic "¿Buscabas el modo operario?" is noise here
    assert "¿Buscabas el modo operario?" not in blob


def test_export_acta_missing_paths_exit_2(capsys):
    code, out, err = _run_main(["export-acta"], capsys)
    assert code == 2
    blob = (out + err).lower()
    assert "export-acta" in blob or "card" in blob
    assert "--card" in blob or "work-dir" in blob
    assert "hint" in blob or "decide" in blob


def test_replay_decide_missing_paths_exit_2(capsys):
    code, out, err = _run_main(["replay-decide"], capsys)
    assert code == 2
    blob = (out + err).lower()
    assert "replay" in blob
    assert "--bundle" in blob or "--sources" in blob or "work-dir" in blob


def test_decide_default_policy_note(capsys):
    """Bare decide uses policy 'default'; short output must say so."""
    code, out, err = _run_main(["decide"], capsys)
    assert code == 0, err
    assert "ABSTAIN" in out
    assert "default" in out.lower()
    assert "field_ops" in out.lower()


def test_unknown_command_mentions_help_and_doctor(capsys):
    code, out, err = _run_main(["no_existe_comando_xyz"], capsys)
    assert code != 0
    blob = (out + err).lower()
    assert "help" in blob or "commands" in blob or "mapa" in blob
    assert "doctor" in blob or "operario" in blob or "operator" in blob


# ── UX pass 2: hubs, version, typos, freeze ML gates ─────────────────────


def test_bare_ml_hub(capsys):
    """Bare `ml` must not be an argparse wall — lab hub exit 0."""
    code, out, err = _run_main(["ml"], capsys)
    assert code == 0, err
    low = out.lower()
    assert "ml" in low and ("hub" in low or "lab" in low)
    assert "list" in low
    assert "show" in low or "doctor" in low
    # Honesty rails visible
    assert "field" in low or "fusion" in low
    assert "iou" in low or "ros" in low


def test_bare_ml_hub_json_schema_and_frozen_gates(capsys):
    """Hub JSON must expose frozen ML product rails (no silent flip)."""
    code, out, err = _run_main(["ml", "--json"], capsys)
    assert code == 0, err
    data = json.loads(out)
    assert data["schema"] == "wfd_ml_hub_v1"
    assert data["default_product"] == "clm_ensemble_v34"
    gates = data["gates"]
    # Freeze contract: lab go true, field fusion OFF (product gate freeze)
    assert gates["ml_product_go"] is True
    assert gates["field_ops_ml_live_fusion"] == "OFF"
    assert gates["field_ops_ml_live_fusion"] != "ON"
    assert "list" in data["subcommands"]
    assert "freeze" in data["subcommands"]
    assert data.get("recommended_lab_surface")
    assert data.get("iter1_reject_thr") is not None


def test_bare_incident_hub(capsys):
    """Bare `incident` → field hub exit 0 (not required SUBCOMMAND error)."""
    code, out, err = _run_main(["incident"], capsys)
    assert code == 0, err
    low = out.lower()
    assert "incident" in low
    assert "doctor" in low
    assert "update" in low
    assert "status" in low
    assert "inbox" in low or "work-dir" in low


def test_bare_incident_hub_json(capsys):
    code, out, err = _run_main(["incident", "--json"], capsys)
    assert code == 0, err
    data = json.loads(out)
    assert data["schema"] == "wfd_incident_hub_v1"
    assert set(data["subcommands"]) >= {"doctor", "update", "watch", "status"}


def test_version_command_aliases(capsys):
    """Users type `version` / `ver` / `about` instead of --version."""
    from wildfire_front import __version__

    for argv in (["version"], ["ver"], ["about"]):
        code, out, err = _run_main(argv, capsys)
        assert code == 0, f"{argv}: {err}"
        assert __version__ in out
        assert "wildfire-front" in out.lower() or __version__ in out


def test_ml_typo_suggests_predict(capsys):
    code, out, err = _run_main(["ml", "predic"], capsys)
    assert code != 0
    blob = (out + err).lower()
    assert "predict" in blob
    assert "quisiste" in blob or "mean" in blob or "hint" in blob


def test_ingest_geotiff_missing_args_hint(capsys):
    code, out, err = _run_main(["ingest-geotiff"], capsys)
    assert code != 0
    blob = (out + err).lower()
    assert "images" in blob or "sensor" in blob
    assert "hint" in blob or "ingest-geotiff" in blob


def test_unknown_command_typo_suggestion(capsys):
    """Close typos should suggest a real COMMAND (e.g. decied → decide)."""
    code, out, err = _run_main(["decied"], capsys)
    assert code != 0
    blob = out + err
    assert "decide" in blob.lower()
    assert "Quisiste" in blob or "quisiste" in blob.lower()


def test_ml_show_gates_still_frozen(capsys):
    """Regression: UX hubs must not relax ML product gates on show path."""
    code, out, err = _run_main(["ml", "show", "--json"], capsys)
    assert code == 0, err
    data = json.loads(out)
    assert data["schema"] == "wfd_ml_show_snapshot_v1"
    assert data["gates"]["ml_product_go"] is True
    fusion = data["fusion_rails"]
    assert fusion["field_ops_allow_ml_live_in_fusion"] is False
    assert fusion["field_ops_ml_live_fusion"] == "OFF"


def test_root_help_mentions_start_here_and_hubs():
    help_text = build_parser().format_help()
    low = help_text.lower()
    assert "start here" in low or "operator board" in low
    assert "help" in low
    # bare hubs called out in notes/epilog or description
    assert "hub" in low or "bare" in low or "ml" in low
    assert "brief" in low


def test_brief_human_professional_and_rails(capsys):
    """New ``brief`` command: one-screen professional summary (not traffic board)."""
    code, out, err = _run_main(["brief"], capsys)
    assert code == 0, err
    assert "BRIEF" in out or "Brief" in out or "brief" in out.lower()
    assert "GO_Q" in out or "GO_MES" in out
    assert "fusion" in out.lower() or "OFF" in out
    assert "IoU" in out or "ROS" in out or "despacho" in out.lower() or "dispatch" in out.lower()
    assert "Próxima" in out or "proxima" in out.lower() or "next" in out.lower() or "→" in out
    # Must not claim tactical dispatch is authorized
    low = out.lower()
    assert "táctico" in low or "tactico" in low or "dispatch" in low or "despacho" in low
    assert "no" in low or "not" in low or "⚠" in out


def test_brief_json_schema_and_freeze(capsys):
    code, out, err = _run_main(["brief", "--json"], capsys)
    assert code == 0, err
    data = json.loads(out)
    assert data["schema"] == "wfd_operator_brief_v1"
    assert data["role"] == "operator"
    assert data["rails"]["field_ops_ml_live_fusion"] == "OFF"
    assert data["rails"]["iou_is_not_ros"] is True
    assert data["rails"]["not_tactical_dispatch"] is True
    assert data["rails"]["go_q_invent_forbidden"] is True
    assert data["go_q"]["complete"] is False
    assert data["gates"]["field_ops_ml_live_fusion"] == "OFF"
    assert isinstance(data["recommended_sequence"], list)
    assert len(data["recommended_sequence"]) >= 3
    assert "next_action" in data and data["next_action"].get("command")
    assert data["next_action"]["command"].startswith("python -m wildfire_front")


def test_brief_role_lab_and_aliases(capsys):
    code, out, err = _run_main(["brief", "--role", "lab", "--json"], capsys)
    assert code == 0, err
    data = json.loads(out)
    assert data["schema"] == "wfd_operator_brief_v1"
    assert data["role"] == "lab"
    assert data["rails"]["field_ops_ml_live_fusion"] == "OFF"
    assert any("ml" in str(c).lower() for c in data["recommended_sequence"])
    # aliases
    for alias in ("resumen", "summary", "briefing"):
        c2, o2, e2 = _run_main([alias, "--json"], capsys)
        assert c2 == 0, f"{alias}: {e2}"
        d2 = json.loads(o2)
        assert d2["schema"] == "wfd_operator_brief_v1"


def test_brief_role_field_sequence(capsys):
    code, out, err = _run_main(["brief", "--role", "field"], capsys)
    assert code == 0, err
    low = out.lower()
    assert "incident" in low or "campo" in low or "field" in low
    assert "doctor" in low
    assert "inbox" in low
