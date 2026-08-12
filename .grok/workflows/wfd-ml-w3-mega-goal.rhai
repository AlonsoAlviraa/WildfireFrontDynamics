// WildfireFrontDynamics — mega goal: new fires + Tobarra KEEP/KILL + zero target leak
// Invoke: /workflow wfd-ml-w3-mega-goal
// Optional args: #{ skip_train: true, fire: "retuerta_2025" }
// Fixed: no empty agent prompts; sequential lanes (parallel host bug with empty eval)

let meta = #{
    name: "wfd-ml-w3-mega-goal",
    description: "CLOSED 2026-08-05 MET — re-audit only. W3 multi-fire + Tobarra protocol; never ECE thrash holdout TEST; never flip field_ops/ml_product_go",
    when_to_use: "CLOSED MET. Re-run only for multi-fire audit. Tobarra weights settled KILL in wfd-ml-tobarra-keep-or-kill. See docs/goals/README.md",
    phases: [
        #{ title: "Sense", detail: "rails, recipe K1–K5, baselines, W3 artifacts" },
        #{ title: "Lanes", detail: "leak audit · score K1–K5 · expand fire · board" },
        #{ title: "Implement", detail: "fill gaps under kill + zero leak" },
        #{ title: "Adversarial", detail: "attack leak/rails/claims" },
        #{ title: "Goal check", detail: "strict met on C1–C5" },
    ],
};

let skip_train = true;
let extra_fire = "retuerta_2025";
if args != () {
    if args.skip_train != () { skip_train = args.skip_train; }
    if args.fire != () { extra_fire = args.fire; }
}
let skip_s = "true";
if skip_train == false { skip_s = "false"; }
let fire_s = extra_fire;
if type_of(fire_s) != "string" { fire_s = "retuerta_2025"; }

let mega_criterion = "MEGA GOAL MET only if ALL true: "
    + "C1 NEW_FIRE: non-pack fire has align+NPZ+frozen Head A (thr~0.795, no thr fit on that fire). "
    + "C2 TOBARRA_KILL: K1-K5 scorecard KEEP|KILL|INCONCLUSIVE with n_leaked_train_val=0; no thr/ECE on test. "
    + "C3 RAILS: field_ops fusion false; ml_product_go false; no ECE thrash holdout TEST. "
    + "C4 BOARD: multi-fire MD+JSON updated with honesty. "
    + "C5 TESTS: pytest w3/align/kill green. Partial is NOT met.";

let checker_schema = #{
    "type": "object",
    "required": ["met", "reason", "c1", "c2", "c3", "c4", "c5", "gaps"],
    "properties": #{
        "met": #{ "type": "boolean" },
        "reason": #{ "type": "string" },
        "c1": #{ "type": "boolean" },
        "c2": #{ "type": "boolean" },
        "c3": #{ "type": "boolean" },
        "c4": #{ "type": "boolean" },
        "c5": #{ "type": "boolean" },
        "gaps": #{ "type": "array", "items": #{ "type": "string" } },
        "suggestions": #{ "type": "array", "items": #{ "type": "string" } },
    },
};

let lane_schema = #{
    "type": "object",
    "required": ["lane", "ok", "summary", "artifacts"],
    "properties": #{
        "lane": #{ "type": "string" },
        "ok": #{ "type": "boolean" },
        "summary": #{ "type": "string" },
        "artifacts": #{ "type": "array", "items": #{ "type": "string" } },
        "blockers": #{ "type": "array", "items": #{ "type": "string" } },
    },
};

let rails_line = "Rails: NEVER flip field_ops.allow_ml_live_in_fusion or ml_product_go; NEVER fit thr/ECE on holdout U1 TEST or held-out fire TEST; IoU is not ROS.";

log("wfd-ml-w3-mega-goal start skip_train=" + skip_s + " fire=" + fire_s);

