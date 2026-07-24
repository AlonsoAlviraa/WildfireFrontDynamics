#!/usr/bin/env python3
"""One command to understand and show the whole product.

cd C:\\Users\\Mariano\\Documents\\ALONSOO\\WildfireFrontDynamics
$env:PYTHONPATH = "."
python scripts/show_all.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str], timeout: int = 180) -> bool:
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    print(">", " ".join(cmd), flush=True)
    p = subprocess.run(cmd, cwd=str(ROOT), env=env, timeout=timeout)
    return p.returncode == 0


def main() -> int:
    print("\n=== WildfireFrontDynamics — SHOW ALL ===\n", flush=True)
    ok = True
    ok &= run([sys.executable, str(ROOT / "scripts" / "reliability_gate.py")])
    ok &= run([sys.executable, str(ROOT / "scripts" / "build_metrics_hub.py")])
    ok &= run([sys.executable, str(ROOT / "scripts" / "build_open_if_index.py")])
    ok &= run([sys.executable, str(ROOT / "scripts" / "build_portal.py")])
    ok &= run([sys.executable, str(ROOT / "scripts" / "build_commander_app.py")])
    ok &= run(
        [
            sys.executable,
            "-m",
            "wildfire_front",
            "decide",
            "--event-id",
            "show",
            "--use-ml-v34",
            "--open-pack",
            str(ROOT / "outputs" / "open_if" / "emsr578"),
            "--require-ops-for-go",
        ]
    )

    commander = ROOT / "docs" / "commander" / "index.html"
    portal = ROOT / "docs" / "PORTAL.html"
    index = ROOT / "outputs" / "open_if" / "index.html"
    print("\n=== Abriendo COMMAND app + portal ===\n", flush=True)
    if commander.is_file():
        webbrowser.open(commander.resolve().as_uri())
    if portal.is_file():
        webbrowser.open(portal.resolve().as_uri())
    if index.is_file():
        webbrowser.open(index.resolve().as_uri())

    print(
        json.dumps(
            {
                "ok": ok,
                "open": [
                    str(commander),
                    str(portal),
                    "docs/START_HERE.md",
                ],
                "message": "App de sala de mando abierta (docs/commander). F=fullscreen, 1-4=packs.",
            },
            indent=2,
        ),
        flush=True,
    )
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
