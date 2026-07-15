"""Dual-product catalog: NDWS global vs CLM Spain specialist."""

from __future__ import annotations

import json
from dataclasses import dataclass
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

    def resolve_existing(self) -> tuple[bool, str]:
        if not self.manifest_path.is_file():
            return False, f"missing manifest: {self.manifest_path}"
        if not self.weights_path.is_file():
            return False, f"missing weights: {self.weights_path}"
        return True, "ok"


def load_catalog(path: Path | None = None) -> dict[str, Any]:
    catalog_path = path or (ROOT / "models" / "catalog.json")
    return json.loads(catalog_path.read_text(encoding="utf-8"))


def get_product(product_id: str, catalog_path: Path | None = None) -> ProductSpec:
    data = load_catalog(catalog_path)
    products = data.get("products") or {}
    if product_id not in products:
        known = ", ".join(sorted(products))
        raise KeyError(f"Unknown product '{product_id}'. Known: {known}")
    p = products[product_id]
    return ProductSpec(
        id=str(p["id"]),
        label=str(p["label"]),
        domain=str(p["domain"]),
        manifest_path=(ROOT / p["manifest"]).resolve(),
        weights_path=(ROOT / p["weights"]).resolve(),
        use_when=str(p.get("use_when", "")),
        not_for=str(p.get("not_for", "")),
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
                "ready": ok,
                "status": msg,
                "manifest": str(spec.manifest_path),
                "weights": str(spec.weights_path),
                "use_when": spec.use_when,
                "not_for": spec.not_for,
            }
        )
    return out
