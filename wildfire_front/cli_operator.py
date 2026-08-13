"""Operator / teach / show / demo-third-party CLI for H1 12-min rehearsal.

Rails: decision-support only. GO_Q stays partial (AMARILLO) until a human
third-party acta is recorded. field_ops ML live fusion follows the catalog
rail (ON ≠ GO_Q complete ≠ despacho).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import webbrowser
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from .product.policy import field_ops_ml_live_fusion_rail, get_policy

AddGlobalFlags = Callable[[argparse.ArgumentParser], None]

# Repo root: wildfire_front/..
_ROOT = Path(__file__).resolve().parents[1]


def _repo_root() -> Path:
    return _ROOT


def _rel(path: Path, root: Path | None = None) -> str:
    root = root or _repo_root()
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def rails_snapshot() -> dict[str, Any]:
    """Honest product rails for the operator board (not a GO_Q flip).

    Fusion is derived from ``field_ops_ml_live_fusion_rail()`` so the hub
    cannot drift from the catalog / ``check_release_flags`` stamp.
    """
    return {
        "GO_MES": True,
        "GO_Q": "partial",
        "GO_Q_semaforo": "AMARILLO",
        "go_q_met": False,
        "go_q_note": "Needs human third-party demo + signed acta (eng cannot close GO_Q)",
        "field_ops_fusion": field_ops_ml_live_fusion_rail(),
        "ml_product_go": "lab_only",
        "disclaimers": [
            "not_validated_tactical_dispatch",
            "ABSTAIN_is_a_feature",
            "replay_ok_is_not_third_party_authenticity",
        ],
    }


def _fusion_on_kill() -> str:
    pol = get_policy("field_ops")
    cap = float(getattr(pol, "ml_live_max_weight", 0.20))
    abstain = float(getattr(pol, "ml_live_abstain_below", 0.45))
    return (
        f"Do not sell fusion ON (capped {cap:.2f} / abstain {abstain:.2f}) "
        "as GO_Q / despacho / field GO"
    )


def honest_kill_list(rails: dict[str, Any] | None = None) -> list[str]:
    """Kill list derived from the live fusion rail — cannot drift from stamp."""
    snap = rails or rails_snapshot()
    fusion = str(snap.get("field_ops_fusion") or field_ops_ml_live_fusion_rail()).upper()
    if fusion == "ON":
        fusion_kill = _fusion_on_kill()
    else:
        fusion_kill = "No field_ops ML live fusion ON"
    return [
        fusion_kill,
        "No inventar ROS",
        "No inventar tercero / no firmar acta vacía",
        "No marcar GO_Q complete desde eng",
        "No go_q_met true desde eng",
        "No IoU = ROS",
        "replay_ok ≠ autenticidad de tercero",
    ]


def build_checklist(*, root: Path | None = None) -> dict[str, Any]:
    root = root or _repo_root()
    checks = [
        {
            "id": "cheatsheet",
            "path": "docs/CHEATSHEET_DEMO_12MIN.md",
            "ok": (root / "docs/CHEATSHEET_DEMO_12MIN.md").is_file(),
        },
        {
            "id": "h1_runbook",
            "path": "docs/H1_GO_Q_RUNBOOK.md",
            "ok": (root / "docs/H1_GO_Q_RUNBOOK.md").is_file(),
        },
        {
            "id": "pilot_fixtures",
            "path": "tests/fixtures/pilot/pilot_sites.json",
            "ok": (root / "tests/fixtures/pilot/pilot_sites.json").is_file(),
        },
        {
            "id": "demo_multi_ccaa_script",
            "path": "scripts/build_demo_multi_ccaa.py",
            "ok": (root / "scripts/build_demo_multi_ccaa.py").is_file(),
        },
        {
            "id": "pilot_honesty_script",
            "path": "scripts/run_pilot_honesty_card.py",
            "ok": (root / "scripts/run_pilot_honesty_card.py").is_file(),
        },
        {
            "id": "decide_module",
            "path": "wildfire_front/product/decide_service.py",
            "ok": (root / "wildfire_front/product/decide_service.py").is_file(),
        },
        {
            "id": "acta_template_or_draft",
            "path": "docs/ACTA_DEMO_TERCERO_TEMPLATE.md|docs/actas/ACTA_DEMO_PENDING_HUMAN.md",
            "ok": (root / "docs/ACTA_DEMO_TERCERO_TEMPLATE.md").is_file()
            or (root / "docs/actas/ACTA_DEMO_PENDING_HUMAN.md").is_file(),
        },
    ]
    n_ok = sum(1 for c in checks if c["ok"])
    rails = rails_snapshot()
    return {
        "schema": "wfd_operator_checklist_v1",
        "product": "operator_hub",
        "eng_prep_ok": n_ok == len(checks),
        "eng_prep": f"{n_ok}/{len(checks)}",
        "checks": checks,
        "rails": rails,
        "go_q_met": False,
        "semaforo": "AMARILLO",
        "next": [
            "python -m wildfire_front operator do --act 1",
            "python -m wildfire_front operator do --act 2",
            "python -m wildfire_front operator do --act 3",
            "python -m wildfire_front operator do --act 4",
            "After real third-party demo: python scripts/record_h1_demo_complete.py --acta <signed>",
        ],
        "kill_list": honest_kill_list(rails),
    }
