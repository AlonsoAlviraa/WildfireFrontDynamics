#!/usr/bin/env python3
"""Export v21 production checkpoint to TorchScript for Docker/edge deployment."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from wildfire_front.ml.export_torchscript import export_torchscript  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Export production spread model to TorchScript")
    parser.add_argument(
        "--manifest",
        default=str(PROJECT_ROOT / "models" / "production" / "manifest.json"),
    )
    parser.add_argument(
        "--weights",
        default=None,
        help="Override weights path (default: from manifest)",
    )
    parser.add_argument(
        "--output",
        default=str(PROJECT_ROOT / "models" / "production" / "spread_model_v21.pt"),
    )
    args = parser.parse_args()

    out = export_torchscript(
        args.manifest,
        args.output,
        weights_path=args.weights,
    )
    print(f"Exported TorchScript: {out}")
    print(f"Metadata: {out.with_suffix('.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())