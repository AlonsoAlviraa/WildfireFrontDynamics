"""Tests for GCP stage-2 telemetry parsing."""

from __future__ import annotations

from scripts.run_rcda_gcp_stage2_nightwatch import parse_running_progress


def test_progress_parser_combines_latest_epoch_and_best_val_checkpoint() -> None:
    progress = parse_running_progress(
        [
            "[resunet seed=0] epoch 4 loss=0.6105 val_f1=0.1823",
            "[resunet seed=0] epoch 5 loss=0.6070 val_f1=0.2160",
            "BEST 5 0.15534215201717377 0.9",
        ]
    )
    assert progress["checkpoint_epoch"] == 5
    assert progress["best_checkpoint_epoch"] == 5
    assert progress["train_loss"] == 0.607
    assert progress["val_f1_at_0_5"] == 0.216
    assert progress["val_event_macro_iou"] == 0.15534215201717377
    assert progress["val_selection_threshold"] == 0.9


def test_progress_parser_accepts_scientific_notation() -> None:
    progress = parse_running_progress(["BEST 3 1.4e-1 1e-1"])
    assert progress["val_event_macro_iou"] == 0.14
    assert progress["val_selection_threshold"] == 0.1

