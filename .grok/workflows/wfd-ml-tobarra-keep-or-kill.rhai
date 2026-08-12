// WildfireFrontDynamics — mega goal: Tobarra LOFO fresh train → KEEP or KILL
// Prior: W3 mega MET with INCONCLUSIVE on v29 re-score only
// Invoke: /workflow wfd-ml-tobarra-keep-or-kill
// Args: #{ smoke: true, max_epochs: 5, device: "cpu" }

let meta = #{
    name: "wfd-ml-tobarra-keep-or-kill",
    description: "CLOSED 2026-08-05 KILL — re-audit/smoke only. Fresh Tobarra LOFO + K1-K5; never ECE thrash U1 TEST; never flip field_ops/ml_product_go",
    when_to_use: "CLOSED: scientific KILL (IoU 0.4776). Re-run only for smoke/audit — do not thrash KEEP without new signal. See docs/goals/README.md",
    phases: [
        #{ title: "Sense", detail: "rails, fold, baseline, recipe, v29 prior" },
        #{ title: "Leak", detail: "re-audit zero target leak" },
        #{ title: "Train", detail: "LOFO train on non-Tobarra; eval Tobarra test once" },
        #{ title: "Score", detail: "K1-K5 KEEP or KILL; regression Cardoso/Hellin" },
        #{ title: "Check", detail: "strict T1-T6 met" },
    ],
};

let smoke = false;
let max_epochs = 15;
let device = "cpu";
if args != () {
    if args.smoke != () { smoke = args.smoke; }
    if args.max_epochs != () { max_epochs = args.max_epochs; }
    if args.device != () { device = args.device; }
}
let smoke_s = "false";
if smoke { smoke_s = "true"; }
let epochs_s = "" + max_epochs;
let device_s = "" + device;
if type_of(device) == "string" { device_s = device; }

let mega_criterion = "MEGA TOBARRA KEEP-OR-KILL MET only if ALL true: "
    + "T1 FRESH_RUN: new train dir under outputs/ml_eval/lofo_tobarra_keep_attempt_* with weights + evaluation_metrics on Tobarra test "
    + "OR documented TRAIN_BLOCKED with hard reason (then overall BLOCKED not MET). "
    + "T2 ZERO_LEAK: n_leaked_train_val=0 on lofo_v1/tobarra_20240802. "
    + "T3 KILL_BOARD: scorecard verdict KEEP or KILL (INCONCLUSIVE only if train blocked) with K1-K5 on THIS run metrics; no thr/ECE fit on Tobarra test or U1 TEST. "
    + "T4 REGRESSION_GUARD: Cardoso or Hellin IoU not silently collapsed by >=0.03 without note. "
    + "T5 RAILS: field_ops fusion false; ml_product_go false; no ECE thrash holdout TEST. "
    + "T6 TESTS+BOARD: pytest kill/w3/align green; MD+JSON board with KEEP/KILL. "
    + "Re-score of v29 alone is NOT enough for MET.";

let checker_schema = #{
    "type": "object",
    "required": ["met", "reason", "t1", "t2", "t3", "t4", "t5", "t6", "verdict", "gaps"],
    "properties": #{
        "met": #{ "type": "boolean" },
        "reason": #{ "type": "string" },
        "t1": #{ "type": "boolean" },
        "t2": #{ "type": "boolean" },
        "t3": #{ "type": "boolean" },
        "t4": #{ "type": "boolean" },
        "t5": #{ "type": "boolean" },
        "t6": #{ "type": "boolean" },
        "verdict": #{ "type": "string" },
        "gaps": #{ "type": "array", "items": #{ "type": "string" } },
        "suggestions": #{ "type": "array", "items": #{ "type": "string" } },
    },
};

let rails_line = "Rails: NEVER flip field_ops.allow_ml_live_in_fusion or ml_product_go; NEVER fit thr/ECE on holdout U1 TEST or Tobarra test; IoU is not ROS; catalog 0.8963 provenance only.";

log("wfd-ml-tobarra-keep-or-kill start smoke=" + smoke_s + " epochs=" + epochs_s + " device=" + device_s);

// ── Sense ──────────────────────────────────────────────────────────────
phase("Sense");
let sense_p = "WFD TOBARRA KEEP-OR-KILL SENSE. " + rails_line + " "
    + "Read: config field_ops fusion; ML_PRODUCT_SCORECARD ml_product_go; "
    + "tobarra_finetune_recipe.json baselines; tobarra_kill_scorecard.json prior verdict; "
    + "lofo_v1/tobarra_20240802 train/val/test counts; v29_lofo_tobarra metrics; "
    + "scripts/run_tobarra_lofo_keep_attempt.py if exists else run_clm_lofo_all_folds.py. "
    + "Return compact markdown. Do not train yet.";
