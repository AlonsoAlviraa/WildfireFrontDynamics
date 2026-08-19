"""Scientific rails for the RCDA paper-tuning Kaggle job."""

from __future__ import annotations

from scripts.push_rcda_paper_kaggle import TUNING_RECIPES, self_contained_tune_kernel


def test_paper_tuning_kernel_is_validation_only_and_compiles() -> None:
    source = self_contained_tune_kernel()
    compile(source, "run_rcda_paper_tune.py", "exec")
    assert "evaluate_test=False" in source
    assert '"test_evaluated": False' in source
    assert '"selection_split": "val"' in source
    assert '"selection_metric": "event_macro_iou"' in source


def test_paper_tuning_recipes_cover_objective_and_context_ablations() -> None:
    modes = {str(row["target_mode"]) for row in TUNING_RECIPES}
    models = {str(row["model_name"]) for row in TUNING_RECIPES}
    assert modes == {"growth", "extent", "hybrid"}
    assert {"unet", "aspp_unet", "resunet"} <= models
    assert len({str(row["run_name"]) for row in TUNING_RECIPES}) == len(TUNING_RECIPES)
