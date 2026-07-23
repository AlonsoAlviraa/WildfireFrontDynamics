#!/usr/bin/env python3
"""Verify Andalucía REDIAM industrial open E2E stack.

Writes:
  docs/AND_INDUSTRIAL_E2E_VERIFICATION.json
  docs/AND_INDUSTRIAL_E2E_VERIFICATION.md

Usage:
  python scripts/verify_and_industrial_e2e.py
  python scripts/verify_and_industrial_e2e.py --live-wfs
  python scripts/verify_and_industrial_e2e.py --skip-pytest
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "docs" / "AND_INDUSTRIAL_E2E_VERIFICATION.json"
OUT_MD = ROOT / "docs" / "AND_INDUSTRIAL_E2E_VERIFICATION.md"
CACHE = ROOT / "data" / "open_if" / "rediam_andalucia" / "wfs_cache"
INV = ROOT / "data" / "open_if" / "rediam_andalucia" / "inventory"
OPEN_IF = ROOT / "outputs" / "open_if"

LAYERS = [
    "rediam_perimeter_present",
    "inventory_catalog",
    "gold_selection",
    "pack_manifest",
    "metrics_o2",
    "scorecard_go_or_partial",
    "map_html",
    "provenance_attribution",
    "pytest_and_smoke",
    "honest_gates",
]


def _utc() -> str:
    return datetime.now(UTC).isoformat()


def _run(cmd: list[str], timeout: int = 300) -> dict[str, Any]:
    env = {**dict(__import__("os").environ.items()), "PYTHONPATH": str(ROOT)}
    p = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    return {
        "cmd": cmd,
        "returncode": p.returncode,
        "ok": p.returncode == 0,
        "stdout_tail": (p.stdout or "")[-2000:],
        "stderr_tail": (p.stderr or "")[-1500:],
    }


def _find_and_packs() -> list[Path]:
    if not OPEN_IF.is_dir():
        return []
    return sorted(
        d
        for d in OPEN_IF.iterdir()
        if d.is_dir()
        and d.name.startswith("and_")
        and (d / "manifest.json").is_file()
    )


def _check_pack(pack: Path) -> dict[str, Any]:
    """Validate pack artifacts and fail-closed honesty gates."""

    def exists(rel: str) -> bool:
        return (pack / rel).is_file()

    manifest: dict[str, Any] = {}
    scorecard: dict[str, Any] = {}
    metrics: dict[str, Any] = {}
    provenance: dict[str, Any] = {}
    if exists("manifest.json"):
        manifest = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))
    if exists("scorecard_and_industrial.json"):
        scorecard = json.loads((pack / "scorecard_and_industrial.json").read_text(encoding="utf-8"))
    if exists("metrics_o2.json"):
        metrics = json.loads((pack / "metrics_o2.json").read_text(encoding="utf-8"))
    if exists("provenance.json"):
        provenance = json.loads((pack / "provenance.json").read_text(encoding="utf-8"))

    layers = {
        "rediam_perimeter_present": exists("vectors/perimeter_rediam.geojson"),
        "pack_manifest": bool(manifest),
        "metrics_o2": bool(metrics) and metrics.get("area_rediam_ha") is not None,
        "scorecard_go_or_partial": scorecard.get("verdict")
        in {"GO_OPEN_AND_O2", "PARTIAL"},
        "map_html": exists("map.html"),
        "provenance_attribution": "REDIAM" in json.dumps(provenance)
        or "REDIAM" in json.dumps(manifest),
        "brief": exists("operator_brief_open_if.md"),
        "dnbr_status": exists("dnbr_status.json"),
    }

    # Fail closed: invented Vp / tactical value is dishonest
    vp_flag = scorecard.get("vp_invented")
    vp_tactical = manifest.get("vp_tactical")
    vp_not_invented_ok = (vp_flag is not True) and (
        vp_tactical is None or vp_tactical == "" or vp_tactical == 0
    )

    # Strict: scorecard must explicitly say hull is NOT official burned area
    hull_flag = scorecard.get("firms_hull_is_official_burned_area")
    firms_hull_not_official = hull_flag is False

    decision = scorecard.get("decision_open")
    decision_not_false_go = decision in {"HOLD", "ABSTAIN", "open_demo"} or (
        decision is None
        and scorecard.get("gates", {}).get("NO_FALSE_DISPATCH") == "PASS"
    )
    # Explicit GO for field dispatch without ASEMA is dishonest
    if decision in {"GO", "DISPATCH", "GO_FIELD_OPS"}:
        decision_not_false_go = False

    honest = {
        "vp_not_invented_ok": vp_not_invented_ok,
        "firms_hull_not_official": firms_hull_not_official,
        "decision_not_false_go": decision_not_false_go,
    }
    return {
        "pack_id": pack.name,
        "path": str(pack.relative_to(ROOT)) if pack.is_relative_to(ROOT) else str(pack),
        "layers": layers,
        "honest": honest,
        "verdict": scorecard.get("verdict"),
        "area_rediam_ha": metrics.get("area_rediam_ha") or manifest.get("area_rediam_ha"),
        "n_firms": metrics.get("n_firms_hotspots"),
        "dnbr_status": metrics.get("dnbr_status"),
        "score": sum(1 for v in layers.values() if v),
        "max_score": len(layers),
        "ok": all(layers.values()) and all(honest.values()),
    }


def verify(
    *,
    skip_pytest: bool,
    skip_live_wfs: bool,
    run_pack_if_missing: bool,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema": "and_industrial_e2e_verification_v1",
        "started_at_utc": _utc(),
        "track": "Pista_B_plus_AND_REDIAM",
        "attribution_required": "Fuente: REDIAM — Junta de Andalucía",
        "layers_contract": LAYERS,
        "steps": [],
        "ok": True,
        "verdict": "NO_GO",
    }

    # Inventory
    catalog = INV / "event_catalog.csv"
    selection = INV / "selection_gold.json"
    inv_ok = catalog.is_file() and selection.is_file()
    report["steps"].append(
        {
            "name": "inventory_catalog",
            "ok": inv_ok,
            "catalog": str(catalog.relative_to(ROOT)) if catalog.is_file() else None,
            "selection": str(selection.relative_to(ROOT)) if selection.is_file() else None,
        }
    )
    gold = []
    if selection.is_file():
        sel = json.loads(selection.read_text(encoding="utf-8"))
        gold = sel.get("gold") or []
        report["selection"] = {
            "n_gold": len(gold),
            "n_silver": len(sel.get("silver") or []),
            "n_catalog": sel.get("n_catalog"),
            "gold_codigos": [g.get("codigo") for g in gold],
        }
        if len(gold) < 1:
            report["ok"] = False
    else:
        report["ok"] = False

    # Cache presence (full years only; ignore _smoke/)
    years_present = []
    if CACHE.is_dir():
        for ydir in sorted(CACHE.iterdir()):
            if not ydir.is_dir() or ydir.name.startswith("_"):
                continue
            if (ydir / f"perim_incendios_{ydir.name}.geojson").is_file():
                years_present.append(ydir.name)
    report["wfs_cache_years"] = years_present
    report["steps"].append(
        {
            "name": "wfs_cache",
            "ok": len(years_present) >= 1 or catalog.is_file(),
            "years": years_present,
        }
    )

    # Live WFS smoke (opt-in via --live-wfs; default skipped)
    # Writes only to wfs_cache/_smoke/ — never overwrites full-year files.
    live: dict[str, Any] = {"attempted": False}
    if not skip_live_wfs:
        live["attempted"] = True
        r = _run(
            [
                sys.executable,
                "scripts/fetch_rediam_perimeters.py",
                "--years",
                "2024",
                "--count",
                "3",
                "--out",
                "data/open_if/rediam_andalucia/wfs_cache",
            ],
            timeout=180,
        )
        live["fetch"] = {
            "ok": r["ok"],
            "returncode": r["returncode"],
            "stdout_tail": r["stdout_tail"][-500:],
            "stderr_tail": r["stderr_tail"][-500:],
            "note": "COUNT smoke writes under wfs_cache/_smoke/ only",
        }
        report["steps"].append({"name": "live_wfs_smoke", "ok": r["ok"]})
        # live fail does not alone fail industrial if fixtures/packs exist
    else:
        report["steps"].append(
            {"name": "live_wfs_smoke", "ok": False, "skipped": True}
        )
    report["live_wfs"] = live

    # Packs
    packs = _find_and_packs()
    if not packs and run_pack_if_missing and selection.is_file():
        r = _run(
            [
                sys.executable,
                "scripts/build_and_if_pack.py",
                "--selection",
                str(selection.relative_to(ROOT)),
                "--tier",
                "gold",
                "--skip-dnbr",
            ],
            timeout=600,
        )
        report["steps"].append({"name": "build_gold_pack_on_demand", **r})
        packs = _find_and_packs()

    pack_reports = [_check_pack(p) for p in packs]
    report["packs"] = pack_reports
    report["n_packs"] = len(pack_reports)
    pack_ok = any(p.get("ok") for p in pack_reports) or (
        any(p.get("verdict") in {"GO_OPEN_AND_O2", "PARTIAL"} for p in pack_reports)
        and any(p.get("layers", {}).get("rediam_perimeter_present") for p in pack_reports)
        and all(all(p.get("honest", {}).values()) for p in pack_reports)
    )
    report["steps"].append(
        {
            "name": "and_packs",
            "ok": pack_ok,
            "n": len(pack_reports),
            "pack_ids": [p["pack_id"] for p in pack_reports],
        }
    )
    if not pack_ok:
        report["ok"] = False

    # Honest gates: fail closed when no packs
    honest_ok = (
        all(all(p.get("honest", {}).values()) for p in pack_reports)
        if pack_reports
        else False
    )
    report["steps"].append({"name": "honest_gates", "ok": honest_ok})
    if not honest_ok:
        report["ok"] = False

    # pytest
    if not skip_pytest:
        r = _run(
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/test_rediam_and_intake.py",
                "tests/test_and_if_pack.py",
                "-q",
                "--tb=line",
            ],
            timeout=180,
        )
        report["steps"].append({"name": "pytest_and_smoke", **r})
        if not r["ok"]:
            report["ok"] = False
    else:
        report["steps"].append(
            {"name": "pytest_and_smoke", "ok": False, "skipped": True}
        )

    # Layer contract rollup — honest_gates is honest_ok only (no pack-existence OR)
    pytest_step = next(
        (s for s in report["steps"] if s.get("name") == "pytest_and_smoke"),
        {},
    )
    pytest_ok = bool(pytest_step.get("ok")) and not pytest_step.get("skipped")
    if pytest_step.get("skipped"):
        # Skipped pytest does not block industrial GO if packs+honesty OK
        pytest_layer = True
    else:
        pytest_layer = pytest_ok

    layer_status = {
        "rediam_perimeter_present": any(
            p.get("layers", {}).get("rediam_perimeter_present") for p in pack_reports
        ),
        "inventory_catalog": inv_ok,
        "gold_selection": bool(gold),
        "pack_manifest": any(p.get("layers", {}).get("pack_manifest") for p in pack_reports),
        "metrics_o2": any(p.get("layers", {}).get("metrics_o2") for p in pack_reports),
        "scorecard_go_or_partial": any(
            p.get("layers", {}).get("scorecard_go_or_partial") for p in pack_reports
        ),
        "map_html": any(p.get("layers", {}).get("map_html") for p in pack_reports),
        "provenance_attribution": any(
            p.get("layers", {}).get("provenance_attribution") for p in pack_reports
        ),
        "pytest_and_smoke": pytest_layer,
        "honest_gates": honest_ok,
    }
    report["layer_status"] = layer_status
    n_pass = sum(1 for v in layer_status.values() if v)
    report["layers_pass"] = n_pass
    report["layers_total"] = len(layer_status)

    if report["ok"] and n_pass >= 8:
        core = [
            "rediam_perimeter_present",
            "inventory_catalog",
            "gold_selection",
            "pack_manifest",
            "metrics_o2",
            "scorecard_go_or_partial",
            "map_html",
            "honest_gates",
        ]
        if all(layer_status.get(k) for k in core):
            report["verdict"] = "GO_AND_INDUSTRIAL_E2E"
        else:
            report["verdict"] = "PARTIAL"
            report["ok"] = False
    elif n_pass >= 5 and pack_ok and honest_ok:
        report["verdict"] = "PARTIAL"
        report["ok"] = True
    else:
        report["verdict"] = "NO_GO"
        report["ok"] = False

    report["finished_at_utc"] = _utc()
    report["gold_pack"] = next(
        (p for p in pack_reports if p.get("verdict") in {"GO_OPEN_AND_O2", "PARTIAL"}),
        pack_reports[0] if pack_reports else None,
    )
    return report


def write_and_index() -> Path | None:
    """Lightweight multi-IF index for AND packs."""
    if not OPEN_IF.is_dir():
        return None
    packs = []
    for d in sorted(OPEN_IF.iterdir()):
        if not d.is_dir() or not d.name.startswith("and_"):
            continue
        man_p = d / "manifest.json"
        if not man_p.is_file():
            continue
        m = json.loads(man_p.read_text(encoding="utf-8"))
        sc_p = d / "scorecard_and_industrial.json"
        s = json.loads(sc_p.read_text(encoding="utf-8")) if sc_p.is_file() else {}
        packs.append(
            {
                "id": d.name,
                "codigo": m.get("codigo"),
                "fecha_inc": m.get("fecha_inc"),
                "municipio": m.get("municipio"),
                "provincia": m.get("provincia"),
                "area_rediam_ha": m.get("area_rediam_ha"),
                "verdict": s.get("verdict") or m.get("scorecard_verdict"),
            }
        )
    rows = []
    for p in packs:
        rows.append(
            "<tr>"
            f'<td><a href="{p["id"]}/map.html">{p["id"]}</a></td>'
            f'<td>{p.get("codigo")}</td><td>{p.get("fecha_inc")}</td>'
            f'<td>{p.get("municipio")}/{p.get("provincia")}</td>'
            f'<td>{p.get("area_rediam_ha")}</td>'
            f'<td><b>{p.get("verdict")}</b></td>'
            "</tr>"
        )
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/><title>AND REDIAM open_if index</title>
<style>
body{{font-family:system-ui,sans-serif;margin:24px;background:#0f1115;color:#e8e8e8}}
a{{color:#6cb6ff}} table{{border-collapse:collapse;width:100%;max-width:1100px}}
th,td{{border:1px solid #333;padding:8px 10px;text-align:left}} th{{background:#1c2333}}
.banner{{background:#1a1a1a;padding:12px 16px;margin-bottom:16px;border-left:4px solid #f5a623}}
</style></head><body>
<div class="banner">
  <b>Andalucía REDIAM — open industrial packs</b><br/>
  Fuente: REDIAM — Junta de Andalucía · FIRMS hull ≠ ha oficiales · no Vp táctico sin ASEMA<br/>
  Built: {_utc()} · n={len(packs)}
</div>
<table>
<tr><th>Pack</th><th>Código</th><th>Fecha</th><th>Lugar</th><th>ha</th><th>Verdict</th></tr>
{''.join(rows)}
</table>
<p><a href="../../docs/AND_INDUSTRIAL_E2E_VERIFICATION.md">Acta E2E</a></p>
</body></html>
"""
    out = OPEN_IF / "and_index.html"
    out.write_text(html, encoding="utf-8")
    return out


