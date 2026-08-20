"""Pre-registration tests for the RCDA stage-2 sweep."""

from __future__ import annotations

from scripts.push_rcda_paper_stage2_kaggle import (
    STAGE2_RECIPES,
    self_contained_stage2_kernel,
)


def test_stage2_kernel_is_validation_only_and_compiles() -> None:
    source = self_contained_stage2_kernel()
    compile(source, "run_rcda_paper_stage2.py", "exec")
    assert "evaluate_test=False" in source
    assert "compute_paper_metrics=False" in source
    assert '"test_evaluated": False' in source


def test_stage2_preregisters_film_sampling_and_loss_ablations() -> None:
    models = {str(row["model_name"]) for row in STAGE2_RECIPES}
    assert "film_unet" in models
    assert any(row.get("weighted_sampling") is False for row in STAGE2_RECIPES)
    assert any(row.get("event_balance_power") == 1.0 for row in STAGE2_RECIPES)
    assert any(row.get("sampling_strategy") == "uniform_events" for row in STAGE2_RECIPES)
    assert {float(row.get("tversky_beta", 0.7)) for row in STAGE2_RECIPES} >= {
        0.6,
        0.7,
        0.8,
    }
    assert len({str(row["run_name"]) for row in STAGE2_RECIPES}) == len(STAGE2_RECIPES)


def test_sampling_ablations_match_low_lr_leader_except_sampler() -> None:
    recipes = {str(row["run_name"]): row for row in STAGE2_RECIPES}
    leader = recipes["resunet_hybrid_low_lr_v2"]
    for run_name in (
        "resunet_hybrid_event_balanced_v1",
        "resunet_hybrid_uniform_events_v1",
    ):
        candidate = recipes[run_name]
        for key in ("model_name", "target_mode", "lr", "epochs", "patience"):
            assert candidate[key] == leader[key]


def test_growth_low_lr_ablation_matches_leader_except_target() -> None:
    recipes = {str(row["run_name"]): row for row in STAGE2_RECIPES}
    leader = recipes["resunet_hybrid_low_lr_v2"]
    candidate = recipes["resunet_growth_low_lr_v1"]
    for key in ("model_name", "lr", "epochs", "patience"):
        assert candidate[key] == leader[key]
    assert leader["target_mode"] == "hybrid"
    assert candidate["target_mode"] == "growth"


def test_multitask_candidate_is_growth_focused_and_event_uniform() -> None:
    recipes = {str(row["run_name"]): row for row in STAGE2_RECIPES}
    candidate = recipes["resunet_multitask_uniform_events_v1"]

    assert candidate["model_name"] == "resunet_multitask"
    assert candidate["target_mode"] == "multitask"
    assert candidate["sampling_strategy"] == "uniform_events"
    assert float(candidate["growth_loss_weight"]) > float(
        candidate["extent_loss_weight"]
    )
