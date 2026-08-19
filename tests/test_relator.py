"""Relator hackathon slice: board, clerk, fiscal, clock. Not a product-gate test."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HACK = Path(__file__).resolve().parents[1] / "hackathon"
if str(HACK) not in sys.path:
    sys.path.insert(0, str(HACK))

from relator.agent import demo_script, handle_event, run_clock  # noqa: E402
from relator.board import cell_status, cited_value, empty_board, quorum  # noqa: E402
from relator.clerk import classify_name, extract_cited_ha  # noqa: E402
from relator.fiscal import compose_briefing, scan_text  # noqa: E402
from relator.maps_grounding import ground_place  # noqa: E402
from relator.render import page  # noqa: E402
from relator.satellites import parse_firms_csv, snapshot_url  # noqa: E402
from relator.scout import ingest_sky_pack  # noqa: E402


def test_inprocess_e2e_clock_passes() -> None:
    from relator.e2e import run_e2e

    report = run_e2e(aoi="nijar")
    assert report["ok"] is True, report.get("failed")
    assert report["llm"] is False
    assert report["n_frames"] == 5


def test_store_roundtrip(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("RELATOR_STORE_DIR", str(tmp_path))
    from relator.store import list_incidents, load_board, save_board

    board = empty_board(incident_id="store_if")
    board["decision"] = "ABSTAIN"
    meta = save_board(board)
    assert meta["ok"] is True
    got = load_board("store_if")
    assert got is not None
    assert got["incident_id"] == "store_if"
    assert "store_if" in list_incidents()


def test_gcp_project_pinned_no_llm() -> None:
    from relator.gcp import PROJECT_ID, settings

    s = settings()
    assert PROJECT_ID == "project-89d8567f-49f2-48bc-a00"
    assert s["project_id"] == PROJECT_ID
    assert s["llm"] is False
    assert "aiplatform.googleapis.com" in s["do_not_enable"]
    assert "run.googleapis.com" in s["apis"]


def test_empty_board_abstains() -> None:
    b = empty_board(incident_id="nijar_demo")
    assert b["decision"] == "ABSTAIN"
    assert b["rails"]["go_q_met"] is False
    assert b["not_tactical_dispatch"] is True
    assert quorum(b)["ready_for_judge"] is False
    assert quorum(b)["firms_alone_is_not_quorum"] is True


def test_firms_alone_still_abstains() -> None:
    b = handle_event(None, {"type": "firms_pulse", "n_hotspots": 12, "aoi": "nijar"})
    assert cell_status(b, "open_sat") == "present"
    assert b["place"]["label"] and "Níjar" in b["place"]["label"]
    assert b["decision"] == "ABSTAIN"
    assert "FIRMS" in (b["cells"]["open_sat"]["note"] or "")
    assert b["judge"]["called"] is False
    assert "burned" in (b["briefing"] or "").lower() or "FIRMS" in (b["briefing"] or "")


def test_jpg_rejected_tif_and_cited_ha() -> None:
    assert classify_name("movil.jpg") == "reject_phone"
    assert classify_name("frente.tif") == "ops_thermal"
    got = extract_cited_ha("EMSR578 rapid mapping. 2169.34 ha cite:emsr578_area_rediam")
    assert got is not None
    assert got["value"] == pytest.approx(2169.34)
    assert got["cite"] == "emsr578_area_rediam"
    assert extract_cited_ha("about 2000 ha somewhere") is None

    b = handle_event(
        None,
        {
            "type": "operator_drop",
            "incident_id": "nijar_demo",
            "files": [
                {"name": "frente.tif"},
                {"name": "movil.jpg"},
                {
                    "name": "cems.txt",
                    "text": "2169.34 ha cite:emsr578_area_rediam",
                },
            ],
        },
    )
    assert cell_status(b, "ops_thermal") == "present"
    assert cited_value(b, "open_official_ha") == pytest.approx(2169.34)
    assert b["clerk"]["jpg_not_enough"] is True
    assert any("JPG" in r["why"] or "Phone" in r["why"] for r in b["clerk"]["rejected"])
    # Thermal is present so the sealed judge *is* called; still not dispatch.
    assert b["rails"]["go_q_met"] is False
    assert b["not_tactical_dispatch"] is True


def test_fiscal_strikes_uncited_ros_ha_go() -> None:
    b = handle_event(None, {"type": "firms_pulse", "n_hotspots": 4, "aoi": "nijar"})
    hits = scan_text("Recommend GO. ROS 8 m/min. Area 4000 ha.", b)
    kinds = {h["kind"] for h in hits}
    assert "ros" in kinds
    assert "ha" in kinds
    assert "go_verb" in kinds

    attacked = handle_event(
        b,
        {"type": "hallucinated_brief", "text": "Recommend GO. ROS 8 m/min. Area 4000 ha."},
    )
    assert attacked["decision"] == "ABSTAIN"
    assert attacked["fiscal"]["forced_abstain"] is True
    assert "⟦STRUCK:uncited⟧" in attacked["briefing"]
    assert cell_status(attacked, "ops_ros") == "struck"


def test_fiscal_allows_cited_numbers_and_go_q_talk() -> None:
    b = empty_board()
    from relator.board import set_cell

    b = set_cell(b, "ops_ros", status="cited", value=6.75, unit="m/min", cite="ops.speed_median")
    b = set_cell(
        b, "open_official_ha", status="cited", value=2169.34, unit="ha", cite="emsr578"
    )
    text = compose_briefing(b)
    assert "6.75" in text and "cite:" in text
    assert scan_text(text, b) == []
    # Product-flag talk must not trip the GO verb.
    assert scan_text("GO_Q is partial. fusion ON ≠ GO. Never GO without a cite.", b) == []


def test_unknown_place_is_not_invented() -> None:
    p = ground_place("atlantis")
    assert p["label"] is None
    assert p["not_tactical_dispatch"] is True


def test_demo_clock_stays_honest() -> None:
    frames = run_clock(demo_script(), incident_id="nijar_demo")
    assert len(frames) == 5
    assert frames[0]["decision"] == "ABSTAIN"
    assert cell_status(frames[1], "open_sat") == "present"
    assert frames[1]["decision"] == "ABSTAIN"
    assert cell_status(frames[2], "ops_thermal") == "present"
    assert cited_value(frames[2], "open_official_ha") == pytest.approx(2169.34)
    assert frames[3]["fiscal"]["forced_abstain"] is True
    assert frames[3]["decision"] == "ABSTAIN"
    assert cell_status(frames[4], "open_sat") == "present"
    assert frames[4]["cells"]["open_sat"]["value"] == 19
    for b in frames:
        assert b["rails"]["go_q_met"] is False
        assert b["not_tactical_dispatch"] is True
    html = page(frames)
    assert "Not tactical dispatch" in html
    assert "struck" in html


def test_gibs_url_and_firms_csv_filter() -> None:
    url = snapshot_url(
        bbox=[-2.4, 36.82, -2.05, 37.08],
        time="2024-06-05",
        layers="VIIRS_SNPP_CorrectedReflectance_TrueColor",
        wrap="day",
    )
    assert "wvs.earthdata.nasa.gov" in url
    assert "TIME=2024-06-05" in url
    csv_text = (
        "latitude,longitude,frp,confidence,acq_date\n"
        "36.95,-2.20,12.5,high,2024-06-05\n"
        "40.0,0.0,1.0,low,2024-06-05\n"
    )
    inside = parse_firms_csv(csv_text, bbox=[-2.4, 36.82, -2.05, 37.08])
    assert len(inside) == 1
    assert inside[0]["lat"] == pytest.approx(36.95)


def test_sky_pack_attaches_chips_without_inventing_ha() -> None:
    board = empty_board(incident_id="nijar_demo")
    pack = {
        "aoi": "nijar",
        "label": "Níjar, Almería — June 2024",
        "place": {"label": "Níjar, Almería, Spain", "cite": "maps_grounding:place/nijar-almeria"},
        "bbox": [-2.4, 36.82, -2.05, 37.08],
        "dates": ["2024-06-05", "2024-06-07"],
        "chips": [
            {
                "role": "true_color",
                "sensor": "VIIRS SNPP",
                "date": "2024-06-05",
                "path": "missing.jpg",
                "cite": "nasa_gibs:true_color:2024-06-05",
            }
        ],
        "n_hotspots": 85,
        "source": "nasa_gibs_worldview",
        "cite": "nasa_gibs:worldview:nijar",
        "query_hash": "abc",
    }
    out = ingest_sky_pack(board, pack)
    assert cell_status(out, "open_sat") == "present"
    assert out["sky"]["chips"][0]["role"] == "true_color"
    assert "chip" in (out["sky"]["look"]["text"] or "").lower()
    assert (out["sky"]["look"] or {}).get("llm") is False
    assert "m/min" not in (out["sky"]["look"]["text"] or "")
    assert cited_value(out, "open_official_ha") is None
    assert out["not_tactical_dispatch"] is True


def test_http_event_roundtrip(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("RELATOR_STORE_DIR", str(tmp_path))
    from relator.server import Handler, _apply

    board = _apply({"type": "clock.start", "incident_id": "http_if"})
    assert board["decision"] == "ABSTAIN"
    assert Handler is not None
    json.dumps(board, default=str)
