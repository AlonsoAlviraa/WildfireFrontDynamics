"""Production product catalog: NDWS, CLM single, CLM ensemble."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


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


def get_product(product_id: str, catalog_path: Path | None = None) -> ProductSpec:
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
    )


def list_products(catalog_path: Path | None = None) -> list[dict[str, Any]]:
    data = load_catalog(catalog_path)
    out = []
    for pid in sorted((data.get("products") or {})):
        spec = get_product(pid, catalog_path)
        ok, msg = spec.resolve_existing()
        out.append(
            {
                "id": spec.id,
                "label": spec.label,
                "domain": spec.domain,
                "product_type": spec.product_type,
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
    """Factory: single-model or ensemble predictor for a catalog product."""
    from wildfire_front.ml.spread_predictor import EnsembleSpreadPredictor, SpreadPredictor

    spec = get_product(product_id, catalog_path)
    ok, msg = spec.resolve_existing()
    if not ok:
        raise FileNotFoundError(f"Product {product_id} not ready: {msg}")

    if spec.product_type == "ensemble":
        return EnsembleSpreadPredictor.from_product_spec(spec, device=device)
    return SpreadPredictor.from_manifest(
        spec.manifest_path, weights_path=spec.weights_path, device=device
    )
