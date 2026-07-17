"""Persistent incident state for the live runtime."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


PRODUCT_ID = "incident_runtime_v1"
STATE_FILENAME = "incident_state.json"


@dataclass
class FrameRecord:
    """One accepted (or seen) inbox frame."""

    path: str
    sha256: str
    stem: str
    accepted_at_utc: str
    size_bytes: int
    status: str = "staged"  # staged | processed | skipped
    reason: str = ""


@dataclass
class IncidentState:
    """Machine-readable state written to outbox after each update."""

    product: str = PRODUCT_ID
    event_id: str = ""
    sensor_id: str = ""
    created_at_utc: str = ""
    updated_at_utc: str = ""
    n_frames_seen: int = 0
    n_frames_staged: int = 0
    n_updates: int = 0
    last_latency_s: float | None = None
    last_error: str | None = None
    quality_grade: str | None = None
    quality_label_es: str | None = None
    primary_ros_m_min: float | None = None
    speed_n_observable: int | None = None
    area_ha_max: float | None = None
    speed_vs_ref_ratio: float | None = None
    engine: str | None = None
    disclaimers: list[str] = field(
        default_factory=lambda: [
            "observed_front_only",
            "not_official_perimeter",
            "not_validated_tactical_dispatch",
            "envelope_is_extrapolated_guidance",
        ]
    )
    frames: list[dict[str, Any]] = field(default_factory=list)
    artifacts: dict[str, str] = field(default_factory=dict)
    not_a_product: str = "validated_tactical_dispatch"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IncidentState:
        from dataclasses import fields as dc_fields

        known = {f.name for f in dc_fields(cls)}
        kwargs = {k: v for k, v in data.items() if k in known}
        return cls(**kwargs)

    def upsert_frame(self, rec: FrameRecord) -> None:
        by_sha = {f.get("sha256"): i for i, f in enumerate(self.frames)}
        payload = asdict(rec)
        if rec.sha256 in by_sha:
            self.frames[by_sha[rec.sha256]] = payload
        else:
            self.frames.append(payload)
        self.n_frames_seen = len(self.frames)
        self.n_frames_staged = sum(1 for f in self.frames if f.get("status") == "staged")


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_state(path: Path) -> IncidentState | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return IncidentState.from_dict(data)


def save_state(state: IncidentState, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    state.updated_at_utc = utc_now_iso()
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state.to_dict(), indent=2), encoding="utf-8")
    tmp.replace(path)
    return path