// ── Sense ──────────────────────────────────────────────────────────────
phase("Sense");
let sense_p = "WFD W3 MEGA GOAL SENSE. " + rails_line + " "
    + "Collect without inventing metrics: (1) git status -sb brief; "
    + "(2) field_ops.allow_ml_live_in_fusion from config/decision_policies.json; "
    + "(3) ml_product_go from docs/ML_PRODUCT_SCORECARD.json; "
    + "(4) tobarra_finetune_recipe.json kill list + leak; "
    + "(5) lab_loop_v34_w3_expert_latest.json and outputs/ml_eval/w3/* presence for hellin brazatortas retuerta; "
    + "(6) v29_lofo_tobarra metrics/weights; "
    + "(7) run python scripts/score_tobarra_kill_criteria.py and report verdict. "
    + "Return compact markdown only.";
let sense = agent(sense_p, #{ label: "mega-sense", capability_mode: "execute" });
let sense_text = "sense_failed";
if sense != () && sense.success {
    if type_of(sense.output) == "string" {
        if sense.output != "" { sense_text = sense.output; }
    } else {
        sense_text = json_encode(sense.output);
    }
}

// ── Lanes (sequential — avoid empty parallel agent prompts) ────────────
phase("Lanes");

let p_leak = rails_line
    + " LANE LEAK: Verify zero target leak for Tobarra LOFO fold artifacts/clm_ndws_patches/lofo_v1/tobarra_20240802. "
    + "Run python scripts/score_tobarra_kill_criteria.py (writes leak audit) or audit NPZ source labels. "
    + "Ensure outputs/ml_eval/lab_loop/tobarra_leak_audit_latest.json has n_leaked_train_val=0. "
    + "Return JSON schema fields lane=leak ok summary artifacts.";
let lane_leak = agent(p_leak, #{
    label: "lane-leak",
    capability_mode: "execute",
    output_schema: lane_schema,
});

let p_score = rails_line
    + " LANE SCORE K1-K5: Apply recipe kill criteria to v29_lofo_tobarra evaluation_metrics or scorecard. "
    + "Baseline Head A mean IoU ~0.489. Write/refresh outputs/ml_eval/lab_loop/tobarra_kill_scorecard.json "
    + "with KEEP|KILL|INCONCLUSIVE. skip_train=" + skip_s + " so do NOT long-train unless skip is false. "
    + "Return JSON lane=score ok summary artifacts.";
let lane_score = agent(p_score, #{
    label: "lane-score",
    capability_mode: "execute",
    output_schema: lane_schema,
});

let p_fire = rails_line
    + " LANE NEW FIRE: fire_id=" + fire_s + ". "
    + "If outputs/ml_eval/w3/" + fire_s + "/patches and head_a_eval.json exist, verify only. "
    + "Else run python scripts/run_lab_ml_loop_v34_w3_expert.py --fires " + fire_s + " --max-head-a-patches 40. "
    + "Hellin_2024 already may satisfy C1. Return JSON lane=new_fire ok summary artifacts.";
let lane_fire = agent(p_fire, #{
    label: "lane-fire",
    capability_mode: "execute",
    output_schema: lane_schema,
});

let p_board = rails_line
    + " LANE BOARD: Ensure docs/ML_LOOP_ITERATIONS/iter_w3_mega_goal_latest.md and "
    + "outputs/ml_eval/lab_loop/lab_loop_v34_w3_mega_latest.json exist with multi-fire Head A table "
    + "pack Tobarra Cardoso Estrella Hellin Brazatortas Retuerta. Honest CARDOSO approx U1. "
    + "Do not flip go rails. Return JSON lane=board ok summary artifacts.";
let lane_board = agent(p_board, #{
    label: "lane-board",
    capability_mode: "execute",
    output_schema: lane_schema,
});

let lane_blob = "lanes:";
if lane_leak != () && lane_leak.success { lane_blob += " leak=" + json_encode(lane_leak.output); }
if lane_score != () && lane_score.success { lane_blob += " score=" + json_encode(lane_score.output); }
if lane_fire != () && lane_fire.success { lane_blob += " fire=" + json_encode(lane_fire.output); }
if lane_board != () && lane_board.success { lane_blob += " board=" + json_encode(lane_board.output); }
if lane_blob == "lanes:" { lane_blob = "lanes: none_ok"; }

