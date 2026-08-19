#!/usr/bin/env python3
"""Refresh the paper console while preserving its existing product payload."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.product.app_spa import write_product_app  # noqa: E402
from wildfire_front.product.research_status import build_research_status  # noqa: E402


def refresh_console(output: Path, repo_root: Path = ROOT) -> dict:
    payload_path = output / "app_payload.json"
    if not payload_path.is_file():
        raise FileNotFoundError(f"paper console payload is missing: {payload_path}")
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    payload["research_status"] = build_research_status(repo_root)
    write_product_app(payload, output)
    validation_figure = (
        repo_root / "docs/figures/rcda_validation_evidence_20260819.svg"
    )
    if validation_figure.is_file():
        shutil.copy2(validation_figure, output / "validation_evidence.svg")
    return payload["research_status"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "outputs/app/rcda_paper_console",
    )
    args = parser.parse_args()
    status = refresh_console(args.output)
    print(json.dumps(status, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
