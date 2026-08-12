"""SPA layout: industrial C2 shell — touch targets, scroll-safe rail, dual-mode."""

from __future__ import annotations

from pathlib import Path

from wildfire_front.product.app_spa import (
    build_product_app_payload,
    render_product_app_html,
    write_product_app,
)

ROOT = Path(__file__).resolve().parents[1]
SLA = ROOT / "outputs" / "incidents" / "_sla_measure"


def test_layout_css_has_touch_targets_and_scroll_safety():
    payload = build_product_app_payload(
        work_dir=SLA if SLA.is_dir() else None,
        live=False,
        ui_mode="simple",
        scan=True,
    )
    html = render_product_app_html(payload)
    # industrial tokens + dual-mode
    assert "#0B1220" in html
    assert "primary-acts" in html
    assert "btn-act-status" in html and "btn-act-decide" in html and "btn-act-acta" in html
    assert "btn-mode-simple" in html and "btn-mode-advanced" in html
    assert "Fácil" in html and "mode-toggle" in html
    # touch targets (≥48px industry stress UX)
    assert "min-height:var(--tap)" in html or "min-height:48px" in html or "--tap" in html
    assert "flex-wrap:wrap" in html
    # scroll side without clipping shell
    assert "overflow-y:auto" in html
    assert "scroll-padding-bottom" in html or "padding-bottom" in html
    # tabs scroll horizontally instead of crushing
    assert "overflow-x:auto" in html
    # toast feedback for copy
    assert 'id="toast"' in html
    assert "function toast" in html or "toast(" in html
    # buttons present
    assert ".btn" in html or ".pact" in html
    # shell grid: top + main, map-first
    assert "100dvh" in html or "100vh" in html
    assert "map-wrap" in html
    assert "minmax(0,1fr)" in html and "grid-template-rows" in html
    # PR04/05: role + last act
    assert "role-seg" in html
    assert "last-act" in html
    assert "Último acto" in html


def test_write_and_reopen_html_intact(tmp_path: Path):
    payload = build_product_app_payload(work_dir=SLA if SLA.is_dir() else None, live=False)
    paths = write_product_app(payload, tmp_path / "ui")
    text = paths["html"].read_text(encoding="utf-8")
    assert text.count("btn") >= 5
    assert "toast" in text
    assert "mode-toggle" in text or "btn-mode-simple" in text
    assert "primary-acts" in text
    assert "#0B1220" in text
    # no truncated style tag
    assert text.count("<style>") == 1
    assert text.count("</style>") == 1
    assert "</html>" in text
    # size band (industrial shell stays substantial but finite)
    assert 15_000 < len(text) < 5_000_000


def test_html_helpers_split_markers():
    """PR03: renderer split into _css/_shell/_js without losing industrial markers."""
    from wildfire_front.product import app_spa_html as mod

    assert callable(mod._css)
    assert callable(mod._shell)
    assert callable(mod._js)
    css = mod._css()
    shell = mod._shell()
    js = mod._js()
    assert "#0B1220" in css
    assert "primary-acts" in shell
    assert "mode-toggle" in shell
    assert "btn-mode-simple" in shell and "btn-mode-advanced" in shell
    assert "Fácil" in shell
    assert "role-seg" in shell
    assert "last-act" in shell
    assert "Último acto" in shell
    assert "function toast" in js or "toast(" in js
    assert "selectFire" in js
    # Bridge same-origin proxy path handling (when --serve + bridge)
    assert "bridgeDecideUrl" in js
    assert "proxy_path" in js
    assert "/bridge/v1/decide" in js
    assert "location.origin" in js


def test_render_product_app_html_dual_mode_and_bridge_markers():
    """Full HTML includes industrial dual-mode shell + bridge proxy wiring."""
    payload = build_product_app_payload(
        work_dir=None,
        live=False,
        scan=False,
        ui_mode="simple",
        bridge_decide="http://127.0.0.1:8765",
    )
    html = render_product_app_html(payload)
    for marker in (
        "#0B1220",
        "primary-acts",
        "btn-act-decide",
        "btn-act-status",
        "btn-act-acta",
        "mode-toggle",
        "btn-mode-simple",
        "btn-mode-advanced",
        "role-seg",
        "last-act",
        "Último acto",
        "bridgeDecideUrl",
        "/bridge/v1/decide",
        "btn-bridge-refresh",
    ):
        assert marker in html, f"missing marker {marker}"
    # Rails honesty embedded in payload JSON (exact OFF — no soft fusion fallback)
    assert '"field_ops_ml_live_fusion": "OFF"' in html
    assert '"go_q_invent_forbidden": true' in html
    assert '"not_tactical_dispatch": true' in html


def test_js_live_unavailable_surfaces_cli_fallback():
    """Offline/501 Live Ops path must show serve hint + CLI copy (not bare HTTP 501)."""
    from wildfire_front.product import app_spa_html as mod

    js = mod._js()
    assert "liveUnavailableFallback" in js
    assert "cliCmdFor" in js
    assert "app --serve" in js
    assert "CLI copiado" in js
    assert "Sin Live Ops (HTTP" in js
    # still no fusion ON control / shell injection helpers
    assert "fusion ON" not in js.lower() or "fusion off" in js.lower()

