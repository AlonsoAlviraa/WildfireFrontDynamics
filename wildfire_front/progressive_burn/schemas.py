"""PSB schemas, honesty constants, artifact names."""

from __future__ import annotations

from typing import Final

PRODUCT_SCHEMA: Final = "progressive_synthetic_burn_v1"
OPS_METHOD: Final = "proxy_ros_from_synthetic_stages"

ATTRIBUTION_REDIAM: Final = (
    "Fuente: REDIAM — Junta de Andalucía. "
    "Uso libre con mención de autores y propietarios."
)

HONESTY_LIMITATIONS: Final[tuple[str, ...]] = (
    "synthetic_observation",
    "not_real_lwir",
    "not_official_intermediate_o2",
    "no_tactical_vp",
    "proxy_synthetic",
)

REQUIRED_STAGE_PROPS: Final[tuple[str, ...]] = (
    "stage_index",
    "n_stages",
    "synthetic",
    "not_real_lwir",
    "not_official_intermediate_o2",
    "source_final",
    "attribution",
)

# Pack-relative paths under progressive/
ARTIFACT_TIMELINE = "progressive/timeline_progressive.geojson"
ARTIFACT_METRICS = "progressive/metrics_progressive.json"
ARTIFACT_SCORECARD = "progressive/scorecard_progressive.json"
ARTIFACT_FRONT_DYNAMICS = "progressive/front_dynamics_progressive.json"
ARTIFACT_BRIEF = "progressive/brief_progressive_addendum.md"

N_STAGES_MIN = 3
N_STAGES_MAX = 64
N_STAGES_DEFAULT = 12

# Fraction band: |f_actual - f_target| <= max(ABS, REL * f_target)
FRACTION_EPS_ABS = 0.02
FRACTION_EPS_REL = 0.05

# KD13 micro-islands (ha in equal-area CRS)
MIN_COMPONENT_AREA_HA_DEFAULT = 2.0

MAP_BANNER_ES = "Crecimiento sintético — perímetro final oficial REDIAM"