def render_md(report: dict[str, Any]) -> str:
    lines = [
        "# AND Industrial E2E Verification — REDIAM Andalucía",
        "",
        f"**Verdict:** `{report.get('verdict')}`  ",
        f"**Started:** {report.get('started_at_utc')}  ",
        f"**Finished:** {report.get('finished_at_utc')}  ",
        f"**Attribution:** {report.get('attribution_required')}",
        "",
        "## Layer contract",
        "",
        "| Layer | Pass |",
        "|-------|------|",
    ]
    for k, v in (report.get("layer_status") or {}).items():
        lines.append(f"| `{k}` | {'PASS' if v else 'FAIL'} |")
    lines += [
        "",
        f"Layers pass: **{report.get('layers_pass')}/{report.get('layers_total')}**",
        "",
        "## Selection",
        "",
    ]
    sel = report.get("selection") or {}
    lines.append(f"- Catalog n: {sel.get('n_catalog')}")
    lines.append(f"- Gold: {sel.get('gold_codigos')}")
    lines.append(f"- Silver n: {sel.get('n_silver')}")
    lines += ["", "## Packs", ""]
    for p in report.get("packs") or []:
        lines.append(
            f"- `{p.get('pack_id')}` · verdict={p.get('verdict')} · "
            f"ha={p.get('area_rediam_ha')} · firms={p.get('n_firms')} · "
            f"dnbr={p.get('dnbr_status')} · score={p.get('score')}/{p.get('max_score')}"
        )
    if not report.get("packs"):
        lines.append("- _(none)_")
    lines += [
        "",
        "## WFS cache years",
        f"- {report.get('wfs_cache_years')}",
        "",
        "## Live WFS",
        f"- attempted: {(report.get('live_wfs') or {}).get('attempted')}",
        f"- ok: {((report.get('live_wfs') or {}).get('fetch') or {}).get('ok')}",
        "",
        "## Steps",
        "",
    ]
    for s in report.get("steps") or []:
        name = s.get("name")
        if s.get("skipped"):
            flag = "SKIP"
        elif s.get("ok"):
            flag = "PASS"
        else:
            flag = "FAIL"
        lines.append(f"- **{name}**: {flag}")
    lines += [
        "",
        "## Honest constraints",
        "",
        "- No invented Vp / tactical ROS",
        "- FIRMS hull ≠ official burned area",
        "- REDIAM / Junta de Andalucía attributed",
        "- Field decision HOLD without ASEMA anchor",
        "",
        "## Relation to gold dual stack",
        "",
        "| Track | Champion |",
        "|-------|----------|",
        "| OPS | Tobarra 2024-08-02 (LWIR + Vp) |",
        "| OPEN CEMS | EMSR578 |",
        "| OPEN O2 CCAA | AND REDIAM gold (this acta) |",
        "",
        f"_Schema: `{report.get('schema')}`_",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-pytest", action="store_true")
    ap.add_argument(
        "--live-wfs",
        action="store_true",
        help="Opt-in live WFS COUNT smoke (writes under wfs_cache/_smoke/ only)",
    )
    ap.add_argument(
        "--skip-live-wfs",
        action="store_true",
        help="Deprecated alias: live WFS is skipped by default",
    )
    ap.add_argument("--no-build", action="store_true", help="Do not build pack if missing")
    args = ap.parse_args()

    # Default: skip live WFS. Only run when --live-wfs is set.
    skip_live = not args.live_wfs

    report = verify(
        skip_pytest=args.skip_pytest,
        skip_live_wfs=skip_live,
        run_pack_if_missing=not args.no_build,
    )
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    OUT_MD.write_text(render_md(report), encoding="utf-8")
    idx = write_and_index()
    print(json.dumps({
        "verdict": report.get("verdict"),
        "ok": report.get("ok"),
        "layers_pass": report.get("layers_pass"),
        "n_packs": report.get("n_packs"),
        "json": str(OUT_JSON.relative_to(ROOT)),
        "md": str(OUT_MD.relative_to(ROOT)),
        "and_index": str(idx.relative_to(ROOT)) if idx else None,
    }, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
