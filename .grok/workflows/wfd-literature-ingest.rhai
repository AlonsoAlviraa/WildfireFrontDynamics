// WFD literature + fuel-stack hygiene cycle
// Re-index corpus, run Rothermel-lite Tobarra demo, keep honesty rails.

let meta = #{
    name: "wfd-literature-ingest",
    description: "Ingest ROS/fuel literature corpus + smoke fuel-terrain + Rothermel-lite Tobarra",
};

fn main(args) {
    let root = args.get("root").or(".");

    // 1) Corpus must exist
    let corpus = agent(#{
        name: "check-corpus",
        prompt: `In repo ${root}: verify data/fire_intel/literature/corpus_v1.json exists and report achieved_n, phase_status from implementation_map, and honesty_rails. Read docs/fire_intel/LITERATURE_CORPUS_ROS_FUEL.md first lines. Return short JSON summary.`,
        capability: "read-only",
    });

    // 2) Fuel stack + physics smoke (local scripts only)
    let smoke = agent(#{
        name: "fuel-stack-smoke",
        prompt: `In repo ${root}: run these commands and report exit codes + key numbers (head ROS, calibration ratio vs Vp 7 if present):
1) python scripts/build_fuel_terrain_stack.py --fire tobarra --with-physics
2) python scripts/run_rothermel_prior.py --abstain-demo
3) pytest tests/test_fuel_rothermel_lite.py -q
Do not invent Vp/ha. Do not flip field_ops ML fusion. Summarize outputs under outputs/fuel_stack/tobarra/.`,
        capability: "execute",
    });

    // 3) Graph STATE note
    let state = agent(#{
        name: "update-state-note",
        prompt: `In repo ${root}: read .grok/graph_engineering/STATE.md. Propose a short markdown patch (do not apply unless file is clearly outdated) describing Graph v4: literature corpus + fuel Rothermel-lite. Keep rails: no invented Vp, ml fusion off. Return the proposed section only.`,
        capability: "read-only",
    });

    return #{
        corpus: corpus,
        smoke: smoke,
        state_proposal: state,
    };
}
