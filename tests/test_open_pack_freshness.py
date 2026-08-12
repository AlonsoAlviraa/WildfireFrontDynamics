"""E5 — open pack freshness_score + content checksum."""

from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "scripts" / "audit_open_pack_freshness.py"
    spec = importlib.util.spec_from_file_location("audit_open_pack_freshness", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_freshness_score_decay():
    mod = _load()
    assert mod.freshness_score_from_age(0.0) == 1.0
    half = mod.freshness_score_from_age(30.0, half_life_days=30.0)
    assert abs(half - 0.5) < 1e-9
    older = mod.freshness_score_from_age(60.0, half_life_days=30.0)
    assert older < half


def test_audit_and_write_manifest(tmp_path: Path):
    mod = _load()
    pack = tmp_path / "emsr_fake"
    pack.mkdir()
    built = (datetime.now(UTC) - timedelta(days=10)).isoformat()
    man = {
        "product": "open_if_pack_v1",
        "activation": "EMSR_FAKE",
        "built_at_utc": built,
        "max_area_ha": 100.0,
    }
    (pack / "manifest.json").write_text(json.dumps(man, indent=2), encoding="utf-8")
    (pack / "metrics_o2.json").write_text(json.dumps({"max_area_ha": 100}), encoding="utf-8")

    rep = mod.audit_pack(pack)
    assert rep["freshness_score"] is not None
    assert 0.0 < rep["freshness_score"] <= 1.0
    assert rep["content_checksum"]
    assert rep["n_files_hashed"] >= 1
    assert rep["freshness_reason"] == "ok"
    # manifest.json must NOT be in the hashed set (avoids self-invalidation)
    assert "manifest.json" not in (rep.get("files_sha256") or {})

    mod.apply_to_manifest(pack, rep)
    updated = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))
    assert "freshness_score" in updated
    assert updated["content_checksum"] == rep["content_checksum"]
    assert updated.get("content_checksum_scope") == "product_files_excluding_manifest"
    assert (pack / "freshness_audit.json").is_file()

    # Regression: re-audit after --write must keep the same content_checksum
    rep2 = mod.audit_pack(pack)
    assert rep2["content_checksum"] == rep["content_checksum"]
    assert rep2["content_checksum"] == updated["content_checksum"]


def test_missing_built_at_null_score(tmp_path: Path):
    mod = _load()
    pack = tmp_path / "no_built"
    pack.mkdir()
    (pack / "manifest.json").write_text(json.dumps({"activation": "X"}), encoding="utf-8")
    rep = mod.audit_pack(pack)
    assert rep["freshness_score"] is None
    assert rep["freshness_reason"] == "missing_built_at_utc"
