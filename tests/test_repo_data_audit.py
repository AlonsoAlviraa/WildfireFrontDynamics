"""Repository-wide data audit tests."""

from __future__ import annotations

import json
from pathlib import Path

from wildfire_front.open_if.repo_data_audit import RepositoryDataAuditor


def test_repo_audit_classifies_data_and_forbids_output_reuse(tmp_path: Path) -> None:
    rcda = tmp_path / "data/external/rcda_net_full"
    rcda.mkdir(parents=True)
    (rcda / "sample.json").write_text('{"ok":true}', encoding="utf-8")
    outputs = tmp_path / "outputs/run"
    outputs.mkdir(parents=True)
    (outputs / "prediction.json").write_text('{"prediction":1}', encoding="utf-8")
    unknown = tmp_path / "data/mystery"
    unknown.mkdir(parents=True)
    (unknown / "empty.bin").write_bytes(b"")
    wfigs = tmp_path / "data/open_if/wfigs_history_2020_2026"
    wfigs.mkdir(parents=True)
    (wfigs / "manifest.json").write_text('{"source":"WFIGS"}', encoding="utf-8")

    output_root = tmp_path / "audit"
    auditor = RepositoryDataAuditor(
        repo_root=tmp_path,
        output_root=output_root,
        hash_mode="small",
    )
    report = auditor.build()
    assert report["files"]["files"] == 4
    assert report["datasets"]["rcda_net_full"]["verdict"] == "usable_with_repaired_protocol"
    assert report["datasets"]["outputs"]["progression_ml"] == "never_training_input"
    assert report["datasets"]["wfigs_history"]["verdict"] == "conditional_research_training"
    assert report["datasets"]["unclassified_data"]["verdict"] == "needs_manual_review"
    assert report["files"]["health"]["empty"] == 1
    rows = [
        json.loads(line)
        for line in (output_root / "DATA_FILE_AUDIT.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    prediction = next(row for row in rows if row["path"].startswith("outputs/"))
    assert prediction["ml_verdict"] == "artifact_only"
    assert prediction["sha256_status"] == "computed"
    refreshed = auditor.refresh_derived()
    assert refreshed["files"] == report["files"]
    assert "derived_refreshed_at" in refreshed
    assert (output_root / "MEGA_DATA_AUDIT.md").is_file()
    reclassified = auditor.refresh_existing()
    assert reclassified["files"]["files"] == 4
    assert reclassified["files"]["files_hashed"] == 3
