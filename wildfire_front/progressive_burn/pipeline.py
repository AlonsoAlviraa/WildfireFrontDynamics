"""PSB pipeline: final geometry → StageSequence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from shapely.geometry.base import BaseGeometry

from .engines import run_area_fraction_engine, run_buffer_rings_engine
from .geometry import (
    area_ha,
    as_multipolygon,
    component_polygons,
    ensure_valid,
    reproject,
)
from .schedules import fraction_schedule, uniform_times_s, validate_n_stages
from .schemas import (
    ATTRIBUTION_REDIAM,
    MIN_COMPONENT_AREA_HA_DEFAULT,
    N_STAGES_DEFAULT,
    PRODUCT_SCHEMA,
)


@dataclass(frozen=True)
class ProgressiveBurnConfig:
    n_stages: int = N_STAGES_DEFAULT
    engine: str = "area_fraction"  # area_fraction | buffer_rings
    schedule: str = "sqrt"
    total_duration_s: float = 86_400.0
    metric_crs: str = "EPSG:6933"
    source_crs: str = "EPSG:4326"
    seed: int = 0
    min_area_ha: float = 0.01
    min_component_area_ha: float = MIN_COMPONENT_AREA_HA_DEFAULT
    custom_fractions: tuple[float, ...] | None = None
    source_final: str = "REDIAM"
    codigo: str | None = None
    attribution: str = ATTRIBUTION_REDIAM

    def validated(self) -> ProgressiveBurnConfig:
        validate_n_stages(self.n_stages)
        eng = self.engine.strip().lower()
        if eng not in ("area_fraction", "buffer_rings"):
            raise ValueError(f"unsupported engine {self.engine!r} (v1: area_fraction|buffer_rings)")
        if self.total_duration_s <= 0:
            raise ValueError("total_duration_s must be positive")
        return self


@dataclass
class StageRecord:
    stage_index: int
    n_stages: int
    geom_metric: BaseGeometry
    area_fraction_target: float
    area_fraction_actual: float
    area_ha: float
    time_s: float
    dt_s_to_next: float
    engine: str
    method: str
    partial_reasons: list[str] = field(default_factory=list)
    synthetic: bool = True
    not_real_lwir: bool = True
    not_official_intermediate_o2: bool = True
    source_final: str = "REDIAM"
    codigo: str | None = None
    attribution: str = ATTRIBUTION_REDIAM
    time_is_assumed: bool = True

    def feature_props(self) -> dict[str, Any]:
        return {
            "stage_index": self.stage_index,
            "n_stages": self.n_stages,
            "area_fraction_target": self.area_fraction_target,
            "area_fraction_actual": self.area_fraction_actual,
            "area_ha": self.area_ha,
            "time_s": self.time_s,
            "dt_s_to_next": self.dt_s_to_next,
            "engine": self.engine,
            "method": self.method,
            "partial_reasons": list(self.partial_reasons),
            "synthetic": True,
            "not_real_lwir": True,
            "not_official_intermediate_o2": True,
            "source_final": self.source_final,
            "codigo": self.codigo,
            "attribution": self.attribution,
            "time_is_assumed": True,
            "layer_role": "synthetic_stage",
        }


@dataclass
class StageSequence:
    schema: str
    config: ProgressiveBurnConfig
    stages: list[StageRecord]
    final_metric: BaseGeometry
    final_area_ha: float
    final_geom_type: str
    final_n_parts: int
    fractions: list[float]
    engine_name: str
    all_partial_reasons: list[str] = field(default_factory=list)

    @property
    def n_stages(self) -> int:
        return len(self.stages)


def build_stage_sequence(
    final_geom,
    config: ProgressiveBurnConfig | None = None,
    *,
    source_crs: str | None = None,
) -> StageSequence:
    """Build nested progressive stages; terminal is exact copy of final in metric CRS."""
    cfg = (config or ProgressiveBurnConfig()).validated()
    src = source_crs or cfg.source_crs

    raw = ensure_valid(final_geom)
    if (
        area_ha(reproject(raw, src, cfg.metric_crs) if src != cfg.metric_crs else raw)
        < cfg.min_area_ha
    ):
        # Area in source CRS may be degrees² — always work metric
        pass

    final_metric = reproject(raw, src, cfg.metric_crs) if src != cfg.metric_crs else raw
    final_metric = ensure_valid(final_metric)
    a_ha = area_ha(final_metric)
    if a_ha < cfg.min_area_ha:
        raise ValueError(f"final area {a_ha:.6f} ha below min_area_ha={cfg.min_area_ha}")

    mp = as_multipolygon(final_metric)
    n_parts = len(component_polygons(mp))
    geom_type = final_metric.geom_type

    n = cfg.n_stages
    eng = cfg.engine.strip().lower()
    times = uniform_times_s(n, cfg.total_duration_s)

    if eng == "area_fraction":
        fracs = fraction_schedule(cfg.schedule, n, custom=cfg.custom_fractions)
        geoms, methods, reasons_list = run_area_fraction_engine(
            final_metric,
            fracs,
            min_component_area_ha=cfg.min_component_area_ha,
        )
    else:
        fracs = fraction_schedule("linear", n)  # induced areas; linear labels only
        geoms, methods, reasons_list = run_buffer_rings_engine(
            final_metric,
            n,
            min_component_area_ha=cfg.min_component_area_ha,
        )
        # Update actual fractions later

    # Force terminal exact identity to final_metric
    geoms[-1] = ensure_valid(final_metric)
    methods[-1] = "terminal_exact"

    stages: list[StageRecord] = []
    all_reasons: list[str] = []
    a_f = float(final_metric.area)
    for i in range(n):
        g = geoms[i]
        a_act = float(g.area) if g is not None and not g.is_empty else 0.0
        f_act = a_act / a_f if a_f > 0 else 0.0
        f_tgt = fracs[i] if eng == "area_fraction" else f_act
        if i == n - 1:
            f_tgt = 1.0
            f_act = 1.0
        dt = (times[i + 1] - times[i]) if i < n - 1 else 0.0
        reasons = list(reasons_list[i]) if i < len(reasons_list) else []
        for r in reasons:
            if r not in all_reasons:
                all_reasons.append(r)
        stages.append(
            StageRecord(
                stage_index=i,
                n_stages=n,
                geom_metric=g,
                area_fraction_target=float(f_tgt),
                area_fraction_actual=float(f_act),
                area_ha=a_act / 10_000.0,
                time_s=float(times[i]),
                dt_s_to_next=float(dt),
                engine=eng,
                method=methods[i] if i < len(methods) else eng,
                partial_reasons=reasons,
                source_final=cfg.source_final,
                codigo=cfg.codigo,
                attribution=cfg.attribution,
            )
        )

    return StageSequence(
        schema=PRODUCT_SCHEMA,
        config=cfg,
        stages=stages,
        final_metric=final_metric,
        final_area_ha=a_ha,
        final_geom_type=geom_type,
        final_n_parts=n_parts,
        fractions=list(fracs),
        engine_name=eng,
        all_partial_reasons=all_reasons,
    )
