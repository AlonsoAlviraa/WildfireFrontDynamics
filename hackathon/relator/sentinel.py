"""Sentinel-2 10 m previews via Element84 Earth Search (same family EE uses).

This is the chip that looks like a satellite, not a VIIRS pixel soup.
Still not official burned area. Still not ROS.
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any

from .satellites import UA, sky_spec

STAC = "https://earth-search.aws.element84.com/v1/search"


def search_s2(
    bbox: list[float],
    start: str,
    end: str,
    *,
    max_cloud: float = 40.0,
    limit: int = 4,
) -> list[dict[str, Any]]:
    body = json.dumps(
        {
            "collections": ["sentinel-2-l2a"],
            "bbox": list(bbox),
            "datetime": f"{start}T00:00:00Z/{end}T23:59:59Z",
            "limit": int(limit),
            "query": {"eo:cloud_cover": {"lt": float(max_cloud)}},
            "sortby": [{"field": "properties.eo:cloud_cover", "direction": "asc"}],
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        STAC,
        data=body,
        headers={"User-Agent": UA, "content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    hits = []
    for feat in payload.get("features") or []:
        props = feat.get("properties") or {}
        assets = feat.get("assets") or {}
        href = None
        for key in ("rendered_preview", "thumbnail", "visual"):
            asset = assets.get(key) or {}
            if asset.get("href"):
                href = asset["href"]
                break
        if not href:
            continue
        hits.append(
            {
                "id": feat.get("id"),
                "datetime": props.get("datetime"),
                "cloud_cover": props.get("eo:cloud_cover"),
                "href": href,
                "cite": f"sentinel2-l2a:{feat.get('id')}",
                "sensor": "Sentinel-2 L2A",
            }
        )
    return hits


def download(href: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(href, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as resp:
        dest.write_bytes(resp.read())
    return dest


def pull_sentinel_previews(aoi: str, dest_dir: Path) -> dict[str, Any]:
    spec = sky_spec(aoi)
    dates = list(spec["dates"])
    start, end = dates[0], dates[-1]
    # Pad a week so a cloudy fire-day still finds a clear Sentinel-2 scene.
    from datetime import date, timedelta

    def _shift(day: str, delta: int) -> str:
        y, m, d = (int(x) for x in day.split("-"))
        return (date(y, m, d) + timedelta(days=delta)).isoformat()

    hits = search_s2(list(spec["bbox"]), _shift(start, -8), _shift(end, 12), max_cloud=60.0)
    chips = []
    errors = []
    dest_dir = Path(dest_dir)
    for hit in hits[:2]:
        day = str(hit.get("datetime") or start)[:10]
        path = dest_dir / f"{spec['aoi']}_{day}_sentinel2.jpg"
        try:
            download(hit["href"], path)
            chips.append(
                {
                    "role": "sentinel2",
                    "sensor": hit["sensor"],
                    "date": day,
                    "path": str(path),
                    "url": hit["href"],
                    "cite": hit["cite"],
                    "cloud_cover": hit.get("cloud_cover"),
                    "why": "10 m optical. Visible scar/smoke only — not official hectares.",
                    "not_official_burned": True,
                }
            )
        except Exception as exc:
            errors.append(f"{hit.get('id')}: {type(exc).__name__}")
    return {
        "ok": bool(chips),
        "aoi": spec["aoi"],
        "label": spec["label"],
        "place": spec["place"],
        "bbox": spec["bbox"],
        "dates": dates,
        "chips": chips,
        "errors": errors,
        "source": "sentinel2_l2a_stac",
        "cite": f"sentinel2-l2a:{spec['aoi']}:{start}/{end}",
        "not_official_burned": True,
        "not_tactical_dispatch": True,
    }
