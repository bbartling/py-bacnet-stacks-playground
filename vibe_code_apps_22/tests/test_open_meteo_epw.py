"""Open-Meteo archive → AMY EPW (no live HTTP)."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from eplus_gym_app.open_meteo_epw import (
    amy_stale,
    default_archive_end,
    default_calendar_window,
    fetch_open_meteo_archive,
    parse_epw_span,
    refresh_amy_epw,
    site_geo,
    to_local_standard,
    write_epw,
)
from eplus_gym_app.weather_files import KIND_AMY, classify_epw, resolve_amy_epw


def _hourly(start: str, hours: int, *, oat_f: float = 20.0) -> pd.DataFrame:
    idx = pd.date_range(start, periods=hours, freq="h", tz="UTC")
    return pd.DataFrame(
        {
            "timestamp_utc": idx,
            "dry_bulb_f": [oat_f + i * 0.1 for i in range(hours)],
            "dew_point_f": [oat_f - 8.0] * hours,
            "relative_humidity_pct": [70.0] * hours,
            "surface_pressure_hpa": [992.0] * hours,
            "shortwave_radiation_wm2": [0.0] * hours,
            "direct_normal_irradiance_wm2": [0.0] * hours,
            "diffuse_radiation_wm2": [0.0] * hours,
            "wind_speed_mph": [5.0] * hours,
            "wind_direction_deg": [270.0] * hours,
        }
    )


def _answers(site: Path, *, end: str = "2026-07-03") -> None:
    path = site / "eplus" / "assumptions" / "answers.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "city": "Sun Prairie, WI",
                "lat": 43.16521,
                "lon": -89.25408,
                "data_window": {"start_utc": "2025-08-01", "end_utc": end},
            }
        ),
        encoding="utf-8",
    )


def test_site_geo_reads_answers(tmp_path: Path):
    _answers(tmp_path)
    geo = site_geo(tmp_path)
    assert geo["lat"] == pytest.approx(43.16521)
    assert geo["lon"] == pytest.approx(-89.25408)
    assert geo["start"] == "2025-08-01"
    assert geo["end"] == "2026-07-03"
    assert geo["utc_offset_hours"] == -6.0


def test_write_epw_has_location_and_complete_days(tmp_path: Path):
    raw = _hourly("2026-01-26T06:00:00Z", 48)
    lst = to_local_standard(raw, utc_offset_hours=-6)
    out = tmp_path / "madison_amy_202601_202601.epw"
    meta = write_epw(
        lst,
        out,
        lat=43.165,
        lon=-89.254,
        elevation_m=261.0,
        location_name="Madison_AMY",
    )
    text = out.read_text(encoding="utf-8")
    assert text.startswith("LOCATION,Madison_AMY,WI,USA,AMY,726410,43.165,-89.254,-6.0,261.0")
    assert "Open-Meteo" in text
    assert meta["rows"] == 48
    assert classify_epw(out) == KIND_AMY
    span = parse_epw_span(out)
    assert span["start"] == date(2026, 1, 26)
    assert span["end"] == date(2026, 1, 27)
    assert span["n_rows"] == 48


def test_amy_stale_missing_and_old(tmp_path: Path):
    assert amy_stale(None, as_of=date(2026, 8, 11)) is True
    missing = tmp_path / "nope.epw"
    assert amy_stale(missing, as_of=date(2026, 8, 11)) is True
    raw = _hourly("2026-07-02T06:00:00Z", 24)
    lst = to_local_standard(raw, utc_offset_hours=-6)
    epw = tmp_path / "madison_amy_old.epw"
    write_epw(lst, epw, lat=43.0, lon=-89.0, elevation_m=261.0)
    assert amy_stale(epw, as_of=date(2026, 8, 11), lag_days=5) is True
    assert amy_stale(epw, as_of=date(2026, 7, 4), lag_days=5) is False


def test_refresh_writes_epw_csv_meta_and_skips_chicago(tmp_path: Path):
    _answers(tmp_path, end="2026-01-27")
    calls: list[tuple] = []

    def fake_fetch(lat, lon, start, end, **kwargs):
        calls.append((lat, lon, start, end))
        df = _hourly(f"{start}T06:00:00Z", 48)
        df.attrs["elevation_m"] = 270.0
        return df

    meta = refresh_amy_epw(
        tmp_path,
        start="2026-01-26",
        end="2026-01-27",
        force=True,
        fetch=fake_fetch,
    )
    assert calls == [(43.16521, -89.25408, "2026-01-26", "2026-01-27")]
    epw = Path(meta["epw"])
    assert epw.is_file()
    assert "_amy_" in epw.name
    assert classify_epw(epw) == KIND_AMY
    assert meta.get("site_slug")
    assert (tmp_path / "eplus" / "weather" / "open_meteo_amy_hourly.csv").is_file()
    sidecar = json.loads((tmp_path / "eplus" / "weather" / "amy_meta.json").read_text(encoding="utf-8"))
    assert sidecar["source"] == "open-meteo-archive"
    assert sidecar["kind"] == KIND_AMY
    assert sidecar["lat"] == pytest.approx(43.16521)
    assert not (tmp_path / "eplus" / "weather" / "madison_tmy_screening.epw").exists()
    assert resolve_amy_epw(tmp_path) == epw


def test_refresh_skips_network_when_fresh(tmp_path: Path):
    _answers(tmp_path)
    raw = _hourly("2026-08-08T06:00:00Z", 24)
    weather = tmp_path / "eplus" / "weather"
    weather.mkdir(parents=True)
    epw = weather / "madison_amy_202508_202608.epw"
    write_epw(to_local_standard(raw), epw, lat=43.0, lon=-89.0, elevation_m=261.0)

    def boom(*_a, **_k):
        raise AssertionError("must not fetch when AMY is fresh")

    meta = refresh_amy_epw(
        tmp_path,
        as_of=date(2026, 8, 11),
        lag_days=5,
        fetch=boom,
    )
    assert meta["skipped"] is True
    assert Path(meta["epw"]) == epw


def test_resolve_amy_prefers_newest_mtime(tmp_path: Path):
    weather = tmp_path / "eplus" / "weather"
    weather.mkdir(parents=True)
    old = weather / "madison_amy_202508_202607.epw"
    new = weather / "madison_amy_202508_202608.epw"
    old.write_text("LOCATION,old", encoding="utf-8")
    new.write_text("LOCATION,new", encoding="utf-8")
    import os

    os.utime(old, (1_700_000_000, 1_700_000_000))
    os.utime(new, (1_800_000_000, 1_800_000_000))
    assert resolve_amy_epw(tmp_path) == new


def test_fetch_open_meteo_archive_parses_payload(monkeypatch: pytest.MonkeyPatch):
    class _Resp:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {
                "elevation": 261.0,
                "hourly": {
                    "time": ["2026-01-26T00:00", "2026-01-26T01:00"],
                    "temperature_2m": [10.0, 11.0],
                    "dew_point_2m": [2.0, 3.0],
                    "relative_humidity_2m": [70, 71],
                    "surface_pressure": [992.0, 993.0],
                    "shortwave_radiation": [0, 5],
                    "direct_normal_irradiance": [0, 1],
                    "diffuse_radiation": [0, 4],
                    "wind_speed_10m": [4.0, 5.0],
                    "wind_direction_10m": [180, 190],
                },
            }

    def fake_get(url, params=None, timeout=None):
        assert "archive-api.open-meteo.com" in url
        assert params["latitude"] == 43.16521
        return _Resp()

    monkeypatch.setattr("eplus_gym_app.open_meteo_epw.requests.get", fake_get)
    df = fetch_open_meteo_archive(43.16521, -89.25408, "2026-01-26", "2026-01-26")
    assert len(df) == 2
    assert df.attrs["elevation_m"] == pytest.approx(261.0)
    assert "dry_bulb_f" in df.columns


def test_default_archive_end_lags_today():
    assert default_archive_end(as_of=date(2026, 8, 11), lag_days=3) == date(2026, 8, 8)


def test_prune_old_amy_reports_locked_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from eplus_gym_app.open_meteo_epw import _prune_old_amy

    weather = tmp_path / "eplus" / "weather"
    weather.mkdir(parents=True)
    keep = weather / "madison_amy_202508_202608.epw"
    old = weather / "madison_amy_202508_202607.epw"
    keep.write_text("new", encoding="utf-8")
    old.write_text("old", encoding="utf-8")

    def locked(self, missing_ok=True):
        raise OSError("locked")

    monkeypatch.setattr(Path, "unlink", locked)
    leftover = _prune_old_amy(weather, keep, slug="madison")
    assert leftover == ["madison_amy_202508_202607.epw"]


def test_default_calendar_window_extends_stale_answers():
    start, end = default_calendar_window(
        answers_start="2025-08-01",
        answers_end="2026-07-03",
        as_of=date(2026, 8, 11),
        lag_days=3,
    )
    assert start == "2025-08-01"
    assert end == "2026-08-08"
