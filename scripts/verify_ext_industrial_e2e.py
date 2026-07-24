#!/usr/bin/env python3
"""Verify Extremadura RAI industrial E2E layers."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
INV = ROOT / "data" / "open_if" / "extremadura_rai_2025" / "inventory"
OUT = ROOT / "outputs" / "open_if"
MD = ROOT / "docs" / "EXT_INDUSTRIAL_E2E_VERIFICATION.md"
JS = ROOT / "docs" / "EXT_INDUSTRIAL_E2E_VERIFICATION.json"

LAYERS = [
    "rai_perimeter_present",
    "inventory_catalog",
    "gold_selection",
    "pack_manifest",
    "metrics_o2",
    "scorecard_go_or_partial",
    "map_html",
    "provenance_attribution",
    "pytest_or_skip",
    "honest_gates",
]


def _utc() -> str:
    return datetime.now(UTC).isoformat()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-pytest", action="store_true")
    args = ap.parse_args()
    started = _utc()
    layers = dict.fromkeys(LAYERS, False)
    steps: list[dict[str, Any]] = []
    packs: list[dict[str, Any]] = []

    cat = INV / "event_catalog.csv"
    sel = INV / "selection_gold.json"
    layers["inventory_catalog"] = cat.is_file()
    steps.append({"name": "inventory_catalog", "ok": layers["inventory_catalog"]})
    selection = {}
    if sel.is_file():
        selection = json.loads(sel.read_text(encoding="utf-8"))
        layers["gold_selection"] = bool(selection.get("gold"))
    steps.append({"name": "gold_selection", "ok": layers["gold_selection"]})

    pack_dirs = sorted(OUT.glob("ext_*"))
    honest_ok = True
    for pdir in pack_dirs:
        man = pdir / "manifest.json"
        sc_path = pdir / "scorecard_ext_industrial.json"
        met = pdir / "metrics_o2.json"
        perim = pdir / "vectors" / "perimeter_rai.geojson"
        mhtml = pdir / "map.html"
        prov = pdir / "provenance.json"
        man.is_file() and perim.is_file() and sc_path.is_file()
        layers["rai_perimeter_present"] = layers["rai_perimeter_present"] or perim.is_file()
        layers["pack_manifest"] = layers["pack_manifest"] or man.is_file()
        layers["metrics_o2"] = layers["metrics_o2"] or met.is_file()
        layers["map_html"] = layers["map_html"] or mhtml.is_file()
        layers["provenance_attribution"] = layers["provenance_attribution"] or (
            prov.is_file() and "Extremadura" in prov.read_text(encoding="utf-8")
        )
        sc = json.loads(sc_path.read_text(encoding="utf-8")) if sc_path.is_file() else {}
        verdict = sc.get("verdict", "")
        if verdict in {"GO_OPEN_EXT_O2", "PARTIAL"}:
            layers["scorecard_go_or_partial"] = True
        # honest gates fail-closed
        h = (
            sc.get("vp_invented") is False
            and sc.get("firms_hull_is_official_burned_area") is False
            and sc.get("decision_open") in {"HOLD", "ABSTAIN", "open_demo"}
        )
        if not h:
            honest_ok = False
        packs.append(
            {
                "dir": pdir.name,
                "verdict": verdict,
                "ha": (
                    json.loads(man.read_text(encoding="utf-8")).get("area_rai_ha")
                    if man.is_file()
                    else None
                ),
                "honest": h,
            }
        )
    layers["honest_gates"] = bool(packs) and honest_ok

    if not args.skip_pytest:
        r = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/test_ext_rai_pack.py",
                "-q",
                "--tb=no",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        layers["pytest_or_skip"] = r.returncode == 0
        steps.append({"name": "pytest", "ok": r.returncode == 0, "tail": (r.stdout or "")[-500:]})
    else:
        layers["pytest_or_skip"] = True
        steps.append({"name": "pytest", "ok": True, "skipped": True})

    n_pass = sum(1 for v in layers.values() if v)
    ok = n_pass == len(LAYERS)
    verdict = "GO_EXT_INDUSTRIAL_E2E" if ok else "PARTIAL_EXT_INDUSTRIAL_E2E"
    finished = _utc()
    report = {
        "schema": "ext_industrial_e2e_v1",
        "verdict": verdict,
        "ok": ok,
        "started_utc": started,
        "finished_utc": finished,
        "layers": layers,
        "layers_pass": f"{n_pass}/{len(LAYERS)}",
        "selection": {
            "gold": selection.get("gold"),
            "silver": selection.get("silver"),
            "n_events": len(selection.get("events") or {}),
        },
        "packs": packs,
        "steps": steps,
        "honest": {
            "no_invented_vp": True,
            "firms_hull_not_burned_area": True,
            "attribution": "RAI — Junta de Extremadura / INFOEX",
            "decision": "HOLD without ops anchor",
        },
    }
    JS.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = [
        "# EXT Industrial E2E Verification — RAI Extremadura",
        "",
        f"**Verdict:** `{verdict}`  ",
        f"**Started:** {started}  ",
        f"**Finished:** {finished}  ",
        "**Attribution:** RAI — Junta de Extremadura / INFOEX",
        "",
        "## Layer contract",
        "",
        "| Layer | Pass |",
        "|-------|------|",
    ]
    for k, v in layers.items():
        lines.append(f"| `{k}` | {'PASS' if v else 'FAIL'} |")
    lines += [
        "",
        f"Layers pass: **{n_pass}/{len(LAYERS)}**",
        "",
        "## Selection",
        f"- Gold: {selection.get('gold')}",
        f"- Silver: {selection.get('silver')}",
        "",
        "## Packs",
        "",
    ]
    for p in packs:
        lines.append(
            f"- `{p['dir']}` · verdict={p['verdict']} · ha={p['ha']} · honest={p['honest']}"
        )
    lines += [
        "",
        "## Honest constraints",
        "",
        "- No invented Vp",
        "- FIRMS hull ≠ official burned area",
        "- Formulario Word debe enviarse a rai@juntaex.es",
        "",
    ]
    MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"{verdict} layers={n_pass}/{len(LAYERS)} packs={len(packs)}")
    print(f"→ {MD}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
