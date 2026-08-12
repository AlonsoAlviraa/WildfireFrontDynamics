"""Minimal V&V scorecard sidecar (Agent B W2 / B5).

Eng-only stub: stable schema + rails/non-claims. No field-validated metrics,
no GO_Q true, no field_ops fusion ON. Paths resolve through decide allowlist
(``PathNotAllowedError`` fail-closed).

Documented eng entry: ``python scripts/run_vv_sidecar.py --work-dir <dir>``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .decide_service import PathNotAllowedError, _as_path, _is_under

VV_SCORECARD_SCHEMA = "wfd_vv_scorecard_stub_v1"
VV_SCORECARD_FILENAME = "vv_scorecard.json"
VV_STATUS_ENG_STUB = "eng_stub"

NON_CLAIMS: tuple[str, ...] = (
    "not_field_ops_validated",
    "not_tactical_dispatch",
    "not_GO_Q_complete",
    "not_field_ops_ml_fusion_ON",
    "not_real_holdout_metrics",
    "not_field_grade_A_claim",
    "eng_only_stub",
)

DEFAULT_RAILS: dict[str, Any] = {
    "GO_Q": "partial",
    "field_ops_fusion": "OFF",
    "ml_product_go": "lab_only",
    "FREEZE_ML_AND_REQUEST_DATA": True,
}


class VvSidecarError(ValueError):
    """Invalid V&V sidecar operation."""


def resolve_work_dir(
    work_dir: str | Path,
    *,
    base: Path | None = None,
    include_repo_root: bool = True,
) -> Path:
    """Resolve work_dir under decide allowlist roots; fail closed outside."""
    resolved = _as_path(
        work_dir,
        base=base,
        include_repo_root=include_repo_root,
    )
    if resolved is None:
        raise PathNotAllowedError(f"work_dir required for V&V sidecar: {work_dir!r}")
    return resolved


def scorecard_path(work_dir: Path) -> Path:
    return Path(work_dir) / VV_SCORECARD_FILENAME


def _now_utc() -> str:
    return datetime.now(UTC).isoformat()


def build_vv_scorecard_stub(
    *,
    event_id: str | None = None,
    work_dir: str | Path | None = None,
    notes: str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build eng-only V&V scorecard dict (no field metrics invented)."""
    card: dict[str, Any] = {
        "schema": VV_SCORECARD_SCHEMA,
        "status": VV_STATUS_ENG_STUB,
        "eng_stub": True,
        "event_id": event_id or "vv_eng",
        "built_at_utc": _now_utc(),
        "rails": dict(DEFAULT_RAILS),
        "non_claims": list(NON_CLAIMS),
        "checks": [
            {
                "id": "schema_present",
                "ok": True,
                "detail": "stable schema id for Agent A/UI later",
            },
            {
                "id": "rails_go_q_partial",
                "ok": True,
                "detail": "GO_Q remains partial until human acta",
            },
            {
                "id": "rails_fusion_off",
                "ok": True,
                "detail": "field_ops ML fusion OFF",
            },
            {
                "id": "no_field_metrics",
                "ok": True,
                "detail": "stub has no IoU/ROS/grade field claims",
            },
        ],
        "metrics": {
            # Explicit empties — never invent field-sounding numbers
            "field_iou": None,
            "field_ros": None,
            "field_grade": None,
            "note": "metrics intentionally null in eng_stub",
        },
        "notes": notes
        or (
            "V&V eng stub only. Not a field scorecard. "
            "Run real evals separately; do not promote to GO_Q or fusion."
        ),
    }
    if work_dir is not None:
        card["work_dir"] = str(work_dir)
    if extra:
        # Shallow merge of non-reserved keys only
        reserved = {
            "schema",
            "status",
            "eng_stub",
            "rails",
            "non_claims",
            "metrics",
        }
        for k, v in extra.items():
            if k not in reserved:
                card[k] = v
    return card


def write_vv_scorecard(
    work_dir: str | Path,
    scorecard: Mapping[str, Any] | None = None,
    *,
    base: Path | None = None,
    include_repo_root: bool = True,
    event_id: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Write V&V scorecard JSON under allowlisted work_dir. Returns the card."""
    work = resolve_work_dir(work_dir, base=base, include_repo_root=include_repo_root)
    work.mkdir(parents=True, exist_ok=True)
    out = scorecard_path(work)
    if not _is_under(out, work):
        raise PathNotAllowedError(f"V&V scorecard path escapes work_dir: {out}")
    if scorecard is None:
        card = build_vv_scorecard_stub(event_id=event_id, work_dir=work, notes=notes)
    else:
        card = dict(scorecard)
        if card.get("schema") != VV_SCORECARD_SCHEMA:
            raise VvSidecarError(
                f"scorecard schema must be {VV_SCORECARD_SCHEMA!r}, got {card.get('schema')!r}"
            )
        if not card.get("eng_stub"):
            raise VvSidecarError("scorecard must set eng_stub=true (no field claims)")
    # Harden rails/non-claims on every write
    card["rails"] = {
        **DEFAULT_RAILS,
        **(card.get("rails") if isinstance(card.get("rails"), dict) else {}),
        "GO_Q": "partial",
        "field_ops_fusion": "OFF",
    }
    claims = list(card.get("non_claims") or [])
    for c in NON_CLAIMS:
        if c not in claims:
            claims.append(c)
    card["non_claims"] = claims
    card["status"] = card.get("status") or VV_STATUS_ENG_STUB
    card["eng_stub"] = True
    card["schema"] = VV_SCORECARD_SCHEMA
    card["work_dir"] = str(work)
    text = json.dumps(card, indent=2, ensure_ascii=False, default=str) + "\n"
    out.write_text(text, encoding="utf-8")
    return card


def load_vv_scorecard(
    work_dir: str | Path,
    *,
    base: Path | None = None,
    include_repo_root: bool = True,
) -> dict[str, Any]:
    """Load V&V scorecard from allowlisted work_dir."""
    work = resolve_work_dir(work_dir, base=base, include_repo_root=include_repo_root)
    path = scorecard_path(work)
    if not _is_under(path, work):
        raise PathNotAllowedError(f"V&V scorecard path escapes work_dir: {path}")
    if not path.is_file():
        raise FileNotFoundError(f"missing {VV_SCORECARD_FILENAME} in {work}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise VvSidecarError("scorecard must be a JSON object")
    return data


def run_vv_sidecar(
    work_dir: str | Path,
    *,
    base: Path | None = None,
    include_repo_root: bool = True,
    event_id: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Primary eng entry: build stub, write, return card (same as command path)."""
    return write_vv_scorecard(
        work_dir,
        None,
        base=base,
        include_repo_root=include_repo_root,
        event_id=event_id,
        notes=notes,
    )
