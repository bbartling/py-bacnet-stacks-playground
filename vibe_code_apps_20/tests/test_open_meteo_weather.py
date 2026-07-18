"""Tests for wattlab.weather.open_meteo (Task 2: actual-year downloader + EPW guards).

TDD: written before wattlab/weather/open_meteo.py existed. No network calls —
every test injects an opener that returns API-shaped JSON bytes matching the
Open-Meteo archive endpoint (Fahrenheit / mph / UTC hourly arrays).
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest
from urllib.error import HTTPError, URLError

from wattlab.contracts import EPW_REQUIRED_VARIABLES, WeatherRequest
from wattlab.weather.epw import build_amy_epw
from wattlab.weather.open_meteo import (
    ARCHIVE_URL,
    COLUMN_MAP,
    download_archive_weather,
)

LAT = 42.33
LON = -83.05


# ---------------------------------------------------------------------------
# Fixture helpers (API-shaped JSON, no network)
# ---------------------------------------------------------------------------


def _hourly_times(start: date, hours: int) -> list[str]:
    t0 = datetime(start.year, start.month, start.day)
    return [(t0 + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M") for i in range(hours)]


def _api_payload(
    *,
    latitude: float = LAT,
    longitude: float = LON,
    start: date = date(2025, 1, 1),
    hours: int = 48,
    include_units: bool = True,
) -> dict:
    """Build an Open-Meteo archive-shaped response covering `hours` hours."""
    times = _hourly_times(start, hours)
    n = len(times)
    hourly: dict[str, list] = {"time": times}
    hourly["temperature_2m"] = [30.0 + 0.01 * i for i in range(n)]
    hourly["dew_point_2m"] = [20.0 + 0.01 * i for i in range(n)]
    hourly["relative_humidity_2m"] = [50.0 for _ in range(n)]
    hourly["surface_pressure"] = [990.0 for _ in range(n)]
    hourly["shortwave_radiation"] = [100.0 for _ in range(n)]
    hourly["direct_normal_irradiance"] = [200.0 for _ in range(n)]
    hourly["diffuse_radiation"] = [50.0 for _ in range(n)]
    hourly["wind_speed_10m"] = [8.0 for _ in range(n)]
    hourly["wind_direction_10m"] = [270.0 for _ in range(n)]
    payload: dict = {
        "latitude": latitude,
        "longitude": longitude,
        "timezone": "GMT",
        "hourly": hourly,
    }
    if include_units:
        payload["hourly_units"] = {
            "time": "iso8601",
            "temperature_2m": "\u00b0F",
            "dew_point_2m": "\u00b0F",
            "relative_humidity_2m": "%",
            "surface_pressure": "hPa",
            "shortwave_radiation": "W/m\u00b2",
            "direct_normal_irradiance": "W/m\u00b2",
            "diffuse_radiation": "W/m\u00b2",
            "wind_speed_10m": "mp/h",
            "wind_direction_10m": "\u00b0",
        }
    return payload


class RecordingOpener:
    """Opener double: returns queued payloads/exceptions, records URLs."""

    def __init__(self, results):
        # each result: bytes to return, or an Exception to raise
        self.results = list(results)
        self.urls: list[str] = []

    def __call__(self, url: str) -> bytes:
        self.urls.append(url)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def _payload_bytes(payload: dict) -> bytes:
    return json.dumps(payload).encode("utf-8")


def _request(**overrides) -> WeatherRequest:
    kwargs = dict(
        latitude=LAT,
        longitude=LON,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 2),
    )
    kwargs.update(overrides)
    return WeatherRequest(**kwargs)


def _full_year_request(**overrides) -> WeatherRequest:
    kwargs = dict(
        latitude=LAT,
        longitude=LON,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
    )
    kwargs.update(overrides)
    return WeatherRequest(**kwargs)


def _download(payload: dict, tmp_path: Path, request: WeatherRequest | None = None, **kw):
    opener = RecordingOpener([_payload_bytes(payload)])
    df, meta = download_archive_weather(
        request or _request(), tmp_path, opener=opener, **kw
    )
    return df, meta, opener


EXPECTED_COLUMNS = {
    "dry_bulb_f",
    "dew_point_f",
    "relative_humidity_pct",
    "surface_pressure_hpa",
    "shortwave_radiation_wm2",
    "direct_normal_irradiance_wm2",
    "diffuse_radiation_wm2",
    "wind_speed_mph",
    "wind_direction_deg",
}


# ---------------------------------------------------------------------------
# Mapping / URL / metadata
# ---------------------------------------------------------------------------


class TestMappingAndMeta:
    def test_column_map_covers_exact_epw_required_variables(self):
        assert set(COLUMN_MAP) == set(EPW_REQUIRED_VARIABLES)
        assert set(COLUMN_MAP.values()) == EXPECTED_COLUMNS

    def test_dataframe_maps_hourly_arrays_to_epw_columns(self, tmp_path):
        payload = _api_payload()
        df, _, _ = _download(payload, tmp_path)
        assert set(df.columns) == EXPECTED_COLUMNS
        assert len(df) == 48
        assert df["dry_bulb_f"].iloc[0] == pytest.approx(30.0)
        assert df["dew_point_f"].iloc[1] == pytest.approx(20.01)
        assert df["surface_pressure_hpa"].iloc[0] == pytest.approx(990.0)
        assert df["wind_speed_mph"].iloc[0] == pytest.approx(8.0)
        assert df["wind_direction_deg"].iloc[0] == pytest.approx(270.0)

    def test_index_is_utc_hourly_starting_at_request_start(self, tmp_path):
        df, _, _ = _download(_api_payload(), tmp_path)
        assert isinstance(df.index, pd.DatetimeIndex)
        assert str(df.index.tz) == "UTC"
        assert df.index[0] == pd.Timestamp("2025-01-01T00:00", tz="UTC")
        deltas = df.index.to_series().diff().dropna().unique()
        assert list(deltas) == [pd.Timedelta(hours=1)]

    def test_url_targets_archive_api_with_units_and_utc(self, tmp_path):
        _, _, opener = _download(_api_payload(), tmp_path)
        assert len(opener.urls) == 1
        url = opener.urls[0]
        assert url.startswith(ARCHIVE_URL)
        assert "archive-api.open-meteo.com/v1/archive" in url
        assert "temperature_unit=fahrenheit" in url
        assert "wind_speed_unit=mph" in url
        assert "timezone=UTC" in url
        assert "start_date=2025-01-01" in url
        assert "end_date=2025-01-02" in url

    def test_meta_has_sha_provenance_and_cache_info(self, tmp_path):
        payload = _api_payload()
        df, meta, _ = _download(payload, tmp_path)
        assert meta.source == "open-meteo-archive"
        # sha256 fingerprints the API response body (not the cache envelope wrapper)
        assert meta.sha256 == hashlib.sha256(_payload_bytes(payload)).hexdigest()
        assert meta.rows == len(df) == 48
        assert meta.cached_path is not None
        cached = Path(meta.cached_path)
        assert cached.exists()
        assert cached.parent == tmp_path
        assert meta.downloaded_at_utc is not None
        assert meta.downloaded_at_utc.tzinfo is not None
        assert meta.latitude == pytest.approx(LAT)
        assert meta.longitude == pytest.approx(LON)
        assert meta.start_date == date(2025, 1, 1)
        assert meta.end_date == date(2025, 1, 2)


# ---------------------------------------------------------------------------
# Cache behavior
# ---------------------------------------------------------------------------


class TestCache:
    def test_second_call_reuses_cache_without_opener(self, tmp_path):
        payload = _api_payload()
        opener = RecordingOpener([_payload_bytes(payload)])
        df1, meta1 = download_archive_weather(_request(), tmp_path, opener=opener)
        df2, meta2 = download_archive_weather(_request(), tmp_path, opener=opener)
        assert len(opener.urls) == 1  # no second network hit
        pd.testing.assert_frame_equal(df1, df2)
        assert meta1.sha256 == meta2.sha256

    def test_cache_hit_preserves_original_downloaded_at_utc(self, tmp_path):
        payload = _api_payload()
        opener = RecordingOpener([_payload_bytes(payload)])
        _, meta1 = download_archive_weather(_request(), tmp_path, opener=opener)
        first_ts = meta1.downloaded_at_utc
        assert first_ts is not None
        # Second call must not invent a new download timestamp
        _, meta2 = download_archive_weather(_request(), tmp_path, opener=opener)
        assert meta2.downloaded_at_utc == first_ts
        assert len(opener.urls) == 1

    def test_cache_envelope_stores_canonical_request_metadata(self, tmp_path):
        req = _request(allow_partial=True)
        payload = _api_payload()
        opener = RecordingOpener([_payload_bytes(payload)])
        _, meta = download_archive_weather(req, tmp_path, opener=opener)
        envelope = json.loads(Path(meta.cached_path).read_text(encoding="utf-8"))
        assert "request" in envelope
        assert "response" in envelope
        assert "downloaded_at_utc" in envelope
        stored = envelope["request"]
        assert stored["latitude"] == req.latitude
        assert stored["longitude"] == req.longitude
        assert stored["start_date"] == req.start_date.isoformat()
        assert stored["end_date"] == req.end_date.isoformat()
        assert stored["timezone"] == "UTC"
        assert stored["variables"] == list(req.variables)
        assert stored["allow_partial"] is True
        assert envelope["response"]["hourly"]["time"][0] == "2025-01-01T00:00"
        assert envelope["downloaded_at_utc"] == meta.downloaded_at_utc.isoformat()

    def test_mismatched_cached_request_metadata_forces_redownload(self, tmp_path):
        payload = _api_payload()
        opener = RecordingOpener([_payload_bytes(payload), _payload_bytes(payload)])
        _, meta1 = download_archive_weather(_request(), tmp_path, opener=opener)
        envelope = json.loads(Path(meta1.cached_path).read_text(encoding="utf-8"))
        envelope["request"]["latitude"] = 0.0  # tamper with stored request
        Path(meta1.cached_path).write_text(json.dumps(envelope), encoding="utf-8")
        df2, _ = download_archive_weather(_request(), tmp_path, opener=opener)
        assert len(opener.urls) == 2
        assert len(df2) == 48

    def test_different_request_gets_its_own_cache_entry(self, tmp_path):
        payload_a = _api_payload()
        payload_b = _api_payload(start=date(2025, 2, 1))
        opener = RecordingOpener(
            [_payload_bytes(payload_a), _payload_bytes(payload_b)]
        )
        _, meta_a = download_archive_weather(_request(), tmp_path, opener=opener)
        req_b = _request(start_date=date(2025, 2, 1), end_date=date(2025, 2, 2))
        _, meta_b = download_archive_weather(req_b, tmp_path, opener=opener)
        assert len(opener.urls) == 2
        assert meta_a.cached_path != meta_b.cached_path

    def test_corrupt_cache_is_ignored_and_redownloaded(self, tmp_path):
        payload = _api_payload()
        opener = RecordingOpener([_payload_bytes(payload), _payload_bytes(payload)])
        _, meta1 = download_archive_weather(_request(), tmp_path, opener=opener)
        Path(meta1.cached_path).write_text("{not json", encoding="utf-8")
        df2, meta2 = download_archive_weather(_request(), tmp_path, opener=opener)
        assert len(opener.urls) == 2
        assert len(df2) == 48
        # cache repaired on disk as a valid envelope
        repaired = json.loads(Path(meta2.cached_path).read_text(encoding="utf-8"))
        assert "response" in repaired and "request" in repaired

    def test_legacy_raw_payload_cache_is_ignored_and_redownloaded(self, tmp_path):
        # Pre-envelope caches were bare Open-Meteo JSON; treat as stale.
        payload = _api_payload()
        opener = RecordingOpener([_payload_bytes(payload)])
        # Seed a bare payload at the would-be cache path by downloading once...
        _, meta = download_archive_weather(_request(), tmp_path, opener=opener)
        Path(meta.cached_path).write_bytes(_payload_bytes(payload))
        opener2 = RecordingOpener([_payload_bytes(payload)])
        df2, meta2 = download_archive_weather(_request(), tmp_path, opener=opener2)
        assert len(opener2.urls) == 1
        assert "request" in json.loads(Path(meta2.cached_path).read_text(encoding="utf-8"))
        assert len(df2) == 48

    def test_cache_write_is_atomic_no_temp_files_left(self, tmp_path):
        _, meta, _ = _download(_api_payload(), tmp_path)
        leftovers = [
            p for p in tmp_path.iterdir() if p != Path(meta.cached_path)
        ]
        assert leftovers == []

    def test_cache_dir_is_created_if_missing(self, tmp_path):
        cache_dir = tmp_path / "nested" / "cache"
        opener = RecordingOpener([_payload_bytes(_api_payload())])
        _, meta = download_archive_weather(_request(), cache_dir, opener=opener)
        assert Path(meta.cached_path).parent == cache_dir


# ---------------------------------------------------------------------------
# Retries
# ---------------------------------------------------------------------------


class TestRetries:
    def test_transient_url_error_is_retried_then_succeeds(self, tmp_path):
        payload = _api_payload()
        opener = RecordingOpener(
            [
                URLError("boom"),
                URLError("boom again"),
                _payload_bytes(payload),
            ]
        )
        sleeps: list[float] = []
        df, _ = download_archive_weather(
            _request(), tmp_path, opener=opener, retries=3, sleep=sleeps.append
        )
        assert len(df) == 48
        assert len(opener.urls) == 3
        assert len(sleeps) == 2
        assert all(0 < s <= 60 for s in sleeps)  # bounded backoff

    def test_http_5xx_is_retried(self, tmp_path):
        payload = _api_payload()
        opener = RecordingOpener(
            [
                HTTPError("http://x", 503, "unavailable", None, None),
                _payload_bytes(payload),
            ]
        )
        df, _ = download_archive_weather(
            _request(), tmp_path, opener=opener, retries=3, sleep=lambda s: None
        )
        assert len(df) == 48
        assert len(opener.urls) == 2

    def test_http_429_is_retried(self, tmp_path):
        payload = _api_payload()
        opener = RecordingOpener(
            [
                HTTPError("http://x", 429, "too many requests", None, None),
                _payload_bytes(payload),
            ]
        )
        df, _ = download_archive_weather(
            _request(), tmp_path, opener=opener, retries=3, sleep=lambda s: None
        )
        assert len(df) == 48
        assert len(opener.urls) == 2

    def test_http_4xx_other_than_429_fails_immediately(self, tmp_path):
        opener = RecordingOpener(
            [HTTPError("http://x", 400, "bad request", None, None)]
        )
        with pytest.raises(HTTPError) as excinfo:
            download_archive_weather(
                _request(), tmp_path, opener=opener, retries=3, sleep=lambda s: None
            )
        assert excinfo.value.code == 400
        assert len(opener.urls) == 1

    def test_http_404_fails_immediately(self, tmp_path):
        opener = RecordingOpener(
            [HTTPError("http://x", 404, "not found", None, None)]
        )
        with pytest.raises(HTTPError) as excinfo:
            download_archive_weather(
                _request(), tmp_path, opener=opener, retries=5, sleep=lambda s: None
            )
        assert excinfo.value.code == 404
        assert len(opener.urls) == 1

    def test_timeout_error_is_retried(self, tmp_path):
        payload = _api_payload()
        opener = RecordingOpener(
            [TimeoutError("timed out"), _payload_bytes(payload)]
        )
        df, _ = download_archive_weather(
            _request(), tmp_path, opener=opener, retries=3, sleep=lambda s: None
        )
        assert len(df) == 48
        assert len(opener.urls) == 2

    def test_truncated_json_is_not_retried(self, tmp_path):
        opener = RecordingOpener([b'{"latitude": 42.3, "hour'])
        with pytest.raises(ValueError):
            download_archive_weather(
                _request(), tmp_path, opener=opener, retries=3, sleep=lambda s: None
            )
        assert len(opener.urls) == 1

    def test_retries_exhausted_raises_and_stops(self, tmp_path):
        opener = RecordingOpener([URLError("down")] * 5)
        with pytest.raises(URLError):
            download_archive_weather(
                _request(), tmp_path, opener=opener, retries=3, sleep=lambda s: None
            )
        assert len(opener.urls) == 3

    def test_validation_failure_is_not_retried(self, tmp_path):
        # coordinate mismatch is a data problem, not transient
        payload = _api_payload(latitude=55.0)
        opener = RecordingOpener([_payload_bytes(payload)] * 3)
        with pytest.raises(ValueError):
            download_archive_weather(
                _request(), tmp_path, opener=opener, retries=3, sleep=lambda s: None
            )
        assert len(opener.urls) == 1


# ---------------------------------------------------------------------------
# Response validation (coordinates, dates, arrays, timestamps, bounds, units)
# ---------------------------------------------------------------------------


class TestResponseValidation:
    def test_coordinate_mismatch_rejected(self, tmp_path):
        with pytest.raises(ValueError, match="latitude"):
            _download(_api_payload(latitude=45.0), tmp_path)

    def test_longitude_mismatch_rejected(self, tmp_path):
        with pytest.raises(ValueError, match="longitude"):
            _download(_api_payload(longitude=-90.0), tmp_path)

    def test_grid_snapped_coordinates_accepted(self, tmp_path):
        # Open-Meteo snaps to its model grid; small deltas are fine.
        df, _, _ = _download(
            _api_payload(latitude=42.40, longitude=-83.00), tmp_path
        )
        assert len(df) == 48

    def test_timestamps_outside_request_dates_rejected(self, tmp_path):
        payload = _api_payload(start=date(2024, 12, 31))
        with pytest.raises(ValueError, match="(?i)date|span|range"):
            _download(payload, tmp_path)

    def test_unequal_hourly_array_lengths_rejected(self, tmp_path):
        payload = _api_payload()
        payload["hourly"]["wind_speed_10m"] = payload["hourly"]["wind_speed_10m"][:-1]
        with pytest.raises(ValueError, match="(?i)length"):
            _download(payload, tmp_path)

    def test_missing_hourly_variable_rejected(self, tmp_path):
        payload = _api_payload()
        del payload["hourly"]["dew_point_2m"]
        with pytest.raises(ValueError, match="dew_point_2m"):
            _download(payload, tmp_path)

    def test_duplicate_timestamp_rejected(self, tmp_path):
        payload = _api_payload()
        payload["hourly"]["time"][5] = payload["hourly"]["time"][4]
        with pytest.raises(ValueError, match="(?i)duplicate"):
            _download(payload, tmp_path)

    def test_missing_hour_gap_rejected(self, tmp_path):
        payload = _api_payload()
        for key, values in payload["hourly"].items():
            del values[10]
        with pytest.raises(ValueError, match="(?i)hourly|gap|missing"):
            _download(payload, tmp_path)

    def test_non_hourly_timestamp_rejected(self, tmp_path):
        payload = _api_payload()
        payload["hourly"]["time"][3] = "2025-01-01T03:30"
        with pytest.raises(ValueError, match="(?i)hourly"):
            _download(payload, tmp_path)

    def test_null_value_rejected(self, tmp_path):
        payload = _api_payload()
        payload["hourly"]["temperature_2m"][7] = None
        with pytest.raises(ValueError, match="temperature_2m"):
            _download(payload, tmp_path)

    def test_nonfinite_value_rejected(self, tmp_path):
        payload = _api_payload()
        payload["hourly"]["surface_pressure"][0] = float("nan")
        with pytest.raises(ValueError, match="surface_pressure"):
            _download(payload, tmp_path)

    @pytest.mark.parametrize(
        ("variable", "bad_value"),
        [
            ("temperature_2m", 250.0),  # °F
            ("temperature_2m", -200.0),
            ("dew_point_2m", 250.0),
            ("relative_humidity_2m", 150.0),
            ("relative_humidity_2m", -5.0),
            ("surface_pressure", 20.0),  # hPa
            ("surface_pressure", 2000.0),
            ("shortwave_radiation", -10.0),
            ("shortwave_radiation", 3000.0),
            ("direct_normal_irradiance", -1.0),
            ("diffuse_radiation", -1.0),
            ("wind_speed_10m", -1.0),
            ("wind_speed_10m", 400.0),  # mph
            ("wind_direction_10m", 361.0),
            ("wind_direction_10m", -1.0),
        ],
    )
    def test_out_of_physical_bounds_rejected(self, tmp_path, variable, bad_value):
        payload = _api_payload()
        payload["hourly"][variable][2] = bad_value
        with pytest.raises(ValueError, match=variable):
            _download(payload, tmp_path)

    def test_missing_hourly_units_block_is_accepted(self, tmp_path):
        df, _, _ = _download(_api_payload(include_units=False), tmp_path)
        assert len(df) == 48

    @pytest.mark.parametrize(
        ("variable", "bad_unit"),
        [
            ("temperature_2m", "\u00b0C"),
            ("dew_point_2m", "K"),
            ("relative_humidity_2m", "fraction"),
            ("surface_pressure", "Pa"),
            ("shortwave_radiation", "kW/m\u00b2"),
            ("direct_normal_irradiance", "MJ/m\u00b2"),
            ("diffuse_radiation", "lux"),
            ("wind_speed_10m", "m/s"),
            ("wind_direction_10m", "rad"),
        ],
    )
    def test_wrong_hourly_units_rejected(self, tmp_path, variable, bad_unit):
        payload = _api_payload()
        payload["hourly_units"][variable] = bad_unit
        with pytest.raises(ValueError, match=variable):
            _download(payload, tmp_path)


# ---------------------------------------------------------------------------
# Annual coverage vs allow_partial
# ---------------------------------------------------------------------------


class TestCoverage:
    def test_full_year_request_with_exact_8760_rows_accepted(self, tmp_path):
        payload = _api_payload(hours=8760)
        df, meta, _ = _download(payload, tmp_path, request=_full_year_request())
        assert len(df) == 8760
        assert meta.rows == 8760

    def test_leap_year_requires_8784_rows(self, tmp_path):
        req = WeatherRequest(
            latitude=LAT,
            longitude=LON,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )
        payload = _api_payload(start=date(2024, 1, 1), hours=8784)
        df, meta, _ = _download(payload, tmp_path, request=req)
        assert len(df) == 8784
        assert meta.rows == 8784

    def test_full_year_short_response_rejected_without_allow_partial(self, tmp_path):
        payload = _api_payload(hours=8759)
        with pytest.raises(ValueError, match="(?i)partial|8760|incomplete"):
            _download(payload, tmp_path, request=_full_year_request())

    def test_full_year_short_response_accepted_with_allow_partial(self, tmp_path):
        payload = _api_payload(hours=8000)  # ends 2025-11-30T07:00
        df, meta, _ = _download(
            payload, tmp_path, request=_full_year_request(allow_partial=True)
        )
        assert len(df) == 8000
        assert meta.rows == 8000
        # meta reflects actual coverage, not the requested span
        assert meta.end_date == date(2025, 11, 30)

    def test_partial_span_request_full_coverage_ok(self, tmp_path):
        df, meta, _ = _download(_api_payload(hours=48), tmp_path)
        assert len(df) == 48

    def test_partial_span_request_short_response_rejected(self, tmp_path):
        payload = _api_payload(hours=40)  # request spans 48 hours
        with pytest.raises(ValueError, match="(?i)partial|incomplete"):
            _download(payload, tmp_path)


# ---------------------------------------------------------------------------
# build_amy_epw coverage_mode guards
# ---------------------------------------------------------------------------


def _hourly_frame(start: str, hours: int) -> pd.DataFrame:
    idx = pd.date_range(start, periods=hours, freq="1h", tz="UTC")
    return pd.DataFrame(
        {
            "dry_bulb_f": 30.0,
            "dew_point_f": 20.0,
            "relative_humidity_pct": 50.0,
            "surface_pressure_hpa": 990.0,
            "shortwave_radiation_wm2": 100.0,
            "direct_normal_irradiance_wm2": 200.0,
            "diffuse_radiation_wm2": 50.0,
            "wind_speed_mph": 8.0,
            "wind_direction_deg": 270.0,
        },
        index=idx,
    )


class TestBuildAmyEpwCoverageMode:
    def test_annual_mode_accepts_exact_8760(self, tmp_path):
        df = _hourly_frame("2025-01-01T00:00", 8760)
        out = tmp_path / "annual.epw"
        meta = build_amy_epw(df, out, coverage_mode="annual")
        assert meta["rows"] == 8760
        lines = out.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 8 + 8760  # header + one line per hour

    def test_annual_mode_accepts_leap_year_8784(self, tmp_path):
        df = _hourly_frame("2024-01-01T00:00", 8784)
        meta = build_amy_epw(df, tmp_path / "leap.epw", coverage_mode="annual")
        assert meta["rows"] == 8784

    def test_annual_mode_rejects_incomplete_year_before_writing(self, tmp_path):
        df = _hourly_frame("2025-01-01T00:00", 8000)
        out = tmp_path / "incomplete.epw"
        with pytest.raises(ValueError, match="(?i)annual|8760"):
            build_amy_epw(df, out, coverage_mode="annual")
        assert not out.exists()  # validated before writing

    def test_annual_mode_rejects_gap_even_with_8760_rows(self, tmp_path):
        df = _hourly_frame("2025-01-01T00:00", 8761)
        df = df.drop(df.index[100])  # 8760 rows but one missing hour
        out = tmp_path / "gappy.epw"
        with pytest.raises(ValueError, match="(?i)annual|missing|gap|hour"):
            build_amy_epw(df, out, coverage_mode="annual")
        assert not out.exists()

    def test_annual_mode_rejects_midyear_start(self, tmp_path):
        df = _hourly_frame("2025-06-01T00:00", 8760)
        with pytest.raises(ValueError, match="(?i)annual|calendar"):
            build_amy_epw(df, tmp_path / "midyear.epw", coverage_mode="annual")

    def test_partial_mode_accepts_partial_year(self, tmp_path):
        df = _hourly_frame("2025-02-01T00:00", 72)
        meta = build_amy_epw(df, tmp_path / "partial.epw", coverage_mode="partial")
        assert meta["rows"] == 72

    def test_partial_mode_is_default(self, tmp_path):
        df = _hourly_frame("2025-02-01T00:00", 24)
        meta = build_amy_epw(df, tmp_path / "default.epw")
        assert meta["rows"] == 24

    def test_unknown_coverage_mode_rejected(self, tmp_path):
        df = _hourly_frame("2025-01-01T00:00", 24)
        with pytest.raises(ValueError, match="coverage_mode"):
            build_amy_epw(df, tmp_path / "bad.epw", coverage_mode="monthly")

    def test_annual_mode_rejects_duplicate_timestamps_before_resample(self, tmp_path):
        # Duplicates would collapse under mean-resample; annual must reject first.
        df = _hourly_frame("2025-01-01T00:00", 8760)
        df = pd.concat([df.iloc[[0]], df])
        out = tmp_path / "dupes.epw"
        with pytest.raises(ValueError, match="(?i)duplicate"):
            build_amy_epw(df, out, coverage_mode="annual")
        assert not out.exists()

    def test_annual_mode_rejects_non_hourly_timestamps_before_resample(self, tmp_path):
        # Half-hour series that mean-resamples to a full year must still be rejected.
        idx = pd.date_range("2025-01-01T00:00", periods=8760 * 2, freq="30min", tz="UTC")
        df = pd.DataFrame(
            {
                "dry_bulb_f": 30.0,
                "dew_point_f": 20.0,
                "relative_humidity_pct": 50.0,
                "surface_pressure_hpa": 990.0,
                "shortwave_radiation_wm2": 100.0,
                "direct_normal_irradiance_wm2": 200.0,
                "diffuse_radiation_wm2": 50.0,
                "wind_speed_mph": 8.0,
                "wind_direction_deg": 270.0,
            },
            index=idx,
        )
        out = tmp_path / "halfhour.epw"
        with pytest.raises(ValueError, match="(?i)hourly"):
            build_amy_epw(df, out, coverage_mode="annual")
        assert not out.exists()

    def test_annual_mode_rejects_out_of_bounds_values(self, tmp_path):
        df = _hourly_frame("2025-01-01T00:00", 8760)
        df.iloc[10, df.columns.get_loc("dry_bulb_f")] = 250.0
        out = tmp_path / "hot.epw"
        with pytest.raises(ValueError, match="dry_bulb_f"):
            build_amy_epw(df, out, coverage_mode="annual")
        assert not out.exists()

    def test_annual_mode_rejects_nonfinite_values(self, tmp_path):
        df = _hourly_frame("2025-01-01T00:00", 8760)
        df.iloc[20, df.columns.get_loc("surface_pressure_hpa")] = float("nan")
        out = tmp_path / "nan.epw"
        with pytest.raises(ValueError, match="surface_pressure_hpa"):
            build_amy_epw(df, out, coverage_mode="annual")
        assert not out.exists()

    def test_partial_mode_still_allows_sub_hourly_resample(self, tmp_path):
        # Historical overlap-window path: partial keeps mean-resample behavior.
        idx = pd.date_range("2025-02-01T00:00", periods=48, freq="30min", tz="UTC")
        df = pd.DataFrame({"dry_bulb_f": 30.0}, index=idx)
        meta = build_amy_epw(df, tmp_path / "partial_half.epw", coverage_mode="partial")
        assert meta["rows"] == 24


# ---------------------------------------------------------------------------
# Downloader output feeds the EPW builder end-to-end (still no network)
# ---------------------------------------------------------------------------


class TestDownloadToEpw:
    def test_full_year_download_builds_annual_epw(self, tmp_path):
        payload = _api_payload(hours=8760)
        df, meta, _ = _download(
            payload, tmp_path / "cache", request=_full_year_request()
        )
        out = tmp_path / "detroit_2025.epw"
        epw_meta = build_amy_epw(
            df, out, lat=meta.latitude, lon=meta.longitude, coverage_mode="annual"
        )
        assert epw_meta["rows"] == 8760
        assert out.exists()
