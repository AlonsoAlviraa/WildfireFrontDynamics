"""Production product catalog: lab ML products + dual-rail ops boundary.

Dual-product rails (first-class, non-negotiable) — identity tied to
``product_facade`` (not a parallel product policy):
  · **lab_ml** — catalog ML products (default ``clm_ensemble_v34``); IoU / ECE only
  · **field_ops** — ``front_dynamics_v1`` (observed ROS); **not** ML, not loadable here

Invariants (sourced from ``product_facade.ProductRails`` / DEFAULT_RAILS):
  · IoU ≠ ROS (never mix scorecard primaries)
  · ``ml_product_go`` never auto-flips from catalog loaders
  · field_ops ML live fusion stays OFF (policy file; catalog does not enable it)
  · Default lab surface freezes **iter1_reject_only** (VAL thr; no same-holdout ECE thrash)

Facade wiring: ``load_predictor_for_product`` / ``load_lab_predictor`` are the
single entry points for ML predictor construction (features → calibrator →
rank/reject layers consume predictors from here; ops never enters this factory).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Literal

from wildfire_front.ml.product_facade import (
    DEFAULT_PRODUCT_ID,
    DEFAULT_RAILS,
    ITER1_LOCKED_REJECT_THR,
    OPS_PRODUCT_ID,
    PRODUCT_RAIL,
    RECOMMENDED_LAB_SURFACE,
    assert_lab_rails,
)

ROOT = Path(__file__).resolve().parents[2]

# ── Dual-product rails (lab ML vs field_ops) — identity from product_facade ─
ProductRail = Literal["lab_ml", "field_ops"]

# Single source of product identity: product_facade (clm_ensemble_v34 / front_dynamics_v1)
DEFAULT_LAB_PRODUCT: Final[str] = str(DEFAULT_PRODUCT_ID)
DEFAULT_OPS_PRODUCT: Final[str] = str(OPS_PRODUCT_ID)
DEFAULT_FALLBACK_ML_PRODUCT: Final[str] = "clm_v28"
DEFAULT_RESEARCH_ML_PRODUCT: Final[str] = "ndws_v21"

# Default lab surface freeze (VAL thr) — same string as product_facade / rank_reject
DEFAULT_LAB_SURFACE: Final[str] = str(RECOMMENDED_LAB_SURFACE)  # iter1_reject_only
LOCKED_REJECT_THR: Final[float] = float(ITER1_LOCKED_REJECT_THR)
_PRODUCT_FACADE: Final[str] = "wildfire_front.ml.product_facade"
_PIPELINE: Final[str] = "features→calibrator→rank/reject→scorecard"

# Honesty rails — human promote authorized 2026-08-05 (lab GO); no silent auto-flip;
# field fusion stays OFF (lab GO ≠ field fusion). Mirror fusion/IoU from DEFAULT_RAILS.
ML_PRODUCT_GO_DEFAULT: Final[bool] = True  # explicit promote; clm_ensemble_v34 lab product
ML_PRODUCT_GO_AUTO_FLIP: Final[bool] = False  # refuse silent thrash only (not the go value)
FIELD_OPS_ML_FUSION_DEFAULT: Final[bool] = bool(
    DEFAULT_RAILS.field_ops_allow_ml_live_in_fusion
)  # False
IOU_IS_NOT_ROS: Final[bool] = bool(DEFAULT_RAILS.iou_is_not_ros)  # True

# PR11 lab track guardrails — documentation kill-criteria only; no retrain, no fusion.
LAB_LARGER_UNET_DEFAULT_BET: Final[bool] = False
LAB_UNET_SCALE_KILL_DOC: Final[str] = "docs/design/LAB_UNET_SCALE_KILL_CRITERIA.md"

# Known ops product ids that must never resolve as ML predictors
_OPS_PRODUCT_ALIASES: Final[frozenset[str]] = frozenset(
    {
        str(OPS_PRODUCT_ID),
        "front_dynamics",
        "ops",
        "field_ops",
    }
)


class ProductBoundaryError(ValueError):
    """Raised when ops/field_ops ids are used on the ML lab product path."""


@dataclass(frozen=True)
class ProductSpec:
    id: str
    label: str
    domain: str
    manifest_path: Path
    weights_path: Path
    use_when: str
    not_for: str
    product_type: str = "single"  # single | ensemble
    member_paths: tuple[Path, ...] = field(default_factory=tuple)
    ensemble_mode: str = "mean_prob"
    # First-class rail: catalog products are always lab_ml (ops is not in products{})
    rail: ProductRail = "lab_ml"
    # Lab surface freeze (product_facade default); ops loaders never set this.
    recommended_lab_surface: str = DEFAULT_LAB_SURFACE

    def resolve_existing(self) -> tuple[bool, str]:
        if not self.manifest_path.is_file():
            return False, f"missing manifest: {self.manifest_path}"
        if self.product_type == "ensemble":
            if len(self.member_paths) < 2:
                return False, "ensemble needs >=2 members in manifest/catalog"
            missing = [str(p) for p in self.member_paths if not p.is_file()]
            if missing:
                return False, f"missing ensemble members: {missing}"
            return True, f"ok ({len(self.member_paths)} members)"
        if not self.weights_path.is_file():
            return False, f"missing weights: {self.weights_path}"
        return True, "ok"


def load_catalog(path: Path | None = None) -> dict[str, Any]:
    catalog_path = path or (ROOT / "models" / "catalog.json")
    return json.loads(catalog_path.read_text(encoding="utf-8"))


def _resolve_repo_path(rel: str | Path) -> Path:
    p = Path(rel)
    if p.is_absolute():
        return p
    return (ROOT / p).resolve()


def default_lab_product(catalog_path: Path | None = None) -> str:
    """Default lab ML product id (``clm_ensemble_v34`` via product_facade). Never ops."""
    data = load_catalog(catalog_path)
    pid = str(data.get("default_product") or DEFAULT_LAB_PRODUCT)
    if is_ops_product_id(pid, catalog_path):
        return DEFAULT_LAB_PRODUCT
    return pid


def default_lab_surface() -> str:
    """Default lab surface freeze: product_facade ``iter1_reject_only``."""
    return DEFAULT_LAB_SURFACE


def ops_product_id(catalog_path: Path | None = None) -> str:
    """Ops product id (``front_dynamics_v1``). Not an ML catalog product."""
    data = load_catalog(catalog_path)
    return str(data.get("ops_product") or DEFAULT_OPS_PRODUCT)


def is_ops_product_id(product_id: str, catalog_path: Path | None = None) -> bool:
    """True if id is the ops/field_ops rail (not ML; IoU ≠ ROS)."""
    pid = str(product_id).strip()
    if pid in _OPS_PRODUCT_ALIASES:
        return True
    try:
        return pid == ops_product_id(catalog_path)
    except (OSError, json.JSONDecodeError, TypeError):
        return pid == DEFAULT_OPS_PRODUCT


def product_rail_for(product_id: str, catalog_path: Path | None = None) -> ProductRail:
    """Map product id → dual-product rail (``lab_ml`` | ``field_ops``)."""
    if is_ops_product_id(product_id, catalog_path):
        return "field_ops"
    return "lab_ml"


def assert_ml_product_boundary(product_id: str, catalog_path: Path | None = None) -> None:
    """Refuse ops/field_ops ids on the ML predictor path (facade guard)."""
    if is_ops_product_id(product_id, catalog_path):
        lab = default_lab_product(catalog_path)
        ops = ops_product_id(catalog_path)
        raise ProductBoundaryError(
            f"product {product_id!r} is ops rail ({ops}), not ML. "
            f"Use lab product {lab!r}. IoU ≠ ROS; field_ops fusion OFF; "
            f"ml_product_go never auto-flips; surface={DEFAULT_LAB_SURFACE}."
        )


def dual_product_rails(catalog_path: Path | None = None) -> dict[str, Any]:
    """First-class dual-rail snapshot tied to product_facade DEFAULT_RAILS.

    Catalog inventory (products on disk) + facade product policy (surface,
    thr freeze, go/fusion rails). Does not read decision_policies.json
    (fusion stays OFF). Emits promoted ``ml_product_go`` True for lab product;
    never silent-auto-flips (``ml_product_go_auto_flip`` stays False).
    """
    data = load_catalog(catalog_path)
    lab = str(data.get("default_product") or DEFAULT_LAB_PRODUCT)
    if is_ops_product_id(lab, catalog_path):
        lab = DEFAULT_LAB_PRODUCT
    facade_rails = assert_lab_rails(DEFAULT_RAILS).as_dict()
    # Prefer facade default when already True; never clamp promoted go to false.
    ml_go = bool(DEFAULT_RAILS.ml_product_go) or ML_PRODUCT_GO_DEFAULT
    return {
        "schema": "wfd_dual_product_rails_v1",
        "lab_rail": str(PRODUCT_RAIL),  # lab_ml
        "ops_rail": "field_ops",
        "default_lab_product": lab,
        "fallback_ml_product": str(data.get("fallback_ml_product") or DEFAULT_FALLBACK_ML_PRODUCT),
        "research_ml_product": str(data.get("research_ml_product") or DEFAULT_RESEARCH_ML_PRODUCT),
        "emergency_ml_product": str(data.get("emergency_ml_product") or lab),
        "ops_product": str(data.get("ops_product") or DEFAULT_OPS_PRODUCT),
        "ops_is_ml": False,
        "ops_note": str(data.get("ops_note") or "Observed front ROS — front_dynamics_v1, not ML."),
        "iou_is_not_ros": IOU_IS_NOT_ROS,
        "ml_product_go": ml_go,
        "ml_product_go_auto_flip": ML_PRODUCT_GO_AUTO_FLIP,
        "field_ops_allow_ml_live_in_fusion": False,
        "field_ops_ml_fusion_default": FIELD_OPS_ML_FUSION_DEFAULT,
        "field_ops_ml_live_fusion": "OFF",
        "recommended_lab_surface": DEFAULT_LAB_SURFACE,
        "locked_reject_thr": LOCKED_REJECT_THR,
        "val_only_threshold_selection": True,
        "stop_ece_thrash_on_same_test": True,
        "tobarra_keep_reopen_forbidden": True,
        "pipeline": _PIPELINE,
        "product_facade": _PRODUCT_FACADE,
        "facade_rails": facade_rails,
        "ml_products": sorted((data.get("products") or {}).keys()),
        # PR11: larger U-Net never default; zero field fusion from lab scale experiments
        "lab_larger_unet_default_bet": LAB_LARGER_UNET_DEFAULT_BET,
        "lab_unet_scale_kill_doc": LAB_UNET_SCALE_KILL_DOC,
        "lab_scale_field_fusion_path": False,
    }


def get_product(product_id: str, catalog_path: Path | None = None) -> ProductSpec:
    assert_ml_product_boundary(product_id, catalog_path)
    data = load_catalog(catalog_path)
    products = data.get("products") or {}
    if product_id not in products:
        known = ", ".join(sorted(products))
        raise KeyError(f"Unknown product '{product_id}'. Known: {known}")
    p = products[product_id]
    manifest_path = (ROOT / p["manifest"]).resolve()
    weights_path = (ROOT / p["weights"]).resolve()

    product_type = str(p.get("product_type") or "single")
    ensemble_mode = str(p.get("ensemble_mode") or "mean_prob")
    members: list[Path] = []

    # Prefer members from product manifest if present
    if manifest_path.is_file():
        try:
            mdata = json.loads(manifest_path.read_text(encoding="utf-8"))
            if mdata.get("product_type") == "ensemble" or mdata.get("members"):
                product_type = "ensemble"
            ensemble_mode = str(mdata.get("ensemble_mode") or ensemble_mode)
            for rel in mdata.get("members") or []:
                members.append(_resolve_repo_path(rel))
        except (OSError, json.JSONDecodeError):
            pass

    if not members and p.get("members"):
        product_type = "ensemble"
        members = [_resolve_repo_path(rel) for rel in p["members"]]

    return ProductSpec(
        id=str(p["id"]),
        label=str(p["label"]),
        domain=str(p["domain"]),
        manifest_path=manifest_path,
        weights_path=weights_path,
        use_when=str(p.get("use_when", "")),
        not_for=str(p.get("not_for", "")),
        product_type=product_type,
        member_paths=tuple(members),
        ensemble_mode=ensemble_mode,
        rail="lab_ml",
        recommended_lab_surface=DEFAULT_LAB_SURFACE,
    )


def list_products(catalog_path: Path | None = None) -> list[dict[str, Any]]:
    data = load_catalog(catalog_path)
    out = []
    for pid in sorted(data.get("products") or {}):
        spec = get_product(pid, catalog_path)
        ok, msg = spec.resolve_existing()
        out.append(
            {
                "id": spec.id,
                "label": spec.label,
                "domain": spec.domain,
                "product_type": spec.product_type,
                "rail": spec.rail,
                "recommended_lab_surface": spec.recommended_lab_surface,
                "ready": ok,
                "status": msg,
                "manifest": str(spec.manifest_path),
                "weights": str(spec.weights_path),
                "members": [str(m) for m in spec.member_paths] if spec.member_paths else None,
                "ensemble_mode": spec.ensemble_mode if spec.product_type == "ensemble" else None,
                "use_when": spec.use_when,
                "not_for": spec.not_for,
            }
        )
    return out


def load_predictor_for_product(
    product_id: str,
    *,
    device: str | None = None,
    catalog_path: Path | None = None,
):
    """Factory: single-model or ensemble predictor for a **lab ML** catalog product.

    Facade layer entry for features → calibrator → rank/reject pipelines.
    Refuses ops/field_ops product ids (ops is ``front_dynamics_v1``, not ML).
    Does not set ``ml_product_go`` or enable field_ops fusion.
    Live conf/reject thr after load uses product_facade surface
    ``iter1_reject_only`` (see ``spread_predictor`` + ``ClmEnsembleV34Facade``).
    """
    from wildfire_front.ml.spread_predictor import EnsembleSpreadPredictor, SpreadPredictor

    assert_ml_product_boundary(product_id, catalog_path)
    # Seal dual-rail honesty at load time (no go auto-flip / fusion ON).
    assert_lab_rails(DEFAULT_RAILS)
    spec = get_product(product_id, catalog_path)
    ok, msg = spec.resolve_existing()
    if not ok:
        raise FileNotFoundError(f"Product {product_id} not ready: {msg}")

    if spec.product_type == "ensemble":
        return EnsembleSpreadPredictor.from_product_spec(spec, device=device)
    return SpreadPredictor.from_manifest(
        spec.manifest_path, weights_path=spec.weights_path, device=device
    )


def load_lab_predictor(
    product_id: str | None = None,
    *,
    device: str | None = None,
    catalog_path: Path | None = None,
):
    """Facade convenience: load default lab ML predictor (``clm_ensemble_v34``).

    Equivalent to ``load_predictor_for_product(default_lab_product())`` when
    ``product_id`` is omitted. Never resolves ops/field_ops. Default surface
    is product_facade ``iter1_reject_only`` (VAL thr freeze).
    """
    pid = product_id or default_lab_product(catalog_path)
    return load_predictor_for_product(pid, device=device, catalog_path=catalog_path)
