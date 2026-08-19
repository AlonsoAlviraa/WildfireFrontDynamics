"""Industrial SLA helper: real ops JSON → shipped decide_from_request."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_sla():
    path = ROOT / "scripts" / "measure_incident_sla.py"
    spec = importlib.util.spec_from_file_location("measure_incident_sla", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_measure_decide_from_ops_json_uses_shipped_decide(tmp_path: Path) -> None:
    ops = {
        "quality_grade": "B",
        "speed_median_m_min": 6.75,
        "input_count": 4,
        "area_ha_max": 26.5,
        "speed_vs_ref_ratio": 0.96,
    }
    path = tmp_path / "operational_metrics.json"
    path.write_text(json.dumps(ops), encoding="utf-8")
    report = _load_sla().measure_decide_from_ops_json(path, n=5, policy_id="field_ops")
    assert report["n"] == 5
    assert report["p95_ms"] >= 0.0
    assert report["budget_p95_ms"] == 500.0
    assert report["last_decision"] in {"GO", "HOLD", "ABSTAIN"}
    # Unverified field_ops must not GO just because we timed it.
    assert report["last_decision"] != "GO"
    assert report["system_reliability_pass"] is False
    assert report["quality_grade"] == "B"
    assert report["n_frames_staged"] == 4


def test_measure_decide_from_real_tobarra_pack_if_present() -> None:
    ops = Path("outputs/temporal_windows/tobarra_20240802/mid/operational_metrics.json")
    if not ops.is_file():
        return
    report = _load_sla().measure_decide_from_ops_json(ops, n=8, policy_id="field_ops")
    assert report["sla_pass"] is True
    assert report["p95_ms"] < 500.0
    assert report["last_decision"] != "GO"
