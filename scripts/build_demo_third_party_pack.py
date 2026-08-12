#!/usr/bin/env python3
"""E1 — Build demo-with-third-parties evidence pack.

One-command::

    python scripts/build_demo_third_party_pack.py
    # → outputs/demo_third_party/  (+ optional zip under dist/)

Contents
--------
* README.md (ES) — how a third party validates offline
* fire_decision_card.json + .md  (policy **field_ops**)
* replay_sources.json + forensic bundle
* replay_manifest.json (content hashes)
* run_replay.ps1 / run_replay.sh  → E3
* sample_data/ — minimal ops + open metrics + pointers
* RESEARCH_CITATIONS.md (Lampman / Orion / fuel corpus)
* reliability_gate_report.json (this-run, field unlock when PASS)

Rails: field_ops · no ML-live fusion claim · replay path documented.
Does not invent Vp/ha. Uses Tobarra ops numbers already in repo scorecards.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import shutil
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT_DEFAULT = ROOT / "outputs" / "demo_third_party"
DIST_DEFAULT = ROOT / "dist"

# Anchored numbers from GO_MES / Metrics Hub (not invented).
# area_ha_max = observed thermal mask max when available from observatorio pack;
# reference_area_ha = INFOCAM anchor 39 ha (not the same field).
TOBARRA_OPS: dict[str, Any] = {
    "quality_grade": "A",
    "primary_ros_m_min": 5.71,
    "n_frames_staged": 35,
    "n_frames": 35,
    "area_ha_max": 51.88,  # observed thermal mask max (observatorio default)
    "reference_area_ha": 39.0,  # INFOCAM anchor ha — NOT observed max
    "reference_vp_m_min": 7.0,
    "speed_vs_ref_ratio": 0.8157142857142857,
    "engine": "front_dynamics_v1",
    "fire_id": "tobarra_20240802",
    "label": "Tobarra 2024-08-02 thermal ops (grade A structural)",
}

# Illustrative CEMS-scale open metrics for multi-source card fusion demo.
# NOT co-incident with Tobarra geography — monitoring layer only.
OPEN_CEMS: dict[str, Any] = {
    "max_area_ha": 44376.7,
    "n_timeline_steps": 10,
    "activation": "EMSR900",
    "O2_cems_delineation": "GO",
    "note": (
        "illustrative_cems_scale_proxy_not_tobarra_coincident — "
        "open weight demonstrates multi-source fusion; GO driven by ops"
    ),
    "role": "illustrative_open_monitoring_not_same_fire",
}

EVENT_ID = "demo_third_party_tobarra"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _enrich_ops_from_repo() -> dict[str, Any]:
    """Prefer live observatorio/hub numbers when present; else static anchors."""
    ops = dict(TOBARRA_OPS)
    hub = _load_json(ROOT / "docs" / "METRICS_HUB.json")
    if hub:
        sources = hub.get("sources") or hub.get("ops") or {}
        if isinstance(sources, dict):
            ros = sources.get("primary_ros_m_min") or sources.get("ros_m_min")
            grade = sources.get("quality_grade") or sources.get("grade")
            if ros is not None:
                with contextlib.suppress(TypeError, ValueError):
                    ops["primary_ros_m_min"] = float(ros)
            if grade:
                ops["quality_grade"] = str(grade)
    # Tobarra operational_metrics (sector export already present)
    om = _load_json(
        ROOT / "outputs" / "observatorio" / "tobarra_20240802" / "operational_metrics.json"
    )
    if om:
        structural = om.get("structural") if isinstance(om.get("structural"), dict) else {}
        ros = structural.get("primary_ros_m_min") or om.get("speed_median_m_min")
        if ros is not None:
            with contextlib.suppress(TypeError, ValueError):
                ops["primary_ros_m_min"] = float(ros)
        grade = (structural.get("structural_grade") or om.get("quality_grade") or "").strip()
        if grade:
            ops["quality_grade"] = grade
        n = om.get("observation_count") or om.get("num_observations")
        if n:
            ops["n_frames_staged"] = int(n)
            ops["n_frames"] = int(n)
        # Observed thermal mask max (not INFOCAM reference ha)
        if om.get("area_ha_max") is not None:
            with contextlib.suppress(TypeError, ValueError):
                ops["area_ha_max"] = float(om["area_ha_max"])
        if om.get("reference_area_ha") is not None:
            with contextlib.suppress(TypeError, ValueError):
                ops["reference_area_ha"] = float(om["reference_area_ha"])
        if om.get("reference_vp_m_min") is not None:
            with contextlib.suppress(TypeError, ValueError):
                ops["reference_vp_m_min"] = float(om["reference_vp_m_min"])
        if om.get("speed_vs_ref_ratio") is not None:
            with contextlib.suppress(TypeError, ValueError):
                ops["speed_vs_ref_ratio"] = float(om["speed_vs_ref_ratio"])
        sector = om.get("sector_ros")
        if isinstance(sector, dict):
            ops["sector_ros"] = sector
    return ops


def _write_readme(out: Path, *, decision: str, conf: Any, replay_ok: bool) -> None:
    conf_s = f"{float(conf):.3f}" if isinstance(conf, (int, float)) else "—"
    text = f"""# Pack demo terceros — WildfireFrontDynamics

