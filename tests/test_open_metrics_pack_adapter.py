"""PR1: open industrial pack → open_metrics adapter (no weights)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wildfire_front.product.decide_service import (
    industrial_scorecard_to_open_metrics,
    load_open_metrics_from_pack,
)

ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "tests" / "fixtures" / "pilot"
OPEN_AND = PILOT / "open_and_min"
OPEN_EXT = PILOT / "open_ext_min"

ROS_BANNED = ("primary_ros_m_min", "vp_m_min", "vp_tactical", "ros_m_min")
FIRMS_AREA_BANNED = ("area_firms_hull_ha", "area_firms_", "firms_hull_")


def _assert_no_ros(metrics: dict) -> None:
    blob = json.dumps(metrics)
    for k in ROS_BANNED:
        assert k not in metrics, f"banned ROS key present: {k}"
        # also ensure not nested as values claiming tactical ROS
        assert f'"{k}"' not in blob or metrics.get(k) is None


def test_and_industrial_fixture_area_and_keys():
    m = load_open_metrics_from_pack(OPEN_AND, base=ROOT, include_repo_root=True)
    assert m is not None
    assert m["max_area_ha"] == pytest.approx(2169.34)
    assert isinstance(m["n_timeline_steps"], int)
    assert m["n_timeline_steps"] >= 0
    assert m["source_scorecard"] == "scorecard_and_industrial.json"
    assert m["area_source"] == "metrics_o2.area_rediam_ha"
    assert m["pack_id"] == "and_2024040053_20240606"
    assert m["O2_cems_delineation"] == "GO"
    assert m["verdict"] == "GO_OPEN_AND_O2"
    assert m["decision_open"] == "HOLD"
    assert m["vp_invented"] is False
    assert m["firms_hull_is_official_burned_area"] is False
    _assert_no_ros(m)
    # FIRMS hull ha must not become max_area_ha
    assert m["max_area_ha"] != pytest.approx(7448.79)


def test_ext_partial_still_returns_ha():
    m = load_open_metrics_from_pack(OPEN_EXT, base=ROOT, include_repo_root=True)
    assert m is not None
    assert m["max_area_ha"] == pytest.approx(2679.14)
    assert m["area_source"] == "metrics_o2.area_rai_ha"
    assert m["verdict"] == "PARTIAL"
    assert m["decision_open"] == "HOLD"
    assert m["source_scorecard"] == "scorecard_ext_industrial.json"
    assert m["O2_cems_delineation"] == "GO"  # O2_RAI PASS → GO
    _assert_no_ros(m)


def test_legacy_pista_b_still_works(tmp_path: Path):
    pack = tmp_path / "legacy_pista"
    pack.mkdir()
    sc = {
        "activation": "EMSR578",
        "max_area_ha": 2693.48,
        "n_timeline_steps": 5,
        "O2_cems_delineation": "GO",
    }
    (pack / "scorecard_pista_b.json").write_text(json.dumps(sc), encoding="utf-8")
    m = load_open_metrics_from_pack(pack, base=tmp_path, include_repo_root=False)
    assert m is not None
    assert m["max_area_ha"] == pytest.approx(2693.48)
    assert m["n_timeline_steps"] == 5
    assert m["activation"] == "EMSR578"
    assert m["source_scorecard"] == "scorecard_pista_b.json"
    # Missing honesty flags → incomplete; never invent vp_invented=False
    assert m.get("vp_invented") is None
    assert m.get("firms_hull_is_official_burned_area") is None
    assert m.get("sources_incomplete") is True
    _assert_no_ros(m)


def test_legacy_pista_b_missing_area_returns_none(tmp_path: Path):
    pack = tmp_path / "legacy_no_area"
    pack.mkdir()
    (pack / "scorecard_pista_b.json").write_text(
        json.dumps({"activation": "X", "O2_cems_delineation": "GO"}),
        encoding="utf-8",
    )
    assert load_open_metrics_from_pack(pack, base=tmp_path, include_repo_root=False) is None


def test_both_and_ext_named_industrial_returns_none(tmp_path: Path):
    pack = tmp_path / "ambiguous_named"
    pack.mkdir()
    (pack / "scorecard_and_industrial.json").write_text("{}", encoding="utf-8")
    (pack / "scorecard_ext_industrial.json").write_text("{}", encoding="utf-8")
    (pack / "metrics_o2.json").write_text(json.dumps({"area_rediam_ha": 100.0}), encoding="utf-8")
    assert load_open_metrics_from_pack(pack, base=tmp_path, include_repo_root=False) is None


def test_two_glob_industrial_returns_none(tmp_path: Path):
    pack = tmp_path / "ambiguous_glob"
    pack.mkdir()
    (pack / "scorecard_foo_industrial.json").write_text(
        json.dumps({"pack_id": "foo"}), encoding="utf-8"
    )
    (pack / "scorecard_bar_industrial.json").write_text(
        json.dumps({"pack_id": "bar"}), encoding="utf-8"
    )
    (pack / "metrics_o2.json").write_text(json.dumps({"area_rediam_ha": 50.0}), encoding="utf-8")
    assert load_open_metrics_from_pack(pack, base=tmp_path, include_repo_root=False) is None


def test_single_other_industrial_glob(tmp_path: Path):
    pack = tmp_path / "other_industrial"
    pack.mkdir()
    (pack / "scorecard_cyl_industrial.json").write_text(
        json.dumps({"pack_id": "cyl_x", "track": "OTHER", "verdict": "HOLD"}),
        encoding="utf-8",
    )
    (pack / "metrics_o2.json").write_text(
        json.dumps({"max_area_ha": 123.0, "n_timeline_steps": 2}),
        encoding="utf-8",
    )
    m = load_open_metrics_from_pack(pack, base=tmp_path, include_repo_root=False)
    assert m is not None
    assert m["max_area_ha"] == pytest.approx(123.0)
    assert m["source_scorecard"] == "scorecard_cyl_industrial.json"
    assert m["n_timeline_steps"] == 2


def test_never_uses_firms_hull_as_area(tmp_path: Path):
    pack = tmp_path / "firms_only"
    pack.mkdir()
    (pack / "scorecard_and_industrial.json").write_text(
        json.dumps({"pack_id": "x", "vp_invented": False}), encoding="utf-8"
    )
    (pack / "metrics_o2.json").write_text(
        json.dumps({"area_firms_hull_ha": 9999.0, "area_firms_ha": 8888.0}),
        encoding="utf-8",
    )
    assert load_open_metrics_from_pack(pack, base=tmp_path, include_repo_root=False) is None


def test_industrial_helper_direct_and_partial(tmp_path: Path):
    pack = tmp_path / "helper"
    pack.mkdir()
    sc = {
        "pack_id": "p",
        "gates": {"O2_RAI": "PASS"},
        "verdict": "PARTIAL",
        "decision_open": "HOLD",
        "vp_invented": False,
        "firms_hull_is_official_burned_area": False,
    }
    (pack / "metrics_o2.json").write_text(json.dumps({"area_rai_ha": 10.5}), encoding="utf-8")
    m = industrial_scorecard_to_open_metrics(
        pack, sc, source_scorecard="scorecard_ext_industrial.json", kind="EXT"
    )
    assert m is not None
    assert m["max_area_ha"] == pytest.approx(10.5)
    assert m["verdict"] == "PARTIAL"
    assert m["area_source"] == "metrics_o2.area_rai_ha"


def test_empty_pack_returns_none(tmp_path: Path):
    pack = tmp_path / "empty"
    pack.mkdir()
    assert load_open_metrics_from_pack(pack, base=tmp_path, include_repo_root=False) is None


def test_missing_vp_invented_marks_sources_incomplete(tmp_path: Path):
    """A12: missing vp_invented / firms_hull must not claim False."""
    pack = tmp_path / "incomplete_honesty"
    pack.mkdir()
    (pack / "scorecard_and_industrial.json").write_text(
        json.dumps({"pack_id": "x", "verdict": "PARTIAL", "decision_open": "HOLD"}),
        encoding="utf-8",
    )
    (pack / "metrics_o2.json").write_text(
        json.dumps({"area_rediam_ha": 42.0}),
        encoding="utf-8",
    )
    m = load_open_metrics_from_pack(pack, base=tmp_path, include_repo_root=False)
    assert m is not None
    assert m.get("vp_invented") is None
    assert m.get("firms_hull_is_official_burned_area") is None
    assert m.get("sources_incomplete") is True
    assert m["max_area_ha"] == pytest.approx(42.0)
