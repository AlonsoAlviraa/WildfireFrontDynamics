let meta = #{
    name: "wfd-fire-intel-scrape",
    description: "Scrape mega-fires ES/FR (X, web/news, optional Reddit) for Tobarra-gap fields; never invent Vp/ha confirmed",
    when_to_use: "Daily/season fire intel; after heatwave peaks; before outreach for new anchors",
    phases: [
        #{ title: "SenseGaps", detail: "Tobarra gold fields vs inventory" },
        #{ title: "FanOut", detail: "parallel web + X + news lanes" },
        #{ title: "Normalize", detail: "fires list + tier T0-T4 + gaps" },
        #{ title: "Write", detail: "update mega_fires JSON/MD + propose anchor stubs" },
    ],
};

let inventory_schema = #{
    "type": "object",
    "required": ["fires", "summary", "report_markdown"],
    "properties": #{
        "fires": #{
            "type": "array",
            "maxItems": 20,
            "items": #{
                "type": "object",
                "required": ["fire_id", "name", "country", "tier", "gaps_vs_tobarra", "priority_for_wfd"],
                "properties": #{
                    "fire_id": #{ "type": "string" },
                    "name": #{ "type": "string" },
                    "country": #{ "type": "string" },
                    "region": #{ "type": "string" },
                    "tier": #{ "type": "string" },
                    "area_ha_press": #{ "type": ["number", "null"] },
                    "area_ha_official": #{ "type": ["number", "null"] },
                    "vp_m_min_official": #{ "type": ["number", "null"] },
                    "gaps_vs_tobarra": #{ "type": "array", "items": #{ "type": "string" } },
                    "priority_for_wfd": #{ "type": "integer" },
                    "source_urls": #{ "type": "array", "items": #{ "type": "string" } },
                    "notes": #{ "type": "string" },
                },
            },
        },
        "summary": #{ "type": "string" },
        "report_markdown": #{ "type": "string" },
        "top_priority_ids": #{ "type": "array", "items": #{ "type": "string" } },
        "next_action": #{ "type": "string" },
    },
};

log("wfd-fire-intel-scrape start");