**Qué es:** paquete **offline** para que un tercero valide el Decision Card
y el replay forense sin red. No es orden táctica ni acta firmada de demo.

**Evento demo:** `{EVENT_ID}` · política **`field_ops`**
**Decisión empaquetada:** **{decision}** · conf={conf_s}
**Self-replay en build:** `replay_ok={replay_ok}`
**Fecha pack:** {datetime.now(UTC).strftime("%Y-%m-%d")} UTC

## Cómo validar (5 minutos)

### 1. Requisitos

- Python 3.11+ y el repo WFD (o este pack dentro del árbol del repo).
- En la raíz del repo:

```powershell
$env:PYTHONPATH = "."
```

### 2. Replay forense (E3) — obligatorio

Desde la **raíz del repositorio**:

```powershell
python scripts/run_third_party_replay.py --bundle outputs/demo_third_party
# debe imprimir: replay_ok: True  (exit 0)
```

O dentro de este pack (si el repo está en el PATH de trabajo):

```powershell
.\\run_replay.ps1
# o: bash run_replay.sh
```

Si alguien altera `fire_decision_card.json` o `replay_sources.json` sin
regenerar hashes, el replay debe fallar (`replay_ok: False`, exit 2).

**Límites de E3 (honestidad):** `exit 0` = **consistencia forense interna**
(decision + output_hash reconstruibles desde el snapshot `replay_sources`).
**No** es autenticación criptográfica ni anti-forgery de un pack controlado:
un atacante con el bundle offline puede reescribir métricas + `expected_*` +
gate embebido a la vez. HTTP / live `publish_decision_card` sigue generando
gate this-run y **no** acepta gates inline no confiables.

### 3. Reconstruir Decision Card (opcional)

```powershell
python -m wildfire_front decide --policy field_ops --json
# vacío → ABSTAIN (sin fuentes)
# Con métricas del pack, el builder usa publish_decision_card + this-run gate.
```

### 4. Reliability gate + Metrics Hub

```powershell
python scripts/reliability_gate.py
python scripts/build_metrics_hub.py
```

Informe legible para terceros: `docs/RELIABILITY_GATE_REPORT_THIRD_PARTY.md`.

## Qué contiene

| Archivo | Rol |
|---------|-----|
| `fire_decision_card.json` / `.md` | Decision Card política **field_ops** |
| `replay_sources.json` | Snapshot forense para re-ejecutar |
| `replay_manifest.json` | Hashes del pack |
| `reliability_gate_report.json` | Gate this-run (no es suite sample de docs/) |
| `run_replay.ps1` / `.sh` | Wrapper E3 |
| `sample_data/` | Métricas ops/open usadas + punteros a datos locales |
| `RESEARCH_CITATIONS.md` | Lampman · Orion UQ · fuel Med |

## Rails (no se violan)

- `field_ops.allow_ml_live_in_fusion` = **false**
- `ml_product_go` = **false**
- Catalog holdout IoU es **proveniencia**, no certeza live ni ROS
- Lampman MAE **no** es SLA de Tobarra
- IoU ≠ ROS (`docs/METRICS_HONESTY_IOU_NE_ROS.md`)
- GO_MES+ / grade A Hellín **no** se reclaman

## Dónde acierta / se abstiene

| Escenario | Comportamiento |
|-----------|----------------|
| Tobarra LWIR multi-frame grade A | Ops confiable; card puede **GO** con gate this-run |
| Solo ML (sin ops) bajo field_ops | **ABSTAIN** (no HOLD táctico) |
| Hellín | Grade **B** honesto (ratio ~0.56 vs Vp 50); no grade A |
| Sin fuentes | **ABSTAIN** |

