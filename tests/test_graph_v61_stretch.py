"""Tests for Graph v6.1 stretch eng (E7, R-A1, R-A3, H3 dry-run helpers)."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    path = ROOT / rel
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _env() -> dict[str, str]:
    e = dict(os.environ)
    e["PYTHONPATH"] = str(ROOT)
    return e


def test_collect_abstention_slice_structure():
    mod = _load("build_metrics_hub", "scripts/build_metrics_hub.py")
    ab = mod.collect_abstention_slice()
    assert ab["schema"] == "metrics_hub_abstention_v1"
    assert ab["graph_id"] == "E7"
    assert ab["ml_live_fusion"] == "OFF"
    assert "abstain_rate" in ab
    assert "source_coverage_mean" in ab
    assert ab["abstain_rate"] >= 0.0
    assert ab["abstain_rate"] <= 1.0
    if ab["n_cards"] == 0:
        assert ab["unknown"] is True
        assert ab["abstain_rate"] == 0.0
    else:
        assert ab["unknown"] is False
        assert ab["n_abstain"] + ab["n_hold"] + ab["n_go"] <= ab["n_cards"] + 5
        # decisions may include only GO/HOLD/ABSTAIN; allow other labels counted in n_cards
        assert ab["n_abstain"] <= ab["n_cards"]


def test_metrics_hub_includes_abstention_key():
    mod = _load("build_metrics_hub", "scripts/build_metrics_hub.py")
    hub = mod.collect()
    assert "abstention" in hub
    assert hub["abstention"]["graph_id"] == "E7"
    md = mod.render_md(hub)
    assert "Abstention slice (E7)" in md
    assert "abstain_rate" in md.lower() or "abstain_rate" in md


def test_hausdorff_lite_identical_zero():
    mod = _load("summarize_open_perimeter", "scripts/summarize_open_perimeter_attempt.py")
    ring = [(0.0, 40.0), (0.1, 40.0), (0.1, 40.1), (0.0, 40.1), (0.0, 40.0)]
    h = mod.hausdorff_lite_m(ring, ring)
    assert h is not None
    assert h < 1.0  # metres, identical rings


def test_hausdorff_lite_separated_positive():
    mod = _load("summarize_open_perimeter", "scripts/summarize_open_perimeter_attempt.py")
    a = [(0.0, 40.0), (0.01, 40.0), (0.01, 40.01), (0.0, 40.01)]
    b = [(1.0, 40.0), (1.01, 40.0), (1.01, 40.01), (1.0, 40.01)]
    h = mod.hausdorff_lite_m(a, b)
    assert h is not None
    assert h > 1000.0  # ~1 degree lon at 40N is tens of km


def test_summarize_open_pack_emsr578_if_present(tmp_path: Path):
    pack = ROOT / "outputs" / "open_if" / "emsr578"
    if not pack.is_dir():
        pytest.skip("emsr578 pack not present")
    mod = _load("summarize_open_perimeter", "scripts/summarize_open_perimeter_attempt.py")
    summary = mod.summarize_pack(pack)
    assert summary["graph_id"] == "R-A1"
    assert summary["o2_national_unlocked"] is False
    assert summary["rails"]["not_national_cadastre"] is True
    out = tmp_path / "r_a1"
    out.mkdir()
    (out / "perimeter_summary.json").write_text(json.dumps(summary), encoding="utf-8")
    assert summary["status"] in ("OK_OPEN_PACK", "GAP_NO_GEOMETRY")


def test_firms_direction_empty_gap():
    mod = _load("firms_direction", "scripts/firms_direction_overlay_note.py")
    note = mod.build_note(pack=ROOT / "outputs" / "open_if" / "__missing_pack__", firms_dir=None)
    assert note["graph_id"] == "R-A3"
    assert note["invented_vp"] is False
    assert note["status"] in ("GAP_NO_HOTSPOTS", "EMPTY_HOTSPOTS")


def test_firms_direction_from_synthetic(tmp_path: Path):
    mod = _load("firms_direction", "scripts/firms_direction_overlay_note.py")
    gj = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"acq_date": "2026-07-01", "acq_time": "1000"},
                "geometry": {"type": "Point", "coordinates": [-3.0, 41.0]},
            },
            {
                "type": "Feature",
                "properties": {"acq_date": "2026-07-01", "acq_time": "1100"},
                "geometry": {"type": "Point", "coordinates": [-2.99, 41.01]},
            },
            {
                "type": "Feature",
                "properties": {"acq_date": "2026-07-02", "acq_time": "1000"},
                "geometry": {"type": "Point", "coordinates": [-2.9, 41.1]},
            },
            {
                "type": "Feature",
                "properties": {"acq_date": "2026-07-02", "acq_time": "1200"},
                "geometry": {"type": "Point", "coordinates": [-2.88, 41.12]},
            },
        ],
    }
    path = tmp_path / "firms_hotspots.geojson"
    path.write_text(json.dumps(gj), encoding="utf-8")
    note = mod.build_note(pack=None, firms_dir=None, geojson_path=path)
    assert note["status"] == "OK_DIRECTION_PROXY"
    assert note["n_hotspots"] == 4
    assert note["direction_bearing_deg"] is not None
    assert 0 <= note["direction_bearing_deg"] < 360
    assert note["invented_vp"] is False


def test_dry_run_report_builder(tmp_path: Path):
    mod = _load("dry_run_demo", "scripts/dry_run_demo_third_party.py")
    # minimal fake out dir
    out = tmp_path / "demo"
    out.mkdir()
    (out / "fire_decision_card.json").write_text(
        json.dumps(
            {
                "decision": "GO",
                "confidence_pred": 0.8,
                "metrics": {
                    "policy_id": "field_ops",
                    "allow_ml_live_in_fusion": False,
                },
            }
        ),
        encoding="utf-8",
    )
    (out / "replay_manifest.json").write_text("{}", encoding="utf-8")
    report = mod.build_report(
        out_dir=out,
        pack_rc={"returncode": 0, "stdout_tail": "", "stderr_tail": ""},
        replay_rc={"returncode": 0, "stdout_tail": "replay_ok: True\n", "stderr_tail": ""},
        skip_build=True,
    )
    assert report["eng_dry_run_ok"] is True
    assert report["h3_human_operator_still_required"] is True
    assert report["rails"]["no_GO_Q_claim"] is True
    md = mod.render_md(report)
    assert "Human still required" in md


def test_docs_stretch_exist():
    required = [
        "docs/fire_intel/ELMFIRE_FOREFIRE_SPIKE_NOTE.md",
        "docs/fire_intel/EO_LWIR_PAIR_INVENTORY.md",
        "docs/fire_intel/CN_RESEARCH_LAB_ONLY.md",
        "docs/fire_intel/OWTRD_NOTES.md",
        "docs/fire_intel/ICFFR_ABSTRACT_DRAFT.md",
        "docs/fire_intel/INDUSTRY_CALENDAR_DECISIONS.md",
    ]
    for rel in required:
        p = ROOT / rel
        assert p.is_file(), f"missing {rel}"
        text = p.read_text(encoding="utf-8")
        assert len(text) > 200


def test_oss_catalog_has_r_oss1_section():
    text = (ROOT / "docs/fire_intel/OSS_DATASETS_CATALOG_2026.md").read_text(encoding="utf-8")
    assert "R-OSS1" in text
    assert "Pyronear" in text
    assert "FlamMap" in text
