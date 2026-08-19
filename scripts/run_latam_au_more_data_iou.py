#!/usr/bin/env python3
"""Additional frozen-decode eval on extra on-disk packs (not the official LATAM 4).

Reuses decode_complete_proxy_pred / fire_growth_ring / classify_temporal_pair.
Does not retune knobs, does not write models/clm_ensemble/weights_multi_if.pt,
does not overwrite outputs/ml_eval/mega_goal_model/complete_proxy_model_iou.json.

  python scripts/run_latam_au_more_data_iou.py
  python scripts/run_latam_au_more_data_iou.py --pack RCDA_NET --require-model-iou

Exit:
  0 — inventory / eval wrote more_data artifacts
  1 — missing weights (a selected pack needs the frozen UNet)
  2 — --require-model-iou but pack is schema-incompatible / not runnable
  3 — requested pack or required data root missing on disk
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.run_latam_au_complete_model_iou import (  # noqa: E402
    GROWTH_RING_CONNECTIVITY,
    GROWTH_RING_MIN_NEIGHBORS,
    N_CH,
    OOD_GROWTH_THRESHOLD,
    WEIGHTS as PRODUCT_WEIGHTS,
    binary_iou,
    decode_complete_proxy_pred,
    eval_pack,
    fire_growth_ring,
    load_mask,
)
from wildfire_front.open_if.latam_au import (  # noqa: E402
    ANNUAL_EVAL_STATUS,
    EMSR_PACK_SPECS,
    WEAK_PACK_SPECS,
    classify_temporal_pair,
    hours_between,
    is_annual_l1_spec,
    label_records_from_meta,
    mean_usable_pair_ious,
    pack_dir_for,
    parse_iso_utc,
)

SCHEMA = "wfd_more_data_frozen_decode_v1"
DEFAULT_OUT = ROOT / "outputs" / "ml_eval" / "mega_goal_model" / "more_data"
OFFICIAL_JSON = ROOT / "outputs" / "ml_eval" / "mega_goal_model" / "complete_proxy_model_iou.json"
LAB_SCRATCH_WEIGHTS = (
    ROOT / "outputs" / "ml_eval" / "mega_goal_model" / "lab_scratch_frozen" / "weights_pretrained_best.pt"
)

EXIT_OK = 0
EXIT_MISSING_WEIGHTS = 1
EXIT_INCOMPATIBLE_SCHEMA = 2
EXIT_MISSING_DATA = 3

OFFICIAL_LATAM_COMPLETE_PROXY_IDS = (
    "AU_EMSR500_PERTH",
    "CL_EMSR647_NACIMIENTO",
    "AU_EMSR408_NSW",
    "CL_EMSR715_VALPARAISO",
)

DEFAULT_PACK_IDS = (
    "ES_EMSR685_TENERIFE",
    "BO_EMSR765",
    "MX_EMSR717",
    "BR_PANTANAL_2020_MAPBIOMAS",
    "AU_NAFI_NT_SEASON_2023",
    "US_FIREBENCH_CALDOR_2021",
    "RCDA_NET",
    "PT_FIRESPRD_SAO_JOAO_PESQUEIRA_2020",
    "CLM_HOLDOUT_V1_TEST",
)

CANNOT_RUN_MODEL = frozenset(
    {
        "incompatible_schema",
        "covariates_not_ready",
        "blocked_annual_not_event",
        "refused_placeholder_covariates",
        "missing_on_disk",
        "official_latam_excluded",
        "need_ge2_labels",
        "missing_meta",
    }
)

NOT_CLAIMS = (
    "additional more-data eval — not the official LATAM complete-proxy mean",
    "not sealed transfer IoU",
    "not GO_Q complete",
    "not GO_TOTAL",
    "not FREEZE lift",
    "not clm_ensemble_v34 product score",
    "not U1 TEST CLM (0.857)",
    "not catalog 0.8963",
    "not RCDA published 0.308",
    "FireBench/Caldor/RCDA are not sold as clm_ensemble_v34 or GO_Q",
    "lab_ok_conaf remains false",
    "FEP/GRA pairs never enter a LATAM complete-proxy mean",
)


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


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


def empty_pack_row(
    pack_id: str,
    *,
    family: str,
    skip_class: str | None,
    model_iou: float | None = None,
    **extra: Any,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "pack_id": pack_id,
        "family": family,
        "skip_class": skip_class,
        "schema_compatible": skip_class is None,
        "model_iou": model_iou,
        "complete_proxy_model_iou": model_iou,
        "n_pairs_used": 0,
        "pairs": [],
        "sold_as_clm_ensemble_v34": False,
        "sold_as_go_q": False,
        "metric_kind": None if model_iou is None else "frozen_decode_model",
    }
    row.update(extra)
    return row


def extra_family_mean_model_ious(packs: list[dict[str, Any]]) -> float | None:
    """Mean of extra LATAM-CEMS usable model IoUs. Never official 4, never FEP/GRA."""
    vals: list[float] = []
    for pack in packs:
        if pack.get("pack_id") in OFFICIAL_LATAM_COMPLETE_PROXY_IDS:
            continue
        if pack.get("family") != "extra_latam_cems":
            continue
        for pair in pack.get("pairs") or []:
            if pair.get("pair_class") != "usable":
                continue
            iou = pair.get("complete_proxy_model_iou")
            if iou is None:
                continue
            vals.append(float(iou))
    if not vals:
        return None
    return float(sum(vals) / len(vals))


def holdout_mean_model_iou(packs: list[dict[str, Any]]) -> float | None:
    for pack in packs:
        if pack.get("pack_id") != "CLM_HOLDOUT_V1_TEST":
            continue
        iou = pack.get("model_iou")
        if iou is None:
            return None
        return float(iou)
    return None


def pair_rows_from_labels(
    label_recs: list[dict[str, Any]],
    *,
    load_fn=load_mask,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for i in range(1, len(label_recs)):
        prev_rec, next_rec = label_recs[i - 1], label_recs[i]
        prev_m = load_fn(Path(prev_rec["path"]))
        next_m = load_fn(Path(next_rec["path"]))
        if prev_m.shape != next_m.shape:
            rows.append(
                {
                    "from": prev_rec.get("name"),
                    "to": next_rec.get("name"),
                    "from_kind": prev_rec.get("kind"),
                    "to_kind": next_rec.get("kind"),
                    "delta_hours": None,
                    "label_mask_iou": None,
                    "copy_mask_iou": None,
                    "pair_class": "label_shape_mismatch",
                    "complete_proxy_model_iou": None,
                    "metric_kind": None,
                }
            )
            continue
        delta = None
        if prev_rec.get("dt") is not None and next_rec.get("dt") is not None:
            delta = hours_between(prev_rec["dt"], next_rec["dt"])
        label_iou = binary_iou(prev_m > 0, next_m > 0)
        pair_class = classify_temporal_pair(
            delta_hours=delta,
            label_mask_iou=label_iou,
            prev_kind=prev_rec.get("kind"),
            next_kind=next_rec.get("kind"),
        )
        rows.append(
            {
                "from": prev_rec.get("name"),
                "to": next_rec.get("name"),
                "from_kind": prev_rec.get("kind"),
                "to_kind": next_rec.get("kind"),
                "from_utc": prev_rec.get("delivery_utc"),
                "to_utc": next_rec.get("delivery_utc"),
                "delta_hours": delta,
                "label_mask_iou": label_iou,
                "copy_mask_iou": label_iou,
                "pair_class": pair_class,
                "complete_proxy_model_iou": None,
                "metric_kind": "label_vs_label_copy",
            }
        )
    return rows


def eval_extra_latam_cems(
    pack_id: str,
    data_root: Path,
    model,
    device,
) -> dict[str, Any]:
    spec = {**EMSR_PACK_SPECS, **WEAK_PACK_SPECS}.get(pack_id) or {}
    if not spec:
        return empty_pack_row(
            pack_id,
            family="extra_latam_cems",
            skip_class="missing_on_disk",
            error="unknown_event_id",
        )
    pack = pack_dir_for(data_root, spec)
    if not pack.is_dir() or not (pack / "meta.json").is_file():
        return empty_pack_row(
            pack_id,
            family="extra_latam_cems" if not is_annual_l1_spec(spec) else "latam_weak_annual",
            skip_class="missing_on_disk",
            path=str(pack),
        )
    if is_annual_l1_spec(spec):
        meta = json.loads((pack / "meta.json").read_text(encoding="utf-8"))
        n_labels = len(label_records_from_meta(pack, meta))
        return empty_pack_row(
            pack_id,
            family="latam_weak_annual",
            skip_class=ANNUAL_EVAL_STATUS,
            n_labels=n_labels,
            eval_status=ANNUAL_EVAL_STATUS,
        )
    if model is not None:
        measured = eval_pack(
            pack_id,
            pack,
            model,
            device,
            growth_threshold=OOD_GROWTH_THRESHOLD,
            require_growth_ring=True,
        )
        if measured.get("complete_proxy_model_iou") is not None:
            measured["pack_id"] = pack_id
            measured["family"] = "extra_latam_cems"
            measured["skip_class"] = None
            measured["schema_compatible"] = True
            measured["model_iou"] = measured.get("complete_proxy_model_iou")
            measured["sold_as_clm_ensemble_v34"] = False
            measured["sold_as_go_q"] = False
            measured["metric_kind"] = "frozen_decode_model"
            return measured
    meta = json.loads((pack / "meta.json").read_text(encoding="utf-8"))
    recs = label_records_from_meta(pack, meta)
    if len(recs) < 2:
        disk = sorted((pack / "labels").glob("*.tif"))
        recs = [
            {"path": p, "name": p.name, "delivery_utc": None, "dt": None, "kind": None}
            for p in disk
        ]
    if len(recs) < 2:
        return empty_pack_row(
            pack_id,
            family="extra_latam_cems",
            skip_class="need_ge2_labels",
            path=rel_to_root(pack),
        )
    pairs = pair_rows_from_labels(recs)
    return {
        "pack_id": pack_id,
        "family": "extra_latam_cems",
        "skip_class": "covariates_not_ready",
        "schema_compatible": False,
        "model_iou": None,
        "complete_proxy_model_iou": None,
        "copy_baseline_iou": mean_usable_pair_ious(pairs, key="copy_mask_iou"),
        "n_pairs": len(pairs),
        "n_pairs_used": 0,
        "pairs": pairs,
        "sold_as_clm_ensemble_v34": False,
        "sold_as_go_q": False,
        "metric_kind": "label_vs_label_copy",
        "hint": "run scripts/fill_latam_au_ndws_covariates.py before model IoU",
    }


def eval_caldor_bridge(caldor_root: Path) -> dict[str, Any]:
    meta_p = caldor_root / "meta.json"
    if not meta_p.is_file():
        return empty_pack_row(
            "US_FIREBENCH_CALDOR_2021",
            family="firebench_caldor",
            skip_class="missing_on_disk",
            path=str(caldor_root),
        )
    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    tensors_manifest = caldor_root / "tensors" / "clean17_physical_v1" / "manifest.json"
    legacy_ok = False
    if tensors_manifest.is_file():
        tdoc = json.loads(tensors_manifest.read_text(encoding="utf-8"))
        legacy_ok = bool(tdoc.get("legacy17_checkpoint_compatible"))
    placeholder = (
        ROOT / "artifacts" / "clm_ndws_patches" / "external_ingest_v1" / "firebench_caldor" / "patch_manifest.json"
    )
    placeholder_status = None
    if placeholder.is_file():
        pdoc = json.loads(placeholder.read_text(encoding="utf-8"))
        placeholder_status = pdoc.get("input_contract_status")
    obs = list(meta.get("observations") or [])
    pairs_doc = {}
    pairs_p = caldor_root / "pairs.json"
    if pairs_p.is_file():
        pairs_doc = json.loads(pairs_p.read_text(encoding="utf-8"))
    recs: list[dict[str, Any]] = []
    for item in obs:
        rel = item.get("cumulative_mask")
        path = caldor_root / rel if rel else None
        if path is None or not path.is_file():
            continue
        recs.append(
            {
                "path": path,
                "name": Path(rel).name,
                "delivery_utc": item.get("timestamp_utc"),
                "dt": parse_iso_utc(str(item.get("timestamp_utc") or "")),
                "kind": "delineation_monitoring",
            }
        )
    pairs = pair_rows_from_labels(recs) if len(recs) >= 2 else []
    next_day = [
        p
        for p in (pairs_doc.get("pairs") or [])
        if p.get("next_day_compatible")
    ]
    return {
        "pack_id": "US_FIREBENCH_CALDOR_2021",
        "family": "firebench_caldor",
        "skip_class": "incompatible_schema",
        "schema_compatible": False,
        "legacy17_checkpoint_compatible": legacy_ok,
        "model_iou": None,
        "complete_proxy_model_iou": None,
        "copy_baseline_iou": mean_usable_pair_ious(pairs, key="copy_mask_iou"),
        "n_observations": int(meta.get("n_observations") or len(obs)),
        "n_pairs": len(pairs),
        "n_pairs_12_to_36h": int(meta.get("n_pairs_12_to_36h") or len(next_day)),
        "n_pairs_used": 0,
        "pairs": pairs,
        "sold_as_clm_ensemble_v34": False,
        "sold_as_go_q": False,
        "metric_kind": "label_vs_label_copy",
        "related_artifacts": {
            "h5": rel_to_root(ROOT / "data/external/firebench/caldor_2021/v2026.1/Caldor.h5")
            if (ROOT / "data/external/firebench/caldor_2021/v2026.1/Caldor.h5").is_file()
            else None,
            "placeholder_npz_status": placeholder_status,
        },
        "not_claims": [
            "not clm_ensemble_v34",
            "not GO_Q",
            "copy_mask_iou is label-vs-label, not model IoU",
            "Caldor label-copy is not catalog 0.8963",
        ],
        "caldor_copy_is_not_catalog_08963": True,
        "catalog_holdout_iou_08963_used": False,
    }


def _probe_rcda_npy(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    arr = np.load(path, mmap_mode="r")
    return {"path": rel_to_root(path), "shape": list(arr.shape), "dtype": str(arr.dtype)}


def eval_rcda(rcda_root: Path) -> dict[str, Any]:
    if not rcda_root.exists():
        return empty_pack_row(
            "RCDA_NET",
            family="rcda_npy",
            skip_class="missing_on_disk",
            path=str(rcda_root),
        )
    test_in = rcda_root / "test" / "inputs"
    train_in = rcda_root / "train" / "inputs"
    sample_in = rcda_root / "inputs"
    n_test = len(list(test_in.glob("*.npy"))) if test_in.is_dir() else 0
    n_train = len(list(train_in.glob("*.npy"))) if train_in.is_dir() else 0
    n_sample = len(list(sample_in.glob("*.npy"))) if sample_in.is_dir() else 0
    probe_src = None
    if test_in.is_dir():
        probe_src = next(iter(sorted(test_in.glob("*.npy"))), None)
    if probe_src is None and sample_in.is_dir():
        probe_src = next(iter(sorted(sample_in.glob("*.npy"))), None)
    probe = _probe_rcda_npy(probe_src) if probe_src is not None else None
    shape_ok = False
    if probe and probe.get("shape"):
        shape = list(probe["shape"])
        # legacy17+prev is 18 after prepare_input; RCDA public/full is 12x256x256.
        shape_ok = len(shape) == 3 and int(shape[0]) == 17
    skip = None if shape_ok else "incompatible_schema"
    return empty_pack_row(
        "RCDA_NET",
        family="rcda_npy",
        skip_class=skip,
        n_test_inputs=n_test,
        n_train_inputs=n_train,
        n_public_sample_inputs=n_sample,
        sample=probe,
        published_iou_cited=False,
        note="12-channel RCDA npy is not frozen complete-proxy input; IoU not invented",
    )


def eval_pt_firesprd(pt_root: Path) -> dict[str, Any]:
    meta_p = pt_root / "meta.json"
    if not meta_p.is_file():
        return empty_pack_row(
            "PT_FIRESPRD_SAO_JOAO_PESQUEIRA_2020",
            family="pt_firesprd",
            skip_class="missing_on_disk",
            path=str(pt_root),
        )
    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    recs: list[dict[str, Any]] = []
    for item in meta.get("geotiffs") or []:
        rel = item.get("rel_mask")
        path = pt_root / rel if rel else None
        if path is None or not path.is_file():
            continue
        raw = str(item.get("date_hour_raw") or "")
        dt = parse_iso_utc(raw.replace(" ", "T") + "Z") if raw else None
        recs.append(
            {
                "path": path,
                "name": Path(rel).name,
                "delivery_utc": raw or None,
                "dt": dt,
                "kind": "delineation_monitoring",
            }
        )
    if len(recs) < 2:
        return empty_pack_row(
            "PT_FIRESPRD_SAO_JOAO_PESQUEIRA_2020",
            family="pt_firesprd",
            skip_class="need_ge2_labels",
            timestamp_tz=meta.get("timestamp_tz"),
        )
    pairs = pair_rows_from_labels(recs)
    return {
        "pack_id": "PT_FIRESPRD_SAO_JOAO_PESQUEIRA_2020",
        "family": "pt_firesprd",
        "skip_class": "covariates_not_ready",
        "schema_compatible": False,
        "model_iou": None,
        "complete_proxy_model_iou": None,
        "copy_baseline_iou": mean_usable_pair_ious(pairs, key="copy_mask_iou"),
        "n_pairs": len(pairs),
        "n_pairs_used": 0,
        "pairs": pairs,
        "timestamp_tz": meta.get("timestamp_tz"),
        "not_verified_utc": meta.get("not_verified_utc"),
        "sold_as_clm_ensemble_v34": False,
        "sold_as_go_q": False,
        "metric_kind": "label_vs_label_copy",
    }


def _load_model(weights: Path, device):
    import torch

    from wildfire_front.ml.unet_train import UNetTrainConfig, build_model

    cfg = UNetTrainConfig(architecture="residual", model="small", target_mode="delta")
    model = build_model(cfg, in_channels=N_CH + 1)
    state = torch.load(Path(weights), map_location=device, weights_only=True)
    model.load_state_dict(state, strict=True)
    model.to(device)
    model.eval()
    return model


def eval_clm_holdout(
    holdout_root: Path,
    model,
    device,
    *,
    max_patches: int,
) -> dict[str, Any]:
    if not holdout_root.is_dir():
        return empty_pack_row(
            "CLM_HOLDOUT_V1_TEST",
            family="clm_holdout_npz",
            skip_class="missing_on_disk",
            path=str(holdout_root),
        )
    files = sorted(holdout_root.glob("*.npz"))
    if not files:
        return empty_pack_row(
            "CLM_HOLDOUT_V1_TEST",
            family="clm_holdout_npz",
            skip_class="need_ge2_labels",
            path=rel_to_root(holdout_root),
        )
    import torch

    from wildfire_front.ml.unet_train import model_forward, prepare_input

    take = files[: max(1, int(max_patches))]
    model_ious: list[float] = []
    copy_ious: list[float] = []
    for path in take:
        with np.load(path) as data:
            seq = np.where(np.isfinite(data["sequence"]), data["sequence"], 0.0).astype(np.float32)
            prev = np.asarray(data["current_fire"], dtype=np.float32)
            tgt = np.asarray(data["target_fire"], dtype=np.float32)
        if seq.ndim == 4:
            seq_t = torch.from_numpy(seq[np.newaxis, ...])
        elif seq.ndim == 5:
            seq_t = torch.from_numpy(seq)
        else:
            continue
        if seq_t.shape[2] != N_CH:
            return empty_pack_row(
                "CLM_HOLDOUT_V1_TEST",
                family="clm_holdout_npz",
                skip_class="incompatible_schema",
                sample_sequence_shape=list(seq_t.shape),
            )
        cur_t = torch.from_numpy(prev[np.newaxis, ...])
        x_in = prepare_input(seq_t, cur_t).to(device)
        with torch.no_grad():
            logits = model_forward(model, x_in, cur_t.to(device), "residual")
            probability = torch.sigmoid(logits)[0, 0].cpu().numpy()
        pred = decode_complete_proxy_pred(
            probability,
            prev,
            architecture="residual",
            target_mode="delta",
            threshold=0.5,
            growth_threshold=OOD_GROWTH_THRESHOLD,
            require_growth_ring=True,
        )
        model_ious.append(binary_iou(pred, tgt > 0.5))
        copy_ious.append(binary_iou(prev >= 0.5, tgt > 0.5))
    if not model_ious:
        return empty_pack_row(
            "CLM_HOLDOUT_V1_TEST",
            family="clm_holdout_npz",
            skip_class="need_ge2_labels",
            n_files_seen=len(files),
        )
    mean_model = float(np.mean(model_ious))
    mean_copy = float(np.mean(copy_ious))
    return {
        "pack_id": "CLM_HOLDOUT_V1_TEST",
        "family": "clm_holdout_npz",
        "skip_class": None,
        "schema_compatible": True,
        "protocol": "clm_holdout_test_seed42_v1",
        "holdout_split": "test",
        "holdout_event": "CARDOSO",
        "model_iou": mean_model,
        "complete_proxy_model_iou": mean_model,
        "copy_baseline_iou": mean_copy,
        "delta_vs_copy": float(mean_model - mean_copy),
        "n_patches_used": len(model_ious),
        "n_patches_available": len(files),
        "n_pairs_used": 0,
        "pairs": [],
        "sold_as_clm_ensemble_v34": False,
        "sold_as_go_q": False,
        "metric_kind": "frozen_decode_model",
        "not_claims": [
            "not U1 TEST CLM (0.857)",
            "not catalog 0.8963",
            "not LATAM complete-proxy",
            "not GO_Q",
            "not clm_ensemble_v34 product score",
        ],
    }


def pack_needs_model(pack_id: str) -> bool:
    return pack_id in {"CLM_HOLDOUT_V1_TEST"} or pack_id in EMSR_PACK_SPECS


def resolve_pack_path(
    pack_id: str,
    *,
    data_root: Path,
    caldor_root: Path,
    rcda_root: Path,
    pt_root: Path,
    holdout_root: Path,
) -> Path | None:
    if pack_id in EMSR_PACK_SPECS or pack_id in WEAK_PACK_SPECS:
        spec = {**EMSR_PACK_SPECS, **WEAK_PACK_SPECS}[pack_id]
        return pack_dir_for(data_root, spec)
    if pack_id == "US_FIREBENCH_CALDOR_2021":
        return caldor_root
    if pack_id == "RCDA_NET":
        return rcda_root
    if pack_id == "PT_FIRESPRD_SAO_JOAO_PESQUEIRA_2020":
        return pt_root
    if pack_id == "CLM_HOLDOUT_V1_TEST":
        return holdout_root
    return None


def pack_present(pack_id: str, path: Path | None) -> bool:
    if path is None:
        return False
    if pack_id in EMSR_PACK_SPECS or pack_id in WEAK_PACK_SPECS:
        return path.is_dir() and (path / "meta.json").is_file()
    if pack_id == "US_FIREBENCH_CALDOR_2021":
        return (path / "meta.json").is_file()
    if pack_id == "RCDA_NET":
        return path.exists() and (
            (path / "test" / "inputs").is_dir()
            or (path / "inputs").is_dir()
            or any(path.glob("*.npy"))
        )
    if pack_id == "PT_FIRESPRD_SAO_JOAO_PESQUEIRA_2020":
        return (path / "meta.json").is_file()
    if pack_id == "CLM_HOLDOUT_V1_TEST":
        return path.is_dir() and any(path.glob("*.npz"))
    return path.exists()


def skip_class_if_unrunnable(pack_id: str, path: Path | None) -> str | None:
    if not pack_present(pack_id, path):
        return "missing_on_disk"
    if pack_id in WEAK_PACK_SPECS and is_annual_l1_spec(WEAK_PACK_SPECS[pack_id]):
        return ANNUAL_EVAL_STATUS
    if pack_id == "US_FIREBENCH_CALDOR_2021":
        return "incompatible_schema"
    if pack_id == "RCDA_NET":
        return "incompatible_schema"
    if pack_id == "PT_FIRESPRD_SAO_JOAO_PESQUEIRA_2020":
        return "covariates_not_ready"
    if pack_id in EMSR_PACK_SPECS and pack_id not in OFFICIAL_LATAM_COMPLETE_PROXY_IDS:
        cov = path / "covariates" / "PROVENANCE.json" if path is not None else None
        if cov is None or not cov.is_file():
            return "covariates_not_ready"
        try:
            doc = json.loads(cov.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return "covariates_not_ready"
        ready = doc.get("channels_ready") or {}
        if not all(ready.get(k) for k in ("meteo", "dem", "veg")):
            return "covariates_not_ready"
        return None
    if pack_id == "CLM_HOLDOUT_V1_TEST":
        return None
    if pack_id in OFFICIAL_LATAM_COMPLETE_PROXY_IDS:
        return "official_latam_excluded"
    return "incompatible_schema"


def write_scorecard(doc: dict[str, Any], path: Path) -> None:
    lines = [
        "# SCORECARD — more-data frozen decode (additional)",
        "",
        "Additional to the official LATAM 4-pair complete-proxy JSON. Not a replacement.",
        "",
        f"- as_of_utc: `{doc.get('as_of_utc')}`",
        f"- product_id: `{doc.get('product_id')}`",
        f"- sold_as_clm_ensemble_v34: `{doc.get('sold_as_clm_ensemble_v34')}`",
        f"- GO_Q: `{doc.get('go_q')}`",
        f"- lab_ok_conaf: `{doc.get('lab_ok_conaf')}`",
        f"- decode: threshold={doc.get('growth_threshold')} "
        f"connectivity={doc.get('growth_ring_connectivity')} "
        f"min_fire_neighbors={doc.get('min_fire_neighbors')} keep_t0=true",
        f"- extra LATAM-CEMS usable model mean: `{doc.get('extra_latam_cems_mean_model_iou')}`",
        f"- CLM holdout frozen-decode mean: `{doc.get('clm_holdout_mean_model_iou')}`",
        f"- mixed family mean: `{doc.get('mixed_family_mean_model_iou')}` (must stay null)",
        "",
        "Copy column is **label-vs-label** on usable pairs only. Empty model IoU means skip, not zero.",
        "Caldor label-copy (if present) is **not** catalog 0.8963 and **not** `clm_ensemble_v34`.",
        "CLM holdout frozen-decode (if present) is **not** U1 TEST 0.857.",
        "",
        "| pack | family | skip_class | n | label copy | model IoU | Δ |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for pack in doc.get("packs") or []:
        n = pack.get("n_patches_used")
        if n is None:
            n = pack.get("n_pairs")
        copy_iou = pack.get("copy_baseline_iou")
        model_iou = pack.get("model_iou")
        delta = pack.get("delta_vs_copy")
        lines.append(
            "| {pack} | {family} | {skip} | {n} | {copy} | {model} | {delta} |".format(
                pack=pack.get("pack_id"),
                family=pack.get("family"),
                skip=pack.get("skip_class") or "ran",
                n="" if n is None else n,
                copy="" if copy_iou is None else f"{float(copy_iou):.6f}",
                model="" if model_iou is None else f"{float(model_iou):.6f}",
                delta="" if delta is None else f"{float(delta):+.6f}",
            )
        )
    lines.extend(["", "## not_claims", ""])
    for claim in doc.get("not_claims") or NOT_CLAIMS:
        lines.append(f"- {claim}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Additional frozen-decode eval on extra packs")
    ap.add_argument("--pack", action="append", dest="packs", default=None)
    ap.add_argument("--data-root", type=Path, default=ROOT / "data" / "open_if" / "latam_au")
    ap.add_argument(
        "--caldor-root",
        type=Path,
        default=ROOT / "data" / "open_if" / "external_bridge" / "US_FIREBENCH_CALDOR_2021",
    )
    ap.add_argument(
        "--rcda-root",
        type=Path,
        default=ROOT / "data" / "external" / "rcda_net_full" / "dataset",
    )
    ap.add_argument(
        "--pt-root",
        type=Path,
        default=(
            ROOT
            / "outputs"
            / "open_if"
            / "best_fires_e2e"
            / "pt_firesprd"
            / "geotiff"
            / "SaoJoaoPesqueira_10072020"
        ),
    )
    ap.add_argument(
        "--holdout-root",
        type=Path,
        default=ROOT / "artifacts" / "clm_ndws_patches" / "holdout_v1" / "test",
    )
    ap.add_argument("--out-root", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--weights", type=Path, default=None)
    ap.add_argument("--max-holdout-patches", type=int, default=200)
    ap.add_argument(
        "--require-model-iou",
        action="store_true",
        help="Exit 2 if a selected pack cannot run the frozen UNet.",
    )
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    wanted = list(args.packs) if args.packs else list(DEFAULT_PACK_IDS)
    known = set(DEFAULT_PACK_IDS) | set(EMSR_PACK_SPECS) | set(WEAK_PACK_SPECS)
    for pack_id in wanted:
        if pack_id not in known:
            print(f"error: missing data / unknown pack {pack_id}", file=sys.stderr)
            return EXIT_MISSING_DATA
        if pack_id in OFFICIAL_LATAM_COMPLETE_PROXY_IDS:
            print(
                f"error: {pack_id} is an official LATAM complete-proxy pack; "
                "more-data path refuses to mix it in",
                file=sys.stderr,
            )
            return EXIT_MISSING_DATA

    resolved: dict[str, Path | None] = {}
    for pack_id in wanted:
        path = resolve_pack_path(
            pack_id,
            data_root=Path(args.data_root),
            caldor_root=Path(args.caldor_root),
            rcda_root=Path(args.rcda_root),
            pt_root=Path(args.pt_root),
            holdout_root=Path(args.holdout_root),
        )
        resolved[pack_id] = path
        if args.packs and not pack_present(pack_id, path):
            print(f"error: missing data for pack {pack_id} at {path}", file=sys.stderr)
            return EXIT_MISSING_DATA

    predicted_skip = {pid: skip_class_if_unrunnable(pid, resolved[pid]) for pid in wanted}
    if args.require_model_iou:
        blocked = [pid for pid, skip in predicted_skip.items() if skip in CANNOT_RUN_MODEL]
        if blocked:
            print(
                "error: incompatible schema / not runnable for frozen decode: "
                + ", ".join(f"{pid}={predicted_skip[pid]}" for pid in blocked),
                file=sys.stderr,
            )
            return EXIT_INCOMPATIBLE_SCHEMA

    needs_weights = any(predicted_skip[pid] is None and pack_needs_model(pid) for pid in wanted)
    extra_cems_ready = any(
        predicted_skip[pid] is None and pid in EMSR_PACK_SPECS for pid in wanted
    )
    weights = Path(args.weights) if args.weights is not None else default_weights()
    model = None
    device = None
    if needs_weights or extra_cems_ready:
        if not weights.is_file():
            print(
                f"error: missing weights {weights} — refusing invented more-data model IoU",
                file=sys.stderr,
            )
            return EXIT_MISSING_WEIGHTS
        import torch

        device = torch.device("cpu")
        model = _load_model(weights, device)

    rows: list[dict[str, Any]] = []
    for pack_id in wanted:
        if pack_id == "US_FIREBENCH_CALDOR_2021":
            rows.append(eval_caldor_bridge(Path(args.caldor_root)))
        elif pack_id == "RCDA_NET":
            rows.append(eval_rcda(Path(args.rcda_root)))
        elif pack_id == "PT_FIRESPRD_SAO_JOAO_PESQUEIRA_2020":
            rows.append(eval_pt_firesprd(Path(args.pt_root)))
        elif pack_id == "CLM_HOLDOUT_V1_TEST":
            if model is None:
                rows.append(
                    empty_pack_row(
                        pack_id,
                        family="clm_holdout_npz",
                        skip_class="covariates_not_ready",
                    )
                )
            else:
                rows.append(
                    eval_clm_holdout(
                        Path(args.holdout_root),
                        model,
                        device,
                        max_patches=int(args.max_holdout_patches),
                    )
                )
        else:
            rows.append(eval_extra_latam_cems(pack_id, Path(args.data_root), model, device))
        print(
            f"{pack_id}: skip={rows[-1].get('skip_class')} "
            f"model_iou={rows[-1].get('model_iou')} "
            f"family={rows[-1].get('family')}"
        )

    extra_mean = extra_family_mean_model_ious(rows)
    holdout_mean = holdout_mean_model_iou(rows)
    weights_rel = rel_to_root(weights) if weights.is_file() else None
    summary = {
        "schema": SCHEMA,
        "as_of_utc": utc_now(),
        "product_id": "extra_data_frozen_decode",
        "claim_class": "additional_more_data_eval",
        "official_latam_complete_proxy_untouched": True,
        "official_json": rel_to_root(OFFICIAL_JSON),
        "sold_as_clm_ensemble_v34": False,
        "sold_as_go_q": False,
        "go_q": "partial",
        "lab_ok_conaf": False,
        "weights": weights_rel,
        "growth_threshold": float(OOD_GROWTH_THRESHOLD),
        "growth_ring_connectivity": int(GROWTH_RING_CONNECTIVITY),
        "min_fire_neighbors": int(GROWTH_RING_MIN_NEIGHBORS),
        "keep_t0": True,
        "require_growth_ring": True,
        "architecture": "residual",
        "target_mode": "delta",
        "extra_latam_cems_mean_model_iou": extra_mean,
        "clm_holdout_mean_model_iou": holdout_mean,
        "mixed_family_mean_model_iou": None,
        "latam_complete_proxy_mean_includes_extra": False,
        "latam_complete_proxy_mean_includes_fep_gra": False,
        "caldor_copy_is_not_catalog_08963": True,
        "official_ids_excluded": list(OFFICIAL_LATAM_COMPLETE_PROXY_IDS),
        "decode_reused_from": "scripts/run_latam_au_complete_model_iou.py",
        "packs": rows,
        "not_claims": list(NOT_CLAIMS),
        "rails": {
            "go_q": "partial",
            "freeze_intact": True,
            "lab_ok_conaf": False,
            "no_retrain": True,
            "no_fp_chain": True,
        },
    }
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    json_path = out_root / "more_data_eval.json"
    json_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    write_scorecard(summary, out_root / "SCORECARD.md")
    print("wrote", json_path)
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
