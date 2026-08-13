"""Product SPA: builders (brief + map_status) + real CLI entry ``app``."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from wildfire_front.cli import build_parser, main
from wildfire_front.product.app_spa import (
    SCHEMA,
    build_product_app_payload,
    render_product_app_html,
    write_product_app,
)
from wildfire_front.product.fire_catalog import (
    new_fire_intake_steps,
    product_action_catalog,
    scan_fire_catalog,
)

ROOT = Path(__file__).resolve().parents[1]
SLA_WORK = ROOT / "outputs" / "incidents" / "_sla_measure"
FIXTURE_CSV = ROOT / "tests" / "fixtures" / "firms_sample_hotspots.csv"
DEMO_FRONTS = ROOT / "outputs" / "demo_v2" / "fronts.geojson"
_STAMP = ROOT / "docs" / "ML_PRODUCT_GO_STATUS.json"


def _expected_fusion() -> str:
    """Stamp is SSOT for fusion rail. Skip honestly if stamp is missing."""
    if not _STAMP.is_file():
        pytest.skip("ML product stamp missing — cannot assert fusion rail")
    stamp = json.loads(_STAMP.read_text(encoding="utf-8"))
    if stamp.get("field_ops_allow_ml_live_in_fusion") is True:
        return "ON"
    rails = stamp.get("rails") or {}
    raw = rails.get("field_ops_fusion")
    return str(raw).upper() if raw is not None else "OFF"


def _run_main(argv: list[str], capsys) -> tuple[int, str, str]:
    try:
        main(argv)
        code = 0
    except SystemExit as exc:
        raw = exc.code
        if raw is None:
            code = 0
        elif isinstance(raw, int):
            code = raw
        else:
            code = 1
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _run_app_module(argv: list[str]) -> tuple[int, str, str]:
    """Drive the shipped ``python -m wildfire_front app`` entry (not a stub)."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    proc = subprocess.run(
        [sys.executable, "-m", "wildfire_front", *argv],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    return int(proc.returncode), proc.stdout or "", proc.stderr or ""


def test_shipped_app_help_mentions_serve():
    """Verification: real module help exits 0 and mentions app / --serve."""
    c1, o1, e1 = _run_app_module(["app", "--help"])
    assert c1 == 0, e1
    assert o1.strip()
    assert "app" in o1.lower() or "--serve" in o1
    assert "--serve" in o1
    assert "--list-fires" in o1
    c2, o2, e2 = _run_app_module(["app", "--help"])
    assert c2 == 0, e2
    assert "--serve" in o2


def test_shipped_app_list_fires_json_rails():
    """Verification: real ``app --list-fires --json`` reports fusion ON / no GO_Q."""
    code, out, err = _run_app_module(["app", "--list-fires", "--json"])
    assert code == 0, err
    data = json.loads(out)
    rails = data.get("rails") or {}
    assert rails.get("field_ops_ml_live_fusion") == _expected_fusion()
    assert rails.get("go_q_invent_forbidden") is True
    assert rails.get("go_q_met") is not True


def test_payload_fusion_follows_stamp_when_cwd_has_no_catalog(tmp_path: Path, monkeypatch):
    """cwd fail-closed must not contradict stamp/catalog (human #46 ON)."""
    expected = _expected_fusion()
    monkeypatch.chdir(tmp_path)
    payload = build_product_app_payload(live=False, scan=False, repo=ROOT)
    assert payload["rails"]["field_ops_ml_live_fusion"] == expected
    assert payload["rails"]["go_q_invent_forbidden"] is True
    assert payload["rails"]["not_tactical_dispatch"] is True
    # Package-relative catalog/stamp must win even when repo is omitted
    payload_cwd = build_product_app_payload(live=False, scan=False)
    assert payload_cwd["rails"]["field_ops_ml_live_fusion"] == expected
    html = render_product_app_html(payload_cwd)
    assert f'"field_ops_ml_live_fusion": "{expected}"' in html


def test_parser_registers_app():
    parser = build_parser()
    help_text = parser.format_help()
    assert "app" in help_text
    args = parser.parse_args(["app", "--role", "field"])
    assert args.command == "app"
    assert args.role == "field"
    assert hasattr(args, "work_dir")
    assert hasattr(args, "open")
    assert hasattr(args, "serve")
    assert hasattr(args, "port")
    args2 = parser.parse_args(["app", "--list-fires"])
    assert args2.list_fires is True
    args3 = parser.parse_args(["app", "--fire", "_sla_measure"])
    assert args3.fire == "_sla_measure"
    args4 = parser.parse_args(["app", "--serve", "--port", "9876"])
    assert args4.serve is True
    assert args4.port == 9876