// --- Sense gaps ---
phase("SenseGaps");
let sense_p = "";
sense_p += "You are SenseGaps for WildfireFrontDynamics fire intel. Read-only. ";
sense_p += "Read data/fire_intel/schema_v1.json and data/infocam_anchors.json and docs/PROJECT_STATUS.md if present. ";
sense_p += "Also read data/fire_intel/mega_fires_2026_es_fr.json if exists. ";
sense_p += "Summarize: (1) Tobarra gold fields we need on other fires, (2) which anchors are confirmed vs pending, ";
sense_p += "(3) which mega fires already listed. DO NOT invent Vp or official ha. Return compact markdown.";
let sense = agent(sense_p, #{ label: "sense-gaps", capability_mode: "read-only" });
let sense_text = "Sense failed";
if sense != () && sense.success {
    sense_text = if type_of(sense.output) == "string" { sense.output } else { json_encode(sense.output) };
}

// --- Fan-out scrape ---
phase("FanOut");
let base = "Season year=2026. Countries Spain + France. Mega-fires only (typically >1000 ha or major evacuations). ";
base += "Honesty: press ha is provisional; NEVER set confirmed Vp without operational parte quote. ";
base += "Tools: web_search, open_page/web_fetch, x_semantic_search, x_keyword_search. Reddit MCP may be down — try web site:reddit.com. ";
base += "SenseGaps:\n" + sense_text + "\n";

let p_es = base;
p_es += "LANE=spain_news_web. Search Spanish mega wildfires July 2026: La Mierla, Burgohondo, Sierra Oeste Madrid, Orés Zaragoza, DSN Miteco. ";
p_es += "Collect fire name, region, press ha (with date), evacuations, URLs. Max 10 fires.";

let p_fr = base;
p_fr += "LANE=france_news_web. Search France wildfires 2026: Gironde Bordeaux Cap Ferret, Landes Biscarrosse, Fontainebleau, Aude. ";
p_fr += "Collect ha press, evacuations, UCPM. Max 8 fires.";

let p_x = base;
p_x += "LANE=x_twitter. Use x_semantic_search and x_keyword_search for incendios España 2026 and incendies France 2026. ";
p_x += "Prefer official accounts (miteco, proteccioncivil, prefets). Extract claims with post ids/URLs.";

let p_sat = base;
p_sat += "LANE=satellite_open. Search EFFIS Copernicus EMS activations Spain France July 2026 burnt area products. ";
p_sat += "Note if open perimeter packs possible for WFD open_if path.";

let lanes = parallel([
    #{ prompt: p_es, label: "lane:es-web", capability_mode: "read-only" },
    #{ prompt: p_fr, label: "lane:fr-web", capability_mode: "read-only" },
    #{ prompt: p_x, label: "lane:x", capability_mode: "read-only" },
    #{ prompt: p_sat, label: "lane:sat", capability_mode: "read-only" },
]);

let lane_blob = "";
let li = 0;
for r in lanes {
    lane_blob += "\n### Lane " + li.to_string() + "\n";
    if r != () && r.success {
        if type_of(r.output) == "string" { lane_blob += r.output; } else { lane_blob += json_encode(r.output); }
    } else {
        lane_blob += "lane failed";
    }
    li += 1;
}

// --- Normalize ---
phase("Normalize");
let np = "";
np += "Normalize mega-fire intel for WFD. Schema tiers: T0 rumor, T1 press, T2 agency open, T3 ops parte, T4 gold stack. ";
np += "Tobarra is the only T4 reference. Press ha NEVER becomes area_ha_official. vp_m_min_official must be null unless explicit parte. ";
np += "Merge duplicate names (e.g. Ávila complex). Fill inventory_schema: fires (max 20), top_priority_ids, next_action, summary, report_markdown. ";
np += "Each fire: fire_id snake_case, gaps_vs_tobarra list, priority_for_wfd 1=highest, source_urls. ";
np += "SenseGaps:\n" + sense_text + "\nLane outputs:\n" + lane_blob;
let inv = agent(np, #{
    label: "normalize-inventory",
    capability_mode: "read-only",
    output_schema: inventory_schema,
});

// --- Write guidance ---
phase("Write");
let wp = "";
wp += "Write agent: produce final report and file update instructions. ";
wp += "You MAY write_file to: data/fire_intel/mega_fires_2026_es_fr.json (full inventory), ";
wp += "docs/fire_intel/MEGA_FIRES_2026_ES_FR.md (human report), ";
wp += "docs/graph_evolution/fire_intel_cycle.md (short cycle note). ";
wp += "If new ES mega-fire priority 1 lacks anchor stub, append pending_external entry instructions for data/infocam_anchors.json ";
wp += "(area_ha null, area_ha_press_provisional only, status pending_external). DO NOT set confirmed. ";
wp += "DO NOT invent Vp. Inventory agent output:\n";
if inv != () && inv.success && inv.output != () {
    wp += json_encode(inv.output);
} else {
    wp += "normalize failed — still write best-effort from lane_blob";
}
wp += "\nLane blob for recovery:\n" + lane_blob;
let writer = agent(wp, #{ label: "write-intel", capability_mode: "read-write" });

let summary = "fire intel incomplete";
let next_action = "manual_review";
let top = [];
if inv != () && inv.success && inv.output != () {
    if inv.output.summary != () { summary = inv.output.summary; }
    if inv.output.next_action != () { next_action = inv.output.next_action; }
    if inv.output.top_priority_ids != () { top = inv.output.top_priority_ids; }
}
if writer != () && writer.success {
    log("write agent finished");
}

complete(#{
    summary: summary,
    next_action: next_action,
    top_priority_ids: top,
    gmail_note: "use wfd-external-unblock for O1 emails after intel",
});
