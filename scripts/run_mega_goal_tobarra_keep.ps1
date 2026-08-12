# Mega goal: Tobarra LOFO fresh train -> KEEP or KILL (via grok-workflows goal)
# Usage:
#   .\scripts\run_mega_goal_tobarra_keep.ps1
#   .\scripts\run_mega_goal_tobarra_keep.ps1 -Smoke
#   .\scripts\run_mega_goal_tobarra_keep.ps1 -Epochs 10

param(
    [switch]$Smoke,
    [int]$Epochs = 15,
    [string]$Device = "cpu"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
$env:PYTHONPATH = "."

$goalJs = Join-Path $env:USERPROFILE ".grok\installed-plugins\c--users-mariano--grok-tools-grok-workflows-4ad5bf96\skills\goal\scripts\run.mjs"
if (-not (Test-Path $goalJs)) {
    Write-Error "goal harness not found at $goalJs"
}

$smokeS = if ($Smoke) { "true" } else { "false" }

$criterion = @'
MEGA TOBARRA KEEP-OR-KILL MET only if ALL true:
T1 FRESH_RUN: new train under outputs/ml_eval/lofo_tobarra_keep_attempt_* with weights and evaluation_metrics on Tobarra test OR documented TRAIN_BLOCKED (then overall not MET for success path).
T2 ZERO_LEAK: n_leaked_train_val equals 0 on lofo_v1/tobarra_20240802.
T3 KILL_BOARD: scorecard verdict KEEP or KILL (INCONCLUSIVE only if train blocked) with K1-K5 on THIS run metrics; no thr or ECE fit on Tobarra test or U1 TEST. Re-score of v29 alone is NOT enough.
T4 REGRESSION_GUARD: note Cardoso or Hellin IoU; flag drop of 0.03 or more.
T5 RAILS: field_ops fusion false; ml_product_go false; no ECE thrash holdout TEST.
T6 TESTS+BOARD: pytest kill/w3/align green; MD and JSON board with KEEP or KILL.
Partial is NOT met.
'@

$task = @'
In WildfireFrontDynamics repo REPO_ROOT:
Rails immutable: never flip field_ops.allow_ml_live_in_fusion or ml_product_go; never fit thr/ECE on U1 TEST or Tobarra test; IoU is not ROS.

1) Sense rails recipe baselines v29.
2) LEAK: python scripts/score_tobarra_kill_criteria.py
3) TRAIN: python scripts/run_tobarra_lofo_keep_attempt.py --epochs EPOCHS --device DEVICE SMOKE_FLAG
4) SCORE: point kill scorecard at new evaluation_metrics if present; write outputs/ml_eval/lab_loop/tobarra_keep_or_kill_scorecard.json with KEEP or KILL (not INCONCLUSIVE after successful train).
5) BOARD: docs/ML_LOOP_ITERATIONS/iter_tobarra_keep_or_kill_latest.md and lab_loop_v34_tobarra_keep_latest.json
6) pytest tests/test_tobarra_kill_score.py tests/test_w3_signal.py tests/test_align_geotiff_stack.py -q
'@
$task = $task.Replace("REPO_ROOT", $Root).Replace("EPOCHS", "$Epochs").Replace("DEVICE", $Device)
if ($Smoke) {
    $task = $task.Replace("SMOKE_FLAG", "--smoke")
} else {
    $task = $task.Replace("SMOKE_FLAG", "")
}

$arg = $criterion + " :: " + $task
Write-Host "=== MEGA GOAL TOBARRA KEEP-OR-KILL ===" -ForegroundColor Cyan
Write-Host "smoke=$smokeS epochs=$Epochs device=$Device"
& node $goalJs $arg
exit $LASTEXITCODE
