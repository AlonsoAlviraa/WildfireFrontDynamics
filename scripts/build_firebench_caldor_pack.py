"""Build the aligned FireBench Caldor label bridge."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.open_if.firebench_caldor import materialize_caldor_label_pack

DEFAULT_SOURCE = ROOT / "data" / "external" / "firebench" / "caldor_2021" / "v2026.1"
DEFAULT_OUT = ROOT / "data" / "open_if" / "external_bridge" / "US_FIREBENCH_CALDOR_2021"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--gsd-m", type=float, default=30.0)
    parser.add_argument("--max-dim", type=int, default=4096)
    args = parser.parse_args()
    report = materialize_caldor_label_pack(
        args.source, args.out, gsd_m=args.gsd_m, max_dim=args.max_dim
    )
    print(json.dumps({k: report[k] for k in ("schema", "n_observations", "n_pairs", "n_pairs_12_to_36h", "n_pairs_with_material_raw_revision", "rights")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
