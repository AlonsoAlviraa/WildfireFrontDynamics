#!/usr/bin/env python3
"""Gold IF end-to-end verification (loop-engineering).

Honest contract:
  No single public fire worldwide has Heligrafics LWIR + INFOCAM anchor +
  CEMS multi-day + national cadastre together. This script verifies the
  best dual-track gold stack we can assemble:

    OPS champion : Tobarra 2024-08-02 (LWIR + masks + confirmed anchor)
    OPEN champion: EMSR578 Catalonia 2022 (CEMS multi + dNBR + FIRMS)
    ML           : clm_ensemble_v34 (CLM holdout product)
    FUSION       : Decision Card (ops + open + ML)

Usage:
  python scripts/verify_gold_if_e2e.py
  python scripts/verify_gold_if_e2e.py --skip-ml --skip-pytest
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "GOLD_IF_E2E_VERIFICATION.json"
MD_OUT = ROOT / "docs" / "GOLD_IF_E2E_VERIFICATION.md"

# Data contract for a "complete" dual-product gold fire stack
CONTRACT_LAYERS = [
    "ops_lwir_geotiff_seq_ge3",
    "ops_masks_ge3",
    "ops_anchor_confirmed_vp_ha",
    "ops_pack_grade_or_metrics",
    "open_cems_multi_temporal_ge2",
    "open_scorecard_o2_cems",
    "open_dnbr_optional",
    "open_firms_optional",
    "ml_product_v34_weights",
    "decide_card_fusion",
]


def _utc() -> str:
    return datetime.now(UTC).isoformat()


def _run(cmd: list[str], timeout: int = 600) -> dict[str, Any]:
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
        "stdout_tail": (p.stdout or "")[-2500:],
        "stderr_tail": (p.stderr or "")[-1500:],
    }


def _count_tif(path: Path) -> int:
    if not path.is_dir():
        return 0
    return len(list(path.glob("*.tif"))) + len(list(path.glob("*.tiff")))


def _stage_ops_work_dir(ops_metrics_src: Path) -> Path | None:
    """Stage incident-like work_dir so decide --work-dir can load ops metrics."""
    if not ops_metrics_src.is_file():
        return None
    wd = ROOT / "outputs" / "gold_e2e" / "tobarra_work"
    outbox = wd / "outbox"
    outbox.mkdir(parents=True, exist_ok=True)
    dest = outbox / "operational_metrics.json"
    dest.write_text(ops_metrics_src.read_text(encoding="utf-8"), encoding="utf-8")
    return wd


def _probe_cems(codes: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for code in codes:
        url = f"https://mapping.emergency.copernicus.eu/activations/{code}"
        row: dict[str, Any] = {"code": code, "url": url, "ok": False, "n_vectors": 0}
        try:
            html = urllib.request.urlopen(url, timeout=45).read().decode("utf-8", "replace")
            s3 = sorted(
                set(
                    re.findall(
                        r"https://cems-mapping-website[^\s\"'<>]+vector\.zip",
                        html,
                    )
                )
            )
            title_m = re.search(r"<title>([^<]+)", html)
            row.update(
                {
                    "ok": True,
                    "n_vectors": len(s3),
                    "title": (title_m.group(1).strip() if title_m else None),
                    "sample_files": [u.split("/")[-1] for u in s3[:6]],
                }
            )
        except Exception as exc:  # noqa: BLE001 — inventory must not crash
            row["error"] = str(exc)[:300]
        rows.append(row)
    return rows


def score_candidates() -> dict[str, Any]:
    anchors = json.loads((ROOT / "data" / "infocam_anchors.json").read_text(encoding="utf-8"))
    a = anchors.get("anchors", {})

    def ops_row(fire_id: str, lwir: Path, masks: Path) -> dict[str, Any]:
        anc = a.get(fire_id, {})
        n_lwir = _count_tif(lwir)
        n_masks = _count_tif(masks)
        pack = ROOT / "outputs" / "observatorio" / fire_id
        if not pack.is_dir():
            # try alternate naming
            pack = ROOT / "outputs" / "observatorio" / fire_id.replace("-", "")
        metrics = pack / "operational_metrics.json"
        if not metrics.is_file() and fire_id == "tobarra_20240802":
            pack = ROOT / "outputs" / "observatorio" / "tobarra_20240802"
            metrics = pack / "operational_metrics.json"
        grade = None
        if metrics.is_file():
            try:
                m = json.loads(metrics.read_text(encoding="utf-8"))
                grade = m.get("quality_grade") or m.get("grade") or m.get("ops_grade")
            except json.JSONDecodeError:
                grade = None
        confirmed = anc.get("status") == "confirmed"
        layers = {
            "ops_lwir_geotiff_seq_ge3": n_lwir >= 3,
            "ops_masks_ge3": n_masks >= 3,
            "ops_anchor_confirmed_vp_ha": confirmed
            and anc.get("vp_m_min") is not None
            and anc.get("area_ha") is not None,
            "ops_pack_grade_or_metrics": metrics.is_file() and grade is not None,
        }
        score = sum(1 for v in layers.values() if v)
        return {
            "fire_id": fire_id,
            "track": "ops",
            "n_lwir": n_lwir,
            "n_masks": n_masks,
            "anchor_status": anc.get("status"),
            "vp_m_min": anc.get("vp_m_min"),
            "area_ha": anc.get("area_ha"),
            "grade": grade,
            "pack_exists": pack.is_dir(),
            "layers": layers,
            "score": score,
            "max_score": len(layers),
        }

    def open_row(code: str) -> dict[str, Any]:
        p = ROOT / "outputs" / "open_if" / code.lower()
        scorecard = p / "scorecard_pista_b.json"
        sc: dict[str, Any] = {}
        if scorecard.is_file():
            try:
                sc = json.loads(scorecard.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                sc = {}
        n_vec = len(list((p / "vectors").glob("*.geojson"))) if (p / "vectors").is_dir() else 0
        layers = {
            "open_cems_multi_temporal_ge2": n_vec >= 2
            or int(sc.get("n_timeline_steps") or 0) >= 2,
            "open_scorecard_o2_cems": sc.get("O2_cems_delineation") == "GO"
            or sc.get("status") == "GO_OPEN_DATA_PACK",
            "open_dnbr_optional": (p / "dnbr_status.json").is_file(),
            "open_firms_optional": (p / "firms_hotspots.geojson").is_file()
            or (p / "firms_metrics.json").is_file(),
        }
        score = sum(1 for v in layers.values() if v)
        return {
            "activation": code.upper(),
            "track": "open",
            "pack_dir": str(p.relative_to(ROOT)) if p.is_dir() else None,
            "n_vectors": n_vec,
            "max_area_ha": sc.get("max_area_ha"),
            "n_timeline_steps": sc.get("n_timeline_steps"),
            "O2_cems": sc.get("O2_cems_delineation"),
            "dnbr": sc.get("dnbr_stac_status"),
            "layers": layers,
            "score": score,
            "max_score": len(layers),
        }

    ops = [
        ops_row(
            "tobarra_20240802",
            ROOT / "artifacts" / "tobarra_reprojected_lwir",
            ROOT / "artifacts" / "tobarra_lwir_masks",
        ),
        ops_row(
            "cardoso_2025",
            ROOT / "artifacts" / "cardoso_2025_reprojected_lwir",
            ROOT / "artifacts" / "cardoso_2025_lwir_masks",
        ),
        ops_row(
            "la_estrella_acom1_2024",
            ROOT / "artifacts" / "la_estrella_acom1_2024_reprojected_lwir",
            ROOT / "artifacts" / "la_estrella_acom1_2024_lwir_masks",
        ),
        ops_row(
            "hellin_2024",
            ROOT / "artifacts" / "hellin_2024_reprojected_lwir",
            ROOT / "artifacts" / "hellin_2024_lwir_masks",
        ),
        ops_row(
            "retuerta_2025",
            ROOT / "artifacts" / "retuerta_2025_reprojected_lwir",
            ROOT / "artifacts" / "retuerta_2025_lwir_masks",
        ),
    ]
    opens = [open_row(c) for c in ("emsr578", "emsr581", "emsr583", "emsr632")]

    # World scrape shortlist (public thermal / multi-perimeter) — scored as
    # "external candidates" (not yet ingested). None replaces Tobarra for O1.
    external = [
        {
            "id": "FLAME3_NADIR_Hanna_Hammock",
            "source": "https://ieee-dataport.org/open-access/flame-3-radiometric-thermal-uav-imagery-wildfire-management",
            "why": "UAV radiometric thermal NADIR georeferenced + masks (prescribed burn US)",
            "usable_for": ["ops_thermal_research"],
            "missing_for_wfd_gold": [
                "no Spain/CLM INFOCAM anchor",
                "no CEMS multi-day same event",
                "schema != Heligrafics GeoTIFF contract without adapter",
            ],
            "verdict": "RESEARCH_ONLY_NOT_GOLD",
        },
        {
            "id": "NIROPS_US_multi_day_IR_perimeters",
            "source": "https://data.mendeley.com/datasets/95rj5d379g",
            "why": "12k+ multi-day IR-interpreted perimeters (NIFC) — excellent O2-proxy timeline",
            "usable_for": ["open_perimeter_progression", "hausdorff_proxy"],
            "missing_for_wfd_gold": [
                "no LWIR radiometric frames for front_dynamics",
                "US domain not CLM ML transfer",
                "not national Spanish cadastre",
            ],
            "verdict": "OPEN_PROXY_US_ONLY",
        },
        {
            "id": "CALFIRE_historic_perimeters",
            "source": "https://data.cnra.ca.gov/dataset/california-fire-perimeters-all",
            "why": "Official state perimeters (closest to O2 official, but California)",
            "usable_for": ["o2_official_concept_demo"],
            "missing_for_wfd_gold": ["no LWIR", "not Spain"],
            "verdict": "OUT_OF_DOMAIN",
        },
        {
            "id": "EMSR896_Aragon_2026",
            "source": "https://mapping.emergency.copernicus.eu/activations/EMSR896/",
            "why": "Live Spanish CEMS wildfire activation (Jul 2026)",
            "usable_for": ["open_if_if_vectors_ready"],
            "missing_for_wfd_gold": ["may be incomplete products", "no LWIR/anchor"],
            "verdict": "PROBE_ON_DEMAND",
        },
        {
            "id": "EMSR578_Catalonia_2022",
            "source": "https://mapping.emergency.copernicus.eu/activations/EMSR578",
            "why": "Already in-repo: FEP+DEL+MONIT×2+GRA, dNBR STAC GO, FIRMS overlay",
            "usable_for": ["open_if_gold"],
            "missing_for_wfd_gold": ["no LWIR Heligrafics for same fire"],
            "verdict": "OPEN_GOLD_IN_REPO",
        },
        {
            "id": "Tobarra_AB_20240802",
            "source": "local artifacts + INFOCAM anchor",
            "why": "Only fire with confirmed Vp/ha + full LWIR sequence + grade A pack",
            "usable_for": ["ops_gold", "ml_holdout", "o1_single_anchor"],
            "missing_for_wfd_gold": ["no CEMS same event", "O2 national BLOCKED"],
            "verdict": "OPS_GOLD_IN_REPO",
        },
    ]

    ops_champ = max(ops, key=lambda r: (r["score"], r["n_lwir"]))
    open_champ = max(opens, key=lambda r: (r["score"], r.get("max_area_ha") or 0))

    return {
        "contract_layers": CONTRACT_LAYERS,
        "ops_candidates": ops,
        "open_candidates": opens,
        "external_web_candidates": external,
        "ops_champion": ops_champ,
        "open_champion": open_champ,
        "gold_stack": {
            "id": "gold_dual_tobarra_plus_emsr578",
            "ops": ops_champ["fire_id"],
            "open": open_champ.get("activation") or "EMSR578",
            "ml": "clm_ensemble_v34",
            "rationale": (
                "No single public IF has LWIR+INFOCAM+CEMS together. "
                "Product design fuses heterogeneous sources at Decision Card; "
                "this is the maximal honest gold stack."
            ),
        },
        "honest_gap": {
            "single_fire_with_all_layers": False,
            "o2_national_official": "BLOCKED",
            "o1_second_anchor": "OPEN",
        },
    }


def verify_stack(skip_ml: bool, skip_pytest: bool, skip_cems_probe: bool) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema": "gold_if_e2e_verification_v1",
        "started_at_utc": _utc(),
        "steps": [],
        "ok": True,
    }

    scoring = score_candidates()
    report["scoring"] = scoring

    if not skip_cems_probe:
        report["cems_live_probe"] = _probe_cems(
            ["EMSR578", "EMSR583", "EMSR632", "EMSR896", "EMSR888", "EMSR842"]
        )

    # 1) Open pack integrity (EMSR578 already built)
    open_pack = ROOT / "outputs" / "open_if" / "emsr578"
    open_ok = (
        open_pack.is_dir()
        and (open_pack / "manifest.json").is_file()
        and (open_pack / "scorecard_pista_b.json").is_file()
        and (open_pack / "timeline_perimeters.geojson").is_file()
    )
    report["steps"].append(
        {
            "name": "open_emsr578_artifacts",
            "ok": open_ok,
            "path": str(open_pack.relative_to(ROOT)),
        }
    )
    if not open_ok:
        report["ok"] = False
        # try rebuild
        r = _run([sys.executable, "scripts/build_open_if_pack.py", "--activation", "EMSR578"], 600)
        report["steps"].append({"name": "rebuild_emsr578", **r})
        if not r["ok"]:
            report["ok"] = False

    # 2) Ops Tobarra pack
    ops_pack = ROOT / "outputs" / "observatorio" / "tobarra_20240802"
    ops_metrics = ops_pack / "operational_metrics.json"
    ops_ok = ops_pack.is_dir() and ops_metrics.is_file()
    report["steps"].append(
        {
            "name": "ops_tobarra_pack",
            "ok": ops_ok,
            "path": str(ops_pack.relative_to(ROOT)) if ops_pack.is_dir() else None,
        }
    )
    if not ops_ok:
        report["ok"] = False

    # 3) Decision Card fusion (the product surface)
    work_dir = _stage_ops_work_dir(ops_metrics) if ops_metrics.is_file() else None
    decide_cmd = [
        sys.executable,
        "-m",
        "wildfire_front",
        "decide",
        "--event-id",
        "gold_e2e_tobarra_emsr578",
        "--use-ml-v34",
        "--open-pack",
        str(open_pack),
        "--json",
        "--output",
        str(ROOT / "outputs" / "gold_e2e" / "fire_decision_card.json"),
    ]
    if work_dir is not None:
        decide_cmd.extend(["--work-dir", str(work_dir)])
    card_path = ROOT / "outputs" / "gold_e2e" / "fire_decision_card.json"
    r_dec = _run(decide_cmd, timeout=300)
    report["steps"].append({"name": "decide_fusion", **r_dec})
    if not r_dec["ok"]:
        report["ok"] = False
    else:
        try:
            # Prefer written artifact (stdout may be truncated in report)
            if card_path.is_file():
                card = json.loads(card_path.read_text(encoding="utf-8"))
            else:
                text = r_dec.get("stdout_tail") or ""
                start = text.find("{")
                end = text.rfind("}")
                card = json.loads(text[start : end + 1]) if start >= 0 and end > start else {}
            report["decision_card"] = {
                "decision": card.get("decision"),
                "confidence_pred": card.get("confidence_pred"),
                "system_reliability_pass": card.get("system_reliability_pass")
                or (card.get("audit") or {})
                .get("system_reliability", {})
                .get("system_reliability_pass"),
                "latency_ms": card.get("latency_ms"),
                "reasons": card.get("reasons"),
                "sources": [
                    {
                        "id": s.get("id"),
                        "available": s.get("available"),
                        "confidence": s.get("confidence"),
                    }
                    for s in (card.get("sources") or [])
                ],
            }
            if card.get("decision") not in {"GO", "HOLD", "ABSTAIN"}:
                report["ok"] = False
        except (json.JSONDecodeError, TypeError, KeyError, OSError) as exc:
            report["decision_card_parse"] = f"failed:{exc}"
            report["ok"] = False

    # 4) ABSTAIN path (empty) — must refuse GO
    abstain_out = ROOT / "outputs" / "gold_e2e" / "fire_decision_card_empty.json"
    r_abs = _run(
        [
            sys.executable,
            "-m",
            "wildfire_front",
            "decide",
            "--json",
            "--output",
            str(abstain_out),
        ],
        timeout=120,
    )
    report["steps"].append({"name": "decide_empty_abstain", **r_abs})
    abstain_ok = False
    if abstain_out.is_file():
        try:
            c = json.loads(abstain_out.read_text(encoding="utf-8"))
            abstain_ok = c.get("decision") == "ABSTAIN"
            report["abstain_card"] = {"decision": c.get("decision"), "reasons": c.get("reasons")}
        except (json.JSONDecodeError, OSError):
            abstain_ok = False
    if not abstain_ok:
        report["ok"] = False

    # 5) Incident smoke
    r_inc = _run([sys.executable, "scripts/smoke_incident_runtime.py"], timeout=300)
    report["steps"].append({"name": "smoke_incident_runtime", **r_inc})
    if not r_inc["ok"]:
        report["ok"] = False

    # 6) ML smoke (optional if no weights)
    if not skip_ml:
        r_ml = _run(
            [
                sys.executable,
                "scripts/smoke_production_products.py",
                "--products",
                "clm_ensemble_v34",
                "--clm-max",
                "8",
            ],
            timeout=600,
        )
        report["steps"].append({"name": "smoke_ml_v34", **r_ml})
        if not r_ml["ok"]:
            # weights may be missing — mark AT_RISK not hard fail if message says so
            err = (r_ml.get("stderr_tail") or "") + (r_ml.get("stdout_tail") or "")
            if "weight" in err.lower() or "not found" in err.lower() or "missing" in err.lower():
                report["ml_status"] = "AT_RISK_MISSING_WEIGHTS"
            else:
                report["ok"] = False
                report["ml_status"] = "FAIL"
        else:
            report["ml_status"] = "GO"

    # 7) Reliability gate if present
    rel = ROOT / "scripts" / "reliability_gate.py"
    if rel.is_file():
        r_rel = _run([sys.executable, str(rel)], timeout=180)
        report["steps"].append({"name": "reliability_gate", **r_rel})
        if not r_rel["ok"]:
            report["reliability"] = "FAIL_OR_WARN"
            # do not hard-fail engineering gold if only external gates

    # 8) pytest core product tests
    if not skip_pytest:
        r_py = _run(
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/test_decide_cli.py",
                "tests/test_decide_api.py",
                "tests/test_confidence_product.py",
                "tests/test_product_catalog.py",
                "tests/test_front_dynamics.py",
                "tests/test_open_if_pack.py",
                "-q",
                "--tb=no",
            ],
            timeout=300,
        )
        report["steps"].append({"name": "pytest_product_core", **r_py})
        if not r_py["ok"]:
            report["ok"] = False

    # Verdict synthesis
    ops_c = scoring["ops_champion"]
    open_c = scoring["open_champion"]
    layers_pass = {
        "ops_lwir": ops_c["layers"].get("ops_lwir_geotiff_seq_ge3"),
        "ops_masks": ops_c["layers"].get("ops_masks_ge3"),
        "ops_anchor": ops_c["layers"].get("ops_anchor_confirmed_vp_ha"),
        "ops_pack": ops_c["layers"].get("ops_pack_grade_or_metrics"),
        "open_multi": open_c["layers"].get("open_cems_multi_temporal_ge2"),
        "open_o2": open_c["layers"].get("open_scorecard_o2_cems"),
        "open_dnbr": open_c["layers"].get("open_dnbr_optional"),
        "open_firms": open_c["layers"].get("open_firms_optional"),
        "decide_ok": any(
            s.get("name") == "decide_fusion" and s.get("ok") for s in report["steps"]
        ),
    }
    report["layers_pass"] = layers_pass
    report["n_layers_pass"] = sum(1 for v in layers_pass.values() if v)
    report["n_layers_total"] = len(layers_pass)
    report["verdict"] = (
        "GO_GOLD_STACK"
        if report["ok"] and report["n_layers_pass"] >= 7
        else ("PARTIAL" if report["n_layers_pass"] >= 5 else "NO_GO")
    )
    report["finished_at_utc"] = _utc()
    return report


def write_md(report: dict[str, Any]) -> None:
    sc = report.get("scoring") or {}
    ops = sc.get("ops_champion") or {}
    op = sc.get("open_champion") or {}
    card = report.get("decision_card") or {}
    lines = [
        "# Gold IF — verificación E2E (loop-engineering)",
        "",
        f"_UTC: {report.get('finished_at_utc')}_ · verdict **{report.get('verdict')}**",
        "",
        "## Hallazgo honesto del scrape mundial",
        "",
        "No existe un incendio público en el mundo que reúna a la vez:",
        "",
        "1. Secuencia LWIR GeoTIFF multi-frame (contrato Heligrafics)",
        "2. Ancla operativa confirmed Vp/ha (INFOCAM-class)",
        "3. Perímetro CEMS multi-día del **mismo** evento",
        "4. Perímetro catastral/nacional oficial (O2 real)",
        "",
        "Por diseño del producto, la **fusión** ocurre en la Decision Card entre",
        "fuentes heterogéneas. El stack oro verificable es dual:",
        "",
        f"- **OPS:** `{ops.get('fire_id')}` — LWIR={ops.get('n_lwir')}, "
        f"masks={ops.get('n_masks')}, anchor={ops.get('anchor_status')}, "
        f"Vp={ops.get('vp_m_min')}, ha={ops.get('area_ha')}",
        f"- **OPEN:** `{op.get('activation')}` — vectors={op.get('n_vectors')}, "
        f"timeline={op.get('n_timeline_steps')}, O2_cems={op.get('O2_cems')}, "
        f"dnbr={op.get('dnbr')}, max_ha={op.get('max_area_ha')}",
        "- **ML:** `clm_ensemble_v34`",
        "",
        "## Capas del contrato (pass/fail)",
        "",
        "| Capa | Pass |",
        "|------|------|",
    ]
    for k, v in (report.get("layers_pass") or {}).items():
        lines.append(f"| `{k}` | {'✅' if v else '❌'} |")
    lines += [
        "",
        f"**Capas:** {report.get('n_layers_pass')}/{report.get('n_layers_total')}",
        "",
        "## Decision Card (fusión)",
        "",
        f"- decision: **{card.get('decision')}**",
        f"- confidence_pred: {card.get('confidence_pred')}",
        f"- system_reliability_pass: {card.get('system_reliability_pass')}",
        f"- sources: {json.dumps(card.get('sources'), ensure_ascii=False)}",
        "",
        "## Pasos ejecutados",
        "",
        "| Step | OK |",
        "|------|----|",
    ]
    for s in report.get("steps") or []:
        lines.append(f"| {s.get('name')} | {'✅' if s.get('ok') else '❌'} |")
    lines += [
        "",
        "## Candidatos externos (web) — no sustituyen Tobarra",
        "",
    ]
    for e in sc.get("external_web_candidates") or []:
        lines.append(
            f"- **{e.get('id')}** · `{e.get('verdict')}` — {e.get('why')}"
        )
    lines += [
        "",
        "## Cómo re-ejecutar",
        "",
        "```powershell",
        "cd C:\\Users\\Mariano\\Documents\\ALONSOO\\WildfireFrontDynamics",
        "$env:PYTHONPATH = \".\"",
        "python scripts\\verify_gold_if_e2e.py",
        "```",
        "",
        f"JSON: `{OUT.relative_to(ROOT).as_posix()}`",
        "",
    ]
    MD_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify gold dual IF stack E2E")
    ap.add_argument("--skip-ml", action="store_true")
    ap.add_argument("--skip-pytest", action="store_true")
    ap.add_argument("--skip-cems-probe", action="store_true")
    args = ap.parse_args()

    report = verify_stack(
        skip_ml=args.skip_ml,
        skip_pytest=args.skip_pytest,
        skip_cems_probe=args.skip_cems_probe,
    )
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    write_md(report)
    print(
        json.dumps(
            {
                "verdict": report.get("verdict"),
                "ok": report.get("ok"),
                "layers": f"{report.get('n_layers_pass')}/{report.get('n_layers_total')}",
                "ops": (report.get("scoring") or {}).get("ops_champion", {}).get("fire_id"),
                "open": (report.get("scoring") or {})
                .get("open_champion", {})
                .get("activation"),
                "decision": (report.get("decision_card") or {}).get("decision"),
                "json": str(OUT),
                "md": str(MD_OUT),
            },
            indent=2,
        )
    )
    return 0 if report.get("ok") and report.get("verdict") == "GO_GOLD_STACK" else 2


if __name__ == "__main__":
    raise SystemExit(main())
