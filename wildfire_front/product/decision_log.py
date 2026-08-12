"""Decision-log + ACK sidecar under allowlisted work_dir (Agent B W2 / B4).

Filesystem-only append/read/ACK. Every work_dir is resolved through the same
path allowlist as ``decide_service`` (``PathNotAllowedError`` fail-closed).

Does not flip GO_Q or field_ops fusion. Not a tactical dispatch journal.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .decide_service import PathNotAllowedError, _as_path, _is_under

DECISION_LOG_SCHEMA = "wfd_decision_log_v1"
DECISION_ENTRY_SCHEMA = "wfd_decision_log_entry_v1"
DECISION_LOG_FILENAME = "decision_log.jsonl"

# Core fields always present on a log entry (stable contract for Agent A UI later).
CORE_DECISION_FIELDS = (
    "decision_id",
    "decision",
    "event_id",
    "confidence_pred",
    "built_at_utc",
    "output_hash",
)


class UnknownDecisionIdError(ValueError):
    """ACK or load for a decision_id that is not in the work_dir log."""


class DecisionLogError(ValueError):
    """Invalid decision-log operation (schema / missing payload)."""


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
        raise PathNotAllowedError(f"work_dir required for decision log: {work_dir!r}")
    return resolved


def log_file_path(work_dir: Path) -> Path:
    return Path(work_dir) / DECISION_LOG_FILENAME


def _now_utc() -> str:
    return datetime.now(UTC).isoformat()


def _ensure_work_dir(work: Path) -> None:
    work.mkdir(parents=True, exist_ok=True)


def _entry_from_decision(
    decision: Mapping[str, Any],
    *,
    decision_id: str | None = None,
    operator: str | None = None,
) -> dict[str, Any]:
    if not isinstance(decision, Mapping) or not decision:
        raise DecisionLogError("decision payload must be a non-empty mapping")
    dec = str(decision.get("decision") or "ABSTAIN")
    event_id = str(decision.get("event_id") or "decision")
    conf = decision.get("confidence_pred")
    conf_f: float | None = float(conf) if isinstance(conf, (int, float)) else None
    audit = decision.get("audit")
    audit_m: Mapping[str, Any] = audit if isinstance(audit, Mapping) else {}
    output_hash = audit_m.get("output_hash") or decision.get("output_hash")
    built = decision.get("built_at_utc") or _now_utc()
    did = decision_id or str(uuid.uuid4())
    entry: dict[str, Any] = {
        "schema": DECISION_ENTRY_SCHEMA,
        "log_schema": DECISION_LOG_SCHEMA,
        "decision_id": did,
        "decision": dec,
        "event_id": event_id,
        "confidence_pred": conf_f,
        "confidence_pred_label": decision.get("confidence_pred_label"),
        "built_at_utc": built,
        "logged_at_utc": _now_utc(),
        "output_hash": output_hash,
        "input_hash": audit_m.get("input_hash"),
        "api_version": decision.get("api_version"),
        "product_id": decision.get("product_id") or "fire_decision_card",
        "operator": operator,
        "ack": None,
        "disclaimers": list(decision.get("disclaimers") or [])[:6],
        # Rails snapshot at log time (honesty — not a gate flip)
        "rails": {
            "GO_Q": "partial",
            "field_ops_fusion": "ON",
            "not_tactical_dispatch": True,
        },
    }
    return entry


def _read_entries(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    entries: list[dict[str, Any]] = []
    text = path.read_text(encoding="utf-8")
    for line_no, line in enumerate(text.splitlines(), start=1):
        raw = line.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise DecisionLogError(f"corrupt decision_log line {line_no}: {exc}") from exc
        if isinstance(obj, dict):
            entries.append(obj)
    return entries


def _write_entries(path: Path, entries: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(e, ensure_ascii=False, default=str) for e in entries]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def append_decision(
    work_dir: str | Path,
    decision: Mapping[str, Any],
    *,
    base: Path | None = None,
    include_repo_root: bool = True,
    operator: str | None = None,
    decision_id: str | None = None,
) -> dict[str, Any]:
    """Append a decision entry under allowlisted work_dir. Returns the entry."""
    work = resolve_work_dir(work_dir, base=base, include_repo_root=include_repo_root)
    _ensure_work_dir(work)
    # Defense: log file must stay under the resolved work dir
    log_path = log_file_path(work)
    if not _is_under(log_path, work):
        raise PathNotAllowedError(f"decision log path escapes work_dir: {log_path}")
    entry = _entry_from_decision(decision, decision_id=decision_id, operator=operator)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    return entry


def load_decision_log(
    work_dir: str | Path,
    *,
    base: Path | None = None,
    include_repo_root: bool = True,
) -> list[dict[str, Any]]:
    """Load all decision-log entries from allowlisted work_dir (oldest first)."""
    work = resolve_work_dir(work_dir, base=base, include_repo_root=include_repo_root)
    return _read_entries(log_file_path(work))


def get_decision(
    work_dir: str | Path,
    decision_id: str,
    *,
    base: Path | None = None,
    include_repo_root: bool = True,
) -> dict[str, Any] | None:
    """Return the latest entry for decision_id, or None if missing."""
    if not decision_id:
        raise DecisionLogError("decision_id required")
    entries = load_decision_log(work_dir, base=base, include_repo_root=include_repo_root)
    found: dict[str, Any] | None = None
    for e in entries:
        if str(e.get("decision_id") or "") == str(decision_id):
            found = e
    return found


def ack_decision(
    work_dir: str | Path,
    decision_id: str,
    *,
    operator: str | None = None,
    note: str | None = None,
    base: Path | None = None,
    include_repo_root: bool = True,
) -> dict[str, Any]:
    """Attach ACK to an existing decision id; fail closed if unknown.

    Rewrites the JSONL sidecar so the entry reloads with ``ack`` populated.
    """
    if not decision_id:
        raise DecisionLogError("decision_id required for ACK")
    work = resolve_work_dir(work_dir, base=base, include_repo_root=include_repo_root)
    log_path = log_file_path(work)
    if not _is_under(log_path, work):
        raise PathNotAllowedError(f"decision log path escapes work_dir: {log_path}")
    entries = _read_entries(log_path)
    idx = None
    for i, e in enumerate(entries):
        if str(e.get("decision_id") or "") == str(decision_id):
            idx = i
    if idx is None:
        raise UnknownDecisionIdError(f"unknown decision_id for ACK (fail closed): {decision_id!r}")
    entry = dict(entries[idx])
    entry["ack"] = {
        "acked": True,
        "acked_at_utc": _now_utc(),
        "operator": operator,
        "note": note,
    }
    entries[idx] = entry
    _write_entries(log_path, entries)
    return entry
