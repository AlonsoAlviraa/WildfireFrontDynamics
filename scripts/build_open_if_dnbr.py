#!/usr/bin/env python3
"""M2.3 — Optional dNBR / STAC post-fire layer for an open IF pack.

  python scripts/build_open_if_dnbr.py --pack outputs/open_if/emsr578
  python scripts/build_open_if_dnbr.py --pack outputs/open_if/emsr578 --event-date 2022-07-15

Writes into the pack dir:
  dnbr_status.json, dnbr_summary.json, dnbr_stac_items.json,
  dnbr_preview.tif (if GO), dnbr_layer.md

On STAC/network failure → status BLOCKED (still a valid plan deliverable).
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.open_if.dnbr import compute_dnbr, severity_fractions
from wildfire_front.open_if.stac_s2 import (
    KNOWN_EVENT_DATES,
    bbox_from_geojson,
    default_date_windows,
    item_summary,
    load_nbr_for_item,
    stac_search,
)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")


def _write_preview_tif(path: Path, arr: np.ndarray, bbox: tuple[float, float, float, float]) -> None:
    import rasterio
    from rasterio.transform import from_bounds

    h, w = arr.shape
    transform = from_bounds(bbox[0], bbox[1], bbox[2], bbox[3], w, h)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=h,
        width=w,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=transform,
        compress="deflate",
        nodata=np.nan,
    ) as ds:
        ds.write(arr.astype(np.float32), 1)


def _render_md(status: dict[str, Any], summary: dict[str, Any] | None) -> str:
    st = status.get("status") or "—"
    act = status.get("activation") or "—"
    lines = [
        f"# dNBR / STAC layer — {act}",
        "",
        f"**Status:** {st}",
        f"_Built: {status.get('built_at_utc')}_",
        "",
        "## What this is",
        "",
        "- Post-fire **severity proxy** from Sentinel-2 L2A (STAC Element84 Earth Search).",
        "- dNBR = NBR_pre − NBR_post using NIR (B08) + SWIR (B12) COG windows.",
        "- **Not** Spanish national cadastre; **not** tactical dispatch.",
        "",
        "## Window",
        "",
        f"- bbox: `{status.get('bbox')}`",
        f"- pre datetime: `{status.get('pre_datetime')}`",
        f"- post datetime: `{status.get('post_datetime')}`",
        f"- event_date used: `{status.get('event_date')}`",
        "",
    ]
    if summary:
        fr = (summary.get("severity") or {}).get("fractions") or {}
        lines += [
            "## Severity fractions (valid pixels)",
            "",
            f"| Class | Fraction |",
            f"|-------|----------|",
        ]
        for k, v in fr.items():
            lines.append(f"| {k} | {float(v):.3f} |")
        sev = summary.get("severity") or {}
        lines += [
            "",
            f"- mean dNBR: **{sev.get('mean')}**",
            f"- p50 / p90: {sev.get('p50')} / {sev.get('p90')}",
            f"- burned_frac ≥0.1: {sev.get('burned_frac_ge_0.1')}",
            f"- burned_frac ≥0.27: {sev.get('burned_frac_ge_0.27')}",
            f"- STAC pre item: `{summary.get('pre_item_id')}`",
            f"- STAC post item: `{summary.get('post_item_id')}`",
            "",
        ]
    if status.get("reasons"):
        lines += ["## Notes / blockers", ""]
        for r in status["reasons"]:
            lines.append(f"- {r}")
        lines.append("")
    lines += [
        "## Disclaimer",
        "",
        "Cloud residual, phenology, and window size affect dNBR. "
        "Use as multi-source fusion signal only — never as sole GO for action.",
        "",
    ]
    return "\n".join(lines)


def run_for_pack(
    pack_dir: Path,
    *,
    event_date: str | None = None,
    max_cloud: float = 40.0,
    max_size: int = 256,
    dry_run_search_only: bool = False,
) -> dict[str, Any]:
    pack_dir = Path(pack_dir)
    activation = pack_dir.name.upper()  # emsr578 → EMSR578

    sc = pack_dir / "scorecard_pista_b.json"
    if sc.is_file():
        try:
            scd = json.loads(sc.read_text(encoding="utf-8"))
            activation = str(scd.get("activation") or activation)
        except (OSError, json.JSONDecodeError):
            pass

    timeline = pack_dir / "timeline_perimeters.geojson"
    status: dict[str, Any] = {
        "schema": "open_if_dnbr_status_v1",
        "activation": activation,
        "pack_dir": str(pack_dir),
        "built_at_utc": _utc(),
        "status": "BLOCKED",
        "reasons": [],
        "product": "dnbr_stac_s2_l2a",
        "disclaimer": "Not official perimeter. Severity proxy only.",
    }

    if not timeline.is_file():
        status["reasons"].append("missing_timeline_perimeters.geojson")
        _write_json(pack_dir / "dnbr_status.json", status)
        (pack_dir / "dnbr_layer.md").write_text(_render_md(status, None), encoding="utf-8")
        return status

    try:
        bbox = bbox_from_geojson(timeline)
    except Exception as exc:  # noqa: BLE001
        status["reasons"].append(f"bbox_error:{exc}")
        _write_json(pack_dir / "dnbr_status.json", status)
        (pack_dir / "dnbr_layer.md").write_text(_render_md(status, None), encoding="utf-8")
        return status

    status["bbox"] = list(bbox)
    ed = event_date or KNOWN_EVENT_DATES.get(activation)
    status["event_date"] = ed
    pre_rng, post_rng = default_date_windows(event_date=ed)
    status["pre_datetime"] = pre_rng
    status["post_datetime"] = post_rng

    try:
        pre_items = stac_search(bbox, pre_rng, max_cloud=max_cloud)
        post_items = stac_search(bbox, post_rng, max_cloud=max_cloud)
    except Exception as exc:  # noqa: BLE001 — network/STAC → BLOCKED artifact
        status["reasons"].append(f"stac_search_failed:{type(exc).__name__}:{exc}")
        status["status"] = "BLOCKED"
        _write_json(pack_dir / "dnbr_status.json", status)
        (pack_dir / "dnbr_layer.md").write_text(_render_md(status, None), encoding="utf-8")
        return status

    if not pre_items:
        status["reasons"].append("no_pre_fire_stac_items")
    if not post_items:
        status["reasons"].append("no_post_fire_stac_items")
    if not pre_items or not post_items:
        status["status"] = "BLOCKED"
        _write_json(
            pack_dir / "dnbr_stac_items.json",
            {"pre": [], "post": [], "pre_range": pre_rng, "post_range": post_rng},
        )
        _write_json(pack_dir / "dnbr_status.json", status)
        (pack_dir / "dnbr_layer.md").write_text(_render_md(status, None), encoding="utf-8")
        return status

    pre_item = pre_items[0]
    post_item = post_items[0]
    items_doc = {
        "pre_range": pre_rng,
        "post_range": post_rng,
        "pre": [item_summary(i) for i in pre_items[:5]],
        "post": [item_summary(i) for i in post_items[:5]],
        "selected_pre": item_summary(pre_item),
        "selected_post": item_summary(post_item),
    }
    _write_json(pack_dir / "dnbr_stac_items.json", items_doc)

    if dry_run_search_only:
        status["status"] = "PARTIAL"
        status["reasons"].append("dry_run_search_only")
        _write_json(pack_dir / "dnbr_status.json", status)
        (pack_dir / "dnbr_layer.md").write_text(_render_md(status, None), encoding="utf-8")
        return status

    try:
        nbr_pre, meta_pre = load_nbr_for_item(pre_item, bbox, max_size=max_size)
        nbr_post, meta_post = load_nbr_for_item(post_item, bbox, max_size=max_size)
        h = min(nbr_pre.shape[0], nbr_post.shape[0])
        w = min(nbr_pre.shape[1], nbr_post.shape[1])
        dnbr = compute_dnbr(nbr_pre[:h, :w], nbr_post[:h, :w])
        sev = severity_fractions(dnbr)
        summary = {
            "schema": "open_if_dnbr_summary_v1",
            "activation": activation,
            "bbox": list(bbox),
            "event_date": ed,
            "pre_item_id": pre_item.get("id"),
            "post_item_id": post_item.get("id"),
            "severity": sev,
            "meta_pre": meta_pre,
            "meta_post": meta_post,
            "window_max_size": max_size,
            "formula": "dNBR = NBR_pre - NBR_post; NBR=(NIR-SWIR)/(NIR+SWIR)",
            "built_at_utc": _utc(),
        }
        _write_json(pack_dir / "dnbr_summary.json", summary)
        preview = pack_dir / "dnbr_preview.tif"
        try:
            _write_preview_tif(preview, dnbr, bbox)
            status["preview_tif"] = str(preview.name)
        except Exception as exc:  # noqa: BLE001
            status["reasons"].append(f"preview_write_failed:{exc}")

        status["status"] = "GO"
        status["reasons"].append("dnbr_window_ok")
        status["severity_mean"] = sev.get("mean")
        status["burned_frac_ge_0.27"] = sev.get("burned_frac_ge_0.27")
        _write_json(pack_dir / "dnbr_status.json", status)
        (pack_dir / "dnbr_layer.md").write_text(_render_md(status, summary), encoding="utf-8")

        # enrich scorecard if present
        if sc.is_file():
            try:
                scd = json.loads(sc.read_text(encoding="utf-8"))
                scd["dnbr_stac_status"] = status["status"]
                scd["dnbr_mean"] = sev.get("mean")
                scd["dnbr_burned_frac_ge_0.27"] = sev.get("burned_frac_ge_0.27")
                scd["dnbr_pre_item"] = pre_item.get("id")
                scd["dnbr_post_item"] = post_item.get("id")
                _write_json(sc, scd)
            except (OSError, json.JSONDecodeError):
                pass
        return status
    except Exception as exc:  # noqa: BLE001
        status["status"] = "BLOCKED"
        status["reasons"].append(f"cog_read_or_dnbr_failed:{exc}")
        status["traceback"] = traceback.format_exc()[-1500:]
        _write_json(pack_dir / "dnbr_status.json", status)
        (pack_dir / "dnbr_layer.md").write_text(_render_md(status, None), encoding="utf-8")
        return status


def main() -> int:
    ap = argparse.ArgumentParser(description="Build optional dNBR/STAC layer for open IF pack")
    ap.add_argument(
        "--pack",
        type=Path,
        default=ROOT / "outputs" / "open_if" / "emsr578",
        help="Open IF pack directory (default: outputs/open_if/emsr578)",
    )
    ap.add_argument("--event-date", default=None, help="YYYY-MM-DD mid-fire date for windows")
    ap.add_argument("--max-cloud", type=float, default=40.0)
    ap.add_argument("--max-size", type=int, default=256, help="COG window max pixels")
    ap.add_argument(
        "--search-only",
        action="store_true",
        help="Only STAC search (no COG read) → PARTIAL",
    )
    args = ap.parse_args()
    status = run_for_pack(
        args.pack,
        event_date=args.event_date,
        max_cloud=args.max_cloud,
        max_size=args.max_size,
        dry_run_search_only=bool(args.search_only),
    )
    print(json.dumps(status, indent=2, default=str))
    # Plan accepts GO or BLOCKED doc as delivery
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