## Datos de muestra / fuentes del card

Ver `sample_data/README.md`.

| Fuente en el card | Qué es | Qué **no** es |
|-------------------|--------|----------------|
| Ops Tobarra | LWIR multi-frame grade A, ROS ~5.7 m/min | |
| `area_ha_max` ops | **Máx. ha máscara térmica observada** (~52 ha) | Ancla INFOCAM 39 ha (`reference_area_ha`) |
| Open EMSR900 ha | **Proxy ilustrativo** de escala CEMS (hub) | Co-incidente geográfico con Tobarra |

El GO del pack lo mueve sobre todo **ops** (`ops_confidence_ok`); open aporta peso de
monitorización multi-fuente, no “mismo incendio”.

Los GeoTIFF LWIR de Tobarra viven en el repo
(`artifacts/tobarra_reprojected_lwir/`, `data/real_if/…`) y **no** se
duplican enteros en el zip (pesados). Las métricas ops ya computadas sí
viajan en el pack para replay offline.

## Contacto / acta humana

La **demo con tercero firmada** (H1 / M3.2) y el informe 8–12 pp (H2)
son tareas **humanas**. Este pack es la evidencia eng reproducible.
Plantilla de acta: `docs/ACTA_DEMO_TERCERO_TEMPLATE.md`.
"""
    (out / "README.md").write_text(text, encoding="utf-8")


def _write_research_citations(out: Path) -> None:
    text = """# Research citations (pack demo)

Tres anclas SOTA usadas en el Reliability Report — **método / rails**, no SLA de Tobarra.

1. **Lampman et al. 2026 (IJWF)** — Repeat-pass TIR / UAS → ROS (y FI/FRP) en fuego prescrito de pastizal. WFD adopta el **principio de medición geométrica** LWIR multi-pasada como capa Ops; **no** traslada MAE/R² del paper a incendios mediterráneos operativos.
   https://connectsci.au/wf/article/35/5/WF25133/272342/Leveraging-drone-based-thermal-imagery-and

2. **Orion-AI-Lab / Kondylatos et al.** — Uncertainty-aware wildfire danger (epistémica + aleatoria) con umbrales de rechazo. WFD mapea u alta → **GO / HOLD / ABSTAIN** en la Decision Card; **nunca** renombra a EVACUATE/SAFE de marketing.
   Paper: https://arxiv.org/abs/2509.25017 · código: https://github.com/Orion-AI-Lab/uncertainty-wildfires

3. **Corpus fuel Med (~93 estudios)** — `docs/fire_intel/LITERATURE_CORPUS_ROS_FUEL.md` + `data/fire_intel/literature/corpus_v1.json`. Hybrid α / Rothermel-lite son **priors de envelope**, peso táctico 0 en field_ops; sin viento medido → abstenerse de despacho por prior.

Más contexto: `docs/fire_intel/SOTA_STACK_ADOPTION_2026.md` · `docs/RELIABILITY_GATE_REPORT_THIRD_PARTY.md`.
"""
    (out / "RESEARCH_CITATIONS.md").write_text(text, encoding="utf-8")


def _write_sample_data(out: Path, ops: dict[str, Any], open_m: dict[str, Any]) -> None:
    sample = out / "sample_data"
    sample.mkdir(parents=True, exist_ok=True)
    (sample / "ops_metrics_tobarra.json").write_text(
        json.dumps(ops, indent=2, default=str), encoding="utf-8"
    )
    (sample / "open_metrics_cems.json").write_text(
        json.dumps(open_m, indent=2, default=str), encoding="utf-8"
    )
    ref_ha = ops.get("reference_area_ha")
    obs_ha = ops.get("area_ha_max")
    readme = f"""# sample_data

Métricas **ya computadas** usadas para el Decision Card del pack (offline).

| Archivo | Origen |
|---------|--------|
| `ops_metrics_tobarra.json` | Tobarra 2024-08-02 ops (grade A, ROS ~5.7 m/min vs Vp 7) |
| `open_metrics_cems.json` | **Illustrative** CEMS-scale open proxy (EMSR900 hub numbers) — **not** Tobarra co-incident |

## Area fields (honesty)

| Field | Typical value | Meaning |
|-------|--------------:|---------|
| `area_ha_max` | **{obs_ha}** | Observed thermal **mask** max ha (ops pack) |
| `reference_area_ha` | **{ref_ha}** | INFOCAM **anchor** ha — not mask max |
| open `max_area_ha` | ~44376 | EMSR900-scale CEMS proxy for multi-source demo only |

