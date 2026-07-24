"""AND REDIAM open_if pack tests — offline fixture, no live WFS/FIRMS."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "rediam_and" / "sample_perim_3042.geojson"


def _load_pack_mod():
    spec = importlib.util.spec_from_file_location(
        "build_and_if_pack", ROOT / "scripts" / "build_and_if_pack.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_build_pack_from_fixture_offline(tmp_path: Path):
    mod = _load_pack_mod()
    feat, meta = mod.load_feature_from_geojson(FIXTURE, codigo="TEST2024070001", index=None)
    out = tmp_path / "open_if"
    result = mod.build_pack_from_feature(
        feat,
        out_root=out,
        meta=meta,
        skip_firms=True,
        skip_dnbr=True,
        codigo_override="TEST2024070001",
    )
    pack_dir = result["pack_dir"]
    assert pack_dir.is_dir()
    for rel in (
        "manifest.json",
        "vectors/perimeter_rediam.geojson",
        "metrics_o2.json",
        "scorecard_and_industrial.json",
        "map.html",
        "operator_brief_open_if.md",
        "provenance.json",
        "dnbr_status.json",
    ):
        assert (pack_dir / rel).is_file(), rel

    manifest = json.loads((pack_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["codigo"] == "TEST2024070001"
    assert float(manifest["area_rediam_ha"]) > 100
    assert "REDIAM" in manifest["attribution"]
    assert manifest["vp_tactical"] is None
    assert manifest["requires_lwir_heligraphics"] is False

    metrics = json.loads((pack_dir / "metrics_o2.json").read_text(encoding="utf-8"))
    assert metrics["area_rediam_ha"] > 100
    notes = " ".join(metrics.get("honest_notes") or [])
    assert "proxy" in notes.lower() or "FIRMS" in notes

    sc = json.loads((pack_dir / "scorecard_and_industrial.json").read_text(encoding="utf-8"))
    assert sc["gates"]["O2_REDIAM"] == "PASS"
    assert sc["gates"]["PROVENANCE"] == "PASS"
    assert sc["gates"]["NO_FALSE_DISPATCH"] == "PASS"
    assert sc["vp_invented"] is False
    assert sc["firms_hull_is_official_burned_area"] is False
    assert sc["decision_open"] == "HOLD"
    assert sc["verdict"] in {"GO_OPEN_AND_O2", "PARTIAL"}

    # Perimeter WGS84 lon/lat
    per = json.loads(
        (pack_dir / "vectors" / "perimeter_rediam.geojson").read_text(encoding="utf-8")
    )
    coords = per["features"][0]["geometry"]["coordinates"][0][0]
    lon, lat = coords[0], coords[1]
    assert -180 <= lon <= 180
    assert -90 <= lat <= 90

    brief = (pack_dir / "operator_brief_open_if.md").read_text(encoding="utf-8")
    assert "REDIAM" in brief
    assert "Junta" in brief

    dnbr = json.loads((pack_dir / "dnbr_status.json").read_text(encoding="utf-8"))
    assert dnbr["status"] in {"SKIP", "BLOCKED", "GO"}


def test_attribution_ok_requires_written_content():
    mod = _load_pack_mod()
    # Literals alone are what we refuse to inject in pack build — helper still
    # checks whatever strings it is given; empty written props must FAIL.
    assert (
        mod.attribution_ok_from_written(
            perimeter_feature_props={},
            perimeter_fc_props={},
            provenance_obj={},
            brief_text="no source cited",
        )
        is False
    )
    assert (
        mod.attribution_ok_from_written(
            perimeter_feature_props={"attribution": "Fuente: REDIAM — Junta de Andalucía"},
            perimeter_fc_props={},
            provenance_obj={},
            brief_text="",
        )
        is True
    )
    # Injecting only mun/prov without REDIAM/Junta fails
    assert mod.attribution_ok_from_text("Níjar", "Almería") is False
    # Must not pass when only unrelated text
    assert mod.attribution_ok_from_text("NASA FIRMS only") is False


def test_scorecard_no_false_dispatch():
    mod = _load_pack_mod()
    sc = mod.build_scorecard(
        pack_id="and_test",
        has_perimeter=True,
        attribution_ok=True,
        firms_status="SKIP",
        n_firms=0,
        haus_status="SKIP",
        dnbr_status="SKIP",
    )
    assert sc["decision_open"] == "HOLD"
    assert sc["gates"]["NO_FALSE_DISPATCH"] == "PASS"
    assert sc["gates"]["REPRO"] == "SKIP"  # not auto-PASS at pack build
    assert sc["firms_hull_is_official_burned_area"] is False
    assert sc["verdict"] in {"PARTIAL", "GO_OPEN_AND_O2"}


def test_scorecard_repro_fail_not_go():
    mod = _load_pack_mod()
    sc = mod.build_scorecard(
        pack_id="and_repro_fail",
        has_perimeter=True,
        attribution_ok=True,
        firms_status="GO",
        n_firms=10,
        haus_status="GO",
        dnbr_status="GO",
        repro_status="FAIL",
    )
    assert sc["gates"]["REPRO"] == "FAIL"
    assert sc["verdict"] != "GO_OPEN_AND_O2"
    assert sc["verdict"] == "PARTIAL"


def test_scorecard_dispatch_go_fails_gate():
    mod = _load_pack_mod()
    sc = mod.build_scorecard(
        pack_id="and_bad_dispatch",
        has_perimeter=True,
        attribution_ok=True,
        firms_status="GO",
        n_firms=5,
        haus_status="SKIP",
        dnbr_status="SKIP",
        decision_open="GO",
    )
    assert sc["gates"]["NO_FALSE_DISPATCH"] == "FAIL"
    assert sc["verdict"] == "NO_GO"


def test_scorecard_no_perimeter_is_nogo():
    mod = _load_pack_mod()
    sc = mod.build_scorecard(
        pack_id="and_bad",
        has_perimeter=False,
        attribution_ok=False,
        firms_status="SKIP",
        n_firms=0,
        haus_status="SKIP",
        dnbr_status="SKIP",
    )
    assert sc["verdict"] == "NO_GO"


def test_null_geometry_raises():
    mod = _load_pack_mod()
    feat = {
        "type": "Feature",
        "properties": {"CODIGO": "BAD", "FECHA_INC": "20240101"},
        "geometry": None,
    }
    import pytest

    with pytest.raises(ValueError, match="missing/null geometry"):
        mod.build_pack_from_feature(
            feat,
            out_root=Path("/tmp/x"),
            meta={"source_path": "x", "feature_index": 0},
            skip_firms=True,
            skip_dnbr=True,
        )


def test_check_pack_honest_fail_closed(tmp_path: Path):
    """Verify-layer honesty must fail when hull claimed official or Vp invented."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "verify_and_industrial_e2e",
        ROOT / "scripts" / "verify_and_industrial_e2e.py",
    )
    assert spec and spec.loader
    ver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ver)

    pack = tmp_path / "and_dishonest_test"
    pack.mkdir()
    (pack / "vectors").mkdir()
    (pack / "vectors" / "perimeter_rediam.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": []}), encoding="utf-8"
    )
    (pack / "map.html").write_text("<html></html>", encoding="utf-8")
    (pack / "operator_brief_open_if.md").write_text("x", encoding="utf-8")
    (pack / "dnbr_status.json").write_text(json.dumps({"status": "SKIP"}), encoding="utf-8")
    (pack / "manifest.json").write_text(
        json.dumps(
            {
                "attribution": "Fuente: REDIAM — Junta de Andalucía",
                "vp_tactical": 7.0,  # invented
                "area_rediam_ha": 100,
            }
        ),
        encoding="utf-8",
    )
    (pack / "metrics_o2.json").write_text(json.dumps({"area_rediam_ha": 100}), encoding="utf-8")
    (pack / "scorecard_and_industrial.json").write_text(
        json.dumps(
            {
                "verdict": "GO_OPEN_AND_O2",
                "vp_invented": True,
                "firms_hull_is_official_burned_area": True,
                "decision_open": "GO",
            }
        ),
        encoding="utf-8",
    )
    (pack / "provenance.json").write_text(json.dumps({"attribution": "REDIAM"}), encoding="utf-8")
    report = ver._check_pack(pack)
    assert report["honest"]["firms_hull_not_official"] is False
    assert report["honest"]["vp_not_invented_ok"] is False
    assert report["honest"]["decision_not_false_go"] is False
    assert report["ok"] is False


