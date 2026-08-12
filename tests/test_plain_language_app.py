"""Plain-language SPA: inventory coverage + modo simple for non-tech users."""

from __future__ import annotations

import json
from pathlib import Path

from wildfire_front.cli import build_parser, main
from wildfire_front.product.app_spa import build_product_app_payload, render_product_app_html
from wildfire_front.product.fire_catalog import product_action_catalog
from wildfire_front.product.plain_language import (
    FEATURES,
    GLOSSARY,
    build_plain_language_payload,
    features_missing_from_actions,
)

ROOT = Path(__file__).resolve().parents[1]
SLA = ROOT / "outputs" / "incidents" / "_sla_measure"


def _run_main(argv: list[str], capsys) -> tuple[int, str, str]:
    try:
        main(argv)
        code = 0
    except SystemExit as exc:
        raw = exc.code
        code = 0 if raw in (0, None) else (int(raw) if isinstance(raw, int) else 1)
    cap = capsys.readouterr()
    return code, cap.out, cap.err


def test_plain_language_inventory_covers_cli_and_actions():
    plain = build_plain_language_payload()
    assert plain["schema"] == "wfd_plain_language_v1"
    assert plain["mode_default"] == "simple"
    assert len(plain["glossary"]) >= 12
    assert len(plain["features"]) >= 25
    # every glossary term has plain + for_fire
    for g in GLOSSARY:
        assert g.get("term")
        assert g.get("plain")
        assert g.get("for_fire")
    # every feature has plain explanations
    for f in FEATURES:
        assert f.get("plain")
        assert f.get("for_fire")
        assert f.get("simple_cta")
    actions = product_action_catalog()
    ids = [a["id"] for a in actions]
    assert features_missing_from_actions(ids) == []
    # actions enriched
    for a in actions:
        assert a.get("plain")
        assert a.get("simple_cta")
        assert a.get("for_fire") is not None
    # CLI top-level commands are represented in feature map (by id or cli string)
    parser = build_parser()
    cli_names: set[str] = set()
    for act in parser._subparsers._group_actions:  # type: ignore[attr-defined]
        if getattr(act, "choices", None):
            cli_names.update(act.choices.keys())
    feat_cli_blob = " ".join(str(f.get("cli") or "") + " " + str(f.get("id") or "") for f in FEATURES)
    for name in cli_names:
        token = name.replace("-", "_")
        assert name in feat_cli_blob or token in feat_cli_blob or name.split("-")[0] in feat_cli_blob, (
            f"CLI command {name} missing from plain FEATURES"
        )


def test_payload_simple_mode_and_html(tmp_path: Path):
    wd = SLA if SLA.is_dir() else None
    payload = build_product_app_payload(work_dir=wd, live=False, ui_mode="simple", scan=True)
    assert payload["ui_mode"] == "simple"
    assert payload["rails"]["field_ops_ml_live_fusion"] == "ON"
    assert payload.get("plain_language", {}).get("schema") == "wfd_plain_language_v1"
    assert len(payload.get("glossary") or []) >= 10
    actions = payload.get("product_actions") or []
    assert len(actions) >= 30
    for a in actions:
        assert a.get("plain") or a.get("simple_cta"), a.get("id")
    # hero plain for non-tech
    assert payload["hero"].get("plain")
    assert payload.get("disclaimer_simple")
    html = render_product_app_html(payload)
    # Industrial C2 dual-mode (Fácil | Pro) — never feature-cut
    assert "mode-toggle" in html or "btn-mode-simple" in html
    assert "Fácil" in html and "btn-mode-advanced" in html
    assert "mode-simple" in html
    assert "Términos" in html or "glossary" in html.lower() or "Glosario" in html
    assert "body.mode-simple .adv" in html or "mode-advanced" in html
    assert "primary-acts" in html
    assert "#0B1220" in html
    assert "para el fuego" in html.lower() or "for_fire" in html
    # jargon explained in embedded JSON / hero
    assert "ABSTAIN" in html
    assert "no es un fallo" in html.lower() or "se calla" in html.lower() or "callarse" in html.lower()


def test_cli_app_embeds_plain_language(capsys, tmp_path: Path):
    out = tmp_path / "spa_plain"
    argv = ["app", "--output", str(out), "--json"]
    if SLA.is_dir():
        argv.extend(["--work-dir", str(SLA)])
    code, stdout, err = _run_main(argv, capsys)
    assert code == 0, err
    data = json.loads(stdout)
    assert data["ui_mode"] == "simple"
    assert data["glossary"]
    assert data["product_actions"][0].get("simple_cta")
    html = (out / "index.html").read_text(encoding="utf-8")
    assert "Términos" in html or "glossary" in html.lower() or "Glosario" in html
    assert "mode-toggle" in html or "btn-mode-simple" in html
    assert "primary-acts" in html
    assert "#0B1220" in html
