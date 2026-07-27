#!/usr/bin/env python3
"""Probe CEMS activations for downloadable vector packages."""
from __future__ import annotations

import json
import re
import urllib.request

CODES = [
    "EMSR578",
    "EMSR580",
    "EMSR581",
    "EMSR583",
    "EMSR632",
    "EMSR812",
    "EMSR837",
    "EMSR888",
    "EMSR896",
    "EMSR898",
]


def main() -> None:
    rows = []
    for code in CODES:
        url = f"https://mapping.emergency.copernicus.eu/activations/{code}"
        row: dict = {"code": code, "url": url}
        try:
            html = urllib.request.urlopen(url, timeout=60).read().decode("utf-8", "replace")
            zips = sorted(
                set(
                    re.findall(
                        r"https://cems-mapping-website[^\s\"'<>]+_vector\.zip",
                        html,
                    )
                )
            )
            title_m = re.search(r"<title>([^<]+)", html)
            row.update(
                {
                    "ok": True,
                    "n_vector_zips": len(zips),
                    "title": title_m.group(1).strip() if title_m else None,
                    "files": [u.split("/")[-1] for u in zips[:12]],
                }
            )
        except Exception as exc:  # noqa: BLE001
            row.update({"ok": False, "error": str(exc)[:200]})
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False))
    out = {
        "n": len(rows),
        "best": max(
            (r for r in rows if r.get("ok")),
            key=lambda r: r.get("n_vector_zips") or 0,
            default=None,
        ),
        "rows": rows,
    }
    print("---BEST---")
    print(json.dumps(out.get("best"), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
