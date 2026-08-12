"""CLI help surface and human report helpers."""

from __future__ import annotations

from pathlib import Path

from wildfire_front.cli import build_parser
from wildfire_front.cli_report import enrich_incident_summary, print_incident_report


def test_root_help_lists_commands() -> None:
    parser = build_parser()
    help_text = parser.format_help()
    assert "demo" in help_text
    assert "ingest-geotiff" in help_text
    assert "incident" in help_text
    assert "commands" in help_text
    assert "doctor" in help_text
    assert "brief" in help_text
    assert "app" in help_text
    assert "examples:" in help_text
    assert "NOT" in help_text or "not" in help_text


def test_parser_registers_commands_and_doctor() -> None:
    parser = build_parser()
    args = parser.parse_args(["commands"])
    assert args.command == "commands"
    args2 = parser.parse_args(["doctor", "--target", "hub"])
    assert args2.command == "doctor"
    assert args2.target == "hub"
    args3 = parser.parse_args(["brief", "--role", "decision"])
    assert args3.command == "brief"
    assert args3.role == "decision"
    args4 = parser.parse_args(["app", "--work-dir", "x", "--open"])
    assert args4.command == "app"
    assert args4.open is True


def test_incident_subcommands_in_help() -> None:
    parser = build_parser()
    args = parser.parse_args(["incident", "doctor", "--inbox", "x"])
    assert args.incident_command == "doctor"
    args2 = parser.parse_args(["incident", "status", "--work-dir", "y"])
    assert args2.incident_command == "status"


def test_version_flag() -> None:
    parser = build_parser()
    try:
        parser.parse_args(["--version"])
        assert False, "expected SystemExit"
    except SystemExit as e:
        assert e.code == 0


def test_enrich_and_print_incident(tmp_path: Path, capsys) -> None:
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    (outbox / "operational_metrics.json").write_text(
        """{
          "quality_grade": "A",
          "quality_label_es": "excelente",
          "speed_median_m_min": 5.71,
          "speed_p25_m_min": 2.8,
          "speed_p75_m_min": 6.9,
          "speed_n_observable": 5,
          "sector_ros": {"status": "estimated", "sectors": {
            "head_m_min": 6.9, "flank_m_min": 5.71, "rear_m_min": 2.8
          }},
          "short_horizon_envelope": {
            "status": "ok",
            "envelopes": [
              {"horizon_min": 15, "head_radius_m": 100, "flank_radius_m": 80, "rear_radius_m": 40, "radius_m": 80}
            ]
          }
        }""",
        encoding="utf-8",
    )
    summary = {
        "product": "incident_runtime_v1",
        "status": "updated",
        "event_id": "demo",
        "n_staged": 3,
        "outbox": str(outbox),
        "primary_ros_m_min": 5.71,
        "quality_grade": "A",
    }
    enriched = enrich_incident_summary(summary)
    assert enriched["detail"]["sector_ros"]["sectors"]["head_m_min"] == 6.9
    print_incident_report(enriched, as_json=False, verbose=True)
    captured = capsys.readouterr().out
    assert "5.71" in captured or "ROS" in captured
    assert "head" in captured.lower()
    assert "NOT dispatch" in captured or "dispatch" in captured.lower()
    assert "Disclaimers" in captured
