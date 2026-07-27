let meta = #{
    name: "wfd-autonomous-cycle",
    description: "Autonomous WFD cycle: sense HEAD/scorecard, parallel honesty+CI+dual-product scan, adversarial verify, synthesize report",
    when_to_use: "Continuous integrity/honesty/CI hygiene for WildfireFrontDynamics without human gates",
    phases: [
        #{ title: "Sense", detail: "repo HEAD, gates, policies" },
        #{ title: "Scan", detail: "parallel honesty / CI / dual-product" },
        #{ title: "Verify", detail: "adversarial skeptics per finding" },
        #{ title: "Synthesize", detail: "report + next-graph decision" },
    ],
};

let findings_schema = #{
    "type": "object",
    "required": ["findings", "scanner"],
    "properties": #{
        "scanner": #{ "type": "string" },
        "findings": #{
            "type": "array",
            "maxItems": 8,
            "items": #{
                "type": "object",
                "required": ["id", "severity", "file", "issue", "evidence"],
                "properties": #{
                    "id": #{ "type": "string" },
                    "severity": #{ "type": "string" },
                    "file": #{ "type": "string" },
                    "issue": #{ "type": "string" },
                    "evidence": #{ "type": "string" },
                    "fix_hint": #{ "type": "string" },
                },
            },
        },
        "notes": #{ "type": "string" },
    },
};

let verdict_schema = #{
    "type": "object",
    "required": ["real", "reason", "evidence"],
    "properties": #{
        "real": #{ "type": "boolean" },
        "reason": #{ "type": "string" },
        "evidence": #{ "type": "string" },
        "severity_if_real": #{ "type": "string" },
    },
};

let synth_schema = #{
    "type": "object",
    "required": ["summary", "next_action", "graph_evolve", "report_markdown"],
    "properties": #{
        "summary": #{ "type": "string" },
        "next_action": #{ "type": "string" },
        "graph_evolve": #{ "type": "string" },
        "report_markdown": #{ "type": "string" },
        "confirmed_count": #{ "type": "integer" },
    },
};

let cycle_id = if args == () { "auto" } else if args.cycle_id == () { "auto" } else { args.cycle_id };
log("wfd-autonomous-cycle start cycle_id=" + cycle_id);

// --- Sense ---
phase("Sense");
let sense_prompt = "";
sense_prompt += "You are the Sense node for WildfireFrontDynamics autonomous graph engineering. ";
sense_prompt += "Use tools (read_file, grep, run_terminal_command read-only style). Do NOT invent metrics. ";
sense_prompt += "Collect: (1) git rev-parse HEAD and git status -sb summary, ";
sense_prompt += "(2) docs/ML_PRODUCT_SCORECARD.json gates: u1_test_honest, ml_product_go, allow_ml_live_in_fusion_recommended, primary.model_iou, uncertainty.ece_patch_conf, ";
sense_prompt += "(3) config/decision_policies.json allow_ml_live_in_fusion for field_ops vs research_open, ";
sense_prompt += "(4) whether ruff format --check wildfire_front tests would fail (run it), ";
sense_prompt += "(5) any obvious honesty rail breakage. ";
sense_prompt += "Return a concise markdown status block only — no questions to humans.";
let sense = agent(sense_prompt, #{
    label: "sense",
    capability_mode: "execute",
});
let sense_text = "";
if sense != () && sense.success {
    sense_text = if type_of(sense.output) == "string" { sense.output } else { json_encode(sense.output) };
} else {
    sense_text = "Sense agent failed or empty.";
    log("sense failed open with note");
}

// --- Scan parallel ---
phase("Scan");
let base_ctx = "Repo WildfireFrontDynamics. Dual product: ops front_dynamics_v1 != ML clm_ensemble_v34. ";
base_ctx += "Never invent ROS. Catalog IoU 0.8963 is provenance only. Pitch U1 TEST honest ~0.86 IoU ECE ~0.15. ";
base_ctx += "field_ops.allow_ml_live_in_fusion must stay false unless human promote. research_open fusion is experimental. ";
base_ctx += "Use read_file/grep/run_terminal_command. Read code before claiming. Empty findings only after real inspection. ";
base_ctx += "Sense snapshot:\n" + sense_text + "\n";

let p_honesty = base_ctx;
p_honesty += "SCANNER=honesty_rails. Find honesty/product-claim regressions: optimistic promote paths, ";
p_honesty += "ml_product_go auto-flip, field_ops fusion true, pitch of catalog 0.8963 as live certainty, ";
p_honesty += "ROS invented from ML IoU, missing ABSTAIN paths. Max 8 findings. ";
p_honesty += "Each finding needs id, severity (bug|suggestion|nit), file path, issue, evidence quote/path, fix_hint.";

let p_ci = base_ctx;
p_ci += "SCANNER=ci_surface. Inspect .github/workflows/ci.yml and run: ruff format --check wildfire_front tests; ";
p_ci += "ruff check wildfire_front tests scripts; mypy wildfire_front --ignore-missing-imports if available. ";
p_ci += "Report only failures or fragile CI config. Max 8 findings with evidence.";

let p_dual = base_ctx;
p_dual += "SCANNER=dual_product. Inspect wildfire_front/product/, progressive_burn, decide paths, scripts/run_ml_live_card_demo.py, ";
p_dual += "scripts/run_pilot_honesty_card.py for dual-product boundary violations (ML mask sold as ops ROS, open IF as tactical dispatch). ";
p_dual += "Max 8 findings with evidence.";

