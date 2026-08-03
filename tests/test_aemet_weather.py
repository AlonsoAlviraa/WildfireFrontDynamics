"""AEMET WeatherScenario parsing, encoding, and honesty merge."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wildfire_front.fuel.weather import (
    _decode_aemet_body,
    aemet_dir_to_from_deg,
    load_dotenv,
    merge_weather_drivers,
    weather_scenario_from_aemet_daily,
)


# Raw AEMET daily record shape (camelCase fields as returned by open-data)
_RAW_TOBARRA_LIKE = {
    "fecha": "2024-08-02",
    "indicativo": "8175",
    "nombre": "ALBACETE BASE AÉREA",
    "tmed": "27,6",
    "hrMedia": "22",
    "velmedia": "5,0",
    "dir": "99",
    "racha": "13,6",
    "prec": "0,0",
}


class TestAemetDecode:
    def test_iso8859_station_name(self) -> None:
        # byte 0xC9 is É in latin-1 — classic AEMET datos payload
        body = b'{"nombre" : "ALBACETE BASE A\xc9REA"}'
        text = _decode_aemet_body(body)
        assert "AÉREA" in text or "AREA" in text.replace("É", "E")
        assert json.loads(text)["nombre"].startswith("ALBACETE")


class TestAemetDir:
    def test_tens_of_degrees(self) -> None:
        assert aemet_dir_to_from_deg(27) == pytest.approx(270.0)

    def test_full_degrees(self) -> None:
        assert aemet_dir_to_from_deg(180) == pytest.approx(180.0)

    def test_variable_99_is_none(self) -> None:
        assert aemet_dir_to_from_deg(99) is None
        assert aemet_dir_to_from_deg("99") is None


class TestAemetScenarioFromDaily:
    def test_camelcase_hrmedia_and_racha(self) -> None:
        ws = weather_scenario_from_aemet_daily(
            _RAW_TOBARRA_LIKE,
            fire_id="tobarra_20240802",
            station_id="8175",
        )
        assert ws.source == "aemet"
        assert ws.temp_c == pytest.approx(27.6)
        assert ws.rh_pct == pytest.approx(22.0)
        assert ws.wind_10m_ms == pytest.approx(5.0)
        assert ws.gust_ms == pytest.approx(13.6)
        assert ws.wind_from_deg is None  # dir=99 variable
        assert ws.dead_fmc_pct is not None and ws.dead_fmc_pct < 10.0
        assert ws.is_assumed is False
        assert "wind_dir_variable_aemet_code_99" in (ws.notes or [])

    def test_merge_fills_dir_and_stamps_assumed(self) -> None:
        ws = weather_scenario_from_aemet_daily(
            _RAW_TOBARRA_LIKE, station_id="8175"
        )
        m = merge_weather_drivers(ws, wind_from_deg=270.0, dead_fmc_pct=7.0)
        assert m.wind_10m_ms == pytest.approx(5.0)
        assert m.wind_from_deg == pytest.approx(270.0)
        assert "wind_from_deg" in m.fields_filled_from_defaults
        assert m.weather_scenario_assumed is True
        assert m.source == "aemet"

    def test_complete_aemet_not_assumed(self) -> None:
        rec = dict(_RAW_TOBARRA_LIKE)
        rec["dir"] = "27"  # tens of deg → 270
        ws = weather_scenario_from_aemet_daily(rec, station_id="8175")
        assert ws.wind_from_deg == pytest.approx(270.0)
        m = merge_weather_drivers(ws)
        assert m.weather_scenario_assumed is False
        assert m.fields_filled_from_defaults == []


class TestDotenv:
    def test_load_dotenv_no_overwrite(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        envf = tmp_path / ".env"
        envf.write_text("AEMET_API_KEY=from_file\nOTHER=1\n", encoding="utf-8")
        monkeypatch.delenv("AEMET_API_KEY", raising=False)
        monkeypatch.setenv("OTHER", "already")
        loaded = load_dotenv(envf)
        assert loaded == envf
        import os

        assert os.environ.get("AEMET_API_KEY") == "from_file"
        assert os.environ.get("OTHER") == "already"  # no overwrite
