"""Stable sample identity adapted from DetectorDeIncendios.

Original source:
https://github.com/AlonsoAlviraa/DetectorDeIncendios/blob/main/src/data_prep/sample_identity.py
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

_SAFE_PATTERN = re.compile(r"[^a-zA-Z0-9_-]+")


def _slugify(value: str, fallback: str) -> str:
    cleaned = _SAFE_PATTERN.sub("_", value.strip()).strip("_")
    return cleaned[:48] or fallback


def sha256_of_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Hash a source file without loading it entirely into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def build_observation_id(event_id: str, sensor_id: str, observed_at: str, source_sha256: str = "") -> str:
    """Build a stable, portable observation identifier."""

    event = _slugify(event_id, "unknown_event")
    sensor = _slugify(sensor_id, "unknown_sensor")
    entropy_source = f"{observed_at}|{source_sha256}"
    entropy = hashlib.sha256(entropy_source.encode("utf-8")).hexdigest()[:12]
    return f"{event}__{sensor}__{entropy}"
