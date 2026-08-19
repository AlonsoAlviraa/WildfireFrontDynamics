"""Tests for scripts/inventory_open_if_urls.py (LATAM+AU F0 URL inventory)."""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "inventory_open_if_urls.py"

sys.path.insert(0, str(ROOT / "scripts"))
import inventory_open_if_urls as inv  # noqa: E402


def _run(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(cwd or ROOT),
        capture_output=True,
        text=True,
    )


def test_missing_catalog_exits_1(tmp_path: Path) -> None:
    missing = tmp_path / "no_such_catalog.json"
    out = tmp_path / "inv.csv"
    p = _run(["--catalog", str(missing), "--output", str(out)])
    assert p.returncode == 1
    assert "error:" in p.stderr
    assert not out.is_file()


def test_empty_catalog_sources_exits_1(tmp_path: Path) -> None:
    catalog = tmp_path / "empty.json"
    catalog.write_text(
        json.dumps({"schema": "wfd_open_if_source_catalog_v1", "sources": []}),
        encoding="utf-8",
    )
    out = tmp_path / "inv.csv"
    p = _run(["--catalog", str(catalog), "--output", str(out)])
    assert p.returncode == 1
    assert "zero usable" in p.stderr


def test_not_checked_writes_schema_exit_0(tmp_path: Path) -> None:
    catalog = tmp_path / "cat.json"
    catalog.write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "source_id": "T1",
                        "name": "Test",
                        "country_or_region": "AU",
                        "role": "index",
                        "url": "https://example.com/",
                        "license_class": "open",
                        "access": "open",
                        "lab_ok_provisional": True,
                        "notes": "fixture",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "inv.csv"
    json_out = tmp_path / "inv.json"
    p = _run(
        [
            "--catalog",
            str(catalog),
            "--output",
            str(out),
            "--json-out",
            str(json_out),
        ]
    )
    assert p.returncode == 0, p.stderr
    assert out.is_file()
    with out.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert rows[0]["source_id"] == "T1"
    assert rows[0]["status"] == "not_checked"
    assert rows[0]["url"] == "https://example.com/"
    for col in inv.INVENTORY_FIELDS:
        assert col in rows[0]
    payload = json.loads(json_out.read_text(encoding="utf-8"))
    assert payload["schema"] == "wfd_open_if_url_inventory_v1"
    assert payload["meta"]["check"] is False
    assert payload["meta"]["n_records"] == 1
    honesty = str(payload["meta"].get("honesty") or "")
    assert "no IoU" in honesty
    # Inventory must not invent product metrics fields
    assert "test_iou" not in payload
    assert "grade_a" not in json.dumps(payload).lower()


def test_check_all_unreachable_exits_2(tmp_path: Path) -> None:
    catalog = tmp_path / "cat.json"
    catalog.write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "source_id": "BAD",
                        "name": "Bad",
                        "url": "https://example.invalid/",
                        "license_class": "open",
                        "access": "open",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "inv.csv"

    def _fail_probe(url: str, timeout: float) -> dict:
        return {
            "status": "unreachable",
            "http_code": "",
            "final_url": "",
            "elapsed_ms": 1,
            "error": "URLError:mocked",
        }

    with patch.object(inv, "probe_url", side_effect=_fail_probe):
        code = inv.main(
            [
                "--catalog",
                str(catalog),
                "--output",
                str(out),
                "--check",
                "--timeout",
                "1",
            ]
        )
    assert code == 2
    with out.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["status"] == "unreachable"
    assert rows[0]["error"]


def test_check_reachable_exits_0(tmp_path: Path) -> None:
    catalog = tmp_path / "cat.json"
    catalog.write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "source_id": "OK",
                        "name": "Ok",
                        "url": "https://example.com/",
                        "license_class": "open",
                        "access": "open",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "inv.csv"

    def _ok_probe(url: str, timeout: float) -> dict:
        return {
            "status": "reachable",
            "http_code": "200",
            "final_url": url,
            "elapsed_ms": 5,
            "error": "",
        }

    with patch.object(inv, "probe_url", side_effect=_ok_probe):
        code = inv.main(
            ["--catalog", str(catalog), "--output", str(out), "--check"]
        )
    assert code == 0
    with out.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["status"] == "reachable"
    assert rows[0]["http_code"] == "200"


def test_is_safe_public_url_blocks_loopback_exact() -> None:
    ok, reason = inv.is_safe_public_url("http://127.0.0.1/secret")
    assert ok is False
    assert "blocked" in reason

    ok2, _ = inv.is_safe_public_url("http://localhost/x")
    assert ok2 is False

    # Spoofed hostname must NOT be treated as loopback via naive startswith
    ok3, reason3 = inv.is_safe_public_url("https://127.0.0.1.example.com/")
    assert ok3 is True
    assert reason3 == ""

    ok4, reason4 = inv.is_safe_public_url("ftp://example.com/")
    assert ok4 is False
    assert "scheme" in reason4


def test_is_safe_public_url_blocks_private_ip() -> None:
    ok, reason = inv.is_safe_public_url("http://192.168.1.1/")
    assert ok is False
    assert "blocked_ip" in reason


