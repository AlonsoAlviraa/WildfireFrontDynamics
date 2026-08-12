#!/usr/bin/env python3
"""Heavy eng rebuild of portal / hub / commander (NOT the operator path).

Operator-first (recommended for non-code users)::

    $env:PYTHONPATH = "."
    python -m wildfire_front operator
    python -m wildfire_front operator do --all

This script rebuilds metrics + PORTAL + commander and opens browsers::

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
    print("\n=== WildfireFrontDynamics — SHOW ALL (eng portal rebuild) ===\n", flush=True)
    print(
        "Nota: camino operario (preferido) → python -m wildfire_front operator\n"
        "      ensayo 4 actos → python -m wildfire_front operator do --all\n"
        "      este script es rebuild pesado de portal/hub/commander.\n",
        flush=True,
    )
    ok = True
    # Operator board first (fast; does not replace show_all rebuild)
    ok &= run(
        [sys.executable, "-m", "wildfire_front", "operator", "checklist"],
        timeout=60,
    )
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
                    "docs/OPERATOR_UX_LOOP_LOG.md",
                ],
                "operator": "python -m wildfire_front operator",
                "message": (
                    "Portal/commander abiertos. Camino operario: "
                    "python -m wildfire_front operator (no este script)."
                ),
            },
            indent=2,
        ),
        flush=True,
    )
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
