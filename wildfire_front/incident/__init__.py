"""Incident runtime: live folder watch → front dynamics → operator outbox.

Product id: ``incident_runtime_v1``

Not validated tactical dispatch. Geometry-first observed front + ROS guidance.
"""

from __future__ import annotations

from .doctor import doctor_incident, read_incident_status
from .pipeline import IncidentConfig, process_incident_once, publish_emergency_layers
from .state import IncidentState, load_state, save_state
from .watch import run_incident_watch

__all__ = [
    "IncidentConfig",
    "IncidentState",
    "load_state",
    "save_state",
    "process_incident_once",
    "publish_emergency_layers",
    "run_incident_watch",
    "doctor_incident",
    "read_incident_status",
]
