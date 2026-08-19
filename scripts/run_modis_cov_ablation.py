#!/usr/bin/env python3
"""Additional NBR-vs-MODIS-NDVI frozen-decode ablation (not official LATAM MET).

Same knobs as complete-proxy: 8-ring k=1 @ 0.90 keep-t0.
Does not overwrite outputs/ml_eval/mega_goal_model/complete_proxy_model_iou.json.
Does not write models/clm_ensemble/weights_multi_if.pt.

  python scripts/run_modis_cov_ablation.py
  python scripts/run_modis_cov_ablation.py --event-id ES_EMSR685_TENERIFE --require-model-iou

Exit:
  0 — inventory / measured additional variants
  1 — missing weights when a variant would run the frozen UNet
  2 — usage / official out-root refused / --require-model-iou cannot run
  3 — requested pack missing on disk
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.fill_latam_au_ndws_covariates import nbr_to_veg  # noqa: E402
from scripts.run_latam_au_complete_model_iou import (  # noqa: E402
    GROWTH_RING_CONNECTIVITY,
    GROWTH_RING_MIN_NEIGHBORS,
    N_CH,
    OOD_GROWTH_THRESHOLD,
    WEIGHTS as PRODUCT_WEIGHTS,
    eval_pack,
    fire_growth_ring,
)
from wildfire_front.open_if.latam_au import (  # noqa: E402
    ALL_PACK_SPECS,
    pack_dir_for,
)
from wildfire_front.open_if.modis_ee import (  # noqa: E402
    LST_RASTER_NAME,
    NDVI_RASTER_NAME,
    ndvi_to_veg_proxy,
)

SCHEMA = "wfd_modis_cov_ablation_v1"
DEFAULT_OUT = ROOT / "outputs" / "ml_eval" / "mega_goal_model" / "modis_cov_ablation"
OFFICIAL_JSON = ROOT / "outputs" / "ml_eval" / "mega_goal_model" / "complete_proxy_model_iou.json"
PRODUCT_WEIGHTS_DIR = PRODUCT_WEIGHTS.parent
LAB_SCRATCH_WEIGHTS = (
    ROOT / "outputs" / "ml_eval" / "mega_goal_model" / "lab_scratch_frozen" / "weights_pretrained_best.pt"
)

EXIT_OK = 0
EXIT_MISSING_WEIGHTS = 1
EXIT_REFUSED = 2
EXIT_MISSING_DATA = 3

DEFAULT_PACK_IDS = (
    "ES_EMSR685_TENERIFE",
    "BO_EMSR765",
    "MX_EMSR717",
    "CL_EMSR647_NACIMIENTO",
    "CL_EMSR715_VALPARAISO",
    "AU_EMSR408_NSW",
    "AU_EMSR500_PERTH",
)
DEFAULT_VARIANTS = ("nbr_veg", "modis_ndvi_veg")
OPTIONAL_LST_VARIANT = "modis_lst_as_temp"
EVENT_ID_RE = re.compile(r"^[A-Za-z0-9_]+$")

NOT_CLAIMS = (
    "not official LATAM MET",
    "not GO_Q",
    "not v34",
    "not catalog 0.8963",
    "not sealed",
    "not ROS",
    "lab_ok_conaf false",
    "modis_lst_as_temp is a contract change (LST ≠ Open-Meteo t2m)",
    "missing modis_ndvi.tif is a skip, not IoU 0.0",
)

CANNOT_RUN = frozenset(
    {
        "missing_on_disk",
        "missing_modis_ndvi",
        "missing_s2_nbr",
        "missing_lst_day_c",
        "covariates_not_ready",
        "need_ge2_labels",
        "missing_meta",
        "missing_weights",
        "official_out_root_refused",
    }
)


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def sanitize_event_id(raw: str) -> str | None:
    text = str(raw or "").strip()
    if not text or ".." in text or "/" in text or "\\" in text:
        return None
    if not EVENT_ID_RE.fullmatch(text):
        return None
    return text


def default_weights() -> Path:
    if LAB_SCRATCH_WEIGHTS.is_file():
        return LAB_SCRATCH_WEIGHTS
    return PRODUCT_WEIGHTS


def rel_to_root(path: Path) -> str:
    resolved = Path(path).resolve()
    try:
        return str(resolved.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def is_forbidden_out_root(path: Path) -> bool:
    try:
        resolved = Path(path).resolve()
    except OSError:
        return True
    official_json = OFFICIAL_JSON.resolve()
    official_dir = official_json.parent
    product_dir = PRODUCT_WEIGHTS_DIR.resolve()
    if resolved == official_json or resolved == official_dir:
        return True
    if (resolved / "complete_proxy_model_iou.json") == official_json:
        return True
    if resolved == PRODUCT_WEIGHTS.resolve() or resolved == product_dir:
        return True
    return False


def _read_tif(path: Path) -> np.ndarray | None:
    if not path.is_file():
        return None
    import rasterio

    with rasterio.open(path) as ds:
        return np.asarray(ds.read(1), dtype=np.float32)


def _provenance_veg_is_nbr(pack: Path) -> bool:
    prov = pack / "covariates" / "PROVENANCE.json"
    if not prov.is_file():
        return False
    try:
        doc = json.loads(prov.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    veg = doc.get("vegetation") or {}
    status = str(veg.get("status") or "")
    source = str(veg.get("source") or "")
    if status in {"modis_harmonic", "modis_monthly"}:
        return False
    if source.startswith("modis"):
        return False
    return status == "ok" or bool(veg.get("nbr_rel"))


def load_variant_cov(pack: Path, variant: str) -> tuple[dict[str, Any] | None, str | None]:
    cov_dir = pack / "covariates"
    elev = _read_tif(cov_dir / "elevation_m.tif")
    humidity = _read_tif(cov_dir / "humidity_pct.tif")
    wind = _read_tif(cov_dir / "wind_speed_ms.tif")
    wdir = _read_tif(cov_dir / "wind_dir_deg.tif")
    precip = _read_tif(cov_dir / "precip_mm.tif")
    if any(x is None for x in (elev, humidity, wind, wdir, precip)):
        return None, "covariates_not_ready"

    temp_path = cov_dir / "temperature_c.tif"
    if variant == OPTIONAL_LST_VARIANT:
        lst_path = cov_dir / LST_RASTER_NAME
        if not lst_path.is_file():
            return None, "missing_lst_day_c"
        temperature = _read_tif(lst_path)
        temp_source = "modis_lst_as_temp"
    else:
        if not temp_path.is_file():
            return None, "covariates_not_ready"
        temperature = _read_tif(temp_path)
        temp_source = "open_meteo_t2m"
    if temperature is None:
        return None, "covariates_not_ready"

    if variant == "modis_ndvi_veg":
        ndvi_path = cov_dir / NDVI_RASTER_NAME
        if not ndvi_path.is_file():
            return None, "missing_modis_ndvi"
        raw = _read_tif(ndvi_path)
        if raw is None:
            return None, "missing_modis_ndvi"
        veg = ndvi_to_veg_proxy(raw)
        veg_source = "modis_ndvi"
    else:
        nbr_path = cov_dir / "s2_nbr_aligned.tif"
        proxy_path = cov_dir / "vegetation_proxy.tif"
        if nbr_path.is_file():
            raw = _read_tif(nbr_path)
            if raw is None:
                return None, "missing_s2_nbr"
            veg = nbr_to_veg(raw)
            veg_source = "s2_nbr"
        elif proxy_path.is_file() and _provenance_veg_is_nbr(pack):
            veg = _read_tif(proxy_path)
            veg_source = "s2_nbr"
        else:
            return None, "missing_s2_nbr"
    if veg is None:
        return None, "missing_s2_nbr"

    try:
        doc = json.loads((cov_dir / "PROVENANCE.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        doc = {}
    return (
        {
            "elevation": elev,
            "temperature": temperature,
            "humidity": humidity,
            "wind_speed": wind,
            "wind_dir": wdir,
            "precip": precip,
            "veg": veg,
            "provenance": doc,
            "veg_source": veg_source,
            "temp_source": temp_source,
            "variant": variant,
            "contract_change": variant == OPTIONAL_LST_VARIANT,
        },
        None,
    )


def empty_row(event_id: str, variant: str, skip: str | None, **extra: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "event_id": event_id,
        "variant": variant,
        "skip_class": skip,
        "model_iou": None,
        "complete_proxy_model_iou": None,
        "n_pairs_used": 0,
        "pairs": [],
        "sold_as_clm_ensemble_v34": False,
        "sold_as_go_q": False,
        "lab_ok_conaf": False,
        "metric_kind": None,
        "observed": False,
    }
    row.update(extra)
    return row


def write_scorecard(doc: dict[str, Any], path: Path) -> None:
    lines = [
        "# SCORECARD — MODIS covariate ablation (additional)",
        "",
        "Additional NBR vs MODIS-NDVI frozen decode. **Not** the official LATAM MET.",
        "``modis_lst_as_temp`` is a **contract change** (skin LST ≠ Open-Meteo t2m).",
        "Empty model IoU is a skip, not an observed 0.0.",
        "",
        f"- as_of_utc: `{doc.get('as_of_utc')}`",
        f"- product_id: `{doc.get('product_id')}`",
        f"- GO_Q: `{doc.get('go_q')}`",
        f"- lab_ok_conaf: `{doc.get('lab_ok_conaf')}`",
        f"- decode: 8-ring k={doc.get('min_fire_neighbors')} @ {doc.get('growth_threshold')} keep-t0",
        "",
        "| event | variant | skip_class | n_pairs | model IoU | observed |",
        "|---|---|---|---:|---:|---|",
    ]
    for row in doc.get("rows") or []:
        iou = row.get("model_iou")
        lines.append(
            "| {event} | {variant} | {skip} | {n} | {iou} | {obs} |".format(
                event=row.get("event_id"),
                variant=row.get("variant"),
                skip=row.get("skip_class") or "ran",
                n="" if row.get("n_pairs_used") is None else row.get("n_pairs_used"),
                iou="" if iou is None else f"{float(iou):.6f}",
                obs="yes" if row.get("observed") else "no",
            )
        )
    lines.extend(["", "## not_claims", ""])
    for claim in doc.get("not_claims") or NOT_CLAIMS:
        lines.append(f"- {claim}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Additional MODIS veg/LST frozen-decode ablation")
    ap.add_argument("--event-id", action="append", dest="event_ids", default=None)
    ap.add_argument("--data-root", type=Path, default=ROOT / "data" / "open_if" / "latam_au")
    ap.add_argument("--out-root", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--weights", type=Path, default=None)
    ap.add_argument(
        "--variant",
        action="append",
        dest="variants",
        choices=("nbr_veg", "modis_ndvi_veg", OPTIONAL_LST_VARIANT),
        default=None,
    )
    ap.add_argument(
        "--include-lst-as-temp",
        action="store_true",
        help="Also run the labeled contract-change variant modis_lst_as_temp",
    )
    ap.add_argument(
        "--require-model-iou",
        action="store_true",
        help="Exit 2 if a selected variant cannot run the frozen UNet.",
    )
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.event_ids:
        ids: list[str] = []
        for raw in args.event_ids:
            eid = sanitize_event_id(str(raw))
            if eid is None or eid not in ALL_PACK_SPECS:
                print(f"error: missing data / unknown pack {raw}", file=sys.stderr)
                return EXIT_MISSING_DATA
            ids.append(eid)
        explicit = True
    else:
        ids = list(DEFAULT_PACK_IDS)
        explicit = False

    variants: list[str] = list(args.variants) if args.variants else list(DEFAULT_VARIANTS)
    if args.include_lst_as_temp and OPTIONAL_LST_VARIANT not in variants:
        variants.append(OPTIONAL_LST_VARIANT)

    out_root = Path(args.out_root)
    if is_forbidden_out_root(out_root):
        print(
            "error: refuses_official_out_root "
            f"(will not write {rel_to_root(OFFICIAL_JSON)} or {rel_to_root(PRODUCT_WEIGHTS)})",
            file=sys.stderr,
        )
        return EXIT_REFUSED

    data_root = Path(args.data_root)
    resolved: dict[str, Path] = {}
    for eid in ids:
        spec = ALL_PACK_SPECS[eid]
        pack = pack_dir_for(data_root, spec)
        resolved[eid] = pack
        if explicit and (not pack.is_dir() or not (pack / "meta.json").is_file()):
            print(f"error: missing pack {eid} at {pack}", file=sys.stderr)
            return EXIT_MISSING_DATA

    predicted: list[tuple[str, str, str | None]] = []
    for eid in ids:
        pack = resolved[eid]
        if not pack.is_dir() or not (pack / "meta.json").is_file():
            for variant in variants:
                predicted.append((eid, variant, "missing_on_disk"))
            continue
        for variant in variants:
            _cov, skip = load_variant_cov(pack, variant)
            predicted.append((eid, variant, skip))

    if args.require_model_iou:
        blocked = [(e, v, s) for e, v, s in predicted if s in CANNOT_RUN]
        if blocked:
            print(
                "error: incompatible / not runnable for frozen decode: "
                + ", ".join(f"{e}/{v}={s}" for e, v, s in blocked),
                file=sys.stderr,
            )
            return EXIT_REFUSED

    needs_model = any(skip is None for _e, _v, skip in predicted)
    weights = Path(args.weights) if args.weights is not None else default_weights()
    model = None
    device = None
    if needs_model:
        if not weights.is_file():
            print(
                f"error: missing weights {weights} — refusing invented modis-cov IoU",
                file=sys.stderr,
            )
            return EXIT_MISSING_WEIGHTS
        import torch

        from wildfire_front.ml.unet_train import UNetTrainConfig, build_model

        device = torch.device("cpu")
        cfg = UNetTrainConfig(architecture="residual", model="small", target_mode="delta")
        model = build_model(cfg, in_channels=N_CH + 1)
        state = torch.load(Path(weights), map_location=device, weights_only=True)
        model.load_state_dict(state, strict=True)
        model.to(device)
        model.eval()

    rows: list[dict[str, Any]] = []
    for eid, variant, skip in predicted:
        pack = resolved[eid]
        if skip is not None:
            rows.append(empty_row(eid, variant, skip, path=str(pack)))
            print(f"{eid}/{variant}: skip={skip} model_iou=None")
            continue
        cov, skip2 = load_variant_cov(pack, variant)
        if cov is None or model is None or device is None:
            reason = skip2 or "missing_weights"
            rows.append(empty_row(eid, variant, reason))
            print(f"{eid}/{variant}: skip={reason} model_iou=None")
            continue
        measured = eval_pack(
            eid,
            pack,
            model,
            device,
            growth_threshold=OOD_GROWTH_THRESHOLD,
            require_growth_ring=True,
            keep_t0=True,
            cov=cov,
        )
        iou = measured.get("complete_proxy_model_iou")
        observed = iou is not None and int(measured.get("n_pairs_used") or 0) > 0
        if observed:
            skip_reason = None
        else:
            skip_reason = measured.get("error")
            if not skip_reason:
                pair_classes = [
                    str(p.get("pair_class"))
                    for p in (measured.get("pairs") or [])
                    if p.get("pair_class")
                ]
                uniq = list(dict.fromkeys(pair_classes))
                if len(uniq) == 1:
                    skip_reason = uniq[0]
                elif uniq:
                    skip_reason = "no_usable_pairs"
                else:
                    skip_reason = "covariates_not_ready"
        row = {
            "event_id": eid,
            "variant": variant,
            "skip_class": skip_reason,
            "model_iou": iou if observed else None,
            "complete_proxy_model_iou": iou if observed else None,
            "copy_baseline_iou": measured.get("copy_baseline_iou") if observed else None,
            "delta_vs_copy": measured.get("delta_vs_copy") if observed else None,
            "n_pairs": measured.get("n_pairs"),
            "n_pairs_used": measured.get("n_pairs_used") if observed else 0,
            "pairs": measured.get("pairs") or [],
            "sold_as_clm_ensemble_v34": False,
            "sold_as_go_q": False,
            "lab_ok_conaf": False,
            "metric_kind": "frozen_decode_model" if observed else None,
            "observed": bool(observed),
            "veg_source": cov.get("veg_source"),
            "temp_source": cov.get("temp_source"),
            "contract_change": bool(cov.get("contract_change")),
            "growth_threshold": float(OOD_GROWTH_THRESHOLD),
            "growth_ring_connectivity": int(GROWTH_RING_CONNECTIVITY),
            "min_fire_neighbors": int(GROWTH_RING_MIN_NEIGHBORS),
            "keep_t0": True,
        }
        rows.append(row)
        print(f"{eid}/{variant}: skip={row['skip_class']} model_iou={row['model_iou']}")

    if args.require_model_iou:
        failed = [r for r in rows if r.get("model_iou") is None or r.get("skip_class") in CANNOT_RUN]
        if failed:
            print(
                "error: --require-model-iou did not obtain IoU for "
                + ", ".join(f"{r.get('event_id')}/{r.get('variant')}" for r in failed),
                file=sys.stderr,
            )
            return EXIT_REFUSED

    weights_rel = rel_to_root(weights) if weights.is_file() else None
    summary = {
        "schema": SCHEMA,
        "as_of_utc": utc_now(),
        "product_id": "modis_cov_ablation_additional",
        "claim_class": "additional_modis_cov_ablation",
        "official_latam_complete_proxy_untouched": True,
        "official_json": rel_to_root(OFFICIAL_JSON),
        "sold_as_clm_ensemble_v34": False,
        "sold_as_go_q": False,
        "go_q": "partial",
        "lab_ok_conaf": False,
        "weights": weights_rel,
        "wrote_product_weights": False,
        "growth_threshold": float(OOD_GROWTH_THRESHOLD),
        "growth_ring_connectivity": int(GROWTH_RING_CONNECTIVITY),
        "min_fire_neighbors": int(GROWTH_RING_MIN_NEIGHBORS),
        "keep_t0": True,
        "require_growth_ring": True,
        "architecture": "residual",
        "target_mode": "delta",
        "pair_protocol": {
            "min_delta_hours": 12.0,
            "static_label_copy_iou_gt": 0.98,
            "excluded_classes": [
                "too_short_delta",
                "static_label_copy",
                "incompatible_product_kind",
            ],
        },
        "variants": variants,
        "rows": rows,
        "not_claims": list(NOT_CLAIMS),
        "rails": {
            "go_q": "partial",
            "freeze_intact": True,
            "lab_ok_conaf": False,
            "no_retrain": True,
            "official_json_untouched": True,
        },
    }
    out_root.mkdir(parents=True, exist_ok=True)
    if (out_root / "complete_proxy_model_iou.json").resolve() == OFFICIAL_JSON.resolve():
        print("error: refuses_official_out_root", file=sys.stderr)
        return EXIT_REFUSED
    json_path = out_root / "modis_cov_ablation.json"
    json_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    write_scorecard(summary, out_root / "SCORECARD.md")
    print("wrote", json_path)
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
