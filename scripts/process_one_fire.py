#!/usr/bin/env python
"""Process a SINGLE fire through the full pipeline.

Usage:
    set PYTHONPATH=. && python scripts\\process_one_fire.py <fire_id>

Where <fire_id> is one of:
    cardoso_2025, la_estrella_acom1_2024, la_estrella_acom2_2024,
    hellin_2024, retuerta_2025, brazatortas_2025, polan_2025

This is a companion to batch_process_fires.py that processes ONE fire
at a time, allowing real-time output monitoring and avoiding timeouts
when processing many fires in a single run.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.batch_process_fires import FIRES, process_fire

FIRE_MAP = {fire_id: (src, eid, err) for fire_id, src, eid, err in FIRES}


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/process_one_fire.py <fire_id>")
        print(f"\nAvailable fires: {', '.join(FIRE_MAP.keys())}")
        return 1

    fire_id = sys.argv[1].strip().lower()

    if fire_id not in FIRE_MAP:
        print(f"ERROR: Unknown fire_id '{fire_id}'")
        print(f"Available: {', '.join(FIRE_MAP.keys())}")
        return 1

    source_rel, event_id, error_m = FIRE_MAP[fire_id]

    try:
        summary = process_fire(fire_id, source_rel, event_id, error_m)
        print(f"\n✅ SUCCESS: {fire_id}")
        print(
            f"   TIFs={summary.get('total_tifs', 0)}  "
            f"Masks={summary.get('masks_persisted', 0)}  "
            f"Skipped={summary.get('skipped', False)}"
        )
        return 0
    except Exception as exc:
        print(f"\n❌ FAILED: {fire_id}: {exc}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
