"""Offline unit tests — La Mierla week plan helpers (Sprint B/C/D)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from wildfire_front.open_if.anchor_guard import (
    assert_not_fake_confirmed,
    can_promote_to_confirmed,
    promote_anchor_to_confirmed,
)
from wildfire_front.open_if.cems_watch import (
    EMSR896_NOTE,
    assert_emsr896_disclaimer,
    build_cems_watch,
)
from wildfire_front.open_if.dnbr_queue import evaluate_dnbr_queue
from wildfire_front.open_if.timeline import (
    append_counts_by_date,
    daily_stats_from_hotspot_rows,
    empty_timeline,
    merge_timeline_days,
)
from wildfire_front.open_if.week_package import (
    DEFAULT_HONESTY_FLAGS,
    WEEK_PACKAGE_SCHEMA,
    build_week_package_manifest,
    export_week_package,
    inventory_pack_artifacts,
    validate_week_package_manifest,
)

EVENT = "guadalajara_la_mierla_20260717"
ROOT = Path(__file__).resolve().parents[1]


def _load_day_runner():
    spec = importlib.util.spec_from_file_location(
        "run_la_mierla_open_day", ROOT / "scripts" / "run_la_mierla_open_day.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _seed_minimal_pack(pack: Path) -> None:
    pack.mkdir(parents=True, exist_ok=True)
    (pack / "scrape_latest.json").write_text(
        json.dumps(
            {
                "scraped_at_utc": "2026-07-21T08:00:00+00:00",
                "infocam_latest": {"ha_estimated": 29000, "level": 2},
                "cems": {
                    "status": "WATCH",
                    "note": "EMSR896 is Aragon (Ores path). No EMSR La Mierla.",
                    "related_news": "https://example.com/emsr896",
                },
                "press": [{"ha": 29000}],
                "x_official": [{"handle": "@Plan_INFOCAM"}],
            }
        ),
        encoding="utf-8",
    )
    (pack / "firms_hotspots_7d.geojson").write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"acq_date": "2026-07-16", "frp": 2.0},
                        "geometry": {"type": "Point", "coordinates": [-3.0, 41.1]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"acq_date": "2026-07-17", "frp": 5.0},
                        "geometry": {"type": "Point", "coordinates": [-3.01, 41.11]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"acq_date": "2026-07-17", "frp": 7.0},
                        "geometry": {"type": "Point", "coordinates": [-3.02, 41.12]},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    (pack / "firms_metrics.json").write_text(
        json.dumps({"hull_area_ha_approx": 1000.0}), encoding="utf-8"
    )
    (pack / "firms_footprint_proxy.geojson").write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {
                            "layer": "firms_convex_hull",
                            "approx_area_ha_from_hull": 1000.0,
                        },
                        "geometry": {"type": "Polygon", "coordinates": []},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (pack / "scorecard_pista_b.json").write_text(
        json.dumps({"activation": EVENT, "notes": []}), encoding="utf-8"
    )
    sat = pack / "satellite_enrichment"
    sat.mkdir(exist_ok=True)
    (sat / "sentinel2_stac_search.json").write_text(
        json.dumps(
            {
                "searches": {
                    "pre_fire_01_15_jul": {
                        "items": [
                            {
                                "id": "S2_pre",
                                "eo:cloud_cover": 0.2,
                                "datetime": "2026-07-13T00:00:00Z",
                            }
                        ]
                    },
                    "strict_clear_during": {
                        "items": [
                            {
                                "id": "S2_16",
                                "eo:cloud_cover": 1.4,
                                "datetime": "2026-07-16T00:00:00Z",
                            }
                        ]
                    },
                    "post_fire": {"items": []},
                }
            }
        ),
        encoding="utf-8",
    )


# ── timeline ──────────────────────────────────────────────────────────────


def test_daily_stats_from_rows():
    rows = [
        {"acq_date": "2026-07-16", "frp": "1.0"},
        {"acq_date": "2026-07-16", "frp": "3.0"},
        {"acq_date": "2026-07-17", "frp": "10"},
    ]
    stats = daily_stats_from_hotspot_rows(rows, sensor="viirs_n20_7d")
    assert stats["2026-07-16"]["n_hotspots"] == 2
    assert stats["2026-07-16"]["frp_sum"] == 4.0
    assert stats["2026-07-16"]["frp_mean"] == 2.0
    assert stats["2026-07-16"]["frp_max"] == 3.0
    assert stats["2026-07-17"]["n_hotspots"] == 1


def test_timeline_bad_frp_still_counts():
    rows = [
        {"acq_date": "2026-07-16", "frp": "bad"},
        {"acq_date": "2026-07-16", "frp": "4"},
    ]
    stats = daily_stats_from_hotspot_rows(rows)
    assert stats["2026-07-16"]["n_hotspots"] == 2
    assert stats["2026-07-16"]["frp_sum"] == 4.0


def test_empty_timeline_schema():
    doc = empty_timeline(EVENT)
    assert doc["schema"] == "open_if_timeline_daily_v1"
    assert doc["n_days"] == 0
    assert doc["series"] == []


def test_timeline_append_merge_prefers_higher_count():
    existing = merge_timeline_days(
        None,
        {
            "2026-07-21": {
                "date": "2026-07-21",
                "n_hotspots": 198,
                "frp_sum": 100.0,
                "sensor": "viirs_n20_7d",
            }
        },
        event_id=EVENT,
        generated_at="2026-07-21T10:00:00+00:00",
    )
    merged = merge_timeline_days(
        existing,
        {
            "2026-07-21": {
                "date": "2026-07-21",
                "n_hotspots": 50,
                "frp_sum": 10.0,
                "sensor": "viirs_n20_7d",
            },
            "2026-07-22": {
                "date": "2026-07-22",
                "n_hotspots": 12,
                "frp_sum": 5.0,
                "sensor": "viirs_n20_7d",
            },
        },
        event_id=EVENT,
        generated_at="2026-07-22T10:00:00+00:00",
    )
    assert merged["days"]["2026-07-21"]["n_hotspots"] == 198
    assert merged["days"]["2026-07-21"].get("merge_note") == "kept_higher_n_hotspots"
    assert merged["days"]["2026-07-22"]["n_hotspots"] == 12


def test_append_counts_merge_conflict_higher_keeps_and_lower_then_higher():
    """n=198 then n=50 keeps 198; n=50 then n=198 accepts 198."""
    high = append_counts_by_date(
        None,
        {"2026-07-21": 198},
        event_id=EVENT,
        frp_by_date={"2026-07-21": {"frp_sum": 500.0, "frp_max": 40.0, "frp_mean": 2.5}},
    )
    low = append_counts_by_date(high, {"2026-07-21": 50}, event_id=EVENT)
    assert low["days"]["2026-07-21"]["n_hotspots"] == 198
    assert low["days"]["2026-07-21"]["frp_sum"] == 500.0

    low_first = append_counts_by_date(None, {"2026-07-21": 50}, event_id=EVENT)
    high_second = append_counts_by_date(
        low_first,
        {"2026-07-21": 198},
        event_id=EVENT,
        frp_by_date={"2026-07-21": {"frp_sum": 500.0, "frp_max": 40.0}},
    )
    assert high_second["days"]["2026-07-21"]["n_hotspots"] == 198
    assert high_second["days"]["2026-07-21"]["frp_sum"] == 500.0


def test_append_counts_equal_n_preserves_frp():
    """Counts-only append with equal n must not null out prior FRP."""
    with_frp = append_counts_by_date(
        None,
        {"2026-07-20": 397},
        event_id=EVENT,
        frp_by_date={"2026-07-20": {"frp_sum": 9000.0, "frp_mean": 22.0, "frp_max": 429.0}},
    )
    counts_only = append_counts_by_date(
        with_frp,
        {"2026-07-20": 397},
        event_id=EVENT,
    )
    day = counts_only["days"]["2026-07-20"]
    assert day["n_hotspots"] == 397
    assert day["frp_sum"] == 9000.0
    assert day["frp_max"] == 429.0
    assert day.get("merge_note") == "preserved_frp_equal_n"


def test_append_counts_by_date_merge():
    doc = append_counts_by_date(
        None,
        {"2026-07-16": 5, "2026-07-17": 133},
        event_id=EVENT,
        sensor="viirs_n20_7d",
        frp_by_date={"2026-07-16": {"frp_sum": 10.0, "frp_max": 4.0, "frp_mean": 2.0}},
    )
    assert doc["days"]["2026-07-16"]["n_hotspots"] == 5
    assert doc["days"]["2026-07-16"]["frp_sum"] == 10.0
    doc2 = append_counts_by_date(doc, {"2026-07-18": 274}, event_id=EVENT)
    assert doc2["n_days"] == 3


# ── anchor_guard ──────────────────────────────────────────────────────────


def test_anchor_guard_refuses_la_mierla_press_only():
    anchor = {
        "fire_id": "guadalajara_la_mierla_20260717",
        "vp_m_min": None,
        "area_ha": None,
        "area_ha_press_provisional": 29000,
        "source": "Plan_INFOCAM X post estimate only",
        "status": "pending_external",
    }
    ok, reasons = can_promote_to_confirmed(anchor)
    assert ok is False
    assert any("missing_vp_m_min" in r for r in reasons)
    assert any("missing_area_ha" in r for r in reasons)
    assert any("press_provisional" in r for r in reasons)
    with pytest.raises(ValueError):
        promote_anchor_to_confirmed(anchor)


def test_anchor_guard_refuses_confirmed_without_vp():
    anchor = {
        "fire_id": "x",
        "vp_m_min": None,
        "area_ha": 100.0,
        "source": "INFOCAM parte operativo",
        "status": "pending_external",
    }
    ok, reasons = can_promote_to_confirmed(anchor)
    assert ok is False
    assert any("missing_vp_m_min" in r for r in reasons)


def test_anchor_guard_allows_tobarra_style():
    anchor = {
        "fire_id": "tobarra_20240802",
        "vp_m_min": 7.0,
        "area_ha": 39.0,
        "source": "INFOCAM 2024 parte operativo",
        "status": "pending_external",
    }
    ok, reasons = can_promote_to_confirmed(anchor)
    assert ok is True, reasons
    promoted = promote_anchor_to_confirmed(anchor)
    assert promoted["status"] == "confirmed"
    assert_not_fake_confirmed(promoted)


def test_assert_not_fake_confirmed_raises():
    bad = {
        "fire_id": "guadalajara_la_mierla_20260717",
        "status": "confirmed",
        "vp_m_min": None,
        "area_ha": None,
        "area_ha_press_provisional": 29000,
        "source": "press",
    }
    with pytest.raises(ValueError, match="fake_confirmed"):
        assert_not_fake_confirmed(bad)


@pytest.mark.parametrize(
    "anchor,expect_ok,reason_substr",
    [
        (
            {
                "fire_id": "a",
                "vp_m_min": -1,
                "area_ha": 10,
                "source": "INFOCAM parte operativo",
            },
            False,
            "vp_m_min_not_positive",
        ),
        (
            {
                "fire_id": "b",
                "vp_m_min": "x",
                "area_ha": 10,
                "source": "INFOCAM parte operativo",
            },
            False,
            "vp_m_min_not_numeric",
        ),
        (
            {
                "fire_id": "c",
                "vp_m_min": 1,
                "area_ha": 0,
                "source": "INFOCAM parte operativo",
            },
            False,
            "area_ha_not_positive",
        ),
        (
            {
                "fire_id": "d",
                "vp_m_min": 1,
                "area_ha": 10,
                "source": "",
            },
            False,
            "missing_source",
        ),
        (
            {
                "fire_id": "e",
                "vp_m_min": 1,
                "area_ha": 10,
                "source": "elpais.com press coverage",
            },
            False,
            "source_is_press_media",
        ),
        (
            {
                "fire_id": "f",
                "vp_m_min": 1,
                "area_ha": 29000,
                "area_ha_press_provisional": 29000,
                "source": "Plan_INFOCAM X post estimate only",
            },
            False,
            "estimate_or_provisional",
        ),
        (
            {
                "fire_id": "g",
                "vp_m_min": 5.0,
                "area_ha": 100.0,
                "source": "EGIF parte oficial 2026",
            },
            True,
            None,
        ),
    ],
)
def test_anchor_guard_edges(anchor, expect_ok, reason_substr):
    ok, reasons = can_promote_to_confirmed(anchor)
    assert ok is expect_ok, reasons
    if reason_substr:
        assert any(reason_substr in r for r in reasons), reasons


def test_anchor_guard_force_true_still_validates():
    bad = {
        "fire_id": "x",
        "vp_m_min": None,
        "area_ha": None,
        "source": None,
    }
    with pytest.raises(ValueError):
        promote_anchor_to_confirmed(bad, force=True)


# ── cems_watch ────────────────────────────────────────────────────────────


def test_cems_watch_emsr896_note():
    doc = build_cems_watch(status="WATCH")
    assert doc["status"] == "WATCH"
    assert "EMSR896" in doc["note"]
    assert "EMSR896" in EMSR896_NOTE
    assert doc["emsr896_is_not_la_mierla"] is True
    assert_emsr896_disclaimer(doc)
    doc2 = build_cems_watch(
        note="EMSR896 is Aragon (Ores path). No confirmed EMSR for La Mierla."
    )
    assert "EMSR896" in doc2["note"]
    assert_emsr896_disclaimer(doc2)


def test_cems_watch_appends_emsr896_if_missing():
    doc = build_cems_watch(note="No CEMS activation found today.")
    assert "EMSR896" in doc["note"]
    assert_emsr896_disclaimer(doc)


def test_assert_emsr896_disclaimer_failures():
    with pytest.raises(AssertionError, match="EMSR896"):
        assert_emsr896_disclaimer({"note": "No activation", "emsr896_is_not_la_mierla": True})
    with pytest.raises(AssertionError, match="emsr896_is_not_la_mierla"):
        assert_emsr896_disclaimer(
            {"note": "EMSR896 is Aragon", "emsr896_is_not_la_mierla": False}
        )


# ── week package ──────────────────────────────────────────────────────────


def test_week_package_manifest_schema(tmp_path: Path):
    pack = tmp_path / "la_mierla_20260717"
    pack.mkdir()
    (pack / "manifest.json").write_text("{}", encoding="utf-8")
    (pack / "scorecard_pista_b.json").write_text("{}", encoding="utf-8")
    (pack / "timeline_daily.json").write_text("{}", encoding="utf-8")

    arts = inventory_pack_artifacts(pack)
    man = build_week_package_manifest(
        event_id=EVENT,
        pack_dir=pack,
        artifacts=arts,
    )
    assert man["schema"] == WEEK_PACKAGE_SCHEMA
    assert validate_week_package_manifest(man) == []
    # All default honesty flags present
    for k, v in DEFAULT_HONESTY_FLAGS.items():
        assert man["honesty_flags"].get(k) is v, k

    exported = export_week_package(pack, event_id=EVENT)
    disk = json.loads((pack / "week_package" / "manifest.json").read_text(encoding="utf-8"))
    assert validate_week_package_manifest(disk) == []
    assert "manifest.json" in (exported.get("copied") or [])


def test_validate_week_package_manifest_errors():
    errs = validate_week_package_manifest({"schema": "wrong"})
    assert any("schema" in e for e in errs)
    assert any("event_id" in e for e in errs)


def test_validate_week_package_manifest_missing_artifacts_and_flags():
    errs = validate_week_package_manifest(
        {
            "schema": WEEK_PACKAGE_SCHEMA,
            "event_id": EVENT,
            # no artifacts
            "honesty_flags": {"not_official_perimeter": True},  # incomplete flags
        }
    )
    assert any("missing_artifacts_list" in e for e in errs)
    assert any("missing_honesty_flag:no_field_ops_go_from_open_only" in e for e in errs)
    assert any("missing_honesty_flag:emsr896_is_not_la_mierla" in e for e in errs)

    errs2 = validate_week_package_manifest(
        {
            "schema": WEEK_PACKAGE_SCHEMA,
            "event_id": EVENT,
            "artifacts": [],
            # no honesty_flags
        }
    )
    assert any("missing_honesty_flags" in e for e in errs2)


# ── dnbr queue ────────────────────────────────────────────────────────────


def test_dnbr_queue_blocked_without_post():
    pre = [{"id": "S2_pre", "eo:cloud_cover": 1.0, "datetime": "2026-07-13T00:00:00Z"}]
    q = evaluate_dnbr_queue(
        pre_items=pre,
        post_items=[],
        during_clear_items=[
            {"id": "S2_16", "eo:cloud_cover": 1.5, "datetime": "2026-07-16T00:00:00Z"}
        ],
        event_date="2026-07-16",
    )
    assert q["status"] == "blocked_clouds"
    assert q["detail_status"] == "incomplete_pre_only"
    assert any("incomplete" in r for r in q["reasons"])


def test_dnbr_queue_ready_with_post():
    pre = [{"id": "S2_pre", "eo:cloud_cover": 2.0, "datetime": "2026-07-13T00:00:00Z"}]
    post = [{"id": "S2_post", "eo:cloud_cover": 5.0, "datetime": "2026-07-25T00:00:00Z"}]
    q = evaluate_dnbr_queue(
        pre_items=pre,
        post_items=post,
        event_date="2026-07-16",
        max_cloud=30.0,
    )
    assert q["status"] == "ready"
    assert q["post_top"] == "S2_post"


def test_dnbr_queue_blocked_no_pre():
    q = evaluate_dnbr_queue(pre_items=[], post_items=[], event_date="2026-07-16")
    assert q["status"] == "blocked_no_pre"
    assert q["detail_status"] == "blocked_no_pre"


def test_dnbr_queue_unknown_cloud_not_clear():
    pre = [{"id": "S2_pre", "eo:cloud_cover": 1.0, "datetime": "2026-07-13T00:00:00Z"}]
    post = [{"id": "S2_post_unknown", "datetime": "2026-07-25T00:00:00Z"}]  # no cloud
    q = evaluate_dnbr_queue(
        pre_items=pre,
        post_items=post,
        event_date="2026-07-16",
        max_cloud=30.0,
    )
    assert q["status"] == "blocked_clouds"
    assert q["n_post_clear"] == 0
    assert q["n_post_unknown_cloud"] == 1
    assert any("unknown_cloud" in r for r in q["reasons"])


def test_dnbr_queue_cloudy_post_blocked():
    pre = [{"id": "S2_pre", "eo:cloud_cover": 1.0, "datetime": "2026-07-13T00:00:00Z"}]
    post = [{"id": "S2_post", "eo:cloud_cover": 80.0, "datetime": "2026-07-25T00:00:00Z"}]
    q = evaluate_dnbr_queue(
        pre_items=pre,
        post_items=post,
        event_date="2026-07-16",
        max_cloud=30.0,
    )
    assert q["status"] == "blocked_clouds"
    assert q["detail_status"] == "incomplete_pre_only"
    assert any("cloudy" in r for r in q["reasons"])


def test_dnbr_queue_ready_requires_pre_clear():
    """Cloudy pre + clear post must NOT be ready (n_pre_clear=0)."""
    pre = [{"id": "S2_pre_cloud", "eo:cloud_cover": 90.0, "datetime": "2026-07-13T00:00:00Z"}]
    post = [{"id": "S2_post", "eo:cloud_cover": 5.0, "datetime": "2026-07-25T00:00:00Z"}]
    q = evaluate_dnbr_queue(
        pre_items=pre,
        post_items=post,
        event_date="2026-07-16",
        max_cloud=30.0,
    )
    assert q["status"] == "blocked_clouds"
    assert q["detail_status"] == "blocked_no_clear_pre"
    assert q["n_pre_clear"] == 0
    assert q["n_post_clear"] == 1
    assert any("no_clear_pre" in r for r in q["reasons"])


def test_dnbr_queue_event_date_excludes_post_on_event_day():
    """Post on event_date must not count as clear post (always apply filter)."""
    pre = [{"id": "S2_pre", "eo:cloud_cover": 2.0, "datetime": "2026-07-13T00:00:00Z"}]
    post = [
        {
            "id": "S2_on_event",
            "eo:cloud_cover": 1.0,
            "datetime": "2026-07-16T11:00:00Z",
        }
    ]
    q = evaluate_dnbr_queue(
        pre_items=pre,
        post_items=post,
        event_date="2026-07-16",
        max_cloud=30.0,
    )
    assert q["status"] != "ready"
    assert q["status"] == "blocked_clouds"
    assert q["detail_status"] == "incomplete_pre_only"
    assert q["n_post_clear"] == 0
    assert q["n_post_on_or_before_event"] == 1
    assert any("on_or_before_event" in r for r in q["reasons"])


def test_dnbr_queue_event_date_keeps_post_after():
    pre = [{"id": "S2_pre", "eo:cloud_cover": 2.0, "datetime": "2026-07-13T00:00:00Z"}]
    post = [
        {"id": "S2_same_day", "eo:cloud_cover": 1.0, "datetime": "2026-07-16T11:00:00Z"},
        {"id": "S2_after", "eo:cloud_cover": 3.0, "datetime": "2026-07-22T00:00:00Z"},
    ]
    q = evaluate_dnbr_queue(
        pre_items=pre,
        post_items=post,
        event_date="2026-07-16",
        max_cloud=30.0,
    )
    assert q["status"] == "ready"
    assert q["post_top"] == "S2_after"
    assert q["n_post_clear"] == 1


# ── day runner offline ────────────────────────────────────────────────────


def test_day_runner_skip_network(tmp_path: Path):
    mod = _load_day_runner()
    pack = tmp_path / "la_mierla_20260717"
    _seed_minimal_pack(pack)
    for name in (
        "fire_decision_card_field_ops.json",
        "fire_decision_card_research.json",
    ):
        (pack / name).write_text(
            json.dumps({"event_id": EVENT, "decision": "HOLD"}), encoding="utf-8"
        )

    report = mod.run_day(
        pack=pack,
        skip_network=True,
        skip_decide=True,
        try_dnbr_flag=False,
        write_forensic=True,
    )
    assert report["ok"] is True
    assert report.get("errors") == []

    tl = json.loads((pack / "timeline_daily.json").read_text(encoding="utf-8"))
    assert tl["days"]["2026-07-16"]["n_hotspots"] == 1
    assert tl["days"]["2026-07-17"]["n_hotspots"] == 2
    assert tl["days"]["2026-07-17"]["frp_sum"] == 12.0

    cems = json.loads((pack / "cems_watch.json").read_text(encoding="utf-8"))
    assert cems["status"] == "WATCH"
    assert "EMSR896" in cems["note"]

    hist = json.loads((pack / "scrape_history.json").read_text(encoding="utf-8"))
    assert hist["days"]
    # per-day history list
    day_slot = next(iter(hist["days"].values()))
    assert "latest" in day_slot
    assert isinstance(day_slot.get("history"), list)
    assert len(day_slot["history"]) >= 1

    queue = json.loads((pack / "dnbr_queue.json").read_text(encoding="utf-8"))
    assert queue["status"] == "blocked_clouds"
    assert queue["detail_status"] == "incomplete_pre_only"

    dnbr = json.loads((pack / "dnbr_status.json").read_text(encoding="utf-8"))
    assert dnbr["status"] == "BLOCKED"
    assert "incomplete_without_clear_post" in (dnbr.get("reasons") or [])

    sc = json.loads((pack / "scorecard_pista_b.json").read_text(encoding="utf-8"))
    assert sc.get("dnbr_status") == "BLOCKED"

    wman = json.loads((pack / "week_package" / "manifest.json").read_text(encoding="utf-8"))
    for k in DEFAULT_HONESTY_FLAGS:
        assert k in wman["honesty_flags"]

    fo = json.loads((pack / "fire_decision_card_field_ops.json").read_text(encoding="utf-8"))
    assert fo["decision"] == "HOLD"
    assert report["steps"]["field_ops_final"]["decision"] == "HOLD"


def test_day_runner_coerces_go_to_hold(tmp_path: Path):
    """Seed GO field_ops card; skip_decide; assert HOLD + hard rule flags."""
    mod = _load_day_runner()
    pack = tmp_path / "la_mierla_20260717"
    _seed_minimal_pack(pack)
    (pack / "fire_decision_card_field_ops.json").write_text(
        json.dumps({"event_id": EVENT, "decision": "GO", "confidence_pred": 0.9}),
        encoding="utf-8",
    )
    (pack / "fire_decision_card_research.json").write_text(
        json.dumps({"event_id": EVENT, "decision": "HOLD"}), encoding="utf-8"
    )

    report = mod.run_day(
        pack=pack,
        skip_network=True,
        skip_decide=True,
        try_dnbr_flag=False,
        write_forensic=False,
    )
    fo = json.loads((pack / "fire_decision_card_field_ops.json").read_text(encoding="utf-8"))
    assert fo["decision"] == "HOLD"
    assert fo.get("open_only_hard_rule") is True
    assert report["steps"]["decide"].get("field_ops_coerced") is True
    assert report["steps"]["field_ops_final"]["decision"] == "HOLD"
    assert report["ok"] is True


def test_day_runner_synthetic_hold_when_missing_card(tmp_path: Path):
    mod = _load_day_runner()
    pack = tmp_path / "la_mierla_20260717"
    _seed_minimal_pack(pack)
    # no decision cards
    report = mod.run_day(
        pack=pack,
        skip_network=True,
        skip_decide=True,
        try_dnbr_flag=False,
        write_forensic=False,
    )
    fo = json.loads((pack / "fire_decision_card_field_ops.json").read_text(encoding="utf-8"))
    assert fo["decision"] == "HOLD"
    assert fo.get("open_only_hard_rule") is True
    assert report["steps"]["decide"].get("field_ops_synthetic") is True


def test_try_dnbr_never_demotes_go_from_queue(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """If dNBR runner returns GO, enrichment queue incomplete must not demote."""
    mod = _load_day_runner()
    pack = tmp_path / "la_mierla_go"
    pack.mkdir()
    (pack / "dnbr_queue.json").write_text(
        json.dumps(
            {
                "status": "blocked_clouds",
                "detail_status": "incomplete_pre_only",
                "reasons": ["clear_pre_only_missing_clear_post"],
            }
        ),
        encoding="utf-8",
    )
    (pack / "scorecard_pista_b.json").write_text(
        json.dumps({"activation": EVENT, "notes": []}), encoding="utf-8"
    )
    (pack / "firms_metrics.json").write_text(
        json.dumps({"hull_area_ha_approx": 1.0}), encoding="utf-8"
    )

    class FakeMod:
        @staticmethod
        def run_for_pack(*_a, **_k):
            status = {
                "schema": "open_if_dnbr_status_v1",
                "status": "GO",
                "reasons": ["dnbr_window_ok"],
                "built_at_utc": "2026-07-21T00:00:00+00:00",
            }
            (pack / "dnbr_status.json").write_text(json.dumps(status), encoding="utf-8")
            (pack / "dnbr_summary.json").write_text(
                json.dumps({"severity": {"burned_frac_ge_0.27": 0.1}}),
                encoding="utf-8",
            )
            return status

    import types

    def fake_spec_from_file_location(name, path):  # noqa: ARG001
        return types.SimpleNamespace(loader=types.SimpleNamespace(exec_module=lambda m: None))

    def fake_module_from_spec(spec):  # noqa: ARG001
        return FakeMod()

    monkeypatch.setattr(mod.importlib.util, "spec_from_file_location", fake_spec_from_file_location)
    monkeypatch.setattr(mod.importlib.util, "module_from_spec", fake_module_from_spec)
    # exec_module is no-op; run_for_pack is on FakeMod — need try_dnbr to get FakeMod
    # Actually try_dnbr does: mod = module_from_spec; loader.exec_module(mod); mod.run_for_pack
    # Our FakeMod has run_for_pack as staticmethod on the class returned by module_from_spec.
    # But exec_module is on loader and no-ops — FakeMod instance is returned by module_from_spec.
    # Wait — module_from_spec returns FakeMod class... we return FakeMod which is the class.
    # FakeMod.run_for_pack works as class method static.

    status = mod.try_dnbr(pack, search_only=True)
    assert status["status"] == "GO"
    assert status.get("queue_disagreement") is not None
    disk = json.loads((pack / "dnbr_status.json").read_text(encoding="utf-8"))
    assert disk["status"] == "GO"


def test_scrape_history_keeps_multiple_snapshots(tmp_path: Path):
    mod = _load_day_runner()
    pack = tmp_path / "hist"
    pack.mkdir()
    s1 = {
        "scraped_at_utc": "2026-07-21T08:00:00+00:00",
        "infocam_latest": {"ha_estimated": 26000},
        "press": [],
        "x_official": [],
    }
    s2 = {
        "scraped_at_utc": "2026-07-21T18:00:00+00:00",
        "infocam_latest": {"ha_estimated": 29000},
        "press": [1],
        "x_official": [1, 2],
    }
    mod.merge_scrape_history(pack, s1, day_key="2026-07-21")
    mod.merge_scrape_history(pack, s2, day_key="2026-07-21")
    hist = json.loads((pack / "scrape_history.json").read_text(encoding="utf-8"))
    slot = hist["days"]["2026-07-21"]
    assert slot["n_snapshots"] == 2
    assert len(slot["history"]) == 2
    assert slot["latest"]["infocam_latest"]["ha_estimated"] == 29000
    assert slot["history"][0]["infocam_latest"]["ha_estimated"] == 26000


def test_derive_ok_false_on_build_fail(tmp_path: Path):
    mod = _load_day_runner()
    report = {
        "steps": {
            "build_pack": {"ok": False, "error": "timeout"},
            "enrich_satellite": {"skipped": True, "ok": True},
            "decide": {"skipped": True, "ok": True},
            "anchor_guard": {"ok": True},
            "field_ops_final": {"decision": "HOLD", "ok": True},
        }
    }
    ok, errors = mod._derive_ok(report)
    assert ok is False
    assert "build_pack_failed" in errors


def test_derive_ok_fake_confirmed_and_field_ops_still_go():
    mod = _load_day_runner()
    ok, errors = mod._derive_ok(
        {
            "steps": {
                "build_pack": {"skipped": True, "ok": True},
                "enrich_satellite": {"skipped": True, "ok": True},
                "decide": {"skipped": True, "ok": True},
                "anchor_guard": {"ok": False, "status": "fake_confirmed"},
                "field_ops_final": {"decision": "HOLD", "ok": True},
            }
        }
    )
    assert ok is False
    assert "fake_confirmed_anchor" in errors

    ok2, errors2 = mod._derive_ok(
        {
            "steps": {
                "build_pack": {"skipped": True, "ok": True},
                "enrich_satellite": {"skipped": True, "ok": True},
                "decide": {"skipped": True, "ok": True},
                "anchor_guard": {"ok": True},
                "field_ops_final": {"decision": "GO", "ok": False},
            }
        }
    )
    assert ok2 is False
    assert "field_ops_still_go" in errors2


def test_check_event_anchor_fake_confirmed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    mod = _load_day_runner()
    anchors = tmp_path / "infocam_anchors.json"
    anchors.write_text(
        json.dumps(
            {
                "anchors": {
                    EVENT: {
                        "fire_id": EVENT,
                        "status": "confirmed",
                        "vp_m_min": None,
                        "area_ha": None,
                        "area_ha_press_provisional": 29000,
                        "source": "press estimate only",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "ANCHORS_PATH", anchors)
    result = mod.check_event_anchor()
    assert result["ok"] is False
    assert result["status"] == "fake_confirmed"
    assert "error" in result


def test_check_event_anchor_pending_ok(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    mod = _load_day_runner()
    anchors = tmp_path / "infocam_anchors.json"
    anchors.write_text(
        json.dumps(
            {
                "anchors": {
                    EVENT: {
                        "fire_id": EVENT,
                        "status": "pending_external",
                        "vp_m_min": None,
                        "area_ha": None,
                        "source": "estimate",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "ANCHORS_PATH", anchors)
    result = mod.check_event_anchor()
    assert result["ok"] is True
    assert result["status"] == "pending_external"