// ── Implement ──────────────────────────────────────────────────────────
phase("Implement");
let impl_p = rails_line
    + " IMPLEMENTER: Close remaining mega gaps. skip_train=" + skip_s + " extra_fire=" + fire_s + ". "
    + "Sense snapshot: " + sense_text + " | " + lane_blob + " | "
    + "Required: tobarra_kill_scorecard.json; tobarra_leak_audit_latest.json n_leaked=0; "
    + "hellin_2024 or " + fire_s + " under outputs/ml_eval/w3/ with head_a; "
    + "pytest tests/test_w3_signal.py tests/test_align_geotiff_stack.py tests/test_tobarra_kill_score.py -q; "
    + "lab_loop_v34_w3_mega_latest.json + iter_w3_mega_goal_latest.md. "
    + "Prefer existing artifacts. Return markdown of actions and paths.";
let impl = agent(impl_p, #{ label: "mega-implement", capability_mode: "execute" });
let impl_text = "implement_failed";
if impl != () && impl.success {
    if type_of(impl.output) == "string" {
        if impl.output != "" { impl_text = impl.output; }
    } else {
        impl_text = json_encode(impl.output);
    }
}

// ── Adversarial ────────────────────────────────────────────────────────
phase("Adversarial");
let adv_p = "Adversarial ML protocol skeptic for WFD. Criterion: " + mega_criterion
    + " Sense: " + sense_text
    + " Implement: " + impl_text
    + " Lanes: " + lane_blob
    + " Read key JSONs if needed. Falsify zero-leak KEEP new-fire claims. "
    + "Flag thr/ECE fit on test field_ops flip IoU-as-ROS. Return markdown attacks survivors residual risks.";
let adv = agent(adv_p, #{ label: "mega-adversarial", capability_mode: "execute" });
let adv_text = "adv_failed";
if adv != () && adv.success {
    if type_of(adv.output) == "string" {
        if adv.output != "" { adv_text = adv.output; }
    } else {
        adv_text = json_encode(adv.output);
    }
}

// ── Goal check ─────────────────────────────────────────────────────────
phase("Goal check");
let chk_p = "STRICT goal checker. Criterion: " + mega_criterion
    + " Evidence sense: " + sense_text
    + " Implement: " + impl_text
    + " Adversarial: " + adv_text
    + " Verify files on disk: kill scorecard leak audit w3 fire dirs. "
    + "met=true ONLY if C1-C5 all true. Fill c1 c2 c3 c4 c5 booleans gaps suggestions reason.";
let check = agent(chk_p, #{
    label: "mega-goal-check",
    capability_mode: "execute",
    output_schema: checker_schema,
});

let met = false;
let reason = "checker failed";
if check != () && check.success && check.output != () {
    if check.output.met != () { met = check.output.met; }
    if check.output.reason != () { reason = check.output.reason; }
}

let met_s = "false";
if met { met_s = "true"; }
let report = "# WFD ML W3 MEGA GOAL\n\n## Met: **" + met_s + "**\n\n## Reason\n\n" + reason
    + "\n\n## Sense\n\n" + sense_text
    + "\n\n## Implement\n\n" + impl_text
    + "\n\n## Adversarial\n\n" + adv_text + "\n";

let write_p = "Write report to docs/ML_LOOP_ITERATIONS/iter_w3_mega_goal_latest.md and refresh "
    + "outputs/ml_eval/lab_loop/lab_loop_v34_w3_mega_latest.json with schema wfd_ml_w3_mega_goal_v1 "
    + "fields met reason rails. Report body follows:\n" + report;
let _w = agent(write_p, #{ label: "mega-write", capability_mode: "execute" });

log("wfd-ml-w3-mega-goal done met=" + met_s + " reason=" + reason);
report
