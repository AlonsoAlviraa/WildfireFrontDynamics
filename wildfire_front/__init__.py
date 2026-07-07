"""Wildfire Front Dynamics MVP."""

from .models import (
    FrontObservation,
    GeometrySpeedConfig,
    GeometrySpeedResult,
    ScenarioConfig,
    SpeedEstimate,
)

__all__ = [
    "FrontObservation",
    "GeometrySpeedConfig",
    "GeometrySpeedResult",
    "ScenarioConfig",
    "SpeedEstimate",
    "__version__",
]
__version__ = "0.1.0"
