let meta = #{
    name: "wfd-open-pack-audit",
    description: "Audit open IF packs AND/EXT/CLM for honesty, offline tests, and dual-product labels",
    when_to_use: "When integrity cycle is clean; expand multi-CCAA pack surface checks",
    phases: [
        #{ title: "Inventory", detail: "list open packs and adapters" },
        #{ title: "Audit", detail: "parallel pack honesty checks" },
        #{ title: "Synthesize", detail: "report + next" },
    ],
};

let findings_schema = #{
    "type": "object",
    "required": ["findings"],
    "properties": #{
        "findings": #{
            "type": "array",
            "maxItems": 10,
            "items": #{
                "type": "object",
                "required": ["pack", "issue", "severity", "evidence"],
                "properties": #{
                    "pack": #{ "type": "string" },
                    "issue": #{ "type": "string" },
                    "severity": #{ "type": "string" },
                    "evidence": #{ "type": "string" },
                },
            },
        },
    },
};

phase("Inventory");
let inv_p = "";
inv_p += "Inventory open IF / CEMS / multi-CCAA packs under data/ and scripts/build_demo_multi_ccaa.py, ";
inv_p += "wildfire_front/open_if if present. List pack ids and whether offline tests exist. Tools only. No human Q.";
let inv = agent(inv_p, #{ label: "inventory", capability_mode: "read-only" });

phase("Audit");
let ap = "";
ap += "Audit open packs for dual-product honesty: no ops ROS claim from open perimeter alone; ABSTAIN/HOLD paths present; ";
ap += "demo multi-CCAA labels honest (U1 TEST not catalog 0.8963 as live fire). Use grep/read_file. ";
ap += "Inventory context: ";
if inv != () && inv.success {
    if type_of(inv.output) == "string" { ap += inv.output; } else { ap += json_encode(inv.output); }
}
ap += " Return findings array max 10.";
let audit = agent(ap, #{ label: "audit-packs", capability_mode: "read-only", output_schema: findings_schema });

phase("Synthesize");
let sp = "";
sp += "Write markdown report of open pack audit findings. Context: ";
if audit != () && audit.success { sp += json_encode(audit.output); } else { sp += "audit failed"; }
sp += " Recommend next_action fix_labels | idle | pilot_regression. No human questions. Output full report as plain text.";
let syn = agent(sp, #{ label: "synth-packs", capability_mode: "read-only" });
let body = "# Open pack audit\n\n";
if syn != () && syn.success {
    if type_of(syn.output) == "string" { body += syn.output; } else { body += json_encode(syn.output); }
} else {
    body += "synth failed\n";
}
let path = write_scratch_file("open_pack_audit.md", body);
complete(#{ path: path, summary: "open pack audit complete" });