let sense = agent(sense_p, #{ label: "tk-sense", capability_mode: "execute" });
let sense_text = "sense_failed";
if sense != () && sense.success {
    if type_of(sense.output) == "string" {
        if sense.output != "" { sense_text = sense.output; }
    } else {
        sense_text = json_encode(sense.output);
    }
}

// ── Leak ───────────────────────────────────────────────────────────────
phase("Leak");
let leak_p = rails_line + " LEAK: Run python scripts/score_tobarra_kill_criteria.py to refresh leak audit, "
    + "or audit NPZ sources under artifacts/clm_ndws_patches/lofo_v1/tobarra_20240802. "
    + "Confirm n_leaked_train_val=0. Return markdown with counts.";
let leak = agent(leak_p, #{ label: "tk-leak", capability_mode: "execute" });
let leak_text = "leak_failed";
if leak != () && leak.success {
    if type_of(leak.output) == "string" {
        if leak.output != "" { leak_text = leak.output; }
    } else {
        leak_text = json_encode(leak.output);
    }
}

// ── Train ──────────────────────────────────────────────────────────────
phase("Train");
let train_p = rails_line + " TRAIN: Fresh Tobarra LOFO attempt. smoke=" + smoke_s
    + " max_epochs=" + epochs_s + " device=" + device_s + ". "
    + "Use scripts/run_tobarra_lofo_keep_attempt.py if present with --epochs " + epochs_s
    + " (add --smoke if smoke true). Else adapt run_clm_lofo_all_folds for held=tobarra_20240802 only. "
    + "Data: artifacts/clm_ndws_patches/lofo_v1/tobarra_20240802 (train=non-Tobarra, test=Tobarra). "
    + "Write under outputs/ml_eval/lofo_tobarra_keep_attempt_<utc>/ and copy/link evaluation_metrics + weights "
    + "to outputs/ml_eval/lofo_tobarra_keep_attempt_latest/. "
    + "Do NOT use Tobarra test for early-stop thr or ECE fit. Early-stop on fold val only. "
    + "If train impossible, write TRAIN_BLOCKED.json with reason. Return paths and key metrics.";
let train = agent(train_p, #{ label: "tk-train", capability_mode: "execute" });
let train_text = "train_failed";
if train != () && train.success {
    if type_of(train.output) == "string" {
        if train.output != "" { train_text = train.output; }
    } else {
        train_text = json_encode(train.output);
    }
}

// ── Score ──────────────────────────────────────────────────────────────
phase("Score");
let score_p = rails_line + " SCORE: Apply K1-K5 to THIS run metrics (not only v29). "
    + "Prefer outputs/ml_eval/lofo_tobarra_keep_attempt_latest/evaluation_metrics.json. "
    + "Baseline Head A Tobarra mean IoU 0.489. "
    + "Write outputs/ml_eval/lab_loop/tobarra_keep_or_kill_scorecard.json with verdict KEEP or KILL "
    + "(INCONCLUSIVE only if TRAIN_BLOCKED). "
    + "Also note Cardoso/Hellin regression if available (T4). "
    + "Run pytest tests/test_tobarra_kill_score.py tests/test_w3_signal.py -q. "
    + "Update docs/ML_LOOP_ITERATIONS/iter_tobarra_keep_or_kill_latest.md and "
    + "outputs/ml_eval/lab_loop/lab_loop_v34_tobarra_keep_latest.json. "
    + "Sense was: " + sense_text + " Train was: " + train_text;
let score = agent(score_p, #{ label: "tk-score", capability_mode: "execute" });
let score_text = "score_failed";
if score != () && score.success {
    if type_of(score.output) == "string" {
        if score.output != "" { score_text = score.output; }
    } else {
        score_text = json_encode(score.output);
    }
}

// ── Check ──────────────────────────────────────────────────────────────
phase("Check");
let chk_p = "STRICT checker. Criterion: " + mega_criterion
    + " Evidence sense: " + sense_text
    + " Leak: " + leak_text
    + " Train: " + train_text
    + " Score: " + score_text
    + " Verify files on disk. met=true ONLY if T1-T6 all true. "
    + "INCONCLUSIVE after successful train is NOT met. Fill t1..t6 met reason verdict gaps suggestions.";
let check = agent(chk_p, #{
    label: "tk-check",
    capability_mode: "execute",
    output_schema: checker_schema,
});

let met = false;
let reason = "checker failed";
let verdict = "UNKNOWN";
if check != () && check.success && check.output != () {
    if check.output.met != () { met = check.output.met; }
    if check.output.reason != () { reason = check.output.reason; }
    if check.output.verdict != () { verdict = check.output.verdict; }
}

let met_s = "false";
if met { met_s = "true"; }
let report = "# WFD Tobarra KEEP-OR-KILL MEGA GOAL\n\n## Met: **" + met_s
    + "**\n\n## Verdict: **" + verdict + "**\n\n## Reason\n\n" + reason
    + "\n\n## Sense\n\n" + sense_text
    + "\n\n## Train\n\n" + train_text
    + "\n\n## Score\n\n" + score_text + "\n";

let write_p = "Write the following to docs/ML_LOOP_ITERATIONS/iter_tobarra_keep_or_kill_latest.md "
    + "and merge key fields into outputs/ml_eval/lab_loop/lab_loop_v34_tobarra_keep_latest.json. Body:\n" + report;
let _w = agent(write_p, #{ label: "tk-write", capability_mode: "execute" });

log("wfd-ml-tobarra-keep-or-kill done met=" + met_s + " verdict=" + verdict);
report