let scan_jobs = [
    #{ prompt: p_honesty, label: "scan:honesty", capability_mode: "execute", output_schema: findings_schema },
    #{ prompt: p_ci, label: "scan:ci", capability_mode: "execute", output_schema: findings_schema },
    #{ prompt: p_dual, label: "scan:dual", capability_mode: "execute", output_schema: findings_schema },
];
let scan_results = parallel(scan_jobs);

let findings = [];
let si = 0;
for r in scan_results {
    if r != () && r.success && r.output != () && r.output.findings != () {
        for f in r.output.findings {
            findings.push(f);
        }
    } else {
        log("scan slot " + si.to_string() + " failed or empty");
    }
    si += 1;
}
log("raw findings count=" + findings.len().to_string());

// Cap verification fan-out
let MAX_V = 6;
let to_verify = [];
let vi = 0;
for f in findings {
    if vi < MAX_V {
        to_verify.push(f);
        vi += 1;
    }
}
if findings.len() > MAX_V {
    log("truncated verification from " + findings.len().to_string() + " to " + MAX_V.to_string());
}

if to_verify.len() == 0 {
    let empty_report = "# WFD Autonomous Cycle " + cycle_id + "\n\n## Sense\n\n" + sense_text + "\n\n## Findings\n\nNo scan findings after inspection.\n\n## Next\n\n- next_action: evolve_graph_add_pilot_regression\n- graph_evolve: v1 stable empty-scan; spawn wfd-pilot-regression next\n";
    let p_empty = write_scratch_file("cycle_report.md", empty_report);
    complete(#{
        summary: "No findings; graph should evolve toward pilot regression",
        next_action: "evolve_graph_add_pilot_regression",
        graph_evolve: "v1 empty-scan → add pilot regression graph",
        path: p_empty,
        confirmed: [],
        cycle_id: cycle_id,
    });
}

// --- Verify ---
phase("Verify");
let vjobs = [];
for f in to_verify {
    let vp = "";
    vp += "Adversarially VERIFY this WFD finding. Default real=false unless you independently read evidence. ";
    vp += "Finding: " + json_encode(f) + ". ";
    vp += "Open the file if path given; re-run commands if CI claim. ";
    vp += "real=true only with concrete evidence string (quote, command output, line). ";
    vp += "Reject speculation, style nits without correctness impact, and anything that invents ROS or weakens honesty rails as 'feature'.";
    vjobs.push(#{
        prompt: vp,
        label: "verify",
        capability_mode: "execute",
        output_schema: verdict_schema,
    });
}
let verdicts = parallel(vjobs);

let confirmed = [];
let i = 0;
for v in verdicts {
    if v != () && v.success && v.output != () && v.output.real == true {
        if v.output.evidence != () && v.output.evidence != "" {
            let item = to_verify[i];
            confirmed.push(#{
                finding: item,
                reason: v.output.reason,
                evidence: v.output.evidence,
            });
        }
    }
    i += 1;
}
log("confirmed " + confirmed.len().to_string() + "/" + to_verify.len().to_string());

// --- Synthesize ---
phase("Synthesize");
let sp = "";
sp += "Synthesize WFD autonomous cycle " + cycle_id + ". Write report_markdown for docs/graph_evolution. ";
sp += "Sense:\n" + sense_text + "\n";
sp += "Confirmed findings JSON:\n" + json_encode(confirmed) + "\n";
sp += "Rejected/unverified count: " + (to_verify.len() - confirmed.len()).to_string() + "\n";
sp += "Decide next_action one of: fix_confirmed_locally | evolve_graph_add_pilot_regression | re_run_same | open_pack_audit | idle_monitor_ci. ";
sp += "graph_evolve: one sentence mutation to the graph topology if needed. ";
sp += "summary: 2-4 sentences. confirmed_count integer. No questions to humans. Dual-product honesty preserved.";
let synth = agent(sp, #{
    label: "synthesize",
    capability_mode: "read-only",
    output_schema: synth_schema,
});

let report_md = "# Cycle incomplete synth\n";
let summary = "synth failed";
let next_action = "re_run_same";
let graph_evolve = "retry synth";
let conf_n = confirmed.len();
if synth != () && synth.success && synth.output != () {
    if synth.output.report_markdown != () { report_md = synth.output.report_markdown; }
    if synth.output.summary != () { summary = synth.output.summary; }
    if synth.output.next_action != () { next_action = synth.output.next_action; }
    if synth.output.graph_evolve != () { graph_evolve = synth.output.graph_evolve; }
    if synth.output.confirmed_count != () { conf_n = synth.output.confirmed_count; }
}

let full = "# WFD Autonomous Cycle Report — " + cycle_id + "\n\n" + report_md + "\n\n## Machine fields\n\n";
full += "- next_action: " + next_action + "\n";
full += "- graph_evolve: " + graph_evolve + "\n";
full += "- confirmed_count: " + conf_n.to_string() + "\n";
full += "- summary: " + summary + "\n";
let path = write_scratch_file("cycle_report.md", full);

complete(#{
    summary: summary,
    next_action: next_action,
    graph_evolve: graph_evolve,
    confirmed_count: conf_n,
    confirmed: confirmed,
    path: path,
    cycle_id: cycle_id,
});
