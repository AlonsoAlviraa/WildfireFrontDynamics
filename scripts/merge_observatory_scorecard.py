#!/usr/bin/env python3
"""Merge existing per-fire packs into observatory_scorecard.json."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = ROOT / "outputs" / "observatorio"
REQUIRED = (
    "report.html",
    "fronts.geojson",
    "local_speeds.csv",
    "summary.json",
    "ingest_manifest.csv",
    "observations_manifest.csv",
)


def main() -> int:
    root = DEFAULT_ROOT
    results: list[dict] = []
    for d in sorted(root.iterdir()):
        if not d.is_dir() or d.name.startswith("_"):
            continue
        missing = [n for n in REQUIRED if not (d / n).is_file()]
        metrics: dict = {}
        if (d / "summary.json").is_file():
            metrics = json.loads((d / "summary.json").read_text(encoding="utf-8")).get(
                "metrics", {}
            )
        if not missing:
            status = "ok"
        elif metrics or (d / "ingest_manifest.csv").is_file():
            status = "partial"
        else:
            status = "failed"
        entry: dict = {
            "fire_id": d.name,
            "status": status,
            "output_dir": str(d),
            "missing_artifacts": missing,
            "metrics": metrics,
        }
        if "tobarra" in d.name:
            med = metrics.get("speed_median_m_min")
            entry["infocam_vp_m_min"] = 7.0
            entry["infocam_area_ha"] = 39.0
            entry["speed_vs_infocam_ratio"] = (
                float(med) / 7.0 if isinstance(med, (int, float)) else None
            )
            entry["notes"] = "INFOCAM 2024: 39 ha, Vp media 7 m/min"
        results.append(entry)

    ok = [r for r in results if r["status"] == "ok"]
    tobarra = next((r for r in results if "tobarra" in r["fire_id"]), None)
    a1 = len(ok) >= 3
    a2 = bool(ok) and all(not r["missing_artifacts"] for r in ok)
    a5 = False
    a5n = "no tobarra complete pack"
    if tobarra and tobarra["status"] == "ok":
        a5 = True
        a5n = (
            f"median={tobarra['metrics'].get('speed_median_m_min')} m/min "
            f"vs INFOCAM 7; ratio={tobarra.get('speed_vs_infocam_ratio')}. "
            "Mask proxy ≠ official perimeter."
        )

    scorecard = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "merged_from_existing_packs",
        "gates": {
            "A1_ge3_fires": {"pass": a1, "n_ok": len(ok)},
            "A2_artifacts_present": {"pass": a2},
            "A5_tobarra_anchor": {"pass": a5, "notes": a5n},
        },
        "fires": results,
        "observatory_message_es": (
            f"Paquete observatorio: {len(ok)} incendios con artefactos completos. "
            f"{a5n} "
            "Reconstruye dinamica OBSERVADA; no prediccion operacional 24h."
        ),
    }
    path = root / "observatory_scorecard.json"
    path.write_text(json.dumps(scorecard, indent=2, default=str), encoding="utf-8")
    print(json.dumps(scorecard["gates"], indent=2))
    print(scorecard["observatory_message_es"])
    for r in results:
        print(r["fire_id"], r["status"], "missing", r["missing_artifacts"])
    print("Wrote", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
