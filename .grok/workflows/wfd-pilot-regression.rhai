let meta = #{
    name: "wfd-pilot-regression",
    description: "Run pilot honesty + ML card offline regression checks and report failures",
    when_to_use: "After integrity cycle is clean; verify pilot/ML demo surfaces still pass offline",
    phases: [
        #{ title: "Probe", detail: "discover test targets" },
        #{ title: "Execute", detail: "pytest focused suites" },
        #{ title: "Report", detail: "summarize pass/fail" },
    ],
};

let report_schema = #{
    "type": "object",
    "required": ["summary", "passed", "failures", "commands"],
    "properties": #{
        "summary": #{ "type": "string" },
        "passed": #{ "type": "boolean" },
        "failures": #{ "type": "array", "items": #{ "type": "string" } },
        "commands": #{ "type": "array", "items": #{ "type": "string" } },
        "next_action": #{ "type": "string" },
    },
};

phase("Probe");
let probe_p = "";
probe_p += "Locate offline regression entry points in WildfireFrontDynamics. Use list_dir/grep. ";
probe_p += "Find tests matching pilot honesty, ml live card demo, decision card, open pack adapters. ";
probe_p += "Return a short list of pytest nodeids or paths that are safe offline (no network). No human questions.";
let probe = agent(probe_p, #{ label: "probe", capability_mode: "read-only" });

phase("Execute");
let exec_p = "";
exec_p += "Run offline regression for WFD pilot/ML honesty. Prefer: ";
exec_p += "python -m pytest tests/test_pilot_honesty_card.py tests/test_ml_live_card_demo.py tests/test_confidence_product.py -q --tb=line ";
exec_p += "with PYTHONPATH=repo root. On Windows PowerShell use ; not &&. ";
exec_p += "If paths missing, adjust from probe. Capture exit code and last 40 lines of failure. ";
exec_p += "Also run ruff format --check wildfire_front tests. Do not push. Do not edit product policy.";
if probe != () && probe.success {
    exec_p += " Probe notes: ";
    if type_of(probe.output) == "string" {
        exec_p += probe.output;
    } else {
        exec_p += json_encode(probe.output);
    }
}
let ex = agent(exec_p, #{ label: "execute-tests", capability_mode: "execute" });

phase("Report");
let rp = "";
rp += "Summarize pilot regression. Execution agent output:\n";
if ex != () && ex.success {
    if type_of(ex.output) == "string" { rp += ex.output; } else { rp += json_encode(ex.output); }
} else {
    rp += "execute agent failed";
}
rp += "\nSet passed=true only if pytest and ruff format check both succeeded. ";
rp += "next_action: fix_tests | cycle_integrity | idle. No human questions.";
let rep = agent(rp, #{ label: "report", capability_mode: "read-only", output_schema: report_schema });

let summary = "report failed";
let passed = false;
let next_action = "cycle_integrity";
let body = "# Pilot regression\n\n";
if rep != () && rep.success && rep.output != () {
    if rep.output.summary != () { summary = rep.output.summary; }
    if rep.output.passed != () { passed = rep.output.passed; }
    if rep.output.next_action != () { next_action = rep.output.next_action; }
    body += summary + "\n\npassed=" + passed.to_string() + "\nnext_action=" + next_action + "\n";
    body += "\n```json\n" + json_encode(rep.output) + "\n```\n";
}
let path = write_scratch_file("pilot_regression_report.md", body);
complete(#{ summary: summary, passed: passed, next_action: next_action, path: path });
