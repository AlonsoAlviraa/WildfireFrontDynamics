"""python -m relator  → print the T+0…T+N clock."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .agent import demo_script, print_frames, run_clock
from .board import render_grid
from .render import write_html


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="relator", description="Relator constellation desk (not dispatch).")
    p.add_argument("--json", action="store_true", help="dump frames as JSON")
    p.add_argument("--html", type=Path, default=None, help="write a one-page board HTML")
    p.add_argument("--incident", default="nijar_demo")
    p.add_argument("--aoi", default="nijar", help="nijar | tobarra")
    p.add_argument(
        "--pull-sky",
        action="store_true",
        help="download NASA GIBS VIIRS chips (true color, SWIR, thermal) for the AOI",
    )
    p.add_argument(
        "--live-europe",
        action="store_true",
        help="fetch FIRMS VIIRS Europe 24h and print the densest cluster (not official ha)",
    )
    p.add_argument("--gcp", action="store_true", help="print pinned GCP project (no LLM)")
    args = p.parse_args(argv)
    if args.gcp:
        from .gcp import settings

        json.dump(settings(), sys.stdout, indent=2)
        sys.stdout.write("\n")
        if not any((args.pull_sky, args.live_europe, args.html, args.json)):
            return 0
    if args.pull_sky:
        from .satellites import pull_constellation, write_manifest

        dest = Path("outputs") / "relator_demo" / "chips"
        pack = pull_constellation(args.aoi, dest)
        write_manifest(pack, dest / "manifest.json")
        sys.stdout.write(
            f"sky pack ok={pack['ok']} chips={len(pack['chips'])} "
            f"errors={len(pack['errors'])} dir={dest}\n"
        )
        for err in pack["errors"]:
            sys.stdout.write(f"  ! {err}\n")
    if args.live_europe:
        from .satellites import densest_cluster, pull_firms_europe_24h

        live = pull_firms_europe_24h()
        cluster = densest_cluster(live.get("points") or [])
        sys.stdout.write(
            f"FIRMS Europe 24h: {live['n_hotspots']} hotspots "
            f"(cite:{live['cite']}) ≠ official burned area\n"
        )
        if cluster:
            sys.stdout.write(f"densest cluster n={cluster['n']} bbox={cluster['bbox']}\n")
    frames = run_clock(demo_script(aoi=args.aoi), incident_id=args.incident)
    if args.json:
        json.dump(frames, sys.stdout, indent=2, default=str)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(print_frames(frames) + "\n")
    if args.html:
        write_html(frames, args.html)
        sys.stdout.write(f"wrote {args.html}\n")
    last = frames[-1]
    sys.stdout.write("\nlast grid\n" + render_grid(last) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
