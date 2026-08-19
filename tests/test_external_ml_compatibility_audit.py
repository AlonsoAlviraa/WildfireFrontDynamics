from __future__ import annotations

import json
from pathlib import Path

from scripts.audit_external_ml_compatibility import build_audit

ROOT = Path(__file__).resolve().parents[1]


def test_external_packs_do_not_promote_incompatible_inputs() -> None:
    report = build_audit(ROOT)
    packs = {row["pack_id"]: row for row in report["packs"]}
    caldor = packs["US_FIREBENCH_CALDOR_2021"]
    assert caldor["label_temporal_compatible"] is True
    assert caldor["input_tensor_semantic_compatible"] is False
    assert caldor["model_inference_allowed"] is False
    assert caldor["sealed_model_iou_allowed"] is False

    pt = packs["PT_FIRESPRD_SAO_JOAO_PESQUEIRA_2020"]
    assert pt["evidence"]["timestamp_tz"] == "unspecified_in_source"
    assert pt["input_tensor_semantic_compatible"] is False
    assert pt["model_inference_allowed"] is False

    proxy = packs["LATAM_AU_EMSR_REAL_PROXY"]
    assert proxy["model_inference_scope"] == "exploratory_proxy_only"
    assert proxy["sealed_model_iou_allowed"] is False


def test_live_proxy_benchmark_reports_copy_comparison() -> None:
    path = ROOT / "outputs/ml_eval/latam_au_complete_iou/complete_proxy_model_iou.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc["n_pairs_measured"] > 0
    assert doc["mean_copy_baseline_iou"] is not None
    assert doc["mean_delta_vs_copy"] is not None
    assert doc["n_pairs_beating_copy"] <= doc["n_pairs_measured"]