def test_check_pack_honest_pass(tmp_path: Path):
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "verify_and_industrial_e2e",
        ROOT / "scripts" / "verify_and_industrial_e2e.py",
    )
    assert spec and spec.loader
    ver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ver)

    pack = tmp_path / "and_honest_test"
    pack.mkdir()
    (pack / "vectors").mkdir()
    (pack / "vectors" / "perimeter_rediam.geojson").write_text("{}", encoding="utf-8")
    (pack / "map.html").write_text("<html></html>", encoding="utf-8")
    (pack / "operator_brief_open_if.md").write_text("REDIAM", encoding="utf-8")
    (pack / "dnbr_status.json").write_text("{}", encoding="utf-8")
    (pack / "manifest.json").write_text(
        json.dumps(
            {
                "attribution": "Fuente: REDIAM — Junta de Andalucía",
                "vp_tactical": None,
            }
        ),
        encoding="utf-8",
    )
    (pack / "metrics_o2.json").write_text(
        json.dumps({"area_rediam_ha": 50, "honest_notes": ["proxy"]}), encoding="utf-8"
    )
    (pack / "scorecard_and_industrial.json").write_text(
        json.dumps(
            {
                "verdict": "PARTIAL",
                "vp_invented": False,
                "firms_hull_is_official_burned_area": False,
                "decision_open": "HOLD",
            }
        ),
        encoding="utf-8",
    )
    (pack / "provenance.json").write_text(
        json.dumps({"attribution": "Fuente: REDIAM — Junta de Andalucía"}),
        encoding="utf-8",
    )
    report = ver._check_pack(pack)
    assert report["honest"]["firms_hull_not_official"] is True
    assert report["honest"]["vp_not_invented_ok"] is True
    assert report["honest"]["decision_not_false_go"] is True


def test_pack_id_stable():
    mod = _load_pack_mod()
    assert mod.pack_id("IIFF2025230035", "2025-07-12") == "and_iiff2025230035_20250712"
    assert mod.pack_id("2024040011", "2024-02-07").startswith("and_2024040011_")


def test_firms_hull_disclaimer_in_metrics():
    mod = _load_pack_mod()
    # 4 points square
    pts = [(-4.0, 38.0), (-3.9, 38.0), (-3.9, 38.1), (-4.0, 38.1)]
    from shapely.geometry import box

    red = box(-4.05, 37.95, -3.85, 38.15)
    metrics, hull_fc = mod.firms_hull_metrics(pts, red)
    assert (
        "NOT official" in metrics["disclaimer"] or "not official" in metrics["disclaimer"].lower()
    )
    if hull_fc is not None:
        props = hull_fc["features"][0]["properties"]
        assert props.get("not_official_perimeter") is True