def test_load_candidates_csv_skips_comments(tmp_path: Path) -> None:
    csv_path = tmp_path / "cands.csv"
    csv_path.write_text(
        "event_id,country,url,notes\n"
        "# comment row should skip if event_id starts with hash,AU,https://a.example/\n"
        "EVT1,AU,https://example.com/event,ok\n",
        encoding="utf-8",
    )
    # First data line has event_id "# comment..." — our loader skips startswith #
    # Actually the event_id would be "# comment row..." only if written that way
    records = inv.load_candidates_csv(csv_path)
    assert any(r.source_id == "EVT1" for r in records)
    assert all(not r.source_id.startswith("#") for r in records)


def test_repo_catalog_schema_and_candidates_min_rows() -> None:
    """Repo artifacts for F0: catalog + ≥20 real candidate rows (no pure fictional SEED_* only)."""
    catalog = ROOT / "docs" / "data_campaigns" / "LATAM_AU_SOURCE_CATALOG.json"
    assert catalog.is_file()
    data = json.loads(catalog.read_text(encoding="utf-8"))
    assert data.get("schema") == "wfd_open_if_source_catalog_v1"
    sources = data["sources"]
    assert len(sources) >= 15
    for s in sources:
        assert s.get("source_id")
        assert s.get("url", "").startswith("http")
        assert s.get("access") in {"open", "mixed", "request_only"}
        assert s.get("license_class")

    cands = ROOT / "docs" / "data_campaigns" / "LATAM_AU_CANDIDATES.csv"
    with cands.open(encoding="utf-8-sig", newline="") as handle:
        rows = [
            r
            for r in csv.DictReader(handle)
            if (r.get("event_id") or "").strip()
            and not (r.get("event_id") or "").startswith("#")
        ]
    assert len(rows) >= 20
    # No leftover pure seed template IDs as sole content
    seedish = [r for r in rows if r["event_id"].startswith("SEED_")]
    assert len(seedish) == 0
    countries = {r["country"] for r in rows}
    assert "AU" in countries
    assert any(c in countries for c in ("CL", "BR", "MX", "BO", "GT", "BZ"))
    assert "GLOBAL" in countries
    required = {
        "event_id",
        "country",
        "year",
        "lat",
        "lon",
        "source_index",
        "n_eo_scenes_est",
        "perimeter_source",
        "license",
        "class",
        "url",
        "notes",
        "r1",
        "r2",
        "r3",
        "r4",
        "r5",
        "r6",
    }
    assert required.issubset(set(rows[0].keys()))
    # Honesty: R6=1 only for packs that have meta.json on disk (or the P0 pair)
    from wildfire_front.open_if.latam_au import ALL_PACK_SPECS, pack_dir_for

    allowed_r6 = {
        eid
        for eid, spec in ALL_PACK_SPECS.items()
        if (pack_dir_for(ROOT / "data" / "open_if" / "latam_au", spec) / "meta.json").is_file()
    }
    allowed_r6 |= {"AU_EMSR500_PERTH", "CL_EMSR647_NACIMIENTO"}
    for r in rows:
        r6 = (r.get("r6") or "0").strip() or "0"
        if r["event_id"] in allowed_r6:
            assert r6 in {"0", "1"}
        else:
            assert r6 == "0"
    # No invented metrics language in notes
    for r in rows:
        notes = (r.get("notes") or "").lower()
        assert "iou=" not in notes
        assert "grade a" not in notes


def test_shortlist_and_license_docs_exist() -> None:
    shortlist = ROOT / "docs" / "data_campaigns" / "LATAM_AU_SHORTLIST.md"
    license_md = ROOT / "docs" / "data_campaigns" / "LATAM_AU_LICENSE_MATRIX.md"
    rights = ROOT / "docs" / "data_campaigns" / "LATAM_AU_RIGHTS.md"
    assert shortlist.is_file()
    assert license_md.is_file()
    assert rights.is_file()
    text = shortlist.read_text(encoding="utf-8")
    assert "AU_EMSR500_PERTH" in text
    assert "CL_EMSR647_NACIMIENTO" in text
    assert "R6" in text
    lic = license_md.read_text(encoding="utf-8")
    assert "Copernicus" in lic
    assert "MapBiomas" in lic
    assert "request" in lic.lower()


def test_probe_rejected_for_unsafe_url() -> None:
    result = inv.probe_url("http://127.0.0.1/", timeout=1.0)
    assert result["status"] == "rejected"
    assert result["error"]


def test_inventory_rows_not_checked_has_no_fake_http() -> None:
    records = [
        inv.UrlRecord(
            source_id="X",
            name="X",
            country_or_region="AU",
            role="t",
            url="https://example.com",
            license_class="open",
            access="open",
            lab_ok_provisional="True",
            notes="",
        )
    ]
    rows = inv.inventory_rows(records, check=False, timeout=1.0)
    assert rows[0]["status"] == "not_checked"
    assert rows[0]["http_code"] == ""
    assert rows[0]["elapsed_ms"] == ""