Do **not** read 39 ha as observed thermal area, or EMSR900 ha as Tobarra burned area.

## Si quieres re-ejecutar ingest LWIR (opcional, no requerido para replay)

En el **repo completo** (no en el zip ligero):

```text
artifacts/tobarra_reprojected_lwir/     # LWIR reproyectado
artifacts/tobarra_lwir_masks/           # máscaras
outputs/observatorio/tobarra_20240802/  # pack ops ya generado
data/infocam_anchors.json               # ancla Vp=7
```

```powershell
# Ejemplo (pesado): ver docs/GUIA_COMANDOS_RECREAR_TODO.md
python scripts/score_infocam_anchors.py
```

El replay forense **no** necesita los GeoTIFF: basta `replay_sources.json`.
"""
    (sample / "README.md").write_text(readme, encoding="utf-8")


def _write_run_scripts(out: Path) -> None:
    ps1 = """# E3 replay from this pack (run from repo root preferred)
$ErrorActionPreference = "Stop"
$PackDir = $PSScriptRoot
$RepoRoot = Resolve-Path (Join-Path $PackDir "..\\..") -ErrorAction SilentlyContinue
if (-not $RepoRoot) { $RepoRoot = Get-Location }
Set-Location $RepoRoot
$env:PYTHONPATH = (Get-Location).Path
Write-Host "Replay bundle: $PackDir"
python scripts/run_third_party_replay.py --bundle $PackDir
exit $LASTEXITCODE
"""
    (out / "run_replay.ps1").write_text(ps1, encoding="utf-8")

    sh = """#!/usr/bin/env bash
