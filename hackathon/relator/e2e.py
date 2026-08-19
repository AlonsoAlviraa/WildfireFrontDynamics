"""In-process Relator clock checks. Used by tests and GET /e2e. No LLM."""

from __future__ import annotations

from typing import Any

from .agent import handle_event, run_clock
from .board import cell_status, cited_value, empty_board


def clock_events(*, aoi: str = "nijar") -> list[dict[str, Any]]:
    return [
        {"type": "clock.start", "incident_id": f"{aoi}_e2e"},
        {"type": "firms_pulse", "aoi": aoi, "n_hotspots": 12, "incident_id": f"{aoi}_e2e"},
        {
            "type": "operator_drop",
            "incident_id": f"{aoi}_e2e",
            "files": [
                {"name": "frente.tif"},
                {"name": "movil.jpg"},
                {"name": "cems.txt", "text": "2169.34 ha cite:emsr578_area_rediam"},
            ],
        },
        {
            "type": "hallucinated_brief",
            "incident_id": f"{aoi}_e2e",
            "text": "Recommend GO. ROS 8 m/min. Area 4000 ha.",
        },
        {"type": "firms_pulse", "aoi": aoi, "n_hotspots": 19, "incident_id": f"{aoi}_e2e"},
    ]


def run_e2e(*, aoi: str = "nijar") -> dict[str, Any]:
    events = clock_events(aoi=aoi)
    frames = run_clock(events, incident_id=f"{aoi}_e2e")
    t0, t1, t2, t3, t4 = frames
    checks = {
        "t0_abstain": t0.get("decision") == "ABSTAIN",
        "t1_sat_present": cell_status(t1, "open_sat") == "present",
        "t1_still_abstain": t1.get("decision") == "ABSTAIN",
        "t1_place": bool((t1.get("place") or {}).get("label")),
        "t2_tif_accepted": cell_status(t2, "ops_thermal") == "present",
        "t2_jpg_rejected": bool((t2.get("clerk") or {}).get("jpg_not_enough")),
        "t2_ha_cited": cited_value(t2, "open_official_ha") == 2169.34,
        "t3_fiscal_struck": bool((t3.get("fiscal") or {}).get("forced_abstain")),
        "t3_abstain": t3.get("decision") == "ABSTAIN",
        "t4_hotspots_19": (t4.get("cells") or {}).get("open_sat", {}).get("value") == 19,
        "no_llm": all((f.get("rails") or {}).get("no_llm") for f in frames),
        "not_dispatch": all(f.get("not_tactical_dispatch") is True for f in frames),
        "go_q_false": all((f.get("rails") or {}).get("go_q_met") is False for f in frames),
    }
    ok = all(checks.values())
    return {
        "ok": ok,
        "llm": False,
        "aoi": aoi,
        "checks": checks,
        "failed": [k for k, v in checks.items() if not v],
        "steps": [
            {
                "t": i,
                "decision": f.get("decision"),
                "reason": f.get("decision_reason"),
                "sat": cell_status(f, "open_sat"),
                "thermal": cell_status(f, "ops_thermal"),
                "ha": cited_value(f, "open_official_ha"),
                "fiscal": (f.get("fiscal") or {}).get("forced_abstain"),
            }
            for i, f in enumerate(frames)
        ],
        "last": frames[-1],
        "n_frames": len(frames),
    }


def apply_event(incident_id: str, event: dict[str, Any], board: dict[str, Any] | None) -> dict[str, Any]:
    ev = dict(event)
    ev.setdefault("incident_id", incident_id)
    return handle_event(board or empty_board(incident_id=incident_id), ev)