def test_fire_catalog_and_actions():
    fires = scan_fire_catalog(ROOT)
    assert isinstance(fires, list)
    actions = product_action_catalog()
    # Industrial inventory: full product surface (plain-language dual-mode)
    assert len(actions) >= 30, f"expected ≥30 product actions, got {len(actions)}"
    groups = {a["group"] for a in actions}
    assert "Campo" in groups or "Mapa" in groups
    # Priority acts inventory (industry dual-mode critical path)
    ids = {a["id"] for a in actions}
    for required in ("decide", "export_acta", "incident_status", "app", "map"):
        assert required in ids, f"missing product action {required}"
    # Every action must expose plain language OR simple_cta for modo fácil
    for a in actions:
        assert a.get("plain") or a.get("simple_cta"), (
            f"action {a.get('id')} missing plain/simple_cta"
        )
        assert a.get("id") and a.get("cmd")
    # Catalog rows expose cmds for primary-acts buttons — every fire (PR02)
    for sample in fires:
        for key in ("rebuild_cmd", "map_cmd", "status_cmd", "decide_cmd", "acta_cmd"):
            assert sample.get(key), f"fire {sample.get('id')} catalog missing {key}"
            assert "python -m wildfire_front" in str(sample[key])
    steps = new_fire_intake_steps()
    assert len(steps) >= 4
    assert any("app" in s.get("cmd", "") for s in steps)


def test_build_payload_brief_only(tmp_path: Path):
    payload = build_product_app_payload(work_dir=None, live=False, title="Test SPA", scan=True)
    assert payload["schema"] == SCHEMA
    assert payload["brief"]["schema"] == "wfd_operator_brief_v1"
    assert payload["map"]["schema"] == "wfd_fire_status_map_v1"
    assert payload["rails"]["field_ops_ml_live_fusion"] == _expected_fusion()
    assert payload["rails"]["not_tactical_dispatch"] is True
    assert payload["rails"]["go_q_invent_forbidden"] is True
    assert payload["brief"]["gates"]["GO_Q"] is not True
    # SPA KPI Producto/Demo reads brief.gates — stamp fallback, not "unknown"
    assert payload["brief"]["gates"]["GO_MES"] is True or str(
        payload["brief"]["gates"]["GO_MES"]
    ).lower() == "true"
    assert payload["brief"]["gates"]["GO_MES"] != "unknown"
    assert payload["brief"]["gates"]["GO_Q"] == "partial"
    assert payload["brief"]["gates"]["GO_Q"] != "unknown"
    assert "Not validated tactical dispatch" in payload["disclaimer"]
    assert isinstance(payload.get("fires"), list)
    assert isinstance(payload.get("product_actions"), list)
    assert len(payload["product_actions"]) >= 30
    for act in payload["product_actions"]:
        assert act.get("plain") or act.get("simple_cta"), act.get("id")
    assert payload.get("new_fire_intake")
    assert payload.get("rebuild", {}).get("selected_cmd")
    # Role switcher payload (PR04) — content, not keys-only
    assert payload.get("role") in ("operator", "field", "lab", "decision")
    assert isinstance(payload.get("role_hints"), dict)
    for r in ("operator", "field", "lab", "decision"):
        assert r in payload["role_hints"]
        h = payload["role_hints"][r]
        assert h.get("id") == r
        assert str(h.get("title") or "").strip(), f"role_hints[{r}].title empty"
        assert str(h.get("primary_cmd") or "").strip(), f"role_hints[{r}].primary_cmd empty"
        assert "wildfire_front" in str(h.get("primary_cmd"))
        assert str(h.get("hint") or h.get("audience") or "").strip()
        assert len(h.get("sequence_head") or []) >= 1, f"role_hints[{r}].sequence_head empty"
    assert payload.get("last_act") is not None
    assert (payload.get("bridge_decide") or {}).get("enabled") is False
    # Pack off by default
    assert payload.get("pack") is None
    html = render_product_app_html(payload)
    assert "leaflet" in html.lower()
    assert "wfd" in html.lower()
    assert "fire-select" in html
    assert "newfire" in html or "Nuevo" in html
    assert "actions" in html or "Acciones" in html
    assert "mode-simple" in html or "Fácil" in html
    assert "btn-copy-rebuild" in html or "Abrir" in html
    assert "glossary" in html or "Términos" in html
    # Industrial C2 shell (Stitch WFD Industrial C2)
    assert "100dvh" in html or "100vh" in html
    assert "map-wrap" in html
    assert "#0B1220" in html  # industrial bg
    assert "IBM Plex Sans" in html or "rail" in html
    # Stress UX: 3 priority acts (industry dual-mode, power not cut)
    assert "btn-act-decide" in html
    assert "btn-act-status" in html
    assert "btn-act-acta" in html
    assert "primary-acts" in html
    # PR04 / PR05 markers
    assert "role-seg" in html
    assert "last-act" in html or "Último acto" in html
    # Embedded payload honesty (exact OFF — no soft fusion fallback)
    assert f'"field_ops_ml_live_fusion": "{_expected_fusion()}"' in html
    assert '"go_q_invent_forbidden": true' in html
    paths = write_product_app(payload, tmp_path)
    assert paths["html"].is_file()
    assert paths["json"].is_file()
    reloaded = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert reloaded["schema"] == SCHEMA
    assert "fires" in reloaded


