#!/usr/bin/env python3
"""Build a light open_if pack from Copernicus Rapid Mapping 2026 API.

Uses public-activations + product stats (burnt ha) + AOI FeatureCollection.
Avoids heavy multi-10MB observedEventA geometry for fast season packs.

  python scripts/build_open_if_from_rm_api.py --activation EMSR898
  python scripts/build_open_if_from_rm_api.py --activation EMSR900
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RM_API = "https://rapidmapping.emergency.copernicus.eu/backend/dashboard-api/public-activations/"


def _utc() -> str:
    return datetime.now(UTC).isoformat()


def _get_json(url: str) -> Any:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "WildfireFrontDynamics-open-if/1.0",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read().decode("utf-8"))


def _burnt_ha(stats: dict[str, Any] | None) -> float | None:
    if not isinstance(stats, dict):
        return None
    ba = stats.get("Burnt area") or stats.get("Burnt Area") or {}
    if not isinstance(ba, dict):
        return None
    # shape: {"None": {"unit":"ha","affected": 26749.6}}
    for _k, v in ba.items():
        if isinstance(v, dict) and v.get("affected") not in (None, "NA"):
            try:
                return float(v["affected"])
            except (TypeError, ValueError):
                continue
    return None


def build(code: str, out_root: Path) -> dict[str, Any]:
    code = code.upper().strip()
    act_data = _get_json(f"{RM_API}?code={code}")
    results = act_data.get("results") or []
    if not results:
        raise RuntimeError(f"No activation results for {code}")
    act = results[0]
    aoi_fc = _get_json(f"{RM_API}download-aois/?code={code}")

    products: list[dict[str, Any]] = []
    for aoi in act.get("aois") or []:
        aoi_name = aoi.get("name")
        aoi_n = aoi.get("number")
        for prod in aoi.get("products") or []:
            ha = _burnt_ha(prod.get("stats"))
            ver = prod.get("version") or {}
            products.append(
                {
                    "aoi_name": aoi_name,
                    "aoi_number": aoi_n,
                    "type": prod.get("type"),
                    "monitoring": prod.get("monitoring"),
                    "monitoringNumber": prod.get("monitoringNumber"),
                    "burnt_area_ha": ha,
                    "deliveryTime": ver.get("deliveryTime"),
                    "statusCode": ver.get("statusCode"),
                    "downloadPath": prod.get("downloadPath"),
                }
            )

    ha_vals = [p["burnt_area_ha"] for p in products if p.get("burnt_area_ha") is not None]
    max_ha = max(ha_vals) if ha_vals else None
    timeline = sorted(
        [p for p in products if p.get("burnt_area_ha") is not None],
        key=lambda p: (p.get("deliveryTime") or "", p.get("aoi_number") or 0),
    )

    pack_dir = out_root / code.lower()
    pack_dir.mkdir(parents=True, exist_ok=True)
    (pack_dir / "raw_api").mkdir(exist_ok=True)
    (pack_dir / "raw_api" / "activation.json").write_text(
        json.dumps(act_data, indent=2, default=str), encoding="utf-8"
    )
    (pack_dir / "aois.geojson").write_text(json.dumps(aoi_fc, indent=2), encoding="utf-8")

    scorecard = {
        "schema": "scorecard_pista_b_v1",
        "activation": code,
        "built_at_utc": _utc(),
        "source": "copernicus_rapidmapping_public_api",
        "name": act.get("name"),
        "eventTime": act.get("eventTime"),
        "activationTime": act.get("activationTime"),
        "countries": act.get("countries"),
        "max_area_ha": max_ha,
        "n_timeline_steps": len(timeline),
        "n_products": len(products),
        "O2_cems_delineation": "GO" if max_ha else "PARTIAL",
        "O2_national_official": "NO_GO_CEMS_PROXY",
        "decision_open": "HOLD",
        "not_tactical_dispatch": True,
        "not_official_perimeter": True,
        "notes": (
            "Areas from CEMS product stats Burnt area (ha). "
            "AOI polygons only in aois.geojson — not national cadastre. "
            "Never invent Vp. Press ha is separate (fire_intel)."
        ),
        "products": products,
        "timeline_burnt_ha": [
            {
                "deliveryTime": p.get("deliveryTime"),
                "aoi": p.get("aoi_name"),
                "type": p.get("type"),
                "burnt_area_ha": p.get("burnt_area_ha"),
            }
            for p in timeline
        ],
        "portal": f"https://mapping.emergency.copernicus.eu/activations/{code}/",
        "api": f"{RM_API}?code={code}",
    }
    (pack_dir / "scorecard_pista_b.json").write_text(
        json.dumps(scorecard, indent=2, default=str), encoding="utf-8"
    )

    brief = [
        f"# Open pack {code} (Rapid Mapping API light)",
        "",
        f"- **Name:** {act.get('name')}",
        f"- **Max burnt ha (CEMS stats):** {max_ha}",
        f"- **Products:** {len(products)}",
        f"- **Timeline steps with ha:** {len(timeline)}",
        "- **decision_open:** HOLD (not tactical)",
        "- **O2 national:** NO_GO_CEMS_PROXY",
        "",
        "See `scorecard_pista_b.json` and `aois.geojson`.",
        "",
    ]
    (pack_dir / "brief.md").write_text("\n".join(brief), encoding="utf-8")

    manifest = {
        "activation": code,
        "built_at_utc": _utc(),
        "pack_kind": "rm_api_light",
        "max_area_ha": max_ha,
        "files": ["scorecard_pista_b.json", "aois.geojson", "brief.md", "raw_api/activation.json"],
    }
    (pack_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return scorecard


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--activation", required=True)
    ap.add_argument(
        "--out-root",
        type=Path,
        default=ROOT / "outputs" / "open_if",
    )
    args = ap.parse_args()
    sc = build(args.activation, args.out_root)
    print(
        json.dumps(
            {
                "ok": True,
                "activation": sc["activation"],
                "max_area_ha": sc["max_area_ha"],
                "n_products": sc["n_products"],
                "n_timeline_steps": sc["n_timeline_steps"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
