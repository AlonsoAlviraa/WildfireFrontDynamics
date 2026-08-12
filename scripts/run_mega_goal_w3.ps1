# Mega goal W3: new fires + Tobarra K1-K5 + zero target leak (via grok-workflows goal)
# Usage:
#   .\scripts\run_mega_goal_w3.ps1
#   .\scripts\run_mega_goal_w3.ps1 -AllowTrain
#   .\scripts\run_mega_goal_w3.ps1 -Fire retuerta_2025

param(
    [switch]$AllowTrain,
    [string]$Fire = "retuerta_2025"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
$env:PYTHONPATH = "."

$goalJs = Join-Path $env:USERPROFILE ".grok\installed-plugins\c--users-mariano--grok-tools-grok-workflows-4ad5bf96\skills\goal\scripts\run.mjs"
if (-not (Test-Path $goalJs)) {
    Write-Error "goal harness not found at $goalJs - install grok-workflows plugin"
}

$skipTrain = if ($AllowTrain) { "false" } else { "true" }

# Single-quoted here-strings: no PowerShell expansion of braces / $ except we inject via -f carefully
$criterion = @'
MEGA GOAL MET only if ALL true:
C1 NEW_FIRE: At least one fire NOT in the set CARDOSO LA_ESTRELLA_ACOM1 LA_ESTRELLA_ACOM2 tobarra_20240802 has aligned LWIR chains plus NPZ patches plus frozen Head A eval JSON thr lock about 0.795 production cal no thr or ECE fit on that fire. Prefer hellin_2024 and/or FIRE_PLACEHOLDER.
C2 TOBARRA_KILL: Scorecard applies K1-K5 from outputs/ml_eval/lab_loop/tobarra_finetune_recipe.json to either a fresh LOFO train on lofo_v1/tobarra_20240802 or re-score of v29_lofo_tobarra with explicit KEEP or KILL or INCONCLUSIVE; leak_audit n_leaked_train_val equals 0; never thr or ECE fit on Tobarra test or holdout U1 TEST.
C3 RAILS: config field_ops.allow_ml_live_in_fusion is false; ml_product_go is false; no same-holdout ECE post-hoc improvement claims.
C4 BOARD: docs/ML_LOOP_ITERATIONS report plus lab_loop JSON updated with multi-fire table and honesty CARDOSO approx U1 Tobarra hard.
C5 TESTS: pytest green for tests/test_w3_signal.py tests/test_align_geotiff_stack.py and tests/test_tobarra_kill_score.py.
Partial progress is NOT met.
'@
$criterion = $criterion.Replace("FIRE_PLACEHOLDER", $Fire)

$task = @'
In WildfireFrontDynamics repo root REPO_ROOT:
Implement mega goal W3 expert path. Rails immutable: never flip field_ops.allow_ml_live_in_fusion or ml_product_go; never fit reject thr or ECE/Platt/temp on holdout U1 TEST or held-out fire TEST; IoU is not ROS.

1) Sense existing outputs/ml_eval/lab_loop/tobarra_finetune_recipe.json lab_loop_v34_w3_expert_latest.json outputs/ml_eval/w3/* and run python scripts/score_tobarra_kill_criteria.py
2) NEW FIRE: ensure hellin_2024 and/or FIRE_ID have align plus patches plus head_a via scripts/run_lab_ml_loop_v34_w3_expert.py or align_lwir_common_grid.py. skip_train=SKIP_TRAIN.
3) LEAK: write or verify outputs/ml_eval/lab_loop/tobarra_leak_audit_latest.json with n_leaked_train_val equals 0 for lofo_v1/tobarra_20240802.
4) SCORE: write outputs/ml_eval/lab_loop/tobarra_kill_scorecard.json applying K1-K5 to v29_lofo_tobarra and/or a new train if skip_train is false and needed.
5) BOARD: docs/ML_LOOP_ITERATIONS/iter_w3_mega_goal_latest.md plus outputs/ml_eval/lab_loop/lab_loop_v34_w3_mega_latest.json.
6) pytest tests/test_w3_signal.py tests/test_align_geotiff_stack.py tests/test_tobarra_kill_score.py -q.

Prefer existing artifacts over re-running heavy inference. Be honest if KEEP is only from prior v29 metrics vs K1 baseline.
'@
$task = $task.Replace("REPO_ROOT", $Root).Replace("FIRE_ID", $Fire).Replace("SKIP_TRAIN", $skipTrain)

$arg = $criterion + " :: " + $task
Write-Host "=== MEGA GOAL W3 ===" -ForegroundColor Cyan
Write-Host "goal.mjs: $goalJs"
Write-Host "skip_train: $skipTrain  fire=$Fire"
Write-Host "Invoking goal harness multi-agent may take long..."

# Pass as single argument to node
& node $goalJs $arg
$code = $LASTEXITCODE
Write-Host "goal exit code: $code"
exit $code