def test_build_payload_with_work_dir_or_geojson(tmp_path: Path):
    if SLA_WORK.is_dir():
        payload = build_product_app_payload(work_dir=SLA_WORK, live=False)
        assert payload["work_dir"]
        # SLA fixture has decision card + ops + geojson
        assert payload["decision_card"] is not None
        assert str(payload["decision_card"].get("decision") or "").upper() in (
            "GO",
            "HOLD",
            "ABSTAIN",
        )
        assert (payload.get("connectivity") or {}).get("local_layers", 0) >= 1
        assert payload["hero"]["decision"] in ("GO", "HOLD", "ABSTAIN")
    else:
        gj = tmp_path / "front.geojson"
        gj.write_text(
            json.dumps(
                {
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "properties": {"name": "test"},
                            "geometry": {
                                "type": "LineString",
                                "coordinates": [[-3.12, 40.94], [-3.08, 40.97]],
                            },
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        payload = build_product_app_payload(
            geojson_paths=[gj], live=False, fixture_csv=FIXTURE_CSV if FIXTURE_CSV.is_file() else None
        )
        assert any(
            (row.get("source") == "local") for row in (payload.get("layer_summary") or [])
        )


def test_cli_list_fires(capsys):
    code, out, err = _run_main(["app", "--list-fires", "--json"], capsys)
    assert code == 0, err
    data = json.loads(out)
    assert data["schema"] == "wfd_fire_catalog_v1"
    assert "fires" in data
    rails = data.get("rails") or {}
    assert rails.get("field_ops_ml_live_fusion") == _expected_fusion()
    assert rails.get("go_q_invent_forbidden") is True
    assert rails.get("go_q_met") is False
    assert rails.get("not_tactical_dispatch") is True
    assert "fusion ON" in (data.get("note") or "") or "fusion" in (data.get("note") or "")


def test_cli_app_json_and_html(tmp_path: Path, capsys):
    out = tmp_path / "spa"
    argv = ["app", "--output", str(out), "--json"]
    if SLA_WORK.is_dir():
        argv.extend(["--work-dir", str(SLA_WORK)])
    elif DEMO_FRONTS.is_file():
        argv.extend(["--geojson", str(DEMO_FRONTS)])
    if FIXTURE_CSV.is_file():
        argv.extend(["--fixture-csv", str(FIXTURE_CSV)])
    # force offline
    argv.append("--no-live")

    code, stdout, err = _run_main(argv, capsys)
    assert code == 0, err
    data = json.loads(stdout)
    assert data["schema"] == SCHEMA
    assert data["rails"]["field_ops_ml_live_fusion"] == _expected_fusion()
    assert data["brief"]["gates"].get("GO_Q") is not True
    assert (out / "index.html").is_file()
    assert (out / "app_payload.json").is_file()
    html = (out / "index.html").read_text(encoding="utf-8")
    assert "L.map" in html or "leaflet" in html.lower()
    assert f'"field_ops_ml_live_fusion": "{_expected_fusion()}"' in html
    reloaded = json.loads((out / "app_payload.json").read_text(encoding="utf-8"))
    assert reloaded["rails"]["field_ops_ml_live_fusion"] == _expected_fusion()
    assert reloaded["rails"]["go_q_invent_forbidden"] is True
    assert "liveUnavailableFallback" in html
    assert 'id="btn-act-status"' in html and 'id="btn-act-decide"' in html
    assert 'id="btn-act-acta"' in html or "btn-act-acta" in html


def test_render_operator_front_markers():
    """Shipped payload→HTML: Live Ops acts + honesty + copy-CLI fallback."""
    payload = build_product_app_payload(live=False, scan=False)
    html = render_product_app_html(payload)
    assert str(payload["rails"]["field_ops_ml_live_fusion"]).upper() == _expected_fusion()
    assert payload["rails"]["go_q_invent_forbidden"] is True
    assert payload["h1_eng_rehearsal"]["go_q_met"] is False
    for marker in (
        "btn-act-status",
        "btn-act-decide",
        "btn-act-acta",
        "liveUnavailableFallback",
        "no es ROS",
        "split-conf",
        "h1-rehearsal",
        "go_q_met",
        "decision-log",
        "vv-scorecard",
        "weakness-board",
    ):
        assert marker in html, f"missing front marker {marker}"


def test_cli_app_human_and_missing_work_dir(tmp_path: Path, capsys):
    out = tmp_path / "spa2"
    code, stdout, err = _run_main(
        ["app", "--output", str(out), "--no-live"],
        capsys,
    )
    assert code == 0, err
    assert "PRODUCT SPA" in stdout or "SPA" in stdout
    assert "index.html" in stdout or str(out) in stdout
    assert "despacho" in stdout.lower() or "táctico" in stdout.lower() or "tactical" in stdout.lower()
    assert f"fusion {_expected_fusion()}" in stdout or "no-serve" in stdout
    assert "copy-CLI" in stdout or "GO_Q" in stdout

    missing = tmp_path / "no_such_incident"
    code2, _out2, err2 = _run_main(
        ["app", "--work-dir", str(missing), "--output", str(tmp_path / "x")],
        capsys,
    )
    assert code2 == 2
    assert "work-dir" in (err2 + _out2).lower() or "not found" in (err2 + _out2).lower()


def test_cli_app_alias_spa(tmp_path: Path, capsys):
    out = tmp_path / "spa_alias"
    code, stdout, _err = _run_main(
        ["spa", "--output", str(out), "--no-live", "--json"],
        capsys,
    )
    assert code == 0
    data = json.loads(stdout)
    assert data["schema"] == SCHEMA


def test_cli_app_alias_console(tmp_path: Path, capsys):
    out = tmp_path / "console_alias"
    code, stdout, _err = _run_main(
        ["console", "--output", str(out), "--no-live", "--json"],
        capsys,
    )
    assert code == 0
    data = json.loads(stdout)
    assert data["schema"] == SCHEMA
    assert (out / "index.html").is_file()
    html = (out / "index.html").read_text(encoding="utf-8")
    assert "#0B1220" in html
    assert "primary-acts" in html
    assert "btn-act-acta" in html


def test_serve_static_spa_http_smoke(tmp_path: Path):
    """Happy-path smoke: loopback serve returns industrial shell (security edges in test_app_spa_security)."""
    import socketserver
    import threading
    import urllib.request

    from wildfire_front.cli_app import _SafeSPARequestHandler

    payload = build_product_app_payload(work_dir=None, live=False, scan=False)
    paths = write_product_app(payload, tmp_path / "served")
    root = paths["html"].resolve().parent
    result: dict[str, object] = {}

    handler = _SafeSPARequestHandler.make(root)

    class _Srv(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

    with _Srv(("127.0.0.1", 0), handler) as httpd:
        port = int(httpd.server_address[1])
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=3) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                result["status"] = resp.status
                result["shell"] = "#0B1220" in body and "primary-acts" in body
                result["fusion_off"] = (
                    f'"field_ops_ml_live_fusion": "{_expected_fusion()}"' in body
                )
        finally:
            httpd.shutdown()

    assert result.get("status") == 200
    assert result.get("shell") is True
    assert result.get("fusion_off") is True


def test_role_switcher_and_bridge_payload(tmp_path: Path):
    from wildfire_front.product.app_spa import is_loopback_http_url

    # Static shell always has all four role buttons
    shell_probe = render_product_app_html(
        build_product_app_payload(live=False, scan=False, role="operator")
    )
    for r in ("operator", "field", "lab", "decision"):
        assert f'data-role="{r}"' in shell_probe
    assert "currentRole = P.role" in shell_probe

    for role in ("operator", "field", "lab", "decision"):
        p = build_product_app_payload(work_dir=None, live=False, scan=False, role=role)
        assert p["role"] == role
        h = p["role_hints"][role]
        assert h.get("id") == role
        assert str(h.get("title") or "").strip()
        assert str(h.get("primary_cmd") or "").strip()
        assert "wildfire_front" in str(h.get("primary_cmd"))
        assert str(h.get("hint") or h.get("audience") or "").strip()
        assert len(h.get("sequence_head") or []) >= 1
        assert p["brief"]["gates"].get("GO_Q") is not True
        html = render_product_app_html(p)
        assert "role-seg" in html
        # Selected role embedded in const P JSON (not vacuous static shell check)
        assert f'"role": "{role}"' in html
        assert "currentRole = P.role" in html
    # bridge only when loopback URL (hostname exact)
    p2 = build_product_app_payload(
        work_dir=None,
        live=False,
        scan=False,
        bridge_decide="http://127.0.0.1:8765",
    )
    assert p2["bridge_decide"]["enabled"] is True
    assert p2["bridge_decide"]["url"] == "http://127.0.0.1:8765"
    assert p2["bridge_decide"]["proxy_path"] == "/bridge/v1/decide"
    assert p2["bridge_decide"]["prefer_proxy"] is True
    p3 = build_product_app_payload(
        work_dir=None,
        live=False,
        scan=False,
        bridge_decide="http://evil.example/v1",
    )
    assert p3["bridge_decide"]["enabled"] is False
    # Prefix / userinfo bypasses must not enable
    for bad in (
        "http://127.0.0.1.evil.example",
        "http://localhost.attacker.tld",
        "http://127.0.0.1@evil.example",
        "http://evil.example/?x=127.0.0.1",
    ):
        assert is_loopback_http_url(bad) is False
        pb = build_product_app_payload(live=False, scan=False, bridge_decide=bad)
        assert pb["bridge_decide"]["enabled"] is False, bad
    html2 = render_product_app_html(p2)
    assert "btn-bridge-refresh" in html2
    assert "Refrescar card" in html2
    assert "bridgeDecideUrl" in html2
    assert "location.origin" in html2
    assert f'"field_ops_ml_live_fusion": "{_expected_fusion()}"' in html2


def test_multi_fire_pack_payload(tmp_path: Path):
    payload = build_product_app_payload(
        work_dir=SLA_WORK if SLA_WORK.is_dir() else None,
        live=False,
        scan=True,
        pack_fires=True,
        pack_cap=8,
    )
    pack = payload.get("pack")
    assert pack is not None
    if payload.get("fire_count", 0) > 0:
        assert pack.get("enabled") is True
        assert pack.get("n", 0) >= 1
        assert pack.get("n", 0) <= 8
        assert isinstance(pack.get("by_id"), dict)
        # soft size cap
        blob = json.dumps(pack, ensure_ascii=False)
        assert len(blob) <= 2_500_000 + 50_000  # allow small overhead vs builder probe
        html = render_product_app_html(payload)
        assert "pack" in html.lower() or "by_id" in html
        assert "primary-acts" in html
        # non-pack select clears stale view (JS markers)
        assert "IF no empaquetado" in html or "no pack" in html
        assert "baselineSnap" in html or "applyFireView" in html
    # pack_cap edge: n=1 with multi catalog — outside pack must not reuse hero
    p1 = build_product_app_payload(live=False, scan=True, pack_fires=True, pack_cap=1)
    if p1.get("fire_count", 0) >= 2 and p1.get("pack"):
        assert p1["pack"]["n"] <= 1
        packed_ids = set(p1["pack"].get("fire_ids") or [])
        catalog_ids = {f.get("id") for f in (p1.get("fires") or [])}
        outside = catalog_ids - packed_ids
        assert outside, "need ≥1 fire outside pack when cap=1 and catalog≥2"
        html1 = render_product_app_html(p1)
        assert "IF no empaquetado" in html1
        assert "REBUILD" in html1 or "rebuild" in html1


def test_pack_first_entry_oversize_skip(monkeypatch):
    """First entry still oversize after ultra-slim → skip (n=0, truncated, skipped_oversize)."""
    import pytest

    import wildfire_front.product.app_spa as spa_mod

    monkeypatch.setattr(spa_mod, "MAX_PACK_JSON_CHARS", 200)

    def _huge_entry(**kwargs):
        return {
            "id": kwargs["fire_row"].get("id"),
            "label": "huge",
            "work_dir_rel": "x",
            "hero": {"decision": "HOLD"},
            # Bulk outside map.geojson so ultra-slim cannot salvage
            "decision_card": {"decision": "HOLD", "blob": "x" * 5000},
            "ops_metrics": {},
            "map": {"layers": [], "center": {"lon": 0, "lat": 0}, "zoom": 7},
            "outbox_last_run": None,
            "cmds": {},
        }

    monkeypatch.setattr(spa_mod, "_build_pack_entry", _huge_entry)
    p = spa_mod.build_product_app_payload(live=False, scan=True, pack_fires=True, pack_cap=2)
    pack = p.get("pack")
    if p.get("fire_count", 0) == 0:
        pytest.skip("no fires in catalog for pack oversize test")
    assert pack is not None
    blob = json.dumps(pack.get("by_id") or {}, ensure_ascii=False)
    assert pack.get("truncated") is True
    assert pack.get("n", 0) == 0
    assert pack.get("enabled") is False
    assert pack.get("skipped_oversize", 0) >= 1
    assert len(blob) <= 200 + 50


def test_pack_first_entry_oversize_slim_accept(monkeypatch):
    """First entry oversize only via map.geojson → ultra-slim accepts under cap."""
    import pytest

    import wildfire_front.product.app_spa as spa_mod

    # Cap large enough for slim entry, small enough that geojson bulk fails probe
    monkeypatch.setattr(spa_mod, "MAX_PACK_JSON_CHARS", 800)

    def _geo_heavy(**kwargs):
        fid = kwargs["fire_row"].get("id")
        return {
            "id": fid,
            "label": "geo-heavy",
            "work_dir_rel": "x",
            "hero": {"decision": "HOLD"},
            "decision_card": {"decision": "HOLD"},
            "ops_metrics": {},
            "map": {
                "layers": [
                    {
                        "id": "L1",
                        "name": "front",
                        "source": "local",
                        "geojson": {
                            "type": "FeatureCollection",
                            "features": [{"type": "Feature", "pad": "y" * 400}] * 8,
                        },
                    }
                ],
                "center": {"lon": 0, "lat": 0},
                "zoom": 7,
            },
            "outbox_last_run": None,
            "cmds": {},
        }

    monkeypatch.setattr(spa_mod, "_build_pack_entry", _geo_heavy)
    p = spa_mod.build_product_app_payload(live=False, scan=True, pack_fires=True, pack_cap=1)
    pack = p.get("pack")
    if p.get("fire_count", 0) == 0:
        pytest.skip("no fires in catalog for pack slim test")
    assert pack is not None
    assert pack.get("truncated") is True
    assert pack.get("enabled") is True
    assert pack.get("n") == 1
    blob = json.dumps(pack.get("by_id") or {}, ensure_ascii=False)
    assert len(blob) <= 800
    # Slimmed: geojson stripped from layers
    entry = next(iter((pack.get("by_id") or {}).values()))
    layers = (entry.get("map") or {}).get("layers") or []
    assert layers
    assert layers[0].get("geojson") is None


def test_pack_mid_entry_truncation_keeps_first(monkeypatch):
    """Second pack entry exceeding cap → keep first, truncated=True, n>=1."""
    import pytest

    import wildfire_front.product.app_spa as spa_mod

    monkeypatch.setattr(spa_mod, "MAX_PACK_JSON_CHARS", 600)
    call_n = {"i": 0}

    def _mixed(**kwargs):
        call_n["i"] += 1
        fid = kwargs["fire_row"].get("id")
        if call_n["i"] == 1:
            return {
                "id": fid,
                "label": "small",
                "work_dir_rel": "x",
                "hero": {"decision": "HOLD"},
                "decision_card": {"decision": "HOLD"},
                "ops_metrics": {},
                "map": {"layers": [], "center": {"lon": 0, "lat": 0}, "zoom": 7},
                "outbox_last_run": None,
                "cmds": {},
            }
        return {
            "id": fid,
            "label": "huge2",
            "work_dir_rel": "x",
            "hero": {"decision": "HOLD"},
            "decision_card": {"decision": "HOLD", "blob": "z" * 4000},
            "ops_metrics": {},
            "map": {"layers": [], "center": {"lon": 0, "lat": 0}, "zoom": 7},
            "outbox_last_run": None,
            "cmds": {},
        }

    monkeypatch.setattr(spa_mod, "_build_pack_entry", _mixed)
    p = spa_mod.build_product_app_payload(live=False, scan=True, pack_fires=True, pack_cap=3)
    if p.get("fire_count", 0) < 2:
        pytest.skip("need ≥2 catalog fires for mid-pack truncation")
    pack = p.get("pack")
    assert pack is not None
    assert pack.get("truncated") is True
    assert pack.get("n", 0) >= 1
    assert pack.get("enabled") is True
    assert len(pack.get("by_id") or {}) == pack["n"]
    blob = json.dumps(pack.get("by_id") or {}, ensure_ascii=False)
    assert len(blob) <= 600 + 20


def test_bridge_decide_mock_http_and_proxy(tmp_path: Path):
    """Real serve-decide shape (top-level card) + SPA same-origin proxy + offline non-fatal."""
    import http.server
    import json as _json
    import socketserver
    import threading
    import urllib.request

    from wildfire_front.cli_app import _SafeSPARequestHandler

    hits: list[str] = []

    class _Upstream(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):  # noqa: ANN002
            return

        def do_GET(self):  # noqa: N802
            hits.append("GET " + self.path)
            body = _json.dumps({"ok": True, "status": "up"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):  # noqa: N802
            hits.append("POST " + self.path)
            n = int(self.headers.get("Content-Length") or 0)
            _ = self.rfile.read(n) if n else b""
            body = _json.dumps(
                {
                    "decision": "HOLD",
                    "confidence_pred": 0.4,
                    "event_id": "MOCK",
                    "system_reliability_pass": False,
                    "sources": [],
                    "reasons": ["mock bridge"],
                    "latency_ms": 1.2,
                }
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    class _Srv(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

    with _Srv(("127.0.0.1", 0), _Upstream) as upstream:
        up_port = int(upstream.server_address[1])
        t = threading.Thread(target=upstream.serve_forever, daemon=True)
        t.start()
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{up_port}/v1/decide",
                data=b'{"policy_id":"field_ops"}',
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            assert data["decision"] == "HOLD"
            assert "latency_ms" in data
            assert any("POST" in h and "/v1/decide" in h for h in hits)

            p = build_product_app_payload(
                live=False,
                scan=False,
                bridge_decide=f"http://127.0.0.1:{up_port}",
            )
            assert p["bridge_decide"]["enabled"] is True
            assert p["bridge_decide"]["proxy_path"] == "/bridge/v1/decide"
            assert p["brief"]["gates"].get("GO_Q") is not True
            assert p["rails"]["field_ops_ml_live_fusion"] == _expected_fusion()

            paths = write_product_app(p, tmp_path / "bridge_spa")
            root = paths["html"].resolve().parent
            handler = _SafeSPARequestHandler.make(
                root, bridge_upstream=f"http://127.0.0.1:{up_port}"
            )
            with _Srv(("127.0.0.1", 0), handler) as spa_httpd:
                spa_port = int(spa_httpd.server_address[1])
                t2 = threading.Thread(target=spa_httpd.serve_forever, daemon=True)
                t2.start()
                try:
                    preq = urllib.request.Request(
                        f"http://127.0.0.1:{spa_port}/bridge/v1/decide",
                        data=b'{"policy_id":"field_ops","event_id":"PROXY"}',
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with urllib.request.urlopen(preq, timeout=3) as resp:
                        proxied = json.loads(resp.read().decode("utf-8"))
                    assert proxied["decision"] == "HOLD"
                    assert sum(1 for h in hits if "POST" in h) >= 2
                    # Health proxy
                    with urllib.request.urlopen(
                        f"http://127.0.0.1:{spa_port}/bridge/health", timeout=3
                    ) as hresp:
                        health = json.loads(hresp.read().decode("utf-8"))
                    assert hresp.status == 200
                    assert health.get("ok") is True
                    assert any("GET" in h and "/health" in h for h in hits)
                finally:
                    spa_httpd.shutdown()

            p_down = build_product_app_payload(
                live=False,
                scan=False,
                bridge_decide="http://127.0.0.1:1",
            )
            assert p_down["bridge_decide"]["enabled"] is True
            assert p_down["bridge_decide"]["url"] == "http://127.0.0.1:1"
            assert p_down["brief"]["gates"].get("GO_Q") is not True
            assert p_down["rails"]["go_q_invent_forbidden"] is True
            assert p_down["rails"]["field_ops_ml_live_fusion"] == _expected_fusion()
            assert p_down["rails"]["not_tactical_dispatch"] is True
        finally:
            upstream.shutdown()


def test_cli_missing_fire_and_pack_flags(tmp_path: Path, capsys):
    code, out, err = _run_main(
        ["app", "--fire", "__no_such_fire_xyz__", "--output", str(tmp_path / "x")],
        capsys,
    )
    assert code == 2
    msg = (err + out).lower()
    assert "not found" in msg
    assert "__no_such_fire_xyz__" in msg or "fire id" in msg

    parser = build_parser()
    args = parser.parse_args(["app", "--all-fires", "--pack-cap", "3", "--bridge-decide", "http://127.0.0.1:8765"])
    assert args.all_fires is True
    assert args.pack_cap == 3
    assert args.bridge_decide == "http://127.0.0.1:8765"


def test_commands_map_mentions_app(capsys):
    code, out, err = _run_main(["commands", "--json"], capsys)
    assert code == 0, err
    data = json.loads(out)
    blob = json.dumps(data)
    assert "app" in blob
    assert "spa" in blob or "console" in blob
    assert "serve" in blob


def test_is_loopback_http_url_matrix():
    """Exact-host loopback only — reject suffix / userinfo / query tricks."""
    from wildfire_front.product.app_spa import is_loopback_http_url

    # Avoid raw IPv6 bracket literals that confuse some parsers
    ipv6_loop = "http://[" + "::1" + "]"
    ipv6_port = "http://[" + "::1" + "]:8765"
    for ok in (
        "http://127.0.0.1",
        "http://127.0.0.1:8765",
        "https://127.0.0.1/v1/decide",
        "http://localhost",
        "http://localhost:9000/path",
        ipv6_loop,
        ipv6_port,
    ):
        assert is_loopback_http_url(ok) is True, ok
    for bad in (
        None,
        "",
        "   ",
        "ftp://127.0.0.1",
        "http://127.0.0.1.evil.example",
        "http://localhost.attacker.tld",
        "http://127.0.0.1@evil.example",
        "http://user:pass@evil.example",
        "http://evil.example/?x=127.0.0.1",
        "http://192.168.1.1",
        "http://10.0.0.1:8080",
        "http://0.0.0.0",
        "not-a-url",
        "http://",
    ):
        assert is_loopback_http_url(bad) is False, bad


def test_invalid_role_falls_back_to_operator():
    p = build_product_app_payload(
        live=False, scan=False, role="not_a_real_role_xyz"
    )
    assert p["role"] == "operator"
    op = p["role_hints"]["operator"]
    assert op.get("id") == "operator"
    assert str(op.get("title") or "").strip()
    assert str(op.get("primary_cmd") or "").strip()
    assert "wildfire_front" in str(op.get("primary_cmd"))
    assert p["rails"]["go_q_invent_forbidden"] is True
    assert p["rails"]["not_tactical_dispatch"] is True
    assert p["rails"]["field_ops_ml_live_fusion"] == _expected_fusion()
    assert p["brief"]["gates"].get("GO_Q") is not True
    html = render_product_app_html(p)
    assert '"role": "operator"' in html


def test_pack_off_by_default_and_cap_clamped():
    p0 = build_product_app_payload(live=False, scan=True, pack_fires=False)
    assert p0.get("pack") is None
    p_cap = build_product_app_payload(
        live=False, scan=True, pack_fires=True, pack_cap=99
    )
    pack = p_cap.get("pack")
    if pack is not None:
        # Builder clamps cap to MAX_PACK_FIRES (8)
        assert pack.get("cap", 0) <= 8
        assert pack.get("n", 0) <= pack.get("cap", 8)
        if pack.get("enabled"):
            assert isinstance(pack.get("by_id"), dict)
            assert pack.get("n") == len(pack.get("by_id") or {})
