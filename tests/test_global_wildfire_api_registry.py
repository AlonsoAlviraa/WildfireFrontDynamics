from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "research" / "global_wildfire_api_registry_2026.json"


def _registry() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def test_global_api_registry_has_unique_complete_sources() -> None:
    data = _registry()
    assert data["schema"] == "wfd_global_wildfire_api_registry_v1"
    assert len(data["sources"]) >= 30
    ids = [source["id"] for source in data["sources"]]
    assert len(ids) == len(set(ids))
    required = {
        "id",
        "name",
        "provider",
        "geography",
        "roles",
        "signals",
        "interface",
        "auth",
        "licence",
        "priority",
        "score",
        "recommended_use",
        "blockers",
        "docs_url",
        "probe",
    }
    for source in data["sources"]:
        assert required <= set(source), source["id"]
        assert source["priority"] in {"P0", "P1", "P2", "P3"}
        assert 0 <= source["score"] <= 25
        assert source["roles"]
        assert source["signals"]


def test_registry_keeps_hotspots_and_context_out_of_progression_labels() -> None:
    data = _registry()
    by_id = {source["id"]: source for source in data["sources"]}
    for source_id in (
        "global_nasa_firms_area",
        "global_nasa_eonet_v3",
        "au_dea_hotspots",
        "africa_afis",
        "global_openaq_v3",
    ):
        assert "progression_label" not in by_id[source_id]["roles"]


def test_public_probe_urls_do_not_embed_secret_parameters() -> None:
    secret_names = {"api_key", "apikey", "key", "token", "access_token", "map_key"}
    for source in _registry()["sources"]:
        probe = source.get("probe")
        if not probe:
            continue
        query_names = {name.lower() for name in parse_qs(urlparse(probe["url"]).query)}
        assert not query_names & secret_names, source["id"]
        if probe.get("auth_required"):
            assert probe.get("auth_env") or source["id"] == "global_opentopography"


def test_registry_has_world_spanning_operational_roles() -> None:
    data = _registry()
    p0 = [source for source in data["sources"] if source["priority"] == "P0"]
    roles = {role for source in p0 for role in source["roles"]}
    assert {
        "event_discovery",
        "active_fire_observation",
        "progression_label",
        "eo_input",
        "weather_input",
    } <= roles
    assert any("global" in source["geography"] for source in p0)
