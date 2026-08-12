let meta = #{
    name: "wfd-external-unblock",
    description: "Sense external blockers (anchors, outreach, CyL/GAL calendars) and propose the single next human/email action — not honesty re-scans",
    when_to_use: "When GO_MES is blocked on O1/O2 or GO_Q lacks third-party demo; after integrity is clean",
    phases: [
        #{ title: "Sense", detail: "anchors + plan status + outreach CSV + scorecard" },
        #{ title: "Triage", detail: "rank blockers by unlock value" },
        #{ title: "Action", detail: "one next_action + due date + owner" },
    ],
};

let triage_schema = #{
    "type": "object",
    "required": ["blockers", "top_blocker_id", "next_action", "due_hint", "code_allowed"],
    "properties": #{
        "blockers": #{
            "type": "array",
            "maxItems": 8,
            "items": #{
                "type": "object",
                "required": ["id", "severity", "why", "unlocks"],
                "properties": #{
                    "id": #{ "type": "string" },
                    "severity": #{ "type": "string" },
                    "why": #{ "type": "string" },
                    "unlocks": #{ "type": "string" },
                    "channel": #{ "type": "string" },
                },
            },
        },
        "top_blocker_id": #{ "type": "string" },
        "next_action": #{ "type": "string" },
        "due_hint": #{ "type": "string" },
        "code_allowed": #{ "type": "boolean" },
        "summary": #{ "type": "string" },
        "report_markdown": #{ "type": "string" },
    },
};

log("wfd-external-unblock start");

phase("Sense");
let sense_p = "";
sense_p += "You are Sense for WildfireFrontDynamics EXTERNAL UNBLOCK graph. Read-only. Do NOT invent Vp/ha or ROS. ";
sense_p += "Read and summarize: (1) data/infocam_anchors.json — count status=confirmed vs pending_external; ";
sense_p += "(2) docs/PLAN_3_MESES_STATUS.json go_q_progress + adaptations; ";
sense_p += "(3) docs/ML_PRODUCT_SCORECARD.json gates u1_test_honest + ml_product_go; ";
sense_p += "(4) config/decision_policies.json field_ops.allow_ml_live_in_fusion; ";
sense_p += "(5) docs/CONTACTOS_OUTREACH.csv key CCAA rows (CyL 4082, GAL Extincion, Pablo/GEACAM, REDIAM, RAI); ";
sense_p += "(6) docs/SCORECARD_MES_1.md or docs/PROJECT_STATUS.md if present for GO_MES; ";
sense_p += "(7) docs/O2_HAUSDORFF_BLOCKED.md status. ";
sense_p += "Return a compact markdown snapshot only.";
let sense = agent(sense_p, #{ label: "sense-external", capability_mode: "read-only" });
let sense_text = "Sense failed";
if sense != () && sense.success {
    sense_text = if type_of(sense.output) == "string" { sense.output } else { json_encode(sense.output) };
}

phase("Triage");
let tp = "";
tp += "Triage external blockers for WFD. Sense snapshot:\n" + sense_text + "\n";
tp += "Rules: inventing anchors is FORBIDDEN. Code-only work does not clear O2 national. ";
tp += "As of 2026-08-03 O1 multi-anchor is PASS if Tobarra+Hellin are both status=confirmed in anchors JSON — do NOT treat Cardoso as required for O1. ";
tp += "Priority order: (1) third-party demo+acta (M3.2/GO_Q) if still missing, ";
tp += "(2) eng-close P1: Hellin front_dynamics grade A vs Vp 50 (code_allowed=true), ";
tp += "(3) O2 national perimeter SHP when available, ";
tp += "(4) CyL 4082 wait until ~2026-08-17 no re-spam, ";
tp += "(5) optional 3rd confirmed Vp (Cardoso/Estrella formal parte only — never invent), ";
tp += "(6) Gmail re-auth if MCP dead. ";
tp += "code_allowed=true for Hellin ops pipeline / scorecard honesty / demo polish WITHOUT false claims. ";
tp += "code_allowed=false for inventing Vp/ha or flipping field_ops fusion. ";
tp += "Fill blockers (max 8), top_blocker_id, next_action (one concrete step), due_hint, summary, report_markdown.";
let tri = agent(tp, #{
    label: "triage-external",
    capability_mode: "read-only",
    output_schema: triage_schema,
});

phase("Action");
let report = "# WFD External Unblock\n\n## Sense\n\n" + sense_text + "\n\n";
let next_action = "idle_wait_external";
let summary = "triage failed";
let code_allowed = false;
let top = "unknown";
if tri != () && tri.success && tri.output != () {
    if tri.output.report_markdown != () { report += tri.output.report_markdown; }
    if tri.output.next_action != () { next_action = tri.output.next_action; }
    if tri.output.summary != () { summary = tri.output.summary; }
    if tri.output.code_allowed != () { code_allowed = tri.output.code_allowed; }
    if tri.output.top_blocker_id != () { top = tri.output.top_blocker_id; }
    report += "\n\n## Machine fields\n\n";
    report += "- top_blocker_id: " + top + "\n";
    report += "- next_action: " + next_action + "\n";
    let code_s = "false";
    if code_allowed { code_s = "true"; }
    report += "- code_allowed: " + code_s + "\n";
    if tri.output.due_hint != () { report += "- due_hint: " + tri.output.due_hint + "\n"; }
} else {
    report += "## Triage failed\n";
}

let path = write_scratch_file("external_unblock_report.md", report);
complete(#{
    summary: summary,
    next_action: next_action,
    top_blocker_id: top,
    code_allowed: code_allowed,
    path: path,
});
