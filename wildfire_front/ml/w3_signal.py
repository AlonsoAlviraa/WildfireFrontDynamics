"""W3 multi-fire honesty + new-signal path (lab ML rail only).

Architectural surface (not ad-hoc scripts)
------------------------------------------
* **Dual rails**: lab ML (``clm_ensemble_v34``) vs field_ops. IoU ≠ ROS.
  ``ml_product_go`` default **True** (human promote 2026-08-05); never auto-flips;
  field fusion stays **OFF** (lab GO ≠ field fusion).
* **Multi-fire honesty first-class**: Tobarra = hard transfer (KEEP reopen sealed);
  W3 external fires = frozen thr/cal **eval-only** probes (report/gate).
* **Shared rank/reject protocol**: features → production calibrator → frozen
  iter1 reject thr (VAL-only) → scorecard. Multi-fire eval delegates **only**
  to ``product_facade`` ``rank_reject`` / ``scorecard`` (no local conf/thr math).
* **Dead thrash paths sealed**: same-holdout ECE retune; Tobarra KEEP re-promote
  of KILL weights / same recipe; ``auto_ml_product_go`` silent thrash
  (explicit promoted true is allowed).

Does not retrain models. Does not retune ECE/thr on holdout TEST or external.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Final

import numpy as np

from wildfire_front.ml.product_facade import (
    DEAD_PATHS,
    DEFAULT_MULTI_FIRE,
    DEFAULT_PRODUCT_ID,
    DEFAULT_RAILS,
    ITER1_LOCKED_REJECT_THR,
    RECOMMENDED_LAB_SURFACE,
    TOBARRA_FIRE_ID,
    W3_EXTERNAL_FIRES,
    ClmEnsembleV34Facade,
    RankRejectConfig,
    assert_lab_rails,
    fire_honesty_tag,
    refuse_dead_path,
)
from wildfire_front.ml.protocol_rails import (
    LAB_ML_BANNER,
    assert_not_forbidden_thrash,
    assert_split_role,
    multi_fire_honesty_dict,
)

_BANNER: Final = LAB_ML_BANNER
_PRODUCT_ID: Final = DEFAULT_PRODUCT_ID
_LOCKED_THR: Final = ITER1_LOCKED_REJECT_THR
_TOBARRA: Final = TOBARRA_FIRE_ID

# Default weather priors for external W3 fires (lab patches only)
_FIRE_WEATHER: dict[str, dict[str, float]] = {
    "hellin_2024": {
        "temp": 36.0,
        "humidity": 20.0,
        "wind_speed": 15.0,
        "wind_dir": 90.0,
        "precip": 0.0,
        "pressure": 1013.0,
        "cloud": 10.0,
        "visibility": 12.0,
        "dew_point": 10.0,
        "ffmc": 86.0,
    },
    "brazatortas_2025": {
        "temp": 28.0,
        "humidity": 35.0,
        "wind_speed": 12.0,
        "wind_dir": 180.0,
        "precip": 0.0,
        "pressure": 1013.0,
        "cloud": 15.0,
        "visibility": 12.0,
        "dew_point": 10.0,
        "ffmc": 78.0,
    },
    "retuerta_2025": {
        "temp": 32.0,
        "humidity": 25.0,
        "wind_speed": 12.0,
        "wind_dir": 200.0,
        "precip": 0.0,
        "pressure": 1013.0,
        "cloud": 10.0,
        "visibility": 12.0,
        "dew_point": 10.0,
        "ffmc": 82.0,
    },
}

# Sources already inside CLM holdout / LOFO pack
_IN_PACK_SOURCES = frozenset(
    {
        "CARDOSO",
        "LA_ESTRELLA_ACOM1",
        "LA_ESTRELLA_ACOM2",
        TOBARRA_FIRE_ID,
    }
)

# External candidates with reprojected LWIR + masks under artifacts/
# Primary honesty catalog = product_facade.W3_EXTERNAL_FIRES; extras are P2 probes.
_EXTERNAL_CANDIDATES: list[dict[str, str]] = [
    {
        "id": "hellin_2024",
        "priority": "P0",
        "lwir_glob": "hellin_2024_reprojected_lwir",
        "masks_glob": "hellin_2024_lwir_masks",
        "note": "W3 external primary (catalog); frozen thr/cal eval-only",
    },
    {
        "id": "brazatortas_2025",
        "priority": "P1",
        "lwir_glob": "brazatortas_2025_reprojected_lwir",
        "masks_glob": "brazatortas_2025_lwir_masks",
        "note": "W3 external catalog; reprojected + masks present",
    },
    {
        "id": "retuerta_2025",
        "priority": "P1",
        "lwir_glob": "retuerta_2025_reprojected_lwir",
        "masks_glob": "retuerta_2025_lwir_masks",
        "note": "W3 external catalog; reprojected + masks present",
    },
    {
        "id": "polan_2025",
        "priority": "P2",
        "lwir_glob": "polan_2025_reprojected_lwir",
        "masks_glob": "polan_2025_lwir_masks",
        "note": "often incomplete masks; not primary honesty catalog",
    },
    {
        "id": "cardoso_2025_lwir_extra",
        "priority": "P2",
        "lwir_glob": "cardoso_2025_reprojected_lwir",
        "masks_glob": "cardoso_2025_lwir_masks",
        "note": "extra LWIR sequences; check non-overlap with CLM CARDOSO pack",
    },
]


# ---------------------------------------------------------------------------
# Shared dual-product rails + multi-fire honesty (architecture, not ad-hoc)
# ---------------------------------------------------------------------------


def w3_lab_rails() -> dict[str, Any]:
    """Canonical lab rails for W3 / Tobarra paths (shared with product facade)."""
    r = assert_lab_rails(DEFAULT_RAILS)
    base = r.as_dict()
    base.update(
        {
            "banner": _BANNER,
            "product_id": _PRODUCT_ID,
            "product_rail": "lab_ml",
            "field_ops_ml_live_fusion": "OFF",
            "no_ece_retune_same_holdout": True,
            "thr_not_retuned_on_external": True,
            "thr_not_retuned_on_tobarra": True,
            "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
            "locked_reject_thr": float(_LOCKED_THR),
            "tobarra_keep_reopen": False,
            "tobarra_keep_reopen_forbidden": True,
            "forbidden_thrash": sorted(DEAD_PATHS),
            "val_only_threshold_selection": True,
        }
    )
    return base


def w3_multi_fire_honesty() -> dict[str, Any]:
    """First-class multi-fire honesty block (Tobarra hard + W3 external)."""
    mf = multi_fire_honesty_dict()
    facade = DEFAULT_MULTI_FIRE.as_dict()
    return {
        **mf,
        **facade,
        "tobarra_hard": True,
        "tobarra_fire_id": _TOBARRA,
        "tobarra_verdict": "KILL",
        "no_tobarra_keep_reopen": True,
        "w3_external_catalog": list(W3_EXTERNAL_FIRES),
        "w3_role": DEFAULT_MULTI_FIRE.w3_role,
        "frozen_thr_and_cal": True,
        "no_ece_retune_same_holdout": True,
        "iou_is_not_ros": True,
        "lab_only": True,
        "note": (
            "Multi-fire honesty is architectural: Tobarra = hard transfer "
            "(KEEP reopen sealed); W3 external = frozen thr/cal eval-only."
        ),
    }


def tobarra_keep_seal() -> dict[str, Any]:
    """Sealed Tobarra KEEP re-promote policy (architecture, not a train hook).

    Documents that KILL weights / same-recipe KEEP reopen are closed dead paths.
    Call :func:`assert_tobarra_keep_reopen_forbidden` when a caller requests reopen.
    """
    return {
        "sealed": True,
        "tobarra_keep_reopen": False,
        "tobarra_keep_verdict": "KILL",
        "re_promote_kill_weights": False,
        "same_recipe_reopen": False,
        "ml_product_go": True,
        "field_ops_allow_ml_live_in_fusion": False,
        "dead_paths": sorted(DEAD_PATHS),
        "forbidden": [
            "tobarra_keep_reopen_same_recipe",
            "tobarra_keep_reopen_kill_weights",
            "tobarra_keep_same_recipe",
            "same_holdout_ece_retune",
            "auto_ml_product_go",
            "ml_product_go_auto_flip",
            "field_ops_ml_live_fusion_on",
        ],
        "note": (
            "Tobarra KEEP re-promote sealed: do not re-open same recipe or "
            "re-promote KILL weights onto product rails. Lab ml_product_go "
            "true (human promote) does not re-open KEEP; field fusion stays OFF."
        ),
    }


def assert_tobarra_keep_reopen_forbidden(*, reopen: bool = False) -> None:
    """Hard-refuse Tobarra KEEP reopen / KILL re-promote when requested."""
    if not reopen:
        return
    refuse_dead_path("tobarra_keep_reopen_same_recipe")
    assert_not_forbidden_thrash("tobarra_keep_reopen_kill_weights")


def assert_w3_eval_only(split: str = "external", action: str = "scorecard") -> None:
    """W3 external / LOFO held-out fire: report-only (never thr/ECE fit)."""
    assert_split_role(str(split), str(action))


def _facade_for_frozen_eval(
    cal: Any,
    *,
    thr: float | None = None,
) -> ClmEnsembleV34Facade:
    """ClmEnsembleV34Facade with frozen VAL iter1 reject thr (default surface)."""
    thr_f = float(_LOCKED_THR if thr is None else thr)
    if abs(thr_f - float(ITER1_LOCKED_REJECT_THR)) < 1e-9:
        return ClmEnsembleV34Facade.with_iter1_locked_thr(cal)
    return ClmEnsembleV34Facade.from_calibrator(
        cal,
        rank_reject_cfg=RankRejectConfig(
            reject_thr=thr_f,
            surface=RECOMMENDED_LAB_SURFACE,
        ),
    )


def _jsonable_rank_reject(surface: dict[str, Any]) -> dict[str, Any]:
    """Drop large arrays from a facade rank_reject surface for JSON packs."""
    skip = {"keep_mask", "conf"}
    out: dict[str, Any] = {}
    for k, v in surface.items():
        if k in skip:
            continue
        if isinstance(v, np.ndarray):
            continue
        out[k] = v
    return out


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _count_files(dir_path: Path, suffixes: tuple[str, ...] = (".tif", ".tiff")) -> int:
    if not dir_path.is_dir():
        return 0
    n = 0
    for p in dir_path.rglob("*"):
        if p.is_file() and p.suffix.lower() in suffixes:
            n += 1
    return n


def _holdout_source_counts(holdout_root: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    if not holdout_root.is_dir():
        return counts
    for split in ("train", "val", "test"):
        d = holdout_root / split
        if not d.is_dir():
            continue
        for p in d.glob("*.npz"):
            src = "unknown"
            try:
                with np.load(p, allow_pickle=True) as z:
                    if "source" in z.files:
                        src = str(z["source"])
                    else:
                        # clm_CARDOSO_000200.npz
                        parts = p.stem.split("_")
                        src = parts[1] if len(parts) >= 2 else p.stem
            except OSError:
                pass
            counts[src] = counts.get(src, 0) + 1
    return counts


def inventory_w3_fires(root: Path) -> dict[str, Any]:
    """Machine inventory: in-pack sources + external READY/PARTIAL/BLOCKED.

    Multi-fire honesty is first-class (Tobarra hard, W3 external catalog).
    """
    art = root / "artifacts"
    holdout = art / "clm_ndws_patches" / "holdout_v1"
    lofo = art / "clm_ndws_patches" / "lofo_v1"
    out_lofo = root / "outputs" / "ml_eval" / "lofo_v1"
    rails = w3_lab_rails()
    multi_fire = w3_multi_fire_honesty()

    in_pack = _holdout_source_counts(holdout)
    lofo_folds: list[dict[str, Any]] = []
    if lofo.is_dir():
        for d in sorted(p for p in lofo.iterdir() if p.is_dir()):
            ha = out_lofo / d.name / "head_a_features.npz"
            honesty = fire_honesty_tag(d.name)
            lofo_folds.append(
                {
                    "fold": d.name,
                    "test_npz": len(list((d / "test").glob("*.npz")))
                    if (d / "test").is_dir()
                    else 0,
                    "head_a_cache": ha.is_file(),
                    "lofo_weights": (out_lofo / d.name / "weights_pretrained_best.pt").is_file(),
                    "honesty": honesty,
                }
            )

    external: list[dict[str, Any]] = []
    for cand in _EXTERNAL_CANDIDATES:
        lwir = art / cand["lwir_glob"]
        masks = art / cand["masks_glob"]
        n_lwir = _count_files(lwir)
        n_masks = _count_files(masks)
        if n_lwir >= 3 and n_masks >= 2:
            status = "READY"
        elif n_lwir >= 1 or n_masks >= 1:
            status = "PARTIAL"
        else:
            status = "BLOCKED"
        in_catalog = cand["id"] in W3_EXTERNAL_FIRES
        honesty = fire_honesty_tag(cand["id"])
        external.append(
            {
                "id": cand["id"],
                "priority": cand["priority"],
                "status": status,
                "n_lwir_tif": n_lwir,
                "n_mask_tif": n_masks,
                "lwir_dir": str(lwir.as_posix()) if lwir.is_dir() else None,
                "masks_dir": str(masks.as_posix()) if masks.is_dir() else None,
                "in_clm_pack": cand["id"].upper().startswith("CARDOSO")
                or cand["id"] in _IN_PACK_SOURCES,
                "in_w3_honesty_catalog": in_catalog,
                "honesty": honesty,
                "eval_only": True,
                "frozen_thr_and_cal": True,
                "note": cand["note"],
                "next_step": (
                    "geotiff_to_training_patches → Head A frozen thr eval-only"
                    if status == "READY"
                    else "fix masks/LWIR or skip"
                ),
            }
        )

    ready_ext = [e for e in external if e["status"] == "READY"]
    # Prefer catalog fires for recommended first signal
    ready_catalog = [e for e in ready_ext if e.get("in_w3_honesty_catalog")]
    recommended = ready_catalog or ready_ext
    return {
        "schema": "w3_fire_inventory_v1",
        "banner": _BANNER,
        "product_id": _PRODUCT_ID,
        "rails": rails,
        "multi_fire_honesty": multi_fire,
        "in_pack": {
            "holdout_root": str(holdout.as_posix()),
            "source_counts": in_pack,
            "n_sources": len(in_pack),
            "hard_fire": _TOBARRA,
            "note": "No more sources inside NPZ pack; new fires need patch pipeline.",
        },
        "lofo_folds": lofo_folds,
        "external_candidates": external,
        "w3_external_catalog": list(W3_EXTERNAL_FIRES),
        "summary": {
            "n_in_pack_sources": len(in_pack),
            "n_external_ready": len(ready_ext),
            "n_external_partial": sum(1 for e in external if e["status"] == "PARTIAL"),
            "n_external_blocked": sum(1 for e in external if e["status"] == "BLOCKED"),
            "recommended_first_fire": recommended[0]["id"] if recommended else None,
            "hard_fire_in_pack": _TOBARRA,
            "tobarra_keep_reopen_sealed": True,
        },
        "kill_list": [
            "ECE post-hoc / Platt / temperature on holdout TEST",
            "Retune reject thr on Tobarra or new-fire test",
            "field_ops fusion ON / auto_ml_product_go silent thrash",
            "Tobarra KEEP reopen / re-promote KILL weights",
        ],
        "tobarra_keep_seal": tobarra_keep_seal(),
    }


def diagnose_tobarra_head_a(
    root: Path,
    *,
    locked_thr: float | None = None,
    low_iou: float = 0.5,
    high_iou: float = 0.8,
) -> dict[str, Any]:
    """Diagnose Tobarra Head A conf vs IoU (frozen production calibrator).

    LOFO held-out report-only: never retunes thr/ECE. Multi-fire eval is
    **only** via ``ClmEnsembleV34Facade.rank_reject`` / ``scorecard`` (shared
    features→calibrator→rank/reject→scorecard path). KEEP reopen sealed.
    """
    from wildfire_front.ml.uncertainty import load_calibrator

    # Architectural: Tobarra LOFO is scorecard/report only; KEEP reopen sealed.
    assert_w3_eval_only("lofo", "scorecard")
    assert_tobarra_keep_reopen_forbidden(reopen=False)
    rails = w3_lab_rails()
    thr = float(_LOCKED_THR if locked_thr is None else locked_thr)

    cache = root / "outputs" / "ml_eval" / "lofo_v1" / _TOBARRA / "head_a_features.npz"
    cal_path = root / "models" / "clm_ensemble" / "uncertainty_calibration_v1.json"
    if not cache.is_file():
        return {
            "schema": "tobarra_head_a_diagnose_v1",
            "ok": False,
            "error": f"missing cache {cache}",
            "rails": rails,
            "multi_fire_honesty": fire_honesty_tag(_TOBARRA),
            "tobarra_keep_seal": tobarra_keep_seal(),
        }
    if not cal_path.is_file():
        return {
            "schema": "tobarra_head_a_diagnose_v1",
            "ok": False,
            "error": f"missing calibrator {cal_path}",
            "rails": rails,
            "tobarra_keep_seal": tobarra_keep_seal(),
        }

    cal = load_calibrator(cal_path)
    with np.load(cache) as z:
        feats = np.asarray(z["features"], dtype=np.float64)
        labels = np.asarray(z["labels"], dtype=np.float64)
        ious = np.asarray(z["ious"], dtype=np.float64)
    # Single product path: facade conf → rank_reject → scorecard (no local thr math)
    facade = _facade_for_frozen_eval(cal, thr=thr)
    pipe = facade.run_pipeline(
        feats,
        ious=ious,
        labels=labels,
        split="lofo",
        fire_id=_TOBARRA,
    )
    conf = np.asarray(pipe["conf"], dtype=np.float64).ravel()
    keep = np.asarray(pipe["keep_mask"], dtype=bool).ravel()
    rr = pipe.get("rank_reject") if isinstance(pipe.get("rank_reject"), dict) else {}
    thr_metrics = (
        rr.get("thr_metrics")
        if isinstance(rr.get("thr_metrics"), dict)
        else rr.get("thr_reject_metrics")
        if isinstance(rr.get("thr_reject_metrics"), dict)
        else {}
    )
    thr_reject = rr.get("thr_reject") if isinstance(rr.get("thr_reject"), dict) else {}
    scorecard = pipe.get("scorecard")
    qs = [0.0, 0.25, 0.5, 0.75, 1.0]
    iquants = [float(x) for x in np.quantile(ious, qs)]
    low_empty = ious < 0.1
    accepted_low = keep & (ious < float(low_iou))
    rejected_high = (~keep) & (ious >= float(high_iou))
    # conf–IoU Pearson
    if conf.std() > 1e-12 and ious.std() > 1e-12:
        corr = float(np.corrcoef(conf, ious)[0, 1])
    else:
        corr = float("nan")

    abstain = thr_metrics.get("abstain_rate", thr_reject.get("abstain_rate"))
    iou_acc = thr_metrics.get("mean_iou_accepted")
    if iou_acc is None:
        iou_acc = float(ious[keep].mean()) if keep.any() else None
    n_accepted = int(keep.sum()) if keep.size else int(thr_reject.get("n_keep") or 0)

    # top fail indices for teaching
    fail_rows: list[dict[str, Any]] = []
    for idx in np.argsort(ious)[:8]:
        fail_rows.append(
            {
                "index": int(idx),
                "iou": float(ious[idx]),
                "conf": float(conf[idx]),
                "accepted": bool(keep[idx]),
                "bucket": "very_low_iou",
            }
        )
    for idx in np.where(accepted_low)[0][:5]:
        fail_rows.append(
            {
                "index": int(idx),
                "iou": float(ious[idx]),
                "conf": float(conf[idx]),
                "accepted": True,
                "bucket": "accepted_low_iou",
            }
        )

    return {
        "schema": "tobarra_head_a_diagnose_v1",
        "ok": True,
        "banner": _BANNER,
        "product_id": _PRODUCT_ID,
        "fire": _TOBARRA,
        "cache": str(cache.as_posix()),
        "calibrator": str(cal_path.as_posix()),
        "locked_thr": thr,
        "thr_source": "val_iter1_reject_frozen",
        "split": "lofo",
        "pipeline": "features→calibrator→rank/reject→scorecard",
        "product_facade": "wildfire_front.ml.product_facade",
        "n_patches": int(ious.size),
        "mean_iou": float(ious.mean()),
        "positive_rate_tau05": float(labels.mean()),
        "iou_quantiles": dict(zip(["q0", "q25", "q50", "q75", "q100"], iquants, strict=True)),
        "frac_iou_lt_0_1": float(low_empty.mean()),
        "frac_iou_gt_0_8": float((ious >= 0.8).mean()),
        "bimodal_hint": bool(iquants[1] < 0.15 and iquants[3] > 0.7),
        "conf": {
            "mean": float(conf.mean()),
            "min": float(conf.min()),
            "max": float(conf.max()),
            "std": float(conf.std()),
            "band_note": "tight band ~0.74–0.81 like other fires",
        },
        "corr_conf_iou": corr,
        "reject_locked": {
            "thr": thr,
            "abstain_rate": float(abstain) if abstain is not None else float("nan"),
            "mean_iou_accepted": float(iou_acc) if iou_acc is not None else None,
            "n_accepted": n_accepted,
            "n_accepted_low_iou": int(accepted_low.sum()),
            "n_rejected_high_iou": int(rejected_high.sum()),
            "surface": RECOMMENDED_LAB_SURFACE,
        },
        "rank_reject": _jsonable_rank_reject(rr),
        "scorecard": scorecard,
        "teaching": {
            "reject_helps": bool(
                keep.any() and float(ious[keep].mean()) > float(ious.mean()) + 0.1
            ),
            "problem": (
                "Hard fire with bimodal IoU; ensemble mean IoU low; "
                "confidence still overconfident in narrow band."
            ),
            "not_the_problem": (
                f"Frozen iter1 reject thr≈{float(ITER1_LOCKED_REJECT_THR):.3f} "
                f"({RECOMMENDED_LAB_SURFACE}) still raises conditional IoU substantially."
            ),
            "next_model_work": [
                "Do not thrash ECE on U1 holdout",
                "Prefer new fires (Hellín) + optional Tobarra finetune with kill criteria",
                "Never re-promote Tobarra KEEP / KILL weights as product",
                "Inspect frac_iou_lt_0_1 for mask/label emptiness vs real growth",
            ],
        },
        "fail_examples": fail_rows,
        "multi_fire_honesty": fire_honesty_tag(_TOBARRA),
        "tobarra_keep_seal": tobarra_keep_seal(),
        "rails": rails,
    }


def build_w3_signal_pack(root: Path) -> dict[str, Any]:
    """W3 signal pack: inventory + Tobarra diagnose on unified multi-fire rails."""
    inv = inventory_w3_fires(root)
    diag = diagnose_tobarra_head_a(root)
    ha = load_json(
        root / "outputs" / "ml_eval" / "lab_loop" / "lab_loop_v34_lofo_head_a_latest.json"
    )
    rails = w3_lab_rails()
    return {
        "schema": "w3_new_signal_pack_v1",
        "banner": _BANNER,
        "product_id": _PRODUCT_ID,
        "inventory": inv,
        "tobarra_diagnose": diag,
        "multi_fire_honesty": w3_multi_fire_honesty(),
        "tobarra_keep_seal": tobarra_keep_seal(),
        "multi_fire_head_a_summary": (ha or {}).get("summary"),
        "recommended_path": {
            "slice_1": "inventory + tobarra diagnose (this pack)",
            "slice_2": inv["summary"].get("recommended_first_fire") or "hellin_2024 if READY",
            "slice_3": (
                "Tobarra finetune only if diagnose not pure label noise; "
                "KEEP reopen sealed — no re-promote of KILL weights"
            ),
            "forbidden": [
                "ECE post-hoc same holdout TEST",
                "Tobarra KEEP reopen same recipe",
                "field_ops fusion ON / auto_ml_product_go silent thrash",
            ],
        },
        "rails": rails,
    }


def w3_fire_dirs(root: Path, fire_id: str) -> dict[str, Path]:
    """Resolve reprojected LWIR / masks / W3 work dirs for a fire id."""
    art = root / "artifacts"
    mapping = {
        "hellin_2024": ("hellin_2024_reprojected_lwir", "hellin_2024_lwir_masks"),
        "brazatortas_2025": (
            "brazatortas_2025_reprojected_lwir",
            "brazatortas_2025_lwir_masks",
        ),
        "retuerta_2025": ("retuerta_2025_reprojected_lwir", "retuerta_2025_lwir_masks"),
        _TOBARRA: ("tobarra_reprojected_lwir", "tobarra_lwir_masks"),
    }
    if fire_id not in mapping:
        # heuristic
        lwir = art / f"{fire_id}_reprojected_lwir"
        masks = art / f"{fire_id}_lwir_masks"
    else:
        lwir = art / mapping[fire_id][0]
        masks = art / mapping[fire_id][1]
    work = root / "outputs" / "ml_eval" / "w3" / fire_id
    return {
        "lwir": lwir,
        "masks": masks,
        "work": work,
        "aligned": work / "aligned",
        "patches": work / "patches",
        "head_a_cache": work / "head_a_features.npz",
        "head_a_eval": work / "head_a_eval.json",
    }


def export_clm_patches_from_aligned(
    images_dir: Path,
    masks_dir: Path,
    output_dir: Path,
    fire_name: str,
    *,
    patch_size: int = 64,
    sequence_length: int = 1,
    max_patches: int | None = None,
    weather: dict[str, float] | None = None,
    start_index: int = 0,
    min_change_fraction: float = 0.02,
) -> dict[str, Any]:
    """Export CLM-compatible NPZ patches (1,17,H,W) from an aligned stack.

    ``min_change_fraction`` drops near-static current≈target windows so Head A
    metrics are not inflated by copy-easy short-Δt drone pairs.
    """
    from wildfire_front.ml.dataset import WildfireDataset

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    weather_data = dict(_FIRE_WEATHER.get(fire_name, _FIRE_WEATHER["hellin_2024"]))
    if weather:
        weather_data.update(weather)

    try:
        dataset = WildfireDataset(
            images_dir=images_dir,
            masks_dir=masks_dir,
            sequence_length=max(int(sequence_length), 1),
            patch_size=int(patch_size),
            weather_data=weather_data,
            max_patches=None,  # filter ourselves
            allow_unaligned_crop=False,
        )
    except ValueError as exc:
        return {
            "ok": False,
            "error": str(exc),
            "images_dir": str(images_dir),
            "masks_dir": str(masks_dir),
            "num_patches": 0,
        }

    written: list[dict[str, Any]] = []
    skipped_static = 0
    idx = int(start_index)
    copy_ious: list[float] = []
    for i in range(len(dataset)):
        sequence, current_fire, target_fire = dataset[i]
        cf = current_fire.numpy().astype(np.float32)
        tf = target_fire.numpy().astype(np.float32)
        change_fraction = float(np.mean((cf >= 0.5) != (tf >= 0.5)))
        inter = float(np.logical_and(cf >= 0.5, tf >= 0.5).sum())
        union = float(np.logical_or(cf >= 0.5, tf >= 0.5).sum())
        copy_iou = float(inter / union) if union > 0 else 1.0
        if change_fraction < float(min_change_fraction):
            skipped_static += 1
            continue
        seq_np = sequence.numpy().astype(np.float32)
        if seq_np.ndim == 4 and seq_np.shape[0] > 1:
            seq_np = seq_np[-1:]
        elif seq_np.ndim == 3:
            seq_np = seq_np[np.newaxis, ...]
        out_path = output_dir / f"clm_{fire_name}_{idx:06d}.npz"
        np.savez_compressed(
            out_path,
            sequence=seq_np,
            current_fire=cf,
            target_fire=tf,
            change_fraction=np.float32(change_fraction),
            source=np.array(fire_name),
        )
        patch_info = dataset.patches[i]
        written.append(
            {
                "file": out_path.name,
                "fire": fire_name,
                "change_fraction": change_fraction,
                "copy_iou": copy_iou,
                "row": patch_info["row"],
                "col": patch_info["col"],
            }
        )
        copy_ious.append(copy_iou)
        idx += 1
        if max_patches is not None and len(written) >= int(max_patches):
            break

    manifest = {
        "ok": len(written) > 0,
        "fire_name": fire_name,
        "images_dir": str(images_dir),
        "masks_dir": str(masks_dir),
        "num_patches": len(written),
        "skipped_static": skipped_static,
        "min_change_fraction": float(min_change_fraction),
        "mean_copy_iou": float(np.mean(copy_ious)) if copy_ious else None,
        "mean_change_fraction": (
            float(np.mean([w["change_fraction"] for w in written])) if written else None
        ),
        "patch_size": patch_size,
        "sequence_length": sequence_length,
        "weather_data": weather_data,
        "patches": written,
    }
    (output_dir / f"manifest_{fire_name}.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return manifest


def align_and_patch_fire(
    root: Path,
    fire_id: str,
    *,
    min_overlap: float = 0.4,
    mode: str = "intersection",
    resolution_m: float | None = None,
    max_side_px: int = 4096,
    patch_size: int = 64,
    sequence_length: int = 1,
    max_patches_per_chain: int | None = 200,
    min_change_fraction: float = 0.02,
    overwrite: bool = True,
) -> dict[str, Any]:
    """W3 slice A: chain-align → CLM NPZ patches for one external fire."""
    from wildfire_front.ml.align_geotiff_stack import align_fire_chains, verify_dir_aligned

    dirs = w3_fire_dirs(root, fire_id)
    if not dirs["lwir"].is_dir() or not dirs["masks"].is_dir():
        return {
            "schema": "w3_align_and_patch_v1",
            "ok": False,
            "fire_id": fire_id,
            "error": f"missing lwir/masks under artifacts for {fire_id}",
            "dirs": {k: str(v) for k, v in dirs.items()},
        }

    if overwrite and dirs["work"].is_dir():
        # Keep work root; clear patches to avoid stale mix
        if dirs["patches"].is_dir():
            shutil.rmtree(dirs["patches"])
        if dirs["aligned"].is_dir():
            shutil.rmtree(dirs["aligned"])

    align = align_fire_chains(
        dirs["lwir"],
        dirs["masks"],
        dirs["aligned"],
        min_overlap=min_overlap,
        min_chain_len=2,
        mode=mode,  # type: ignore[arg-type]
        resolution_m=resolution_m,
        max_side_px=max_side_px,
        overwrite=overwrite,
        pair_fallback=True,
    )
    patch_rows: list[dict[str, Any]] = []
    total = 0
    skipped_static = 0
    start = 0
    copy_ious: list[float] = []
    for ch in align.get("chains") or []:
        if not ch.get("ok"):
            continue
        v = verify_dir_aligned(Path(ch["images_dir"]), Path(ch["masks_dir"]))
        if not v.get("ok"):
            patch_rows.append(
                {
                    "chain_id": ch.get("chain_id"),
                    "ok": False,
                    "error": "post-align verify failed",
                    "verify": v,
                }
            )
            continue
        exp = export_clm_patches_from_aligned(
            Path(ch["images_dir"]),
            Path(ch["masks_dir"]),
            dirs["patches"],
            fire_id,
            patch_size=patch_size,
            sequence_length=sequence_length,
            max_patches=max_patches_per_chain,
            weather=_FIRE_WEATHER.get(fire_id),
            start_index=start,
            min_change_fraction=min_change_fraction,
        )
        n = int(exp.get("num_patches") or 0)
        start += n
        total += n
        skipped_static += int(exp.get("skipped_static") or 0)
        if exp.get("mean_copy_iou") is not None:
            copy_ious.append(float(exp["mean_copy_iou"]))
        patch_rows.append({"chain_id": ch.get("chain_id"), **exp})

    out = {
        "schema": "w3_align_and_patch_v1",
        "ok": total > 0,
        "fire_id": fire_id,
        "banner": _BANNER,
        "align": {
            "ok": align.get("ok"),
            "n_matched_frames": align.get("n_matched_frames"),
            "n_aligned_ok": align.get("n_aligned_ok"),
            "raw_chain_lengths": align.get("raw_chain_lengths"),
            "manifest": str((dirs["aligned"] / "align_manifest.json").as_posix()),
        },
        "patches": {
            "dir": str(dirs["patches"].as_posix()),
            "n_total": total,
            "skipped_static": skipped_static,
            "min_change_fraction": float(min_change_fraction),
            "mean_copy_iou": float(np.mean(copy_ious)) if copy_ious else None,
            "honesty_note": (
                "min_change_fraction filters copy-easy short-Δt windows; "
                "compare mean_copy_iou vs model IoU"
            ),
            "per_chain": patch_rows,
        },
        "rails": {
            **w3_lab_rails(),
            "no_allow_unaligned_crop": True,
        },
        "multi_fire_honesty": fire_honesty_tag(fire_id),
    }
    dirs["work"].mkdir(parents=True, exist_ok=True)
    (dirs["work"] / "align_and_patch.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


def frozen_head_a_eval_on_patches(
    root: Path,
    fire_id: str,
    *,
    product_id: str = DEFAULT_PRODUCT_ID,
    locked_thr: float | None = None,
    max_patches: int = 0,
    device: str | None = None,
) -> dict[str, Any]:
    """Frozen Head A eval on W3 patches (production calibrator + locked thr).

    External multi-fire honesty probe: thr/cal frozen from VAL iter1 reject.
    Rank/reject + scorecard via ``ClmEnsembleV34Facade`` only (no local thr math).
    Never fits calibrator or thr on this fire / holdout TEST.
    """
    from wildfire_front.ml.lab_lofo_head_a import build_fold_head_a_cache
    from wildfire_front.ml.product_catalog import load_predictor_for_product
    from wildfire_front.ml.uncertainty import load_calibrator

    # Architectural: W3 external = eval-only (report/scorecard); no thr fit.
    assert_w3_eval_only("external", "scorecard")
    thr = float(_LOCKED_THR if locked_thr is None else locked_thr)
    rails = w3_lab_rails()
    honesty = fire_honesty_tag(fire_id)

    dirs = w3_fire_dirs(root, fire_id)
    patch_dir = dirs["patches"]
    if not patch_dir.is_dir() or not list(patch_dir.glob("*.npz")):
        return {
            "schema": "w3_head_a_eval_v1",
            "ok": False,
            "fire_id": fire_id,
            "error": f"no patches under {patch_dir}",
            "rails": rails,
            "multi_fire_honesty": honesty,
        }

    cal_path = root / "models" / "clm_ensemble" / "uncertainty_calibration_v1.json"
    if not cal_path.is_file():
        return {
            "schema": "w3_head_a_eval_v1",
            "ok": False,
            "fire_id": fire_id,
            "error": f"missing calibrator {cal_path}",
            "rails": rails,
            "multi_fire_honesty": honesty,
        }

    try:
        predictor = load_predictor_for_product(product_id, device=device)
    except Exception as exc:  # noqa: BLE001
        return {
            "schema": "w3_head_a_eval_v1",
            "ok": False,
            "fire_id": fire_id,
            "error": f"cannot load predictor: {exc}",
            "rails": rails,
            "multi_fire_honesty": honesty,
        }

    cache_path = dirs["head_a_cache"]
    build = build_fold_head_a_cache(
        fold=fire_id,
        test_dir=patch_dir,
        out_path=cache_path,
        predictor=predictor,
        product_id=product_id,
        max_patches=int(max_patches),
    )
    if not build.get("ok"):
        return {
            "schema": "w3_head_a_eval_v1",
            "ok": False,
            "fire_id": fire_id,
            "build": build,
            "rails": rails,
            "multi_fire_honesty": honesty,
        }

    # Single product path: facade features→calibrator→rank/reject→scorecard
    cal = load_calibrator(cal_path)
    facade = _facade_for_frozen_eval(cal, thr=thr)
    with np.load(cache_path) as z:
        feats = np.asarray(z["features"], dtype=np.float64)
        labels = np.asarray(z["labels"], dtype=np.float64)
        ious = np.asarray(z["ious"], dtype=np.float64)
    pipe = facade.run_pipeline(
        feats,
        ious=ious,
        labels=labels,
        split="external",
        fire_id=fire_id,
    )
    conf = np.asarray(pipe["conf"], dtype=np.float64).ravel()
    keep = np.asarray(pipe["keep_mask"], dtype=bool).ravel()
    rr = pipe.get("rank_reject") if isinstance(pipe.get("rank_reject"), dict) else {}
    thr_metrics = (
        rr.get("thr_metrics")
        if isinstance(rr.get("thr_metrics"), dict)
        else rr.get("thr_reject_metrics")
        if isinstance(rr.get("thr_reject_metrics"), dict)
        else {}
    )
    thr_reject = rr.get("thr_reject") if isinstance(rr.get("thr_reject"), dict) else {}
    mean_iou = float(np.mean(ious)) if ious.size else float("nan")
    abstain = thr_metrics.get("abstain_rate", thr_reject.get("abstain_rate"))
    iou_acc = thr_metrics.get("mean_iou_accepted")
    if iou_acc is None and keep.size and keep.any():
        iou_acc = float(ious[keep].mean())
    thr_locked = {
        "thr": thr,
        "abstain_rate": float(abstain) if abstain is not None else float("nan"),
        "mean_iou_accepted": float(iou_acc) if iou_acc is not None else None,
        "keep_rate": thr_metrics.get("keep_rate", thr_reject.get("keep_rate")),
        "n_keep": int(keep.sum()) if keep.size else int(thr_reject.get("n_keep") or 0),
        "ece_full": thr_metrics.get("ece_full", rr.get("ece_full")),
        "surface": RECOMMENDED_LAB_SURFACE,
    }
    # Compatibility surface with prior LOFO Head A eval shape (expert MD table).
    ev: dict[str, Any] = {
        "n_patches": int(ious.size),
        "mean_iou": mean_iou,
        "ece_full": thr_locked.get("ece_full"),
        "thr_locked": thr_locked,
        "locked_thr": thr,
        "default_thr": None,
        "rank_family": "logistic_conf",
        "pipeline": "features→calibrator→rank/reject→scorecard",
        "product_facade": "wildfire_front.ml.product_facade",
        "rank_reject": _jsonable_rank_reject(rr),
        "scorecard": pipe.get("scorecard"),
        "multi_fire_honesty": honesty,
        "cache": str(cache_path.as_posix()),
        "conf_band": {
            "mean": float(conf.mean()) if conf.size else float("nan"),
            "min": float(conf.min()) if conf.size else float("nan"),
            "max": float(conf.max()) if conf.size else float("nan"),
            "std": float(conf.std()) if conf.size else float("nan"),
        },
    }

    # Copy baseline honesty (current→target IoU) on the same patch set
    copy_ious: list[float] = []
    for p in sorted(patch_dir.glob("*.npz"))[
        : int(max_patches) if max_patches and max_patches > 0 else None
    ]:
        with np.load(p) as z:
            if "current_fire" not in z.files or "target_fire" not in z.files:
                continue
            cf = np.asarray(z["current_fire"])
            tf = np.asarray(z["target_fire"])
            inter = float(np.logical_and(cf >= 0.5, tf >= 0.5).sum())
            union = float(np.logical_or(cf >= 0.5, tf >= 0.5).sum())
            copy_ious.append(float(inter / union) if union > 0 else 1.0)
    mean_copy = float(np.mean(copy_ious)) if copy_ious else None
    ev["mean_copy_iou"] = mean_copy
    ev["improvement_vs_copy_iou"] = mean_iou - mean_copy if mean_copy is not None else None
    out = {
        "schema": "w3_head_a_eval_v1",
        "ok": True,
        "fire_id": fire_id,
        "banner": _BANNER,
        "product_id": product_id,
        "locked_thr": thr,
        "thr_source": "val_iter1_reject_frozen",
        "split": "external",
        "pipeline": "features→calibrator→rank/reject→scorecard",
        "product_facade": "wildfire_front.ml.product_facade",
        "calibrator": str(cal_path.as_posix()),
        "build": build,
        "eval": ev,
        "scorecard": pipe.get("scorecard"),
        "note": (
            "Frozen production calibrator + locked thr (iter1 reject); "
            "no ECE/thr fit on this fire or holdout TEST. "
            "W3 external multi-fire honesty probe — report only via "
            "facade.rank_reject/scorecard. "
            "Report IoU vs copy baseline for short-Δt honesty."
        ),
        "multi_fire_honesty": honesty,
        "rails": {
            **rails,
            "thr_not_retuned_on_new_fire": True,
            "eval_only": True,
        },
    }
    dirs["work"].mkdir(parents=True, exist_ok=True)
    dirs["head_a_eval"].write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


def tobarra_finetune_recipe(root: Path) -> dict[str, Any]:
    """Honest Tobarra LOFO finetune recipe with kill criteria and zero target leak.

    Does **not** train by default. Documents protocol + kill gates using existing
    diagnose + v29 LOFO evidence. Never tunes thr/ECE on holdout TEST.

    Architectural seal: Tobarra KEEP re-promote of prior KILL weights / same
    recipe is a dead thrash path (``tobarra_keep_seal``). A *new* LOFO attempt
    may still be documented with kill criteria; it must not silently re-open
    sealed KEEP as product_go.
    """
    assert_w3_eval_only("lofo", "scorecard")
    assert_tobarra_keep_reopen_forbidden(reopen=False)
    keep_seal = tobarra_keep_seal()

    diag = diagnose_tobarra_head_a(root)
    v29 = load_json(root / "docs" / "V29_LOFO_TOBARRA_VERDICT.json") or {}
    lofo_fold = root / "artifacts" / "clm_ndws_patches" / "lofo_v1" / _TOBARRA
    leak = audit_lofo_zero_target_leak(lofo_fold, held_out=_TOBARRA)

    baseline_iou = float(diag.get("mean_iou") or 0.489)
    # Kill criteria (lab KEEP only if all pass — never auto product_go)
    min_delta_vs_baseline = 0.03
    min_delta_vs_copy = 0.05
    max_val_only_ece_fit = True  # ECE fit only on VAL of non-held-out / train folds

    kill_criteria = [
        {
            "id": "K1_test_iou_lift",
            "rule": (
                f"held-out Tobarra mean IoU must improve vs frozen ensemble baseline "
                f"({baseline_iou:.3f}) by >= {min_delta_vs_baseline}"
            ),
            "metric": "test_mean_iou - baseline_mean_iou",
            "threshold": min_delta_vs_baseline,
            "on_fail": "KILL_finetune_weights",
        },
        {
            "id": "K2_beats_copy",
            "rule": (f"improvement_vs_copy_iou on held-out Tobarra >= {min_delta_vs_copy}"),
            "metric": "improvement_vs_copy_iou",
            "threshold": min_delta_vs_copy,
            "on_fail": "KILL_finetune_weights",
        },
        {
            "id": "K3_zero_target_leak",
            "rule": (
                "Tobarra patches never appear in train/val of the LOFO fold; "
                "source label audit must pass"
            ),
            "metric": "n_leaked_train_val",
            "threshold": 0,
            "on_fail": "KILL_protocol_invalid",
        },
        {
            "id": "K4_no_holdout_test_thr_ece",
            "rule": (
                "Never fit reject thr or ECE/Platt/temperature on holdout U1 TEST "
                "or on Tobarra test fold"
            ),
            "metric": "thr_ece_fit_split",
            "allowed": ["train", "val_non_held_out"],
            "on_fail": "KILL_claim",
        },
        {
            "id": "K5_no_field_rails",
            "rule": (
                "ml_product_go true (human promote authorized; no auto_ml_product_go "
                "silent thrash); field_ops.allow_ml_live_in_fusion stays false "
                "(lab GO ≠ field fusion)"
            ),
            "on_fail": "KILL_claim",
        },
        {
            "id": "K6_no_keep_reopen_kill_weights",
            "rule": (
                "Do not re-promote prior KILL weights or reopen sealed same-recipe "
                "KEEP as product path (tobarra_keep_seal)"
            ),
            "metric": "tobarra_keep_reopen",
            "threshold": False,
            "on_fail": "KILL_claim",
        },
    ]

    recipe_steps = [
        f"Use artifacts/clm_ndws_patches/lofo_v1/{_TOBARRA} (train=non-Tobarra, test=Tobarra).",
        "Audit zero target leak (this recipe's leak_audit).",
        "Init from CLM specialist / ensemble member weights (e.g. v28), not from Tobarra-tuned thr.",
        "Train on fold train; early-stop on fold val (non-Tobarra only).",
        "Evaluate once on fold test (Tobarra). Compare to baseline Head A mean IoU + copy Δ.",
        "Apply kill criteria K1–K6. Do not retune thr/ECE on Tobarra test or U1 holdout TEST.",
        "If lab KEEP: store weights under outputs/ml_eval/ as lab-only candidate — not product_go.",
        "Sealed: never re-promote prior KILL weights / same-recipe KEEP onto product rails.",
    ]

    prior_verdict = str(v29.get("verdict") or "KILL").upper()
    prior = {
        "v29_lofo_tobarra": {
            "verdict": v29.get("verdict"),
            "test_iou": v29.get("test_iou"),
            "improvement_vs_copy_iou": v29.get("improvement_vs_copy_iou"),
            "G2_lofo": v29.get("G2_lofo"),
            "weights": v29.get("weights"),
            "note": v29.get("note"),
            "re_promote_forbidden": prior_verdict in ("KILL", "KILL_WEIGHTS", ""),
        },
        "head_a_baseline": {
            "mean_iou": diag.get("mean_iou") if diag.get("ok") else None,
            "ece": None,  # not re-fit here
            "bimodal": diag.get("bimodal_hint") if diag.get("ok") else None,
            "reject_helps": (diag.get("teaching") or {}).get("reject_helps"),
            "locked_thr_not_retuned": True,
        },
    }

    # Decision: finetune needed? (lab research only — KEEP reopen sealed)
    pure_label_noise = bool(
        diag.get("ok")
        and float(diag.get("frac_iou_lt_0_1") or 0) > 0.6
        and float(diag.get("corr_conf_iou") or 0) < 0.1
    )
    recommendation = (
        "SKIP_finetune_fix_labels"
        if pure_label_noise
        else (
            "OPTIONAL_lofo_finetune_with_kill"
            if diag.get("ok") and float(diag.get("mean_iou") or 1) < 0.65
            else "NO_finetune_priority_new_fires"
        )
    )

    rails = w3_lab_rails()
    rails["zero_target_leak_required"] = True

    out = {
        "schema": "w3_tobarra_finetune_recipe_v1",
        "banner": _BANNER,
        "ok": True,
        "product_id": _PRODUCT_ID,
        "fire": _TOBARRA,
        "recommendation": recommendation,
        "pure_label_noise_hint": pure_label_noise,
        "baseline_mean_iou": baseline_iou,
        "kill_criteria": kill_criteria,
        "min_delta_vs_baseline": min_delta_vs_baseline,
        "min_delta_vs_copy": min_delta_vs_copy,
        "max_val_only_ece_fit": max_val_only_ece_fit,
        "recipe_steps": recipe_steps,
        "prior_evidence": prior,
        "leak_audit": leak,
        "diagnose_summary": {
            "ok": diag.get("ok"),
            "mean_iou": diag.get("mean_iou"),
            "bimodal_hint": diag.get("bimodal_hint"),
            "frac_iou_lt_0_1": diag.get("frac_iou_lt_0_1"),
            "corr_conf_iou": diag.get("corr_conf_iou"),
            "reject_helps": (diag.get("teaching") or {}).get("reject_helps"),
        },
        "forbidden": [
            "ECE / Platt / temperature on holdout U1 TEST",
            "Retune reject thr on Tobarra test or U1 TEST",
            "Train patches from Tobarra inside LOFO train/val",
            "field_ops fusion ON / auto_ml_product_go silent thrash",
            "Tobarra KEEP reopen same recipe / re-promote KILL weights",
        ],
        "tobarra_keep_seal": keep_seal,
        "multi_fire_honesty": fire_honesty_tag(_TOBARRA),
        "rails": rails,
    }
    out_path = root / "outputs" / "ml_eval" / "lab_loop" / "tobarra_finetune_recipe.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


def audit_lofo_zero_target_leak(
    fold_dir: Path,
    *,
    held_out: str,
) -> dict[str, Any]:
    """Ensure held-out source never appears in train/val NPZ ``source`` fields."""
    fold_dir = Path(fold_dir)
    if not fold_dir.is_dir():
        return {
            "ok": False,
            "error": f"missing fold dir {fold_dir}",
            "held_out": held_out,
        }
    leaked: list[str] = []
    counts = {"train": 0, "val": 0, "test": 0}
    held_in_test = 0
    foreign_in_test = 0
    for split in ("train", "val", "test"):
        d = fold_dir / split
        if not d.is_dir():
            continue
        for p in d.glob("*.npz"):
            counts[split] = counts.get(split, 0) + 1
            try:
                with np.load(p, allow_pickle=True) as z:
                    src = str(z["source"]) if "source" in z.files else "unknown"
            except OSError:
                src = "unreadable"
            if split in ("train", "val") and src == held_out:
                leaked.append(f"{split}/{p.name}")
            if split == "test":
                if src == held_out:
                    held_in_test += 1
                else:
                    foreign_in_test += 1
    return {
        "ok": len(leaked) == 0 and counts.get("test", 0) > 0,
        "held_out": held_out,
        "fold_dir": str(fold_dir.as_posix()),
        "counts": counts,
        "n_leaked_train_val": len(leaked),
        "leaked_examples": leaked[:20],
        "test_held_out": held_in_test,
        "test_foreign": foreign_in_test,
        "note": "zero target leak = held-out source only in test, never train/val",
    }


def build_w3_expert_pack(
    root: Path,
    *,
    fires: list[str] | None = None,
    run_head_a: bool = True,
    max_patches_per_chain: int | None = 150,
    max_head_a_patches: int = 0,
    device: str | None = None,
) -> dict[str, Any]:
    """Full W3 expert path: align+patch fires, optional Head A, Tobarra recipe.

    Multi-fire honesty first-class: external fires eval-only with frozen thr;
    Tobarra KEEP re-promote sealed.
    """
    inv = inventory_w3_fires(root)
    if fires is None:
        # Prefer honesty catalog fires when READY (Hellín then Brazatortas)
        catalog = set(W3_EXTERNAL_FIRES)
        ready = [
            e["id"]
            for e in inv.get("external_candidates") or []
            if e.get("status") == "READY" and e["id"] in catalog
        ]
        # Stable preference: hellin first among catalog
        prefer = [f for f in ("hellin_2024", "brazatortas_2025", "retuerta_2025") if f in ready]
        fires = prefer or ready or ["hellin_2024"]

    fire_results: dict[str, Any] = {}
    for fid in fires:
        ap = align_and_patch_fire(
            root,
            fid,
            max_patches_per_chain=max_patches_per_chain,
        )
        ha = None
        if run_head_a and ap.get("ok"):
            ha = frozen_head_a_eval_on_patches(
                root,
                fid,
                max_patches=max_head_a_patches,
                device=device,
            )
        fire_results[fid] = {
            "align_and_patch": ap,
            "head_a": ha,
            "honesty": fire_honesty_tag(fid),
        }

    recipe = tobarra_finetune_recipe(root)
    any_patches = any((v.get("align_and_patch") or {}).get("ok") for v in fire_results.values())
    any_ha = any(
        (v.get("head_a") or {}).get("ok") for v in fire_results.values() if v.get("head_a")
    )
    rails = w3_lab_rails()
    return {
        "schema": "w3_expert_pack_v1",
        "banner": _BANNER,
        "product_id": _PRODUCT_ID,
        "fires_requested": fires,
        "fire_results": fire_results,
        "tobarra_recipe": recipe,
        "inventory_summary": inv.get("summary"),
        "multi_fire_honesty": w3_multi_fire_honesty(),
        "tobarra_keep_seal": tobarra_keep_seal(),
        "verdict": {
            "align_patch_ok": any_patches,
            "head_a_ok": any_ha,
            "tobarra_recipe_ok": bool(recipe.get("ok")),
            "tobarra_recommendation": recipe.get("recommendation"),
            "zero_target_leak_ok": (recipe.get("leak_audit") or {}).get("ok"),
            "forbidden_ece_same_holdout": True,
            "tobarra_keep_reopen_sealed": True,
            "field_product": False,
            "ml_product_go": True,
            "field_ops_fusion": "OFF",
            "eval_only_external": True,
        },
        "rails": rails,
    }
