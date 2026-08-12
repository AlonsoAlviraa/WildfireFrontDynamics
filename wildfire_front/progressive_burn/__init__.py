"""Progressive Synthetic Burn (PSB) — reverse-growth stages under official final perimeter.

Honesty: stages are synthetic, not LWIR, not official intermediate O2, no tactical Vp.
Terminal stage is an exact copy of the official geometry (REDIAM / pack).
"""

from .pipeline import (
    ProgressiveBurnConfig,
    StageRecord,
    StageSequence,
    build_stage_sequence,
    multihorizon_from_stage_sequence,
)
from .schemas import (
    ATTRIBUTION_REDIAM,
    HONESTY_LIMITATIONS,
    PRODUCT_SCHEMA,
    REQUIRED_STAGE_PROPS,
)

__all__ = [
    "ATTRIBUTION_REDIAM",
    "HONESTY_LIMITATIONS",
    "PRODUCT_SCHEMA",
    "REQUIRED_STAGE_PROPS",
    "ProgressiveBurnConfig",
    "StageRecord",
    "StageSequence",
    "build_stage_sequence",
    "multihorizon_from_stage_sequence",
]
