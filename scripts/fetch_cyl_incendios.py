#!/usr/bin/env python3
"""Fetch Castilla y León open-data forest fire parts (INFORCYL dataset).

Dataset: incendios-forestales (JCyL OpenDataSoft)
  https://analisis.datosabiertos.jcyl.es/explore/dataset/incendios-forestales/

Examples:
  python scripts/fetch_cyl_incendios.py --query "LLAMAS DE CABRERA"
  python scripts/fetch_cyl_incendios.py --min-nivel 2 --limit 50 --out docs/cyl_candidates.json
  python scripts/fetch_cyl_incendios.py --query YERES --fecha-inicio 2025-08-09
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = (
    "https://jcyl.opendatasoft.com/api/explore/v2.1/catalog/datasets/"
    "incendios-forestales/records"
)


def fetch_records(
    *,
    where: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    params: dict[str, str] = {"limit": str(limit), "offset": str(offset)}
    if where:
        params["where"] = where
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "WildfireFrontDynamics/0.1"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _prov(rec: dict) -> str:
    p = rec.get("provincia")
    if isinstance(p, list):
        return ",".join(str(x) for x in p)
    return str(p or "")


def build_where(
    *,
    query: str | None,
    min_nivel: int | None,
    provincia: str | None,
) -> str | None:
    """Server-side filters. Date is applied client-side (API date ops are brittle)."""
    clauses: list[str] = []
    if query:
        # search() is case-insensitive on OpenDataSoft
        q = query.replace('"', "")
        clauses.append(f'search(termino_municipal, "{q}")')
    if min_nivel is not None and min_nivel > 0:
        # nivel_maximo_alcanzado is often string "0"/"1"/"2"
        levels = ", ".join(f'"{i}"' for i in range(min_nivel, 4))
        clauses.append(f"nivel_maximo_alcanzado IN ({levels})")
    if provincia:
        # provincia is a multivalued text field — use search for robustness
        prov = provincia.replace('"', "")
        clauses.append(f'search(provincia, "{prov}")')
    if not clauses:
        return None
    return " AND ".join(clauses)


def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch CyL open-data fire parts")
    ap.add_argument("--query", type=str, default=None, help="Search termino_municipal")
    ap.add_argument("--fecha-inicio", type=str, default=None, help="YYYY-MM-DD")
    ap.add_argument("--min-nivel", type=int, default=None, help="Min nivel_maximo (0-3)")
    ap.add_argument("--provincia", type=str, default=None, help="e.g. LEÓN or LEON")
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write JSON (default: stdout summary only)",
    )
    ap.add_argument(
        "--csv",
        type=Path,
        default=None,
        help="Optional CSV export of unique fires",
    )
    ap.add_argument(
        "--recommend",
        action="store_true",
        help="Print recommended transparency target (Llamas de Cabrera)",
    )
    args = ap.parse_args()

    if args.recommend and not args.query:
        args.query = "LLAMAS DE CABRERA"
        args.fecha_inicio = args.fecha_inicio or "2025-08-08"

    where = build_where(
        query=args.query,
        min_nivel=args.min_nivel,
        provincia=args.provincia,
    )
    # Pull more rows if filtering by date client-side
    pull = max(args.limit, 100) if args.fecha_inicio else args.limit
    try:
        data = fetch_records(where=where, limit=min(pull, 100))
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR fetching open data: {exc}", file=sys.stderr)
        return 1

    results = data.get("results") or []
    if args.fecha_inicio:
        target = args.fecha_inicio
        results = [
            r
            for r in results
            if str(r.get("fecha_de_inicio") or "").startswith(target)
        ]

    # Dedupe by province+municipio+start; prefer records with richer surface text
    unique: dict[tuple, dict] = {}
    for rec in results:
        key = (_prov(rec), rec.get("termino_municipal"), rec.get("fecha_de_inicio"))
        prev = unique.get(key)
        if prev is None:
            unique[key] = rec
            continue
        prev_sup = str(prev.get("tipo_y_has_de_superficie_afectada") or "")
        cur_sup = str(rec.get("tipo_y_has_de_superficie_afectada") or "")
        # Prefer non "EN PERIMETRACION" and longer descriptions
        def _score(s: str) -> int:
            if not s or "PERIMETR" in s.upper():
                return 0
            return len(s)

        if _score(cur_sup) >= _score(prev_sup):
            unique[key] = rec

    rows = []
    for rec in unique.values():
        rows.append(
            {
                "fecha_de_inicio": rec.get("fecha_de_inicio"),
                "provincia": _prov(rec),
                "termino_municipal": rec.get("termino_municipal"),
                "nivel_maximo_alcanzado": rec.get("nivel_maximo_alcanzado"),
                "situacion_actual": rec.get("situacion_actual"),
                "superficie_texto": rec.get("tipo_y_has_de_superficie_afectada"),
                "fecha_del_parte": rec.get("fecha_del_parte"),
                "hora_del_parte": rec.get("hora_del_parte"),
                "posicion": rec.get("posicion"),
            }
        )
    rows.sort(key=lambda r: str(r.get("fecha_de_inicio") or ""), reverse=True)
    rows = rows[: args.limit]

    report = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source": API,
        "where": where,
        "total_count_api": data.get("total_count"),
        "n_returned": len(results),
        "n_unique": len(rows),
        "fires": rows,
        "transparency_hint": {
            "doc": "docs/SOLICITUD_TRANSPARENCIA_CYL.md",
            "recommended": "Llamas de Cabrera (Benuza), León, 2025-08-08",
            "ask_for": ["perímetro vectorial", "ficha ha finales", "IGR/nivel"],
        },
    }

    print(json.dumps({k: report[k] for k in report if k != "fires"}, indent=2))
    print(f"\n=== {len(rows)} unique fires ===")
    for r in rows[:25]:
        print(
            f"{r.get('fecha_de_inicio')} | {r.get('provincia')} | "
            f"{str(r.get('termino_municipal'))[:45]} | "
            f"nmax={r.get('nivel_maximo_alcanzado')} | "
            f"{str(r.get('superficie_texto') or '')[:60]}"
        )
    if len(rows) > 25:
        print(f"... +{len(rows) - 25} more")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print("Wrote", args.out)

    if args.csv:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        fields = [
            "fecha_de_inicio",
            "provincia",
            "termino_municipal",
            "nivel_maximo_alcanzado",
            "situacion_actual",
            "superficie_texto",
            "fecha_del_parte",
        ]
        with args.csv.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            for r in rows:
                w.writerow(r)
        print("Wrote", args.csv)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
