"""Organism / channel decision policies (thresholds for GO/HOLD/ABSTAIN).

Dream M2.10: GEACAM-style field_ops ≠ research_open ≠ default.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CATALOG = REPO_ROOT / "config" / "decision_policies.json"


@dataclass(frozen=True)
class DecisionPolicy:
    id: str = "default"
    label: str = "Default"
    require_ops_for_go: bool = False
    abstain_below: float = 0.20
    go_ops_min: float = 0.55
    go_ops_open_min: float = 0.45
    hold_open_min: float = 0.35
    hold_ml_only_min: float = 0.50
    allow_ml_only_hold: bool = True
    allow_open_only_hold: bool = True
    min_available_sources: int = 1
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Historical product behavior (must stay bit-stable for default)
LEGACY_DEFAULT = DecisionPolicy(
    id="default",
    label="Default (historical product thresholds)",
    require_ops_for_go=False,
    abstain_below=0.20,
    go_ops_min=0.55,
    go_ops_open_min=0.45,
    hold_open_min=0.35,
    hold_ml_only_min=0.50,
    allow_ml_only_hold=True,
    allow_open_only_hold=True,
    min_available_sources=1,
    notes="Built-in fallback if catalog missing.",
)


def _policy_from_mapping(data: Mapping[str, Any], *, fallback_id: str) -> DecisionPolicy:
    known = {f.name for f in fields(DecisionPolicy)}
    kwargs: dict[str, Any] = {}
    for k, v in data.items():
        if k in known:
            kwargs[k] = v
    if "id" not in kwargs:
        kwargs["id"] = fallback_id
    # merge with defaults for missing keys
    base = asdict(LEGACY_DEFAULT)
    base.update(kwargs)
    return DecisionPolicy(**base)


def load_policy_catalog(path: Path | str | None = None) -> dict[str, Any]:
    p = Path(path) if path else DEFAULT_CATALOG
    if not p.is_file():
        return {
            "schema": "decision_policies_v1",
            "default_policy": "default",
            "policies": {"default": LEGACY_DEFAULT.to_dict()},
        }
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "schema": "decision_policies_v1",
            "default_policy": "default",
            "policies": {"default": LEGACY_DEFAULT.to_dict()},
        }


def list_policies(path: Path | str | None = None) -> list[dict[str, Any]]:
    cat = load_policy_catalog(path)
    policies = cat.get("policies") or {}
    out = []
    for pid, pdata in policies.items():
        if isinstance(pdata, dict):
            out.append(
                {
                    "id": pdata.get("id") or pid,
                    "label": pdata.get("label") or pid,
                    "require_ops_for_go": pdata.get("require_ops_for_go"),
                    "notes": pdata.get("notes"),
                }
            )
    return out


def get_policy(
    policy_id: str | None = None,
    *,
    catalog_path: Path | str | None = None,
    overrides: Mapping[str, Any] | None = None,
) -> DecisionPolicy:
    """Resolve a named policy; unknown id falls back to default with notes."""
    cat = load_policy_catalog(catalog_path)
    default_id = str(cat.get("default_policy") or "default")
    pid = (policy_id or default_id).strip() or default_id
    policies = cat.get("policies") or {}
    raw = policies.get(pid)
    if not isinstance(raw, dict):
        raw = policies.get(default_id) or LEGACY_DEFAULT.to_dict()
        pol = _policy_from_mapping(raw if isinstance(raw, dict) else {}, fallback_id=default_id)
        # preserve requested id in notes if missing
        if pid not in policies:
            pol = DecisionPolicy(
                **{
                    **asdict(pol),
                    "notes": (pol.notes or "")
                    + f" [unknown policy_id={pid!r}; using {pol.id}]",
                }
            )
    else:
        pol = _policy_from_mapping(raw, fallback_id=pid)

    if overrides:
        data = asdict(pol)
        for k, v in overrides.items():
            if k in data and v is not None:
                data[k] = v
        pol = DecisionPolicy(**data)
    return pol
