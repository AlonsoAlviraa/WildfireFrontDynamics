let meta = #{
    name: "wfd-status-sync",
    description: "Regenerate plan status + metrics hub + reliability gate from live repo evidence (no claim inflation)",
    when_to_use: "Weekly or after product commits; keep PLAN_3_MESES_STATUS and METRICS_HUB fresh",
    phases: [
        #{ title: "Execute", detail: "run_plan_cycle --execute-m1" },
        #{ title: "Verify", detail: "sanity-check gates and holdout conf caps" },
        #{ title: "Report", detail: "summarize drift" },
    ],
};

let report_schema = #{
    "type": "object",
    "required": ["summary", "ok", "next_action"],
    "properties": #{
        "summary": #{ "type": "string" },
        "ok": #{ "type": "boolean" },
        "next_action": #{ "type": "string" },
        "issues": #{ "type": "array", "items": #{ "type": "string" } },
    },
};

log("wfd-status-sync start");

phase("Execute");
let exec_p = "";
exec_p += "In WildfireFrontDynamics repo root, run these with PYTHONPATH=repo (PowerShell use ; not &&):\n";
exec_p += "1) python scripts/run_plan_cycle.py --execute-m1\n";
exec_p += "2) If build_metrics_hub already ran via execute-m1, skip; else python scripts/build_metrics_hub.py\n";
exec_p += "Capture exit codes and last 30 lines. Do not push. Do not flip ml_product_go or field_ops fusion.";
let ex = agent(exec_p, #{ label: "run-status-scripts", capability_mode: "execute" });

phase("Verify");
let vp = "";
vp += "Verify status honesty after sync. Read: docs/PLAN_3_MESES_STATUS.json, docs/METRICS_HUB.json, ";
vp += "docs/FIRE_DECISION_CARD.json, docs/ML_PRODUCT_SCORECARD.json, config/decision_policies.json. ";
vp += "Fail if: holdout conf or holdout_quality > 0.75 on shipped card; ml_product_go true without human; ";
vp += "field_ops.allow_ml_live_in_fusion true; catalog 0.8963 claimed as live certainty in card reasons. ";
vp += "Execution notes:\n";
if ex != () && ex.success {
    if type_of(ex.output) == "string" { vp += ex.output; } else { vp += json_encode(ex.output); }
} else {
    vp += "execute failed";
}
vp += "\nReturn ok, summary, next_action (idle|fix_status|run_external_unblock), issues list.";
let rep = agent(vp, #{
    label: "verify-status",
    capability_mode: "read-only",
    output_schema: report_schema,
});

let summary = "verify failed";
let ok = false;
let next_action = "fix_status";
if rep != () && rep.success && rep.output != () {
    if rep.output.summary != () { summary = rep.output.summary; }
    if rep.output.ok != () { ok = rep.output.ok; }
    if rep.output.next_action != () { next_action = rep.output.next_action; }
}

complete(#{
    summary: summary,
    ok: ok,
    next_action: next_action,
});
