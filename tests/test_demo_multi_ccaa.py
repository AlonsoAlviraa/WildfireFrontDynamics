"""Tests for multi-CCAA demo hub builder (Tobarra + Níjar + Caminomorisco)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "demo_multi_ccaa"


def _load_builder():
    spec = importlib.util.spec_from_file_location(
        "build_demo_multi_ccaa", ROOT / "scripts" / "build_demo_multi_ccaa.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_builder_runs_and_writes_artifacts():
    mod = _load_builder()
    man = mod.build()
    assert (OUT / "index.html").is_file()
    assert (OUT / "demo_manifest.json").is_file()
    assert man.get("schema") in {
        "demo_multi_ccaa_v1",
        "demo_multi_ccaa_v2",
        "demo_multi_ccaa_v3",
    }
    assert len(man.get("sites") or []) == 3
    assert (OUT / "data" / "kpi_board.json").is_file()
    assert (OUT / "data" / "compare_matrix.json").is_file()
    assert (OUT / "data" / "scoreboard.json").is_file()
    assert (OUT / "export" / "pitch_onepager.md").is_file()
    assert (OUT / "export" / "guion_12min.md").is_file()


def test_index_html_contains_three_sites():
    mod = _load_builder()
    mod.build()
    html = (OUT / "index.html").read_text(encoding="utf-8")
    assert "Tobarra" in html
    assert "Níjar" in html or "Nijar" in html
    assert "Caminomorisco" in html
    assert "Guion" in html
    assert "HOLD" in html
    assert "panel=tobarra" in html or 'data-panel="tobarra"' in html
    assert "panel=nijar" in html or 'data-panel="nijar"' in html
    assert "panel=camino" in html or 'data-panel="camino"' in html
    # Sales front sections (mega-plan)
    assert "KPIs" in html or "kpi-strip" in html or 'id="kpis"' in html
    assert "Scoreboard" in html or "scoreboard" in html
    assert "Comparar" in html or "compare" in html
    assert "Sell kit" in html or "CTA" in html or "feedback" in html.lower()
    assert "Exportar pitch" in html or "btn-print" in html
    assert "whatif" in html.lower() or "What-if" in html


def test_demo_manifest_sites_required_keys():
    mod = _load_builder()
    man = mod.build()
    sites = man["sites"]
    assert len(sites) == 3
    by_id = {s["id"]: s for s in sites}
    assert set(by_id) == {"tobarra", "nijar", "camino"}

    required = {
        "id",
        "panel",
        "name",
        "ccaa",
        "track",
        "verdict",
        "key_numbers",
        "attribution",
        "links",
        "vp_invented",
    }
    for sid, site in by_id.items():
        missing = required - set(site.keys())
        assert not missing, f"{sid} missing {missing}"
        assert site["panel"] in {"tobarra", "nijar", "camino"}
        assert isinstance(site["key_numbers"], dict)
        # All three sites must expose area_ha key (value may be None if pack SKIP)
        assert "area_ha" in site["key_numbers"], f"{sid} missing area_ha"


def test_kpi_board_and_sales_sections():
    mod = _load_builder()
    man = mod.build()
    assert man.get("schema") in {"demo_multi_ccaa_v2", "demo_multi_ccaa_v3"}
    kpi = json.loads((OUT / "data" / "kpi_board.json").read_text(encoding="utf-8"))
    assert kpi.get("n_sites") == 3
    assert kpi.get("n_ccaa") >= 3
    assert isinstance(kpi.get("kpis"), list) and len(kpi["kpis"]) >= 6
    html = (OUT / "index.html").read_text(encoding="utf-8")
    assert "mini-map" in html
    assert "leaflet" in html.lower()
    assert "Guion interactivo" in html or "guion-start" in html
    # forbidden overclaims (honesty disclaimers may say "not 99.9999%")
    low = html.lower()
    assert "apagamos incendios" not in low
    # Affirmative magic accuracy claim forbidden; "is not 99.9999%" disclaimers OK
    assert "99.9999% de precisión" not in low
    assert "99.9999% accuracy" not in low
    for m in __import__("re").finditer(r"99\.9999%", low):
        window = low[max(0, m.start() - 40) : m.end() + 10]
        assert "not " in window or "no " in window or "≠" in window or "no reclam" in window


def test_no_invented_vp():
    mod = _load_builder()
    man = mod.build()
    honesty = man.get("honesty") or {}
    assert honesty.get("vp_invented") is False
    assert honesty.get("any_vp_invented") is False
    assert honesty.get("policy_never_invent_vp") is True
    assert honesty.get("firms_hull_is_official_burned_area") is False
    assert honesty.get("no_tactical_dispatch") is True
    for site in man["sites"]:
        assert site.get("vp_invented") is False
        kn = site.get("key_numbers") or {}
        assert kn.get("vp_invented") in (False, None)
        if site["id"] != "tobarra":
            assert kn.get("vp_m_min") is None


def test_tobarra_anchor_numbers_when_present():
    anchors_path = ROOT / "data" / "infocam_anchors.json"
    if not anchors_path.is_file():
        return
    anchors = json.loads(anchors_path.read_text(encoding="utf-8"))
    tb = (anchors.get("anchors") or {}).get("tobarra_20240802") or {}
    if tb.get("status") != "confirmed":
        return
    mod = _load_builder()
    man = mod.build()
    site = next(s for s in man["sites"] if s["id"] == "tobarra")
    kn = site["key_numbers"]
    assert kn.get("vp_m_min") == float(tb["vp_m_min"])
    assert kn.get("area_ha") == float(tb["area_ha"])
    html = (OUT / "index.html").read_text(encoding="utf-8")
    assert site.get("status_anchor") == "confirmed"
    assert "confirmed" in html or "OPS gold" in html or "7" in html


def test_and_ext_packs_linked_when_present():
    mod = _load_builder()
    man = mod.build()
    by_id = {s["id"]: s for s in man["sites"]}
    and_pack = ROOT / "outputs" / "open_if" / "and_2024040053_20240606"
    ext_pack = ROOT / "outputs" / "open_if" / "ext_2025100393_20250729"
    if and_pack.is_dir() and (and_pack / "map.html").is_file():
        href = by_id["nijar"]["links"].get("map")
        assert href
        assert href.startswith("../")
        assert "open_if" in href
        assert not href.startswith("file:")
        assert ":\\" not in href and not (len(href) > 1 and href[1] == ":")
        ha = by_id["nijar"]["key_numbers"].get("area_ha")
        assert ha is not None and ha > 1000
    if ext_pack.is_dir() and (ext_pack / "map.html").is_file():
        href = by_id["camino"]["links"].get("map")
        assert href
        assert href.startswith("../")
        ha = by_id["camino"]["key_numbers"].get("area_ha")
        assert ha is not None and ha > 1000


def test_html_attributions_and_hold():
    mod = _load_builder()
    mod.build()
    html = (OUT / "index.html").read_text(encoding="utf-8")
    assert "INFOCAM" in html
    assert "REDIAM" in html
    assert "RAI" in html
    assert "HOLD" in html
    assert "FIRMS hull" in html or "hull" in html.lower()


def test_html_escapes_dynamic_fields(monkeypatch, tmp_path):
    """Inject malicious attribution via fake pack paths and ensure it is escaped."""
    mod = _load_builder()
    and_dir = tmp_path / "and_pack"
    and_dir.mkdir()
    payload = "<img src=x onerror=alert(1)>"
    reason_payload = "<script>alert(2)</script>"
    (and_dir / "manifest.json").write_text(
        json.dumps(
            {
                "pack_id": "and_evil",
                "codigo": "EVIL",
                "fecha_inc": "2024-01-01",
                "area_rediam_ha": 10.0,
                "municipio": "X",
                "attribution": payload,
            }
        ),
        encoding="utf-8",
    )
    (and_dir / "scorecard_and_industrial.json").write_text(
        json.dumps(
            {
                "verdict": "GO_OPEN_AND_O2",
                "decision_open": "HOLD",
                "vp_invented": False,
                "firms_hull_is_official_burned_area": False,
                "attribution": payload,
            }
        ),
        encoding="utf-8",
    )
    (and_dir / "map.html").write_text("<html></html>", encoding="utf-8")

    # Poison decision-card reasons/disclaimers
    evil_card = tmp_path / "evil_card.json"
    evil_card.write_text(
        json.dumps(
            {
                "event_id": "evil",
                "decision": "HOLD",
                "system_reliability_pass": False,
                "reasons": [reason_payload],
                "disclaimers": [payload, "Not a tactical dispatch order."],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "AND_PACK", and_dir)
    monkeypatch.setattr(
        mod,
        "DECISION_CARD_CANDIDATES",
        [("gold_e2e", evil_card, "Evil card", "live")],
    )
    # Keep real EXT + anchors; only AND is poisoned
    man = mod.build()
    html = (OUT / "index.html").read_text(encoding="utf-8")
    assert payload not in html
    assert reason_payload not in html
    assert "&lt;img" in html
    assert "&lt;script&gt;" in html or "&lt;script" in html
    nj = next(s for s in man["sites"] if s["id"] == "nijar")
    assert nj["key_numbers"]["area_ha"] == 10.0
    # Disclaimer honesty still present (escaped content ok)
    assert "Not a tactical dispatch order" in html


def test_fail_soft_missing_packs(monkeypatch, tmp_path):
    mod = _load_builder()
    empty_and = tmp_path / "missing_and"
    empty_ext = tmp_path / "missing_ext"
    empty_and.mkdir()
    empty_ext.mkdir()
    monkeypatch.setattr(mod, "AND_PACK", empty_and)
    monkeypatch.setattr(mod, "EXT_PACK", empty_ext)
    man = mod.build()
    assert man["skips"]["and_pack"].startswith("SKIP")
    assert man["skips"]["ext_pack"].startswith("SKIP")
    by_id = {s["id"]: s for s in man["sites"]}
    assert by_id["nijar"]["links"].get("map") is None
    assert by_id["camino"]["links"].get("map") is None
    assert by_id["nijar"]["key_numbers"].get("area_ha") is None
    assert by_id["camino"]["key_numbers"].get("fecha_det") is None
    assert by_id["camino"]["key_numbers"].get("fecha_ext") is None
    assert by_id["nijar"]["year_label"] == "—"
    assert by_id["camino"]["year_label"] == "—"
    # No invented plan dates in year_label when packs missing
    assert by_id["nijar"]["year_label"] != "2024-06-06"
    assert "2025-07-29" not in str(by_id["camino"]["year_label"])
    # rebuild main with monkeypatched paths
    assert mod.main() == 0


def test_verdict_class_no_gold_false_positive():
    mod = _load_builder()
    assert mod._verdict_class("GOLD only") == "muted"
    assert mod._verdict_class("NO_GO") == "bad"
    assert mod._verdict_class("GO_OPEN_AND_O2") == "ok"
    assert mod._verdict_class("GO_OPS") == "ok"
    assert mod._verdict_class("Grade A / OPS gold") == "ok"
    assert mod._verdict_class("PARTIAL") == "warn"
    assert mod._verdict_class("HOLD") == "warn"
    assert mod._verdict_class("PENDING") == "bad"


def test_tobarra_unconfirmed_no_confirmed_claim(monkeypatch, tmp_path):
    mod = _load_builder()
    anchors = tmp_path / "anchors.json"
    # Provisional numbers present but status not confirmed → must NOT publish Vp/ha
    anchors.write_text(
        json.dumps(
            {
                "anchors": {
                    "tobarra_20240802": {
                        "status": "pending_external",
                        "vp_m_min": 99.0,
                        "area_ha": 1234.0,
                        "source": "provisional draft",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "ANCHORS_PATH", anchors)
    man = mod.build()
    html = (OUT / "index.html").read_text(encoding="utf-8")
    # Hero strip must not claim confirmed when anchor is pending
    assert "ha · ancla confirmed" not in html
    assert "ha confirmed." not in html  # guion phrase when confirmed
    tb = next(s for s in man["sites"] if s["id"] == "tobarra")
    assert tb.get("status_anchor") == "pending_external"
    assert tb["key_numbers"].get("vp_m_min") is None
    assert tb["key_numbers"].get("area_ha") is None
    assert "99" not in (tb.get("headline") or "")
    assert "1234" not in (tb.get("headline") or "")
    assert "pending_external" in html


def test_main_exit_code_zero():
    mod = _load_builder()
    assert mod.main() == 0


def test_scoreboard_rows_and_export_files():
    mod = _load_builder()
    man = mod.build()
    sb = json.loads((OUT / "data" / "scoreboard.json").read_text(encoding="utf-8"))
    assert isinstance(sb, list) and len(sb) == 3
    by_id = {r.get("id"): r for r in sb}
    for row in sb:
        assert "name" in row
        assert "verdict" in row
        assert "O2" in row or "FIRMS" in row
    # Tobarra OPS must NOT synthesize industrial O2/NO_FALSE_DISPATCH PASS
    tb = by_id.get("tobarra") or {}
    assert tb.get("O2") != "PASS"
    assert str(tb.get("O2") or "").lower().startswith("n/a") or tb.get("O2") in {"—", "n/a (OPS)"}
    assert tb.get("NO_FALSE_DISPATCH") in {"—", None}
    assert (OUT / "export" / "pitch_onepager.html").is_file()
    pitch_html = (OUT / "export" / "pitch_onepager.html").read_text(encoding="utf-8")
    assert "Tobarra" in pitch_html
    assert "HOLD" in pitch_html or "Decision" in pitch_html
    assert man.get("exports", {}).get("pitch_html") == "export/pitch_onepager.html"
    guion = (OUT / "export" / "guion_12min.md").read_text(encoding="utf-8")
    assert "Guion 12 min" in guion
    assert "Tobarra" in guion and "Níjar" in guion
    assert "0:00" in guion or "0:45" in guion


def test_modes_strings_and_i18n_in_html():
    mod = _load_builder()
    mod.build()
    html = (OUT / "index.html").read_text(encoding="utf-8")
    assert "mode=pitch" in html or "btn-mode-pitch" in html
    assert "mode=guion" in html or "btn-mode-guion" in html
    assert "mode-full" in html or "btn-mode-full" in html
    assert "hero_title" in html
    assert "Multi-region decision support" in html or "decision support" in html.lower()
    assert "btn-lang" in html


def test_no_fake_pack_dates_when_present_or_skip():
    """year_label must not invent fixed plan defaults when packs missing (covered soft);
    when packs present, labels come from pack fields only."""
    mod = _load_builder()
    man = mod.build()
    by_id = {s["id"]: s for s in man["sites"]}
    # Never claim a tactical dispatch string
    html = (OUT / "index.html").read_text(encoding="utf-8")
    low = html.lower()
    assert (
        "despacho táctico" not in low
        or "no despacho" in low
        or "sin despacho" in low
        or "no_tactical" in str(man)
    )
    assert "orden táctica" not in low
    # Sites always have year_label key
    for sid in ("tobarra", "nijar", "camino"):
        assert "year_label" in by_id[sid]


def test_forbidden_commercial_claims():
    mod = _load_builder()
    mod.build()
    html = (OUT / "index.html").read_text(encoding="utf-8").lower()
    assert "99% de precisión" not in html
    assert "99% accuracy" not in html
    assert "apagamos incendios con ia" not in html
    assert "sustituimos infoca" not in html
    assert "inventamos vp" not in html or "no inventamos" in html
    # Positive honesty markers
    assert "hold" in html
    assert "rediam" in html
    assert "rai" in html


def test_decision_card_skip_or_present():
    mod = _load_builder()
    man = mod.build()
    cards = man.get("decision_cards") or []
    assert isinstance(cards, list) and len(cards) >= 1
    assert (OUT / "data" / "decision_cards.json").is_file()
    html = (OUT / "index.html").read_text(encoding="utf-8")
    assert "Decision Card" in html or "decision" in html.lower()
    # Soft SKIP language allowed when no cards; or GO/HOLD when present
    statuses = {c.get("status") for c in cards}
    assert statuses & {"OK", "SKIP"} or any(c.get("decision") for c in cards)
    # Never invent a tactical GO claim without source
    for c in cards:
        if c.get("status") == "SKIP":
            assert c.get("decision") in {"SKIP", "—", None} or "SKIP" in str(c.get("reasons"))
    # Disclaimers must surface (sales honesty)
    assert "Not a tactical dispatch order" in html
    # Sample schema must not look like anonymous field GO
    samples = [c for c in cards if c.get("kind") == "schema_sample"]
    if samples:
        assert "SAMPLE SCHEMA" in html or "sample" in html.lower()
    # reliability_pass=false emphasized when GO cards present
    if any(c.get("system_reliability_pass") is False for c in cards if c.get("status") == "OK"):
        assert "Reliability gate not green" in html or "not a tactical GO" in html.lower()


def test_decision_card_soft_skip_all_missing(monkeypatch, tmp_path):
    """When all decision-card sources are missing → single SKIP, no invented GO."""
    mod = _load_builder()
    empty = tmp_path / "no_cards"
    empty.mkdir()
    monkeypatch.setattr(
        mod,
        "DECISION_CARD_CANDIDATES",
        [
            ("gold_e2e", empty / "missing_gold.json", "Tobarra gold E2E", "live"),
            ("forensic_demo", empty / "missing_forensic.json", "Forensic demo", "live"),
            ("docs_schema", empty / "missing_docs.json", "Hub schema sample", "schema_sample"),
        ],
    )
    man = mod.build()
    cards = man.get("decision_cards") or []
    assert man.get("skips", {}).get("decision_cards") == "SKIP_none_found"
    assert len(cards) == 1
    assert cards[0].get("status") == "SKIP"
    assert cards[0].get("decision") == "SKIP"
    assert cards[0].get("id") == "none"
    html = (OUT / "index.html").read_text(encoding="utf-8")
    assert "SKIP" in html
    assert "no se encontró fire_decision_card" in html or "SKIP" in html
    # Must not invent a live GO from thin air
    live_go = [
        c
        for c in cards
        if c.get("status") == "OK" and str(c.get("decision", "")).upper().startswith("GO")
    ]
    assert not live_go


def test_panel_decision_deep_link_not_tobarra():
    mod = _load_builder()
    mod.build()
    html = (OUT / "index.html").read_text(encoding="utf-8")
    # highlight only known site panels; decision opens #decision
    assert "SITE_PANELS" in html or "panel === 'decision'" in html
    assert "openSection('decision')" in html or 'openSection("decision")' in html
    # old false-positive ternary default tobarra for unknown panels must be gone
    assert "p === 'nijar' ? 'nijar' : p === 'camino' ? 'camino' : 'tobarra'" not in html


def test_la_mierla_soft_optional():
    mod = _load_builder()
    man = mod.build()
    # Core pitch remains 3 sites
    assert len(man.get("sites") or []) == 3
    lm = man.get("la_mierla")
    pack = ROOT / "outputs" / "open_if" / "la_mierla_20260717"
    if pack.is_dir():
        assert lm is not None
        assert lm.get("optional") is True
        assert "HOLD" in str(lm.get("decision_open") or lm.get("verdict") or "").upper() or lm.get(
            "decision_open"
        )
        html = (OUT / "index.html").read_text(encoding="utf-8")
        assert "La Mierla" in html
        assert "Más IF open" in html or "la_mierla" in html
        assert man.get("skips", {}).get("la_mierla") == "OK"
    else:
        assert lm is None
        assert str(man.get("skips", {}).get("la_mierla", "")).startswith("SKIP")


def test_version_stamp_and_provenance():
    mod = _load_builder()
    man = mod.build()
    assert man.get("demo_version")
    html = (OUT / "index.html").read_text(encoding="utf-8")
    assert "demo_version" in html
    assert man.get("demo_version") in html
    assert "provenance" in html.lower() or "Provenance" in html
    assert "rediam.atiende" in html or "rai@juntaex" in html or "INFOCAM" in html
    # git_short may be None offline without git — key present in manifest
    assert "git_short" in man
    assert "git" in html.lower()


def test_charts_gates_and_commander_links():
    mod = _load_builder()
    man = mod.build()
    html = (OUT / "index.html").read_text(encoding="utf-8")
    assert "Gates PASS" in html or "Total gates" in html or "gates" in html.lower()
    assert "Commander" in html
    assert "PORTAL" in html or "Portal" in html
    assert "../../docs/commander" in html or "commander/index.html" in html
    # charts meta written
    assert (OUT / "data" / "charts_meta.json").is_file()
    meta = json.loads((OUT / "data" / "charts_meta.json").read_text(encoding="utf-8"))
    assert "gate_counts" in meta
    assert man.get("schema") == "demo_multi_ccaa_v3"


def test_demo_charts_module_standalone():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "demo_charts", ROOT / "scripts" / "demo_charts.py"
    )
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    sites = [
        {
            "id": "a",
            "name_display": "A",
            "track": "OPEN_O2",
            "gates": {"O2": "PASS", "FIRMS": "SKIP", "X": "FAIL"},
            "key_numbers": {"area_ha": 100.0, "fecha_det": "2025-07-01", "fecha_ext": "2025-07-10"},
        }
    ]
    c = m.gate_status_counts(sites)
    assert c["PASS"] == 1 and c["SKIP"] == 1 and c["FAIL"] == 1
    assert m.duration_days("2025-07-01", "2025-07-10") == 9
    svg = m.svg_gates_stacked(sites)
    assert "PASS" in svg and "svg" in svg
    tl = m.svg_timeline_camino("2025-07-01", "2025-07-10", area_ha=100.0)
    assert "días" in tl or "det" in tl