# E3 replay from this pack (run from repo root preferred)
set -euo pipefail
PACK_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$PACK_DIR/../.." 2>/dev/null && pwd || pwd)"
cd "$REPO_ROOT"
export PYTHONPATH="$REPO_ROOT"
echo "Replay bundle: $PACK_DIR"
python scripts/run_third_party_replay.py --bundle "$PACK_DIR"
"""
    (out / "run_replay.sh").write_text(sh, encoding="utf-8")


def _write_manifest(out: Path, card: dict[str, Any], *, self_replay_ok: bool) -> dict[str, Any]:
    files: dict[str, str] = {}
    for name in (
        "fire_decision_card.json",
        "fire_decision_card.md",
        "replay_sources.json",
        "forensic_manifest.json",
        "reliability_gate_report.json",
        "README.md",
        "RESEARCH_CITATIONS.md",
        "run_replay.ps1",
        "run_replay.sh",
        "sample_data/ops_metrics_tobarra.json",
        "sample_data/open_metrics_cems.json",
    ):
        p = out / name
        if p.is_file():
            files[name] = _sha256_file(p)

    audit = card.get("audit") or {}
    manifest = {
        "schema": "demo_third_party_replay_manifest_v1",
        "pack_id": "demo_third_party",
        "event_id": card.get("event_id") or EVENT_ID,
        "built_at_utc": datetime.now(UTC).isoformat(),
        "policy_id": (card.get("metrics") or {}).get("policy_id")
        or (audit.get("policy_id") or "field_ops"),
        "decision": card.get("decision"),
        "confidence_pred": card.get("confidence_pred"),
        "system_reliability_pass": card.get("system_reliability_pass"),
        "self_replay_ok": self_replay_ok,
        "allow_ml_live_in_fusion": False,
        "ml_product_go": False,
        "rails": {
            "field_ops_ml_live_fusion": "OFF",
            "lampman_mae_as_sla": False,
            "iou_as_ros": False,
        },
        "card_output_hash": audit.get("output_hash"),
        "card_input_hash": audit.get("input_hash"),
        "files_sha256": files,
        "content_checksum": _sha256_text(json.dumps(files, sort_keys=True)),
        "pack_version": "1.0.0",
        "how_to_replay": "python scripts/run_third_party_replay.py --bundle outputs/demo_third_party",
        "docs": {
            "reliability_report": "docs/RELIABILITY_GATE_REPORT_THIRD_PARTY.md",
            "honesty": "docs/METRICS_HONESTY_IOU_NE_ROS.md",
            "plan": "docs/PLAN_1_MES_GRAPH_V6_IMPLEMENT.md",
        },
    }
    (out / "replay_manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str), encoding="utf-8"
    )
    return manifest


def build_pack(
    out: Path,
    *,
    make_zip: bool = True,
    dist_dir: Path | None = None,
) -> dict[str, Any]:
    from wildfire_front.incident.pipeline import publish_decision_card
    from wildfire_front.product.forensics import load_and_replay_bundle

    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    ops = _enrich_ops_from_repo()
    open_m = dict(OPEN_CEMS)

    # Publish field_ops card + this-run reliability gate + forensic bundle.
    # Keys: fire_decision_card_json/md, forensic_*, decision, …
    artifacts = publish_decision_card(
        out,
        EVENT_ID,
        ops,
        n_frames=int(ops.get("n_frames_staged") or ops.get("n_frames") or 0),
        include_ml_metrics=True,  # holdout provenance only; not fused under field_ops
        open_metrics=open_m,
        decision_policy="field_ops",
        require_ops_for_go=True,
        write_this_run_gate=True,
    )
    card_path = Path(artifacts.get("fire_decision_card_json") or (out / "fire_decision_card.json"))
    if not card_path.is_file():
        raise FileNotFoundError(f"decision card not written: {card_path}")
    card = json.loads(card_path.read_text(encoding="utf-8"))

    self_replay_ok = str(artifacts.get("forensic_self_replay_ok")).lower() in {
        "true",
        "1",
    }
    # Double-check with E3 path
    replay_result = load_and_replay_bundle(out, base=ROOT)
    self_replay_ok = bool(replay_result.get("replay_ok"))

    _write_readme(
        out,
        decision=str(card.get("decision")),
        conf=card.get("confidence_pred"),
        replay_ok=self_replay_ok,
    )
    _write_research_citations(out)
    _write_sample_data(out, ops, open_m)
    _write_run_scripts(out)
    manifest = _write_manifest(out, card, self_replay_ok=self_replay_ok)

    zip_path: Path | None = None
    if make_zip:
        dist = Path(dist_dir or DIST_DEFAULT)
        dist.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%d")
        zip_path = dist / f"demo_third_party_{stamp}.zip"
        if zip_path.is_file():
            zip_path.unlink()
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for p in sorted(out.rglob("*")):
                if p.is_file():
                    zf.write(p, arcname=str(Path("demo_third_party") / p.relative_to(out)))
        try:
            zip_rel = str(zip_path.relative_to(ROOT)).replace("\\", "/")
        except ValueError:
            zip_rel = str(zip_path)
        manifest["zip_path"] = zip_rel
        manifest["zip_sha256"] = _sha256_file(zip_path)
        (out / "replay_manifest.json").write_text(
            json.dumps(manifest, indent=2, default=str), encoding="utf-8"
        )

    summary = {
        "ok": self_replay_ok and card.get("decision") in {"GO", "HOLD", "ABSTAIN"},
        "out_dir": str(out),
        "zip_path": str(zip_path) if zip_path else None,
        "decision": card.get("decision"),
        "confidence_pred": card.get("confidence_pred"),
        "policy_id": manifest.get("policy_id"),
        "system_reliability_pass": card.get("system_reliability_pass"),
        "self_replay_ok": self_replay_ok,
        "allow_ml_live_in_fusion": False,
        "event_id": EVENT_ID,
        "artifacts": artifacts,
    }
    (out / "pack_build_summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8"
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build demo-with-third-parties pack (E1).")
    parser.add_argument(
        "--output",
        type=Path,
        default=OUT_DEFAULT,
        help=f"Output directory (default: {OUT_DEFAULT})",
    )
    parser.add_argument(
        "--dist",
        type=Path,
        default=DIST_DEFAULT,
        help=f"Zip output directory (default: {DIST_DEFAULT})",
    )
    parser.add_argument("--no-zip", action="store_true", help="Skip zip under dist/")
    args = parser.parse_args(argv)

    summary = build_pack(args.output, make_zip=not args.no_zip, dist_dir=args.dist)
    print("demo third-party pack built:")
    print(f"  out:      {summary['out_dir']}")
    print(f"  decision: {summary['decision']}  conf={summary.get('confidence_pred')}")
    print(f"  policy:   {summary.get('policy_id')}")
    print(f"  reliability_pass: {summary.get('system_reliability_pass')}")
    print(f"  self_replay_ok:   {summary.get('self_replay_ok')}")
    if summary.get("zip_path"):
        print(f"  zip:      {summary['zip_path']}")
    if not summary.get("self_replay_ok"):
        print("warning: self_replay_ok is False — pack still written", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
