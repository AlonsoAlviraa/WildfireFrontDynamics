"""Relator orchestrator: event in → board out. ADK wraps these tools later."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .board import append_event, empty_board, quorum, render_grid
from .clerk import ingest_drop
from .fiscal import compose_briefing, prosecute
from .judge import seal_judgment
from .scout import ingest_firms_pulse


def _refresh_briefing(board: dict[str, Any]) -> dict[str, Any]:
    out = dict(board)
    out["briefing"] = compose_briefing(out)
    out["quorum"] = quorum(out)
    return out


def handle_event(board: dict[str, Any] | None, event: dict[str, Any]) -> dict[str, Any]:
    """Apply one source.arrived / challenge event and re-run judge + fiscal."""
    kind = str(event.get("type") or "")
    state = deepcopy(board) if board else empty_board(
        incident_id=str(event.get("incident_id") or "nijar_demo")
    )

    if kind in ("clock.start", "tick_empty"):
        state = append_event(
            state,
            {
                "type": "clock.start",
                "actor": "relator",
                "summary": "Empty dossier. Relator ABSTAIN.",
            },
        )
    elif kind in ("firms_pulse", "source.firms", "sky_pack"):
        state = ingest_firms_pulse(
            state,
            n_hotspots=int(event.get("n_hotspots") or 0),
            bbox=event.get("bbox"),
            source=str(event.get("source") or "nasa_gibs_worldview"),
            aoi=str(event.get("aoi") or state.get("incident_id") or "nijar"),
            sky=event.get("sky"),
        )
    elif kind in ("pull_sky", "sky.pull"):
        from pathlib import Path

        from .scout import pull_and_ingest

        dest = Path(event.get("dest") or "/tmp/relator_chips")
        try:
            state = pull_and_ingest(
                state,
                aoi=str(event.get("aoi") or state.get("incident_id") or "nijar"),
                dest_dir=dest,
            )
        except Exception as exc:
            state = append_event(
                state,
                {
                    "type": "sky.pull_failed",
                    "actor": "scout",
                    "summary": f"sky pull failed {type(exc).__name__} — FIRMS-only fallback.",
                },
            )
            state = ingest_firms_pulse(
                state,
                n_hotspots=int(event.get("n_hotspots") or 0),
                aoi=str(event.get("aoi") or "nijar"),
            )
    elif kind in ("operator_drop", "source.drop"):
        state = ingest_drop(state, list(event.get("files") or []), work_dir=event.get("work_dir"))
    elif kind in ("hallucinated_brief", "card.challenged"):
        # Inject hostile prose *before* fiscal, as a red-team step.
        state = dict(state)
        state["briefing"] = str(event.get("text") or "")
        state = prosecute(state, briefing=state["briefing"])
        state["quorum"] = quorum(state)
        return state
    elif kind in ("ops_ros_cited", "source.ops_ros"):
        from .board import set_cell

        if event.get("cite") and event.get("value") is not None:
            state = set_cell(
                state,
                "ops_ros",
                status="cited",
                value=float(event["value"]),
                unit="m/min",
                cite=str(event["cite"]),
                source="ops_metrics",
                note="ROS copied from cited operational metrics. Not invented.",
            )
            state = append_event(
                state,
                {
                    "type": "source.arrived",
                    "actor": "clerk",
                    "summary": f"Cited ROS {event['value']} m/min cite:{event['cite']}",
                },
            )
        else:
            state = append_event(
                state,
                {
                    "type": "source.rejected",
                    "actor": "clerk",
                    "summary": "ROS offered without cite — ignored.",
                },
            )
    else:
        state = append_event(
            state,
            {
                "type": "event.ignored",
                "actor": "relator",
                "summary": f"Unknown event type {kind!r} — ignored fail-closed.",
            },
        )
        return _refresh_briefing(state)

    state = seal_judgment(state, policy=str(event.get("policy") or "field_ops"))
    state = _refresh_briefing(state)
    state = prosecute(state, briefing=state.get("briefing"))
    state["quorum"] = quorum(state)
    return state


def run_clock(events: list[dict[str, Any]], *, incident_id: str = "nijar_demo") -> list[dict[str, Any]]:
    board = empty_board(incident_id=incident_id)
    frames = []
    for ev in events:
        ev = dict(ev)
        ev.setdefault("incident_id", incident_id)
        board = handle_event(board, ev)
        frames.append(board)
    return frames


def _demo_sky(aoi: str = "nijar") -> dict[str, Any] | None:
    """Reuse chips already pulled to disk (python -m relator --pull-sky)."""
    from pathlib import Path

    from .satellites import sky_spec

    root = Path(__file__).resolve().parents[2] / "outputs" / "relator_demo" / "chips"
    # package lives at hackathon/relator → parents[2] is repo if PYTHONPATH=hackathon
    # also try repo-relative via cwd
    candidates = [
        root,
        Path("outputs") / "relator_demo" / "chips",
        Path(__file__).resolve().parents[3] / "outputs" / "relator_demo" / "chips",
    ]
    spec = sky_spec(aoi)
    for folder in candidates:
        if not folder.is_dir():
            continue
        chips = []
        for p in sorted(folder.glob(f"{spec['aoi']}_*_sentinel2.jpg")):
            day = p.name.split("_")[1]
            chips.append(
                {
                    "role": "sentinel2",
                    "date": day,
                    "path": str(p.resolve()),
                    "cite": f"sentinel2-l2a:{p.stem}",
                    "sensor": "Sentinel-2 L2A",
                }
            )
        for day in spec["dates"]:
            for role in ("true_color", "swir_false", "thermal"):
                p = folder / f"{spec['aoi']}_{day}_{role}.jpg"
                if p.is_file():
                    chips.append(
                        {
                            "role": role,
                            "date": day,
                            "path": str(p.resolve()),
                            "cite": f"nasa_gibs:{role}:{day}",
                            "sensor": "VIIRS SNPP",
                        }
                    )
        if chips:
            return {
                "aoi": spec["aoi"],
                "label": spec["label"],
                "place": spec["place"],
                "bbox": spec["bbox"],
                "dates": list(spec["dates"]),
                "chips": chips,
                "source": "nasa_gibs_worldview",
                "cite": f"nasa_gibs:worldview:{spec['aoi']}",
                "n_hotspots": None,
                "not_official_burned": True,
            }
    return None


def demo_script(*, aoi: str = "nijar") -> list[dict[str, Any]]:
    """T+0 … T+N clock. Uses real VIIRS chips when --pull-sky has been run."""
    sky = _demo_sky(aoi)
    first_sky = {
        "type": "sky_pack",
        "aoi": aoi,
        "n_hotspots": 12,
        "source": "nasa_gibs_worldview",
        "sky": sky,
    }
    second_sky = {
        "type": "sky_pack",
        "aoi": aoi,
        "n_hotspots": 19,
        "source": "nasa_gibs_worldview",
        "sky": sky,
    }
    return [
        {"type": "clock.start"},
        first_sky,
        {
            "type": "operator_drop",
            "files": [
                {"name": "frente.tif", "content_b64": ""},  # name-only is enough for classify
                {"name": "movil.jpg"},
                {
                    "name": "cems_emsr578.txt",
                    "text": "Copernicus EMSR578 rapid mapping. 2169.34 ha cite:emsr578_area_rediam",
                },
            ],
        },
        {
            "type": "hallucinated_brief",
            "text": "Recommend GO. ROS 8 m/min toward the A-7. Area 4000 ha.",
        },
        second_sky,
    ]


def print_frames(frames: list[dict[str, Any]]) -> str:
    blocks = []
    for i, board in enumerate(frames):
        blocks.append(f"── T+{i} ──\n{render_grid(board)}\n{board.get('briefing')}")
    return "\n\n".join(blocks)
