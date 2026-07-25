"""Offline tests for Extremadura RAI industrial pack path."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_verify_ext_honest_report_derives_from_packs(tmp_path: Path, monkeypatch):
    """A9: honest.* must derive from pack scorecards, never hardcode True."""
    spec = importlib.util.spec_from_file_location(
        "verify_ext_industrial_e2e",
        ROOT / "scripts" / "verify_ext_industrial_e2e.py",
    )
    assert spec and spec.loader
    ver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ver)

    out = tmp_path / "open_if"
    out.mkdir()
    # Dishonest pack: missing vp_invented → must not claim no_invented_vp True
    pdir = out / "ext_fake_20250101"
    pdir.mkdir()
    (pdir / "scorecard_ext_industrial.json").write_text(
        json.dumps(
            {
                "verdict": "PARTIAL",
                "decision_open": "HOLD",
                # vp_invented intentionally omitted
                "firms_hull_is_official_burned_area": False,
            }
        ),
        encoding="utf-8",
    )
    (pdir / "manifest.json").write_text(json.dumps({"area_rai_ha": 1.0}), encoding="utf-8")

    inv = tmp_path / "inventory"
    inv.mkdir()
    (inv / "event_catalog.csv").write_text("id\n", encoding="utf-8")
    (inv / "selection_gold.json").write_text(
        json.dumps({"gold": [], "silver": [], "events": {}}), encoding="utf-8"
    )

    monkeypatch.setattr(ver, "OUT", out)
    monkeypatch.setattr(ver, "INV", inv)
    md = tmp_path / "EXT.md"
    js = tmp_path / "EXT.json"
    monkeypatch.setattr(ver, "MD", md)
    monkeypatch.setattr(ver, "JS", js)
    monkeypatch.setattr(
        "sys.argv",
        ["verify_ext_industrial_e2e.py", "--skip-pytest"],
    )

    rc = ver.main()
    assert rc in (0, 1)  # may be partial overall
    report = json.loads(js.read_text(encoding="utf-8"))
    assert report["honest"]["no_invented_vp"] is False
    assert report["packs"]
    assert report["packs"][0]["vp_invented_ok"] is False


def test_inventory_and_build_offline(tmp_path, monkeypatch):
    pyshp = pytest.importorskip("shapefile")
    pytest.importorskip("shapely")
    pytest.importorskip("pyproj")

    # Minimal synthetic polygon in EPSG:25829-like meters near Extremadura
    # Use geographic coords already in 4326 for simplicity in test shp
    raw = tmp_path / "raw" / "TestMun"
    raw.mkdir(parents=True)
    shp_path = raw / "test.shp"
    w = pyshp.Writer(str(shp_path), shapeType=pyshp.POLYGON)
    w.field("OBJECTID", "N")
    w.field("Id_incen", "N", decimal=0)
    w.field("Hectareas", "N", decimal=4)
    w.field("MEDICION", "N")
    w.field("fecha_det", "C", size=24)
    w.field("fecha_ext", "C", size=24)
    # small square in lon/lat degrees (geographic)
    # Clockwise exterior ring for shapefile polygon orientation
    ring = [[-6.3, 40.3], [-6.3, 40.31], [-6.29, 40.31], [-6.29, 40.3], [-6.3, 40.3]]
    w.poly([ring])
    w.record(1, 2025999999, 100.0, 5, "2025/08/01 00:00:00.000", "2025/08/05 00:00:00.000")
    w.close()
    # Write geographic WGS84 prj
    (raw / "test.prj").write_text(
        'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137,298.257223563]],'
        'PRIMEM["Greenwich",0],UNIT["Degree",0.017453292519943295]]',
        encoding="utf-8",
    )

    inv_out = tmp_path / "inventory"
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "inventory_ext_rai", ROOT / "scripts" / "inventory_ext_rai.py"
    )
    inv = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(inv)
    rows = inv.inventory_dir(tmp_path / "raw")
    assert len(rows) == 1
    assert rows[0]["id_incen"] == "2025999999"
    sel = inv.select_gold(rows)
    assert sel["gold"] == ["2025999999"]
    inv_out.mkdir()
    (inv_out / "selection_gold.json").write_text(json.dumps(sel), encoding="utf-8")
    # fix shp_path relative to ROOT for builder — rewrite with absolute under tmp and patch selection
    # Builder joins ROOT / shp_path; copy selection events with path relative by monkeypatching ROOT
    # Simpler: call build_one with synthetic event pointing to absolute via symlink under data
    # Use pack builder's load via path relative: write into repo tests fixtures temp under ROOT
    fix_dir = ROOT / "tests" / "fixtures" / "ext_rai_tmp"
    if fix_dir.exists():
        for p in fix_dir.rglob("*"):
            if p.is_file():
                p.unlink()
    dest = fix_dir / "raw" / "TestMun"
    dest.mkdir(parents=True, exist_ok=True)
    for f in raw.iterdir():
        (dest / f.name).write_bytes(f.read_bytes())
    rel = str((dest / "test.shp").relative_to(ROOT)).replace("\\", "/")
    event = {
        **sel["events"]["2025999999"],
        "shp_path": rel,
        "municipio": "TestMun",
        "fecha_det": "2025-08-01",
        "fecha_ext": "2025-08-05",
        "hectareas_attr": 100.0,
    }
    spec2 = importlib.util.spec_from_file_location(
        "build_ext_if_pack", ROOT / "scripts" / "build_ext_if_pack.py"
    )
    build = importlib.util.module_from_spec(spec2)
    assert spec2 and spec2.loader
    spec2.loader.exec_module(build)
    pack_dir = build.build_one(event, skip_firms=True, skip_dnbr=True)
    assert (pack_dir / "vectors" / "perimeter_rai.geojson").is_file()
    sc = json.loads((pack_dir / "scorecard_ext_industrial.json").read_text(encoding="utf-8"))
    assert sc["vp_invented"] is False
    assert sc["firms_hull_is_official_burned_area"] is False
    assert sc["decision_open"] == "HOLD"
    assert sc["verdict"] in {"GO_OPEN_EXT_O2", "PARTIAL", "NO_GO"}
    # cleanup pack + fixture
    import shutil

    if pack_dir.exists() and pack_dir.name.startswith("ext_"):
        shutil.rmtree(pack_dir, ignore_errors=True)
    shutil.rmtree(fix_dir, ignore_errors=True)


def test_zips_present_or_skip():
    base = ROOT / "data" / "open_if" / "extremadura_rai_2025"
    zips = list(base.glob("*.zip"))
    if not zips:
        pytest.skip("no RAI zips downloaded")
    assert any("Caminomorisco" in z.name for z in zips)
