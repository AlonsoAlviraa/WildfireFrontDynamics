#!/usr/bin/env python3
"""Record CLI + app + one-fire e2e walkthrough (not H1, does not close GO_Q).

  python scripts/record_product_walkthrough.py
  python scripts/record_product_walkthrough.py --skip-encode
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.product.demo_walkthrough import (  # noqa: E402
    encode_video,
    probe_video,
    run_walkthrough,
    storyboard_markdown,
    walkthrough_spec,
    write_frames,
)

DEFAULT_OUT = ROOT / "outputs" / "walkthrough"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Record WFD operator walkthrough video.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--work-dir", type=Path, default=None)
    parser.add_argument("--skip-encode", action="store_true")
    parser.add_argument("--hold", type=int, default=6, help="Duplicate frames per chapter")
    args = parser.parse_args(argv)

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    run = run_walkthrough(repo=ROOT, work_dir=args.work_dir, out_dir=out)
    (out / "run.json").write_text(json.dumps(run, indent=2, default=str), encoding="utf-8")
    board = storyboard_markdown(run)
    (out / "STORYBOARD.md").write_text(board, encoding="utf-8")
    spec = walkthrough_spec(work_dir=args.work_dir, out_dir=out)
    (out / "chapters.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")

    print(json.dumps({"phase": "run", "ok": run.get("ok"), "n": len(run.get("results") or [])}))
    if args.skip_encode:
        return 0 if run.get("ok") else 1

    frames = write_frames(run, out / "frames", hold=max(1, args.hold))
    video = out / "wfd_operator_walkthrough.mp4"
    enc = encode_video(out / "frames", video)
    (out / "encode.json").write_text(json.dumps(enc, indent=2), encoding="utf-8")
    probes = [probe_video(video), probe_video(video)]
    (out / "probe.json").write_text(json.dumps(probes, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": bool(run.get("ok") and enc.get("ok")),
                "video": enc.get("path"),
                "bytes": enc.get("bytes"),
                "frames": len(frames),
                "duration_s": (probes[0] or {}).get("duration_s"),
                "go_q": "partial",
                "not_tactical_dispatch": True,
            },
            default=str,
        )
    )
    if not enc.get("ok"):
        print(enc.get("stderr") or "encode failed", file=sys.stderr)
        return 2
    return 0 if run.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
