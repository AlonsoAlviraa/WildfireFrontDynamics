"""España-solo vs con-todo ranking for WFIGS growth IoU. Never opens TEST."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from scipy.ndimage import binary_dilation

from wildfire_front.open_if.regional.base import _atomic_write_json, utc_now

from .wfigs_sellable_gate import (
    DILATED_COPY_EVENT_MACRO,
    HISTORICAL_GATE,
    SELLABLE_DELTA,
    wfigs_dev_is_sellable,
)

COHORT_ESPANA_SOLO = "espana_solo"
COHORT_CON_TODO = "con_todo"
RANKING_SCHEMA = "wfd_wfigs_industry_dual_cohort_ranking_v1"
WFIGS_TENSOR_CONTRACT = "wfigs_256_growth"
CEMS_LABEL_CONTRACT = "cems_delineation_rasters"
# 180 m halo: WFIGS train-selected 3 px at 60 m, scaled to 30 m CEMS rasters.
ESPANA_DILATION_RADIUS_PX = 6

_ESPANA_LABEL_GLOBS = (
    "data/open_if/latam_au/es/*/labels/*.tif",
)


def assert_wfigs_dataset_is_dev_only(dataset_root: Path) -> None:
    """Fail closed if a TEST or confirmation split is present."""

    root = Path(dataset_root)
    if (root / "test.json").is_file():
        raise RuntimeError(f"refusing TEST split at {root / 'test.json'}")
    if (root / "samples" / "test").exists():
        raise RuntimeError(f"refusing TEST sample directory at {root / 'samples' / 'test'}")
    lowered = str(root).lower().replace("\\", "/")
    for token in ("/confirm", "prospective"):
        if token in lowered:
            raise ValueError(f"refusing sealed split root {root}")


def growth_transition_masks(
    previous: np.ndarray,
    target: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """pred-ready true growth: t1 AND NOT t0; previous as bool."""

    prev = np.asarray(previous) > 0.5
    tgt = np.asarray(target) > 0.5
    return prev, np.logical_and(tgt, np.logical_not(prev))


def dilated_copy_growth(previous: np.ndarray, *, radius_px: int) -> np.ndarray:
    """Morphological persistence: dilate t0, then drop already-burned pixels."""

    prev, _true = growth_transition_masks(previous, previous)
    if radius_px < 0:
        raise ValueError("dilation radius must be non-negative")
    if radius_px == 0:
        return np.zeros_like(prev)
    grown = binary_dilation(prev, iterations=int(radius_px))
    return np.logical_and(grown, np.logical_not(prev))


def confusion_from_growth(prediction: np.ndarray, true_growth: np.ndarray) -> dict[str, float | int]:
    pred = np.asarray(prediction, dtype=bool)
    truth = np.asarray(true_growth, dtype=bool)
    tp = int(np.logical_and(pred, truth).sum())
    tn = int(np.logical_and(~pred, ~truth).sum())
    fp = int(np.logical_and(pred, ~truth).sum())
    fn = int(np.logical_and(~pred, truth).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    iou = tp / (tp + fp + fn) if tp + fp + fn else 0.0
    return {
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "iou": iou,
        "event_macro_iou": iou,
        "n_events": 1,
        "n_samples": 1,
        "wfigs_test_loaded": False,
    }


def selected_from_events(per_event: list[dict[str, float | int]]) -> dict[str, float | int]:
    """Pool precision/recall; event-macro IoU is the unweighted event mean."""

    if not per_event:
        raise ValueError("need at least one event to build a selected row")
    tp = sum(int(row["tp"]) for row in per_event)
    tn = sum(int(row["tn"]) for row in per_event)
    fp = sum(int(row["fp"]) for row in per_event)
    fn = sum(int(row["fn"]) for row in per_event)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    pooled_iou = tp / (tp + fp + fn) if tp + fp + fn else 0.0
    event_macro = float(np.mean([float(row["iou"]) for row in per_event]))
    return {
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "iou": pooled_iou,
        "event_macro_iou": event_macro,
        "n_events": len(per_event),
        "n_samples": len(per_event),
        "wfigs_test_loaded": False,
    }


def cohort_row(
    *,
    cohort: str,
    selected: dict[str, Any],
    tensor_contract: str,
    predictor: str,
    wfigs_test_loaded: bool = False,
    notes: str | None = None,
) -> dict[str, Any]:
    if cohort not in {COHORT_ESPANA_SOLO, COHORT_CON_TODO}:
        raise ValueError(f"unknown cohort {cohort!r}")
    if wfigs_test_loaded:
        raise RuntimeError("refusing a cohort row that loaded TEST")
    selected = dict(selected)
    selected.setdefault("wfigs_test_loaded", False)
    sellable = False
    if tensor_contract == WFIGS_TENSOR_CONTRACT:
        sellable = wfigs_dev_is_sellable(selected)
    row = {
        "cohort": cohort,
        "predictor": predictor,
        "tensor_contract": tensor_contract,
        "event_macro_iou": float(selected["event_macro_iou"]),
        "pooled_iou": float(
            selected.get("iou")
            or selected.get("pooled_iou")
            or selected["event_macro_iou"]
        ),
        "precision": float(selected["precision"]),
        "recall": float(selected["recall"]),
        "n_events": int(selected.get("n_events") or 0),
        "sellable": sellable,
        "wfigs_test_loaded": False,
        "delta_vs_dilated_copy": float(selected["event_macro_iou"]) - DILATED_COPY_EVENT_MACRO,
    }
    if notes:
        row["notes"] = notes
    return row


def write_dual_cohort_ranking(
    path: Path,
    *,
    con_todo: dict[str, Any],
    espana_solo: dict[str, Any],
    recipes: list[dict[str, Any]] | None = None,
    winner_name: str | None = None,
) -> dict[str, Any]:
    """Write one ranking artifact with both cohort labels. TEST stays sealed."""

    if con_todo.get("cohort") != COHORT_CON_TODO:
        raise ValueError("con_todo row must use cohort=con_todo")
    if espana_solo.get("cohort") != COHORT_ESPANA_SOLO:
        raise ValueError("espana_solo row must use cohort=espana_solo")
    if con_todo.get("wfigs_test_loaded") or espana_solo.get("wfigs_test_loaded"):
        raise RuntimeError("refusing ranking that loaded TEST")
    document = {
        "schema": RANKING_SCHEMA,
        "generated_at": utc_now(),
        "wfigs_test_loaded": False,
        "confirmation_opened": False,
        "dilated_copy_event_macro_iou": DILATED_COPY_EVENT_MACRO,
        "sellable_delta": SELLABLE_DELTA,
        "historical_gate": HISTORICAL_GATE,
        "cohorts": [con_todo, espana_solo],
        "recipes": list(recipes or []),
        "winner_name": winner_name,
        "promotion_decision": (
            "candidate_for_internal_demo"
            if con_todo.get("sellable")
            else "reject_confirmation_keep_iterating"
        ),
    }
    _atomic_write_json(Path(path), document)
    return document


def _read_binary_tif(path: Path) -> np.ndarray:
    import rasterio

    with rasterio.open(path) as dataset:
        band = dataset.read(1)
    return np.asarray(band) > 0


def discover_espana_label_pairs(repo_root: Path) -> list[dict[str, Any]]:
    """Consecutive CEMS delineation rasters under Spanish LATAM-AU packs."""

    root = Path(repo_root)
    pairs: list[dict[str, Any]] = []
    for pack in sorted((root / "data/open_if/latam_au/es").glob("*")):
        labels = sorted((pack / "labels").glob("*.tif"))
        if len(labels) < 2:
            continue
        event_id = pack.name
        for left, right in zip(labels, labels[1:]):
            pairs.append(
                {
                    "event_id": event_id,
                    "t0": left,
                    "t1": right,
                    "tensor_contract": CEMS_LABEL_CONTRACT,
                }
            )
    return pairs


def score_espana_solo_dilated_copy(
    repo_root: Path,
    *,
    radius_px: int = ESPANA_DILATION_RADIUS_PX,
) -> dict[str, Any]:
    """Score España packs with the same growth IoU formula; no WFIGS TEST."""

    pairs = discover_espana_label_pairs(repo_root)
    if not pairs:
        return cohort_row(
            cohort=COHORT_ESPANA_SOLO,
            selected={
                "event_macro_iou": 0.0,
                "iou": 0.0,
                "precision": 0.0,
                "recall": 0.0,
                "n_events": 0,
                "wfigs_test_loaded": False,
            },
            tensor_contract=CEMS_LABEL_CONTRACT,
            predictor="dilated_copy",
            notes="no Spanish CEMS delineation pairs on disk",
        )
    per_event: dict[str, list[dict[str, float | int]]] = {}
    for pair in pairs:
        previous = _read_binary_tif(pair["t0"])
        target = _read_binary_tif(pair["t1"])
        _prev, true_growth = growth_transition_masks(previous, target)
        prediction = dilated_copy_growth(previous, radius_px=radius_px)
        row = confusion_from_growth(prediction, true_growth)
        per_event.setdefault(str(pair["event_id"]), []).append(row)
    event_rows = []
    for event_id, rows in sorted(per_event.items()):
        merged = selected_from_events(rows)
        merged["event_id"] = event_id
        event_rows.append(merged)
    selected = selected_from_events(event_rows)
    return cohort_row(
        cohort=COHORT_ESPANA_SOLO,
        selected=selected,
        tensor_contract=CEMS_LABEL_CONTRACT,
        predictor="dilated_copy",
        notes=(
            "WFIGS 256² RCDA tensors are absent for Spanish packs; "
            f"growth IoU uses CEMS label rasters with {radius_px} px dilated-copy "
            "(180 m, matching WFIGS 3 px at 60 m). Not the WFIGS sellable gate."
        ),
    )
